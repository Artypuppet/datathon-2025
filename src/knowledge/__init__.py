"""
Knowledge extraction and enrichment modules.
"""

from .entity_extractor import EntityExtractor
from .contextual_enricher import ContextualEnricher
from .company_knowledge_db import CompanyKnowledgeDB

try:
    from .data_providers import (
        YahooFinanceProvider,
        FinancialModelingPrepProvider,
        CompanyDataProvider
    )
    __all__ = [
        'EntityExtractor',
        'ContextualEnricher',
        'CompanyKnowledgeDB',
        'YahooFinanceProvider',
        'FinancialModelingPrepProvider',
        'CompanyDataProvider'
    ]
except ImportError:
    __all__ = [
        'EntityExtractor',
        'ContextualEnricher',
        'CompanyKnowledgeDB'
    ]

