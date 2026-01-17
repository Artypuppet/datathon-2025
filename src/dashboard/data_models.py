"""
Data models for regulatory risk dashboard.

Defines the data structures used to represent company risk profiles
and their contributions from legislation.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class SentenceContribution:
    """Represents a sentence from a filing with its similarity score to legislation."""
    sentence: str
    similarity_score: float
    section_title: Optional[str] = None
    section_type: Optional[str] = None
    filing_date: Optional[str] = None


@dataclass
class LegislationContribution:
    """Represents how a specific legislation contributes to a company's risk."""
    legislation_name: str
    contribution_percent: float
    top_sentences: List[SentenceContribution]
    impact_score: Optional[float] = None
    risk_level: Optional[str] = None


@dataclass
class CompanyRiskProfile:
    """Complete risk profile for a company."""
    company_name: str
    ticker: str
    risk_score: float
    risk_level: Optional[str] = None
    legislations: List[LegislationContribution] = None
    
    def __post_init__(self):
        """Initialize default empty list if None."""
        if self.legislations is None:
            self.legislations = []

