"""
Knowledge Graph Builder with Neo4j-compatible output.

Builds knowledge graphs from aggregated company data with Neo4j import format.
"""

import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import json
from datetime import datetime

logger = logging.getLogger(__name__)


class KnowledgeGraphBuilder:
    """
    Constructs knowledge graphs from aggregated company data.
    
    Outputs Neo4j-compatible format (nodes and relationships) that can be
    imported via Cypher queries or Neo4j's import tools.
    """
    
    def __init__(self):
        """Initialize knowledge graph builder."""
        logger.info("[INFO] KnowledgeGraphBuilder initialized")
    
    def build_graph(self, aggregated_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build knowledge graph from aggregated company data.
        
        Args:
            aggregated_data: Aggregated company data from CompanyAggregator
            
        Returns:
            Knowledge graph dictionary with Neo4j-compatible structure
        """
        ticker = aggregated_data.get('ticker', '').upper()
        company_name = aggregated_data.get('company_name', ticker)
        
        logger.info(f"[INFO] Building knowledge graph for {ticker}")
        
        nodes = []
        relationships = []
        
        # 1. Company Node
        company_node = {
            'id': ticker,
            'labels': ['Company'],
            'properties': {
                'ticker': ticker,
                'company_name': company_name,
                'cik': aggregated_data.get('cik', ''),
                'sector': aggregated_data.get('metadata', {}).get('sector', ''),
                'industry': aggregated_data.get('metadata', {}).get('industry', ''),
            }
        }
        nodes.append(company_node)
        
        # 2. Extract entities and create nodes
        entities = aggregated_data.get('entities', {})
        
        # Country/Region nodes
        for country in entities.get('countries', []):
            node = self._create_or_get_node(
                nodes, 
                country, 
                'Country',
                {'name': country}
            )
            # Create relationship: Company -> OPERATES_IN -> Country
            rel = {
                'source': ticker,
                'target': country,
                'type': 'OPERATES_IN',
                'properties': {
                    'evidence': self._find_evidence(aggregated_data, country),
                    'confidence': 0.8  # MVP: Fixed confidence
                }
            }
            relationships.append(rel)
        
        # 3. Operations nodes
        for operation in entities.get('operations', []):
            node = self._create_or_get_node(
                nodes,
                operation,
                'Operation',
                {'name': operation, 'type': 'business_operation'}
            )
            # Create relationship: Company -> HAS_OPERATION -> Operation
            rel = {
                'source': ticker,
                'target': operation,
                'type': 'HAS_OPERATION',
                'properties': {
                    'evidence': self._find_evidence(aggregated_data, operation),
                    'confidence': 0.7
                }
            }
            relationships.append(rel)
        
        # 4. Extract relationships from sections (simple pattern matching)
        section_rels = self._extract_relationships_from_sections(aggregated_data, ticker)
        relationships.extend(section_rels)
        
        # 5. Build graph structure
        graph = {
            'nodes': nodes,
            'relationships': relationships,
            'metadata': {
                'ticker': ticker,
                'total_nodes': len(nodes),
                'total_relationships': len(relationships),
                'sources': [
                    f.get('source_file') 
                    for f in aggregated_data.get('source_filings', [])
                ],
                'built_at': datetime.now().isoformat()
            }
        }
        
        logger.info(f"[OK] Built graph: {len(nodes)} nodes, {len(relationships)} relationships")
        return graph
    
    def _create_or_get_node(
        self,
        nodes: List[Dict],
        node_id: str,
        labels: str,
        properties: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a new node or return existing one.
        
        Args:
            nodes: List of existing nodes
            node_id: Unique identifier for the node
            labels: Node label (e.g., 'Country', 'Operation')
            properties: Node properties
            
        Returns:
            Node dictionary
        """
        # Check if node already exists
        for node in nodes:
            if node['id'] == node_id:
                # Merge properties
                node['properties'].update(properties)
                return node
        
        # Create new node
        node = {
            'id': node_id,
            'labels': [labels] if isinstance(labels, str) else labels,
            'properties': properties
        }
        nodes.append(node)
        return node
    
    def _find_evidence(self, aggregated_data: Dict[str, Any], entity: str) -> List[str]:
        """
        Find evidence for an entity in aggregated sections.
        
        Args:
            aggregated_data: Aggregated company data
            entity: Entity name to search for
            
        Returns:
            List of section titles containing the entity
        """
        evidence = []
        entity_lower = entity.lower()
        
        sections = aggregated_data.get('aggregated_sections', {})
        for section_type, section_list in sections.items():
            for section in section_list:
                text = section.get('text', '').lower()
                if entity_lower in text:
                    evidence.append(section.get('title', section_type))
        
        return evidence[:5]  # Limit to 5 pieces of evidence
    
    def _extract_relationships_from_sections(
        self,
        aggregated_data: Dict[str, Any],
        company_id: str
    ) -> List[Dict[str, Any]]:
        """
        Extract relationships from section text using pattern matching.
        
        Args:
            aggregated_data: Aggregated company data
            company_id: Company ticker symbol
            
        Returns:
            List of relationship dictionaries
        """
        relationships = []
        
        # Patterns for relationship extraction
        patterns = [
            (r'manufactur.*?in\s+([A-Z][a-z]+)', 'MANUFACTURES_IN', 'Country'),
            (r'operat.*?in\s+([A-Z][a-z]+)', 'OPERATES_IN', 'Country'),
            (r'supply.*?chain.*?in\s+([A-Z][a-z]+)', 'SUPPLY_CHAIN_IN', 'Country'),
        ]
        
        sections = aggregated_data.get('aggregated_sections', {})
        for section_list in sections.values():
            for section in section_list:
                text = section.get('text', '')
                
                # Simple pattern matching (MVP)
                import re
                for pattern, rel_type, target_label in patterns:
                    matches = re.findall(pattern, text, re.IGNORECASE)
                    for match in matches[:3]:  # Limit matches per section
                        if match and len(match) > 2:  # Valid entity
                            target_id = match.strip()
                            relationships.append({
                                'source': company_id,
                                'target': target_id,
                                'type': rel_type,
                                'properties': {
                                    'evidence': [section.get('title', 'Unknown')],
                                    'confidence': 0.6,
                                    'source_section': section.get('source', 'unknown')
                                }
                            })
        
        return relationships
    
    def to_neo4j_cypher(self, graph: Dict[str, Any]) -> str:
        """
        Convert knowledge graph to Neo4j Cypher import statements.
        
        Args:
            graph: Knowledge graph dictionary
            
        Returns:
            Cypher query string
        """
        cypher_statements = []
        
        # Create nodes
        for node in graph['nodes']:
            labels = ':'.join(node['labels'])
            props = self._format_properties(node['properties'])
            cypher_statements.append(
                f"CREATE (n:{labels} {props});"
            )
        
        # Create relationships
        for rel in graph['relationships']:
            props = self._format_properties(rel.get('properties', {}))
            cypher_statements.append(
                f"MATCH (a {{id: '{rel['source']}'}}), (b {{id: '{rel['target']}'}})"
                f" CREATE (a)-[r:{rel['type']} {props}]->(b);"
            )
        
        return '\n'.join(cypher_statements)
    
    def to_neo4j_csv(self, graph: Dict[str, Any], output_dir: Path) -> Dict[str, Path]:
        """
        Export graph to Neo4j CSV import format.
        
        Args:
            graph: Knowledge graph dictionary
            output_dir: Directory to save CSV files
            
        Returns:
            Dictionary mapping file type to file path
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        files = {}
        
        # Nodes CSV
        nodes_file = output_dir / 'nodes.csv'
        with open(nodes_file, 'w', encoding='utf-8') as f:
            # Header
            f.write('id:ID,labels:LABEL,company_name,sector,industry,country\n')
            
            for node in graph['nodes']:
                labels = ':'.join(node['labels'])
                props = node['properties']
                f.write(f"{node['id']},{labels},{props.get('company_name', '')},"
                       f"{props.get('sector', '')},{props.get('industry', '')},"
                       f"{props.get('country', '')}\n")
        
        files['nodes'] = nodes_file
        
        # Relationships CSV
        rels_file = output_dir / 'relationships.csv'
        with open(rels_file, 'w', encoding='utf-8') as f:
            # Header
            f.write(':START_ID,:END_ID,:TYPE,evidence,confidence\n')
            
            for rel in graph['relationships']:
                props = rel.get('properties', {})
                evidence = '|'.join(props.get('evidence', []))
                confidence = props.get('confidence', 0.5)
                f.write(f"{rel['source']},{rel['target']},{rel['type']},"
                       f"{evidence},{confidence}\n")
        
        files['relationships'] = rels_file
        
        return files
    
    def _format_properties(self, properties: Dict[str, Any]) -> str:
        """Format properties dictionary as Cypher property string."""
        props_str = ', '.join(
            f"{k}: '{v}'" if isinstance(v, str) else f"{k}: {v}"
            for k, v in properties.items()
        )
        return '{' + props_str + '}' if props_str else '{}'
    
    def save_graph(self, graph: Dict[str, Any], output_path: Path, format: str = 'json') -> bool:
        """
        Save knowledge graph to file.
        
        Args:
            graph: Knowledge graph dictionary
            output_path: Path to save file
            format: 'json', 'cypher', or 'csv'
            
        Returns:
            True if successful
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            if format == 'json':
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(graph, f, indent=2, ensure_ascii=False)
            
            elif format == 'cypher':
                cypher = self.to_neo4j_cypher(graph)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(cypher)
            
            elif format == 'csv':
                self.to_neo4j_csv(graph, output_path.parent)
            
            else:
                logger.error(f"[ERROR] Unknown format: {format}")
                return False
            
            logger.info(f"[OK] Saved graph to {output_path} ({format})")
            return True
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to save graph: {e}")
            return False

