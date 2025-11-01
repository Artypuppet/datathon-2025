"""
Parser Factory for automatically selecting the appropriate parser.
"""

from pathlib import Path
from typing import Optional
import logging

from .base import BaseParser
from .csv_parser import CSVParser
from .html_filing_parser import HTMLFilingParser
from .html_legislation_parser import HTMLLegislationParser

logger = logging.getLogger(__name__)


class ParserFactory:
    """Factory for creating appropriate parser for a given file."""
    
    def __init__(self):
        """Initialize factory with all available parsers."""
        self.parsers = [
            CSVParser(),
            HTMLFilingParser(),
            HTMLLegislationParser(),
        ]
    
    def get_parser(self, file_path: Path) -> Optional[BaseParser]:
        """
        Get appropriate parser for the given file.
        
        Args:
            file_path: Path to file to parse
            
        Returns:
            Parser instance if one can handle the file, None otherwise
        """
        for parser in self.parsers:
            if parser.can_parse(file_path):
                logger.info(f"[INFO] Selected {parser.__class__.__name__} for {file_path.name}")
                return parser
        
        logger.warning(f"[WARN] No parser found for {file_path.name}")
        return None
    
    def parse_file(self, file_path: Path):
        """
        Automatically select parser and parse file.
        
        Args:
            file_path: Path to file to parse
            
        Returns:
            ParseResult or None if no parser found
        """
        parser = self.get_parser(file_path)
        if parser:
            return parser.parse(file_path)
        
        return None

