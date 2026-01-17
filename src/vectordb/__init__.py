"""
Vector database module for storing and querying embeddings.

Supports:
- AWS OpenSearch (production)
- ChromaDB (local development)
"""

from .client import VectorDBClient, get_vectordb_client
from .inference import LegislationImpactAnalyzer
from .risk_scorer import RegulatoryRiskScorer
from .llm_analyzer import LLMAnalyzer

__all__ = [
    'VectorDBClient',
    'get_vectordb_client',
    'LegislationImpactAnalyzer',
    'RegulatoryRiskScorer',
    'LLMAnalyzer',
]

