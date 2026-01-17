"""
Data transformer for converting test results JSON to CompanyRiskProfile format.

Converts the output from vector similarity tests into the format expected
by the Streamlit dashboard.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from collections import defaultdict

from .data_models import (
    CompanyRiskProfile,
    LegislationContribution,
    SentenceContribution
)

logger = logging.getLogger(__name__)


class RiskDataTransformer:
    """
    Transforms test results JSON into CompanyRiskProfile format.
    
    Handles the conversion from the format:
    {
        "legislation_id": "...",
        "ticker": "...",
        "impact_score": 0.5,
        "matched_sentences": [...]
    }
    
    To the format:
    {
        "company_name": "...",
        "risk_score": 78.2,
        "legislations": [...]
    }
    """
    
    def __init__(self):
        """Initialize transformer."""
        pass
    
    def transform_from_test_results(
        self,
        test_results_path: Path,
        output_path: Optional[Path] = None
    ) -> List[CompanyRiskProfile]:
        """
        Transform test results JSON file to list of CompanyRiskProfile.
        
        Args:
            test_results_path: Path to test results JSON file
            output_path: Optional path to save transformed data
            
        Returns:
            List of CompanyRiskProfile objects
        """
        logger.info(f"[INFO] Loading test results from {test_results_path}")
        
        try:
            with open(test_results_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"[ERROR] Failed to load test results: {e}")
            return []
        
        # Group by ticker and legislation
        company_data = defaultdict(lambda: defaultdict(list))
        
        # If single result (one legislation for one company)
        if isinstance(data, dict) and 'ticker' in data:
            ticker = data.get('ticker', 'UNKNOWN')
            legislation_id = data.get('legislation_id', 'Unknown Legislation')
            company_data[ticker][legislation_id] = data
        
        # If list of results
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and 'ticker' in item:
                    ticker = item.get('ticker', 'UNKNOWN')
                    legislation_id = item.get('legislation_id', 'Unknown Legislation')
                    company_data[ticker][legislation_id] = item
        
        # Transform to CompanyRiskProfile
        profiles = []
        for ticker, legislations_dict in company_data.items():
            profile = self._create_profile_from_dict(ticker, legislations_dict)
            if profile:
                profiles.append(profile)
        
        logger.info(f"[OK] Transformed {len(profiles)} company profiles")
        
        # Save if output path provided
        if output_path:
            self.save_profiles(profiles, output_path)
        
        return profiles
    
    def _create_profile_from_dict(
        self,
        ticker: str,
        legislations_dict: Dict[str, Dict[str, Any]]
    ) -> Optional[CompanyRiskProfile]:
        """
        Create CompanyRiskProfile from grouped legislation data.
        
        Args:
            ticker: Company ticker
            legislations_dict: Dict mapping legislation_id to test results
            
        Returns:
            CompanyRiskProfile or None if invalid
        """
        legislations = []
        total_impact = 0.0
        
        for legislation_id, result_data in legislations_dict.items():
            impact_score = result_data.get('impact_score', 0.0)
            risk_level = result_data.get('risk_level', 'unknown')
            matched_sentences = result_data.get('matched_sentences', [])
            
            # Convert matched sentences to SentenceContribution
            sentence_contributions = []
            for match in matched_sentences[:50]:  # Top 50 sentences
                similarity = match.get('similarity', 0.0)
                sentence_text = match.get('original_sentence', '')
                
                if sentence_text:
                    sentence_contributions.append(
                        SentenceContribution(
                            sentence=sentence_text[:500],  # Truncate long sentences
                            similarity_score=float(similarity),
                            section_title=match.get('section_title'),
                            section_type=match.get('section_type'),
                            filing_date=match.get('filing_date')
                        )
                    )
            
            # Calculate contribution percent (normalized impact score * 100)
            # If multiple legislations, each contributes proportionally
            contribution_percent = impact_score * 100
            
            legislation_contrib = LegislationContribution(
                legislation_name=self._format_legislation_name(legislation_id),
                contribution_percent=contribution_percent,
                top_sentences=sentence_contributions,
                impact_score=impact_score,
                risk_level=risk_level
            )
            
            legislations.append(legislation_contrib)
            total_impact += impact_score
        
        # Overall risk score is the maximum impact or weighted average
        # For MVP, use max impact converted to 0-100 scale
        risk_score = min(100.0, max(legislations, key=lambda x: x.impact_score or 0.0).impact_score * 100) if legislations else 0.0
        
        # Determine overall risk level
        if risk_score >= 70:
            overall_risk_level = 'high'
        elif risk_score >= 40:
            overall_risk_level = 'medium'
        else:
            overall_risk_level = 'low'
        
        # Get company name from first result or use ticker
        company_name = ticker
        if legislations_dict:
            first_result = list(legislations_dict.values())[0]
            company_name = first_result.get('company_name', ticker)
        
        return CompanyRiskProfile(
            company_name=company_name,
            ticker=ticker.upper(),
            risk_score=risk_score,
            risk_level=overall_risk_level,
            legislations=legislations
        )
    
    def _format_legislation_name(self, legislation_id: str) -> str:
        """
        Format legislation ID to readable name.
        
        Args:
            legislation_id: Raw legislation ID
            
        Returns:
            Formatted name
        """
        # Replace underscores and format
        name = legislation_id.replace('_', ' ')
        
        # Split by common patterns
        if '_' in legislation_id:
            parts = legislation_id.split('_')
            if len(parts) >= 2:
                # Try to extract readable parts
                name = ' '.join(parts[1:])  # Skip prefix like "US_"
        
        return name.title()
    
    def save_profiles(
        self,
        profiles: List[CompanyRiskProfile],
        output_path: Path
    ) -> None:
        """
        Save profiles to JSON file.
        
        Args:
            profiles: List of CompanyRiskProfile objects
            output_path: Path to save JSON file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to dict format
        data = []
        for profile in profiles:
            profile_dict = {
                'company_name': profile.company_name,
                'ticker': profile.ticker,
                'risk_score': profile.risk_score,
                'risk_level': profile.risk_level,
                'legislations': [
                    {
                        'legislation_name': leg.legislation_name,
                        'contribution_percent': leg.contribution_percent,
                        'impact_score': leg.impact_score,
                        'risk_level': leg.risk_level,
                        'top_sentences': [
                            {
                                'sentence': sent.sentence,
                                'similarity_score': sent.similarity_score,
                                'section_title': sent.section_title,
                                'section_type': sent.section_type,
                                'filing_date': sent.filing_date
                            }
                            for sent in leg.top_sentences
                        ]
                    }
                    for leg in profile.legislations
                ]
            }
            data.append(profile_dict)
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"[OK] Saved {len(profiles)} profiles to {output_path}")
        except Exception as e:
            logger.error(f"[ERROR] Failed to save profiles: {e}")
            raise

