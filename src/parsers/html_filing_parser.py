"""
HTML Filing Parser for SEC 10-K and 10-Q documents.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import logging
import time
import re
from datetime import datetime
from bs4 import BeautifulSoup

from .base import BaseParser, ParseResult, DocumentType

logger = logging.getLogger(__name__)


class HTMLFilingParser(BaseParser):
    """Parser for SEC 10-K/10-Q filings in HTML format."""
    
    def __init__(self, parser_version: str = "1.0.0"):
        super().__init__(parser_version)
        
        # Section patterns to identify key sections
        self.section_patterns = {
            "item_1": [
                r"item\s*1[^a\d].*?business",
                r"^business$",
            ],
            "item_1a": [
                r"item\s*1a.*?risk\s*factors",
                r"^risk\s*factors$",
            ],
            "item_7": [
                r"item\s*7[^a\d].*?management.*?discussion",
                r"management.*?discussion.*?analysis",
                r"^md&a$",
            ],
            "item_8": [
                r"item\s*8.*?financial\s*statements",
                r"^financial\s*statements$",
            ]
        }
    
    def can_parse(self, file_path: Path) -> bool:
        """Check if file is an HTML filing."""
        if file_path.suffix.lower() != '.html':
            return False
        # Check if filename matches pattern: YYYY-MM-DD-10k-TICKER.html or YYYY-MM-DD-10q-TICKER.html
        return bool(re.match(r'\d{4}-\d{2}-\d{2}-10[kq]-\w+\.html', file_path.name, re.IGNORECASE))
    
    def get_document_type(self) -> DocumentType:
        return DocumentType.HTML_FILING
    
    def parse(self, file_path: Path) -> ParseResult:
        """
        Parse SEC filing HTML.
        
        Args:
            file_path: Path to HTML filing
            
        Returns:
            ParseResult with parsed data
        """
        try:
            logger.info(f"[INFO] Parsing filing: {file_path.name}")
            start_time = time.time()
            
            # Extract metadata from filename
            ticker = self._extract_ticker_from_filename(file_path.name)
            filing_date = self._extract_date_from_filename(file_path.name)
            filing_type = self._extract_filing_type_from_filename(file_path.name)
            
            # Read HTML
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                html_content = f.read()
            
            # Parse HTML
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Try sec-parser first, fallback to BeautifulSoup
            try:
                sections = self._parse_with_sec_parser(html_content)
            except Exception as e:
                logger.warning(f"[WARN] sec-parser failed: {e}, using fallback")
                sections = self._fallback_parse(soup)
            
            # Extract company name and CIK
            company_name = self._extract_company_name(soup)
            cik = self._extract_cik(soup)
            
            # Build output
            total_words = sum(s.get('word_count', 0) for s in sections)
            
            data = {
                "document_type": "html_filing",
                "source_file": file_path.name,
                "ticker": ticker,
                "company": company_name,
                "filing_type": filing_type,
                "filing_date": filing_date,
                "fiscal_year": int(filing_date.split('-')[0]) if filing_date else 0,
                "cik": cik,
                "sections": sections,
                "entities": [],  # Will be populated by feature extraction module
                "metadata": {
                    "parsed_at": datetime.now().isoformat(),
                    "parser_version": self.parser_version,
                    "parse_duration_seconds": time.time() - start_time,
                    "total_word_count": total_words,
                    "total_sections": len(sections),
                }
            }
            
            duration = time.time() - start_time
            logger.info(f"[OK] Parsed {len(sections)} sections in {duration:.2f}s")
            
            return ParseResult(
                success=True,
                document_type=DocumentType.HTML_FILING,
                data=data,
                metadata={"duration": duration}
            )
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to parse filing: {e}", exc_info=True)
            return ParseResult(
                success=False,
                document_type=DocumentType.HTML_FILING,
                error=str(e)
            )
    
    def _parse_with_sec_parser(self, html_content: str) -> List[Dict[str, Any]]:
        """
        Parse using sec-parser library.
        
        Args:
            html_content: HTML content
            
        Returns:
            List of parsed sections
        """
        # Try to use sec-parser if available
        try:
            from sec_parser import parse_filing
            parsed = parse_filing(html_content)
            # Convert to our format (implementation depends on sec-parser API)
            return self._convert_sec_parser_output(parsed)
        except ImportError:
            raise Exception("sec-parser not available")
        except Exception as e:
            raise Exception(f"sec-parser failed: {e}")
    
    def _convert_sec_parser_output(self, parsed_data: Any) -> List[Dict[str, Any]]:
        """Convert sec-parser output to our format."""
        # This depends on sec-parser's actual API
        # For now, raise to use fallback
        raise Exception("sec-parser conversion not implemented")
    
    def _fallback_parse(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        Fallback HTML parsing with BeautifulSoup.
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            List of parsed sections
        """
        sections = []
        
        # Get all text for full-text search
        full_text = soup.get_text()
        
        # Try to find sections by patterns
        for section_id, patterns in self.section_patterns.items():
            section_data = self._find_section_by_patterns(soup, full_text, section_id, patterns)
            if section_data:
                sections.append(section_data)
        
        # If no sections found, extract all major text blocks
        if not sections:
            sections = self._extract_text_blocks(soup)
        
        return sections
    
    def _find_section_by_patterns(
        self, 
        soup: BeautifulSoup, 
        full_text: str,
        section_id: str, 
        patterns: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Find a section by matching patterns.
        
        Args:
            soup: BeautifulSoup object
            full_text: Full text content
            section_id: Section identifier
            patterns: List of regex patterns to match
            
        Returns:
            Section data dict or None
        """
        for pattern in patterns:
            # Search for pattern in text
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                # Found potential section header
                start_pos = match.start()
                
                # Extract text after this position (next 50000 chars)
                section_text = full_text[start_pos:start_pos + 50000]
                
                # Clean and truncate
                section_text = self._clean_text(section_text)
                
                # Get title from match
                title = self._extract_title_from_match(match.group(0))
                
                return {
                    "section_id": section_id,
                    "title": title,
                    "text": section_text,  # No truncation limit
                    "subsections": [],
                    "tables": [],
                    "word_count": len(section_text.split()),
                    "char_count": len(section_text)
                }
        
        return None
    
    def _extract_text_blocks(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        Extract major text blocks when section detection fails.
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            List of text block sections
        """
        sections = []
        
        # Find all major text containers
        for i, elem in enumerate(soup.find_all(['div', 'section', 'article'], limit=20)):
            text = elem.get_text(strip=True)
            if len(text) > 500:  # Only include substantial blocks
                sections.append({
                    "section_id": f"block_{i}",
                    "title": f"Text Block {i+1}",
                    "text": self._clean_text(text),  # No truncation limit
                    "subsections": [],
                    "tables": [],
                    "word_count": len(text.split()),
                    "char_count": len(text)
                })
        
        return sections
    
    @staticmethod
    def _extract_ticker_from_filename(filename: str) -> str:
        """Extract ticker from filename like '2024-11-01-10k-AAPL.html'."""
        match = re.search(r'-([A-Z]+)\.html$', filename, re.IGNORECASE)
        return match.group(1).upper() if match else ""
    
    @staticmethod
    def _extract_date_from_filename(filename: str) -> str:
        """Extract date from filename."""
        match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
        return match.group(1) if match else ""
    
    @staticmethod
    def _extract_filing_type_from_filename(filename: str) -> str:
        """Extract filing type (10-K or 10-Q)."""
        match = re.search(r'10[kq]', filename, re.IGNORECASE)
        return match.group(0).upper() if match else "10-K"
    
    def _extract_company_name(self, soup: BeautifulSoup) -> str:
        """Extract company name from HTML."""
        # Try various common patterns
        patterns = [
            ('meta', {'name': 'company'}),
            ('span', {'class': re.compile(r'company', re.I)}),
            ('div', {'class': re.compile(r'company', re.I)}),
        ]
        
        for tag, attrs in patterns:
            elem = soup.find(tag, attrs)
            if elem:
                text = elem.get('content') if tag == 'meta' else elem.get_text()
                if text:
                    return self._clean_text(text)[:100]
        
        return "Unknown Company"
    
    def _extract_cik(self, soup: BeautifulSoup) -> str:
        """Extract CIK (Central Index Key) from HTML."""
        # Look for CIK in text
        text = soup.get_text()
        match = re.search(r'CIK[:\s]+(\d{10})', text, re.IGNORECASE)
        if match:
            return match.group(1)
        
        # Look for CIK in meta tags
        cik_meta = soup.find('meta', {'name': re.compile(r'cik', re.I)})
        if cik_meta:
            return cik_meta.get('content', '')
        
        return ""
    
    @staticmethod
    def _clean_text(text: str) -> str:
        """Clean and normalize text."""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s\.\,\;\:\!\?\-\(\)]', '', text)
        return text.strip()
    
    @staticmethod
    def _extract_title_from_match(matched_text: str) -> str:
        """Extract clean title from matched text."""
        # Clean up the matched section header
        title = re.sub(r'item\s*\d+[a-z]?[\.\:]?\s*', '', matched_text, flags=re.IGNORECASE)
        title = title.strip()
        # Capitalize properly
        return title.title() if title else "Section"

