"""
Risk analysis router endpoints.
"""

import logging
from fastapi import APIRouter, HTTPException
from typing import Optional

from ..models.risk import RiskAnalysisRequest, RiskAnalysisResponse, RiskScore, TopContributor
from ..models.recommendation import RecommendationResponse, Recommendation, TraceableParagraph
from ..services.risk_service import RiskService
from ..services.polymarket_service import PolymarketService
from ...db.neo4j_client import Neo4jClient
from ...llm.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

router = APIRouter()
risk_service = RiskService()
polymarket_service = PolymarketService()
neo4j_client = Neo4jClient()
gemini_client = GeminiClient()


@router.post("/analyze", response_model=RiskAnalysisResponse)
async def analyze_risk(request: RiskAnalysisRequest):
    """Analyze regulatory risk for legislation."""
    try:
        # Get Polymarket probability (placeholder for now)
        polymarket_probability = 0.5  # Default
        
        # Analyze risk
        result = risk_service.analyze_risk(
            legislation_text=request.legislation_text,
            ticker=request.ticker,
            top_k=request.top_k,
            polymarket_probability=polymarket_probability
        )
        
        if not result.get('success'):
            raise HTTPException(status_code=400, detail=result.get('error', 'Analysis failed'))
        
        risk_score_data = result['risk_score']
        
        return RiskAnalysisResponse(
            ticker=result['ticker'],
            company_name=result['company_name'],
            legislation_summary=result['legislation_summary'],
            risk_score=RiskScore(
                raw_score=risk_score_data['raw_score'],
                sensitivity=risk_score_data['sensitivity'],
                adjusted_score=risk_score_data['adjusted_score'],
                final_expected=risk_score_data['final_expected'],
                final_worst=risk_score_data['final_worst'],
                risk_level=risk_score_data['risk_level'],
                total_matches=risk_score_data['total_matches']
            ),
            top_contributors=[
                TopContributor(**c) for c in result['top_contributors']
            ],
            polymarket_probability=result['polymarket_probability']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ERROR] Risk analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/companies/{ticker}/risk")
async def get_company_risk(
    ticker: str,
    legislation_text: str,
    top_k: int = 10
):
    """Get risk score for a specific company and legislation."""
    try:
        result = risk_service.analyze_risk(
            legislation_text=legislation_text,
            ticker=ticker,
            top_k=top_k
        )
        
        if not result.get('success'):
            raise HTTPException(status_code=400, detail=result.get('error', 'Analysis failed'))
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ERROR] Failed to get risk: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recommendations/{ticker}", response_model=RecommendationResponse)
async def get_recommendation(
    ticker: str,
    legislation_text: str,
    top_k: int = 10
):
    """Get Gemini-generated trading recommendation for a company."""
    try:
        # Get risk analysis first
        risk_result = risk_service.analyze_risk(
            legislation_text=legislation_text,
            ticker=ticker,
            top_k=top_k
        )
        
        if not risk_result.get('success'):
            raise HTTPException(status_code=400, detail=risk_result.get('error', 'Analysis failed'))
        
        # Get Neo4j context
        neo4j_context = neo4j_client.get_company_context(ticker, depth=2)
        
        # Generate recommendation using Gemini
        recommendation = gemini_client.generate_recommendation(
            company_name=risk_result['company_name'],
            ticker=ticker,
            legislation_summary=risk_result['legislation_summary'],
            matched_sentences=risk_result['top_contributors'],
            risk_score=risk_result['risk_score']['final_expected'],
            polymarket_probability=risk_result['polymarket_probability'],
            neo4j_context=neo4j_context
        )
        
        # Format traceable paragraphs
        traceable_paragraphs = [
            TraceableParagraph(
                section=p.get('section', ''),
                text=p.get('text', ''),
                relevance=p.get('relevance', '')
            )
            for p in recommendation.get('traceable_paragraphs', [])
        ]
        
        return RecommendationResponse(
            ticker=ticker,
            company_name=risk_result['company_name'],
            legislation_summary=risk_result['legislation_summary'],
            recommendation=Recommendation(
                recommendation=recommendation.get('recommendation', 'neutral'),
                reasoning=recommendation.get('reasoning', ''),
                kelly_fraction=recommendation.get('kelly_fraction', 0.0),
                position_sizing=recommendation.get('position_sizing', ''),
                impact_magnitude=recommendation.get('impact_magnitude', 0.0),
                traceable_paragraphs=traceable_paragraphs,
                confidence=recommendation.get('confidence', 0)
            ),
            risk_score=risk_result['risk_score']['final_expected'],
            polymarket_probability=risk_result['polymarket_probability']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ERROR] Failed to get recommendation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
