"""
Simplified metadata cache for company data (Yahoo Finance API wrapper).

No TTL logic for MVP - just fetches from Yahoo Finance API.
Future: Can add TTL, local caching, DynamoDB backend.
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class MetadataCache:
    """
    Simplified metadata cache for company data.
    
    Currently just wraps Yahoo Finance API - no caching logic.
    Future: Add JSON/DynamoDB backend with TTL.
    """
    
    def __init__(self):
        """Initialize metadata cache."""
        try:
            from .data_providers import YahooFinanceProvider
            self.provider = YahooFinanceProvider()
            self.available = self.provider.available
            logger.info("[INFO] MetadataCache initialized (Yahoo Finance)")
        except ImportError:
            self.provider = None
            self.available = False
            logger.warning("[WARN] YahooFinanceProvider not available")
    
    def get_company_metadata(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get company metadata from Yahoo Finance.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Company metadata dictionary or None if unavailable
        """
        if not self.available or not self.provider:
            logger.warning(f"[WARN] MetadataCache not available for {ticker}")
            return None
        
        try:
            logger.info(f"[INFO] Fetching metadata for {ticker} from Yahoo Finance")
            metadata = self.provider.get_company_info(ticker)
            
            if metadata:
                # Extract enrichment-ready fields
                enriched = {
                    'ticker': ticker.upper(),
                    'company_name': metadata.get('company_name', ''),
                    'sector': metadata.get('sector', ''),
                    'industry': metadata.get('industry', ''),
                    'country': metadata.get('country', ''),
                    'business_summary': metadata.get('business_summary', ''),
                    # Extract regions and operations from summary
                    'regions': self.provider.get_regions_from_info(metadata) if hasattr(self.provider, 'get_regions_from_info') else [],
                    'operations': self.provider.get_operations_from_info(metadata) if hasattr(self.provider, 'get_operations_from_info') else [],
                    'risk_types': self.provider.get_risk_types_from_info(metadata) if hasattr(self.provider, 'get_risk_types_from_info') else [],
                }
                logger.info(f"[OK] Fetched metadata for {ticker}")
                return enriched
            else:
                logger.warning(f"[WARN] No metadata found for {ticker}")
                return None
                
        except Exception as e:
            logger.error(f"[ERROR] Failed to fetch metadata for {ticker}: {e}")
            return None
    
    def enrich_company_data(self, ticker: str, existing_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich existing company data with metadata from Yahoo Finance.
        
        Args:
            ticker: Stock ticker symbol
            existing_data: Existing company data dictionary
            
        Returns:
            Enriched company data
        """
        metadata = self.get_company_metadata(ticker)
        
        if not metadata:
            return existing_data
        
        # Merge metadata into existing data (metadata takes precedence for missing fields)
        enriched = existing_data.copy()
        
        # Update fields if they're missing or empty
        for key in ['company_name', 'sector', 'industry', 'country']:
            if not enriched.get(key) and metadata.get(key):
                enriched[key] = metadata[key]
        
        # Merge lists (union) - check both top-level and entities
        for key in ['regions', 'operations', 'risk_types']:
            # Get existing values from top-level or entities
            existing_top = set(enriched.get(key, []))
            existing_entities = set(enriched.get('entities', {}).get(key, []))
            existing = existing_top | existing_entities
            
            # Get new values from metadata
            new = set(metadata.get(key, []))
            
            # Merge and update both locations
            merged = sorted(list(existing | new))
            enriched[key] = merged
            
            # Also update in entities if it exists
            if 'entities' in enriched:
                if key in enriched['entities']:
                    enriched['entities'][key] = merged
                elif key == 'risk_types':  # risk_types might not be in entities dict yet
                    if 'entities' in enriched:
                        enriched['entities'][key] = merged
        
        return enriched

