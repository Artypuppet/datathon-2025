"""
Polymarket API service.

Fetches prediction market data for legislative events.
"""

import logging
import os
from typing import Dict, Any, List, Optional
import requests

logger = logging.getLogger(__name__)


class PolymarketService:
    """
    Service for interacting with Polymarket API.
    
    Uses Gamma API (REST) to fetch market data.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Polymarket service.
        
        Args:
            api_key: Polymarket API key (optional, may not be required for public endpoints)
        """
        self.api_key = api_key or os.getenv('POLYMARKET_API_KEY')
        self.base_url = "https://gamma-api.polymarket.com"
        
        logger.info("[OK] PolymarketService initialized")
    
    def get_markets(
        self,
        tags: Optional[List[str]] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get active markets from Polymarket.
        
        Args:
            tags: Filter by tags (e.g., ["Business", "US Politics"])
            limit: Maximum number of markets to return
        
        Returns:
            List of market dictionaries
        """
        logger.info(f"[INFO] Fetching markets (tags={tags}, limit={limit})")
        
        try:
            url = f"{self.base_url}/markets"
            params = {
                'limit': limit,
                'active': 'true'
            }
            
            if tags:
                params['tags'] = ','.join(tags)
            
            headers = {}
            if self.api_key:
                headers['Authorization'] = f"Bearer {self.api_key}"
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            markets = response.json()
            logger.info(f"[OK] Fetched {len(markets)} markets")
            return markets
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to fetch markets: {e}")
            return []
    
    def get_market_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """
        Get market by slug.
        
        Args:
            slug: Market slug (e.g., "will-tiktok-be-banned-2024")
        
        Returns:
            Market dictionary or None
        """
        logger.info(f"[INFO] Fetching market: {slug}")
        
        try:
            url = f"{self.base_url}/markets/{slug}"
            
            headers = {}
            if self.api_key:
                headers['Authorization'] = f"Bearer {self.api_key}"
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            market = response.json()
            logger.info(f"[OK] Fetched market: {slug}")
            return market
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to fetch market: {e}")
            return None
    
    def get_probability(self, market_slug: str) -> Optional[float]:
        """
        Get implied probability from market.
        
        Args:
            market_slug: Market slug
        
        Returns:
            Probability (0-1) or None
        """
        market = self.get_market_by_slug(market_slug)
        
        if not market:
            return None
        
        # Extract probability from market data
        # Structure may vary, this is a placeholder
        try:
            # Try to get probability from outcome prices
            outcomes = market.get('outcomes', [])
            if outcomes:
                # Get "Yes" outcome probability
                yes_outcome = next((o for o in outcomes if o.get('outcome') == 'Yes'), None)
                if yes_outcome:
                    return float(yes_outcome.get('price', 0.5))
            
            # Fallback: use market probability if available
            return float(market.get('probability', 0.5))
            
        except Exception as e:
            logger.warning(f"[WARN] Could not extract probability: {e}")
            return None
