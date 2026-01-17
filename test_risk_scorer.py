"""
Test script for RegulatoryRiskScorer.

Tests the comprehensive risk scoring engine with:
- Chunk-level weighting
- Sensitivity adjustments
- External probability integration
- Risk categorization
- Recommendations
"""

import logging
import argparse
import json
from pathlib import Path
from typing import Dict, Any
import numpy as np

from src.vectordb import VectorDBClient, LegislationImpactAnalyzer, get_vectordb_client
from src.embeddings import EmbeddingGenerator
from src.utils import get_s3_client


def setup_logging(log_level: str = 'INFO', log_file: str = None):
    """Setup logging configuration."""
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


def print_section(title: str, subtitle: str = ""):
    """Print a formatted section header."""
    print("\n" + "="*80)
    print(title)
    if subtitle:
        print(subtitle)
    print("="*80)


def create_tariff_legislation() -> str:
    """Create test tariff legislation text."""
    return """
    Title: US Smartphone Tariff Act 2025
    
    Section 1: Imposition of Tariffs
    Effective January 1, 2025, a tariff of 50% shall be imposed on all smartphones 
    assembled and manufactured outside the United States. This includes devices 
    manufactured in China, India, Vietnam, Taiwan, South Korea, and other countries.
    
    Section 2: Covered Products
    The tariff applies to:
    - Complete smartphones and mobile phones
    - Smartphone components and assemblies
    - Accessories packaged with smartphones
    
    Section 3: Enforcement
    The tariff will be enforced at all US ports of entry. Companies importing 
    smartphones manufactured outside the US must pay the 50% tariff based on 
    the declared value of the goods.
    
    Section 4: Retaliatory Measures
    Countries affected by this tariff may impose reciprocal tariffs on US exports,
    which could adversely impact US companies with significant international operations.
    """


def check_opensearch_config():
    """Check if OpenSearch is configured."""
    import os
    endpoint = os.getenv('OPENSEARCH_ENDPOINT')
    use_iam = os.getenv('OPENSEARCH_USE_IAM_AUTH', 'false').lower() == 'true'
    
    if not endpoint:
        raise ValueError("OPENSEARCH_ENDPOINT environment variable not set")
    
    if not use_iam:
        username = os.getenv('OPENSEARCH_USERNAME')
        password = os.getenv('OPENSEARCH_PASSWORD')
        if not username or not password:
            raise ValueError("OPENSEARCH_USERNAME and OPENSEARCH_PASSWORD required for basic auth")
    
    return True


