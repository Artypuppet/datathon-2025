"""
Parser Factory for automatically selecting the appropriate parser.
"""

from pathlib import Path
from typing import Optional
import logging

from .base import BaseParser, DocumentType
from .csv_parser import CSVParser
from .html_filing_parser import HTMLFilingParser
from .html_legislation_parser import HTMLLegislationParser

logger = logging.getLogger(__name__)


class ParserFactory:
    """Factory for creating appropriate parser for a given file."""
    
    def __init__(self):
        """Initialize factory with all available parsers."""
        # Order matters: most specific parsers first
        self.parsers = [
            CSVParser(),
            HTMLLegislationParser(),  # More specific than generic HTML filing
            HTMLFilingParser(),
        ]
        
        # Map document types to parser classes for explicit selection
        self.document_type_map = {
            DocumentType.CSV_FINANCIAL: CSVParser,
            DocumentType.HTML_FILING: HTMLFilingParser,
            DocumentType.HTML_LEGISLATION: HTMLLegislationParser,
            DocumentType.XML_LEGISLATION: HTMLLegislationParser,
        }
    
    def get_parser(self, file_path: Path, document_type: Optional[DocumentType] = None) -> Optional[BaseParser]:
        """
        Get appropriate parser for the given file.
        
        Args:
            file_path: Path to file to parse
            document_type: Optional explicit document type (for user-selected files)
            
        Returns:
            Parser instance if one can handle the file, None otherwise
        """
        # If document type is explicitly provided, use it directly (skip can_parse for temp files)
        if document_type and document_type in self.document_type_map:
            parser_class = self.document_type_map[document_type]
            parser = parser_class()
            logger.info(f"[INFO] Selected {parser.__class__.__name__} for {file_path.name} (type: {document_type.name})")
            return parser
        
        # Otherwise, auto-detect based on file
        for parser in self.parsers:
            if parser.can_parse(file_path):
                logger.info(f"[INFO] Selected {parser.__class__.__name__} for {file_path.name}")
                return parser
        
        logger.warning(f"[WARN] No parser found for {file_path.name}")
        return None
    
    def parse_file(self, file_path: Path, document_type: Optional[DocumentType] = None):
        """
        Automatically select parser and parse file.
        
        Args:
            file_path: Path to file to parse
            document_type: Optional explicit document type (for user-selected files)
            
        Returns:
            ParseResult or None if no parser found
        """
        parser = self.get_parser(file_path, document_type)
        if parser:
            return parser.parse(file_path)
        
        return None

