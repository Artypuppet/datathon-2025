# Detailed Pipeline Overview - PolyFinances Datathon 2025

## Executive Summary

The PolyFinances pipeline is an end-to-end system that transforms raw regulatory and financial documents into actionable risk insights. It processes SEC filings, legislation, and financial data through four main stages: parsing, aggregation, embedding generation, and vector database storage. The system supports both single-file processing (via Streamlit) and batch processing (via SageMaker) for all S&P 500 companies.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          DATA INGESTION                                  │
├─────────────────────────────────────────────────────────────────────────┤
│  Input Sources:                                                          │
│  • SEC Filings (10-K, 10-Q, 8-K) - HTML format                         │
│  • Legislation (EU/US/CN directives) - HTML/XML format                  │
│  • Financial Data (S&P 500 composition, stock metrics) - CSV format     │
│  • User uploads via Streamlit dashboard                                │
└───────────────────────┬─────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    STAGE 1: PARSE & AGGREGATE                           │
├─────────────────────────────────────────────────────────────────────────┤
│  For Company Filings:                                                    │
│  1. Parse individual filings → structured JSON                          │
│  2. Group all filings by ticker                                          │
│  3. Merge sections (Business, Risk Factors, MD&A)                       │
│  4. Extract entities (companies, countries, products)                   │
│  5. Build knowledge graph (relationships, temporal events)              │
│  6. Enrich with external metadata (Yahoo Finance, cached)              │
│                                                                          │
│  For Legislation:                                                        │
│  1. Parse HTML/XML → structured JSON                                    │
│  2. Extract jurisdiction, scope, affected regions/sectors               │
│  3. Identify key provisions and effective dates                          │
│                                                                          │
│  Output: aggregated/companies/{ticker}.json                            │
│          aggregated/regulations/{regulation_id}.json                    │
└───────────────────────┬─────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    STAGE 2: EMBEDDING GENERATION                         │
├─────────────────────────────────────────────────────────────────────────┤
│  Model: llmware/industry-bert-sec-v0.1 (384-dimensional vectors)       │
│                                                                          │
│  For Companies:                                                          │
│  1. Load aggregated company knowledge graph                              │
│  2. Chunk text into sentences/paragraphs                               │
│  3. Generate embeddings for each chunk                                 │
│  4. Create document-level embedding (mean pooling)                      │
│  5. Optional: Contextual enrichment (add metadata context)              │
│                                                                          │
│  For Regulations:                                                        │
│  1. Load processed regulation data                                       │
│  2. Generate embeddings with jurisdiction context                       │
│  3. Store chunk-level and document-level embeddings                     │
│                                                                          │
│  Output: embeddings/{ticker}_embedded.json                             │
│          embeddings/{regulation_id}_embedded.json                       │
└───────────────────────┬─────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    STAGE 3: VECTOR DATABASE STORAGE                      │
├─────────────────────────────────────────────────────────────────────────┤
│  Backend: OpenSearch (production) or ChromaDB (local)                  │
│                                                                          │
│  1. Store company embeddings with metadata                              │
│     - Ticker, company name, sector, filing dates                         │
│     - Chunk embeddings with source text references                      │
│                                                                          │
│  2. Store regulation embeddings with metadata                           │
│     - Regulation ID, jurisdiction, effective date                        │
│     - Affected regions/sectors                                          │
│                                                                          │
│  3. Index for similarity search                                         │
│     - Cosine similarity for semantic matching                           │
│     - Metadata filtering (sector, region, date ranges)                 │
│                                                                          │
│  Output: OpenSearch index: company_embeddings                           │
└───────────────────────┬─────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    STAGE 4: RISK SCORING & VISUALIZATION                 │
├─────────────────────────────────────────────────────────────────────────┤
│  Risk Assessment:                                                        │
│  1. Query similarity between regulations and companies                  │
│  2. Calculate risk scores based on:                                     │
│     - Semantic similarity (embedding cosine distance)                    │
│     - Financial metrics (market cap, EPS, FCF)                          │
│     - Sector/region exposure                                             │
│     - Temporal factors (filing recency, regulation effective dates)     │
│                                                                          │
│  3. Generate explainable risk factors                                   │
│     - Top contributing sentences from filings                            │
│     - Legislation sections with highest similarity                       │
│     - Confidence scores per factor                                       │
│                                                                          │
│  Dashboard:                                                              │
│  • Streamlit interface for interactive exploration                      │
│  • Sector-level aggregation and filtering                               │
│  • Pie charts, risk score tables, drill-down views                     │
│  • Export capabilities (CSV, JSON)                                       │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Detailed Stage Breakdown

