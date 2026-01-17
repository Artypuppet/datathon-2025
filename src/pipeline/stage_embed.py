"""
Stage 2: Generate embeddings from parsed data.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

from ..embeddings import TextProcessor, EmbeddingGenerator
from ..utils import get_s3_client, S3Client

logger = logging.getLogger(__name__)


class EmbeddingStage:
    """Embedding stage: Converts parsed JSON to embeddings."""
    
    def __init__(
        self,
        s3_client: Optional[S3Client] = None,
        model_name: str = "llmware/industry-bert-sec-v0.1",
        use_spacy: bool = False,
        normalize_text: bool = False,
        use_contextual_enrichment: bool = False,
        sentence_level_chunking: bool = False,
        context_window_sentences: int = 3,  # Extended context window
        sentences_per_chunk: int = 3  # Number of sentences per chunk
    ):
        """
        Initialize embedding stage.
        
        Args:
            s3_client: S3 client instance (optional, auto-created if None)
            model_name: Transformer model name (default: llmware/industry-bert-sec-v0.1)
            use_spacy: Whether to use spaCy NLP
            normalize_text: Whether to normalize text (lowercase, etc.)
            use_contextual_enrichment: Whether to add domain context
            sentence_level_chunking: Whether to chunk at sentence level with context (default: False for section-level)
            context_window_sentences: Number of surrounding sentences to include (default: 2)
            sentences_per_chunk: Number of sentences per chunk (default: 3)
        """
        self.s3_client = s3_client or get_s3_client()
        self.sentence_level_chunking = sentence_level_chunking
        self.context_window_sentences = context_window_sentences
        self.sentences_per_chunk = sentences_per_chunk
        
        # Load knowledge database if contextual enrichment is enabled
        knowledge_db = None
        if use_contextual_enrichment:
            try:
                from ..knowledge import CompanyKnowledgeDB
                knowledge_db = CompanyKnowledgeDB()
                logger.info("[INFO] Company knowledge database loaded")
            except Exception as e:
                logger.warning(f"[WARN] Failed to load knowledge database: {e}")
                knowledge_db = None
        
        # Initialize processors
        self.processor = TextProcessor(
            use_spacy=use_spacy,
            normalize_text=normalize_text,
            use_contextual_enrichment=use_contextual_enrichment,
            knowledge_db=knowledge_db
        )
        
        self.generator = EmbeddingGenerator(model_name=model_name)
        
        logger.info("[INFO] EmbeddingStage initialized")
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute embedding stage.
        
        Can work with either:
        - Parsed filing JSON (single filing)
        - Aggregated company JSON (multiple filings combined)
        
        Args:
            context: Pipeline context with parsed_key or aggregated_key
            
        Returns:
            Updated context with embedding_key
        """
        # Prefer aggregated data if available (for company filings)
        aggregated_key = context.get('aggregated_key')
        parsed_key = context.get('parsed_key')
        
        input_key = aggregated_key or parsed_key
        
        if not input_key:
            logger.warning("[WARN] No parsed or aggregated key in context, skipping embeddings")
            context['embedding_status'] = 'skipped'
            return context
        
        try:
            # Download JSON from S3
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)
            
            success = self.s3_client.download_file(input_key, tmp_path)
            if not success:
                raise Exception(f"Failed to download {input_key} from S3")
            
            # Load JSON
            import json
            with open(tmp_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Check if this is aggregated data (has aggregated_sections and knowledge_graph)
            is_aggregated = 'aggregated_sections' in data or 'knowledge_graph' in data
            
            if is_aggregated:
                # Process aggregated company data
                if self.sentence_level_chunking:
                    logger.info("[INFO] Processing aggregated company data with sentence-level chunking")
                    chunks = self._process_aggregated_data_sentence_level(data)
                else:
                    logger.info("[INFO] Processing aggregated company data for embeddings")
                    chunks = self._process_aggregated_data(data)
            else:
                # Process single parsed filing
                logger.info("[INFO] Processing single parsed filing for embeddings")
                chunks = self.processor.process_document(data)
            
            if not chunks:
                logger.warning("[WARN] No chunks generated, skipping embeddings")
                context['embedding_status'] = 'skipped'
                return context
            
            # Generate embeddings
            result = self.generator.embed_document(chunks)
            
            # Determine output key
            input_filename = Path(input_key).stem
            embedding_key = f"embeddings/{input_filename}_embedded.json"
            
            # Upload embeddings to S3
            self.s3_client.write_json(result, embedding_key)
            
            logger.info(f"[OK] Embeddings generated: {embedding_key}")
            
            # Update context
            context.update({
                'embedding_status': 'success',
                'embedding_key': embedding_key,
                'total_chunks': result['total_chunks'],
                'embedding_dim': result['embedding_dim']
            })
            
            # Cleanup
            if tmp_path.exists():
                tmp_path.unlink()
            
            return context
            
        except Exception as e:
            logger.error(f"[ERROR] EmbeddingStage failed: {e}", exc_info=True)
            context.update({
                'embedding_status': 'failed',
                'embedding_error': str(e)
            })
            raise
    
    def _process_aggregated_data(self, aggregated_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Process aggregated company data into chunks for embedding.
        
        Properly uses:
        - All sections from aggregated_sections
        - Entities (countries, regions, operations, risk_types)
        - Knowledge graph triples (as structured context)
        - Contextual enrichment (if enabled)
        
        Args:
            aggregated_data: Aggregated company JSON
            
        Returns:
            List of chunk dictionaries ready for embedding (with contextual enrichment)
        """
        # Get metadata
        ticker = aggregated_data.get('ticker', '').upper()
        company_name = aggregated_data.get('company_name', '')
        metadata = aggregated_data.get('metadata', {})
        sector = metadata.get('sector', '')
        industry = metadata.get('industry', '')
        
        # Extract structured information
        entities = aggregated_data.get("entities", {})
        kg_triples = aggregated_data.get("knowledge_graph", [])
        sections = aggregated_data.get("aggregated_sections", {})
        
        logger.info(f"[INFO] Processing aggregated data for {ticker}")
        logger.info(f"  Sections: {sum(len(items) for items in sections.values())}")
        logger.info(f"  Entities: {sum(len(v) if isinstance(v, list) else 0 for v in entities.values())}")
        logger.info(f"  Knowledge graph triples: {len(kg_triples)}")
        
        # Build contextual information from entities and knowledge graph
        contextual_info = self._build_contextual_info(
            ticker, company_name, entities, kg_triples, sector, industry
        )
        
        # Process each section type separately to maintain section-level context
        all_chunks = []
        
        for section_type, items in sections.items():
            for item in items:
                title = item.get('title', 'Untitled')
                text = item.get('text', '')
                filing_type = item.get('filing_type', 'N/A')
                filing_date = item.get('filing_date', 'N/A')
                
                # Build enriched text with context
                enriched_text = self._enrich_section_text(
                    text=text,
                    section_type=section_type,
                    title=title,
                    filing_type=filing_type,
                    filing_date=filing_date,
                    contextual_info=contextual_info
                )
                
                # Create chunk with metadata
                chunk = {
                    'text': enriched_text,
                    'ticker': ticker,
                    'company_name': company_name,
                    'document_type': 'aggregated_company',
                    'section_type': section_type,
                    'section_title': title,
                    'filing_type': filing_type,
                    'filing_date': filing_date,
                    'chunk_index': len(all_chunks),
                    'total_chunks': 0  # Will set after
                }
                
                all_chunks.append(chunk)
        
        # If contextual enrichment is enabled, further enrich each chunk
        if self.processor.use_contextual_enrichment and self.processor.enricher:
            logger.info("[INFO] Applying additional contextual enrichment to chunks")
            filing_metadata = {
                'ticker': ticker,
                'company': company_name,
                'sector': sector,
                'industry': industry
            }
            
            for chunk in all_chunks:
                # Use contextual enricher to add DB-based context
                enriched_text = self.processor.enricher.enrich_filing_chunk(
                    chunk, filing_metadata
                )
                chunk['text'] = enriched_text
        
        # Update total_chunks for each chunk
        for chunk in all_chunks:
            chunk['total_chunks'] = len(all_chunks)
        
        logger.info(f"[OK] Processed aggregated data into {len(all_chunks)} enriched chunks")
        return all_chunks
    
    def _build_contextual_info(
        self,
        ticker: str,
        company_name: str,
        entities: Dict[str, Any],
        kg_triples: List[Dict[str, Any]],
        sector: str,
        industry: str
    ) -> Dict[str, Any]:
        """
        Build contextual information from entities and knowledge graph.
        
        Args:
            ticker: Company ticker
            company_name: Company name
            entities: Extracted entities
            kg_triples: Knowledge graph triples
            sector: Company sector
            industry: Company industry
            
        Returns:
            Dictionary of contextual information
        """
        context = {
            'company': company_name,
            'ticker': ticker,
            'sector': sector,
            'industry': industry,
            'countries': entities.get('countries', []),
            'regions': entities.get('regions', []),
            'operations': entities.get('operations', []),
            'risk_types': entities.get('risk_types', []),
            'products': entities.get('products', []),
            'kg_relationships': {}
        }
        
        # Organize knowledge graph triples by relationship type
        for triple in kg_triples:
            relation = triple.get('relation', '')
            obj = triple.get('object', '')
            
            if relation and obj:
                if relation not in context['kg_relationships']:
                    context['kg_relationships'][relation] = []
                context['kg_relationships'][relation].append(obj)
        
        return context
    
    def _enrich_section_text(
        self,
        text: str,
        section_type: str,
        title: str,
        filing_type: str,
        filing_date: str,
        contextual_info: Dict[str, Any]
    ) -> str:
        """
        Enrich section text with contextual information from entities and knowledge graph.
        
        Args:
            text: Original section text
            section_type: Type of section (business, risk_factors, etc.)
            title: Section title
            filing_type: Type of filing (10-K, 10-Q, 8-K)
            filing_date: Filing date
            contextual_info: Contextual information dictionary
            
        Returns:
            Enriched text with context
        """
        context_parts = []
        
        # Company context
        if contextual_info.get('company'):
            context_parts.append(f"COMPANY: {contextual_info['company']} ({contextual_info.get('ticker', '')})")
        
        if contextual_info.get('sector'):
            context_parts.append(f"SECTOR: {contextual_info['sector']}")
        
        if contextual_info.get('industry'):
            context_parts.append(f"INDUSTRY: {contextual_info['industry']}")
        
        # Section context
        context_parts.append(f"SECTION: {section_type.upper()} - {title}")
        context_parts.append(f"FILING: {filing_type} dated {filing_date}")
        
        # Entity context
        if contextual_info.get('countries'):
            countries = ', '.join(str(c) for c in contextual_info['countries'])
            context_parts.append(f"COUNTRIES_MENTIONED: {countries}")
        
        if contextual_info.get('regions'):
            regions = ', '.join(str(r) for r in contextual_info['regions'])
            context_parts.append(f"REGIONS_OPERATIONS: {regions}")
        
        if contextual_info.get('operations'):
            operations = ', '.join(str(op) for op in contextual_info['operations'])
            context_parts.append(f"OPERATIONS: {operations}")
        
        if contextual_info.get('risk_types'):
            risks = ', '.join(str(r) for r in contextual_info['risk_types'])
            context_parts.append(f"RISK_TYPES: {risks}")
        
        # Knowledge graph context - show relevant relationships
        kg_rel = contextual_info.get('kg_relationships', {})
        if kg_rel:
            kg_parts = []
            
            # Show key relationships (operations, manufacturing, supply chain)
            for rel_type in ['OPERATES_IN', 'MANUFACTURES_IN', 'HAS_OPERATION', 
                           'SUPPLY_CHAIN_IN', 'HAS_RISK_TYPE']:
                if rel_type in kg_rel:
                    targets = ', '.join(str(t) for t in kg_rel[rel_type][:5])  # Limit to 5
                    if len(kg_rel[rel_type]) > 5:
                        targets += f" (+{len(kg_rel[rel_type])-5} more)"
                    kg_parts.append(f"{rel_type}: {targets}")
            
            if kg_parts:
                context_parts.append(f"KNOWLEDGE_GRAPH_RELATIONSHIPS: {'; '.join(kg_parts)}")
        
        # Build final enriched text
        if context_parts:
            context_header = "\n".join(["[CONTEXT]"] + context_parts + ["[CONTENT]"])
            enriched_text = f"{context_header}\n{text}"
        else:
            enriched_text = text
        
        return enriched_text
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences using spaCy if available, otherwise regex.
        
        Args:
            text: Text to split
            
        Returns:
            List of sentences
        """
        # Try spaCy first (more accurate)
        if self.processor.use_spacy and self.processor.nlp:
            try:
                doc = self.processor.nlp(text)
                sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]
                return sentences
            except Exception as e:
                logger.warning(f"[WARN] spaCy sentence splitting failed: {e}, using regex")
        
        # Fallback to regex-based sentence splitting
        # Pattern matches: . ! ? followed by space and capital letter or end of string
        import re
        # Split on sentence endings, but preserve them
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])|(?<=[.!?])\s*$', text)
        # Filter out empty sentences and strip whitespace
        sentences = [s.strip() for s in sentences if s.strip()]
        return sentences
    
    def _process_aggregated_data_sentence_level(self, aggregated_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Process aggregated company data into sentence-level chunks with context windows.
        
        Hybrid approach:
        - Each sentence gets its own embedding
        - But includes surrounding context (prev N + target + next N sentences)
        - Preserves all contextual information (entities, KG, etc.)
        
        Args:
            aggregated_data: Aggregated company JSON
            
        Returns:
            List of sentence-level chunk dictionaries ready for embedding
        """
        # Get metadata
        ticker = aggregated_data.get('ticker', '').upper()
        company_name = aggregated_data.get('company_name', '')
        metadata = aggregated_data.get('metadata', {})
        sector = metadata.get('sector', '')
        industry = metadata.get('industry', '')
        
        # Extract structured information
        entities = aggregated_data.get("entities", {})
        kg_triples = aggregated_data.get("knowledge_graph", [])
        sections = aggregated_data.get("aggregated_sections", {})
        
        logger.info(f"[INFO] Processing aggregated data for {ticker} at sentence level")
        logger.info(f"  Sentences per chunk: {self.sentences_per_chunk} (non-overlapping)")
        logger.info(f"  Context window: ±{self.context_window_sentences} sentences (for enrichment)")
        logger.info(f"  Sections: {sum(len(items) for items in sections.values())}")
        logger.info(f"  Entities: {sum(len(v) if isinstance(v, list) else 0 for v in entities.values())}")
        logger.info(f"  Knowledge graph triples: {len(kg_triples)}")
        
        # Build contextual information from entities and knowledge graph
        contextual_info = self._build_contextual_info(
            ticker, company_name, entities, kg_triples, sector, industry
        )
        
        # Process each section into sentence-level chunks
        all_chunks = []
        
        for section_type, items in sections.items():
            for item in items:
                title = item.get('title', 'Untitled')
                text = item.get('text', '')
                filing_type = item.get('filing_type', 'N/A')
                filing_date = item.get('filing_date', 'N/A')
                
                # Split section into sentences
                sentences = self._split_into_sentences(text)
                logger.debug(f"[DEBUG] Split '{title}' into {len(sentences)} sentences")
                
                # Create sentence-level chunks using non-overlapping windows
                # Each chunk contains N consecutive sentences with no overlap
                # This ensures each sentence appears in exactly one chunk (more exclusivity)
                # while still providing context from surrounding sentences
                
                # Step through sentences in chunks of N (non-overlapping)
                for sent_idx in range(0, len(sentences), self.sentences_per_chunk):
                    # Determine chunk boundaries: take N sentences starting from sent_idx
                    chunk_end = min(len(sentences), sent_idx + self.sentences_per_chunk)
                    chunk_sentences = sentences[sent_idx:chunk_end]
                    
                    # If this is the last chunk and it's shorter than sentences_per_chunk,
                    # we can merge it with the previous chunk to avoid very short final chunks
                    # Only merge if it's significantly shorter (< 50% of target size)
                    if len(chunk_sentences) < self.sentences_per_chunk and len(chunk_sentences) < (self.sentences_per_chunk / 2):
                        # Merge with previous chunk if possible (only if very short)
                        if len(all_chunks) > 0 and sent_idx > 0:
                            # Get previous chunk's sentences (from original_sentence)
                            prev_chunk = all_chunks[-1]
                            prev_sentences_text = prev_chunk['original_sentence']
                            # Combine with new sentences
                            combined_sentences = prev_sentences_text + ' ' + ' '.join(chunk_sentences)
                            prev_chunk['original_sentence'] = combined_sentences
                            
                            # Rebuild enriched text with combined sentences
                            # Split combined text back into sentences for enrichment
                            combined_sent_list = self._split_into_sentences(combined_sentences)
                            prev_target = combined_sent_list[0] if combined_sent_list else ''
                            
                            prev_chunk['text'] = self._enrich_sentence_with_context(
                                target_sentence=prev_target,
                                context_sentences=combined_sent_list,
                                target_idx=0,
                                section_type=section_type,
                                title=title,
                                filing_type=filing_type,
                                filing_date=filing_date,
                                contextual_info=contextual_info
                            )
                            prev_chunk['sentences_in_chunk'] = len(combined_sent_list)
                            continue  # Skip creating new chunk
                    
                    # Skip if chunk is empty
                    if len(chunk_sentences) < 1:
                        continue
                    
                    # The target sentence is the first one in the chunk
                    target_sentence = chunk_sentences[0]
                    target_idx_in_chunk = 0
                    
                    # Build enriched chunk with all sentences in the chunk
                    enriched_chunk_text = self._enrich_sentence_with_context(
                        target_sentence=target_sentence,
                        context_sentences=chunk_sentences,
                        target_idx=target_idx_in_chunk,
                        section_type=section_type,
                        title=title,
                        filing_type=filing_type,
                        filing_date=filing_date,
                        contextual_info=contextual_info
                    )
                    
                    # Store all sentences in the chunk as original sentences (space-separated)
                    original_sentences = ' '.join(chunk_sentences)
                    
                    # Create chunk with metadata
                    chunk = {
                        'text': enriched_chunk_text,
                        'ticker': ticker,
                        'company_name': company_name,
                        'document_type': 'aggregated_company',
                        'section_type': section_type,
                        'section_title': title,
                        'filing_type': filing_type,
                        'filing_date': filing_date,
                        'sentence_idx': sent_idx,  # Starting index of this chunk
                        'total_sentences_in_section': len(sentences),
                        'sentences_in_chunk': len(chunk_sentences),  # Number of sentences in this chunk
                        'original_sentence': original_sentences,  # All sentences in chunk (N sentences)
                        'chunk_index': len(all_chunks),
                        'total_chunks': 0  # Will set after
                    }
                    
                    all_chunks.append(chunk)
        
        # If contextual enrichment is enabled, further enrich each chunk
        if self.processor.use_contextual_enrichment and self.processor.enricher:
            logger.info("[INFO] Applying additional contextual enrichment to sentence chunks")
            filing_metadata = {
                'ticker': ticker,
                'company': company_name,
                'sector': sector,
                'industry': industry
            }
            
            for chunk in all_chunks:
                # Use contextual enricher to add DB-based context
                enriched_text = self.processor.enricher.enrich_filing_chunk(
                    chunk, filing_metadata
                )
                chunk['text'] = enriched_text
        
        # Update total_chunks for each chunk
        for chunk in all_chunks:
            chunk['total_chunks'] = len(all_chunks)
        
        logger.info(f"[OK] Processed aggregated data into {len(all_chunks)} sentence-level chunks")
        return all_chunks
    
    def _enrich_sentence_with_context(
        self,
        target_sentence: str,
        context_sentences: List[str],
        target_idx: int,
        section_type: str,
        title: str,
        filing_type: str,
        filing_date: str,
        contextual_info: Dict[str, Any]
    ) -> str:
        """
        Build enriched text from a chunk of sentences with contextual information.
        
        Each chunk contains multiple sentences (typically 3) for better context.
        The sentences are enriched with company metadata, entities, and knowledge graph.
        
        Args:
            target_sentence: The primary target sentence (first in chunk)
            context_sentences: List of all sentences in the chunk (typically 3)
            target_idx: Index of target sentence in context_sentences
            section_type: Type of section (business, risk_factors, etc.)
            title: Section title
            filing_type: Filing type (10-K, 10-Q, etc.)
            filing_date: Filing date
            contextual_info: Additional context (entities, KG, etc.)
            
        Returns:
            Enriched text ready for embedding (all sentences in chunk + context)
        """
        context_parts = []
        
        # Company context
        if contextual_info.get('company'):
            context_parts.append(f"COMPANY: {contextual_info['company']} ({contextual_info.get('ticker', '')})")
        
        if contextual_info.get('sector'):
            context_parts.append(f"SECTOR: {contextual_info['sector']}")
        
        if contextual_info.get('industry'):
            context_parts.append(f"INDUSTRY: {contextual_info['industry']}")
        
        # Section context
        context_parts.append(f"SECTION: {section_type.upper()} - {title}")
        context_parts.append(f"FILING: {filing_type} dated {filing_date}")
        
        # Entity context (key entities only)
        if contextual_info.get('countries'):
            countries = ', '.join(str(c) for c in contextual_info['countries'][:5])  # Limit to top 5
            context_parts.append(f"COUNTRIES: {countries}")
        
        if contextual_info.get('operations'):
            operations = ', '.join(str(op) for op in contextual_info['operations'][:3])  # Limit to top 3
            context_parts.append(f"OPERATIONS: {operations}")
        
        if contextual_info.get('risk_types'):
            risks = ', '.join(str(r) for r in contextual_info['risk_types'][:3])  # Limit to top 3
            context_parts.append(f"RISK_TYPES: {risks}")
        
        # Knowledge graph context (key relationships only)
        kg_rel = contextual_info.get('kg_relationships', {})
        if kg_rel:
            kg_parts = []
            for rel_type in ['OPERATES_IN', 'MANUFACTURES_IN', 'HAS_RISK_TYPE']:
                if rel_type in kg_rel:
                    targets = ', '.join(str(t) for t in kg_rel[rel_type][:3])
                    kg_parts.append(f"{rel_type}: {targets}")
            if kg_parts:
                context_parts.append(f"KG: {'; '.join(kg_parts)}")
        
        # Build context window text
        context_window_parts = []
        
        # Previous sentences
        if target_idx > 0:
            prev_sentences = context_sentences[:target_idx]
            if prev_sentences:
                context_window_parts.append(f"[PREV_CONTEXT] {' '.join(prev_sentences)}")
        
        # Target sentence
        context_window_parts.append(f"[TARGET_SENTENCE] {target_sentence}")
        
        # Next sentences
        if target_idx < len(context_sentences) - 1:
            next_sentences = context_sentences[target_idx + 1:]
            if next_sentences:
                context_window_parts.append(f"[NEXT_CONTEXT] {' '.join(next_sentences)}")
        
        # Build final enriched text
        context_header = "\n".join(["[CONTEXT]"] + context_parts + ["[CONTENT]"])
        context_window_text = "\n".join(context_window_parts)
        enriched_text = f"{context_header}\n{context_window_text}"
        
        return enriched_text
    
    def can_execute(self, context: Dict[str, Any]) -> bool:
        """
        Check if this stage can execute.
        
        Args:
            context: Pipeline context
            
        Returns:
            True if stage can execute
        """
        # Can execute if either parsed_key or aggregated_key is available
        parsed_key = context.get('parsed_key')
        aggregated_key = context.get('aggregated_key')
        return (
            self.s3_client is not None and
            (parsed_key is not None or aggregated_key is not None)
        )
