"""
Google Gemini 1.5 Pro client for LLM analysis.

Provides methods for:
- Legislation summarization
- Entity extraction from SEC filings
- Risk recommendation generation
"""

import logging
import os
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

try:
    # Try newer API first (if available)
    from google import genai
except ImportError:
    # Fallback to standard google-generativeai package
    import google.generativeai as genai

logger = logging.getLogger(__name__)


# Pydantic models for structured output
class Relationship(BaseModel):
    """Relationship between entities."""
    type: str = Field(description="Relationship type (e.g., SUPPLIES_TO, OPERATES_IN)")
    target: str = Field(description="Target entity name")
    evidence: str = Field(description="Sentence from filing that provides evidence for this relationship")


class ExtractedEntities(BaseModel):
    """Extracted entities from SEC filing."""
    suppliers: List[str] = Field(description="List of suppliers and major partners mentioned")
    countries: List[str] = Field(description="List of countries/regions where company operates or has supply chains")
    operations: List[str] = Field(description="List of business operations and segments")
    sectors: List[str] = Field(description="List of sectors/industries the company operates in")
    relationships: List[Relationship] = Field(description="List of relationships between entities")


class TraceableParagraph(BaseModel):
    """Traceable paragraph from filing."""
    section: str = Field(description="Section identifier (e.g., Item 1A)")
    text: str = Field(description="Relevant sentence from filing")
    relevance: str = Field(description="Explanation of why this paragraph matters")


class Recommendation(BaseModel):
    """Trading recommendation."""
    recommendation: str = Field(description="Recommendation: buy, sell, trim, or neutral")
    reasoning: str = Field(description="2-3 sentence explanation for the recommendation")
    kelly_fraction: float = Field(description="Kelly Criterion fraction (0.0-1.0)")
    position_sizing: str = Field(description="Specific recommendation (e.g., 'Reduce position by 30%')")
    impact_magnitude: float = Field(description="Estimated impact magnitude if law passes (0.0-1.0)")
    traceable_paragraphs: List[TraceableParagraph] = Field(description="List of traceable paragraphs from filings")
    confidence: int = Field(description="Confidence level (0-100)")


class GeminiClient:
    """
    Client for Google Gemini 1.5 Pro operations.
    
    Uses Gemini for summarization, entity extraction, and recommendations.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-1.5-pro"
    ):
        """
        Initialize Gemini client.
        
        Args:
            api_key: Google AI API key (defaults to GEMINI_API_KEY env var)
            model_name: Gemini model name (default: gemini-1.5-pro)
        """
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY must be provided via env var or constructor")
        
        # Try to use Client API (newer SDK), fallback to GenerativeModel (older SDK)
        try:
            self.client = genai.Client(api_key=self.api_key)
            self.use_client_api = True
        except (AttributeError, TypeError):
            # Fallback to older API
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(model_name)
            self.use_client_api = False
        
        self.model_name = model_name
        
        logger.info(f"[OK] GeminiClient initialized with model: {model_name}")
    
    def summarize_legislation(
        self,
        legislation_text: str,
        legislation_id: Optional[str] = None
    ) -> str:
        """
        Generate a concise summary of legislation.
        
        Args:
            legislation_text: Full text of the legislation
            legislation_id: Optional identifier for logging
        
        Returns:
            Summarized text (2-3 sentences)
        """
        logger.info(f"[INFO] Summarizing legislation: {legislation_id or 'unknown'}")
        
        # Limit text to avoid token limits (keep first 8000 chars)
        legislation_truncated = legislation_text[:8000]
        
        prompt = f"""You are an expert in regulatory and legal analysis.

Summarize the following legislation in 2-3 clear, concise sentences. Focus on:
1. What the legislation does
2. Who or what it affects
3. Key requirements or restrictions

**Legislation Text:**
{legislation_truncated}

Provide only the summary, no preamble or explanation."""

        try:
            if self.use_client_api:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt
                )
                summary = response.text.strip()
            else:
                response = self.model.generate_content(prompt)
                summary = response.text.strip()
            
            logger.info(f"[OK] Generated summary ({len(summary)} chars)")
            return summary
        except Exception as e:
            logger.error(f"[ERROR] Failed to generate summary: {e}")
            # Fallback
            return legislation_text[:500] + "..." if len(legislation_text) > 500 else legislation_text
    
    def extract_entities(
        self,
        filing_text: str,
        ticker: str,
        company_name: str
    ) -> Dict[str, Any]:
        """
        Extract entities and relationships from SEC filing text.
        
        Args:
            filing_text: Text from SEC filing (10-K)
            ticker: Company ticker
            company_name: Company name
        
        Returns:
            Dictionary with extracted entities:
            {
                "suppliers": List[str],
                "countries": List[str],
                "operations": List[str],
                "sectors": List[str],
                "relationships": List[Dict]
            }
        """
        logger.info(f"[INFO] Extracting entities for {ticker}")
        
        # Limit text to avoid token limits
        filing_truncated = filing_text[:10000]
        
        prompt = f"""You are an expert in financial document analysis.

Extract entities and relationships from the following SEC 10-K filing for {company_name} ({ticker}).

Focus on:
1. Suppliers and major partners mentioned
2. Countries/regions where company operates or has supply chains
3. Business operations and segments
4. Sectors/industries the company operates in

