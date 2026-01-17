#!/bin/bash
# Example usage of batch embedding script

# Example 1: Process specific tickers (testing)
python scripts/batch_embed_all_tickers.py \
    --tickers AAPL MSFT NVDA GOOGL \
    --max-tickers 4 \
    --opensearch-endpoint "${OPENSEARCH_ENDPOINT:-https://your-endpoint.es.amazonaws.com}" \
    --output-results output/batch_embedding_results.json

# Example 2: Process from S&P 500 CSV (local)
python scripts/batch_embed_all_tickers.py \
    --sp500-csv data/initial-dataset/2025-08-15_composition_sp500.csv \
    --max-tickers 10 \
    --opensearch-endpoint "${OPENSEARCH_ENDPOINT:-https://your-endpoint.es.amazonaws.com}" \
    --use-contextual-enrichment \
    --checkpoint-path output/checkpoint.json

# Example 3: Process from S3 CSV
python scripts/batch_embed_all_tickers.py \
    --s3-csv-key data/2025-08-15_composition_sp500.csv \
    --opensearch-endpoint "${OPENSEARCH_ENDPOINT:-https://your-endpoint.es.amazonaws.com}" \
    --checkpoint-path /tmp/checkpoint.json \
    --s3-results-key results/batch_embedding_results.json

# Example 4: Resume from checkpoint
python scripts/batch_embed_all_tickers.py \
    --sp500-csv data/initial-dataset/2025-08-15_composition_sp500.csv \
    --opensearch-endpoint "${OPENSEARCH_ENDPOINT:-https://your-endpoint.es.amazonaws.com}" \
    --checkpoint-path output/checkpoint.json \
    --output-results output/batch_embedding_results.json

# Example 5: Fresh start (no resume)
python scripts/batch_embed_all_tickers.py \
    --sp500-csv data/initial-dataset/2025-08-15_composition_sp500.csv \
    --opensearch-endpoint "${OPENSEARCH_ENDPOINT:-https://your-endpoint.es.amazonaws.com}" \
    --no-resume \
    --output-results output/batch_embedding_results.json

