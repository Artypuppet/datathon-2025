"""
LLM-based risk factor analysis for legislation impact.

Uses AWS Bedrock (Claude) to:
1. Summarize legislation text
2. Analyze impact on companies based on semantic matches
3. Provide structured recommendations
"""

import logging
import json
import re
from typing import Dict, Any, List, Optional
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class LLMAnalyzer:
    """
    LLM-based analyzer using AWS Bedrock (Claude) for risk analysis.
    
    Features:
    - Legislation summarization
    - Impact analysis with structured JSON output
    - Recommendation generation (buy/sell/trim/rotate/neutral)
    """
    
    # Claude model IDs (most recent versions)
    CLAUDE_3_5_SONNET = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    CLAUDE_3_SONNET = "anthropic.claude-3-sonnet-20240229-v1:0"
    CLAUDE_3_HAIKU = "anthropic.claude-3-haiku-20240307-v1:0"
    
    def __init__(
        self,
        model_id: str = None,
        region_name: str = "us-east-1",
        temperature: float = 0.2,
        max_tokens: int = 1000,
        use_bedrock: bool = True
    ):
        """
        Initialize LLM analyzer.
        
        Args:
            model_id: Claude model ID (defaults to Claude 3.5 Sonnet)
            region_name: AWS region for Bedrock (default: us-east-1)
            temperature: Sampling temperature (0-1, lower = more deterministic)
            max_tokens: Maximum tokens in response
            use_bedrock: Whether to use Bedrock (True) or mock (False) for testing
        """
        self.model_id = model_id or self.CLAUDE_3_5_SONNET
        self.region_name = region_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.use_bedrock = use_bedrock
        
        if use_bedrock:
            try:
                self.client = boto3.client(
                    "bedrock-runtime",
                    region_name=region_name
                )
                logger.info(f"[OK] Bedrock client initialized for region: {region_name}")
            except Exception as e:
                logger.error(f"[ERROR] Failed to initialize Bedrock client: {e}")
                raise
        else:
            self.client = None
            logger.warning("[WARN] Using mock mode (use_bedrock=False)")
        
        logger.info(f"[INFO] LLMAnalyzer initialized")
        logger.info(f"  Model: {self.model_id}")
        logger.info(f"  Temperature: {temperature}")
        logger.info(f"  Max tokens: {max_tokens}")
    
    def summarize_legislation(
        self,
        legislation_text: str,
        legislation_id: Optional[str] = None
    ) -> str:
        """
        Generate a concise summary of legislation using Claude.
        
        Args:
            legislation_text: Full text of the legislation
            legislation_id: Optional identifier for logging
            
        Returns:
            Summarized text (2-3 sentences)
        """
        logger.info(f"[INFO] Summarizing legislation: {legislation_id or 'unknown'}")
        
        # Limit legislation text to avoid token limits (keep first 8000 chars)
        legislation_truncated = legislation_text[:8000]
        
        prompt = f"""You are an expert in regulatory and legal analysis.

Summarize the following legislation in 2-3 clear, concise sentences. Focus on:
1. What the legislation does
2. Who or what it affects
3. Key requirements or restrictions

**Legislation Text:**
{legislation_truncated}

Provide only the summary, no preamble or explanation."""

        response = self._invoke_claude(prompt)
        
        if response:
            summary = response.strip()
            logger.debug(f"[DEBUG] Generated summary ({len(summary)} chars)")
            return summary
        else:
            logger.warning("[WARN] Failed to generate summary, using fallback")
            return legislation_text[:500] + "..." if len(legislation_text) > 500 else legislation_text
    
    def analyze_impact(
        self,
        legislation_summary: str,
        company_name: str,
        ticker: str,
        matched_sentences: List[Dict[str, Any]],
        sector: Optional[str] = None,
        industry: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze impact of legislation on a company using semantic matches.
        
        Args:
            legislation_summary: Summarized legislation text
            company_name: Company name
            ticker: Company ticker symbol
            matched_sentences: List of semantically similar sentences from filings
            sector: Optional sector (e.g., "Technology")
            industry: Optional industry (e.g., "Consumer Electronics")
            
        Returns:
            Dictionary with structured analysis:
            {
                "impact_summary": str,
                "affected_risk_types": List[str],
                "business_impact": str,
                "recommendation": str,  # "buy", "sell", "trim", "rotate", "neutral"
                "recommendation_reasoning": str,
                "rotation_target": Optional[str],  # Ticker if recommendation is "rotate"
                "confidence": int,  # 0-100
                "mitigation_strategies": List[str]
            }
        """
        logger.info(f"[INFO] Analyzing impact for {company_name} ({ticker})")
        
        # Group and format matched sentences
        sentences_text = self._format_matched_sentences(matched_sentences)
        
        sector_info = f"\n**Sector:** {sector}" if sector else ""
        industry_info = f"\n**Industry:** {industry}" if industry else ""
        
        prompt = f"""You are an expert financial analyst specializing in regulatory risk assessment.

Analyze how the following legislation impacts {company_name} ({ticker}) based on their SEC filings.{sector_info}{industry_info}

**Legislation Summary:**
{legislation_summary}

**Relevant Company Disclosures:**
{sentences_text}

Provide a comprehensive analysis in the following JSON format (no markdown, valid JSON only):

{{
  "impact_summary": "2-3 sentence summary of overall impact",
  "affected_risk_types": ["Risk Category 1", "Risk Category 2"],
  "business_impact": "Detailed analysis of how this affects the business operations, revenue, margins, supply chain, etc.",
  "recommendation": "buy|sell|trim|rotate|neutral",
  "recommendation_reasoning": "Explanation for the recommendation (2-3 sentences)",
  "rotation_target": "TICKER or null",
  "confidence": 85,
  "mitigation_strategies": ["Strategy 1", "Strategy 2", "Strategy 3"]
}}

**Guidelines:**
- **buy**: Strong positive impact or minimal negative impact, good opportunity
- **sell**: Severe negative impact, high regulatory risk, material financial exposure
- **trim**: Moderate negative impact, reduce position size by 20-40%
- **rotate**: Similar risk exposure but better positioned alternative in same sector (specify rotation_target)
- **neutral**: Minimal impact or uncertain, maintain current position
- **confidence**: 0-100 based on clarity of impact and quality of evidence

Return ONLY valid JSON, no markdown, no code blocks."""

        response = self._invoke_claude(prompt)
        
        if not response:
            logger.error("[ERROR] Failed to get LLM analysis")
            return self._default_analysis(company_name, ticker)
        
        # Parse JSON from response
        analysis = self._parse_json_response(response)
        
        if not analysis:
            logger.warning("[WARN] Failed to parse JSON, using default")
            return self._default_analysis(company_name, ticker)
        
        # Validate and normalize recommendation
        analysis["recommendation"] = self._normalize_recommendation(
            analysis.get("recommendation", "neutral")
        )
        
        logger.info(f"[OK] Generated analysis: {analysis.get('recommendation', 'neutral')} (confidence: {analysis.get('confidence', 0)})")
        
        return analysis
    
    def _format_matched_sentences(self, matched_sentences: List[Dict[str, Any]], limit: int = 10) -> str:
        """
        Format matched sentences for LLM prompt.
        
        Args:
            matched_sentences: List of matched sentence dictionaries
            limit: Maximum number of sentences to include
            
        Returns:
            Formatted string
        """
        if not matched_sentences:
            return "No relevant disclosures found."
        
        formatted = []
        top_matches = matched_sentences[:limit]
        
        for i, match in enumerate(top_matches, 1):
            sentence = match.get("sentence", match.get("text", ""))
            similarity = match.get("similarity", match.get("similarity_score", 0))
            section = match.get("section_type", match.get("section", "unknown"))
            filing_type = match.get("filing_type", "N/A")
            filing_date = match.get("filing_date", "N/A")
            
            formatted.append(
                f"{i}. [Similarity: {similarity:.2f}] [{section}] [{filing_type} - {filing_date}]\n"
                f"   {sentence}"
            )
        
        return "\n\n".join(formatted)
    
    def _invoke_claude(self, prompt: str) -> Optional[str]:
        """
        Invoke Claude model via Bedrock.
        
        Args:
            prompt: User prompt
            
        Returns:
            Response text or None if error
        """
        if not self.use_bedrock:
            # Mock response for testing
            logger.debug("[DEBUG] Mock mode: returning mock response")
            return '{"impact_summary": "Mock analysis", "recommendation": "neutral", "confidence": 50}'
        
        try:
            # Format request for Claude Messages API
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "top_p": 0.9,
                "messages": [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": prompt}]
                    }
                ]
            }
            
            logger.debug(f"[DEBUG] Invoking Claude model: {self.model_id}")
            
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body),
                accept="application/json",
                contentType="application/json"
            )
            
            response_body = json.loads(response["body"].read())
            
            # Extract text from response
            if "content" in response_body and len(response_body["content"]) > 0:
                text = response_body["content"][0].get("text", "")
                logger.debug(f"[DEBUG] Received response ({len(text)} chars)")
                return text
            else:
                logger.error(f"[ERROR] Unexpected response structure: {response_body}")
                return None
                
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_msg = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"[ERROR] Bedrock API error ({error_code}): {error_msg}")
            return None
        except Exception as e:
            logger.error(f"[ERROR] Failed to invoke Claude: {e}")
            return None
    
    def _parse_json_response(self, response: str) -> Optional[Dict[str, Any]]:
        """
        Parse JSON from LLM response, handling markdown code blocks.
        
        Args:
            response: Raw LLM response
            
        Returns:
            Parsed dictionary or None
        """
        if not response:
            return None
        
        # Remove markdown code blocks if present
        response = response.strip()
        
        # Try to extract JSON from code blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if json_match:
            response = json_match.group(1)
        
        # Try direct JSON parsing
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Try to find JSON object in text
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass
        
        logger.warning(f"[WARN] Failed to parse JSON from response: {response[:200]}...")
        return None
    
    def _normalize_recommendation(self, recommendation: str) -> str:
        """
        Normalize recommendation to valid values.
        
        Args:
            recommendation: Raw recommendation string
            
        Returns:
            Normalized recommendation (buy/sell/trim/rotate/neutral)
        """
        rec_lower = recommendation.lower().strip()
        
        valid_options = ["buy", "sell", "trim", "rotate", "neutral"]
        
        # Exact match
        if rec_lower in valid_options:
            return rec_lower
        
        # Fuzzy matching
        if "buy" in rec_lower or "purchase" in rec_lower or "increase" in rec_lower:
            return "buy"
        elif "sell" in rec_lower or "exit" in rec_lower or "liquidate" in rec_lower:
            return "sell"
        elif "trim" in rec_lower or "reduce" in rec_lower:
            return "trim"
        elif "rotate" in rec_lower or "swap" in rec_lower or "replace" in rec_lower:
            return "rotate"
        else:
            return "neutral"
    
    def _default_analysis(self, company_name: str, ticker: str) -> Dict[str, Any]:
        """
        Return default analysis when LLM call fails.
        
        Args:
            company_name: Company name
            ticker: Ticker symbol
            
        Returns:
            Default analysis dictionary
        """
        return {
            "impact_summary": f"Insufficient information to determine impact on {company_name}.",
            "affected_risk_types": [],
            "business_impact": "Unable to analyze impact due to processing error.",
            "recommendation": "neutral",
            "recommendation_reasoning": "No analysis available.",
            "rotation_target": None,
            "confidence": 0,
            "mitigation_strategies": ["Review regulatory filings for updates", "Monitor news and regulatory developments"]
        }

