"""
Text processing and normalization for embeddings.
"""

import re
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    logging.warning("[WARN] beautifulsoup4 not available, skipping HTML cleanup")

try:
    import spacy
    HAS_SPACY = True
except ImportError:
    HAS_SPACY = False
    logging.warning("[WARN] spacy not available, skipping advanced NLP")

try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False
    logging.warning("[WARN] langchain not available, using simple chunking")

logger = logging.getLogger(__name__)


class TextProcessor:
    """
    Process and normalize text for embeddings.
    
    Features:
    - HTML cleanup (BeautifulSoup)
    - Text normalization (lowercase, whitespace, special chars)
    - Optional spaCy NLP (lemmatization, stop words)
    - Document chunking (RecursiveCharacterTextSplitter or fallback)
    """
    
    def __init__(
        self,
        use_spacy: bool = False,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        normalize_text: bool = True,
        use_contextual_enrichment: bool = False,
        knowledge_db=None
    ):
        """
        Initialize text processor.
        
        Args:
            use_spacy: Whether to use spaCy for advanced NLP (requires model)
            chunk_size: Target chunk size in tokens for splitting
            chunk_overlap: Overlap between chunks
            normalize_text: Whether to normalize text (lowercase, etc.)
            use_contextual_enrichment: Whether to add domain context to chunks
            knowledge_db: Optional CompanyKnowledgeDB instance for rich company context
        """
        self.use_spacy = use_spacy and HAS_SPACY
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.normalize_text = normalize_text
        self.use_contextual_enrichment = use_contextual_enrichment
        self.knowledge_db = knowledge_db
        
        # Initialize contextual enricher if requested
        self.enricher = None
        if self.use_contextual_enrichment:
            try:
                from ..knowledge import ContextualEnricher
                self.enricher = ContextualEnricher(knowledge_db=self.knowledge_db)
                logger.info("[INFO] Contextual enrichment enabled (DB: enabled)" if self.knowledge_db else "[INFO] Contextual enrichment enabled")
            except ImportError:
                logger.warning("[WARN] ContextualEnricher not available, disabling enrichment")
                self.use_contextual_enrichment = False
        
        # Initialize spaCy if requested
        self.nlp = None
        if self.use_spacy:
            try:
                self.nlp = spacy.load("en_core_web_sm")
                logger.info("[INFO] Loaded spaCy model: en_core_web_sm")
            except OSError:
                logger.warning("[WARN] spaCy model not found, falling back to basic processing")
                self.use_spacy = False
                self.nlp = None
        
        # Initialize chunker
        if HAS_LANGCHAIN:
            self.chunker = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                length_function=len,
                separators=["\n\n", "\n", ". ", " ", ""]
            )
            logger.info("[INFO] Using RecursiveCharacterTextSplitter for chunking")
        else:
            self.chunker = None
            logger.info("[INFO] Using simple chunking (langchain not available)")
    
    def clean_html(self, text: str) -> str:
        """
        Remove HTML tags and extract text.
        
        Args:
            text: HTML text
            
        Returns:
            Cleaned plain text
        """
        if not HAS_BS4:
            logger.warning("[WARN] BeautifulSoup not available, skipping HTML cleanup")
            return text
        
        try:
            soup = BeautifulSoup(text, "html.parser")
            return soup.get_text(separator=" ", strip=True)
        except Exception as e:
            logger.warning(f"[WARN] HTML cleanup failed: {e}")
            return text
    
    def normalize(self, text: str) -> str:
        """
        Normalize text: lowercase, remove extra whitespace, clean special chars.
        
        Args:
            text: Raw text
            
        Returns:
            Normalized text
        """
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        # Optionally lowercase
        if self.normalize_text:
            text = text.lower()
        
        return text
    
    def clean_with_spacy(self, text: str) -> str:
        """
        Advanced NLP cleaning with spaCy: lemmatization, stop word removal.
        
        Args:
            text: Input text
            
        Returns:
            Cleaned text
        """
        if not self.use_spacy or not self.nlp:
            return text
        
        try:
            doc = self.nlp(text)
            tokens = []
            for token in doc:
                if not token.is_stop and not token.is_punct:
                    tokens.append(token.lemma_)
            return " ".join(tokens)
        except Exception as e:
            logger.warning(f"[WARN] spaCy processing failed: {e}")
            return text
    
    def chunk_text(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Split text into chunks for embedding.
        
        Args:
            text: Text to chunk
            metadata: Optional metadata to attach to each chunk
            
        Returns:
            List of chunks with metadata
        """
        if self.chunker:
            # Use langchain's advanced chunking
            chunks = self.chunker.split_text(text)
        else:
            # Simple chunking fallback
            chunks = self._simple_chunk(text)
        
        # Add metadata to each chunk
        result = []
        for i, chunk in enumerate(chunks):
            chunk_data = {
                "text": chunk,
                "chunk_index": i,
                "total_chunks": len(chunks)
            }
            
            # Add provided metadata
            if metadata:
                chunk_data.update(metadata)
            
            result.append(chunk_data)
        
        return result
    
    def _simple_chunk(self, text: str) -> List[str]:
        """
        Simple chunking fallback (sentence-based).
        
        Args:
            text: Text to chunk
            
        Returns:
            List of text chunks
        """
        # Split by sentences (., !, ?)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        chunks = []
        current_chunk = []
        current_length = 0
        
        for sentence in sentences:
            sent_length = len(sentence.split())
            
            # If adding this sentence would exceed chunk size, save current chunk
            if current_length + sent_length > self.chunk_size and current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                current_length = 0
            
            current_chunk.append(sentence)
            current_length += sent_length
        
        # Add remaining sentences
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        return chunks
    
    def process_document(self, parsed_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Process a parsed document into embeddable chunks.
        
        Args:
            parsed_data: Parsed JSON from parser
            
        Returns:
            List of processed chunks ready for embedding
        """
        chunks = []
        
        # Extract document type
        doc_type = parsed_data.get("document_type", "unknown")
        source_file = parsed_data.get("source_file", "unknown")
        
        # Build base metadata
        base_metadata = {
            "document_type": doc_type,
            "source_file": source_file
        }
        
        # Add document-specific metadata
        if doc_type == "html_filing":
            base_metadata.update({
                "ticker": parsed_data.get("ticker"),
                "filing_type": parsed_data.get("filing_type"),
                "filing_date": parsed_data.get("filing_date")
            })
        elif doc_type == "html_legislation":
            base_metadata.update({
                "title": parsed_data.get("title"),
                "jurisdiction": parsed_data.get("jurisdiction"),
                "language": parsed_data.get("language")
            })
        elif doc_type == "csv_financial":
            base_metadata.update({
                "snapshot_date": parsed_data.get("snapshot_date"),
                "data_type": parsed_data.get("data_type")
            })
        
        # Process sections (for filings and legislation)
        if "sections" in parsed_data:
            sections = parsed_data["sections"]
            
            for section in sections:
                section_title = section.get("title", "Unknown")
                section_text = section.get("text", "")
                
                # Clean and process text
                cleaned_text = self.clean_html(section_text)
                
                # Apply contextual enrichment BEFORE normalization (preserves context structure)
                if self.use_contextual_enrichment and self.enricher:
                    chunk_dict = {"text": cleaned_text, "section_title": section_title}
                    if doc_type == "html_filing":
                        cleaned_text = self.enricher.enrich_filing_chunk(chunk_dict, parsed_data)
                    elif doc_type == "html_legislation":
                        cleaned_text = self.enricher.enrich_regulation_text(cleaned_text, parsed_data)
                
                # Normalize AFTER enrichment
                cleaned_text = self.normalize(cleaned_text)
                
                if self.use_spacy:
                    cleaned_text = self.clean_with_spacy(cleaned_text)
                
                # Chunk the text
                section_chunks = self.chunk_text(
                    cleaned_text,
                    metadata={**base_metadata, "section_title": section_title}
                )
                chunks.extend(section_chunks)
        
        # Handle CSV financial data
        elif doc_type == "csv_financial" and "companies" in parsed_data:
            companies = parsed_data["companies"]
            
            for company in companies:
                ticker = company.get("ticker", "")
                company_name = company.get("company", "")
                metrics = company.get("metrics", {})
                
                # Build text representation
                text_parts = [f"Company: {company_name}"]
                text_parts.append(f"Ticker: {ticker}")
                
                for metric_name, metric_value in metrics.items():
                    text_parts.append(f"{metric_name}: {metric_value}")
                
                company_text = " ".join(text_parts)
                
                # Create a single chunk per company
                company_metadata = {
                    **base_metadata,
                    "ticker": ticker,
                    "company_name": company_name
                }
                
                chunks.append({
                    "text": company_text,
                    "chunk_index": 0,
                    "total_chunks": 1,
                    **company_metadata
                })
        
        logger.info(f"[OK] Processed {len(chunks)} chunks from {source_file}")
        
        return chunks

