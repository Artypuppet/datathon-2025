"""
Snowflake Cortex client for vector embeddings and similarity search.

Uses Snowflake Cortex EMBED_TEXT_768 function for generating embeddings
and VECTOR similarity search for finding relevant filing chunks.
"""

import logging
import os
from typing import Dict, Any, List, Optional, Tuple
import snowflake.connector
from snowflake.connector import DictCursor
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)


class SnowflakeClient:
    """
    Client for Snowflake operations including vector embeddings and search.
    
    Uses Snowflake Cortex for embedding generation and vector similarity search.
    """
    
    def __init__(
        self,
        account: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        warehouse: Optional[str] = None,
        database: Optional[str] = None,
        schema: Optional[str] = None,
        role: Optional[str] = None
    ):
        """
        Initialize Snowflake client.
        
        Args:
            account: Snowflake account identifier
            user: Snowflake username
            password: Snowflake password
            warehouse: Snowflake warehouse name
            database: Snowflake database name
            schema: Snowflake schema name
            role: Snowflake role (optional)
        """
        self.account = account or os.getenv('SNOWFLAKE_ACCOUNT')
        self.user = user or os.getenv('SNOWFLAKE_USER')
        self.password = password or os.getenv('SNOWFLAKE_PASSWORD')
        self.warehouse = warehouse or os.getenv('SNOWFLAKE_WAREHOUSE', 'COMPUTE_WH')
        self.database = database or os.getenv('SNOWFLAKE_DATABASE', 'REGALPHA')
        self.schema = schema or os.getenv('SNOWFLAKE_SCHEMA', 'PUBLIC')
        self.role = role or os.getenv('SNOWFLAKE_ROLE')
        
        if not all([self.account, self.user, self.password]):
            raise ValueError("Snowflake credentials must be provided via env vars or constructor")
        
        self.conn = None
        self._connect()
        self._ensure_schema()
        
        logger.info(f"[OK] SnowflakeClient initialized: {self.database}.{self.schema}")
    
    def _connect(self):
        """Establish connection to Snowflake."""
        try:
            conn_params = {
                'account': self.account,
                'user': self.user,
                'password': self.password,
                'warehouse': self.warehouse,
                'database': self.database,
                'schema': self.schema
            }
            
            if self.role:
                conn_params['role'] = self.role
            
            self.conn = snowflake.connector.connect(**conn_params)
            logger.info(f"[OK] Connected to Snowflake: {self.account}")
        except Exception as e:
            logger.error(f"[ERROR] Failed to connect to Snowflake: {e}")
            raise
    
    def _ensure_schema(self):
        """Ensure database and schema exist, create if needed."""
        try:
            cursor = self.conn.cursor()
            
            # Create database if not exists
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.database}")
            
            # Use database
            cursor.execute(f"USE DATABASE {self.database}")
            
            # Create schema if not exists
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {self.schema}")
            
            # Use schema
            cursor.execute(f"USE SCHEMA {self.schema}")
            
            # Create filings table if not exists
            self._create_filings_table()
            
            cursor.close()
            logger.info(f"[OK] Schema ensured: {self.database}.{self.schema}")
        except Exception as e:
            logger.error(f"[ERROR] Failed to ensure schema: {e}")
            raise
    
    def _create_filings_table(self):
        """Create filings table with vector column."""
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {self.schema}.filings (
            id STRING PRIMARY KEY,
            ticker STRING NOT NULL,
            company_name STRING,
            filing_type STRING,
            filing_date DATE,
            section_type STRING,
            section_title STRING,
            chunk_text STRING,
            sentence_idx INTEGER,
            total_sentences INTEGER,
            original_sentence STRING,
            embedding VECTOR(FLOAT, 768),
            created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
        )
        """
        
        try:
            cursor = self.conn.cursor()
            cursor.execute(create_table_sql)
            cursor.close()
            logger.info(f"[OK] Filings table created/verified")
        except Exception as e:
            logger.error(f"[ERROR] Failed to create filings table: {e}")
            raise
    
    def store_filing_chunks(
        self,
        ticker: str,
        company_name: str,
        chunks: List[Dict[str, Any]]
    ) -> int:
        """
        Store filing chunks in Snowflake.
        
        Args:
            ticker: Company ticker symbol
            company_name: Company name
            chunks: List of chunk dictionaries with:
                - text: chunk text
                - section_type: section identifier
                - section_title: section title
                - filing_type: 10-K, 10-Q, etc.
                - filing_date: filing date
                - sentence_idx: sentence index
                - total_sentences: total sentences in section
                - original_sentence: original sentence text
        
        Returns:
            Number of chunks stored
        """
        if not chunks:
            logger.warning("[WARN] No chunks to store")
            return 0
        
        logger.info(f"[INFO] Storing {len(chunks)} chunks for {ticker}")
        
        try:
            cursor = self.conn.cursor()
            
            insert_sql = f"""
            INSERT INTO {self.schema}.filings (
                id, ticker, company_name, filing_type, filing_date,
                section_type, section_title, chunk_text,
                sentence_idx, total_sentences, original_sentence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            stored_count = 0
            for chunk in chunks:
                chunk_id = f"{ticker}_{chunk.get('section_type', 'unknown')}_{chunk.get('sentence_idx', 0)}"
                
                # Generate embedding using Cortex
                chunk_text = chunk.get('text', chunk.get('chunk_text', ''))
                if not chunk_text:
                    logger.warning(f"[WARN] Skipping chunk with no text")
                    continue
                
                try:
                    cursor.execute(insert_sql, (
                        chunk_id,
                        ticker,
                        company_name,
                        chunk.get('filing_type', 'N/A'),
                        chunk.get('filing_date'),
                        chunk.get('section_type', 'unknown'),
                        chunk.get('section_title', ''),
                        chunk_text,
                        chunk.get('sentence_idx', 0),
                        chunk.get('total_sentences', 0),
                        chunk.get('original_sentence', chunk_text)
                    ))
                    stored_count += 1
                except Exception as e:
                    logger.warning(f"[WARN] Failed to insert chunk: {e}")
                    continue
            
            cursor.close()
            logger.info(f"[OK] Stored {stored_count} chunks for {ticker}")
            
            # Generate embeddings for newly inserted chunks
            if stored_count > 0:
                self.generate_embeddings(ticker)
            
            return stored_count
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to store chunks: {e}", exc_info=True)
            raise
    
    def generate_embeddings(self, ticker: Optional[str] = None) -> int:
        """
        Generate embeddings for chunks that don't have embeddings yet.
        
        Uses Snowflake Cortex EMBED_TEXT_768 function.
        
        Args:
            ticker: Optional ticker to limit embedding generation
        
        Returns:
            Number of embeddings generated
        """
        logger.info(f"[INFO] Generating embeddings for {ticker or 'all companies'}")
        
        try:
            cursor = self.conn.cursor()
            
            # Update chunks without embeddings
            where_clause = "WHERE embedding IS NULL"
            if ticker:
                where_clause += f" AND ticker = '{ticker}'"
            
            update_sql = f"""
            UPDATE {self.schema}.filings
            SET embedding = SNOWFLAKE.CORTEX.EMBED_TEXT_768('e5-base-v2', chunk_text)
            {where_clause}
            """
            
            cursor.execute(update_sql)
            updated_count = cursor.rowcount
            cursor.close()
            
            logger.info(f"[OK] Generated {updated_count} embeddings")
            return updated_count
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to generate embeddings: {e}", exc_info=True)
            raise
    
    def similarity_search(
        self,
        query_text: str,
        ticker: Optional[str] = None,
        top_k: int = 10,
        min_similarity: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Perform similarity search using vector embeddings.
        
        Args:
            query_text: Query text to search for
            ticker: Optional ticker to filter results
            top_k: Number of results to return
            min_similarity: Minimum similarity threshold
        
        Returns:
            List of matching chunks with similarity scores
        """
        logger.info(f"[INFO] Similarity search: query='{query_text[:50]}...', ticker={ticker}, top_k={top_k}")
        
        try:
            cursor = self.conn.cursor(DictCursor)
            
            # Generate query embedding
            query_embedding_sql = f"""
            SELECT SNOWFLAKE.CORTEX.EMBED_TEXT_768('e5-base-v2', ?) AS query_embedding
            """
            cursor.execute(query_embedding_sql, (query_text,))
            query_result = cursor.fetchone()
            
            if not query_result or not query_result['QUERY_EMBEDDING']:
                logger.error("[ERROR] Failed to generate query embedding")
                return []
            
            query_embedding = query_result['QUERY_EMBEDDING']
            
            # Build search query
            where_clause = "WHERE embedding IS NOT NULL"
            if ticker:
                where_clause += f" AND ticker = '{ticker}'"
            
            search_sql = f"""
            SELECT 
                id,
                ticker,
                company_name,
                filing_type,
                filing_date,
                section_type,
                section_title,
                chunk_text,
                original_sentence,
                VECTOR_COSINE_SIMILARITY(embedding, ?) AS similarity
            FROM {self.schema}.filings
            {where_clause}
            QUALIFY similarity >= {min_similarity}
            ORDER BY similarity DESC
            LIMIT {top_k}
            """
            
            cursor.execute(search_sql, (query_embedding,))
            results = cursor.fetchall()
            cursor.close()
            
            # Format results
            formatted_results = []
            for row in results:
                formatted_results.append({
                    'doc_id': row['ID'],
                    'ticker': row['TICKER'],
                    'company_name': row['COMPANY_NAME'],
                    'filing_type': row['FILING_TYPE'],
                    'filing_date': str(row['FILING_DATE']) if row['FILING_DATE'] else None,
                    'section_type': row['SECTION_TYPE'],
                    'section_title': row['SECTION_TITLE'],
                    'chunk_text': row['CHUNK_TEXT'],
                    'original_sentence': row['ORIGINAL_SENTENCE'],
                    'similarity': float(row['SIMILARITY'])
                })
            
            logger.info(f"[OK] Found {len(formatted_results)} similar chunks")
            return formatted_results
            
        except Exception as e:
            logger.error(f"[ERROR] Similarity search failed: {e}", exc_info=True)
            raise
    
    def get_company_chunks(
        self,
        ticker: str,
        section_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all chunks for a company.
        
        Args:
            ticker: Company ticker
            section_type: Optional section type filter
        
        Returns:
            List of chunk dictionaries
        """
        logger.info(f"[INFO] Retrieving chunks for {ticker}")
        
        try:
            cursor = self.conn.cursor(DictCursor)
            
            where_clause = f"WHERE ticker = '{ticker}'"
            if section_type:
                where_clause += f" AND section_type = '{section_type}'"
            
            select_sql = f"""
            SELECT 
                id,
                ticker,
                company_name,
                filing_type,
                filing_date,
                section_type,
                section_title,
                chunk_text,
                original_sentence,
                sentence_idx,
                total_sentences,
                embedding
            FROM {self.schema}.filings
            {where_clause}
            ORDER BY filing_date DESC, section_type, sentence_idx
            """
            
            cursor.execute(select_sql)
            results = cursor.fetchall()
            cursor.close()
            
            # Format results
            chunks = []
            for row in results:
                chunk = {
                    'doc_id': row['ID'],
                    'ticker': row['TICKER'],
                    'company_name': row['COMPANY_NAME'],
                    'filing_type': row['FILING_TYPE'],
                    'filing_date': str(row['FILING_DATE']) if row['FILING_DATE'] else None,
                    'section_type': row['SECTION_TYPE'],
                    'section_title': row['SECTION_TITLE'],
                    'text': row['CHUNK_TEXT'],
                    'original_sentence': row['ORIGINAL_SENTENCE'],
                    'sentence_idx': row['SENTENCE_IDX'],
                    'total_sentences': row['TOTAL_SENTENCES']
                }
                
                # Include embedding if available
                if row['EMBEDDING']:
                    chunk['embedding'] = row['EMBEDDING']
                
                chunks.append(chunk)
            
            logger.info(f"[OK] Retrieved {len(chunks)} chunks for {ticker}")
            return chunks
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to retrieve chunks: {e}", exc_info=True)
            raise
    
    def delete_company_chunks(self, ticker: str) -> int:
        """
        Delete all chunks for a company.
        
        Args:
            ticker: Company ticker
        
        Returns:
            Number of chunks deleted
        """
        logger.info(f"[INFO] Deleting chunks for {ticker}")
        
        try:
            cursor = self.conn.cursor()
            
            delete_sql = f"DELETE FROM {self.schema}.filings WHERE ticker = ?"
            cursor.execute(delete_sql, (ticker,))
            deleted_count = cursor.rowcount
            cursor.close()
            
            logger.info(f"[OK] Deleted {deleted_count} chunks for {ticker}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to delete chunks: {e}", exc_info=True)
            raise
    
    def close(self):
        """Close Snowflake connection."""
        if self.conn:
            self.conn.close()
            logger.info("[OK] Snowflake connection closed")