### Stage 1: Parse & Aggregate

**Purpose**: Transform raw documents into structured, aggregated knowledge graphs.

#### 1.1 File Parsing

**Input**: Raw files from S3 or local storage
- `input/filings/{ticker}/{date}-{type}.html` (10-K, 10-Q, 8-K)
- `input/regulations/{jurisdiction}/{regulation_id}.html`
- `input/financial/sp500_composition.csv`

**Process**:

**For SEC Filings (HTMLFilingParser)**:
```python
1. Detect filing type (10-K, 10-Q, 8-K) from filename or content
2. Extract structured sections:
   - Business Description
   - Risk Factors
   - Management Discussion & Analysis (MD&A)
   - Financial Statements (tables)
   - Significant Events (8-K)
3. Parse HTML tables → structured data
4. Extract metadata:
   - Filing date, period end date
   - Company name, CIK, ticker
   - Document structure (sections, subsections)
5. Extract entities using spaCy NER:
   - Organizations (suppliers, partners)
   - Locations (countries, regions)
   - Products/Services
6. Output: parsed/filings/{ticker}/{date}-{type}.json
```

**For Legislation (LegislationParser)**:
```python
1. Detect jurisdiction (EU, US, CN) from filename or content
2. Extract structured sections:
   - Title, effective date, scope
   - Key provisions/articles
   - Affected industries/sectors
   - Geographic applicability
3. Parse HTML/XML structure
4. Extract metadata:
   - Regulation ID, jurisdiction
   - Effective dates, compliance deadlines
   - Affected regions/sectors
5. Output: parsed/regulations/{regulation_id}.json
```

**For Financial Data (CSVParser)**:
```python
1. Detect CSV type (S&P 500 composition, stock performance)
2. Parse columns:
   - Ticker, company name, sector, industry
   - Market cap, EPS, FCF, net income
   - Price, weight (for S&P 500)
3. Normalize data types and formats
4. Output: parsed/financial/{filename}.json
```

#### 1.2 Company Aggregation

**Purpose**: Merge multiple filings per company into a unified knowledge graph.

**Process** (`CompanyAggregator`):
```python
1. Group all filings by ticker from parsed/filings/{ticker}/
2. Temporal ordering:
   - Latest 10-K (most comprehensive)
   - Recent 10-Q filings (quarterly updates)
   - Recent 8-K filings (significant events)
3. Merge sections by type:
   - Business Description: Use latest, merge updates
   - Risk Factors: Combine all unique risks
   - MD&A: Merge quarterly discussions
   - Significant Events: Chronological timeline
4. Entity extraction across all filings:
   - All mentioned companies, countries, products
   - Deduplicate and merge attributes
5. Build knowledge graph:
   - Nodes: Company, Countries, Products, Sectors
   - Edges: operates_in, manufactures_in, supplies_to
   - Temporal: filing_dates, event_dates
6. Enrich with external data (Yahoo Finance):
   - Sector, industry classification
   - Geographic operations
   - Market metrics (cached to avoid rate limits)
7. Output: aggregated/companies/{ticker}.json
```

**Output Schema**:
```json
{
  "ticker": "AAPL",
  "company_name": "Apple Inc.",
  "aggregated_sections": {
    "business": {
      "text": "Merged business description...",
      "sources": ["10-K-2024", "10-Q-2024-Q3"],
      "latest_update": "2024-11-01"
    },
    "risk_factors": [
      {
        "text": "Risk factor text...",
        "category": "supply_chain",
        "sources": ["10-K-2024"],
        "entities": ["China", "Foxconn"]
      }
    ],
    "significant_events": [
      {
        "date": "2024-09-15",
        "type": "supply_chain_disruption",
        "description": "...",
        "source": "8-K-2024-09-15"
      }
    ]
  },
  "entities": {
    "countries": ["China", "USA", "Ireland"],
    "suppliers": ["Foxconn", "TSMC"],
    "products": ["iPhone", "Mac", "Services"]
  },
  "relationships": [
    {
      "source": "AAPL",
      "target": "China",
      "type": "manufactures_in",
      "weight": 0.8,
      "evidence": ["10-K-2024-business", "10-Q-2024-Q3"]
    }
  ],
  "metadata": {
    "latest_10k_date": "2024-11-01",
    "latest_10q_date": "2024-08-01",
    "total_filings": 5,
    "sector": "Technology",
    "industry": "Consumer Electronics",
    "market_cap": 3000000000000,
    "enrichment_date": "2024-12-01"
  }
}
```

