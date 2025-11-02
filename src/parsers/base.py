"""
Base classes for all parsers.

Defines the abstract interface and common structures.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


class DocumentType(Enum):
    """Supported document types."""
    CSV_FINANCIAL = "csv_financial"
    CSV_COMPOSITION = "csv_composition"
    HTML_FILING = "html_filing"
    HTML_LEGISLATION = "html_legislation"
    XML_LEGISLATION = "xml_legislation"
    PDF_DOCUMENT = "pdf_document"
    UNKNOWN = "unknown"


@dataclass
class ParseResult:
    """Standardized result from any parser."""
    
    success: bool
    document_type: DocumentType
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.data is None:
            self.data = {}
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "document_type": self.document_type.value,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata
        }


class BaseParser(ABC):
    """Abstract base class for all parsers."""
    
    def __init__(self, parser_version: str = "1.0.0"):
        self.parser_version = parser_version
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def can_parse(self, file_path: Path) -> bool:
        """
        Check if this parser can handle the given file.
        
        Args:
            file_path: Path to file to check
            
        Returns:
            True if this parser can handle the file
        """
        pass
    
    @abstractmethod
    def parse(self, file_path: Path, s3_key: Optional[str] = None) -> ParseResult:
        """
        Parse the file and return structured data.
        
        Args:
            file_path: Path to file to parse
            s3_key: Optional S3 key of source file (for metadata extraction)
            
        Returns:
            ParseResult with structured data or error
        """
        pass
    
    @abstractmethod
    def get_document_type(self) -> DocumentType:
        """
        Return the document type this parser handles.
        
        Returns:
            DocumentType enum value
        """
        pass
    
    def validate_output(self, data: Dict[str, Any]) -> bool:
        """
        Validate the parsed data against expected schema.
        
        Override in subclasses for specific validation.
        
        Args:
            data: Parsed data to validate
            
        Returns:
            True if valid
        """
        return True

