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
    from .metadata_cache import MetadataCache
    from .graph_builder import KnowledgeGraphBuilder
    
    __all__ = [
        'EntityExtractor',
        'ContextualEnricher',
        'CompanyKnowledgeDB',
        'YahooFinanceProvider',
        'FinancialModelingPrepProvider',
        'CompanyDataProvider',
        'MetadataCache',
        'KnowledgeGraphBuilder'
    ]
except ImportError:
    __all__ = [
        'EntityExtractor',
        'ContextualEnricher',
        'CompanyKnowledgeDB'
    ]
    
    # Try to import what's available
    try:
        from .metadata_cache import MetadataCache
        __all__.append('MetadataCache')
    except ImportError:
        pass
    
    try:
        from .graph_builder import KnowledgeGraphBuilder
        __all__.append('KnowledgeGraphBuilder')
    except ImportError:
        pass