#### 1.3 Regulation Processing

**Process**:
```python
1. Load parsed regulation JSON
2. Extract jurisdiction and scope
3. Identify affected regions/sectors
4. Structure key provisions
5. Output: aggregated/regulations/{regulation_id}.json
```

---

### Stage 2: Embedding Generation

**Purpose**: Convert structured text into vector embeddings for semantic similarity search.

#### 2.1 Model Configuration

**Model**: `llmware/industry-bert-sec-v0.1`
- **Dimensions**: 384
- **Domain**: Pre-trained on SEC filings and financial documents
- **Performance**: Optimized for regulatory/financial text similarity

#### 2.2 Company Embedding Process

**Input**: `aggregated/companies/{ticker}.json`

**Process** (`EmbeddingStage`):
```python
1. Load aggregated company data
2. Extract text sections:
   - Business description
   - Risk factors (all)
   - MD&A sections
   - Entity relationships (as text)
3. Chunking strategy:
   Option A: Sentence-level (default)
   - Split into sentences
   - Group 3-5 sentences per chunk
   - Preserve context (3 sentences before/after)
   
   Option B: Paragraph-level
   - Split by paragraphs
   - Max chunk size: 512 tokens
4. Generate embeddings:
   - For each chunk: model.encode(chunk_text)
   - Document-level: mean pooling of all chunks
5. Optional: Contextual enrichment
   - Prepend metadata: "Technology sector company operating in China..."
   - Enhances sector/region matching
6. Store chunk embeddings with:
   - Source text
   - Section reference (business, risk_factors, etc.)
   - Filing date
   - Chunk index
7. Output: embeddings/{ticker}_embedded.json
```

**Output Schema**:
```json
{
  "ticker": "AAPL",
  "document_embedding": [0.123, 0.456, ..., 0.789],  // 384-dim vector
  "chunk_embeddings": [
    {
      "chunk_id": 0,
      "text": "Apple Inc. designs and manufactures...",
      "embedding": [0.111, 0.222, ...],
      "section": "business",
      "section_title": "Business Description",
      "filing_date": "2024-11-01",
      "source_filings": ["10-K-2024"]
    },
    {
      "chunk_id": 1,
      "text": "The Company's manufacturing operations...",
      "embedding": [0.333, 0.444, ...],
      "section": "risk_factors",
      "section_title": "Supply Chain Risks",
      "filing_date": "2024-11-01",
      "source_filings": ["10-K-2024"]
    }
  ],
  "metadata": {
    "total_chunks": 150,
    "model": "llmware/industry-bert-sec-v0.1",
    "embedding_dim": 384,
    "sources": ["10-K-2024", "10-Q-2024-Q3"],
    "generated_at": "2024-12-01T10:00:00Z",
    "contextual_enrichment": true
  }
}
```

#### 2.3 Regulation Embedding Process

**Input**: `aggregated/regulations/{regulation_id}.json`

**Process**:
```python
1. Load regulation data
2. Extract text with jurisdiction context:
   - Prepend: "EU regulation affecting Technology sector..."
   - Include affected regions/sectors in context
3. Generate embeddings (same chunking strategy)
4. Store with regulation metadata
5. Output: embeddings/{regulation_id}_embedded.json
```

---

### Stage 3: Vector Database Storage

**Purpose**: Store embeddings for efficient similarity search and retrieval.

#### 3.1 OpenSearch Configuration

**Index**: `company_embeddings`
- **Mapping**: Vector field (384-dim), metadata fields (ticker, sector, dates)
- **Similarity**: Cosine similarity for semantic search
- **Authentication**: IAM (production) or Basic Auth (local)

#### 3.2 Storage Process (`VectorDBStage`)

