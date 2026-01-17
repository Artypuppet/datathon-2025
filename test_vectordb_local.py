"""
End-to-end test for VectorDB with ChromaDB (local testing).

Tests the complete pipeline:
1. Parse and aggregate AAPL filings
2. Generate embeddings
3. Store in ChromaDB (local)
4. Store legislation embedding
5. Analyze similarity and impact
6. Display results with explainability
"""

import logging
import json
import argparse
from pathlib import Path
import numpy as np

from src.pipeline import PipelineOrchestrator, PipelineConfig
from src.vectordb import get_vectordb_client, LegislationImpactAnalyzer
from src.embeddings.embedding_generator import EmbeddingGenerator
from src.utils import get_s3_client

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
)
logger = logging.getLogger(__name__)


def create_tariff_legislation() -> str:
    """Create test legislation text about smartphone tariffs."""
    return """The United States Congress hereby imposes a tariff of 50% on all smartphones 
    that are assembled or manufactured outside the United States. This tariff applies to 
    all finished smartphone products imported into the United States, regardless of the 
    country of origin. The tariff is designed to incentivize domestic manufacturing and 
    assembly of smartphones within the United States. Companies importing smartphones 
    manufactured or assembled in countries including but not limited to China, Vietnam, 
    Taiwan, India, and other foreign manufacturing locations will be subject to this tariff."""


