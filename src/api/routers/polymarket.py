"""
Polymarket router endpoints.
"""

import logging
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional

from ..services.polymarket_service import PolymarketService

logger = logging.getLogger(__name__)

router = APIRouter()
polymarket_service = PolymarketService()


@router.get("/markets")
async def get_markets(
    tags: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Get active Polymarket markets."""
    try:
        tag_list = tags.split(',') if tags else None
        markets = polymarket_service.get_markets(tags=tag_list, limit=limit)
        return markets
        
    except Exception as e:
        logger.error(f"[ERROR] Failed to get markets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/markets/{slug}")
async def get_market(slug: str) -> Dict[str, Any]:
    """Get market by slug."""
    try:
        market = polymarket_service.get_market_by_slug(slug)
        
        if not market:
            raise HTTPException(status_code=404, detail=f"Market {slug} not found")
        
        return market
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ERROR] Failed to get market: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/markets/{slug}/probability")
async def get_market_probability(slug: str) -> Dict[str, Any]:
    """Get probability from market."""
    try:
        probability = polymarket_service.get_probability(slug)
        
        if probability is None:
            raise HTTPException(status_code=404, detail=f"Could not get probability for {slug}")
        
        return {
            "slug": slug,
            "probability": probability
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ERROR] Failed to get probability: {e}")
        raise HTTPException(status_code=500, detail=str(e))
