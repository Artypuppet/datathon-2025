"""
Filings router endpoints.
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional

from ..models.filing import FilingChunk, CompanyFiling, FilingSearchResponse
from ...db.snowflake_client import SnowflakeClient

logger = logging.getLogger(__name__)

router = APIRouter()
snowflake_client = SnowflakeClient()


@router.get("/companies", response_model=List[str])
async def list_companies():
    """List all companies with filings."""
    # TODO: Query Snowflake for distinct tickers
    # For now, return hardcoded list of 10 companies
    return ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "JPM", "V", "JNJ"]


@router.get("/companies/{ticker}", response_model=List[CompanyFiling])
async def get_company_filings(ticker: str):
    """Get all filings for a company."""
    try:
        chunks = snowflake_client.get_company_chunks(ticker)
        
        # Group by filing
        filings = {}
        for chunk in chunks:
            filing_key = f"{chunk.get('filing_type')}_{chunk.get('filing_date')}"
            if filing_key not in filings:
                filings[filing_key] = {
                    'ticker': ticker,
                    'company_name': chunk.get('company_name', ticker),
                    'filing_type': chunk.get('filing_type', 'N/A'),
                    'filing_date': chunk.get('filing_date'),
                    'total_chunks': 0
                }
            filings[filing_key]['total_chunks'] += 1
        
        return list(filings.values())
        
    except Exception as e:
        logger.error(f"[ERROR] Failed to get filings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search", response_model=FilingSearchResponse)
async def search_filings(
    query: str = Query(..., description="Search query text"),
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
    top_k: int = Query(10, description="Number of results")
):
    """Search filings using similarity search."""
    try:
        results = snowflake_client.similarity_search(
            query_text=query,
            ticker=ticker,
            top_k=top_k
        )
        
        return FilingSearchResponse(
            query=query,
            results=[FilingChunk(**r) for r in results],
            total_results=len(results)
        )
        
    except Exception as e:
        logger.error(f"[ERROR] Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