def main():
    parser = argparse.ArgumentParser(description='Test RegulatoryRiskScorer with AAPL')
    parser.add_argument('--ticker', type=str, default='AAPL',
                       help='Company ticker to test (default: AAPL)')
    parser.add_argument('--skip-pipeline', action='store_true',
                       help='Skip pipeline execution, use existing S3 data')
    parser.add_argument('--skip-embeddings', action='store_true',
                       help='Skip embedding generation, use existing embeddings')
    parser.add_argument('--clear-opensearch', action='store_true',
                       help='Clear existing OpenSearch data before test')
    parser.add_argument('--polymarket-p', type=float, default=0.75,
                       help='Polymarket probability of legislation passing (default: 0.75)')
    parser.add_argument('--log-level', type=str, default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level (default: INFO)')
    parser.add_argument('--log-file', type=str, default=None,
                       help='Optional log file path')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level, args.log_file)
    logger = logging.getLogger(__name__)
    
    print_section("REGULATORY RISK SCORER TEST", f"Testing risk scoring for {args.ticker}")
    
    # Check configuration
    try:
        check_opensearch_config()
    except ValueError as e:
        logger.error(f"[ERROR] Configuration error: {e}")
        return
    
    ticker = args.ticker.upper()
    legislation_id = "US_SMARTPHONE_TARIFF_2025"
    polymarket_p = args.polymarket_p
    
    # Step 1: Run Pipeline (if needed)
    print_section("STEP 1: Running Pipeline", f"Processing {ticker} filings...")
    
    if not args.skip_pipeline:
        logger.info(f"[INFO] Running pipeline for {ticker}")
        
        from src.pipeline import PipelineOrchestrator, PipelineConfig
        from src.pipeline.stage_embed import EmbeddingStage
        
        config = PipelineConfig()
        config.skip_embeddings = False
        config.dry_run = False
        
        orchestrator = PipelineOrchestrator(config=config)
        
        # Enable sentence-level chunking with contextual enrichment
        orchestrator.embedding_stage = EmbeddingStage(
            use_contextual_enrichment=True,
            sentence_level_chunking=True,
            context_window_sentences=3,
            sentences_per_chunk=3
        )
        logger.info("[INFO] Enabled sentence-level chunking with contextual enrichment")
        
        # Find a filing for the ticker
        s3_client = get_s3_client()
        files = s3_client.list_files(prefix=f"input/filings/{ticker}/")
        
        if not files:
            logger.error(f"[ERROR] No filings found for {ticker}")
            return
        
        test_file = files[0]
        logger.info(f"[INFO] Found filing: {test_file}")
        
        event = {
            'file_key': test_file,
            'ticker': ticker
        }
        
        result = orchestrator.execute(event)
        
        if result.get('status') != 'success':
            logger.error(f"[ERROR] Pipeline failed: {result}")
            return
        
        logger.info("[OK] Pipeline completed successfully")
        embedding_key = result.get('embedding_key')
        logger.info(f"  - Embeddings: {embedding_key}")
    else:
        embedding_key = f"embeddings/{ticker}_embedded.json"
        logger.info(f"[INFO] Skipping pipeline, using existing embeddings: {embedding_key}")
    
    # Step 2: Initialize VectorDB and Risk Scorer
    print_section("STEP 2: Initializing VectorDB and Risk Scorer", "Connecting to OpenSearch...")
    
    try:
        vectordb = VectorDBClient(backend='opensearch')
        logger.info("[OK] OpenSearch client initialized")
    except Exception as e:
        logger.error(f"[ERROR] Failed to initialize OpenSearch: {e}", exc_info=True)
        return
    
    # Initialize analyzer with advanced scoring
    analyzer = LegislationImpactAnalyzer(
        vectordb_client=vectordb,
        similarity_threshold=0.7,
        top_k=50,
        use_advanced_scoring=True
    )
    logger.info("[OK] LegislationImpactAnalyzer initialized with advanced scoring")
    
    # Clear existing data if requested
    if args.clear_opensearch:
        logger.info("[INFO] Clearing existing OpenSearch data...")
        deleted = vectordb.delete_company_embeddings(ticker)
        logger.info(f"[OK] Deleted {deleted} existing embeddings for {ticker}")
    
    # Step 3: Ensure embeddings are in VectorDB
    print_section("STEP 3: Storing Company Embeddings", f"Loading embeddings for {ticker}...")
    
    try:
        s3_client = get_s3_client()
        
        # Load embeddings from S3
        embeddings_data = s3_client.read_json(embedding_key)
        
        if 'chunks' not in embeddings_data:
            logger.error(f"[ERROR] No 'chunks' key in embeddings data")
            return
        
        chunks = embeddings_data['chunks']
        logger.info(f"[INFO] Loaded {len(chunks)} chunks from S3")
        
        # Verify chunks have embeddings
        chunks_with_embeddings = [c for c in chunks if 'embedding' in c]
        if len(chunks_with_embeddings) < len(chunks):
            logger.warning(f"[WARN] Only {len(chunks_with_embeddings)}/{len(chunks)} chunks have embeddings")
        
        # Get company metadata
        ticker_from_chunk = chunks[0].get('ticker') or ticker
        company_name = chunks[0].get('company_name', ticker)
        
        logger.info(f"[INFO] Storing embeddings for {ticker_from_chunk} ({company_name})")
        
        # Store in OpenSearch
        stored_count = vectordb.store_company_embeddings(
            ticker=ticker_from_chunk,
            company_name=company_name,
            chunks=chunks_with_embeddings
        )
        
        logger.info(f"[OK] Stored {stored_count} embeddings in OpenSearch")
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
        
        # Store in OpenSearch
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
        logger.info(f"[OK] Stored legislation embedding: {legislation_id}")
    except Exception as e:
        logger.error(f"[ERROR] Failed to store legislation embedding: {e}", exc_info=True)
        return
    
    # Step 5: Run Risk Scoring Analysis
    print_section("STEP 5: Risk Scoring Analysis", "Computing comprehensive risk score...")
    
    try:
        # Prepare company metadata for sensitivity calculation
        # In a real scenario, this would come from external data sources
        company_metadata = {
            'company_name': company_name,
            'ticker': ticker,
            'market_cap': 3.0e12,  # $3 trillion (example)
            'margin_sensitivity': 0.6,  # 60% sensitivity
            'supply_chain_dependency': 0.8,  # High dependency
            'revenue_by_region': {
                'Greater China': 0.20,  # 20% of revenue
                'Europe': 0.25,  # 25% of revenue
                'Americas': 0.40,  # 40% of revenue
                'Japan': 0.08,
                'Rest of Asia Pacific': 0.07
            },
            'affected_regions': ['China', 'Taiwan', 'Vietnam', 'India', 'South Korea'],
            'entities': {
                'countries': ['China', 'Taiwan', 'Vietnam', 'India', 'South Korea', 'United States']
            }
        }
        
        logger.info("[INFO] Company metadata:")
        logger.info(f"  Market Cap: ${company_metadata['market_cap']/1e9:.1f}B")
        logger.info(f"  Margin Sensitivity: {company_metadata['margin_sensitivity']*100:.0f}%")
        logger.info(f"  Supply Chain Dependency: {company_metadata['supply_chain_dependency']*100:.0f}%")
        logger.info(f"  Polymarket Probability: {polymarket_p*100:.0f}%")
        
        # Analyze impact with advanced scoring
        result = analyzer.analyze_impact(
            legislation_id=legislation_id,
            legislation_embedding=legislation_embedding,
            ticker=ticker,
            company_name=company_name,
            company_metadata=company_metadata,
            polymarket_p=polymarket_p
        )
        
        logger.info("[OK] Risk analysis complete")
        
        # Step 6: Display Results
        print_section("STEP 6: RISK SCORING RESULTS", "")
        
        # Extract advanced scoring results
        advanced_scoring = result.get('advanced_scoring')
        
        if advanced_scoring:
            print(f"\n{'='*80}")
            print("COMPREHENSIVE RISK SCORE BREAKDOWN")
            print(f"{'='*80}\n")
            
            print(f"Company: {company_name} ({ticker})")
            print(f"Legislation: {legislation_id}")
            print(f"Polymarket Probability: {polymarket_p*100:.1f}%")
            print(f"\n{'─'*80}\n")
            
            # Score breakdown
            print("SCORE BREAKDOWN:")
            print(f"  Raw Score:           {advanced_scoring.get('raw_score', 0):.4f}")
            print(f"  Sensitivity Factor:  {advanced_scoring.get('sensitivity', 0):.4f}")
            print(f"  Adjusted Score:      {advanced_scoring.get('adjusted_score', 0):.4f}")
            print(f"  Expected Score:      {advanced_scoring.get('final_expected', 0):.4f} (with {polymarket_p*100:.0f}% probability)")
            print(f"  Worst Case Score:    {advanced_scoring.get('final_worst', 0):.4f} (if 100% probability)")
            
            # Risk level - check both places
            risk_level = advanced_scoring.get('risk_level') or result.get('risk_level', 'unknown')
            print(f"\n  Final Risk Level:    {risk_level.upper()}")
            
            # Sensitivity breakdown
            exp = advanced_scoring.get('explanation', {})
            sens_breakdown = exp.get('sensitivity_breakdown', {})
            print(f"\n{'─'*80}\n")
            print("SENSITIVITY BREAKDOWN:")
            print(f"  Overall Sensitivity:     {sens_breakdown.get('overall_sensitivity', 0):.4f}")
            print(f"  Revenue Exposed:         {sens_breakdown.get('revenue_exposed', 0):.4f}")
            print(f"  Margin Sensitivity:      {sens_breakdown.get('margin_sensitivity', 0):.4f}")
            print(f"  Supply Chain Dependency: {sens_breakdown.get('supply_chain_dependency', 0):.4f}")
            
            # Recommendations
            recommendations = advanced_scoring.get('recommendations', {})
            if recommendations:
                print(f"\n{'─'*80}\n")
                print("RECOMMENDATIONS:")
                print(f"  Action:              {recommendations.get('action', 'N/A')}")
                print(f"  Suggested Reduction: {recommendations.get('suggested_reduction', 0)*100:.1f}%")
                print(f"  Hedge Recommended:   {'Yes' if recommendations.get('hedge_recommended', False) else 'No'}")
                print(f"  Monitoring Level:    {recommendations.get('monitoring', 'N/A')}")
                print(f"\n  Detailed Recommendations:")
                for rec in recommendations.get('recommendations', []):
                    print(f"    • {rec}")
            
            # Top Contributors
            top_contributors = advanced_scoring.get('top_contributors', [])
            if top_contributors:
                print(f"\n{'─'*80}\n")
                print("TOP 5 CONTRIBUTING CHUNKS:")
                for i, contrib in enumerate(top_contributors[:5], 1):
                    print(f"\n  {i}. {contrib.get('section_title', 'N/A')} (Section: {contrib.get('section_type', 'unknown')})")
                    print(f"     Similarity: {contrib.get('similarity', 0):.4f}")
                    print(f"     Weight: {contrib.get('weight', 0):.4f}")
                    print(f"     Exposure: {contrib.get('exposure', 0):.4f}")
                    print(f"     Filing: {contrib.get('filing_type', 'N/A')} from {contrib.get('filing_date', 'N/A')}")
                    sentence = contrib.get('sentence_text', '')
                    if len(sentence) > 150:
                        sentence = sentence[:150] + "..."
                    print(f"     Text: {sentence}")
        
        # Legacy scores (for comparison)
        print(f"\n{'='*80}\n")
        print("LEGACY SCORING (for comparison):")
        print(f"  Impact Score: {result.get('impact_score', 0):.4f}")
        print(f"  Risk Level:   {result.get('risk_level', 'unknown').upper()}")
        print(f"  Total Matches: {result.get('total_matches', 0)}")
        
        # Save results
        output_dir = Path('output')
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / f"{ticker}_risk_scorer_test_results.json"
        
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        
        logger.info(f"\n[OK] Results saved to: {output_file}")
        
        # Summary
        print(f"\n{'='*80}")
        print("TEST COMPLETE")
        print(f"{'='*80}")
        print(f"Successfully tested RegulatoryRiskScorer for {ticker}")
        if advanced_scoring:
            risk_level = advanced_scoring.get('risk_level') or result.get('risk_level', 'unknown')
            print(f"[SUCCESS] Advanced Risk Scoring:")
            print(f"  - Risk Level: {risk_level.upper()}")
            print(f"  - Expected Score: {advanced_scoring.get('final_expected', 0):.4f}")
            print(f"  - Sensitivity: {advanced_scoring.get('sensitivity', 0):.4f}")
            print(f"  - Top Contributors: {len(advanced_scoring.get('top_contributors', []))} chunks")
            if recommendations:
                print(f"  - Recommendations: {recommendations.get('action', 'N/A')}")
        else:
            print(f"[WARN] Advanced scoring not available, using legacy scoring")
        
    except Exception as e:
        logger.error(f"[ERROR] Risk scoring failed: {e}", exc_info=True)
        return


if __name__ == '__main__':
    main()

