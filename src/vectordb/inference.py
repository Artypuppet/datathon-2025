"""
Inference module for computing legislation impact on companies.

Uses vector database similarity search to:
1. Find relevant sentences in company filings
2. Calculate impact scores
3. Provide explainability through matched sentences
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

from .client import VectorDBClient, get_vectordb_client
from .risk_scorer import RegulatoryRiskScorer
from .llm_analyzer import LLMAnalyzer

logger = logging.getLogger(__name__)


class LegislationImpactAnalyzer:
    """
    Analyze the impact of legislation on companies using vector similarity.
    
    Features:
    - Find matching sentences between legislation and company filings
    - Calculate impact scores based on similarity
    - Provide explainability through sentence references
    - Aggregate scores across multiple filings
    """
    
    def __init__(
        self,
        vectordb_client: Optional[VectorDBClient] = None,
        similarity_threshold: float = 0.7,
        top_k: int = 50,
        use_advanced_scoring: bool = True,
        risk_scorer: Optional[RegulatoryRiskScorer] = None,
        use_llm_analysis: bool = False,
        llm_analyzer: Optional[LLMAnalyzer] = None,
        legislation_text: Optional[str] = None
    ):
        """
        Initialize impact analyzer.
        
        Args:
            vectordb_client: VectorDB client instance (auto-created if None)
            similarity_threshold: Minimum similarity to consider a match (0-1)
            top_k: Number of top matches to retrieve per query
            use_advanced_scoring: Whether to use RegulatoryRiskScorer (default: True)
            risk_scorer: Optional pre-configured risk scorer (auto-created if None)
            use_llm_analysis: Whether to use LLM for analysis (default: False)
            llm_analyzer: Optional pre-configured LLM analyzer (auto-created if None)
            legislation_text: Optional legislation text for summarization
        """
        self.vectordb = vectordb_client or get_vectordb_client()
        self.similarity_threshold = similarity_threshold
        self.top_k = top_k
        self.use_advanced_scoring = use_advanced_scoring
        self.use_llm_analysis = use_llm_analysis
        self.legislation_text = legislation_text
        
        if use_advanced_scoring:
            self.risk_scorer = risk_scorer or RegulatoryRiskScorer(
                sim_threshold=similarity_threshold
            )
        else:
            self.risk_scorer = None
        
        if use_llm_analysis:
            try:
                self.llm_analyzer = llm_analyzer or LLMAnalyzer()
                # Summarize legislation if text provided
                if legislation_text:
                    self.legislation_summary = self.llm_analyzer.summarize_legislation(legislation_text)
                    logger.info(f"[OK] Legislation summarized ({len(self.legislation_summary)} chars)")
                else:
                    self.legislation_summary = None
            except Exception as e:
                logger.warning(f"[WARN] Failed to initialize LLM analyzer: {e}")
                logger.warning("[WARN] Continuing without LLM analysis")
                self.llm_analyzer = None
                self.legislation_summary = None
                self.use_llm_analysis = False
        else:
            self.llm_analyzer = None
            self.legislation_summary = None
        
        logger.info(f"[INFO] LegislationImpactAnalyzer initialized")
        logger.info(f"  Similarity threshold: {similarity_threshold}")
        logger.info(f"  Top K: {top_k}")
        logger.info(f"  Advanced scoring: {use_advanced_scoring}")
        logger.info(f"  LLM analysis: {use_llm_analysis}")
    
    def analyze_impact(
        self,
        legislation_id: str,
        legislation_embedding: np.ndarray,
        ticker: str,
        company_name: Optional[str] = None,
        company_metadata: Optional[Dict[str, Any]] = None,
        polymarket_p: float = 1.0
    ) -> Dict[str, Any]:
        """
        Analyze the impact of legislation on a company.
        
        Args:
            legislation_id: Unique identifier for the legislation
            legislation_embedding: Embedding vector for the legislation
            ticker: Company ticker symbol
            company_name: Optional company name
            company_metadata: Optional company metadata for advanced scoring:
                - revenue_by_region: Dict[str, float]
                - market_cap: float
                - margin_sensitivity: float (0-1)
                - supply_chain_dependency: float (0-1)
                - entities: Dict with 'countries', etc.
            polymarket_p: External probability of legislation passing (0-1)
            
        Returns:
            Dictionary containing:
            - impact_score: Overall impact score (0-1) [legacy: uses final_expected if advanced scoring]
            - risk_level: Risk level classification (low/medium/high/critical)
            - matched_sentences: List of matched sentences with details
            - statistics: Aggregated statistics
            - explanation: Human-readable explanation
            - advanced_scoring: Advanced scoring details (if enabled)
        """
        logger.info(f"[INFO] Analyzing impact of {legislation_id} on {ticker}")
        
        # Find similar sentences
        matches = self.vectordb.find_similar_sentences(
            query_embedding=legislation_embedding,
            content_type="company_sentence",
            ticker=ticker,
            top_k=self.top_k
        )
        
        # Filter by threshold
        filtered_matches = [
            m for m in matches 
            if m.get('similarity', 0.0) >= self.similarity_threshold
        ]
        
        logger.info(f"[INFO] Found {len(filtered_matches)} matches above threshold")
        
        # Use advanced scoring if enabled
        if self.use_advanced_scoring and self.risk_scorer:
            # Convert matches to chunk format for risk scorer
            # Use pre-computed similarities from vector DB instead of recomputing
            company_chunks = []
            for match in filtered_matches:
                # Extract embedding if available, otherwise we'll use pre-computed similarity
                embedding = match.get('embedding')
                if embedding is not None:
                    if isinstance(embedding, list):
                        embedding = np.array(embedding)
                    else:
                        embedding = np.array(embedding)
                else:
                    # If embedding not in match, we'll need to fetch it or use similarity
                    # For now, mark as None and use pre-computed similarity
                    embedding = None
                
                chunk = {
                    'embedding': embedding,  # May be None if not in metadata
                    'precomputed_similarity': match.get('similarity', 0.0),  # Use this if embedding missing
                    'section_type': match.get('section_type', 'other'),
                    'filing_date': match.get('filing_date'),
                    'original_sentence': match.get('original_sentence', ''),
                    'section_title': match.get('section_title', ''),
                    'filing_type': match.get('filing_type', 'N/A'),
                    'ticker': ticker,
                    'company_name': company_name
                }
                company_chunks.append(chunk)
            
            # Compute advanced score
            company_metadata = company_metadata or {}
            if company_name:
                company_metadata['company_name'] = company_name
            
            # Use pre-computed similarities if embeddings are missing
            advanced_result = self.risk_scorer.compute_company_score_from_matches(
                company_chunks=company_chunks,
                legislation_embedding=legislation_embedding,
                company_metadata=company_metadata,
                polymarket_p=polymarket_p
            )
            
            # Get recommendations
            recommendations = self.risk_scorer.get_recommendations(
                final_score=advanced_result['final_expected'],
                risk_level=advanced_result['risk_level'],
                company_metadata=company_metadata
            )
            
            impact_score = advanced_result['final_expected']
            risk_level = advanced_result['risk_level']
            advanced_scoring = {
                'raw_score': advanced_result['raw_score'],
                'sensitivity': advanced_result['sensitivity'],
                'adjusted_score': advanced_result['adjusted_score'],
                'final_expected': advanced_result['final_expected'],
                'final_worst': advanced_result['final_worst'],
                'recommendations': recommendations,
                'top_contributors': advanced_result['top_contributors'],
                'explanation': advanced_result['explanation']
            }
        else:
            # Legacy scoring
            impact_score, risk_level = self._calculate_impact_score(filtered_matches)
            advanced_scoring = None
        
        # Build matched sentences with context
        matched_sentences = self._format_matched_sentences(filtered_matches)
        
        # Calculate statistics
        statistics = self._calculate_statistics(filtered_matches)
        
        # Generate explanation
        explanation = self._generate_explanation(
            legislation_id=legislation_id,
            ticker=ticker,
            company_name=company_name,
            impact_score=impact_score,
            risk_level=risk_level,
            statistics=statistics,
            top_matches=matched_sentences[:5]  # Top 5 for explanation
        )
        
        result = {
            'legislation_id': legislation_id,
            'ticker': ticker,
            'company_name': company_name,
            'impact_score': float(impact_score),
            'risk_level': risk_level,
            'similarity_threshold': self.similarity_threshold,
            'total_matches': len(matched_sentences),
            'matched_sentences': matched_sentences,
            'statistics': statistics,
            'explanation': explanation
        }
        
        if advanced_scoring:
            result['advanced_scoring'] = advanced_scoring
        
        # LLM-based analysis
        if self.use_llm_analysis and self.llm_analyzer:
            logger.info(f"[INFO] Running LLM analysis for {ticker}")
            
            # Get legislation summary (summarize on demand if not already done)
            legislation_summary = self.legislation_summary
            if not legislation_summary and self.legislation_text:
                legislation_summary = self.llm_analyzer.summarize_legislation(
                    self.legislation_text,
                    legislation_id
                )
            
            if legislation_summary:
                # Extract company metadata for context
                sector = company_metadata.get('sector') if company_metadata else None
                industry = company_metadata.get('industry') if company_metadata else None
                
                # Run LLM impact analysis
                llm_analysis = self.llm_analyzer.analyze_impact(
                    legislation_summary=legislation_summary,
                    company_name=company_name or ticker,
                    ticker=ticker,
                    matched_sentences=matched_sentences,
                    sector=sector,
                    industry=industry
                )
                
                result['llm_analysis'] = llm_analysis
                result['legislation_summary'] = legislation_summary
                
                logger.info(f"[OK] LLM analysis complete: recommendation={llm_analysis.get('recommendation', 'neutral')}")
            else:
                logger.warning("[WARN] Cannot run LLM analysis: no legislation summary available")
        
        logger.info(f"[OK] Impact analysis complete: {ticker} - {risk_level} risk (score: {impact_score:.3f})")
        
        return result
    
    def _calculate_impact_score(self, matches: List[Dict[str, Any]]) -> Tuple[float, str]:
        """
        Calculate overall impact score from matches.
        
        Uses weighted scoring:
        - Higher similarity = higher weight
        - Risk factors sections weighted more heavily
        - Business sections weighted moderately
        - Other sections weighted less
        
        Args:
            matches: List of matched sentences
            
        Returns:
            Tuple of (impact_score, risk_level)
        """
        if not matches:
            return 0.0, "low"
        
        # Weight by section type
        section_weights = {
            'risk_factors': 1.5,
            'business': 1.2,
            'significant_events': 1.0,
            'other': 0.8
        }
        
        weighted_scores = []
        for match in matches:
            similarity = match.get('similarity', 0.0)
            section_type = match.get('section_type', 'other')
            weight = section_weights.get(section_type, 0.8)
            weighted_scores.append(similarity * weight)
        
        # Impact score is average weighted similarity, normalized to 0-1
        avg_weighted = np.mean(weighted_scores) if weighted_scores else 0.0
        max_possible = max(section_weights.values())  # Normalize by max weight
        impact_score = min(avg_weighted / max_possible, 1.0)
        
        # Determine risk level
        if impact_score >= 0.8:
            risk_level = "high"
        elif impact_score >= 0.5:
            risk_level = "medium"
        else:
            risk_level = "low"
        
        return float(impact_score), risk_level
    
    def _format_matched_sentences(self, matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Format matched sentences with all context for explainability.
        
        Args:
            matches: Raw matches from vector DB
            
        Returns:
            List of formatted sentence matches
        """
        formatted = []
        
        for match in matches:
            sentence_idx = match.get('sentence_idx')
            total_sentences = match.get('total_sentences') or match.get('total_sentences_in_section', 0)
            
            # Convert to int if string (ChromaDB stores metadata as strings)
            try:
                sentence_idx = int(sentence_idx) if sentence_idx is not None else 0
            except (ValueError, TypeError):
                sentence_idx = 0
            
            try:
                total_sentences = int(total_sentences) if total_sentences else 0
            except (ValueError, TypeError):
                total_sentences = 0
            
            formatted.append({
                'similarity': match.get('similarity', 0.0),
                'section_type': match.get('section_type', ''),
                'section_title': match.get('section_title', ''),
                'filing_type': match.get('filing_type', ''),
                'filing_date': match.get('filing_date', ''),
                'sentence_idx': sentence_idx,
                'total_sentences': total_sentences,
                'sentence_position': f"{sentence_idx + 1} of {total_sentences}" if total_sentences > 0 else f"{sentence_idx + 1}",
                'original_sentence': match.get('original_sentence', ''),
                'enriched_text': match.get('sentence_text', ''),  # Includes context window
                'metadata': {
                    'ticker': match.get('ticker', ''),
                    'company_name': match.get('company_name', ''),
                    'created_at': match.get('created_at', '')
                }
            })
        
        return formatted
    
    def _calculate_statistics(self, matches: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate statistics from matches."""
        if not matches:
            return {
                'total_matches': 0,
                'avg_similarity': 0.0,
                'max_similarity': 0.0,
                'min_similarity': 0.0,
                'by_section_type': {},
                'by_filing_type': {}
            }
        
        similarities = [m.get('similarity', 0.0) for m in matches]
        
        # Group by section type
        by_section_type = {}
        for match in matches:
            section_type = match.get('section_type', 'unknown')
            if section_type not in by_section_type:
                by_section_type[section_type] = []
            by_section_type[section_type].append(match.get('similarity', 0.0))
        
        # Calculate averages per section type
        section_stats = {}
        for section_type, sims in by_section_type.items():
            section_stats[section_type] = {
                'count': len(sims),
                'avg_similarity': float(np.mean(sims)),
                'max_similarity': float(np.max(sims))
            }
        
        # Group by filing type
        by_filing_type = {}
        for match in matches:
            filing_type = match.get('filing_type', 'unknown')
            if filing_type not in by_filing_type:
                by_filing_type[filing_type] = []
            by_filing_type[filing_type].append(match.get('similarity', 0.0))
        
        filing_stats = {}
        for filing_type, sims in by_filing_type.items():
            filing_stats[filing_type] = {
                'count': len(sims),
                'avg_similarity': float(np.mean(sims)),
                'max_similarity': float(np.max(sims))
            }
        
        return {
            'total_matches': len(matches),
            'avg_similarity': float(np.mean(similarities)),
            'max_similarity': float(np.max(similarities)),
            'min_similarity': float(np.min(similarities)),
            'by_section_type': section_stats,
            'by_filing_type': filing_stats
        }
    
    def _generate_explanation(
        self,
        legislation_id: str,
        ticker: str,
        company_name: Optional[str],
        impact_score: float,
        risk_level: str,
        statistics: Dict[str, Any],
        top_matches: List[Dict[str, Any]]
    ) -> str:
        """
        Generate human-readable explanation of the impact.
        
        Args:
            legislation_id: Legislation identifier
            ticker: Company ticker
            company_name: Company name
            impact_score: Calculated impact score
            risk_level: Risk level
            statistics: Match statistics
            top_matches: Top matching sentences
            
        Returns:
            Explanation text
        """
        company_label = company_name or ticker
        
        explanation_parts = [
            f"IMPACT ASSESSMENT: {risk_level.upper()} RISK",
            f"",
            f"Legislation: {legislation_id}",
            f"Company: {company_label} ({ticker})",
            f"Overall Impact Score: {impact_score:.3f} (scale: 0 = no impact, 1 = high impact)",
            f"",
            f"Analysis Summary:",
            f"  - Total matching sentences: {statistics['total_matches']}",
            f"  - Average similarity: {statistics['avg_similarity']:.3f}",
            f"  - Maximum similarity: {statistics['max_similarity']:.3f}",
            f"",
        ]
        
        # Add section breakdown
        if statistics.get('by_section_type'):
            explanation_parts.append("Similarity by Section Type:")
            for section_type, stats in statistics['by_section_type'].items():
                explanation_parts.append(
                    f"  - {section_type}: {stats['count']} matches, "
                    f"avg similarity {stats['avg_similarity']:.3f}"
                )
            explanation_parts.append("")
        
        # Add top matches
        if top_matches:
            explanation_parts.append("Most Relevant Matches:")
            for i, match in enumerate(top_matches[:5], 1):
                explanation_parts.append(
                    f"  {i}. {match['section_title']} "
                    f"(similarity: {match['similarity']:.3f})"
                )
                explanation_parts.append(
                    f"     Sentence {match['sentence_position']} in {match['section_type']} section"
                )
                explanation_parts.append(
                    f"     From {match['filing_type']} filed {match['filing_date']}"
                )
                sentence = match['original_sentence']
                if len(sentence) > 200:
                    sentence = sentence[:200] + "..."
                explanation_parts.append(f"     \"{sentence}\"")
                explanation_parts.append("")
        
        # Add risk interpretation
        explanation_parts.append(f"Risk Interpretation:")
        if risk_level == "high":
            explanation_parts.append(
                "This legislation shows strong similarity to company disclosures, "
                "indicating significant potential impact. Key areas of concern are "
                "highlighted in the matched sentences above."
            )
        elif risk_level == "medium":
            explanation_parts.append(
                "This legislation shows moderate similarity to company disclosures. "
                "There is some overlap between the regulation and company operations, "
                "warranting further review of the specific matched content."
            )
        else:
            explanation_parts.append(
                "This legislation shows low similarity to company disclosures. "
                "While some matches were found, the overall impact appears limited."
            )
        
        return "\n".join(explanation_parts)
    
    def batch_analyze_impact(
        self,
        legislation_id: str,
        legislation_embedding: np.ndarray,
        tickers: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Analyze impact for multiple companies.
        
        Args:
            legislation_id: Legislation identifier
            legislation_embedding: Legislation embedding
            tickers: List of company tickers
            
        Returns:
            Dictionary mapping ticker to impact analysis results
        """
        logger.info(f"[INFO] Batch analyzing impact on {len(tickers)} companies")
        
        results = {}
        for ticker in tickers:
            try:
                result = self.analyze_impact(
                    legislation_id=legislation_id,
                    legislation_embedding=legislation_embedding,
                    ticker=ticker
                )
                results[ticker] = result
            except Exception as e:
                logger.error(f"[ERROR] Failed to analyze {ticker}: {e}")
                results[ticker] = {
                    'ticker': ticker,
                    'error': str(e),
                    'impact_score': 0.0,
                    'risk_level': 'unknown'
                }
        
        logger.info(f"[OK] Batch analysis complete: {len(results)} results")
        return results