**Process**:
```python
1. Load embedding JSON from S3
2. Connect to OpenSearch
3. For each chunk embedding:
   - Create document with:
     * Vector: chunk embedding
     * Metadata: ticker, section, filing_date, chunk_text
     * ID: {ticker}_{chunk_id}
4. Bulk index to OpenSearch
5. Store document-level embedding separately
6. Verify indexing success
7. Output: Indexed in OpenSearch, ready for queries
```

**Document Structure in OpenSearch**:
```json
{
  "ticker": "AAPL",
  "chunk_id": 0,
  "embedding": [0.123, 0.456, ...],  // 384-dim vector
  "text": "Apple Inc. designs and manufactures...",
  "section": "business",
  "section_title": "Business Description",
  "filing_date": "2024-11-01",
  "source_filings": ["10-K-2024"],
  "company_name": "Apple Inc.",
  "sector": "Technology",
  "indexed_at": "2024-12-01T10:00:00Z"
}
```

#### 3.3 Query Interface

**Similarity Search**:
```python
# Find companies at risk from a regulation
query_vector = regulation_embedding
results = opensearch.search(
    index="company_embeddings",
    body={
        "query": {
            "knn": {
                "embedding": {
                    "vector": query_vector,
                    "k": 10
                }
            }
        },
        "filter": {
            "term": {"sector": "Technology"}  # Optional metadata filter
        }
    }
)
```

---

### Stage 4: Risk Scoring & Visualization

**Purpose**: Calculate risk scores and generate actionable insights.

#### 4.1 Risk Scoring (`RegulatoryRiskScorer`)

**Process**:
```python
1. For each company:
   a. Query OpenSearch for similar regulations
      - Use company document embedding
      - Top-K regulations by similarity
   
   b. For each matching regulation:
      - Calculate similarity score (cosine distance)
      - Extract contributing sentences (top chunks)
      - Calculate impact score:
        * Base: similarity score (0-1)
        * Weighted by: sector match, region exposure, financial health
   
   c. Aggregate risk factors:
      - Sum impact scores per regulation
      - Normalize to 0-1 risk score
      - Identify top contributing factors
   
   d. Generate recommendations:
      - Buy: Low risk (< 0.3)
      - Neutral: Medium risk (0.3-0.6)
      - Trim: High risk (0.6-0.8)
      - Sell: Very high risk (> 0.8)
      - Rotate: High risk in one sector, low in another

2. Output: Risk profiles with explainability
```

**Risk Score Calculation**:
```python
risk_score = (
    similarity_score * 0.5 +           # Semantic match
    sector_exposure * 0.2 +            # Sector alignment
    region_exposure * 0.2 +            # Geographic exposure
    financial_health_factor * 0.1      # Ability to absorb impact
)

# Financial health factor:
# - High market cap → lower risk (more resilient)
# - Low debt → lower risk
# - High FCF → lower risk
```

#### 4.2 Dashboard Visualization

**Streamlit Interface** (`risk_dashboard.py`):
```python
1. File Upload Widget:
   - Upload test results JSON
   - Transform to CompanyRiskProfile format
   
2. Risk Factors Widget:
   - Filter by sector, risk level, ticker
   - Search by company name
   - Display risk scores with color coding
   - Show top contributing legislation
   - Export to CSV/JSON
   
3. Sector Analysis:
   - Pie chart: Legislation impact by sector
   - Bar chart: Average risk score by sector
   - Filter by legislation type
   
4. Price Impact Visualization:
   - Scatter plot: Risk score vs. estimated price impact
   - Grouped by recommendation (buy/sell/trim/rotate)
   - Tooltips with company details
```

---

## Data Flow Examples

### Example 1: Single Filing Processing (Streamlit)

```
User uploads: AAPL_10-K_2024.html
    ↓
Stage 1: Parse
    - Extract sections, entities, metadata
    - Save: parsed/filings/AAPL/2024-11-01-10k.json
    ↓
Stage 1: Aggregate (if other AAPL filings exist)
    - Load all AAPL filings
    - Merge into unified knowledge graph
    - Save: aggregated/companies/AAPL.json
    ↓
Stage 2: Embeddings
    - Generate embeddings from aggregated data
    - Save: embeddings/AAPL_embedded.json
    ↓
Stage 3: VectorDB
    - Index embeddings in OpenSearch
    - Ready for similarity search
    ↓
Dashboard: Display results
```

### Example 2: Batch Processing (SageMaker)

