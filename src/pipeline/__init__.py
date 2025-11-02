"""
Pipeline module for processing uploaded files.
"""

from .stage_parse import ParseStage
from .stage_aggregate import AggregateStage, CompanyAggregator
from .stage_parse_and_aggregate import ParseAndAggregateStage
from .stage_embed import EmbeddingStage
from .orchestrator import PipelineOrchestrator
from .config import PipelineConfig

__all__ = ['ParseStage', 'AggregateStage', 'CompanyAggregator', 'ParseAndAggregateStage', 'EmbeddingStage', 'PipelineOrchestrator', 'PipelineConfig']

