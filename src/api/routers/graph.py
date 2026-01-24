"""
Knowledge graph router endpoints.
"""

import logging
from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from ...db.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)

router = APIRouter()
neo4j_client = Neo4jClient()


@router.get("/{ticker}")
async def get_company_graph(ticker: str, depth: int = 2) -> Dict[str, Any]:
    """Get Neo4j subgraph for a company."""
    try:
        context = neo4j_client.get_company_context(ticker, depth=depth)
        
        if not context:
            raise HTTPException(status_code=404, detail=f"Company {ticker} not found in graph")
        
        return context
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ERROR] Failed to get graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sectors/{sector}/companies")
async def get_companies_by_sector(sector: str):
    """Get all companies in a sector."""
    try:
        tickers = neo4j_client.get_companies_by_sector(sector)
        return {"sector": sector, "tickers": tickers}
        
    except Exception as e:
        logger.error(f"[ERROR] Failed to get companies: {e}")
        raise HTTPException(status_code=500, detail=str(e))