```
Input: S&P 500 CSV with 500 tickers
    ↓
For each ticker (parallel processing):
    ↓
Stage 1: Parse & Aggregate
    - Load all filings for ticker from S3
    - Aggregate into knowledge graph
    - Save: aggregated/companies/{ticker}.json
    ↓
Stage 2: Embeddings
    - Generate embeddings
    - Save: embeddings/{ticker}_embedded.json
    ↓
Stage 3: VectorDB
    - Bulk index to OpenSearch
    - Checkpoint progress
    ↓
After all tickers:
    - Generate summary report
    - Verify all embeddings indexed
```

### Example 3: Risk Assessment Query

```
User queries: "Which companies are at risk from EU AI Act?"
    ↓
1. Load EU AI Act regulation embedding
    ↓
2. Query OpenSearch:
    - Vector similarity search
    - Filter: Technology sector (optional)
    - Top 50 matches
    ↓
3. Risk Scoring:
    - Calculate risk scores for each company
    - Extract contributing sentences
    - Generate recommendations
    ↓
4. Dashboard:
    - Display risk scores table
    - Show sector distribution
    - Export results
```

---

## Storage Architecture

### S3 Bucket Structure

```
s3://datathon-2025-bucket/
├── input/
│   ├── filings/
│   │   ├── AAPL/
│   │   │   ├── 2024-11-01-10k.html
│   │   │   ├── 2024-08-01-10q.html
│   │   │   └── 2024-09-15-8k.html
│   │   └── MSFT/...
│   ├── regulations/
│   │   ├── EU_AI_ACT_2024.html
│   │   └── US_TARIFF_2024.html
│   └── financial/
│       └── sp500_composition.csv
│
├── parsed/
│   ├── filings/
│   │   ├── AAPL/
│   │   │   ├── 2024-11-01-10k.json
│   │   │   ├── 2024-08-01-10q.json
│   │   │   └── 2024-09-15-8k.json
│   │   └── MSFT/...
│   ├── regulations/
│   │   ├── EU_AI_ACT_2024.json
│   │   └── US_TARIFF_2024.json
│   └── financial/
│       └── sp500_composition.json
│
├── aggregated/
│   ├── companies/
│   │   ├── AAPL.json  # Unified knowledge graph
│   │   └── MSFT.json
│   └── regulations/
│       ├── EU_AI_ACT_2024.json
│       └── US_TARIFF_2024.json
│
├── embeddings/
│   ├── companies/
│   │   ├── AAPL_embedded.json
│   │   └── MSFT_embedded.json
│   └── regulations/
│       ├── EU_AI_ACT_2024_embedded.json
│       └── US_TARIFF_2024_embedded.json
│
└── cache/
    └── yahoo_finance/
        ├── AAPL.json  # Cached external data (7-day TTL)
        └── MSFT.json
```

### OpenSearch Index Structure

**Index**: `company_embeddings`

**Mapping**:
```json
{
  "mappings": {
    "properties": {
      "embedding": {
        "type": "knn_vector",
        "dimension": 384,
        "method": {
          "name": "hnsw",
          "space_type": "cosinesimil",
          "engine": "nmslib"
        }
      },
      "ticker": {"type": "keyword"},
      "company_name": {"type": "text"},
      "sector": {"type": "keyword"},
      "chunk_id": {"type": "integer"},
      "text": {"type": "text"},
      "section": {"type": "keyword"},
      "section_title": {"type": "text"},
      "filing_date": {"type": "date"},
      "source_filings": {"type": "keyword"},
      "indexed_at": {"type": "date"}
    }
  }
}
```

---

## Technologies & Dependencies

### Core Libraries
- **Python 3.11+**: Runtime environment
- **Transformers 4.33.3**: HuggingFace model loading (`llmware/industry-bert-sec-v0.1`)
- **PyTorch 2.1.0**: Deep learning framework (from base Docker image)
- **spaCy 3.7+**: Named entity recognition
- **BeautifulSoup4 + lxml**: HTML/XML parsing
- **pandas**: Data manipulation
- **opensearch-py 2.0+**: OpenSearch client
- **boto3**: AWS SDK (S3, SageMaker, STS)
- **requests-aws4auth**: IAM authentication for OpenSearch

