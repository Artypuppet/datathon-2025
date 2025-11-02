"""
Data Providers for Company Knowledge.

Fetches company information from external APIs (Yahoo Finance, Financial Modeling Prep, etc.)
to populate the company knowledge database with rich, structured data.
"""

import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)


class YahooFinanceProvider:
    """
    Fetches company data from Yahoo Finance using yfinance library.
    
    Free, no API key required. Provides sector, industry, business description, etc.
    """
    
    def __init__(self):
        """Initialize Yahoo Finance provider."""
        try:
            import yfinance as yf
            self.yf = yf
            self.available = True
            logger.info("[INFO] Yahoo Finance provider initialized")
        except ImportError:
            self.available = False
            logger.warning("[WARN] yfinance not installed. Install with: pip install yfinance")
    
    def get_company_info(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get company information for a ticker.
        
        Args:
            ticker: Stock ticker symbol (e.g., "AAPL")
            
        Returns:
            Dictionary with company information or None if unavailable
        """
        if not self.available:
            return None
        
        try:
            ticker_obj = self.yf.Ticker(ticker.upper())
            info = ticker_obj.info
            
            if not info or len(info) == 0:
                return None
            
            # Extract relevant fields
            company_data = {
                'ticker': ticker.upper(),
                'company_name': info.get('longName') or info.get('shortName', ''),
                'sector': info.get('sector', ''),
                'industry': info.get('industry', ''),
                'country': info.get('country', ''),
                'state': info.get('state', ''),
                'city': info.get('city', ''),
                'business_summary': info.get('longBusinessSummary', '') or info.get('businessSummary', ''),
                'website': info.get('website', ''),
                'employees': info.get('fullTimeEmployees', 0),
                'phone': info.get('phone', ''),
                'address': info.get('address1', ''),
            }
            
            logger.debug(f"[DEBUG] Fetched Yahoo Finance data for {ticker}")
            return company_data
            
        except Exception as e:
            logger.warning(f"[WARN] Failed to fetch Yahoo Finance data for {ticker}: {e}")
            return None
    
    def get_regions_from_info(self, info: Dict[str, Any]) -> List[str]:
        """
        Extract regions/countries from company info.
        
        Args:
            info: Company info dictionary
            
        Returns:
            List of region strings
        """
        regions = []
        
        # Country
        country = info.get('country', '')
        if country:
            # Normalize country names
            country_map = {
                'United States': 'United States',
                'US': 'United States',
                'USA': 'United States',
            }
            normalized = country_map.get(country, country)
            if normalized and normalized not in regions:
                regions.append(normalized)
        
        # Extract from business summary (mentions of countries)
        summary = info.get('business_summary', '').lower()
        if summary:
            # Common country mentions
            country_keywords = {
                'china': 'China',
                'chinese': 'China',
                'japan': 'Japan',
                'japanese': 'Japan',
                'germany': 'Germany',
                'german': 'Germany',
                'united kingdom': 'United Kingdom',
                'uk': 'United Kingdom',
                'france': 'France',
                'french': 'France',
                'india': 'India',
                'indian': 'India',
                'south korea': 'South Korea',
                'korea': 'South Korea',
                'taiwan': 'Taiwan',
                'vietnam': 'Vietnam',
                'brazil': 'Brazil',
                'canada': 'Canada',
                'mexico': 'Mexico',
            }
            
            for keyword, country_name in country_keywords.items():
                if keyword in summary and country_name not in regions:
                    regions.append(country_name)
        
        return regions
    
    def get_operations_from_info(self, info: Dict[str, Any]) -> List[str]:
        """
        Infer operation types from company info.
        
        Args:
            info: Company info dictionary
            
        Returns:
            List of operation types
        """
        operations = []
        summary = (info.get('business_summary', '') or '').lower()
        industry = (info.get('industry', '') or '').lower()
        
        # Check for operation keywords
        if any(kw in summary for kw in ['manufacturer', 'production', 'factory', 'plant']):
            operations.append('Manufacturing')
        
        if any(kw in summary for kw in ['research', 'development', 'r&d', 'innovation']):
            operations.append('Research')
        
        if any(kw in summary for kw in ['supply chain', 'supplier', 'sourcing', 'vendor']):
            operations.append('Supply Chain')
        
        if any(kw in summary for kw in ['distribution', 'retail', 'wholesale', 'sales channel']):
            operations.append('Distribution')
        
        if any(kw in summary for kw in ['service', 'consulting', 'support']):
            operations.append('Services')
        
        if any(kw in summary for kw in ['software', 'technology', 'platform', 'digital']):
            operations.append('Technology')
        
        return operations


class FinancialModelingPrepProvider:
    """
    Fetches company data from Financial Modeling Prep API.
    
    Requires API key but provides very comprehensive data including geographic details.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Financial Modeling Prep provider.
        
        Args:
            api_key: FMP API key (from environment variable FMP_API_KEY if not provided)
        """
        import os
        
        self.api_key = api_key or os.getenv('FMP_API_KEY')
        self.base_url = 'https://financialmodelingprep.com/api/v3'
        self.available = bool(self.api_key)
        
        if not self.api_key:
            logger.warning("[WARN] FMP_API_KEY not set. Financial Modeling Prep provider disabled.")
        else:
            logger.info("[INFO] Financial Modeling Prep provider initialized")
    
    def get_company_info(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get company information from FMP API.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Dictionary with company information or None if unavailable
        """
        if not self.available:
            return None
        
        try:
            import requests
            
            url = f"{self.base_url}/profile/{ticker.upper()}"
            params = {'apikey': self.api_key}
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if not data or len(data) == 0:
                return None
            
            profile = data[0] if isinstance(data, list) else data
            
            company_data = {
                'ticker': ticker.upper(),
                'company_name': profile.get('companyName', ''),
                'sector': profile.get('sector', ''),
                'industry': profile.get('industry', ''),
                'country': profile.get('country', ''),
                'state': profile.get('state', ''),
                'city': profile.get('city', ''),
                'business_summary': profile.get('description', ''),
                'website': profile.get('website', ''),
                'employees': profile.get('fullTimeEmployees', 0),
                'phone': profile.get('phone', ''),
                'address': profile.get('address', ''),
            }
            
            logger.debug(f"[DEBUG] Fetched FMP data for {ticker}")
            return company_data
            
        except Exception as e:
            logger.warning(f"[WARN] Failed to fetch FMP data for {ticker}: {e}")
            return None


class CompanyDataProvider:
    """
    Unified interface for fetching company data from multiple providers.
    
    Tries providers in order of preference and returns the best available data.
    """
    
    def __init__(self, use_yahoo: bool = True, use_fmp: bool = False, fmp_api_key: Optional[str] = None):
        """
        Initialize company data provider.
        
        Args:
            use_yahoo: Whether to use Yahoo Finance (default: True)
            use_fmp: Whether to use Financial Modeling Prep (default: False, requires API key)
            fmp_api_key: Optional FMP API key
        """
        self.providers = []
        
        if use_yahoo:
            yahoo = YahooFinanceProvider()
            if yahoo.available:
                self.providers.append(yahoo)
        
        if use_fmp:
            fmp = FinancialModelingPrepProvider(api_key=fmp_api_key)
            if fmp.available:
                self.providers.append(fmp)
        
        if not self.providers:
            logger.warning("[WARN] No data providers available")
        else:
            logger.info(f"[INFO] CompanyDataProvider initialized with {len(self.providers)} provider(s)")
    
    def get_company_info(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get company information from available providers.
        
        Tries providers in order and returns first successful result.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Dictionary with company information or None if all providers fail
        """
        for provider in self.providers:
            info = provider.get_company_info(ticker)
            if info:
                return info
        
        logger.warning(f"[WARN] No data available for {ticker} from any provider")
        return None
    
    def enrich_company_knowledge(
        self,
        ticker: str,
        existing_knowledge: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Enrich company knowledge with data from providers.
        
        Merges external data with existing knowledge.
        
        Args:
            ticker: Stock ticker symbol
            existing_knowledge: Optional existing knowledge dict
            
        Returns:
            Enriched knowledge dictionary
        """
        # Get data from providers
        provider_info = self.get_company_info(ticker)
        
        if not provider_info:
            return existing_knowledge or {}
        
        # Use Yahoo Finance provider to extract regions/operations if available
        yahoo_provider = next((p for p in self.providers if isinstance(p, YahooFinanceProvider)), None)
        
        regions = []
        operations = []
        
        if yahoo_provider:
            regions = yahoo_provider.get_regions_from_info(provider_info)
            operations = yahoo_provider.get_operations_from_info(provider_info)
        
        # Build enriched knowledge
        enriched = existing_knowledge or {}
        
        # Update with provider data
        if provider_info.get('company_name'):
            enriched['company_name'] = provider_info['company_name']
        
        if provider_info.get('sector'):
            enriched['sector'] = provider_info['sector']
        
        if provider_info.get('industry'):
            enriched['industry'] = provider_info.get('industry')
        
        # Merge regions
        existing_regions = set(enriched.get('regions', []))
        new_regions = set(regions)
        enriched['regions'] = sorted(list(existing_regions | new_regions))
        
        # Merge operations
        existing_ops = set(enriched.get('operations', []))
        new_ops = set(operations)
        enriched['operations'] = sorted(list(existing_ops | new_ops))
        
        # Store metadata
        enriched['metadata'] = enriched.get('metadata', {})
        enriched['metadata']['data_provider'] = 'yahoo_finance' if yahoo_provider else 'unknown'
        enriched['metadata']['last_external_update'] = provider_info.get('last_updated')
        
        return enriched