**Filing Text:**
{filing_truncated}"""

        try:
            if self.use_client_api:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json",
                        "response_json_schema": ExtractedEntities.model_json_schema(),
                    },
                )
                entities = ExtractedEntities.model_validate_json(response.text)
            else:
                # Fallback: use standard API with JSON mode
                generation_config = genai.types.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=ExtractedEntities.model_json_schema()
                )
                response = self.model.generate_content(
                    prompt,
                    generation_config=generation_config
                )
                entities = ExtractedEntities.model_validate_json(response.text)
            
            # Convert to dict format for backward compatibility
            entities_dict = {
                "suppliers": entities.suppliers,
                "countries": entities.countries,
                "operations": entities.operations,
                "sectors": entities.sectors,
                "relationships": [
                    {
                        "type": rel.type,
                        "target": rel.target,
                        "evidence": rel.evidence
                    }
                    for rel in entities.relationships
                ]
            }
            
            logger.info(f"[OK] Extracted entities: {len(entities.suppliers)} suppliers, {len(entities.countries)} countries")
            return entities_dict
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to extract entities: {e}", exc_info=True)
            return {
                "suppliers": [],
                "countries": [],
                "operations": [],
                "sectors": [],
                "relationships": []
            }
    
    def generate_recommendation(
        self,
        company_name: str,
        ticker: str,
        legislation_summary: str,
        matched_sentences: List[Dict[str, Any]],
        risk_score: float,
        polymarket_probability: float,
        neo4j_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate trading recommendation using Kelly Criterion and context.
        
        Args:
            company_name: Company name
            ticker: Company ticker
            legislation_summary: Summarized legislation text
            matched_sentences: List of matched sentences from filings
            risk_score: Computed risk score (0-1)
            polymarket_probability: Polymarket probability of law passing (0-1)
            neo4j_context: Optional Neo4j graph context
        
        Returns:
            Dictionary with recommendation:
            {
                "recommendation": "buy|sell|trim|neutral",
                "reasoning": str,
                "kelly_fraction": float,
                "position_sizing": str,
                "traceable_paragraphs": List[Dict]
            }
        """
        logger.info(f"[INFO] Generating recommendation for {ticker}")
        
        # Format matched sentences
        sentences_text = "\n\n".join([
            f"{i+1}. [{s.get('section_type', 'unknown')}] {s.get('original_sentence', '')[:200]}"
            for i, s in enumerate(matched_sentences[:10])
        ])
        
        # Format Neo4j context if available
        context_text = ""
        if neo4j_context:
            suppliers = [n.get('name') for n in neo4j_context.get('related_nodes', []) if n.get('labels', []) == ['Supplier']]
            if suppliers:
                context_text = f"\n**Supply Chain Context:** Company relies on: {', '.join(suppliers[:5])}"
        
        prompt = f"""You are a quantitative risk manager analyzing regulatory risk.

**Company:** {company_name} ({ticker})
**Legislation:** {legislation_summary}
**Risk Score:** {risk_score:.3f}
**Polymarket Probability:** {polymarket_probability:.1%} chance of passing

**Relevant Company Disclosures:**
{sentences_text}
{context_text}

Generate a trading recommendation using Kelly Criterion for position sizing.

Calculate:
- f* = (p * b - q) / b
  where p = probability of law passing ({polymarket_probability:.3f})
        q = 1 - p
        b = estimated impact magnitude (if law passes, estimate % impact on stock price)

The recommendation must be one of: buy, sell, trim, or neutral."""

        try:
            if self.use_client_api:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json",
                        "response_json_schema": Recommendation.model_json_schema(),
                    },
                )
                recommendation_model = Recommendation.model_validate_json(response.text)
            else:
                # Fallback: use standard API with JSON mode
                generation_config = genai.types.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=Recommendation.model_json_schema()
                )
                response = self.model.generate_content(
                    prompt,
                    generation_config=generation_config
                )
                recommendation_model = Recommendation.model_validate_json(response.text)
            
            # Validate recommendation value
            valid_recs = ['buy', 'sell', 'trim', 'neutral']
            rec_value = recommendation_model.recommendation.lower()
            if rec_value not in valid_recs:
                logger.warning(f"[WARN] Invalid recommendation '{rec_value}', defaulting to 'neutral'")
                rec_value = 'neutral'
            
            # Convert to dict format for backward compatibility
            recommendation_dict = {
                "recommendation": rec_value,
                "reasoning": recommendation_model.reasoning,
                "kelly_fraction": recommendation_model.kelly_fraction,
                "position_sizing": recommendation_model.position_sizing,
                "impact_magnitude": recommendation_model.impact_magnitude,
                "traceable_paragraphs": [
                    {
                        "section": p.section,
                        "text": p.text,
                        "relevance": p.relevance
                    }
                    for p in recommendation_model.traceable_paragraphs
                ],
                "confidence": recommendation_model.confidence
            }
            
            logger.info(f"[OK] Generated recommendation: {rec_value}")
            return recommendation_dict
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to generate recommendation: {e}", exc_info=True)
            return self._default_recommendation(ticker, risk_score)
    
    def _default_recommendation(self, ticker: str, risk_score: float) -> Dict[str, Any]:
        """Return default recommendation when LLM fails."""
        return {
            "recommendation": "neutral",
            "reasoning": "Unable to generate recommendation due to processing error.",
            "kelly_fraction": 0.0,
            "position_sizing": "No action recommended",
            "impact_magnitude": 0.0,
            "traceable_paragraphs": [],
            "confidence": 0
        }
