"""
Vector database client for storing and querying embeddings.

Supports:
- AWS OpenSearch (production) - vector search with k-NN
- ChromaDB (local development) - lightweight vector store

Features:
- Store company filing embeddings with sentence references
- Store legislation embeddings
- Query for similarity between legislation and companies
- Retrieve matched sentences with context for explainability
"""

import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to import vector DB libraries
try:
    import chromadb
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False
    logger.warning("[WARN] chromadb not available")

try:
    from opensearchpy import OpenSearch
    HAS_OPENSEARCH = True
except ImportError:
    HAS_OPENSEARCH = False
    logger.warning("[WARN] opensearch-py not available")


class VectorDBClient:
    """
    Unified interface for vector database operations.
    
    Supports both ChromaDB (local) and OpenSearch (AWS production).
    Automatically selects based on configuration.
    """
    
    def __init__(
        self,
        backend: str = "auto",  # "chroma", "opensearch", or "auto"
        collection_name: str = "company_legislation_embeddings",
        embedding_dim: int = 768  # BERT base embedding dimension (industry-bert-sec-v0.1)
    ):
        """
        Initialize vector database client.
        
        Args:
            backend: Database backend ("chroma", "opensearch", or "auto")
            collection_name: Collection/index name
            embedding_dim: Embedding dimension (default: 768 for BERT base models)
        """
        self.backend = self._determine_backend(backend)
        self.collection_name = collection_name
        self.embedding_dim = embedding_dim
        
        if self.backend == "chroma":
            self._init_chroma()
        elif self.backend == "opensearch":
            self._init_opensearch()
        else:
            raise ValueError(f"Unsupported backend: {self.backend}")
        
        logger.info(f"[INFO] VectorDBClient initialized with backend: {self.backend}")
    
    def _determine_backend(self, backend: str) -> str:
        """Determine which backend to use."""
        if backend == "auto":
            # Prefer OpenSearch if endpoint is configured, otherwise ChromaDB
            opensearch_endpoint = os.getenv('OPENSEARCH_ENDPOINT')
            if opensearch_endpoint and HAS_OPENSEARCH:
                return "opensearch"
            elif HAS_CHROMADB:
                return "chroma"
            else:
                raise RuntimeError("No vector database backend available (need chromadb or opensearch-py)")
        elif backend == "chroma":
            if not HAS_CHROMADB:
                raise ImportError("chromadb not available")
            return "chroma"
        elif backend == "opensearch":
            if not HAS_OPENSEARCH:
                raise ImportError("opensearch-py not available")
            return "opensearch"
        else:
            raise ValueError(f"Unknown backend: {backend}")
    
    def _init_chroma(self):
        """Initialize ChromaDB client."""
        persist_directory = os.getenv('CHROMA_PERSIST_DIR', './chroma_db')
        
        # Create directory if it doesn't exist
        Path(persist_directory).mkdir(parents=True, exist_ok=True)
        
        # Use PersistentClient to actually persist data to disk
        self.client = chromadb.PersistentClient(
            path=persist_directory
        )
        
        # Get or create collection
        try:
            self.collection = self.client.get_collection(
                name=self.collection_name,
                embedding_function=None  # We'll provide embeddings directly
            )
        except Exception:
            self.collection = self.client.create_collection(
                name=self.collection_name,
                embedding_function=None  # We'll provide embeddings directly
            )
        
        logger.info(f"[OK] ChromaDB collection '{self.collection_name}' ready")
    
    def _init_opensearch(self):
        """Initialize OpenSearch client."""
        endpoint = os.getenv('OPENSEARCH_ENDPOINT')
        if not endpoint:
            raise ValueError("OPENSEARCH_ENDPOINT environment variable required")
        
        logger.info(f"[DEBUG] OpenSearch initialization started")
        logger.info(f"[DEBUG] OPENSEARCH_ENDPOINT: {endpoint}")
        
        # Parse endpoint (format: https://search-xxx.region.es.amazonaws.com)
        use_ssl = endpoint.startswith('https://')
        host = endpoint.replace('https://', '').replace('http://', '')
        
        auth = None
        aws_auth = None
        
        # Check if using AWS IAM auth
        use_iam_auth_env = os.getenv('OPENSEARCH_USE_IAM_AUTH', 'false')
        use_iam_auth = use_iam_auth_env.lower() == 'true'
        
        logger.info(f"[DEBUG] OPENSEARCH_USE_IAM_AUTH env value: '{use_iam_auth_env}'")
        logger.info(f"[DEBUG] Using IAM auth: {use_iam_auth}")
        
        if use_iam_auth:
            from opensearchpy import RequestsHttpConnection
            from requests_aws4auth import AWS4Auth
            import boto3
            
            region = os.getenv('AWS_REGION') or os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
            logger.info(f"[DEBUG] IAM auth: region={region}")
            
            # Log AWS credential environment variables (without exposing secrets)
            aws_key_id = os.getenv('AWS_ACCESS_KEY_ID')
            aws_secret = os.getenv('AWS_SECRET_ACCESS_KEY')
            aws_session_token = os.getenv('AWS_SESSION_TOKEN')
            
            logger.info(f"[DEBUG] AWS_ACCESS_KEY_ID: {'SET' if aws_key_id else 'NOT SET'} ({aws_key_id[:10] + '...' if aws_key_id and len(aws_key_id) > 10 else 'N/A'})")
            logger.info(f"[DEBUG] AWS_SECRET_ACCESS_KEY: {'SET' if aws_secret else 'NOT SET'}")
            logger.info(f"[DEBUG] AWS_SESSION_TOKEN: {'SET' if aws_session_token else 'NOT SET'}")
            logger.info(f"[DEBUG] AWS_REGION: {os.getenv('AWS_REGION', 'NOT SET')}")
            logger.info(f"[DEBUG] AWS_DEFAULT_REGION: {os.getenv('AWS_DEFAULT_REGION', 'NOT SET')}")
            
            try:
                session = boto3.Session()
                credentials = session.get_credentials()
                if not credentials:
                    logger.error("[ERROR] boto3.Session().get_credentials() returned None")
                    raise ValueError("No AWS credentials found. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
                
                logger.info(f"[DEBUG] boto3 credentials found: access_key={credentials.access_key[:10]}..., secret_key={'SET' if credentials.secret_key else 'NOT SET'}")
                
                aws_auth = AWS4Auth(
                    credentials.access_key,
                    credentials.secret_key,
                    region,
                    'es',
                    session_token=credentials.token
                )
                connection_class = RequestsHttpConnection
                logger.info(f"[INFO] Using IAM authentication for OpenSearch (region: {region})")
            except Exception as e:
                logger.error(f"[ERROR] Failed to initialize IAM auth: {e}", exc_info=True)
                raise ValueError(f"Failed to initialize IAM authentication: {e}")
        else:
            # Basic auth
            username = os.getenv('OPENSEARCH_USERNAME')
            password = os.getenv('OPENSEARCH_PASSWORD')
            
            logger.info(f"[DEBUG] OPENSEARCH_USERNAME env: {'SET' if username else 'NOT SET'}")
            if username:
                logger.info(f"[DEBUG] OPENSEARCH_USERNAME value: {username}")
            logger.info(f"[DEBUG] OPENSEARCH_PASSWORD env: {'SET' if password else 'NOT SET'}")
            
            if not username or not password:
                logger.error(f"[ERROR] Missing credentials - username={bool(username)}, password={bool(password)}")
                raise ValueError(
                    "OpenSearch authentication credentials missing. "
                    "Set OPENSEARCH_USERNAME and OPENSEARCH_PASSWORD for basic auth, "
                    "or set OPENSEARCH_USE_IAM_AUTH=true for IAM authentication."
                )
            
            auth = (username, password)
            connection_class = None
            logger.info(f"[INFO] Using basic authentication (username/password) for OpenSearch")
            logger.info(f"[DEBUG] Auth tuple created: username={username}, password={'SET' if password else 'NOT SET'}")
        
        # Log what we're using for auth (but don't log passwords)
        if use_iam_auth:
            logger.info(f"[INFO] OpenSearch client config: IAM auth, host={host}, region={region}")
            logger.info(f"[DEBUG] aws_auth object: {type(aws_auth).__name__ if aws_auth else 'None'}")
        else:
            logger.info(f"[INFO] OpenSearch client config: Basic auth, host={host}, username={username}")
            logger.info(f"[DEBUG] http_auth tuple: {type(auth).__name__}, username={auth[0] if auth else 'None'}")
        
        # Initialize OpenSearch client with correct auth parameters
        # For basic auth: use http_auth, set aws_auth=None
        # For IAM auth: use aws_auth, set http_auth=None
        client_kwargs = {
            'hosts': [{'host': host, 'port': 443 if use_ssl else 80}],
            'use_ssl': use_ssl,
            'verify_certs': True,
        }
        
        if use_iam_auth:
            client_kwargs['http_auth'] = None
            client_kwargs['aws_auth'] = aws_auth
            client_kwargs['connection_class'] = connection_class
            logger.info(f"[DEBUG] OpenSearch client kwargs: http_auth=None, aws_auth={type(aws_auth).__name__}, connection_class={connection_class.__name__ if connection_class else 'None'}")
        else:
            client_kwargs['http_auth'] = auth
            client_kwargs['aws_auth'] = None
            logger.info(f"[DEBUG] OpenSearch client kwargs: http_auth={type(auth).__name__} (username: {auth[0] if auth else 'None'}), aws_auth=None")
        
        logger.info(f"[DEBUG] Creating OpenSearch client with host={host}, port={443 if use_ssl else 80}, use_ssl={use_ssl}")
        self.client = OpenSearch(**client_kwargs)
        logger.info(f"[DEBUG] OpenSearch client created successfully")
        
        # Test connection before trying to use index
        try:
            logger.info("[INFO] Testing OpenSearch connection...")
            info = self.client.info()
            logger.info(f"[OK] OpenSearch connection successful. Cluster: {info.get('cluster_name', 'unknown')}")
        except Exception as e:
            logger.error(f"[ERROR] Failed to connect to OpenSearch: {e}")
            logger.error(f"[ERROR] Endpoint: {endpoint}")
            if use_iam_auth:
                logger.error(f"[ERROR] IAM auth failed. Check AWS credentials and IAM permissions.")
            else:
                logger.error(f"[ERROR] Basic auth failed. Check username/password.")
            raise
        
        # Create index if it doesn't exist
        self._ensure_opensearch_index()
        
        logger.info(f"[OK] OpenSearch connected to {endpoint}")
    
    def _ensure_opensearch_index(self):
        """Ensure OpenSearch index exists with proper mapping."""
        index_name = self.collection_name
        
        # Check if index exists
        index_exists = self.client.indices.exists(index=index_name)
        
        # If index exists, check if it has the correct mapping (filing_date as keyword)
        if index_exists:
            try:
                current_mapping = self.client.indices.get_mapping(index=index_name)
                props = current_mapping[index_name]['mappings'].get('properties', {})
                filing_date_mapping = props.get('filing_date', {})
                
                # If filing_date is still mapped as 'date', delete and recreate
                if filing_date_mapping.get('type') == 'date':
                    logger.warning(f"[WARN] Index '{index_name}' has old mapping (filing_date as date)")
                    logger.info(f"[INFO] Deleting index to recreate with correct mapping...")
                    self.client.indices.delete(index=index_name)
                    index_exists = False
            except Exception as e:
                logger.warning(f"[WARN] Could not check index mapping: {e}")
                # If we can't check, try to continue - will fail with clear error if wrong
        
        if not index_exists:
            # Create index with k-NN mapping for vector search
            index_body = {
                "settings": {
                    "index": {
                        "knn": True,
                        "knn.algo_param.ef_search": 100
                    }
                },
                "mappings": {
                    "properties": {
                        "embedding": {
                            "type": "knn_vector",
                            "dimension": self.embedding_dim,
                            "method": {
                                "name": "hnsw",
                                "space_type": "cosinesimil",
                                "engine": "lucene"
                            }
                        },
                        "content_type": {"type": "keyword"},  # "company_sentence" or "legislation"
                        "ticker": {"type": "keyword"},
                        "company_name": {"type": "text"},
                        "legislation_id": {"type": "keyword"},
                        "section_type": {"type": "keyword"},
                        "section_title": {"type": "text"},
                        "filing_type": {"type": "keyword"},
                        "filing_date": {"type": "keyword"},  # Changed from date to keyword to handle "N/A" values
                        "sentence_idx": {"type": "integer"},
                        "total_sentences": {"type": "integer"},
                        "original_sentence": {"type": "text"},
                        "sentence_text": {"type": "text"},  # Enriched text with context
                        "metadata": {"type": "object"},
                        "created_at": {"type": "date"}
                    }
                }
            }
            
            self.client.indices.create(index=index_name, body=index_body)
            logger.info(f"[OK] Created OpenSearch index: {index_name}")
        else:
            logger.info(f"[INFO] OpenSearch index '{index_name}' already exists")
    
    def store_company_embeddings(
        self,
        ticker: str,
        company_name: str,
        chunks: List[Dict[str, Any]]
    ) -> int:
        """
        Store company filing embeddings in vector DB.
        
        Args:
            ticker: Company ticker symbol
            company_name: Company name
            chunks: List of chunk dictionaries with embeddings and metadata
            
        Returns:
            Number of embeddings stored
        """
        logger.info(f"[INFO] Storing {len(chunks)} embeddings for {ticker}")
        
        # Use batch operations for better performance
        if self.backend == "opensearch":
            return self._store_company_embeddings_batch_opensearch(
                ticker=ticker,
                company_name=company_name,
                chunks=chunks
            )
        else:
            # ChromaDB - store individually (no bulk API available)
            stored_count = 0
            for chunk in chunks:
                embedding = chunk.get('embedding')
                if embedding is None:
                    logger.warning(f"[WARN] Chunk missing embedding, skipping")
                    continue
                
                doc_id = self._build_doc_id(
                    content_type='company_sentence',
                    ticker=ticker,
                    section_type=chunk.get('section_type', 'unknown'),
                    sentence_idx=chunk.get('sentence_idx')
                )
                
                metadata = self._build_chunk_metadata(chunk, ticker, company_name)
                self._store_chroma(doc_id, embedding, metadata)
                stored_count += 1
            
            logger.info(f"[OK] Stored {stored_count} embeddings for {ticker}")
            return stored_count
    
    def _build_chunk_metadata(
        self,
        chunk: Dict[str, Any],
        ticker: str,
        company_name: str
    ) -> Dict[str, Any]:
        """Build metadata dictionary for a chunk."""
        metadata = {
            'content_type': 'company_sentence',
            'ticker': ticker,
            'company_name': company_name,
            'section_type': chunk.get('section_type', ''),
            'section_title': chunk.get('section_title', ''),
            'sentence_idx': chunk.get('sentence_idx'),
            'total_sentences': chunk.get('total_sentences_in_section'),
            'original_sentence': chunk.get('original_sentence', ''),
            'sentence_text': chunk.get('text', ''),  # Enriched text with context
            'created_at': datetime.now().isoformat()
        }
        
        # Only include filing_type if it's not N/A or empty
        filing_type = chunk.get('filing_type', '')
        if filing_type and filing_type != 'N/A':
            metadata['filing_type'] = filing_type
        
        # Only include filing_date if it's not N/A or empty
        filing_date = chunk.get('filing_date', '')
        if filing_date and filing_date != 'N/A':
            metadata['filing_date'] = filing_date
        
        return metadata
    
    def _store_company_embeddings_batch_opensearch(
        self,
        ticker: str,
        company_name: str,
        chunks: List[Dict[str, Any]]
    ) -> int:
        """
        Store company embeddings in OpenSearch using bulk API for better performance.
        
        Args:
            ticker: Company ticker
            company_name: Company name
            chunks: List of chunk dictionaries with embeddings
            
        Returns:
            Number of embeddings stored
        """
        from opensearchpy.helpers import bulk
        
        logger.info(f"[INFO] Batch storing {len(chunks)} embeddings in OpenSearch")
        
        # Prepare bulk operations
        actions = []
        valid_chunks = 0
        
        for chunk in chunks:
            embedding = chunk.get('embedding')
            if embedding is None:
                logger.warning(f"[WARN] Chunk missing embedding, skipping")
                continue
            
            # Build document ID
            doc_id = self._build_doc_id(
                content_type='company_sentence',
                ticker=ticker,
                section_type=chunk.get('section_type', 'unknown'),
                sentence_idx=chunk.get('sentence_idx')
            )
            
            # Build metadata
            metadata = self._build_chunk_metadata(chunk, ticker, company_name)
            
            # Build document for bulk operation
            document = {
                '_index': self.collection_name,
                '_id': doc_id,
                '_source': {
                    'embedding': embedding.tolist() if isinstance(embedding, np.ndarray) else embedding,
                    **metadata
                }
            }
            
            actions.append(document)
            valid_chunks += 1
        
        if not actions:
            logger.warning("[WARN] No valid chunks to store")
            return 0
        
        # Perform bulk insert
        try:
            success_count, failed_items = bulk(
                self.client,
                actions,
                chunk_size=100,  # Process in batches of 100
                max_retries=3,
                raise_on_error=False  # Don't raise on individual failures
            )
            
            if failed_items:
                logger.warning(f"[WARN] {len(failed_items)} items failed to index")
                # Log first few failures for debugging
                for item in failed_items[:5]:
                    logger.warning(f"[WARN] Failed item: {item}")
            
            logger.info(f"[OK] Stored {success_count} embeddings for {ticker} (batch mode)")
            return success_count
            
        except Exception as e:
            logger.error(f"[ERROR] Bulk insert failed: {e}", exc_info=True)
            # Fallback to individual inserts
            logger.info("[INFO] Falling back to individual inserts...")
            return self._store_company_embeddings_individual_opensearch(
                ticker=ticker,
                company_name=company_name,
                chunks=chunks
            )
    
    def _store_company_embeddings_individual_opensearch(
        self,
        ticker: str,
        company_name: str,
        chunks: List[Dict[str, Any]]
    ) -> int:
        """Fallback: Store embeddings one by one (slower)."""
        stored_count = 0
        
        for chunk in chunks:
            embedding = chunk.get('embedding')
            if embedding is None:
                continue
            
            doc_id = self._build_doc_id(
                content_type='company_sentence',
                ticker=ticker,
                section_type=chunk.get('section_type', 'unknown'),
                sentence_idx=chunk.get('sentence_idx')
            )
            
            metadata = self._build_chunk_metadata(chunk, ticker, company_name)
            self._store_opensearch(doc_id, embedding, metadata)
            stored_count += 1
        
        return stored_count
    
    def store_legislation_embedding(
        self,
        legislation_id: str,
        legislation_text: str,
        embedding: np.ndarray,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Store legislation embedding in vector DB.
        
        Args:
            legislation_id: Unique identifier for the legislation
            legislation_text: Original legislation text
            embedding: Embedding vector
            metadata: Additional metadata (jurisdiction, title, etc.)
            
        Returns:
            Document ID
        """
        logger.info(f"[INFO] Storing legislation embedding: {legislation_id}")
        
        doc_id = self._build_doc_id(
            content_type='legislation',
            legislation_id=legislation_id
        )
        
        metadata = metadata or {}
        metadata.update({
            'content_type': 'legislation',
            'legislation_id': legislation_id,
            'legislation_text': legislation_text,
            'created_at': datetime.now().isoformat()
        })
        
        # Store based on backend
        if self.backend == "chroma":
            self._store_chroma(doc_id, embedding.tolist(), metadata)
        elif self.backend == "opensearch":
            self._store_opensearch(doc_id, embedding.tolist(), metadata)
        
        logger.info(f"[OK] Stored legislation embedding: {legislation_id}")
        return doc_id
    
    def find_similar_sentences(
        self,
        query_embedding: np.ndarray,
        content_type: str = "company_sentence",
        ticker: Optional[str] = None,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find similar sentences using vector similarity search.
        
        Args:
            query_embedding: Query embedding vector
            content_type: Filter by content type ("company_sentence" or "legislation")
            ticker: Optional ticker filter for company sentences
            top_k: Number of results to return
            
        Returns:
            List of similar documents with metadata
        """
        logger.info(f"[INFO] Finding top {top_k} similar {content_type} documents")
        
        if self.backend == "chroma":
            return self._query_chroma(query_embedding, content_type, ticker, top_k)
        elif self.backend == "opensearch":
            return self._query_opensearch(query_embedding, content_type, ticker, top_k)
        else:
            raise ValueError(f"Unknown backend: {self.backend}")
    
    def _build_doc_id(
        self,
        content_type: str,
        ticker: Optional[str] = None,
        legislation_id: Optional[str] = None,
        section_type: Optional[str] = None,
        sentence_idx: Optional[int] = None
    ) -> str:
        """Build unique document ID."""
        parts = [content_type]
        
        if ticker:
            parts.append(ticker)
        if legislation_id:
            parts.append(legislation_id)
        if section_type:
            parts.append(section_type)
        if sentence_idx is not None:
            parts.append(str(sentence_idx))
        
        return "_".join(parts)
    
    def _store_chroma(self, doc_id: str, embedding: List[float], metadata: Dict[str, Any]):
        """Store document in ChromaDB."""
        # ChromaDB expects embeddings as arrays and metadata as dict
        self.collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            metadatas=[{
                k: str(v) if v is not None else "" 
                for k, v in metadata.items()
            }],
            documents=[metadata.get('original_sentence', metadata.get('legislation_text', ''))]
        )
    
    def _store_opensearch(self, doc_id: str, embedding: List[float], metadata: Dict[str, Any]):
        """Store document in OpenSearch."""
        document = {
            'embedding': embedding,
            **metadata
        }
        
        self.client.index(
            index=self.collection_name,
            id=doc_id,
            body=document
        )
    
    def _query_chroma(
        self,
        query_embedding: np.ndarray,
        content_type: str,
        ticker: Optional[str],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Query ChromaDB."""
        # Build where clause with proper ChromaDB syntax
        where_clause = None
        if ticker:
            # ChromaDB requires $and for multiple conditions
            where_clause = {
                "$and": [
                    {"content_type": content_type},
                    {"ticker": ticker}
                ]
            }
        else:
            where_clause = {"content_type": content_type}
        
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k,
            where=where_clause
        )
        
        # Format results
        formatted_results = []
        if results['ids'] and len(results['ids'][0]) > 0:
            for i in range(len(results['ids'][0])):
                doc_id = results['ids'][0][i]
                distance = results['distances'][0][i]
                metadata = results['metadatas'][0][i]
                
                # Convert distance to similarity (ChromaDB uses cosine distance)
                similarity = 1 - distance
                
                formatted_results.append({
                    'doc_id': doc_id,
                    'similarity': float(similarity),
                    'distance': float(distance),
                    **metadata
                })
        
        return formatted_results
    
    def _query_opensearch(
        self,
        query_embedding: np.ndarray,
        content_type: str,
        ticker: Optional[str],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Query OpenSearch using k-NN."""
        query_body = {
            "size": top_k,
            "query": {
                "bool": {
                    "must": [
                        {
                            "knn": {
                                "embedding": {
                                    "vector": query_embedding.tolist(),
                                    "k": top_k
                                }
                            }
                        }
                    ],
                    "filter": [
                        {"term": {"content_type": content_type}}
                    ]
                }
            }
        }
        
        # Add ticker filter if provided
        if ticker:
            query_body["query"]["bool"]["filter"].append(
                {"term": {"ticker": ticker}}
            )
        
        response = self.client.search(
            index=self.collection_name,
            body=query_body
        )
        
        # Format results
        formatted_results = []
        for hit in response['hits']['hits']:
            source = hit['_source']
            score = hit['_score']
            
            # OpenSearch k-NN returns score (higher is better)
            # For cosine similarity, normalize if needed
            similarity = float(score) / 100.0 if score > 1.0 else float(score)
            
            formatted_results.append({
                'doc_id': hit['_id'],
                'similarity': similarity,
                'distance': 1 - similarity,
                **source
            })
        
        return formatted_results
    
    def delete_company_embeddings(self, ticker: str) -> int:
        """
        Delete all embeddings for a company.
        
        Args:
            ticker: Company ticker
            
        Returns:
            Number of documents deleted
        """
        logger.info(f"[INFO] Deleting embeddings for {ticker}")
        
        if self.backend == "chroma":
            # ChromaDB requires querying with where clause that has correct syntax
            # ChromaDB uses $and, $or operators for multiple conditions
            try:
                # Try to get IDs matching both conditions
                results = self.collection.get(
                    where={
                        "$and": [
                            {"ticker": ticker},
                            {"content_type": "company_sentence"}
                        ]
                    }
                )
                
                if results and results.get('ids') and len(results['ids']) > 0:
                    self.collection.delete(ids=results['ids'])
                    deleted_count = len(results['ids'])
                    logger.info(f"[OK] Deleted {deleted_count} embeddings for {ticker}")
                    return deleted_count
                else:
                    logger.info(f"[INFO] No embeddings found for {ticker}")
                    return 0
            except Exception as e:
                # Fallback: try to find by ticker only, then filter
                logger.warning(f"[WARN] Delete with $and failed, trying alternative: {e}")
                try:
                    results = self.collection.get(
                        where={"ticker": ticker}
                    )
                    if results and results.get('ids'):
                        # Filter by content_type manually
                        ids_to_delete = []
                        metadatas = results.get('metadatas', [])
                        for i, meta in enumerate(metadatas):
                            if meta and meta.get('content_type') == 'company_sentence':
                                ids_to_delete.append(results['ids'][i])
                        
                        if ids_to_delete:
                            self.collection.delete(ids=ids_to_delete)
                            deleted_count = len(ids_to_delete)
                            logger.info(f"[OK] Deleted {deleted_count} embeddings for {ticker}")
                            return deleted_count
                except Exception as e2:
                    logger.warning(f"[WARN] Alternative delete failed: {e2}")
                    return 0
        
        elif self.backend == "opensearch":
            # OpenSearch delete by query
            query = {
                "query": {
                    "bool": {
                        "filter": [
                            {"term": {"ticker": ticker}},
                            {"term": {"content_type": "company_sentence"}}
                        ]
                    }
                }
            }
            
            response = self.client.delete_by_query(
                index=self.collection_name,
                body=query
            )
            
            deleted_count = response.get('deleted', 0)
            logger.info(f"[OK] Deleted {deleted_count} embeddings for {ticker}")
            return deleted_count
        
        return 0


def get_vectordb_client(backend: str = "auto") -> VectorDBClient:
    """
    Get a configured vector database client.
    
    Args:
        backend: Backend to use ("chroma", "opensearch", or "auto")
        
    Returns:
        VectorDBClient instance
    """
    return VectorDBClient(backend=backend)

