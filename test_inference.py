"""
Test script for legislation impact inference using vector database.

Tests:
1. Store company embeddings in vector DB
2. Store legislation embedding
3. Query for similar sentences
4. Calculate impact scores
5. Generate explainability reports
"""

import logging
import json
import numpy as np
import argparse
from pathlib import Path

from src.vectordb import get_vectordb_client, LegislationImpactAnalyzer
from src.embeddings.embedding_generator import EmbeddingGenerator
from src.utils import get_s3_client

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
)
logger = logging.getLogger(__name__)


def create_test_legislation_text() -> str:
    """Create test legislation text about smartphone tariffs."""
    return """The United States Congress hereby imposes a tariff of 50% on all smartphones 
    that are assembled or manufactured outside the United States. This tariff applies to 
    all finished smartphone products imported into the United States, regardless of the 
    country of origin. The tariff is designed to incentivize domestic manufacturing and 
    assembly of smartphones within the United States. Companies importing smartphones 
    manufactured or assembled in countries including but not limited to China, Vietnam, 
    Taiwan, India, and other foreign manufacturing locations will be subject to this tariff."""


def main():
    parser = argparse.ArgumentParser(description='Test legislation impact inference')
    parser.add_argument('--ticker', type=str, default='AAPL',
                       help='Company ticker to analyze (default: AAPL)')
    parser.add_argument('--legislation-id', type=str, default='US_SMARTPHONE_TARIFF_2025',
                       help='Legislation identifier')
    parser.add_argument('--similarity-threshold', type=float, default=0.7,
                       help='Minimum similarity threshold (default: 0.7)')
    parser.add_argument('--top-k', type=int, default=50,
                       help='Number of top matches to retrieve (default: 50)')
    parser.add_argument('--backend', type=str, default='auto',
                       choices=['auto', 'chroma', 'opensearch'],
                       help='Vector DB backend (default: auto)')
    parser.add_argument('--skip-embeddings', action='store_true',
                       help='Skip generating embeddings, use existing')
    parser.add_argument('--embeddings-key', type=str,
                       help='S3 key to existing embeddings JSON')
    
    args = parser.parse_args()
    
    logger.info("="*80)
    logger.info("LEGISLATION IMPACT INFERENCE TEST")
    logger.info("="*80)
    
    # Step 1: Get or generate legislation embedding
    logger.info("\n[STEP 1] Preparing legislation embedding...")
    
    legislation_text = create_test_legislation_text()
    legislation_id = args.legislation_id
    
    if args.skip_embeddings and args.embeddings_key:
        logger.info(f"[INFO] Loading legislation embedding from {args.embeddings_key}")
        # Would load from S3, but for now generate fresh
        skip_legislation_embedding = False
    else:
        skip_legislation_embedding = False
    
    if not skip_legislation_embedding:
        # Generate legislation embedding
        embedding_gen = EmbeddingGenerator()
        logger.info("[INFO] Generating legislation embedding...")
        legislation_embedding = embedding_gen.generate_embeddings([legislation_text])[0]
        logger.info(f"[OK] Generated legislation embedding: shape {legislation_embedding.shape}")
    
    # Step 2: Initialize VectorDB and store legislation
    logger.info("\n[STEP 2] Storing legislation in VectorDB...")
    
    vectordb = get_vectordb_client(backend=args.backend)
    
    # Store legislation embedding
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
    logger.info(f"[OK] Stored legislation: {doc_id}")
    
    # Step 3: Load company embeddings from S3 (or pipeline output)
    logger.info(f"\n[STEP 3] Loading company embeddings for {args.ticker}...")
    
    s3_client = get_s3_client()
    embedding_key = args.embeddings_key or f"embeddings/{args.ticker}_embedded.json"
    
    try:
        embeddings_data = s3_client.read_json(embedding_key)
        chunks = embeddings_data.get('chunks', [])
        logger.info(f"[OK] Loaded {len(chunks)} chunks from {embedding_key}")
    except Exception as e:
        logger.error(f"[ERROR] Failed to load embeddings: {e}")
        logger.info("[INFO] You may need to run the pipeline first to generate embeddings")
        return
    
    # Step 4: Store company embeddings in VectorDB
    logger.info(f"\n[STEP 4] Storing company embeddings in VectorDB...")
    
    # Get ticker and company name from chunks
    ticker = chunks[0].get('ticker') or args.ticker
    company_name = chunks[0].get('company_name', ticker)
    
    # Delete existing embeddings (if any)
    deleted_count = vectordb.delete_company_embeddings(ticker)
    if deleted_count > 0:
        logger.info(f"[INFO] Deleted {deleted_count} existing embeddings")
    
    # Store new embeddings
    stored_count = vectordb.store_company_embeddings(
        ticker=ticker,
        company_name=company_name,
        chunks=chunks
    )
    logger.info(f"[OK] Stored {stored_count} company embeddings")
    
    # Step 5: Run impact analysis
    logger.info(f"\n[STEP 5] Analyzing impact of legislation on {ticker}...")
    
    analyzer = LegislationImpactAnalyzer(
        vectordb_client=vectordb,
        similarity_threshold=args.similarity_threshold,
        top_k=args.top_k
    )
    
    impact_result = analyzer.analyze_impact(
        legislation_id=legislation_id,
        legislation_embedding=legislation_embedding,
        ticker=ticker,
        company_name=company_name
    )
    
    # Step 6: Display results
    logger.info("\n" + "="*80)
    logger.info("IMPACT ANALYSIS RESULTS")
    logger.info("="*80)
    
    print(f"\nCompany: {impact_result['company_name']} ({impact_result['ticker']})")
    print(f"Legislation: {impact_result['legislation_id']}")
    print(f"\nOverall Impact Score: {impact_result['impact_score']:.3f}")
    print(f"Risk Level: {impact_result['risk_level'].upper()}")
    print(f"Total Matches: {impact_result['total_matches']}")
    
    print(f"\nStatistics:")
    stats = impact_result['statistics']
    print(f"  Average Similarity: {stats['avg_similarity']:.3f}")
    print(f"  Maximum Similarity: {stats['max_similarity']:.3f}")
    print(f"  Minimum Similarity: {stats['min_similarity']:.3f}")
    
    if stats.get('by_section_type'):
        print(f"\nMatches by Section Type:")
        for section_type, section_stats in stats['by_section_type'].items():
            print(f"  {section_type}:")
            print(f"    Count: {section_stats['count']}")
            print(f"    Avg Similarity: {section_stats['avg_similarity']:.3f}")
            print(f"    Max Similarity: {section_stats['max_similarity']:.3f}")
    
    print(f"\nTop 10 Most Relevant Sentences:")
    for i, match in enumerate(impact_result['matched_sentences'][:10], 1):
        print(f"\n  {i}. Similarity: {match['similarity']:.3f}")
        print(f"     Section: {match['section_title']} ({match['section_type']})")
        print(f"     Filing: {match['filing_type']} from {match['filing_date']}")
        print(f"     Position: Sentence {match['sentence_position']}")
        sentence = match['original_sentence']
        if len(sentence) > 200:
            sentence = sentence[:200] + "..."
        print(f"     Sentence: \"{sentence}\"")
    
    print(f"\n{'-'*80}")
    print(f"EXPLANATION:")
    print(f"{'-'*80}")
    print(impact_result['explanation'])
    
    # Step 7: Save results
    output_file = f"output/{ticker}_impact_{legislation_id}.json"
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(impact_result, f, indent=2, ensure_ascii=False)
    
    logger.info(f"\n[OK] Results saved to: {output_file}")
    logger.info("\n" + "="*80)
    logger.info("TEST COMPLETE")
    logger.info("="*80)


if __name__ == '__main__':
    main()

