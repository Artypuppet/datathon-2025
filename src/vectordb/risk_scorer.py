"""
Advanced regulatory risk scoring engine.

Implements comprehensive scoring methodology with:
- Chunk-level weighting (section, recency, size)
- Sensitivity adjustments (revenue exposure, margins, supply chain)
- External probability integration (Polymarket)
- Explainability and provenance tracking
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, date
import numpy as np

logger = logging.getLogger(__name__)

# Default hyperparameters
DEFAULT_SECTION_WEIGHTS = {
    'risk_factors': 1.0,
    'significant_events': 0.95,  # 8-K events are important
    'business': 0.6,
    'other': 0.5
}

DEFAULT_LAMBDA_RECENCY = 0.001  # Decay rate per day
DEFAULT_SIM_THRESHOLD = 0.7  # Minimum similarity to consider
DEFAULT_TOKEN_BASE = 1000  # Base tokens for size normalization

# Sensitivity weights
DEFAULT_SENSITIVITY_WEIGHTS = {
    'revenue_exposed': 0.6,
    'margin_sensitivity': 0.3,
    'supply_chain_dependency': 0.1,
    'legal_exposure': 0.0  # Can be enabled if data available
}

# Risk category thresholds
RISK_THRESHOLDS = {
    'low': (0.0, 0.20),
    'medium': (0.20, 0.50),
    'high': (0.50, 0.75),
    'critical': (0.75, 1.00)
}


class RegulatoryRiskScorer:
    """
    Compute regulatory risk scores using comprehensive methodology.
    
    Implements the scoring algorithm from REGULATORY_RISK_SCORING.md:
    1. Chunk-level weighting (section, recency, size)
    2. Similarity computation with aggregation
    3. Company-level raw score
    4. Sensitivity adjustment
    5. External probability integration
    6. Risk categorization
    7. Explainability
    """
    
    def __init__(
        self,
        section_weights: Optional[Dict[str, float]] = None,
        lambda_recency: float = DEFAULT_LAMBDA_RECENCY,
        sim_threshold: float = DEFAULT_SIM_THRESHOLD,
        token_base: int = DEFAULT_TOKEN_BASE,
        sensitivity_weights: Optional[Dict[str, float]] = None,
        aggregation_method: str = 'max'  # 'max' or 'weighted_avg'
    ):
        """
        Initialize risk scorer.
        
        Args:
            section_weights: Weight mapping for section types
            lambda_recency: Recency decay rate (per day)
            sim_threshold: Minimum similarity to consider
            token_base: Base token count for size normalization
            sensitivity_weights: Weights for sensitivity components
            aggregation_method: How to aggregate legislation-to-chunk similarity ('max' or 'weighted_avg')
        """
        self.section_weights = section_weights or DEFAULT_SECTION_WEIGHTS.copy()
        self.lambda_recency = lambda_recency
        self.sim_threshold = sim_threshold
        self.token_base = token_base
        self.sensitivity_weights = sensitivity_weights or DEFAULT_SENSITIVITY_WEIGHTS.copy()
        self.aggregation_method = aggregation_method
        
        logger.info(f"[INFO] RegulatoryRiskScorer initialized")
        logger.info(f"  Section weights: {self.section_weights}")
        logger.info(f"  Recency decay (λ): {self.lambda_recency}")
        logger.info(f"  Similarity threshold: {self.sim_threshold}")
        logger.info(f"  Aggregation method: {self.aggregation_method}")
    
    def compute_company_score_from_matches(
        self,
        company_chunks: List[Dict[str, Any]],
        legislation_embedding: np.ndarray,
        company_metadata: Optional[Dict[str, Any]] = None,
        polymarket_p: float = 1.0
    ) -> Dict[str, Any]:
        """
        Compute risk score using pre-computed similarities from vector DB.
        
        More efficient than recomputing embeddings - uses similarity scores
        already computed by the vector database.
        
        Args:
            company_chunks: List of chunk dictionaries with:
                - 'precomputed_similarity': float (from vector DB)
                - 'section_type': str
                - 'filing_date': str or date
                - 'original_sentence': str
                - 'embedding': Optional np.ndarray (for fallback)
            legislation_embedding: Legislation embedding (single)
            company_metadata: Company metadata dict
            polymarket_p: External probability (0-1)
            
        Returns:
            Same structure as compute_company_score
        """
        if not company_chunks:
            return self._empty_score()
        
        company_metadata = company_metadata or {}
        
        # Step 1: Compute chunk-level weights and use pre-computed similarities
        chunk_data = []
        
        for chunk in company_chunks:
            # Compute chunk weight
            w_section = self._get_section_weight(chunk.get('section_type', 'other'))
            w_recency = self._compute_recency_weight(chunk.get('filing_date'))
            w_size = self._compute_size_weight(chunk.get('original_sentence', ''))
            w_i = w_section * w_recency * w_size
            
            # Use pre-computed similarity if available
            sim_i = chunk.get('precomputed_similarity', 0.0)
            
            # Fallback: compute similarity if embedding available and similarity missing
            if sim_i == 0.0 and chunk.get('embedding') is not None:
                embedding = chunk['embedding']
                if isinstance(embedding, list):
                    embedding = np.array(embedding)
                sim_i = self._cosine_similarity(embedding, legislation_embedding)
            
            # Apply threshold
            if sim_i < self.sim_threshold:
                continue
            
            # Compute exposure
            exposure_i = sim_i * w_i
            
            chunk_data.append({
                'chunk': chunk,
                'weight': w_i,
                'similarity': sim_i,
                'exposure': exposure_i,
                'w_section': w_section,
                'w_recency': w_recency,
                'w_size': w_size
            })
        
        if not chunk_data:
            return self._empty_score()
        
        # Continue with same logic as compute_company_score
        total_exposure = sum(cd['exposure'] for cd in chunk_data)
        total_weight = sum(cd['weight'] for cd in chunk_data)
        
        eps = 1e-12
        raw_score = total_exposure / (total_weight + eps)
        raw_score = min(1.0, max(0.0, raw_score))
        
        sensitivity = self._compute_sensitivity(company_metadata)
        adjusted_score = raw_score * sensitivity
        final_expected = adjusted_score * polymarket_p
        final_worst = adjusted_score
        risk_level = self._classify_risk(final_expected)
        top_contributors = self._get_top_contributors(chunk_data, top_n=10)
        
        explanation = self._build_explanation(
            raw_score=raw_score,
            sensitivity=sensitivity,
            adjusted_score=adjusted_score,
            final_expected=final_expected,
            final_worst=final_worst,
            risk_level=risk_level,
            top_contributors=top_contributors,
            total_chunks=len(chunk_data),
            company_metadata=company_metadata,
            polymarket_p=polymarket_p
        )
        
        return {
            'raw_score': float(raw_score),
            'sensitivity': float(sensitivity),
            'adjusted_score': float(adjusted_score),
            'final_expected': float(final_expected),
            'final_worst': float(final_worst),
            'risk_level': risk_level,
            'top_contributors': top_contributors,
            'explanation': explanation,
            'total_matches': len(chunk_data),
            'total_exposure': float(total_exposure),
            'total_weight': float(total_weight)
        }
    
    def compute_company_score(
        self,
        company_chunks: List[Dict[str, Any]],
        legislation_embeddings: List[np.ndarray],
        company_metadata: Optional[Dict[str, Any]] = None,
        polymarket_p: float = 1.0
    ) -> Dict[str, Any]:
        """
        Compute comprehensive risk score for a company.
        
        Args:
            company_chunks: List of company chunk dictionaries with:
                - 'embedding': np.ndarray
                - 'section_type': str
                - 'filing_date': str (ISO format) or date
                - 'original_sentence': str (text for token counting)
                - Other metadata (ticker, company_name, etc.)
            legislation_embeddings: List of legislation embedding vectors
            company_metadata: Optional company metadata dict:
                - revenue_by_region: Dict[str, float]
                - market_cap: float
                - sp500_weight: float
                - supply_chain_dependency: float (0-1)
                - margin_sensitivity: float (0-1)
                - legal_exposure: float (0-1)
            polymarket_p: External probability of legislation passing (0-1)
            
        Returns:
            Dictionary with:
            - raw_score: Base score (0-1)
            - sensitivity: Company sensitivity factor (0-1)
            - adjusted_score: raw_score * sensitivity
            - final_expected: adjusted_score * polymarket_p
            - final_worst: adjusted_score (worst case if p=1)
            - risk_level: Categorical risk level
            - top_contributors: List of top contributing chunks
            - explanation: Detailed breakdown
        """
        if not company_chunks:
            return self._empty_score()
        
        if not legislation_embeddings:
            return self._empty_score()
        
        company_metadata = company_metadata or {}
        
        # Step 1: Compute chunk-level weights and similarities
        chunk_data = []
        
        for chunk in company_chunks:
            # Compute chunk weight
            w_section = self._get_section_weight(chunk.get('section_type', 'other'))
            w_recency = self._compute_recency_weight(chunk.get('filing_date'))
            w_size = self._compute_size_weight(chunk.get('original_sentence', ''))
            w_i = w_section * w_recency * w_size
            
            # Compute similarity (aggregate across legislation chunks)
            chunk_embedding = chunk.get('embedding')
            if chunk_embedding is None:
                continue
            
            if isinstance(chunk_embedding, list):
                chunk_embedding = np.array(chunk_embedding)
            
            sim_i = self._aggregate_similarity(chunk_embedding, legislation_embeddings)
            
            # Apply threshold
            if sim_i < self.sim_threshold:
                continue
            
            # Compute exposure
            exposure_i = sim_i * w_i
            
            chunk_data.append({
                'chunk': chunk,
                'weight': w_i,
                'similarity': sim_i,
                'exposure': exposure_i,
                'w_section': w_section,
                'w_recency': w_recency,
                'w_size': w_size
            })
        
        if not chunk_data:
            return self._empty_score()
        
        # Step 2: Compute raw score
        total_exposure = sum(cd['exposure'] for cd in chunk_data)
        total_weight = sum(cd['weight'] for cd in chunk_data)
        
        eps = 1e-12
        raw_score = total_exposure / (total_weight + eps)
        raw_score = min(1.0, max(0.0, raw_score))  # Clamp to [0,1]
        
        # Step 3: Compute sensitivity
        sensitivity = self._compute_sensitivity(company_metadata)
        
        # Step 4: Adjusted score
        adjusted_score = raw_score * sensitivity
        
        # Step 5: External probability adjustment
        final_expected = adjusted_score * polymarket_p
        final_worst = adjusted_score
        
        # Step 6: Risk categorization
        risk_level = self._classify_risk(final_expected)
        
        # Step 7: Get top contributors
        top_contributors = self._get_top_contributors(chunk_data, top_n=10)
        
        # Step 8: Build explanation
        explanation = self._build_explanation(
            raw_score=raw_score,
            sensitivity=sensitivity,
            adjusted_score=adjusted_score,
            final_expected=final_expected,
            final_worst=final_worst,
            risk_level=risk_level,
            top_contributors=top_contributors,
            total_chunks=len(chunk_data),
            company_metadata=company_metadata,
            polymarket_p=polymarket_p
        )
        
        return {
            'raw_score': float(raw_score),
            'sensitivity': float(sensitivity),
            'adjusted_score': float(adjusted_score),
            'final_expected': float(final_expected),
            'final_worst': float(final_worst),
            'risk_level': risk_level,
            'top_contributors': top_contributors,
            'explanation': explanation,
            'total_matches': len(chunk_data),
            'total_exposure': float(total_exposure),
            'total_weight': float(total_weight)
        }
    
    def _get_section_weight(self, section_type: str) -> float:
        """Get weight for section type."""
        return self.section_weights.get(section_type.lower(), 0.5)
    
    def _compute_recency_weight(self, filing_date: Optional[Any]) -> float:
        """
        Compute recency weight using exponential decay.
        
        w_recency = exp(-λ * age_days)
        """
        if not filing_date:
            return 0.5  # Default for missing dates
        
        try:
            if isinstance(filing_date, str):
                # Parse ISO format
                if 'T' in filing_date:
                    date_obj = datetime.fromisoformat(filing_date.split('T')[0]).date()
                else:
                    date_obj = datetime.fromisoformat(filing_date).date()
            elif isinstance(filing_date, date):
                date_obj = filing_date
            else:
                return 0.5
            
            age_days = (date.today() - date_obj).days
            if age_days < 0:
                age_days = 0  # Future dates -> weight = 1.0
            
            w_recency = np.exp(-self.lambda_recency * age_days)
            return min(1.0, max(0.0, w_recency))
        except Exception as e:
            logger.warning(f"[WARN] Failed to parse date '{filing_date}': {e}")
            return 0.5
    
    def _compute_size_weight(self, text: str) -> float:
        """
        Compute size weight based on token count.
        
        w_size = min(1.0, length_tokens / token_base)
        """
        if not text:
            return 0.5
        
        # Rough token estimate: ~4 chars per token
        estimated_tokens = len(text) / 4
        w_size = min(1.0, estimated_tokens / self.token_base)
        return max(0.1, w_size)  # Minimum 0.1 to avoid zero weights
    
    def _aggregate_similarity(
        self,
        chunk_embedding: np.ndarray,
        legislation_embeddings: List[np.ndarray]
    ) -> float:
        """
        Aggregate similarity across multiple legislation chunks.
        
        Args:
            chunk_embedding: Single company chunk embedding
            legislation_embeddings: List of legislation chunk embeddings
            
        Returns:
            Aggregated similarity score (0-1)
        """
        if not legislation_embeddings:
            return 0.0
        
        similarities = []
        for leg_emb in legislation_embeddings:
            if isinstance(leg_emb, list):
                leg_emb = np.array(leg_emb)
            
            sim = self._cosine_similarity(chunk_embedding, leg_emb)
            similarities.append(sim)
        
        if self.aggregation_method == 'max':
            return max(similarities) if similarities else 0.0
        elif self.aggregation_method == 'weighted_avg':
            # Equal weights for now (can be enhanced)
            return np.mean(similarities) if similarities else 0.0
        else:
            return max(similarities) if similarities else 0.0
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        eps = 1e-12
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a < eps or norm_b < eps:
            return 0.0
        
        dot_product = np.dot(a, b)
        similarity = dot_product / (norm_a * norm_b + eps)
        return float(np.clip(similarity, -1.0, 1.0))
    
    def _compute_sensitivity(self, company_metadata: Dict[str, Any]) -> float:
        """
        Compute company sensitivity factor.
        
        s_c = clamp(α1*revenue_exposed + α2*margin_sensitivity + α3*supply_chain + α4*legal, 0, 1)
        """
        revenue_exposed = self._estimate_revenue_exposed(company_metadata)
        margin_sensitivity = company_metadata.get('margin_sensitivity', 0.2)
        supply_chain_dep = company_metadata.get('supply_chain_dependency', 0.0)
        legal_exposure = company_metadata.get('legal_exposure', 0.0)
        
        weights = self.sensitivity_weights
        s_c = (
            weights['revenue_exposed'] * revenue_exposed +
            weights['margin_sensitivity'] * margin_sensitivity +
            weights['supply_chain_dependency'] * supply_chain_dep +
            weights.get('legal_exposure', 0.0) * legal_exposure
        )
        
        return float(np.clip(s_c, 0.0, 1.0))
    
    def _estimate_revenue_exposed(self, company_metadata: Dict[str, Any]) -> float:
        """
        Estimate revenue exposure to affected regions/products.
        
        Returns value in [0,1] representing share of revenue at risk.
        """
        revenue_by_region = company_metadata.get('revenue_by_region', {})
        
        # If explicit revenue data available, use it
        if revenue_by_region:
            # Sum revenue from affected regions (this could be configurable)
            # For now, assume affected regions are passed in metadata
            affected_regions = company_metadata.get('affected_regions', [])
            if affected_regions:
                total_revenue = sum(revenue_by_region.values())
                if total_revenue > 0:
                    exposed_revenue = sum(
                        revenue_by_region.get(region, 0) 
                        for region in affected_regions
                    )
                    return exposed_revenue / total_revenue
        
        # Fallback: heuristic based on entities mentioned in filings
        # This is a placeholder - could be enhanced with entity extraction
        entities = company_metadata.get('entities', {})
        countries = entities.get('countries', [])
        
        # If company mentions China, Taiwan, Vietnam (common tariff targets), assume some exposure
        high_risk_countries = {'china', 'taiwan', 'vietnam', 'india', 'south korea'}
        if any(c.lower() in high_risk_countries for c in countries):
            return 0.4  # Heuristic: 40% exposure
        
        return 0.2  # Default: 20% exposure
    
    def _classify_risk(self, score: float) -> str:
        """Classify risk level from score."""
        if score >= RISK_THRESHOLDS['critical'][0]:
            return 'critical'
        elif score >= RISK_THRESHOLDS['high'][0]:
            return 'high'
        elif score >= RISK_THRESHOLDS['medium'][0]:
            return 'medium'
        else:
            return 'low'
    
    def _get_top_contributors(
        self,
        chunk_data: List[Dict[str, Any]],
        top_n: int = 10
    ) -> List[Dict[str, Any]]:
        """Get top N contributing chunks sorted by exposure."""
        sorted_chunks = sorted(chunk_data, key=lambda x: x['exposure'], reverse=True)
        
        contributors = []
        for cd in sorted_chunks[:top_n]:
            chunk = cd['chunk']
            contributors.append({
                'section_type': chunk.get('section_type', 'unknown'),
                'section_title': chunk.get('section_title', ''),
                'filing_type': chunk.get('filing_type', 'N/A'),
                'filing_date': chunk.get('filing_date', 'N/A'),
                'sentence_text': chunk.get('original_sentence', '')[:200] + '...' if len(chunk.get('original_sentence', '')) > 200 else chunk.get('original_sentence', ''),
                'similarity': float(cd['similarity']),
                'weight': float(cd['weight']),
                'exposure': float(cd['exposure']),
                'w_section': float(cd['w_section']),
                'w_recency': float(cd['w_recency']),
                'w_size': float(cd['w_size'])
            })
        
        return contributors
    
    def _build_explanation(
        self,
        raw_score: float,
        sensitivity: float,
        adjusted_score: float,
        final_expected: float,
        final_worst: float,
        risk_level: str,
        top_contributors: List[Dict[str, Any]],
        total_chunks: int,
        company_metadata: Dict[str, Any],
        polymarket_p: float
    ) -> Dict[str, Any]:
        """Build detailed explanation object."""
        return {
            'summary': f"Risk Level: {risk_level.upper()}, Score: {final_expected:.3f}",
            'raw_score': float(raw_score),
            'sensitivity_breakdown': {
                'overall_sensitivity': float(sensitivity),
                'revenue_exposed': float(self._estimate_revenue_exposed(company_metadata)),
                'margin_sensitivity': company_metadata.get('margin_sensitivity', 0.0),
                'supply_chain_dependency': company_metadata.get('supply_chain_dependency', 0.0)
            },
            'adjustments': {
                'polymarket_probability': float(polymarket_p),
                'expected_score': float(final_expected),
                'worst_case_score': float(final_worst)
            },
            'top_contributors': top_contributors,
            'statistics': {
                'total_matching_chunks': total_chunks,
                'section_breakdown': self._get_section_breakdown(top_contributors)
            }
        }
    
    def _get_section_breakdown(self, contributors: List[Dict[str, Any]]) -> Dict[str, int]:
        """Get count of contributors by section type."""
        breakdown = {}
        for contrib in contributors:
            section = contrib.get('section_type', 'unknown')
            breakdown[section] = breakdown.get(section, 0) + 1
        return breakdown
    
    def _empty_score(self) -> Dict[str, Any]:
        """Return empty score structure."""
        return {
            'raw_score': 0.0,
            'sensitivity': 0.0,
            'adjusted_score': 0.0,
            'final_expected': 0.0,
            'final_worst': 0.0,
            'risk_level': 'low',
            'top_contributors': [],
            'explanation': {'summary': 'No matches found'},
            'total_matches': 0,
            'total_exposure': 0.0,
            'total_weight': 0.0
        }
    
    def get_recommendations(self, final_score: float, risk_level: str, company_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate actionable recommendations based on risk score.
        
        Returns:
            Dictionary with recommendation details
        """
        market_cap = company_metadata.get('market_cap', 0.0)
        
        if risk_level == 'critical':
            reduction = min(0.8, 0.6 * final_score)
            return {
                'action': 'reduce_weight_aggressively',
                'suggested_reduction': float(reduction),
                'hedge_recommended': True,
                'monitoring': 'immediate_analyst_review',
                'recommendations': [
                    f"Reduce position by up to {reduction*100:.0f}%",
                    "Consider buying puts or short sector ETF exposure",
                    "Flag for immediate legal review",
                    "Monitor news and filings daily"
                ]
            }
        elif risk_level == 'high':
            reduction = min(0.4, 0.3 * final_score)
            return {
                'action': 'trim_position',
                'suggested_reduction': float(reduction),
                'hedge_recommended': True,
                'monitoring': 'daily',
                'recommendations': [
                    f"Trim position by {reduction*100:.0f}%",
                    "Consider partial hedges",
                    "Monitor news and filings daily"
                ]
            }
        elif risk_level == 'medium':
            return {
                'action': 'monitor_closely',
                'suggested_reduction': 0.0,
                'hedge_recommended': market_cap > 1e9,  # Only for large caps
                'monitoring': 'set_alerts',
                'recommendations': [
                    "No immediate trade action",
                    "Monitor closely and set alerts",
                    "Consider small hedges if position is large"
                ]
            }
        else:  # low
            return {
                'action': 'no_action',
                'suggested_reduction': 0.0,
                'hedge_recommended': False,
                'monitoring': 'normal',
                'recommendations': [
                    "No action required",
                    "Continue normal monitoring"
                ]
            }

