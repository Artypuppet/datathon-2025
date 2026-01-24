"""
Risk analysis service.

Wraps RegulatoryRiskScorer and integrates with Snowflake and Polymarket.
"""

import logging
from typing import Dict, Any, List, Optional
import numpy as np

from src.vectordb.risk_scorer import RegulatoryRiskScorer
from src.db.snowflake_client import SnowflakeClient
from src.db.neo4j_client import Neo4jClient
from src.llm.gemini_client import GeminiClient

logger = logging.getLogger(__name__)


class RiskService:
    """
    Service for computing regulatory risk scores.
    
    Integrates:
    - Snowflake for similarity search
    - RegulatoryRiskScorer for scoring
    - Polymarket for probabilities
    """
    
    def __init__(
        self,
        snowflake_client: Optional[SnowflakeClient] = None,
        neo4j_client: Optional[Neo4jClient] = None,
        gemini_client: Optional[GeminiClient] = None
    ):
        """
        Initialize risk service.
        
        Args:
            snowflake_client: SnowflakeClient instance
            neo4j_client: Neo4jClient instance
            gemini_client: GeminiClient instance
        """
        self.snowflake_client = snowflake_client or SnowflakeClient()
        self.neo4j_client = neo4j_client or Neo4jClient()
        self.gemini_client = gemini_client or GeminiClient()
        self.risk_scorer = RegulatoryRiskScorer()
        
        logger.info("[OK] RiskService initialized")
    
    def analyze_risk(
        self,
        legislation_text: str,
        ticker: Optional[str] = None,
        top_k: int = 10,
        polymarket_probability: float = 0.5
    ) -> Dict[str, Any]:
        """
        Analyze regulatory risk for legislation.
        
        Args:
            legislation_text: Legislation text to analyze
            ticker: Optional ticker to filter results
            top_k: Number of top matches to retrieve
            polymarket_probability: Polymarket probability (0-1)
        
        Returns:
            Dictionary with risk analysis results
        """
        logger.info(f"[INFO] Analyzing risk for legislation (ticker={ticker})")
        
        # Step 1: Summarize legislation
        legislation_summary = self.gemini_client.summarize_legislation(legislation_text)
        
        # Step 2: Search for similar chunks in Snowflake
        matched_chunks = self.snowflake_client.similarity_search(
            query_text=legislation_text,
            ticker=ticker,
            top_k=top_k
        )
        
        if not matched_chunks:
            logger.warning("[WARN] No matching chunks found")
            return {
                'success': False,
                'error': 'No matching chunks found'
            }
        
        # Step 3: Group by ticker if no specific ticker provided
        if ticker:
            # Single company analysis
            company_chunks = matched_chunks
            ticker = matched_chunks[0]['ticker']
            company_name = matched_chunks[0]['company_name']
        else:
            # Multi-company analysis - group by ticker
            ticker_groups = {}
            for chunk in matched_chunks:
                t = chunk['ticker']
                if t not in ticker_groups:
                    ticker_groups[t] = []
                ticker_groups[t].append(chunk)
            
            # For now, return results for first ticker (can be extended)
            ticker = list(ticker_groups.keys())[0]
            company_chunks = ticker_groups[ticker]
            company_name = company_chunks[0]['company_name']
        
        # Step 4: Format chunks for risk scorer
        formatted_chunks = []
        for chunk in company_chunks:
            formatted_chunks.append({
                'precomputed_similarity': chunk.get('similarity', 0.0),
                'section_type': chunk.get('section_type', 'other'),
                'filing_date': chunk.get('filing_date'),
                'original_sentence': chunk.get('original_sentence', chunk.get('chunk_text', '')),
                'section_title': chunk.get('section_title', ''),
                'filing_type': chunk.get('filing_type', 'N/A')
            })
        
        # Step 5: Get legislation embedding for risk scorer
        # Generate embedding for legislation (dummy embedding for now, scorer uses precomputed similarities)
        legislation_embedding = np.zeros(768)  # Placeholder
        
        # Step 6: Compute risk score
        risk_result = self.risk_scorer.compute_company_score_from_matches(
            company_chunks=formatted_chunks,
            legislation_embedding=legislation_embedding,
            polymarket_p=polymarket_probability
        )
        
        # Step 7: Format top contributors
        top_contributors = []
        for contrib in risk_result.get('top_contributors', [])[:10]:
            top_contributors.append({
                'section_type': contrib.get('section_type', 'unknown'),
                'section_title': contrib.get('section_title', ''),
                'filing_type': contrib.get('filing_type', 'N/A'),
                'filing_date': contrib.get('filing_date', 'N/A'),
                'sentence_text': contrib.get('sentence_text', ''),
                'similarity': contrib.get('similarity', 0.0),
                'weight': contrib.get('weight', 0.0),
                'exposure': contrib.get('exposure', 0.0)
            })
        
        return {
            'success': True,
            'ticker': ticker,
            'company_name': company_name,
            'legislation_summary': legislation_summary,
            'risk_score': risk_result,
            'top_contributors': top_contributors,
            'polymarket_probability': polymarket_probability
        }