### AWS Services
- **S3**: Document storage and processed data
- **SageMaker**: Batch processing jobs (Docker container)
- **OpenSearch**: Vector database for embeddings
- **ECR**: Docker image registry
- **Lambda**: Event-driven triggers (future)
- **Step Functions**: Pipeline orchestration (future)

### Local Development
- **ChromaDB**: Local vector database alternative
- **Streamlit**: Interactive dashboard
- **python-dotenv**: Environment variable management

---

## Execution Modes

### 1. Local Development Mode

**Streamlit Dashboard**:
```bash
streamlit run dashboard.py
```
- Upload files via UI
- Process single files
- View results inline
- Test mode (dry run) available

**Command Line**:
```bash
python test_aapl_legislation_similarity.py --ticker AAPL
```
- Test risk scoring for specific ticker
- Local OpenSearch or ChromaDB

### 2. Batch Processing Mode

**SageMaker Processing Job**:
```bash
# Build and push Docker image
./scripts/build_and_push_manual.sh

# Run batch embedding for all tickers
python scripts/batch_embed_all_tickers.py \
    --s3-csv-key input/financial/sp500_composition.csv \
    --opensearch-endpoint https://search-xxx.es.amazonaws.com \
    --opensearch-index company_embeddings \
    --model-name llmware/industry-bert-sec-v0.1 \
    --use-contextual-enrichment \
    --sentence-level-chunking
```

**Features**:
- Checkpoint/resume capability
- Error handling and retry logic
- Progress logging to CloudWatch
- Parallel processing support

### 3. AWS Lambda Mode (Future)

**Trigger**: S3 object creation event
```python
# Lambda handler automatically processes new files
# Event: S3 upload → Lambda → Pipeline → OpenSearch
```

---

## Performance Characteristics

### Processing Times (Approximate)

| Stage | Single Filing | Batch (500 companies) |
|-------|--------------|------------------------|
| Parse | 2-5 seconds | 10-15 minutes |
| Aggregate | 3-8 seconds | 20-30 minutes |
| Embeddings | 10-30 seconds | 2-4 hours |
| VectorDB Index | 1-2 seconds | 30-60 minutes |
| **Total** | **15-45 seconds** | **3-6 hours** |

### Resource Requirements

**Local Development**:
- CPU: 4+ cores recommended
- RAM: 8GB minimum, 16GB recommended
- Storage: 10GB for models and data

**SageMaker Batch Processing**:
- Instance: `ml.m5.xlarge` (4 vCPU, 16GB RAM) minimum
- GPU: Optional (faster embeddings with `ml.g4dn.xlarge`)
- Storage: 50GB EBS volume for models and data

**OpenSearch**:
- Instance: `t3.small` (2 vCPU, 2GB RAM) for MVP
- Production: `r6g.large` (2 vCPU, 16GB RAM) for 500+ companies

---

## Error Handling & Resilience

### Checkpointing
- Batch processing saves progress after each ticker
- Resume from last successful ticker on failure
- Checkpoint file: `output/batch_embedding_checkpoint.json`

### Error Recovery
- **Parse failures**: Log error, skip file, continue
- **Embedding failures**: Retry with exponential backoff
- **OpenSearch failures**: Retry up to 3 times, then skip
- **Network timeouts**: Automatic retry with longer timeout

### Validation
- **Input validation**: File type, format, required fields
- **Output validation**: Embedding dimensions, JSON schema
- **OpenSearch validation**: Index existence, mapping compatibility

---

## Future Enhancements

### Phase 2 Features
1. **Real-time Updates**: Lambda triggers for new filings
2. **Polymarket Integration**: Predictive market data for risk scoring
3. **Multi-language Support**: EU regulations in multiple languages
4. **Advanced Graph**: Full knowledge graph with Neo4j
5. **Fine-tuning**: Domain-specific embedding model training

### Performance Optimizations
1. **Parallel Processing**: Multi-threaded embedding generation
2. **Caching**: Embedding cache for unchanged filings
3. **Incremental Updates**: Only process new/changed filings
4. **GPU Acceleration**: SageMaker GPU instances for faster embeddings

---

## See Also

- [Pipeline Implementation](../src/pipeline/)
- [Streamlit Dashboard](../risk_dashboard.py)
- [Batch Embedding Script](../scripts/batch_embed_all_tickers.py)
- [AWS Setup Guide](./AWS_SETUP_GUIDE.md)
- [Docker Setup](../scripts/DOCKER_SETUP.md)

