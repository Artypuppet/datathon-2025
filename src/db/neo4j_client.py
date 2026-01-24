"""
Neo4j Aura client for knowledge graph operations.

Manages Company, Sector, Supplier, Law, and PolymarketBet nodes
with relationships for supply chains and regulatory impact.
"""

import logging
import os
from typing import Dict, Any, List, Optional
from neo4j import GraphDatabase, ManagedTransaction

logger = logging.getLogger(__name__)


class Neo4jClient:
    """
    Client for Neo4j Aura operations.
    
    Manages knowledge graph with companies, suppliers, sectors, and legislation.
    """
    
    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None
    ):
        """
        Initialize Neo4j client.
        
        Args:
            uri: Neo4j Aura URI (e.g., neo4j+s://xxxx.databases.neo4j.io)
            user: Neo4j username
            password: Neo4j password
        """
        self.uri = uri or os.getenv('NEO4J_URI')
        self.user = user or os.getenv('NEO4J_USER')
        self.password = password or os.getenv('NEO4J_PASSWORD')
        
        if not all([self.uri, self.user, self.password]):
            raise ValueError("Neo4j credentials must be provided via env vars or constructor")
        
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        
        # Verify connection
        try:
            self.driver.verify_connectivity()
            logger.info(f"[OK] Neo4jClient connected to {self.uri}")
        except Exception as e:
            logger.error(f"[ERROR] Failed to connect to Neo4j: {e}")
            raise
    
    def close(self):
        """Close Neo4j driver connection."""
        if self.driver:
            self.driver.close()
            logger.info("[OK] Neo4j connection closed")
    
    def create_company_node(
        self,
        ticker: str,
        company_name: str,
        sector: Optional[str] = None,
        industry: Optional[str] = None,
        cik: Optional[str] = None
    ) -> bool:
        """
        Create or update a Company node.
        
        Args:
            ticker: Company ticker symbol
            company_name: Company name
            sector: Sector (e.g., "Technology")
            industry: Industry (e.g., "Consumer Electronics")
            cik: CIK number
        
        Returns:
            True if successful
        """
        logger.info(f"[INFO] Creating/updating Company node: {ticker}")
        
        def _create_company(tx: ManagedTransaction, ticker: str, company_name: str, sector: Optional[str] = None, industry: Optional[str] = None, cik: Optional[str] = None) -> Optional[Dict[str, Any]]:
            query = """
            MERGE (c:Company {ticker: $ticker})
            SET c.company_name = $company_name,
                c.sector = $sector,
                c.industry = $industry,
                c.cik = $cik,
                c.updated_at = datetime()
            RETURN c
            """
            result = tx.run(
                query,
                ticker=ticker,
                company_name=company_name,
                sector=sector,
                industry=industry,
                cik=cik
            )
            return result.single()
        
        try:
            with self.driver.session() as session:
                result = session.execute_write(
                    _create_company,
                    ticker, company_name, sector, industry, cik
                )
                logger.info(f"[OK] Company node created/updated: {ticker}")
                return True
        except Exception as e:
            logger.error(f"[ERROR] Failed to create company node: {e}")
            return False
    
    def create_sector_node(self, sector_name: str) -> bool:
        """Create or update a Sector node."""
        def _create_sector(tx, sector_name):
            query = """
            MERGE (s:Sector {name: $sector_name})
            SET s.updated_at = datetime()
            RETURN s
            """
            result = tx.run(query, sector_name=sector_name)
            return result.single()
        
        try:
            with self.driver.session() as session:
                session.execute_write(_create_sector, sector_name)
                logger.info(f"[OK] Sector node created: {sector_name}")
                return True
        except Exception as e:
            logger.error(f"[ERROR] Failed to create sector node: {e}")
            return False
    
    def create_supplier_node(self, supplier_name: str, supplier_type: Optional[str] = None) -> bool:
        """Create or update a Supplier node."""
        def _create_supplier(tx, supplier_name, supplier_type):
            query = """
            MERGE (s:Supplier {name: $supplier_name})
            SET s.supplier_type = $supplier_type,
                s.updated_at = datetime()
            RETURN s
            """
            result = tx.run(query, supplier_name=supplier_name, supplier_type=supplier_type)
            return result.single()
        
        try:
            with self.driver.session() as session:
                session.execute_write(_create_supplier, supplier_name, supplier_type)
                logger.info(f"[OK] Supplier node created: {supplier_name}")
                return True
        except Exception as e:
            logger.error(f"[ERROR] Failed to create supplier node: {e}")
            return False
    
    def create_relationships(
        self,
        ticker: str,
        relationships: List[Dict[str, Any]]
    ) -> int:
        """
        Create relationships for a company.
        
        Args:
            ticker: Company ticker
            relationships: List of relationship dicts with:
                - type: relationship type (OPERATES_IN, SUPPLIES_TO, etc.)
                - target: target node identifier
                - target_label: target node label (Sector, Supplier, Country, etc.)
                - properties: optional relationship properties
        
        Returns:
            Number of relationships created
        """
        logger.info(f"[INFO] Creating {len(relationships)} relationships for {ticker}")
        
        def _create_relationships(tx, ticker, relationships):
            created_count = 0
            
            for rel in relationships:
                rel_type = rel.get('type', '').upper()
                target = rel.get('target', '')
                target_label = rel.get('target_label', '')
                properties = rel.get('properties', {})
                
                if not all([rel_type, target, target_label]):
                    logger.warning(f"[WARN] Skipping invalid relationship: {rel}")
                    continue
                
                # Build properties string
                props_str = ', '.join([f"r.{k} = ${k}" for k in properties.keys()])
                props_dict = {k: v for k, v in properties.items()}
                
                query = f"""
                MATCH (c:Company {{ticker: $ticker}})
                MATCH (t:{target_label} {{name: $target}})
                MERGE (c)-[r:{rel_type}]->(t)
                {f'SET {props_str}' if props_str else ''}
                RETURN r
                """
                
                try:
                    result = tx.run(
                        query,
                        ticker=ticker,
                        target=target,
                        **props_dict
                    )
                    if result.single():
                        created_count += 1
                except Exception as e:
                    logger.warning(f"[WARN] Failed to create relationship {rel_type}: {e}")
                    continue
            
            return created_count
        
        try:
            with self.driver.session() as session:
                created_count = session.execute_write(
                    _create_relationships,
                    ticker, relationships
                )
                logger.info(f"[OK] Created {created_count} relationships for {ticker}")
                return created_count
        except Exception as e:
            logger.error(f"[ERROR] Failed to create relationships: {e}")
            return 0
    
    def get_company_context(
        self,
        ticker: str,
        depth: int = 2
    ) -> Dict[str, Any]:
        """
        Get company context by traversing the graph.
        
        Args:
            ticker: Company ticker
            depth: Traversal depth
        
        Returns:
            Dictionary with company info and related entities
        """
        logger.info(f"[INFO] Getting context for {ticker} (depth={depth})")
        
        def _get_context(tx, ticker, depth):
            query = f"""
            MATCH (c:Company {{ticker: $ticker}})
            OPTIONAL MATCH path = (c)-[*1..{depth}]-(related)
            RETURN c, collect(DISTINCT related) as related_nodes,
                   collect(DISTINCT relationships(path)) as relationships
            """
            result = tx.run(query, ticker=ticker)
            record = result.single()
            
            if not record:
                return None
            
            company = dict(record['c'])
            related_nodes = [dict(node) for node in record['related_nodes']]
            relationships = []
            
            for rel_list in record['relationships']:
                for rel in rel_list:
                    if rel:
                        relationships.append({
                            'type': rel.type,
                            'start': rel.start_node.get('ticker') or rel.start_node.get('name'),
                            'end': rel.end_node.get('ticker') or rel.end_node.get('name')
                        })
            
            return {
                'company': company,
                'related_nodes': related_nodes,
                'relationships': relationships
            }
        
        try:
            with self.driver.session() as session:
                context = session.execute_read(_get_context, ticker, depth)
                if context:
                    logger.info(f"[OK] Retrieved context for {ticker}")
                return context or {}
        except Exception as e:
            logger.error(f"[ERROR] Failed to get context: {e}")
            return {}
    
    def link_law_to_sectors(
        self,
        law_id: str,
        law_title: str,
        affected_sectors: List[str]
    ) -> int:
        """
        Link legislation to affected sectors.
        
        Args:
            law_id: Unique law identifier
            law_title: Law title
            affected_sectors: List of sector names
        
        Returns:
            Number of relationships created
        """
        logger.info(f"[INFO] Linking law {law_id} to {len(affected_sectors)} sectors")
        
        def _link_law(tx, law_id, law_title, affected_sectors):
            # Create Law node
            create_law_query = """
            MERGE (l:Law {id: $law_id})
            SET l.title = $law_title,
                l.updated_at = datetime()
            RETURN l
            """
            tx.run(create_law_query, law_id=law_id, law_title=law_title)
            
            # Link to sectors
            linked_count = 0
            for sector in affected_sectors:
                link_query = """
                MATCH (l:Law {id: $law_id})
                MATCH (s:Sector {name: $sector})
                MERGE (l)-[r:AFFECTS]->(s)
                RETURN r
                """
                result = tx.run(link_query, law_id=law_id, sector=sector)
                if result.single():
                    linked_count += 1
            
            return linked_count
        
        try:
            with self.driver.session() as session:
                linked_count = session.execute_write(
                    _link_law,
                    law_id, law_title, affected_sectors
                )
                logger.info(f"[OK] Linked law to {linked_count} sectors")
                return linked_count
        except Exception as e:
            logger.error(f"[ERROR] Failed to link law: {e}")
            return 0
    
    def get_companies_by_sector(self, sector: str) -> List[str]:
        """Get all company tickers in a sector."""
        def _get_companies(tx, sector):
            query = """
            MATCH (c:Company)-[:OPERATES_IN]->(s:Sector {name: $sector})
            RETURN c.ticker as ticker
            """
            result = tx.run(query, sector=sector)
            return [record['ticker'] for record in result]
        
        try:
            with self.driver.session() as session:
                tickers = session.execute_read(_get_companies, sector)
                return tickers
        except Exception as e:
            logger.error(f"[ERROR] Failed to get companies by sector: {e}")
            return []