def setup_logging(log_level: str = "INFO", log_file: str = None):
    """Configure logging for the test."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    handlers = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
        handlers=handlers,
        force=True
    )


def print_section(title: str, content: str = ""):
    """Print a formatted section header."""
    print("\n" + "="*80)
    print(title)
    print("="*80)
    if content:
        print(content)


def main():
    parser = argparse.ArgumentParser(description='Test VectorDB locally with ChromaDB')
    parser.add_argument('--ticker', type=str, default='AAPL',
                       help='Company ticker to test (default: AAPL)')
    parser.add_argument('--skip-pipeline', action='store_true',
                       help='Skip pipeline execution, use existing S3 data')
    parser.add_argument('--skip-embeddings', action='store_true',
                       help='Skip embedding generation, use existing embeddings')
    parser.add_argument('--clear-chroma', action='store_true',
                       help='Clear existing ChromaDB data before test')
    parser.add_argument('--log-level', type=str, default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level (default: INFO)')
    parser.add_argument('--log-file', type=str, default=None,
                       help='Optional log file path')
    
    args = parser.parse_args()
    
    setup_logging(args.log_level, args.log_file)
    
    print_section("VECTORDB LOCAL TEST", f"Testing with {args.ticker} using ChromaDB")
    
    ticker = args.ticker
    legislation_id = "US_SMARTPHONE_TARIFF_2025"
    
    # Step 1: Run Pipeline (Parse + Aggregate + Embed)
    print_section("STEP 1: Running Pipeline", f"Processing {ticker} filings...")
    
    if not args.skip_pipeline:
        logger.info(f"[INFO] Running pipeline for {ticker}")
        
        # Configure pipeline to enable embeddings
        config = PipelineConfig()
        config.skip_embeddings = False  # Enable embeddings
        config.dry_run = False
        
        # Initialize orchestrator
        orchestrator = PipelineOrchestrator(config=config)
        
        # Find a filing for the ticker
        s3_client = get_s3_client()
        files = s3_client.list_files(prefix=f"input/filings/{ticker}/")
        
        if not files:
            logger.error(f"[ERROR] No filings found for {ticker}")
            return
        
        # Use first filing found (orchestrator will process all filings for the ticker)
        test_file = files[0]
        logger.info(f"[INFO] Found filing: {test_file}")
        
        # Execute pipeline
        event = {
            'file_key': test_file,
            'ticker': ticker
        }
        
        result = orchestrator.execute(event)
        
        if result.get('status') != 'success':
            logger.error(f"[ERROR] Pipeline failed: {result}")
            return
        
        logger.info("[OK] Pipeline completed successfully")
        logger.info(f"  - Aggregated: {result.get('stages', {}).get('aggregate', 'N/A')}")
        logger.info(f"  - Embeddings: {result.get('stages', {}).get('embeddings', 'N/A')}")
        logger.info(f"  - VectorDB: {result.get('stages', {}).get('vectordb', 'N/A')}")
        
        aggregated_key = result.get('aggregated_key')
        embedding_key = result.get('embedding_key')
        
        if not embedding_key:
            logger.error("[ERROR] No embedding_key in pipeline result")
            return
    else:
        logger.info("[INFO] Skipping pipeline, using existing data")
        embedding_key = f"embeddings/{ticker}_embedded.json"
        aggregated_key = f"aggregated/companies/{ticker}.json"
    
    # Step 2: Initialize ChromaDB
    print_section("STEP 2: Initializing ChromaDB", "Setting up local vector database...")
    
    try:
        vectordb = get_vectordb_client(backend='chroma')
        logger.info("[OK] ChromaDB initialized")
        
        if args.clear_chroma:
            logger.info("[INFO] Clearing existing ChromaDB data...")
            # ChromaDB doesn't have a simple "clear all" - we'll delete by ticker
            try:
                vectordb.delete_company_embeddings(ticker)
                logger.info(f"[OK] Deleted existing embeddings for {ticker}")
            except Exception as e:
                logger.warning(f"[WARN] Could not clear existing data: {e}")
    except Exception as e:
        logger.error(f"[ERROR] Failed to initialize ChromaDB: {e}")
        logger.error("[ERROR] Make sure chromadb is installed: pip install chromadb==0.4.22")
        return
    
    # Step 3: Load and Store Company Embeddings
    print_section("STEP 3: Storing Company Embeddings", f"Loading embeddings for {ticker}...")
    
    try:
        s3_client = get_s3_client()
        embeddings_data = s3_client.read_json(embedding_key)
        chunks = embeddings_data.get('chunks', [])
        
        if not chunks:
            logger.error("[ERROR] No chunks in embeddings data")
            logger.error(f"[ERROR] Keys in embeddings_data: {list(embeddings_data.keys())}")
            return
        
        logger.info(f"[INFO] Loaded {len(chunks)} chunks from S3")
        
        # Verify chunks have embeddings
        chunks_with_embeddings = [c for c in chunks if 'embedding' in c]
        if len(chunks_with_embeddings) < len(chunks):
            logger.warning(f"[WARN] Only {len(chunks_with_embeddings)}/{len(chunks)} chunks have embeddings")
        
        # Get company metadata
        ticker_from_chunk = chunks[0].get('ticker') or ticker
        company_name = chunks[0].get('company_name', ticker)
        
        logger.info(f"[INFO] Storing embeddings for {ticker_from_chunk} ({company_name})")
        
        # Store in ChromaDB (will use ChromaDB since OpenSearch not configured)
        stored_count = vectordb.store_company_embeddings(
            ticker=ticker_from_chunk,
            company_name=company_name,
            chunks=chunks_with_embeddings  # Only store chunks with embeddings
        )
        
        logger.info(f"[OK] Stored {stored_count} embeddings in ChromaDB")
        
    except Exception as e:
        logger.error(f"[ERROR] Failed to store company embeddings: {e}", exc_info=True)
        return
    
    # Step 4: Generate and Store Legislation Embedding
    print_section("STEP 4: Storing Legislation Embedding", "Generating embedding for tariff legislation...")
    
    try:
        legislation_text = create_tariff_legislation()
        
        # Generate embedding
        embedding_gen = EmbeddingGenerator()
        logger.info("[INFO] Generating legislation embedding...")
        legislation_embedding = embedding_gen.generate_embeddings([legislation_text])[0]
        logger.info(f"[OK] Generated embedding: shape {legislation_embedding.shape}")
        
        # Store in ChromaDB
        doc_id = vectordb.store_legislation_embedding(
            legislation_id=legislation_id,
            legislation_text=legislation_text,
            embedding=legislation_embedding,
            metadata={
                'jurisdiction': 'US',
                'title': 'Smartphone Tariff Legislation',
                'effective_date': '2025-01-01'
            }
        )
        
        logger.info(f"[OK] Stored legislation embedding: {doc_id}")
        
    except Exception as e:
        logger.error(f"[ERROR] Failed to store legislation embedding: {e}", exc_info=True)
        return
    
    # Step 5: Analyze Impact
    print_section("STEP 5: Analyzing Impact", f"Finding similarity between legislation and {ticker} filings...")
    
    try:
        analyzer = LegislationImpactAnalyzer(
            vectordb_client=vectordb,
            similarity_threshold=0.7,
            top_k=50
        )
        
        impact_result = analyzer.analyze_impact(
            legislation_id=legislation_id,
            legislation_embedding=legislation_embedding,
            ticker=ticker_from_chunk,
            company_name=company_name
        )
        
        logger.info("[OK] Impact analysis complete")
        
    except Exception as e:
        logger.error(f"[ERROR] Impact analysis failed: {e}", exc_info=True)
        return
    
    # Step 6: Display Results
    print_section("STEP 6: RESULTS", "Impact Analysis Summary")
    
    print(f"\nCompany: {impact_result['company_name']} ({impact_result['ticker']})")
    print(f"Legislation: {impact_result['legislation_id']}")
    print(f"\n{'='*80}")
    print(f"Overall Impact Score: {impact_result['impact_score']:.3f} / 1.0")
    print(f"Risk Level: {impact_result['risk_level'].upper()}")
    print(f"Total Matching Sentences: {impact_result['total_matches']}")
    print(f"Similarity Threshold: {impact_result['similarity_threshold']:.2f}")
    
    # Statistics
    stats = impact_result['statistics']
    print(f"\nStatistics:")
    print(f"  Average Similarity: {stats['avg_similarity']:.3f}")
    print(f"  Maximum Similarity: {stats['max_similarity']:.3f}")
    print(f"  Minimum Similarity: {stats['min_similarity']:.3f}")
    
    # By section type
    if stats.get('by_section_type'):
        print(f"\nMatches by Section Type:")
        for section_type, section_stats in stats['by_section_type'].items():
            print(f"  {section_type}:")
            print(f"    Count: {section_stats['count']}")
            print(f"    Avg Similarity: {section_stats['avg_similarity']:.3f}")
            print(f"    Max Similarity: {section_stats['max_similarity']:.3f}")
    
    # By filing type
    if stats.get('by_filing_type'):
        print(f"\nMatches by Filing Type:")
        for filing_type, filing_stats in stats['by_filing_type'].items():
            print(f"  {filing_type}:")
            print(f"    Count: {filing_stats['count']}")
            print(f"    Avg Similarity: {filing_stats['avg_similarity']:.3f}")
    
    # Top matches
    print(f"\n{'='*80}")
    print(f"Top 10 Most Relevant Sentences:")
    print(f"{'='*80}")
    
    for i, match in enumerate(impact_result['matched_sentences'][:10], 1):
        print(f"\n{i}. {match['section_title']} (similarity: {match['similarity']:.3f})")
        print(f"   Section: {match['section_type']} | Filing: {match['filing_type']} from {match['filing_date']}")
        if 'sentence_position' in match:
            print(f"   Position: Sentence {match['sentence_position']} in section")
        sentence = match['original_sentence']
        if len(sentence) > 300:
            sentence = sentence[:300] + "..."
        print(f"   Sentence: \"{sentence}\"")
    
    # Explanation
    print(f"\n{'='*80}")
    print("EXPLANATION:")
    print(f"{'='*80}")
    print(impact_result['explanation'])
    
    # Save results
    output_file = Path(f"output/{ticker}_vectordb_test_results.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(impact_result, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*80}")
    print(f"[OK] Results saved to: {output_file}")
    print(f"{'='*80}")
    
    print_section("TEST COMPLETE", f"Successfully tested VectorDB with ChromaDB for {ticker}")
    print("\n[SUCCESS] All steps completed successfully!")
    print(f"  - Stored {stored_count} company embeddings")
    print(f"  - Stored 1 legislation embedding")
    print(f"  - Found {impact_result['total_matches']} matching sentences")
    print(f"  - Impact score: {impact_result['impact_score']:.3f} ({impact_result['risk_level']} risk)")


if __name__ == '__main__':
    main()

