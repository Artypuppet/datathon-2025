"""
Dashboard module for Streamlit UI.
"""

from .upload_widget import FileUploadWidget
from .risk_factors_widget import RiskFactorsWidget
from .data_models import (
    CompanyRiskProfile,
    LegislationContribution,
    SentenceContribution
)
from .data_transformer import RiskDataTransformer

__all__ = [
    'FileUploadWidget',
    'RiskFactorsWidget',
    'CompanyRiskProfile',
    'LegislationContribution',
    'SentenceContribution',
    'RiskDataTransformer'
]

