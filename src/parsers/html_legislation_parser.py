"""
HTML/XML Legislation Parser for regulatory documents.
"""

from pathlib import Path
from typing import Dict, Any, List
import logging
import time
import re
from datetime import datetime
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

from .base import BaseParser, ParseResult, DocumentType

logger = logging.getLogger(__name__)


class HTMLLegislationParser(BaseParser):
    """Parser for legislation documents (HTML/XML)."""
    
    def __init__(self, parser_version: str = "1.0.0"):
        super().__init__(parser_version)
    
    def can_parse(self, file_path: Path) -> bool:
        """Check if file is legislation HTML/XML in directives folder."""
        suffix = file_path.suffix.lower()
        if suffix not in ['.html', '.xml']:
            return False
        
        # Check if in directives folder or has legislation keywords
        is_in_directives = 'directive' in str(file_path.parent).lower()
        
        # Check for legislation keywords (ASCII and non-ASCII)
        filename_lower = file_path.name.lower()
        has_leg_keywords = any(kw in filename_lower for kw in 
                              ['directive', 'regulation', 'law', 'act', 'bill', 'h.r.'])
        
        # Check for Chinese law keywords (中华人民共和国 = People's Republic of China, 法 = law)
        has_chinese_law = '中华人民共和国' in file_path.name or '法' in file_path.name
        
        return is_in_directives or has_leg_keywords or has_chinese_law
    
    def get_document_type(self) -> DocumentType:
        """Return legislation document type."""
        return DocumentType.HTML_LEGISLATION
    
    def parse(self, file_path: Path) -> ParseResult:
        """
        Parse legislation document.
        
        Args:
            file_path: Path to legislation file
            
        Returns:
            ParseResult with parsed data
        """
        try:
            logger.info(f"[INFO] Parsing legislation: {file_path.name}")
            start_time = time.time()
            
            # Read file
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Detect language
            language = self._detect_language(content)
            
            # Parse based on format
            if file_path.suffix.lower() == '.xml':
                data = self._parse_xml(content, file_path)
            else:
                data = self._parse_html(content, file_path)
            
            # Add common metadata
            data["language"] = language
            data["metadata"]["parse_duration_seconds"] = time.time() - start_time
            
            duration = time.time() - start_time
            logger.info(f"[OK] Parsed legislation in {duration:.2f}s")
            
            return ParseResult(
                success=True,
                document_type=DocumentType.HTML_LEGISLATION,
                data=data,
                metadata={"duration": duration}
            )
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to parse legislation: {e}", exc_info=True)
            return ParseResult(
                success=False,
                document_type=DocumentType.HTML_LEGISLATION,
                error=str(e)
            )
    
    def _parse_html(self, content: str, file_path: Path) -> Dict[str, Any]:
        """
        Parse HTML legislation.
        
        Args:
            content: HTML content
            file_path: Path to file
            
        Returns:
            Parsed data dictionary
        """
        soup = BeautifulSoup(content, 'lxml')
        
        # Extract title
        title = self._extract_title(soup, file_path.name)
        
        # Extract sections
        sections = self._extract_sections(soup)
        
        # Extract official identifier
        identifier_info = self._extract_official_identifier(content)
        
        # Infer jurisdiction
        jurisdiction_info = self._infer_jurisdiction(content, file_path.name, soup)
        
        return {
            "document_type": "html_legislation",
            "source_file": file_path.name,
            "title": title,
            "identifier": identifier_info.get('identifier', ''),
            "jurisdiction": jurisdiction_info.get('jurisdiction', 'UNKNOWN'),
            "type": identifier_info.get('type', 'legislation'),
            "enacted_date": "",
            "effective_date": "",
            "summary": self._extract_summary(soup),
            "keywords": [],
            "affected_sectors": [],
            "affected_countries": [],
            "sections": sections,
            "metadata": {
                "parsed_at": datetime.now().isoformat(),
                "parser_version": self.parser_version,
                "total_word_count": sum(s.get('word_count', 0) for s in sections),
                "source_url": "",
                "jurisdiction_confidence": jurisdiction_info.get('confidence', 0.0),
                "jurisdiction_method": jurisdiction_info.get('method', 'unknown'),
            }
        }
    
    def _parse_xml(self, content: str, file_path: Path) -> Dict[str, Any]:
        """
        Parse XML legislation (e.g., US bills).
        
        Args:
            content: XML content
            file_path: Path to file
            
        Returns:
            Parsed data dictionary
        """
        try:
            # Strip leading/trailing whitespace and try to parse
            content_stripped = content.strip()
            root = ET.fromstring(content_stripped)
            
            # Extract title from XML
            title = ""
            for elem in root.iter():
                if 'title' in elem.tag.lower() or 'official-title' in elem.tag.lower():
                    if elem.text:
                        title = elem.text.strip()
                        break
            
            if not title:
                title = file_path.stem
            
            # Extract all text sections
            sections = []
            for i, elem in enumerate(root.iter()):
                if elem.text and len(elem.text.strip()) > 100:
                    text = elem.text.strip()
                    sections.append({
                        "section_id": f"xml_section_{i}",
                        "title": elem.tag,
                        "text": text[:5000],
                        "articles": [],
                        "word_count": len(text.split())
                    })
            
            return {
                "document_type": "xml_legislation",
                "source_file": file_path.name,
                "title": title,
                "identifier": self._extract_official_identifier(content).get('identifier', ''),
                "jurisdiction": "US",  # XML format typically US
                "type": "bill",
                "enacted_date": "",
                "effective_date": "",
                "summary": "",
                "keywords": [],
                "affected_sectors": [],
                "affected_countries": [],
                "sections": sections[:10],  # Limit sections
                "metadata": {
                    "parsed_at": datetime.now().isoformat(),
                    "parser_version": self.parser_version,
                    "total_word_count": sum(s.get('word_count', 0) for s in sections),
                }
            }
            
        except ET.ParseError as e:
            logger.warning(f"[WARN] XML parse error: {e}, falling back to text extraction")
            # Fallback to text extraction
            return self._parse_html(content, file_path)
    
    def _extract_title(self, soup: BeautifulSoup, filename: str) -> str:
        """Extract document title."""
        # Try HTML title tag
        title_tag = soup.find('title')
        if title_tag and title_tag.text:
            return title_tag.text.strip()[:200]
        
        # Try h1 tags
        h1 = soup.find('h1')
        if h1 and h1.text:
            return h1.text.strip()[:200]
        
        # Try meta tags
        meta_title = soup.find('meta', {'name': 'title'})
        if meta_title:
            return meta_title.get('content', '')[:200]
        
        # Fallback to filename
        return filename.replace('.html', '').replace('.xml', '')
    
    def _extract_sections(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract main sections from document."""
        sections = []
        
        # Look for common section patterns
        section_tags = soup.find_all(['section', 'article', 'div'], limit=20)
        
        for i, tag in enumerate(section_tags):
            text = tag.get_text(strip=True)
            if len(text) > 200:  # Only substantial sections
                # Try to find section title
                title_elem = tag.find(['h1', 'h2', 'h3', 'h4', 'strong', 'b'])
                title = title_elem.get_text(strip=True) if title_elem else f"Section {i+1}"
                
                sections.append({
                    "section_id": f"section_{i}",
                    "title": title[:100],
                    "text": text[:5000],  # Limit text length
                    "articles": [],
                    "word_count": len(text.split())
                })
        
        # If no sections found, extract main text
        if not sections:
            body = soup.find('body')
            if body:
                text = body.get_text(strip=True)
                sections.append({
                    "section_id": "main",
                    "title": "Main Text",
                    "text": text[:5000],
                    "articles": [],
                    "word_count": len(text.split())
                })
        
        return sections[:10]  # Limit to 10 sections for MVP
    
    def _extract_summary(self, soup: BeautifulSoup) -> str:
        """Extract document summary if available."""
        # Look for summary/abstract (using string parameter instead of deprecated text)
        for keyword in ['summary', 'abstract', 'overview']:
            elem = soup.find(string=re.compile(keyword, re.IGNORECASE))
            if elem and elem.parent:
                text = elem.parent.get_text(strip=True)
                if len(text) > 100:
                    return text[:500]
        return ""
    
    def _extract_official_identifier(self, content: str) -> Dict[str, Any]:
        """
        Extract official document identifier.
        
        Returns:
            Dict with identifier and type
        """
        patterns = {
            'EU': [
                (r'REGULATION\s*\(EU\)\s*(\d{4}/\d+)', 'regulation'),
                (r'DIRECTIVE\s*\(EU\)\s*(\d{4}/\d+)', 'directive'),
            ],
            'US': [
                (r'(H\.R\.\s*\d+)', 'bill'),
                (r'(S\.\s*\d+)', 'bill'),
                (r'Public\s+Law\s+(\d+-\d+)', 'law'),
            ],
            'CN': [
                (r'(中华人民共和国[\u4e00-\u9fa5]+法)', 'law'),
            ],
            'JP': [
                (r'(法律第\d+号)', 'law'),
            ],
        }
        
        for jurisdiction, pattern_list in patterns.items():
            for pattern, doc_type in pattern_list:
                match = re.search(pattern, content[:5000])
                if match:
                    return {
                        'identifier': match.group(1),
                        'type': doc_type,
                        'jurisdiction': jurisdiction
                    }
        
        return {'identifier': '', 'type': 'legislation', 'jurisdiction': 'UNKNOWN'}
    
    def _infer_jurisdiction(
        self, 
        content: str, 
        filename: str, 
        soup: BeautifulSoup
    ) -> Dict[str, Any]:
        """
        Infer jurisdiction using official identifiers and patterns.
        
        Returns:
            Dict with jurisdiction, confidence, method
        """
        # Strategy 1: Official identifier
        id_info = self._extract_official_identifier(content)
        if id_info['jurisdiction'] != 'UNKNOWN':
            return {
                'jurisdiction': id_info['jurisdiction'],
                'confidence': 0.95,
                'method': 'official_identifier'
            }
        
        # Strategy 2: Explicit statements
        intro = content[:3000]
        jurisdiction_phrases = {
            'EU': ['European Union', 'European Parliament', 'Member States'],
            'US': ['United States', 'Congress', 'enacted by'],
            'CN': ['中华人民共和国', '全国人民代表大会'],
            'JP': ['日本国'],
        }
        
        for jur, phrases in jurisdiction_phrases.items():
            if any(phrase in intro for phrase in phrases):
                return {
                    'jurisdiction': jur,
                    'confidence': 0.80,
                    'method': 'text_analysis'
                }
        
        # Strategy 3: Filename
        if 'REGULATION' in filename or 'DIRECTIVE' in filename:
            return {'jurisdiction': 'EU', 'confidence': 0.60, 'method': 'filename'}
        elif 'H.R.' in filename:
            return {'jurisdiction': 'US', 'confidence': 0.60, 'method': 'filename'}
        elif '中华人民共和国' in filename:
            return {'jurisdiction': 'CN', 'confidence': 0.60, 'method': 'filename'}
        elif '人工知能' in filename or '法律' in filename:
            return {'jurisdiction': 'JP', 'confidence': 0.60, 'method': 'filename'}
        
        return {'jurisdiction': 'UNKNOWN', 'confidence': 0.0, 'method': 'none'}
    
    def _detect_language(self, content: str) -> str:
        """
        Detect document language using langdetect.
        
        Args:
            content: Document text
            
        Returns:
            ISO language code
        """
        try:
            import langdetect
            # Detect from a sample
            sample = content[:1000].strip()
            if not sample:
                return 'en'
            detected = langdetect.detect(sample)
            # Normalize Chinese variants
            if detected.startswith('zh'):
                return 'zh'
            return detected
        except Exception as e:
            logger.warning(f"[WARN] Language detection failed: {e}")
            return 'en'

