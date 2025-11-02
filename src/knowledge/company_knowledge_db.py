"""
Company Knowledge Database: Stores extracted knowledge for S&P 500 companies.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from collections import defaultdict

logger = logging.getLogger(__name__)


class CompanyKnowledgeDB:
    """
    Database of company-specific knowledge extracted from filings.
    
    Stores:
    - Regions of operation
    - Types of operations (manufacturing, R&D, sales, etc.)
    - Common risk types
    - Sectors/industries
    - Key relationships (suppliers, partners, etc.)
    """
    
    def __init__(self, db_path: Optional[Path] = None, use_external_data: bool = True):
        """
        Initialize knowledge database.
        
        Args:
            db_path: Path to JSON database file (default: data/company_knowledge.json)
            use_external_data: Whether to use external data providers (Yahoo Finance, etc.)
        """
        if db_path is None:
            db_path = Path("data/company_knowledge.json")
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # In-memory database
        self.db: Dict[str, Dict[str, Any]] = {}
        
        # Initialize external data provider if requested
        self.data_provider = None
        if use_external_data:
            try:
                from .data_providers import CompanyDataProvider
                self.data_provider = CompanyDataProvider(use_yahoo=True, use_fmp=False)
                logger.info("[INFO] External data provider enabled")
            except Exception as e:
                logger.warning(f"[WARN] Failed to initialize data provider: {e}")
        
        # Load existing database if it exists
        self.load()
        
        logger.info(f"[INFO] CompanyKnowledgeDB initialized with {len(self.db)} companies")
    
    def load(self) -> None:
        """Load database from disk."""
        if self.db_path.exists():
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    self.db = json.load(f)
                logger.info(f"[OK] Loaded {len(self.db)} companies from {self.db_path}")
            except Exception as e:
                logger.warning(f"[WARN] Failed to load database: {e}, starting fresh")
                self.db = {}
        else:
            self.db = {}
    
    def save(self) -> None:
        """Save database to disk."""
        try:
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump(self.db, f, indent=2, ensure_ascii=False)
            logger.info(f"[OK] Saved {len(self.db)} companies to {self.db_path}")
        except Exception as e:
            logger.error(f"[ERROR] Failed to save database: {e}")
            raise
    
    def get_company(self, ticker: str, fetch_if_missing: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get knowledge for a company.
        
        Args:
            ticker: Company ticker (e.g., "AAPL")
            fetch_if_missing: If True and company not in DB, fetch from external provider
            
        Returns:
            Company knowledge dict or None if not found
        """
        ticker = ticker.upper()
        
        # If not in DB and fetch_if_missing, try external provider
        if ticker not in self.db and fetch_if_missing and self.data_provider:
            self.update_from_external_data(ticker)
        
        return self.db.get(ticker)
    
    def update_from_external_data(self, ticker: str) -> bool:
        """
        Fetch and update company knowledge from external data provider.
        
        Args:
            ticker: Company ticker symbol
            
        Returns:
            True if successful, False otherwise
        """
        if not self.data_provider:
            return False
        
        try:
            existing = self.db.get(ticker.upper(), {})
            enriched = self.data_provider.enrich_company_knowledge(ticker, existing)
            
            if enriched:
                # Update database
                self.db[ticker.upper()] = enriched
                logger.info(f"[OK] Updated {ticker} from external data provider")
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"[WARN] Failed to fetch external data for {ticker}: {e}")
            return False
    
    def update_company(
        self,
        ticker: str,
        regions: Optional[List[str]] = None,
        operations: Optional[List[str]] = None,
        risk_types: Optional[List[str]] = None,
        sector: Optional[str] = None,
        company_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Update company knowledge (merges with existing).
        
        Args:
            ticker: Company ticker
            regions: List of regions/countries
            operations: List of operation types
            risk_types: List of risk types
            sector: Industry sector
            company_name: Full company name
            metadata: Additional metadata
        """
        ticker = ticker.upper()
        
        if ticker not in self.db:
            self.db[ticker] = {
                'ticker': ticker,
                'company_name': company_name,
                'sector': sector,
                'regions': [],
                'operations': [],
                'risk_types': [],
                'metadata': metadata or {},
                'sources': [],  # Track which filings contributed
                'last_updated': None
            }
        
        # Merge new data
        if regions:
            existing_regions = set(self.db[ticker]['regions'])
            new_regions = set(regions)
            self.db[ticker]['regions'] = sorted(list(existing_regions | new_regions))
        
        if operations:
            existing_ops = set(self.db[ticker]['operations'])
            new_ops = set(operations)
            self.db[ticker]['operations'] = sorted(list(existing_ops | new_ops))
        
        if risk_types:
            existing_risks = set(self.db[ticker]['risk_types'])
            new_risks = set(risk_types)
            self.db[ticker]['risk_types'] = sorted(list(existing_risks | new_risks))
        
        if sector and not self.db[ticker]['sector']:
            self.db[ticker]['sector'] = sector
        
        if company_name and not self.db[ticker]['company_name']:
            self.db[ticker]['company_name'] = company_name
        
        if metadata:
            self.db[ticker]['metadata'].update(metadata)
    
    def update_from_filing(
        self,
        filing_data: Dict[str, Any],
        source_file: Optional[str] = None
    ) -> None:
        """
        Extract and update knowledge from a parsed filing.
        
        Args:
            filing_data: Parsed filing JSON
            source_file: Source filename
        """
        from .contextual_enricher import ContextualEnricher
        
        ticker = filing_data.get('ticker', '').upper()
        if not ticker:
            logger.warning("[WARN] No ticker in filing data, skipping")
            return
        
        enricher = ContextualEnricher()
        
        # Process all sections to extract knowledge
        all_regions = set()
        all_operations = set()
        all_risks = set()
        
        sections = filing_data.get('sections', [])
        for section in sections:
            section_text = section.get('text', '')
            
            # Extract regions
            regions = enricher._extract_regions_from_text(section_text)
            all_regions.update(regions)
            
            # Extract operations
            operations = enricher._identify_operations(section_text)
            all_operations.update(operations)
            
            # Extract risk types
            risks = enricher._identify_risk_types(section_text)
            all_risks.update(risks)
        
        # Update database
        company_name = filing_data.get('company')
        sector = filing_data.get('sector')  # May not be in filing, could come from CSV
        
        self.update_company(
            ticker=ticker,
            regions=list(all_regions),
            operations=list(all_operations),
            risk_types=list(all_risks),
            sector=sector,
            company_name=company_name,
            metadata={
                'last_filing_date': filing_data.get('filing_date'),
                'filing_type': filing_data.get('filing_type')
            }
        )
        
        # Track source
        if source_file:
            if 'sources' not in self.db[ticker]:
                self.db[ticker]['sources'] = []
            if source_file not in self.db[ticker]['sources']:
                self.db[ticker]['sources'].append(source_file)
        
        logger.info(f"[OK] Updated knowledge for {ticker}: {len(all_regions)} regions, {len(all_operations)} operations, {len(all_risks)} risk types")
    
    def get_enrichment_context(self, ticker: str) -> Dict[str, Any]:
        """
        Get enrichment context for a company.
        
        Args:
            ticker: Company ticker
            
        Returns:
            Dict with regions, operations, risk_types, sector, etc.
        """
        company = self.get_company(ticker)
        
        if not company:
            return {
                'regions': [],
                'operations': [],
                'risk_types': [],
                'sector': None,
                'company_name': None
            }
        
        return {
            'regions': company.get('regions', []),
            'operations': company.get('operations', []),
            'risk_types': company.get('risk_types', []),
            'sector': company.get('sector'),
            'company_name': company.get('company_name')
        }
    
    def get_all_companies(self) -> List[str]:
        """Get list of all company tickers in database."""
        return sorted(self.db.keys())
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        if not self.db:
            return {
                'total_companies': 0,
                'avg_regions': 0,
                'avg_operations': 0,
                'avg_risk_types': 0
            }
        
        total_regions = sum(len(c.get('regions', [])) for c in self.db.values())
        total_operations = sum(len(c.get('operations', [])) for c in self.db.values())
        total_risks = sum(len(c.get('risk_types', [])) for c in self.db.values())
        n = len(self.db)
        
        return {
            'total_companies': n,
            'avg_regions': total_regions / n if n > 0 else 0,
            'avg_operations': total_operations / n if n > 0 else 0,
            'avg_risk_types': total_risks / n if n > 0 else 0,
            'total_regions_mentioned': len(set(
                region for c in self.db.values()
                for region in c.get('regions', [])
            )),
            'total_operations_mentioned': len(set(
                op for c in self.db.values()
                for op in c.get('operations', [])
            ))
        }
    
    def search_companies(
        self,
        region: Optional[str] = None,
        operation: Optional[str] = None,
        risk_type: Optional[str] = None,
        sector: Optional[str] = None
    ) -> List[str]:
        """
        Search for companies matching criteria.
        
        Args:
            region: Filter by region
            operation: Filter by operation type
            risk_type: Filter by risk type
            sector: Filter by sector
            
        Returns:
            List of matching tickers
        """
        matches = []
        
        for ticker, company in self.db.items():
            if region and region not in company.get('regions', []):
                continue
            if operation and operation not in company.get('operations', []):
                continue
            if risk_type and risk_type not in company.get('risk_types', []):
                continue
            if sector and company.get('sector', '').lower() != sector.lower():
                continue
            
            matches.append(ticker)
        
        return matches

