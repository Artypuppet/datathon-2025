# PolyFinances Datathon 2025 - Regulatory Risk Tracking

Comprehensive system for tracking regulatory risk across multiple jurisdictions using AI-powered document analysis.

## 🎯 Project Overview

Parse SEC filings and legislation, extract risk factors, and visualize regulatory impact on company portfolios.

**Current Status**: MVP Pipeline Complete ✅

## ⚡ Quick Start

```bash
# 1. Setup environment
conda env create -f environment-local.yml
conda activate datathon-local
./install_pytorch_gpu.sh
pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl

# 2. Test parsers
python test_parsers_manual.py

# 3. Run dashboard
streamlit run dashboard.py

# 4. Parse dataset
python parse_batch.py --local --input data/initial-dataset/ --output output/
```

**Full Setup**: See [`docs/QUICK_START.md`](docs/QUICK_START.md)

## 📊 What's Implemented

### ✅ MVP Complete

- **3 Parser Types**: CSV, SEC filings (10-K/10-Q), legislation (EU/US/CN)
- **S3 Integration**: Full storage operations with batch processing
- **Pipeline System**: Stage-based processing with orchestration
- **Streamlit Dashboard**: File upload and processing interface
- **45 Unit Tests**: 100% passing
- **Complete Documentation**: 7 comprehensive guides

### 🔄 Next Phase

- **Embeddings**: Sentence-transformers integration
- **Vector Database**: OpenSearch/ChromaDB setup
- **Risk Scoring**: Multi-factor analysis
- **AWS Deployment**: Lambda + S3 triggers

## 📁 Project Structure

```
datathon-2025/
├── docs/                   # Documentation (7 guides)
├── src/
│   ├── parsers/           # Parser implementations
│   ├── pipeline/          # Processing pipeline
│   ├── dashboard/         # Streamlit UI
│   ├── lambda/            # AWS Lambda handler
│   └── utils/             # Utilities (S3 client)
├── tests/unit/            # Unit tests (45 tests)
├── examples/              # Usage examples
├── dashboard.py           # Main dashboard app
├── parse_batch.py         # Batch processing CLI
└── test_*.py             # Test scripts
```

## 🚀 Key Features

### Smart Parsing
- Auto-detect file types (CSV, HTML, XML)
- Multi-jurisdiction support (EU, US, CN)
- Language detection
- Robust metadata extraction

### S3 Integration
- Upload/download files
- Direct memory operations
- Batch processing
- JSON serialization

### Pipeline System
- Stage-based architecture
- Dry run testing
- Error handling
- Status reporting

### Dashboard
- File upload interface
- Real-time processing
- Results display
- Test mode

## 📚 Documentation

### Essential Guides
- [`docs/QUICK_START.md`](docs/QUICK_START.md) - Get started in 5 minutes
- [`docs/AWS_SETUP_GUIDE.md`](docs/AWS_SETUP_GUIDE.md) - AWS credentials and S3
- [`docs/PIPELINE_OVERVIEW.md`](docs/PIPELINE_OVERVIEW.md) - Pipeline architecture
- [`docs/TESTING.md`](docs/TESTING.md) - Testing guide
- [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) - Common issues

### Quick References
- [`QUICK_REFERENCE.md`](QUICK_REFERENCE.md) - Command cheat sheet
- [`PROJECT_STATUS.md`](PROJECT_STATUS.md) - Current status
- [`MVP_COMPLETE.md`](MVP_COMPLETE.md) - MVP summary

## 🧪 Testing

```bash
# All tests
pytest tests/unit/ -v

# Manual test
python test_parsers_manual.py

# Pipeline test
python test_pipeline.py

# S3 connection
python test_s3_connection.py

# Automated runner
./run_tests.sh --all
```

**Test Coverage**: 45/45 passing (100%)

## 💻 Usage Examples

### Upload via Dashboard
```bash
streamlit run dashboard.py
# Upload file, view results inline
```

### Parse Local Files
```bash
python parse_batch.py --local --input data/ --output output/
```

### Parse from S3
```bash
python parse_batch.py --s3 --input-prefix input/financial/
```

### Use Pipeline Programmatically
```python
from src.pipeline import PipelineOrchestrator, PipelineConfig

config = PipelineConfig()
orch = PipelineOrchestrator(config=config)

result = orch.execute({'file_key': 'input/file.csv'})
print(result)
```

## 🏗️ Architecture

```
User uploads file
      ↓
S3 storage (input/)
      ↓
Pipeline Orchestrator
      ↓
Stage 1: Parse
  ├─ Detect file type
  ├─ Extract metadata
  └─ Output JSON
      ↓
Stage 2: Embeddings (Future)
  └─ Generate vectors
      ↓
Stage 3: Database (Future)
  └─ Update vector DB
      ↓
Results visualization
```

## 📦 Technology Stack

- **Python 3.11**: Core language
- **BeautifulSoup4/lxml**: HTML/XML parsing
- **langdetect**: Language detection
- **spaCy**: NLP processing
- **sentence-transformers**: Embeddings (future)
- **boto3**: AWS S3 integration
- **Streamlit**: Dashboard UI
- **pytest**: Testing framework

## 🔧 Configuration

Environment variables (`.env`):
```bash
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1
S3_BUCKET=your-bucket-name
```

## 📈 Current Capabilities

✅ Parse CSV financial data  
✅ Parse SEC 10-K/10-Q filings  
✅ Parse legislation (EU/US/CN)  
✅ Upload to S3  
✅ Download from S3  
✅ Process via pipeline  
✅ Dashboard upload interface  
✅ Test mode support  
✅ Error handling  
✅ Comprehensive logging  

## 🎯 Roadmap

### Phase 1: MVP ✅ Complete
- Parsers (3 types)
- S3 integration
- Pipeline MVP
- Dashboard

### Phase 2: Embeddings 🚧 Next
- Sentence-transformers
- Vector generation
- ChromaDB/OpenSearch
- Batch optimization

### Phase 3: Risk Scoring 📋 Planned
- Risk factor extraction
- Multi-factor analysis
- Temporal analysis
- Impact scoring

### Phase 4: Deployment 📋 Planned
- Lambda deployment
- S3 triggers
- Monitoring/alerts
- Scale optimization

## 🤝 Contributing

See [Style Guide](.cursor/STYLE_GUIDE.md) for code standards.

**Key Rules**:
- **NO EMOJIS** in code or docs
- Use text markers: [OK], [ERROR], [WARN]
- Follow PEP8
- Write tests for new features
- Document changes

## 📄 License

Datathon 2025 Project

## 🔗 Resources

- [Challenge Description](.cursor/01_challenge.md)
- [Architecture](.cursor/02_architecture.md)
- [MVP Implementation](.cursor/03_mvp_implementation.md)
- [AWS S3 Integration](S3_INTEGRATION.md)
- [Pipeline Overview](docs/PIPELINE_OVERVIEW.md)

---

**Status**: MVP Complete | **Tests**: 45/45 Passing | **Next**: Embeddings Phase

