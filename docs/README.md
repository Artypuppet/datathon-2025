# Documentation

Complete documentation for the PolyFinances Datathon 2025 project.

## Getting Started

- **[Quick Start Guide](QUICK_START.md)** - Get up and running in 5 minutes
- **[Setup Environment](../.cursor/04_setup_environment.md)** - Detailed environment setup
- **[AWS Setup Guide](AWS_SETUP_GUIDE.md)** - AWS credentials and S3 configuration
- **[Pipeline Overview](PIPELINE_OVERVIEW.md)** - Pipeline architecture and usage
- **[Dashboard Guide](RUN_DASHBOARD.md)** - Running the Streamlit dashboard
- **[Testing Guide](TESTING.md)** - How to run and write tests
- **[Troubleshooting Guide](TROUBLESHOOTING.md)** - Common issues and solutions

## Core Documentation

### Project Overview
- **[Challenge Description](../.cursor/01_challenge.md)** - Project goals and constraints
- **[Architecture](../.cursor/02_architecture.md)** - System design and AWS services
- **[MVP Implementation](../.cursor/03_mvp_implementation.md)** - MVP scope and steps

### Development
- **[Code Style](../.cursor/05_code_style.md)** - Coding standards
- **[Style Guide](../.cursor/STYLE_GUIDE.md)** - Quick reference
- **[Testing Strategy](../.cursor/references/testing_strategy.md)** - Testing approach

## Module Documentation

### Parsing Module (Current)
- **[Parser Implementation](../PARSERS_IMPLEMENTED.md)** - Parser details and usage
- **[S3 Integration](../S3_INTEGRATION.md)** - Complete S3 guide
- **[S3 Workflow Summary](../S3_WORKFLOW_SUMMARY.md)** - Quick S3 overview
- **[Testing Guide](TESTING.md)** - How to test parsers

### Reference
- **[Data Schemas](../.cursor/references/data_schemas.md)** - JSON structures
- **[Glossary](../.cursor/references/glossary.md)** - Terms and acronyms
- **[Decisions Log](../.cursor/references/decisions_log.md)** - Technical decisions
- **[Language Detection](../.cursor/references/language_detection.md)** - Language/jurisdiction detection
- **[Parser Design](../.cursor/references/parser_design.md)** - Parser architecture
- **[Local Testing](../.cursor/references/local_testing_workflow.md)** - Local vs AWS testing

## Quick Links

### Common Tasks

**Setup:**
```bash
conda env create -f environment-local.yml
conda activate datathon-local
./install_pytorch_gpu.sh
python -m spacy download en_core_web_sm
```

**Test:**
```bash
python test_parsers_manual.py
pytest tests/unit/ -v
```

**Parse:**
```bash
python parse_batch.py --local --input data/ --output output/
```

**S3:**
```bash
cp .env.example .env
# Edit .env with credentials
python parse_batch.py --s3 --input-prefix input/
```

### File Structure

```
datathon-2025/
├── docs/                       # This directory
│   ├── README.md              # This file
│   ├── QUICK_START.md         # Quick start guide
│   └── TESTING.md             # Testing guide
├── .cursor/                    # Project context
│   ├── 00_README.md           # Project overview
│   ├── 01_challenge.md        # Challenge description
│   ├── 02_architecture.md     # System architecture
│   ├── 03_mvp_implementation.md
│   ├── 04_setup_environment.md
│   ├── 05_code_style.md
│   ├── STYLE_GUIDE.md
│   └── references/            # Detailed references
├── src/                        # Source code
│   ├── parsers/               # Parser implementations
│   └── utils/                 # Utilities (S3, etc.)
├── tests/                      # Test suite
│   └── unit/                  # Unit tests
├── examples/                   # Usage examples
└── data/                       # Input data
```

## Documentation by Role

### For Developers

1. [Quick Start](QUICK_START.md) - Setup and basics
2. [Code Style](../.cursor/05_code_style.md) - Coding standards
3. [Parser Implementation](../PARSERS_IMPLEMENTED.md) - How parsers work
4. [Testing Guide](TESTING.md) - Running tests

### For Data Scientists

1. [Architecture](../.cursor/02_architecture.md) - System overview
2. [MVP Implementation](../.cursor/03_mvp_implementation.md) - What we're building
3. [Data Schemas](../.cursor/references/data_schemas.md) - Data formats
4. [Local Testing](../.cursor/references/local_testing_workflow.md) - Local vs AWS

### For DevOps

1. [Setup Environment](../.cursor/04_setup_environment.md) - Environment setup
2. [S3 Integration](../S3_INTEGRATION.md) - S3 configuration
3. [Architecture](../.cursor/02_architecture.md) - AWS services
4. [Testing Strategy](../.cursor/references/testing_strategy.md) - CI/CD testing

## Status

| Module | Status | Documentation | Tests |
|--------|--------|---------------|-------|
| Parsers | [COMPLETE] | [OK] | 40+ tests |
| S3 Integration | [COMPLETE] | [OK] | Examples |
| Feature Extraction | [TODO] | - | - |
| Risk Scoring | [TODO] | - | - |
| Dashboard | [TODO] | - | - |

## Contributing

1. **Read Style Guide**: [STYLE_GUIDE.md](../.cursor/STYLE_GUIDE.md)
2. **Write Tests**: Follow [Testing Guide](TESTING.md)
3. **Document Changes**: Update relevant docs
4. **No Emojis**: Use text markers ([OK], [ERROR], etc.)

## Need Help?

1. Check [Quick Start](QUICK_START.md) for setup issues
2. Review [Testing Guide](TESTING.md) for test issues
3. Read [S3 Integration](../S3_INTEGRATION.md) for S3 issues
4. Check error messages and logs
5. Review examples in `examples/` folder

## Next Steps

After completing parser setup:

1. **Verify Tests**: `python test_parsers_manual.py`
2. **Parse Sample Data**: `python parse_batch.py --local --input data/`
3. **Set up S3** (optional): Follow [S3 Integration](../S3_INTEGRATION.md)
4. **Next Module**: Feature extraction and embeddings

## Documentation Standards

When writing documentation:

- **[OK]** for success/completion
- **[ERROR]** for errors
- **[WARN]** for warnings
- **[INFO]** for information
- **[TODO]** for pending tasks
- **No emojis** in any documentation

Use code blocks with language tags:
\`\`\`bash
command here
\`\`\`

\`\`\`python
code here
\`\`\`

## Changelog

- **2024-11-01**: Initial documentation structure
- **2024-11-01**: Parser module complete with S3 integration
- **2024-11-01**: Testing guide and quick start added

---

**Current Status**: Parser module complete, ready for feature extraction module.

