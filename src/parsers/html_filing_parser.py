"""
HTML Filing Parser for SEC 10-K and 10-Q documents.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import logging
import time
import re
from datetime import datetime

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
    
    def parse(self, file_path: Path, s3_key: Optional[str] = None) -> ParseResult:
        """
        Parse SEC filing HTML.
        
        Args:
            file_path: Path to HTML filing
            s3_key: Optional S3 key of source file (preferred for metadata)
            
        Returns:
            ParseResult with parsed data
        """
        try:
            logger.info(f"[INFO] Parsing filing: {file_path.name}")
            start_time = time.time()
            
            # Extract metadata from S3 key (preferred) or filename
            # S3 keys have format: input/filings/{ticker}/{date}-{filing_type}-{ticker}{ext}
            source_filename = Path(s3_key).name if s3_key else file_path.name
            metadata_source = s3_key if s3_key else file_path.name
            
            ticker = self._extract_ticker_from_filename(metadata_source)
            filing_date = self._extract_date_from_filename(metadata_source)
            filing_type = self._extract_filing_type_from_filename(metadata_source)
            
            # Read raw text (can be HTML or plain text)
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                raw_content = f.read()
            
            # Extract documents using <DOCUMENT> tags (SEC filings use this structure)
            documents = self._extract_documents(raw_content)
            
            # Use the main document (usually the first or largest)
            main_document = self._select_main_document(documents)
            
            # Parse using edgartools Document class (robust parsing for SEC filings)
            try:
                from edgar.files.html import Document
                from edgar.files.html import HeadingNode, TextBlockNode, TableNode
            except ImportError:
                raise ImportError("edgartools not available. Install with: pip install edgartools")
            
            logger.info(f"[INFO] Using edgartools Document parser for {filing_type} filing")
            
            # Extract section positions from original HTML first (before parsing removes headings)
            section_positions = self._find_section_positions_in_html(main_document, filing_type)
            
            if not section_positions:
                # Fallback: try parsing with edgartools and search in parsed text
                logger.warning("[WARN] No sections found in HTML, trying edgartools parser")
                try:
                    document = Document.parse(main_document)
                    sections = self._extract_sections_from_document(document, filing_type)
                except Exception as e:
                    logger.error(f"[ERROR] edgartools parsing failed: {e}")
                    # Final fallback: regex on cleaned text
                    plain_text = self._clean_html_tags(main_document)
                    sections = self._extract_sections_with_regex(plain_text)
            else:
                # Use edgartools to get clean text, then extract sections based on HTML positions
                sections = self._extract_sections_using_positions(main_document, section_positions, filing_type)
            
            # Extract company name and CIK using regex patterns (from raw content for better detection)
            company_name = self._extract_company_name(raw_content)
            cik = self._extract_cik(raw_content)
            
            # Build output
            total_words = sum(s.get('word_count', 0) for s in sections)
            
            # Use S3 key as source_file if available, otherwise use filename
            # Extract meaningful filename from S3 key (e.g., "2024-10-31-10-k-AAPL.html" from "input/filings/AAPL/2024-10-31-10-k-AAPL.html")
            if s3_key:
                source_file = Path(s3_key).name
            else:
                source_file = file_path.name
            
            data = {
                "document_type": "html_filing",
                "source_file": source_file,
                "source_s3_key": s3_key,  # Store S3 key for reference
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
    
    def _extract_documents(self, raw_text: str) -> List[str]:
        """
        Extract <DOCUMENT> blocks from SEC filing text.
        
        Args:
            raw_text: Raw filing text (can contain multiple <DOCUMENT> tags)
            
        Returns:
            List of document content strings
        """
        documents = re.findall(r'<DOCUMENT>(.*?)</DOCUMENT>', raw_text, re.DOTALL | re.IGNORECASE)
        
        if not documents:
            # If no DOCUMENT tags, assume the entire file is one document
            logger.debug("[DEBUG] No <DOCUMENT> tags found, treating entire file as one document")
            return [raw_text]
        
        logger.info(f"[INFO] Extracted {len(documents)} document(s) from filing")
        return documents
    
    def _select_main_document(self, documents: List[str]) -> str:
        """
        Select the main document from multiple documents.
        Prefers documents with TYPE=10-K/10-Q or the largest HTML document.
        
        Args:
            documents: List of document content strings
            
        Returns:
            Main document content string
        """
        if len(documents) == 1:
            return documents[0]
        
        # First, try to find document with TYPE=10-K or 10-Q
        for doc in documents:
            type_match = re.search(r'<TYPE>(.*?)</TYPE>', doc, re.IGNORECASE | re.DOTALL)
            if type_match:
                doc_type = type_match.group(1).strip().upper()
                if '10-K' in doc_type or '10-Q' in doc_type or '8-K' in doc_type:
                    # Extract TEXT section if available
                    text_match = re.search(r'<TEXT>(.*?)</TEXT>', doc, re.DOTALL | re.IGNORECASE)
                    if text_match:
                        logger.debug(f"[DEBUG] Selected main document by TYPE ({doc_type}, {len(text_match.group(1)):,} chars)")
                        return text_match.group(1)
        
        # Fallback: Find the largest document with TEXT/HTML content
        best_doc = None
        best_size = 0
        for doc in documents:
            # Check if it has TEXT section
            text_match = re.search(r'<TEXT>(.*?)</TEXT>', doc, re.DOTALL | re.IGNORECASE)
            if text_match:
                text_content = text_match.group(1)
                # Prefer documents with ITEM patterns
                item_count = len(re.findall(r'ITEM\s+\d+[A-Z]?', text_content, re.IGNORECASE))
                if item_count > 0 and len(text_content) > best_size:
                    best_doc = text_content
                    best_size = len(text_content)
        
        if best_doc:
            logger.debug(f"[DEBUG] Selected main document by size/ITEM count ({best_size:,} chars)")
            return best_doc
        
        # Final fallback: largest document
        main_doc = max(documents, key=len)
        logger.debug(f"[DEBUG] Selected main document by size ({len(main_doc):,} chars)")
        return main_doc
    
    def _clean_html_tags(self, text: str) -> str:
        """
        Remove HTML tags from text using regex (much faster than DOM parsing).
        
        Args:
            text: Text containing HTML tags
            
        Returns:
            Plain text with HTML tags removed
        """
        # Remove all HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)
        
        # Clean up whitespace
        text = self._clean_text(text)
        
        return text
    
    def _find_section_positions_in_html(self, html_content: str, filing_type: str) -> List[tuple]:
        """
        Find section header positions in original HTML before parsing.
        Only extracts relevant sections based on filing type.
        
        Args:
            html_content: Raw HTML content
            filing_type: Filing type (10-K, 10-Q, 8-K)
            
        Returns:
            List of (position, section_id, title, matched_text) tuples
        """
        # Define sections to extract based on filing type
        section_patterns = []
        
        filing_type_upper = filing_type.upper()
        
        if filing_type_upper == '10-K':
            # 10-K: Item 1, Item 1A, Item 3, Item 7, Item 9A
            section_patterns = [
                # Item 1A must come before Item 1
                (r'ITEM\s+1A\.?\s*[:\-&#;\s]*RISK\s+FACTORS', 'item_1a', 'Item 1A. Risk Factors'),
                # Item 1 - match "Item 1" or "Item 1." not followed by letter (to exclude 1A, 1B, 1C)
                (r'ITEM\s+1\.?\s*(?:[:\-&#;\s]|$)(?![A-Z])', 'item_1', 'Item 1. Business'),
                # Item 3 - Legal Proceedings
                (r'ITEM\s+3\.?\s*[:\-&#;\s]*(?:LEGAL|PROCEEDINGS)', 'item_3', 'Item 3. Legal Proceedings'),
                # Item 7 - Management Discussion (more flexible)
                (r'ITEM\s+7\.?\s*[:\-&#;\s]*(?:MANAGEMENT[^A]|MD&A|MD\s*&amp;\s*A|DISCUSSION)', 'item_7', 'Item 7. Management\'s Discussion and Analysis'),
                # Item 9A - Controls and Procedures (flexible - may appear in different contexts)
                (r'ITEM\s+9A\.?\s*[:\-&#;\s]', 'item_9a', 'Item 9A. Controls and Procedures'),
            ]
        elif filing_type_upper == '10-Q':
            # 10-Q: Item 1A, Item 2, Item 4
            section_patterns = [
                (r'ITEM\s+1A\.?\s*[:\-&#;\s]*RISK\s+FACTORS', 'item_1a', 'Item 1A. Risk Factors'),
                (r'ITEM\s+2\.?\s*[:\-&#;\s]*PROPERTIES', 'item_2', 'Item 2. Properties'),
                (r'ITEM\s+4\.?\s*[:\-&#;\s]*(?:MINE|CONTROLS)', 'item_4', 'Item 4. Controls and Procedures'),
            ]
        elif filing_type_upper == '8-K':
            # 8-K: Item 1.01–1.02, Item 3.01, Item 4.01–4.02, Item 5.02, Item 8.01
            section_patterns = [
                # Item 1.01 - Entry into Material Definitive Agreement
                (r'ITEM\s+1\.01\.?\s*[:\-&#;\s]*(?:ENTRY|MATERIAL|DEFINITIVE)', 'item_1.01', 'Item 1.01 Entry into Material Definitive Agreement'),
                # Item 1.02 - Termination of Material Definitive Agreement
                (r'ITEM\s+1\.02\.?\s*[:\-&#;\s]*(?:TERMINATION|MATERIAL|DEFINITIVE)', 'item_1.02', 'Item 1.02 Termination of Material Definitive Agreement'),
                # Item 3.01 - Notice of Delisting or Failure to Satisfy a Continued Listing Rule
                (r'ITEM\s+3\.01\.?\s*[:\-&#;\s]*(?:NOTICE|DELISTING|FAILURE)', 'item_3.01', 'Item 3.01 Notice of Delisting or Failure to Satisfy Listing Rule'),
                # Item 4.01 - Changes in Registrant's Certifying Accountant
                (r'ITEM\s+4\.01\.?\s*[:\-&#;\s]*(?:CHANGES|CERTIFYING|ACCOUNTANT)', 'item_4.01', 'Item 4.01 Changes in Registrant\'s Certifying Accountant'),
                # Item 4.02 - Non-Reliance on Previously Issued Financial Statements
                (r'ITEM\s+4\.02\.?\s*[:\-&#;\s]*(?:NON-?RELIANCE|PREVIOUSLY|FINANCIAL)', 'item_4.02', 'Item 4.02 Non-Reliance on Previously Issued Financial Statements'),
                # Item 5.02 - Departure of Directors or Principal Officers
                (r'ITEM\s+5\.02\.?\s*[:\-&#;\s]*(?:DEPARTURE|DIRECTORS|PRINCIPAL|OFFICERS)', 'item_5.02', 'Item 5.02 Departure of Directors or Principal Officers'),
                # Item 8.01 - Other Events
                (r'ITEM\s+8\.01\.?\s*[:\-&#;\s]*(?:OTHER\s+EVENTS?)', 'item_8.01', 'Item 8.01 Other Events'),
            ]
        else:
            # Default: extract common sections if filing type unknown
            logger.warning(f"[WARN] Unknown filing type: {filing_type}, using default patterns")
            section_patterns = [
                (r'ITEM\s+1A\.?\s*[:\-&#;\s]*RISK\s+FACTORS', 'item_1a', 'Item 1A. Risk Factors'),
                (r'ITEM\s+1\.?\s*(?:[:\-&#;\s]+(?:BUSINESS|AND\s+RESULTS\s+OF\s+OPERATIONS)|(?![A-Z]))', 'item_1', 'Item 1. Business'),
            ]
        
        # Find all section headers in HTML
        section_positions = []
        for pattern, section_id, title in section_patterns:
            matches = list(re.finditer(pattern, html_content, re.IGNORECASE | re.MULTILINE))
            for match in matches:
                section_positions.append((match.start(), section_id, title, match.group(0)))
        
        # Sort by position
        section_positions.sort(key=lambda x: x[0])
        
        # Remove duplicates - if same section_id appears multiple times, keep the first one
        seen_section_ids = set()
        unique_positions = []
        for pos, section_id, title, matched_text in section_positions:
            if section_id not in seen_section_ids:
                seen_section_ids.add(section_id)
                unique_positions.append((pos, section_id, title, matched_text))
            else:
                logger.debug(f"[DEBUG] Skipping duplicate section: {section_id} at position {pos}")
        
        logger.info(f"[INFO] Found {len(unique_positions)} section(s) for {filing_type} filing")
        return unique_positions
    
    def _extract_sections_using_positions(self, html_content: str, section_positions: List[tuple], filing_type: str) -> List[Dict[str, Any]]:
        """
        Extract sections using positions found in HTML, then use edgartools for clean text.
        
        Args:
            html_content: Raw HTML content
            section_positions: List of (position, section_id, title, matched_text) tuples
            filing_type: Filing type
            
        Returns:
            List of parsed sections
        """
        from edgar.files.html import Document
        from edgar.files.html import TextBlockNode, TableNode
        
        sections = []
        
        # Parse HTML with edgartools to get clean text structure
        document = Document.parse(html_content)
        
        # Build text with positions
        full_text = ""
        node_positions = []
        
        for i, node in enumerate(document.nodes):
            start_pos = len(full_text)
            
            if isinstance(node, TextBlockNode):
                text = node.content.strip()
                full_text += text + "\n"
            elif hasattr(node, 'content'):
                text = str(node.content).strip()
                full_text += text + "\n"
            else:
                continue
            
            end_pos = len(full_text)
            node_positions.append((i, start_pos, end_pos, node))
        
        # Extract each section based on HTML positions
        for idx, (html_pos, section_id, title, matched_text) in enumerate(section_positions):
            # Find corresponding position in cleaned text
            # We need to find where this section starts in the cleaned text
            # Approximate by finding the text after the HTML position
            
            # Extract HTML section content (rough approximation)
            if idx + 1 < len(section_positions):
                next_html_pos = section_positions[idx + 1][0]
                html_section = html_content[html_pos:next_html_pos]
            else:
                html_section = html_content[html_pos:]
            
            # Parse just this section with edgartools for clean text
            try:
                section_doc = Document.parse(html_section)
                section_text_parts = []
                section_tables = []
                
                for node in section_doc.nodes:
                    if isinstance(node, TextBlockNode):
                        text = node.content.strip()
                        if text:
                            section_text_parts.append(text)
                    elif isinstance(node, TableNode):
                        try:
                            table_data = {
                                "rows": [],
                                "row_count": 0,
                                "column_count": 0,
                                "text": node.content if hasattr(node, 'content') else ""
                            }
                            if hasattr(node, 'table') and node.table:
                                table = node.table
                                if hasattr(table, 'rows'):
                                    table_data["rows"] = [
                                        [cell.content if hasattr(cell, 'content') else str(cell) 
                                         for cell in row.cells] 
                                        for row in table.rows
                                    ] if hasattr(table.rows, '__iter__') else []
                                    table_data["row_count"] = len(table_data["rows"])
                                    table_data["column_count"] = len(table_data["rows"][0]) if table_data["rows"] else 0
                            section_tables.append(table_data)
                            section_text_parts.append(f"[TABLE {len(section_tables)}]")
                        except Exception as e:
                            logger.debug(f"[DEBUG] Failed to extract table: {e}")
                
                section_text = '\n'.join(section_text_parts)
                section_text = self._clean_text(section_text)
                
                # Remove the section header from the text (it's usually at the start)
                section_text = re.sub(r'^ITEM\s+\d+[A-Z]?\.?\s*[:\-]?\s*[^\n]*\n+', '', section_text, flags=re.IGNORECASE | re.MULTILINE)
                section_text = section_text.strip()
                
                if len(section_text) < 50:  # Too short, likely not a real section
                    continue
                
                sections.append({
                    "section_id": section_id,
                    "title": title,
                    "text": section_text,
                    "subsections": [],
                    "tables": section_tables,
                    "word_count": len(section_text.split()),
                    "char_count": len(section_text)
                })
            except Exception as e:
                logger.debug(f"[DEBUG] Failed to parse section {section_id}: {e}")
                continue
        
        if sections:
            logger.info(f"[INFO] Extracted {len(sections)} section(s) using HTML positions + edgartools")
        
        return sections
    
    def _extract_sections_from_document(self, document, filing_type: str = "10-K") -> List[Dict[str, Any]]:
        """
        Extract SEC filing sections using edgartools Document parser (robust parsing).
        
        Args:
            document: edgartools Document object
            filing_type: Filing type (10-K, 10-Q, 8-K)
            
        Returns:
            List of parsed sections
        """
        from edgar.files.html import HeadingNode, TextBlockNode, TableNode
        
        sections = []
        
        # Section patterns for SEC filings
        # Patterns handle HTML entities (&#160;), spacing variations, and optional keywords
        section_patterns = [
            # Item 1A must come before Item 1
            (r'ITEM\s+1A\.?\s*[:\-&#;\s]*RISK\s+FACTORS', 'item_1a', 'Item 1A. Risk Factors'),
            # Item 1 - business keyword is optional, can be just "Item 1" or "Item 1."
            (r'ITEM\s+1\.?\s*(?:[:\-&#;\s]+(?:BUSINESS|AND\s+RESULTS\s+OF\s+OPERATIONS)|(?![A-Z]))', 'item_1', 'Item 1. Business'),
            # Item 7A before Item 7
            (r'ITEM\s+7A\.?\s*[:\-&#;\s]*QUANTITATIVE', 'item_7a', 'Item 7A. Quantitative and Qualitative Disclosures'),
            # Item 7 - Management Discussion (more flexible)
            (r'ITEM\s+7\.?\s*[:\-&#;\s]*(?:MANAGEMENT[^A]|MD&A|MD\s*&amp;\s*A)', 'item_7', 'Item 7. Management\'s Discussion and Analysis'),
            # Item 8 - Financial Statements
            (r'ITEM\s+8\.?\s*[:\-&#;\s]*FINANCIAL', 'item_8', 'Item 8. Financial Statements'),
            # Other items
            (r'ITEM\s+2\.?\s*[:\-&#;\s]*PROPERTIES', 'item_2', 'Item 2. Properties'),
            (r'ITEM\s+3\.?\s*[:\-&#;\s]*LEGAL', 'item_3', 'Item 3. Legal Proceedings'),
            (r'ITEM\s+4\.?\s*[:\-&#;\s]*MINE', 'item_4', 'Item 4. Mine Safety Disclosures'),
            (r'ITEM\s+5\.?\s*[:\-&#;\s]*MARKET', 'item_5', 'Item 5. Market for Registrant\'s Common Equity'),
            (r'ITEM\s+6\.?\s*[:\-&#;\s]*SELECTED', 'item_6', 'Item 6. Selected Financial Data'),
        ]
        
        # Build full text content with position tracking
        full_text = ""
        node_positions = []  # Track which node corresponds to which character position
        
        for i, node in enumerate(document.nodes):
            start_pos = len(full_text)
            
            if isinstance(node, HeadingNode):
                text = node.content.strip()
                full_text += text + "\n\n"
            elif isinstance(node, TextBlockNode):
                text = node.content.strip()
                full_text += text + "\n"
            else:
                # For other node types, try to get text content
                if hasattr(node, 'content'):
                    text = str(node.content).strip()
                    full_text += text + "\n"
                continue
            
            end_pos = len(full_text)
            node_positions.append((i, start_pos, end_pos, node))
        
        # Find section headers in the full text (more robust - works even if headings are flattened)
        section_positions = []
        for pattern, section_id, title in section_patterns:
            matches = list(re.finditer(pattern, full_text, re.IGNORECASE | re.MULTILINE))
            for match in matches:
                section_positions.append((match.start(), section_id, title, match.group(0)))
        
        # Sort by position
        section_positions.sort(key=lambda x: x[0])
        
        # Find which nodes correspond to each section position
        section_headings = []
        for pos, section_id, title, matched_text in section_positions:
            # Find the node that contains this position
            for node_idx, start_pos, end_pos, node in node_positions:
                if start_pos <= pos < end_pos:
                    section_headings.append((node_idx, section_id, title, node))
                    break
        
        # Extract content for each section
        for idx, (heading_pos, section_id, title, heading_node) in enumerate(section_headings):
            # Determine end position (next section heading or end of document)
            if idx + 1 < len(section_headings):
                end_pos = section_headings[idx + 1][0]
            else:
                end_pos = len(document.nodes)
            
            # Collect content nodes between headings
            content_parts = []
            tables = []
            
            for i in range(heading_pos, end_pos):
                node = document.nodes[i]
                
                if isinstance(node, TextBlockNode):
                    text = node.content.strip()
                    if text:
                        content_parts.append(text)
                
                elif isinstance(node, TableNode):
                    # Extract table data
                    try:
                        table_data = {
                            "rows": [],
                            "row_count": 0,
                            "column_count": 0,
                            "text": node.content if hasattr(node, 'content') else ""
                        }
                        # Try to extract table structure if available
                        if hasattr(node, 'table') and node.table:
                            table = node.table
                            if hasattr(table, 'rows'):
                                table_data["rows"] = [
                                    [cell.content if hasattr(cell, 'content') else str(cell) 
                                     for cell in row.cells] 
                                    for row in table.rows
                                ] if hasattr(table.rows, '__iter__') else []
                                table_data["row_count"] = len(table_data["rows"])
                                table_data["column_count"] = len(table_data["rows"][0]) if table_data["rows"] else 0
                        tables.append(table_data)
                        # Also add table text reference
                        content_parts.append(f"[TABLE {len(tables)}]")
                    except Exception as e:
                        logger.debug(f"[DEBUG] Failed to extract table: {e}")
            
            # Combine all text content
            section_text = '\n'.join(content_parts)
            section_text = self._clean_text(section_text)
            
            # Skip very short sections (likely false positives)
            if len(section_text) < 100:
                continue
            
            sections.append({
                "section_id": section_id,
                "title": title,
                "text": section_text,
                "subsections": [],
                "tables": tables,
                "word_count": len(section_text.split()),
                "char_count": len(section_text)
            })
        
        # If no sections found, create a default section with all text content
        if not sections:
            logger.warning("[WARN] No sections found using edgartools parser, creating default section")
            all_text_parts = []
            for node in document.nodes:
                if isinstance(node, TextBlockNode):
                    text = node.content.strip()
                    if text:
                        all_text_parts.append(text)
            
            if all_text_parts:
                all_text = self._clean_text('\n'.join(all_text_parts))
                sections.append({
                    "section_id": "full_document",
                    "title": "Full Document",
                    "text": all_text,
                    "subsections": [],
                    "tables": [],
                    "word_count": len(all_text.split()),
                    "char_count": len(all_text)
                })
        
        logger.info(f"[INFO] Extracted {len(sections)} section(s) using edgartools Document parser")
        return sections
    
    def _extract_sections_with_regex(self, plain_text: str) -> List[Dict[str, Any]]:
        """
        Extract SEC filing sections using regex patterns (ITEM 1, ITEM 1A, ITEM 7, etc.).
        Much faster than DOM parsing.
        
        Args:
            plain_text: Plain text content (HTML tags already removed)
            
        Returns:
            List of parsed sections
        """
        sections = []
        
        # Section patterns for SEC filings
        # Order matters: check more specific patterns first (1A before 1, 7A before 7)
        section_patterns = [
            (r'ITEM\s+1A\.?\s*[:\-]?\s*RISK\s+FACTORS', 'item_1a', 'Item 1A. Risk Factors'),
            (r'ITEM\s+1\.?\s*[:\-]?\s*BUSINESS', 'item_1', 'Item 1. Business'),
            (r'ITEM\s+7A\.?\s*[:\-]?\s*QUANTITATIVE', 'item_7a', 'Item 7A. Quantitative and Qualitative Disclosures'),
            (r'ITEM\s+7\.?\s*[:\-]?\s*MANAGEMENT[^A]', 'item_7', 'Item 7. Management\'s Discussion and Analysis'),
            (r'ITEM\s+8\.?\s*[:\-]?\s*FINANCIAL', 'item_8', 'Item 8. Financial Statements'),
            (r'ITEM\s+2\.?\s*[:\-]?\s*PROPERTIES', 'item_2', 'Item 2. Properties'),
            (r'ITEM\s+3\.?\s*[:\-]?\s*LEGAL', 'item_3', 'Item 3. Legal Proceedings'),
            (r'ITEM\s+4\.?\s*[:\-]?\s*MINE', 'item_4', 'Item 4. Mine Safety Disclosures'),
            (r'ITEM\s+5\.?\s*[:\-]?\s*MARKET', 'item_5', 'Item 5. Market for Registrant\'s Common Equity'),
            (r'ITEM\s+6\.?\s*[:\-]?\s*SELECTED', 'item_6', 'Item 6. Selected Financial Data'),
        ]
        
        # Find all section matches
        section_matches = []
        for pattern, section_id, title in section_patterns:
            matches = list(re.finditer(pattern, plain_text, re.IGNORECASE | re.MULTILINE))
            for match in matches:
                section_matches.append((match.start(), section_id, title, match.group(0)))
        
        # Sort by position in document
        section_matches.sort(key=lambda x: x[0])
        
        # Extract section content
        for i, (start_pos, section_id, title, matched_text) in enumerate(section_matches):
            # Determine end position (start of next section or end of document)
            if i + 1 < len(section_matches):
                end_pos = section_matches[i + 1][0]
            else:
                end_pos = len(plain_text)
            
            # Extract section text
            section_text = plain_text[start_pos:end_pos]
            
            # Clean up the section text
            section_text = self._clean_text(section_text)
            
            # Skip very short sections (likely false positives)
            if len(section_text) < 100:
                continue
            
            sections.append({
                "section_id": section_id,
                "title": title,
                "text": section_text,
                "subsections": [],
                "tables": [],
                "word_count": len(section_text.split()),
                "char_count": len(section_text)
            })
        
        # If no sections found, create a default section with all text
        if not sections:
            logger.warning("[WARN] No sections found using regex, creating default section")
            if plain_text.strip():
                sections.append({
                    "section_id": "full_document",
                    "title": "Full Document",
                    "text": self._clean_text(plain_text),
                    "subsections": [],
                    "tables": [],
                    "word_count": len(plain_text.split()),
                    "char_count": len(plain_text)
                })
        
        logger.info(f"[INFO] Extracted {len(sections)} section(s) using regex patterns")
        return sections
    
    def _get_section_id_from_title(self, title: str) -> str:
        """
        Map section title to our section_id format.
        
        Args:
            title: Section title string
            
        Returns:
            Section ID string
        """
        title_lower = title.lower()
        
        # Check for Item 1A first (before Item 1, since "item 1" matches "item 1a")
        if 'item 1a' in title_lower or ('item 1' in title_lower and ('risk' in title_lower and 'factor' in title_lower)):
            return "item_1a"
        # Then check for Item 1
        elif 'item 1' in title_lower and 'business' in title_lower:
            return "item_1"
        elif 'item 7' in title_lower or 'md&a' in title_lower or ('management' in title_lower and 'discussion' in title_lower):
            return "item_7"
        elif 'item 8' in title_lower or ('financial' in title_lower and 'statement' in title_lower):
            return "item_8"
        elif 'item 2' in title_lower:
            return "item_2"
        elif 'item 3' in title_lower:
            return "item_3"
        elif 'item 4' in title_lower:
            return "item_4"
        elif 'item 5' in title_lower:
            return "item_5"
        elif 'item 6' in title_lower:
            return "item_6"
        else:
            # Generate a safe ID from title
            safe_id = re.sub(r'[^a-z0-9]+', '_', title_lower).strip('_')
            return safe_id[:50]  # Limit length
    
    @staticmethod
    def _extract_ticker_from_filename(filename: str) -> str:
        """Extract ticker from filename or S3 key like '2024-11-01-10k-AAPL.html' or 'input/filings/AAPL/2024-10-31-10-k-AAPL.html'."""
        # Extract just the filename part if it's a full path/S3 key
        name = Path(filename).name
        
        # Pattern 1: YYYY-MM-DD-{filing_type}-TICKER.ext (e.g., 2024-10-31-10-k-AAPL.html)
        # Match the ticker at the end before the extension
        match = re.search(r'-\d+[-_]?[kq]?[-_]?([A-Z]{1,5})(?:\.(?:html|txt|json))?$', name, re.IGNORECASE)
        if match:
            ticker = match.group(1).upper()
            # Filter out invalid tickers (single letters, numbers, etc.)
            if len(ticker) >= 1 and ticker.isalpha():
                return ticker
        
        # Pattern 2: Look for ticker pattern after filing type digits
        # E.g., 10-k-AAPL, 10q-MSFT
        match = re.search(r'\d+[-_]?[kq][-_]?([A-Z]{1,5})', name, re.IGNORECASE)
        if match:
            ticker = match.group(1).upper()
            if len(ticker) >= 1 and ticker.isalpha():
                return ticker
        
        # Pattern 3: Look for common ticker patterns (1-5 uppercase letters)
        match = re.search(r'\b([A-Z]{1,5})\b', name)
        if match:
            potential_ticker = match.group(1).upper()
            # Filter out common false positives
            if potential_ticker not in ['HTML', 'TXT', 'JSON', 'K', 'Q']:
                return potential_ticker
        
        return ""
    
    @staticmethod
    def _extract_date_from_filename(filename: str) -> str:
        """Extract date from filename or S3 key."""
        # Extract just the filename part if it's a full path/S3 key
        name = Path(filename).name
        # Look for YYYY-MM-DD pattern
        match = re.search(r'(\d{4}-\d{2}-\d{2})', name)
        return match.group(1) if match else ""
    
    @staticmethod
    def _extract_filing_type_from_filename(filename: str) -> str:
        """Extract filing type (10-K, 10-Q, or 8-K) from filename or S3 key."""
        # Extract just the filename part if it's a full path/S3 key
        name = Path(filename).name.lower()
        
        # Pattern 1: 8-K (check first since it's more specific)
        if '8-k' in name or '8k' in name:
            return "8-K"
        
        # Pattern 2: 10-Q (check before 10-K since both contain '10')
        if '10-q' in name or '10q' in name:
            return "10-Q"
        
        # Pattern 3: 10-K
        if '10-k' in name or '10k' in name:
            return "10-K"
        
        # Pattern 4: Try generic pattern
        match = re.search(r'(\d+[-_]?[kq])', name, re.IGNORECASE)
        if match:
            ftype = match.group(1).upper()
            # Normalize: 10k -> 10-K, 10-q -> 10-Q, 8k -> 8-K
            ftype = re.sub(r'(\d+)[-_]?([kq])', r'\1-\2', ftype)
            return ftype
        
        # Default
        return "10-K"
    
    def _extract_company_name(self, html_content: str) -> str:
        """
        Extract company name from HTML using regex patterns (no BeautifulSoup).
        
        Args:
            html_content: Raw HTML content
            
        Returns:
            Company name string
        """
        # Pattern 1: Look in <title> tag
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html_content, re.IGNORECASE | re.DOTALL)
        if title_match:
            title_text = title_match.group(1).strip()
            # Remove common suffixes like " - 10-K" or " | SEC Filing"
            title_text = re.sub(r'\s*[-|]\s*(10-[KQ]|8-K|SEC.*?Filing).*$', '', title_text, flags=re.IGNORECASE)
            if title_text and len(title_text) > 3:
                return self._clean_text(title_text)[:100]
        
        # Pattern 2: Look for meta tags with company name
        meta_patterns = [
            r'<meta[^>]*name=["\']company["\'][^>]*content=["\']([^"\']+)["\']',
            r'<meta[^>]*property=["\']og:site_name["\'][^>]*content=["\']([^"\']+)["\']',
            r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*name=["\']company["\']',
        ]
        for pattern in meta_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                company = self._clean_text(match.group(1))[:100]
                if company and len(company) > 3:
                    return company
        
        # Pattern 3: Look for common HTML structures with company name
        # SEC filings often have company name in specific divs/spans
        structure_patterns = [
            r'<div[^>]*class=["\'][^"\']*company[^"\']*["\'][^>]*>([^<]+)</div>',
            r'<span[^>]*class=["\'][^"\']*company[^"\']*["\'][^>]*>([^<]+)</span>',
            r'<h1[^>]*>([^<]{3,100})</h1>',
            r'<h2[^>]*>([^<]{3,100})</h2>',
        ]
        for pattern in structure_patterns:
            matches = re.finditer(pattern, html_content, re.IGNORECASE)
            for match in matches:
                text = self._clean_text(match.group(1))
                # Filter out common non-company-name patterns
                if (text and len(text) > 3 and 
                    not re.search(r'^(10-[KQ]|8-K|FORM|SEC|FILING|EDGAR)', text, re.IGNORECASE) and
                    not re.search(r'^\d{4}-\d{2}-\d{2}', text)):
                    return text[:100]
        
        # Pattern 4: Extract from SEC header format
        # SEC filings often have: "COMPANY CONFORMED NAME: [Company Name]"
        header_match = re.search(r'COMPANY\s+CONFORMED\s+NAME[:\s]+([^\n\r]+)', html_content, re.IGNORECASE)
        if header_match:
            company = self._clean_text(header_match.group(1))[:100]
            if company:
                return company
        
        # Pattern 5: Look for text near "FILER" or "COMPANY" in headers
        header_text_match = re.search(r'(?:FILER|COMPANY)[:\s]+([A-Z][A-Z\s&\.,\-]{2,80})', html_content, re.IGNORECASE)
        if header_text_match:
            company = self._clean_text(header_text_match.group(1))[:100]
            if company:
                return company
        
        logger.warning("[WARN] Could not extract company name from HTML")
        return "Unknown Company"
    
    def _extract_cik(self, html_content: str) -> str:
        """
        Extract CIK (Central Index Key) from HTML using regex patterns (no BeautifulSoup).
        
        Args:
            html_content: Raw HTML content
            
        Returns:
            CIK string (10 digits)
        """
        # Pattern 1: Standard CIK format in text: "CIK: 0000320193" or "CIK 0000320193"
        cik_patterns = [
            r'CIK[:\s]+(\d{10})',  # "CIK: 0000320193" or "CIK 0000320193"
            r'CENTRAL\s+INDEX\s+KEY[:\s]+(\d{10})',  # "CENTRAL INDEX KEY: 0000320193"
            r'C\.I\.K\.\s*[:\s]*(\d{10})',  # "C.I.K.: 0000320193"
        ]
        
        for pattern in cik_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                cik = match.group(1).strip()
                if len(cik) == 10 and cik.isdigit():
                    return cik
        
        # Pattern 2: CIK in meta tags
        meta_patterns = [
            r'<meta[^>]*name=["\']cik["\'][^>]*content=["\'](\d{10})["\']',
            r'<meta[^>]*content=["\'](\d{10})["\'][^>]*name=["\']cik["\']',
            r'<meta[^>]*property=["\']cik["\'][^>]*content=["\'](\d{10})["\']',
        ]
        for pattern in meta_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                cik = match.group(1).strip()
                if len(cik) == 10 and cik.isdigit():
                    return cik
        
        # Pattern 3: CIK in SEC header format
        # "CIK: 0000320193" or "CENTRAL INDEX KEY: 0000320193"
        header_match = re.search(r'(?:CIK|CENTRAL\s+INDEX\s+KEY)[:\s]+(\d{10})', html_content, re.IGNORECASE)
        if header_match:
            cik = header_match.group(1).strip()
            if len(cik) == 10 and cik.isdigit():
                return cik
        
        # Pattern 4: Look for 10-digit numbers that might be CIK (in header context)
        # SEC filings often have CIK near the top of the document
        header_section = html_content[:50000]  # Check first 50KB
        cik_candidates = re.findall(r'\b(\d{10})\b', header_section)
        for candidate in cik_candidates:
            # CIK typically starts with zeros or is in specific context
            if candidate.startswith('00') or '0000' in candidate:
                # Verify it's in a CIK-like context
                context = html_content[max(0, html_content.find(candidate) - 50):
                                      html_content.find(candidate) + 60]
                if re.search(r'cik|central.*index', context, re.IGNORECASE):
                    return candidate
        
        logger.warning("[WARN] Could not extract CIK from HTML")
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

