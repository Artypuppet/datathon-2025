"""
Stage 2: Aggregate multiple filings per company into unified knowledge graphs.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from ..utils import get_s3_client, S3Client
from ..parsers.base import DocumentType

logger = logging.getLogger(__name__)

# Optional import for metadata enrichment
try:
    from ..knowledge.metadata_cache import MetadataCache
    HAS_METADATA_CACHE = True
except ImportError:
    HAS_METADATA_CACHE = False

# Optional import for knowledge graph builder
try:
    from ..knowledge.graph_builder import KnowledgeGraphBuilder
    HAS_GRAPH_BUILDER = True
except ImportError:
    HAS_GRAPH_BUILDER = False


class CompanyAggregator:
    """
    Aggregates multiple filings (10-K, 10-Q, 8-K) per company into unified knowledge graph.
    """
    
    def __init__(self, s3_client: Optional[S3Client] = None, use_metadata_enrichment: bool = True):
        """
        Initialize company aggregator.
        
        Args:
            s3_client: S3 client instance (optional, auto-created if None)
            use_metadata_enrichment: Whether to enrich with Yahoo Finance metadata
        """
        self.s3_client = s3_client or get_s3_client()
        if not self.s3_client:
            logger.warning("[WARN] S3 client not configured, S3 operations will fail")
        
        # Initialize metadata cache if available
        self.metadata_cache = None
        if use_metadata_enrichment and HAS_METADATA_CACHE:
            try:
                self.metadata_cache = MetadataCache()
                logger.info("[INFO] Metadata enrichment enabled (Yahoo Finance)")
            except Exception as e:
                logger.warning(f"[WARN] Failed to initialize metadata cache: {e}")
        
        # Initialize knowledge graph builder if available
        self.graph_builder = None
        if HAS_GRAPH_BUILDER:
            try:
                self.graph_builder = KnowledgeGraphBuilder()
                logger.info("[INFO] Knowledge graph builder enabled")
            except Exception as e:
                logger.warning(f"[WARN] Failed to initialize knowledge graph builder: {e}")
    
    def aggregate_company(
        self,
        ticker: str,
        filing_paths: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Combine all filings for a company.
        
        Args:
            ticker: Stock ticker symbol
            filing_paths: Optional list of S3 keys to specific filings.
                         If None, discovers all filings from S3.
        
        Returns:
            Aggregated company data with merged sections, entities, timeline
        """
        ticker = ticker.upper().strip()
        logger.info(f"[INFO] Aggregating filings for {ticker}")
        
        # Load filings
        if filing_paths is None:
            filing_paths = self._discover_filings(ticker)
        
        if not filing_paths:
            logger.warning(f"[WARN] No filings found for {ticker}")
            return self._empty_aggregation(ticker)
        
        logger.info(f"[INFO] Found {len(filing_paths)} filing(s) for {ticker}")
        
        # Load and parse all filings
        filings_data = []
        for filing_path in filing_paths:
            filing_data = self._load_filing(filing_path)
            if filing_data:
                filings_data.append(filing_data)
        
        if not filings_data:
            logger.warning(f"[WARN] No valid filings loaded for {ticker}")
            return self._empty_aggregation(ticker)
        
        # Aggregate the filings
        aggregated = self._merge_filings(ticker, filings_data)
        
        logger.info(f"[OK] Aggregated {len(filings_data)} filing(s) for {ticker}")
        return aggregated
    
    def _discover_filings(self, ticker: str) -> List[str]:
        """
        Discover all filings for a ticker from S3.
        
        Looks in:
        - parsed/ (for parsed JSON files with ticker in filename)
        - parsed/filings/{ticker}/ (alternative structure)
        - input/filings/{ticker}/ (if raw files exist)
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            List of S3 keys to parsed filing files (JSON only)
        """
        if not self.s3_client:
            return []
        
        filing_keys = []
        ticker_upper = ticker.upper()
        
        # First, check for parsed filings in parsed/ directory (flat structure)
        parsed_files = self.s3_client.list_files(prefix="parsed/")
        # Filter for files that contain ticker and are JSON
        filing_keys.extend([
            f for f in parsed_files 
            if f.endswith('.json') and ticker_upper in Path(f).stem.upper()
        ])
        
        # Also check parsed/filings/{ticker}/ structure
        if not filing_keys:
            parsed_prefix = f"parsed/filings/{ticker}/"
            parsed_files = self.s3_client.list_files(prefix=parsed_prefix)
            filing_keys.extend([f for f in parsed_files if f.endswith('.json')])
        
        # Sort by filename (most recent first typically)
        filing_keys.sort(reverse=True)
        
        return filing_keys
    
    def _load_filing(self, s3_key: str) -> Optional[Dict[str, Any]]:
        """
        Load a filing from S3.
        
        Args:
            s3_key: S3 key to the filing file (should be parsed JSON)
            
        Returns:
            Parsed filing data, or None if failed
        """
        if not self.s3_client:
            return None
        
        try:
            # Only load parsed JSON files
            if not s3_key.endswith('.json'):
                logger.warning(f"[WARN] Expected JSON file, got: {s3_key}")
                return None
            
            data = self.s3_client.read_json(s3_key)
            if data:
                logger.debug(f"[DEBUG] Loaded filing: {Path(s3_key).name}")
                return data
            else:
                logger.warning(f"[WARN] Empty or invalid JSON: {s3_key}")
                return None
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to load filing {s3_key}: {e}")
            return None
    
    def _merge_filings(self, ticker: str, filings_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge multiple filings into unified company data.
        
        Args:
            ticker: Stock ticker symbol
            filings_data: List of parsed filing dictionaries
            
        Returns:
            Aggregated company data
        """
        # Separate filings by type
        filing_10k = []
        filing_10q = []
        filing_8k = []
        
        for filing in filings_data:
            filing_type = filing.get('filing_type', '').upper()
            if '10-K' in filing_type:
                filing_10k.append(filing)
            elif '10-Q' in filing_type:
                filing_10q.append(filing)
            elif '8-K' in filing_type:
                filing_8k.append(filing)
        
        # Sort by date (most recent first)
        filing_10k.sort(key=lambda x: x.get('filing_date', ''), reverse=True)
        filing_10q.sort(key=lambda x: x.get('filing_date', ''), reverse=True)
        filing_8k.sort(key=lambda x: x.get('filing_date', ''), reverse=True)
        
        # Extract base metadata from most recent 10-K
        latest_10k = filing_10k[0] if filing_10k else {}
        company_name = latest_10k.get('company_name') or ticker
        cik = latest_10k.get('cik', '')
        
        # Merge sections by type
        aggregated_sections = self._merge_sections(filing_10k, filing_10q, filing_8k)
        
        # Build temporal timeline
        temporal_timeline = self._build_timeline(filing_10k, filing_10q, filing_8k)
        
        # Extract entities across all filings (simple extraction for MVP)
        entities = self._extract_entities(filing_10k + filing_10q + filing_8k)
        
        # Build knowledge graph triples
        knowledge_graph_triples = self._build_knowledge_graph_triples(
            ticker, aggregated_sections, entities, filing_10k, filing_10q, filing_8k
        )
        
        # Build aggregated structure
        aggregated = {
            'ticker': ticker,
            'company_name': company_name,
            'cik': cik,
            'aggregated_sections': aggregated_sections,
            'entities': entities,
            'temporal_timeline': temporal_timeline,
            'knowledge_graph': knowledge_graph_triples,
            'metadata': {
                'latest_10k_date': filing_10k[0].get('filing_date') if filing_10k else None,
                'latest_10q_date': filing_10q[0].get('filing_date') if filing_10q else None,
                'total_filings': len(filings_data),
                'filing_counts': {
                    '10-K': len(filing_10k),
                    '10-Q': len(filing_10q),
                    '8-K': len(filing_8k)
                },
                'aggregated_at': datetime.now().isoformat()
            },
            'source_filings': [
                {
                    'type': f.get('filing_type'),
                    'date': f.get('filing_date'),
                    'source_file': f.get('source_file')
                }
                for f in filings_data
            ]
        }
        
        # Enrich with external metadata (Yahoo Finance)
        if self.metadata_cache:
            try:
                aggregated = self.metadata_cache.enrich_company_data(ticker, aggregated)
                # Also update metadata dict
                metadata = self.metadata_cache.get_company_metadata(ticker)
                if metadata:
                    aggregated['metadata'].update({
                        'sector': metadata.get('sector', ''),
                        'industry': metadata.get('industry', ''),
                        'country': metadata.get('country', ''),
                    })
                    # Merge risk_types from Yahoo Finance with extracted ones
                    yahoo_risk_types = set(metadata.get('risk_types', []))
                    extracted_risk_types = set(aggregated['entities'].get('risk_types', []))
                    aggregated['entities']['risk_types'] = sorted(list(yahoo_risk_types | extracted_risk_types))
            except Exception as e:
                logger.warning(f"[WARN] Metadata enrichment failed for {ticker}: {e}")
        
        return aggregated
    
    def _merge_sections(
        self,
        filing_10k: List[Dict],
        filing_10q: List[Dict],
        filing_8k: List[Dict]
    ) -> Dict[str, Any]:
        """
        Merge sections across filings, prioritizing most recent data.
        
        Args:
            filing_10k: List of 10-K filings (sorted by date, most recent first)
            filing_10q: List of 10-Q filings (sorted by date, most recent first)
            filing_8k: List of 8-K filings (sorted by date, most recent first)
            
        Returns:
            Dictionary of merged sections
        """
        merged = {
            'business': [],
            'risk_factors': [],
            'significant_events': [],
            'other': []
        }
        
        # Merge from 10-K (most authoritative for business and risk factors)
        if filing_10k:
            latest_10k = filing_10k[0]
            sections = latest_10k.get('sections', [])
            
            for section in sections:
                section_id = section.get('section_id', '').lower()
                title = section.get('title', '').lower()
                text = section.get('text', '')
                
                # Improved categorization: check section_id exactly and title
                # Business sections: item_1 (exact match), or title contains "Business" (but not "Risk")
                is_business = (
                    section_id == 'item_1' or
                    section_id.startswith('item_1') and section_id not in ['item_1a', 'item_1b', 'item_1c'] or
                    (title and 'business' in title and 'risk' not in title and 'financial' not in title)
                )
                
                # Risk factors: item_1a (exact match) or title contains "Risk Factor"
                is_risk = (
                    section_id == 'item_1a' or
                    section_id.startswith('item_1a') or
                    (title and ('risk factor' in title or 'risk factors' in title))
                )
                
                if is_business:
                    merged['business'].append({
                        'title': section.get('title'),
                        'text': text,
                        'source': '10-K',
                        'date': latest_10k.get('filing_date')
                    })
                elif is_risk:
                    merged['risk_factors'].append({
                        'title': section.get('title'),
                        'text': text,
                        'source': '10-K',
                        'date': latest_10k.get('filing_date')
                    })
                else:
                    merged['other'].append({
                        'title': section.get('title'),
                        'text': text,
                        'source': '10-K',
                        'date': latest_10k.get('filing_date')
                    })
        
        # Add recent 10-Q sections
        # 10-Q structure: Item 1A (Risk Factors), Item 2 (Properties), Item 4 (Controls and Procedures)
        if filing_10q:
            for filing in filing_10q:
                sections = filing.get('sections', [])
                filing_date = filing.get('filing_date')
                filing_type = filing.get('filing_type', '10-Q')
                
                for section in sections:
                    section_id = section.get('section_id', '').lower()
                    title = section.get('title', '').lower()
                    
                    # Risk factors: Item 1A
                    is_risk = (
                        section_id == 'item_1a' or
                        section_id.startswith('item_1a') or
                        (title and 'risk factor' in title)
                    )
                    
                    # Properties: Item 2 (this is unique to 10-Q)
                    is_properties = (
                        section_id == 'item_2' or
                        section_id.startswith('item_2') or
                        (title and 'properties' in title)
                    )
                    
                    # Controls and Procedures: Item 4 (10-Q specific)
                    is_controls = (
                        section_id == 'item_4' or
                        section_id.startswith('item_4') or
                        (title and ('controls' in title or 'procedures' in title))
                    )
                    
                    section_data = {
                        'title': section.get('title'),
                        'text': section.get('text', ''),
                        'source': filing_type,
                        'filing_type': filing_type,
                        'filing_date': filing_date,
                        'section_id': section.get('section_id')
                    }
                    
                    if is_risk:
                        merged['risk_factors'].append(section_data)
                    elif is_properties:
                        # Properties could go to "other" or a new category
                        # For now, add to "other" with a note that it's properties
                        merged['other'].append(section_data)
                    elif is_controls:
                        # Controls and procedures could go to "other" or business
                        # Since it's governance-related, adding to "other"
                        merged['other'].append(section_data)
                    else:
                        # Fallback: add to "other" if it doesn't match known patterns
                        merged['other'].append(section_data)
        
        # Add 8-K events (these are significant events)
        for filing in filing_8k[:5]:  # Limit to 5 most recent 8-Ks
            sections = filing.get('sections', [])
            for section in sections:
                merged['significant_events'].append({
                    'title': section.get('title'),
                    'text': section.get('text', ''),
                    'source': '8-K',
                    'date': filing.get('filing_date')
                })
        
        return merged
    
    def _build_knowledge_graph_triples(
        self,
        ticker: str,
        aggregated_sections: Dict[str, Any],
        entities: Dict[str, Any],
        filing_10k: List[Dict],
        filing_10q: List[Dict],
        filing_8k: List[Dict]
    ) -> List[Dict[str, str]]:
        """
        Build knowledge graph triples from aggregated data.
        
        Returns triples in format: [{"subject": "...", "relation": "...", "object": "..."}]
        
        Args:
            ticker: Company ticker
            aggregated_sections: Merged sections dictionary
            entities: Extracted entities dictionary
            filing_10k: 10-K filings
            filing_10q: 10-Q filings
            filing_8k: 8-K filings
            
        Returns:
            List of triple dictionaries
        """
        triples = []
        company_name = None
        
        # Get company name from first available filing
        for filing_list in [filing_10k, filing_10q, filing_8k]:
            if filing_list:
                company_name = filing_list[0].get('company_name', ticker)
                break
        
        if not company_name:
            company_name = ticker
        
        # Company basic properties (from metadata)
        if filing_10k:
            latest_10k = filing_10k[0]
            sector = latest_10k.get('sector') or entities.get('sector')
            industry = latest_10k.get('industry') or entities.get('industry')
            country = latest_10k.get('country') or entities.get('country')
            
            if sector:
                triples.append({
                    'subject': company_name,
                    'relation': 'HAS_SECTOR',
                    'object': sector
                })
            if industry:
                triples.append({
                    'subject': company_name,
                    'relation': 'HAS_INDUSTRY',
                    'object': industry
                })
            if country:
                triples.append({
                    'subject': company_name,
                    'relation': 'OPERATES_IN',
                    'object': country
                })
        
        # Country relationships
        for country in entities.get('countries', []):
            triples.append({
                'subject': company_name,
                'relation': 'OPERATES_IN',
                'object': country
            })
        
        # Region relationships
        for region in entities.get('regions', []):
            triples.append({
                'subject': company_name,
                'relation': 'OPERATES_IN_REGION',
                'object': region
            })
        
        # Operations relationships
        for operation in entities.get('operations', []):
            triples.append({
                'subject': company_name,
                'relation': 'HAS_OPERATION',
                'object': operation
            })
        
        # Risk type relationships
        for risk_type in entities.get('risk_types', []):
            triples.append({
                'subject': company_name,
                'relation': 'HAS_RISK_TYPE',
                'object': risk_type
            })
        
        # Extract relationships from sections (if graph builder available)
        if self.graph_builder:
            try:
                # Create temporary aggregated data structure for graph builder
                temp_aggregated = {
                    'ticker': ticker,
                    'company_name': company_name,
                    'entities': entities,
                    'aggregated_sections': aggregated_sections,
                    'cik': filing_10k[0].get('cik', '') if filing_10k else '',
                    'metadata': {
                        'sector': filing_10k[0].get('sector', '') if filing_10k else '',
                        'industry': filing_10k[0].get('industry', '') if filing_10k else '',
                    },
                    'source_filings': []
                }
                
                # Build graph using graph builder
                graph = self.graph_builder.build_graph(temp_aggregated)
                
                # Convert relationships to triples format
                for rel in graph.get('relationships', []):
                    triples.append({
                        'subject': rel.get('source', ''),
                        'relation': rel.get('type', ''),
                        'object': rel.get('target', '')
                    })
            except Exception as e:
                logger.warning(f"[WARN] Failed to extract relationships from graph builder: {e}")
        
        # Deduplicate triples (same subject-relation-object)
        seen = set()
        unique_triples = []
        for triple in triples:
            key = (triple['subject'], triple['relation'], triple['object'])
            if key not in seen:
                seen.add(key)
                unique_triples.append(triple)
        
        logger.info(f"[INFO] Built {len(unique_triples)} knowledge graph triple(s)")
        return unique_triples
    
    def _build_timeline(
        self,
        filing_10k: List[Dict],
        filing_10q: List[Dict],
        filing_8k: List[Dict]
    ) -> List[Dict[str, Any]]:
        """
        Build temporal timeline of filings and events.
        
        Args:
            filing_10k, filing_10q, filing_8k: Lists of filings
            
        Returns:
            List of timeline entries
        """
        timeline = []
        
        for filing in filing_10k + filing_10q + filing_8k:
            timeline.append({
                'date': filing.get('filing_date'),
                'type': filing.get('filing_type'),
                'source_file': filing.get('source_file'),
                'event_type': 'filing'
            })
        
        # Sort by date (most recent first)
        timeline.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        return timeline
    
    def _extract_entities(self, filings: List[Dict]) -> Dict[str, List[str]]:
        """
        Extract simple entities from filings (MVP: basic keyword extraction).
        
        Args:
            filings: List of filing dictionaries
            
        Returns:
            Dictionary of entity types and values
        """
        entities = {
            'countries': set(),
            'regions': set(),
            'products': set(),
            'operations': set(),
            'risk_types': set()
        }
        
        # Simple keyword-based extraction (MVP)
        country_keywords = ['china', 'india', 'japan', 'taiwan', 'vietnam', 'korea', 
                           'united states', 'usa', 'eu', 'europe', 'uk', 'germany']
        
        operation_keywords = ['manufacturing', 'production', 'supply chain', 
                             'operations', 'factory', 'plant']
        
        # Risk type keywords (extract from risk factors sections)
        risk_type_patterns = {
            'Tariff/Trade': ['tariff', 'trade war', 'trade dispute', 'trade restriction', 'import', 'export restriction'],
            'Regulatory': ['regulation', 'regulatory change', 'compliance', 'regulatory risk', 'new regulation'],
            'Supply Chain': ['supply chain', 'supplier risk', 'sourcing risk', 'manufacturing disruption'],
            'Market': ['market risk', 'competitive', 'competition', 'market condition'],
            'Currency/FX': ['currency risk', 'foreign exchange', 'fx risk', 'exchange rate', 'currency fluctuation'],
            'Technology': ['cybersecurity', 'data breach', 'privacy risk', 'technology risk', 'cyber attack'],
            'Geopolitical': ['geopolitical', 'political risk', 'sanctions', 'embargo', 'political uncertainty'],
            'Climate/Environmental': ['climate', 'environmental risk', 'carbon', 'sustainability risk', 'climate change'],
            'Credit/Financial': ['credit risk', 'financial risk', 'liquidity risk', 'debt risk', 'financial condition']
        }
        
        for filing in filings:
            sections = filing.get('sections', [])
            for section in sections:
                text = section.get('text', '').lower()
                title = section.get('title', '').lower()
                
                # Extract countries/regions
                for keyword in country_keywords:
                    if keyword in text:
                        entities['countries'].add(keyword.title())
                
                # Extract operations
                for keyword in operation_keywords:
                    if keyword in text:
                        entities['operations'].add(keyword.title())
                
                # Extract risk types (especially from risk factors sections)
                if 'risk' in title or 'risk factor' in title:
                    for risk_type, keywords in risk_type_patterns.items():
                        if any(kw in text for kw in keywords):
                            entities['risk_types'].add(risk_type)
        
        # Convert sets to lists
        return {
            'countries': sorted(list(entities['countries'])),
            'regions': sorted(list(entities['regions'])),
            'products': sorted(list(entities['products'])),
            'operations': sorted(list(entities['operations'])),
            'risk_types': sorted(list(entities['risk_types']))
        }
    
    def _empty_aggregation(self, ticker: str) -> Dict[str, Any]:
        """Return empty aggregation structure for a ticker."""
        return {
            'ticker': ticker,
            'company_name': ticker,
            'cik': '',
            'aggregated_sections': {
                'business': [],
                'risk_factors': [],
                'significant_events': [],
                'other': []
            },
            'entities': {
                'countries': [],
                'regions': [],
                'products': [],
                'operations': []
            },
            'temporal_timeline': [],
            'metadata': {
                'latest_10k_date': None,
                'latest_10q_date': None,
                'total_filings': 0,
                'filing_counts': {'10-K': 0, '10-Q': 0, '8-K': 0},
                'aggregated_at': datetime.now().isoformat()
            },
            'knowledge_graph': [],
            'source_filings': []
        }


class AggregateStage:
    """Pipeline stage for aggregating company filings."""
    
    def __init__(self, s3_client: Optional[S3Client] = None):
        """
        Initialize aggregation stage.
        
        Args:
            s3_client: S3 client instance (optional)
        """
        self.aggregator = CompanyAggregator(s3_client=s3_client)
        self.s3_client = s3_client or get_s3_client()
        logger.info("[INFO] AggregateStage initialized")
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute aggregation stage.
        
        Args:
            context: Pipeline context containing parsed_key or file_key
            
        Returns:
            Updated context with aggregation results
        """
        # Determine ticker from context
        ticker = context.get('ticker')
        if not ticker:
            # Try to extract from file path
            file_key = context.get('file_key') or context.get('parsed_key', '')
            if file_key:
                # Extract ticker from path like "parsed/filings/AAPL/..."
                parts = file_key.split('/')
                if len(parts) >= 3 and parts[1] == 'filings':
                    ticker = parts[2].upper()
        
        if not ticker:
            logger.warning("[WARN] No ticker found in context, skipping aggregation")
            context['aggregation_status'] = 'skipped'
            return context
        
        logger.info(f"[INFO] AggregateStage: Processing {ticker}")
        
        try:
            # Aggregate company filings
            aggregated_data = self.aggregator.aggregate_company(ticker)
            
            # Save to S3
            if self.s3_client:
                output_key = f"aggregated/companies/{ticker}.json"
                if self.s3_client.write_json(aggregated_data, output_key):
                    logger.info(f"[OK] Saved aggregated data: {output_key}")
                    context.update({
                        'aggregation_status': 'success',
                        'aggregated_key': output_key,
                        'ticker': ticker,
                        'total_filings': aggregated_data['metadata']['total_filings']
                    })
                else:
                    raise Exception("Failed to save aggregated data to S3")
            else:
                context.update({
                    'aggregation_status': 'success',
                    'aggregated_data': aggregated_data,
                    'ticker': ticker
                })
            
            return context
            
        except Exception as e:
            logger.error(f"[ERROR] AggregateStage failed: {e}", exc_info=True)
            context.update({
                'aggregation_status': 'failed',
                'aggregation_error': str(e)
            })
            return context
    
    def can_execute(self, context: Dict[str, Any]) -> bool:
        """
        Check if aggregation stage can execute.
        
        Args:
            context: Pipeline context
            
        Returns:
            True if stage can execute
        """
        return (
            self.s3_client is not None and
            (context.get('ticker') or context.get('file_key') or context.get('parsed_key'))
        )

