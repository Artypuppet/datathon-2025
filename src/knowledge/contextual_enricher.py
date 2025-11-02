"""
Contextual text enrichment for improved embeddings.
"""

import logging
from typing import Dict, Any, List, Optional
import re

logger = logging.getLogger(__name__)


class ContextualEnricher:
    """
    Enrich chunks with domain-specific context before embedding.
    
    Adds metadata, entities, and domain examples to improve semantic matching.
    """
    
    def __init__(self, knowledge_db=None):
        """
        Initialize contextual enricher.
        
        Args:
            knowledge_db: Optional CompanyKnowledgeDB instance for rich company context
        """
        # Risk keywords that signal important context
        self.risk_keywords = [
            'tariff', 'trade', 'sanction', 'embargo', 'restriction',
            'supply chain', 'manufacturing', 'operations', 'regulation',
            'compliance', 'export', 'import', 'foreign', 'overseas'
        ]
        
        # Country/region patterns
        self.country_patterns = {
            'China': ['China', 'Chinese', 'PRC', 'mainland'],
            'United States': ['United States', 'U.S.', 'USA', 'America'],
            'EU': ['European Union', 'EU', 'Europe', 'EUR'],
            'Japan': ['Japan', 'Japanese', 'JP'],
            'Taiwan': ['Taiwan', 'Taiwanese'],
            'Vietnam': ['Vietnam', 'Vietnamese'],
            'India': ['India', 'Indian']
        }
        
        self.knowledge_db = knowledge_db
        
        logger.info(f"[INFO] ContextualEnricher initialized (DB: {'enabled' if knowledge_db else 'disabled'})")
    
    def enrich_filing_chunk(
        self,
        chunk: Dict[str, Any],
        filing_metadata: Dict[str, Any]
    ) -> str:
        """
        Enrich a filing chunk with contextual information.
        
        Uses knowledge database if available, otherwise extracts from text.
        
        Args:
            chunk: Chunk dictionary with 'text' and metadata
            filing_metadata: Document-level metadata (ticker, company, etc.)
            
        Returns:
            Enriched text with added context
        """
        text = chunk['text']
        ticker = filing_metadata.get('ticker', '').upper()
        
        # Get company knowledge from DB if available
        db_context = {}
        if self.knowledge_db and ticker:
            db_context = self.knowledge_db.get_enrichment_context(ticker)
        
        # Extract from current text (fallback or supplement)
        text_regions = self._extract_regions_from_text(text)
        text_operations = self._identify_operations(text)
        text_risks = self._identify_risk_types(text)
        
        # Merge DB knowledge with text-extracted (prefer DB for known companies)
        if db_context and db_context.get('regions'):
            # Union: DB knowledge + text mentions
            all_regions = set(db_context['regions']) | set(text_regions)
        else:
            all_regions = set(text_regions)
        
        if db_context and db_context.get('operations'):
            all_operations = set(db_context['operations']) | set(text_operations)
        else:
            all_operations = set(text_operations)
        
        if db_context and db_context.get('risk_types'):
            all_risks = set(db_context['risk_types']) | set(text_risks)
        else:
            all_risks = set(text_risks)
        
        # Build context header
        context_lines = []
        
        # Document-level context
        company_name = db_context.get('company_name') or filing_metadata.get('company', '')
        if ticker:
            context_lines.append(f"COMPANY: {company_name} ({ticker})")
        
        sector = db_context.get('sector') or filing_metadata.get('sector')
        if sector:
            context_lines.append(f"SECTOR: {sector}")
        
        # Section-level context
        if chunk.get('section_title'):
            context_lines.append(f"SECTION: {chunk['section_title']}")
        
        # Region context (richer from DB)
        if all_regions:
            regions_str = ", ".join(sorted(all_regions))
            context_lines.append(f"REGIONS_MENTIONED: {regions_str}")
        
        # Operation context (richer from DB)
        if all_operations:
            ops_str = ", ".join(sorted(all_operations))
            context_lines.append(f"OPERATIONS: {ops_str}")
        
        # Risk context (richer from DB)
        if all_risks:
            risks_str = ", ".join(sorted(all_risks))
            context_lines.append(f"RISK_TYPES: {risks_str}")
        
        # Build enriched text
        if context_lines:
            context_header = "\n".join(context_lines)
            enriched_text = f"[CONTEXT]\n{context_header}\n\n[CONTENT]\n{text}"
        else:
            enriched_text = text
        
        logger.debug(f"[DEBUG] Enriched chunk: added {len(context_lines)} context lines (DB: {bool(db_context)})")
        
        return enriched_text
    
    def enrich_regulation_text(
        self,
        text: str,
        regulation_metadata: Dict[str, Any]
    ) -> str:
        """
        Enrich a regulation text with contextual information.
        
        Args:
            text: Regulation text
            regulation_metadata: Metadata (jurisdiction, type, etc.)
            
        Returns:
            Enriched text with added context
        """
        # Extract entities from regulation
        entities = self._extract_entities_from_text(text)
        regions = self._extract_regions_from_text(text)
        affected_areas = self._identify_affected_areas(text)
        
        # Build context header
        context_lines = []
        
        # Document-level context
        if regulation_metadata.get('jurisdiction'):
            context_lines.append(f"JURISDICTION: {regulation_metadata['jurisdiction']}")
        
        if regulation_metadata.get('type'):
            context_lines.append(f"REGULATION_TYPE: {regulation_metadata['type']}")
        
        if regulation_metadata.get('identifier'):
            context_lines.append(f"REGULATION_ID: {regulation_metadata['identifier']}")
        
        # Region context
        if regions:
            regions_str = ", ".join(sorted(regions))
            context_lines.append(f"AFFECTED_REGIONS: {regions_str}")
        
        # Affected areas
        if affected_areas:
            areas_str = ", ".join(sorted(affected_areas))
            context_lines.append(f"AFFECTED_AREAS: {areas_str}")
        
        # Build enriched text
        if context_lines:
            context_header = "\n".join(context_lines)
            enriched_text = f"[CONTEXT]\n{context_header}\n\n[CONTENT]\n{text}"
        else:
            enriched_text = text
        
        return enriched_text
    
    def _extract_entities_from_text(self, text: str) -> List[str]:
        """
        Extract key entities from text.
        
        Returns:
            List of entity strings
        """
        entities = []
        
        # Extract potential tickers (A-Z, 2-5 chars)
        ticker_pattern = r'\b([A-Z]{2,5})\b'
        potential_tickers = re.findall(ticker_pattern, text)
        
        # Common company names
        company_patterns = [
            r'([A-Z][a-z]+\s+(Inc|Corp|LLC|Ltd|Co))',
        ]
        
        # Could add more sophisticated NER here
        
        return entities
    
    def _extract_regions_from_text(self, text: str) -> List[str]:
        """
        Extract mentioned countries/regions.
        
        Returns:
            List of region strings
        """
        regions = []
        text_lower = text.lower()
        
        for region, patterns in self.country_patterns.items():
            for pattern in patterns:
                if pattern.lower() in text_lower:
                    regions.append(region)
                    break
        
        return regions
    
    def _identify_operations(self, text: str) -> List[str]:
        """
        Identify types of operations mentioned.
        
        Returns:
            List of operation types
        """
        operations = []
        text_lower = text.lower()
        
        operation_patterns = {
            'Manufacturing': ['manufacturing', 'production', 'assembly', 'factory', 'plant'],
            'Supply Chain': ['supply chain', 'supplier', 'vendor', 'sourcing'],
            'Distribution': ['distribution', 'distribution channel', 'retail', 'wholesale'],
            'Research': ['research', 'development', 'r&d', 'rd'],
            'Sales': ['sales', 'revenue', 'market', 'customer'],
        }
        
        for op_type, keywords in operation_patterns.items():
            if any(keyword in text_lower for keyword in keywords):
                operations.append(op_type)
        
        return operations
    
    def _identify_risk_types(self, text: str) -> List[str]:
        """
        Identify types of risks mentioned.
        
        Returns:
            List of risk types
        """
        risks = []
        text_lower = text.lower()
        
        risk_patterns = {
            'Tariff/Trade': ['tariff', 'trade', 'customs', 'duty'],
            'Supply Chain': ['supply chain', 'supplier', 'logistics'],
            'Regulatory': ['regulation', 'compliance', 'regulatory'],
            'Political': ['political', 'geopolitical', 'government', 'embargo'],
            'Currency': ['currency', 'exchange rate', 'forex'],
            'Export/Import': ['export', 'import', 'restriction'],
        }
        
        for risk_type, keywords in risk_patterns.items():
            if any(keyword in text_lower for keyword in keywords):
                risks.append(risk_type)
        
        return risks
    
    def _identify_affected_areas(self, text: str) -> List[str]:
        """
        Identify areas/industries affected by regulation.
        
        Returns:
            List of affected areas
        """
        areas = []
        text_lower = text.lower()
        
        area_patterns = {
            'Technology': ['technology', 'semiconductor', 'chip', 'electronic'],
            'Manufacturing': ['manufacturing', 'production', 'industrial'],
            'Consumer Goods': ['consumer', 'product', 'smartphone', 'device'],
            'Financial': ['financial', 'banking', 'payment'],
            'Energy': ['energy', 'power', 'electric'],
        }
        
        for area, keywords in area_patterns.items():
            if any(keyword in text_lower for keyword in keywords):
                areas.append(area)
        
        return areas

