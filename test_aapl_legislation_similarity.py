#!/usr/bin/env python3
"""
Test AAPL pipeline with legislation similarity analysis.

This test:
1. Processes AAPL filings through full pipeline (parse, aggregate, embed)
2. Uses contextual enrichment and knowledge graph
3. Compares aggregated AAPL data against negative legislation (50% tariff)
4. Calculates similarity between legislation and different filing sections
5. Identifies what parts are similar and why
"""

import sys
import json
import logging
import argparse
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
import numpy as np
from scipy.spatial.distance import cosine

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.pipeline import PipelineOrchestrator, PipelineConfig
from src.utils import get_s3_client
from src.embeddings import TextProcessor, EmbeddingGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)8s] [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def serialize_company_json(company_json: Dict[str, Any]) -> str:
    """
    Serialize aggregated company JSON to text for embedding.
    
    Includes:
    - Textual content from all sections
    - Structured entities
    - Knowledge graph triples
    
    Args:
        company_json: Aggregated company data
        
    Returns:
        Serialized text string
    """
    text_parts = []
    
    # Textual content from aggregated sections
    sections = company_json.get("aggregated_sections", {})
    for section_type, items in sections.items():
        for item in items:
            title = item.get('title', 'Untitled')
            text = item.get('text', '')
            filing_type = item.get('filing_type', 'N/A')
            filing_date = item.get('filing_date', 'N/A')
            
            text_parts.append(
                f"{section_type.title()}: {title} "
                f"(from {filing_type} filing dated {filing_date}): {text}"
            )
    
    # Structured entities
    entities = company_json.get("entities", {})
    company_name = company_json.get("company_name", "Company")
    
    for cat, vals in entities.items():
        if vals and isinstance(vals, list):
            text_parts.append(
                f"{company_name} mentions {cat}: {', '.join(str(v) for v in vals)}."
            )
    
    # Knowledge graph triples
    kg_triples = company_json.get("knowledge_graph", [])
    for triple in kg_triples:
        subject = triple.get('subject', '')
        relation = triple.get('relation', '')
        obj = triple.get('object', '')
        if subject and relation and obj:
            text_parts.append(f"{subject} {relation} {obj}.")
    
    return "\n".join(text_parts)


def process_aapl_pipeline(enable_embeddings: bool = True, use_contextual_enrichment: bool = True):
    """
    Process AAPL through full pipeline.
    
    Args:
        enable_embeddings: Whether to generate embeddings
        use_contextual_enrichment: Whether to use contextual enrichment
        
    Returns:
        Dictionary with pipeline results and aggregated data
    """
    logger.info("="*80)
    logger.info("PROCESSING AAPL THROUGH PIPELINE")
    logger.info("="*80)
    
    s3_client = get_s3_client()
    if not s3_client:
        raise RuntimeError("S3 client not available")
    
    # Find AAPL filings
    aapl_files = s3_client.list_files(prefix='input/filings/AAPL/')
    if not aapl_files:
        raise RuntimeError("No AAPL filings found in S3")
    
    logger.info(f"Found {len(aapl_files)} AAPL filing(s)")
    
    # Use first 10-K file (or first available)
    test_file = None
    for f in aapl_files:
        if '10-k' in f.lower():
            test_file = f
            break
    if not test_file:
        test_file = aapl_files[0]
    
    logger.info(f"Processing: {test_file}")
    
    # Initialize pipeline with embeddings enabled
    config = PipelineConfig(
        dry_run=False,
        skip_embeddings=not enable_embeddings
    )
    orchestrator = PipelineOrchestrator(config=config)
    
    # Enable contextual enrichment and sentence-level chunking if requested
    if enable_embeddings and use_contextual_enrichment:
        orchestrator.embedding_stage = None  # Will recreate with enrichment
        from src.pipeline.stage_embed import EmbeddingStage
        orchestrator.embedding_stage = EmbeddingStage(
            use_contextual_enrichment=True,
            sentence_level_chunking=True,  # Enable sentence-level chunking
            context_window_sentences=2  # Include ±2 sentences around target
        )
        logger.info("[INFO] Contextual enrichment enabled for embeddings")
        logger.info("[INFO] Sentence-level chunking enabled (context window: ±2 sentences)")
    
    # Create event
    event = {
        'file_key': test_file,
        'document_type': 'HTML_FILING',
        'timestamp': datetime.now().isoformat()
    }
    
    # Execute pipeline
    logger.info("Executing pipeline...")
    result = orchestrator.execute(event)
    
    if result['status'] != 'success':
        raise RuntimeError(f"Pipeline failed: {result.get('error', 'Unknown error')}")
    
    # Load aggregated data
    ticker = 'AAPL'
    aggregated_key = f'aggregated/companies/{ticker}.json'
    aggregated_data = s3_client.read_json(aggregated_key)
    
    logger.info(f"[OK] Pipeline completed successfully")
    logger.info(f"[OK] Aggregated data available at: {aggregated_key}")
    
    return {
        'result': result,
        'aggregated_data': aggregated_data,
        'aggregated_key': aggregated_key
    }


def create_legislation_text():
    """Create the negative legislation text about smartphone tariffs."""
    return """
The United States government imposes a 50% tariff on all smartphones 
manufactured and assembled outside of the United States. This regulation 
applies to all imports of smartphones regardless of brand, country of origin, 
or price point. The tariff is intended to protect domestic manufacturing 
and reduce reliance on foreign supply chains for critical technology products.
"""


def analyze_similarity_with_existing_embeddings(
    aggregated_data: Dict[str, Any],
    legislation_text: str,
    existing_embeddings: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Analyze similarity using pre-existing embeddings from pipeline.
    
    Args:
        aggregated_data: Aggregated company data
        legislation_text: Legislation text to compare
        existing_embeddings: Pre-existing embeddings from pipeline
        
    Returns:
        Similarity analysis results
    """
    logger.info("="*80)
    logger.info("ANALYZING SIMILARITY USING EXISTING EMBEDDINGS")
    logger.info("="*80)
    
    # Extract chunks from existing embeddings
    chunks = existing_embeddings.get('chunks', [])
    if not chunks:
        raise ValueError("No chunks found in existing embeddings")
    
    logger.info(f"[INFO] Using {len(chunks)} existing chunks")
    
    # Extract legislation embedding separately (need to generate this)
    embedding_generator = EmbeddingGenerator(
        model_name='allenai/longformer-base-4096',
        device='cpu'
    )
    legislation_embedding = embedding_generator.generate_embeddings([legislation_text])[0]
    
    # Calculate similarity for each chunk
    similarities = []
    for i, chunk in enumerate(chunks):
        chunk_embedding = np.array(chunk.get('embedding', []))
        if len(chunk_embedding) == 0:
            logger.warning(f"[WARN] Chunk {i} has no embedding, skipping")
            continue
        
        # Cosine similarity (1 - cosine distance)
        similarity = 1 - cosine(legislation_embedding, chunk_embedding)
        
        # Check if this is sentence-level chunking
        is_sentence_level = 'sentence_idx' in chunk and 'original_sentence' in chunk
        
        if is_sentence_level:
            # Sentence-level chunking - show specific sentence
            similarities.append({
                'section_type': chunk.get('section_type', 'unknown'),
                'title': chunk.get('section_title', 'Unknown'),
                'filing_type': chunk.get('filing_type', 'N/A'),
                'filing_date': chunk.get('filing_date', 'N/A'),
                'sentence_idx': chunk.get('sentence_idx'),
                'total_sentences': chunk.get('total_sentences_in_section'),
                'similarity': float(similarity),
                'original_sentence': chunk.get('original_sentence', ''),
                'text_preview': chunk.get('text', '')[:300] + '...' if len(chunk.get('text', '')) > 300 else chunk.get('text', '')
            })
        else:
            # Section-level chunking - show section preview
            similarities.append({
                'section_type': chunk.get('section_type', 'unknown'),
                'title': chunk.get('section_title', 'Unknown'),
                'filing_type': chunk.get('filing_type', 'N/A'),
                'filing_date': chunk.get('filing_date', 'N/A'),
                'similarity': float(similarity),
                'text_preview': chunk.get('text', '')[:200] + '...' if len(chunk.get('text', '')) > 200 else chunk.get('text', '')
            })
    
    # Sort by similarity (highest first)
    similarities.sort(key=lambda x: x['similarity'], reverse=True)
    
    # Calculate statistics
    similarity_values = [s['similarity'] for s in similarities]
    avg_similarity = np.mean(similarity_values) if similarity_values else 0.0
    max_similarity = max(similarity_values) if similarity_values else 0.0
    
    # Group by section type
    by_section_type = {}
    for sim in similarities:
        section_type = sim['section_type']
        if section_type not in by_section_type:
            by_section_type[section_type] = []
        by_section_type[section_type].append(sim)
    
    # Calculate average similarity per section type
    section_type_stats = {}
    for section_type, sims in by_section_type.items():
        section_type_stats[section_type] = {
            'count': len(sims),
            'avg_similarity': float(np.mean([s['similarity'] for s in sims])),
            'max_similarity': float(max([s['similarity'] for s in sims]))
        }
    
    # Build analysis results
    results = {
        'legislation_text': legislation_text.strip(),
        'company': aggregated_data.get('company_name', 'AAPL'),
        'ticker': aggregated_data.get('ticker', 'AAPL'),
        'total_sections': len(similarities),
        'average_similarity': float(avg_similarity),
        'max_similarity': float(max_similarity),
        'section_type_statistics': section_type_stats,
        'similarities_by_section': similarities,
        'top_similar_sections': similarities[:10],  # Top 10 most similar
        'knowledge_graph_triples_count': len(aggregated_data.get('knowledge_graph', [])),
        'entities_count': {
            k: len(v) if isinstance(v, list) else 0
            for k, v in aggregated_data.get('entities', {}).items()
        }
    }
    
    logger.info(f"[OK] Similarity analysis complete")
    logger.info(f"  Average similarity: {avg_similarity:.4f}")
    logger.info(f"  Maximum similarity: {max_similarity:.4f}")
    logger.info(f"  Sections analyzed: {len(similarities)}")
    
    return results


def analyze_similarity(
    aggregated_data: Dict[str, Any],
    legislation_text: str,
    embedding_generator: EmbeddingGenerator
) -> Dict[str, Any]:
    """
    Analyze similarity between legislation and company filings.
    
    Args:
        aggregated_data: Aggregated company data
        legislation_text: Legislation text to compare
        embedding_generator: Embedding generator instance
        
    Returns:
        Similarity analysis results
    """
    logger.info("="*80)
    logger.info("ANALYZING SIMILARITY BETWEEN LEGISLATION AND AAPL FILINGS")
    logger.info("="*80)
    
    # Serialize company data to text
    company_text = serialize_company_json(aggregated_data)
    logger.info(f"[INFO] Serialized company data: {len(company_text)} characters")
    
    # Split company text into sections for detailed analysis
    sections = aggregated_data.get('aggregated_sections', {})
    
    # Prepare texts for embedding
    texts_to_embed = []
    text_metadata = []
    
    # Add legislation
    texts_to_embed.append(legislation_text)
    text_metadata.append({
        'type': 'legislation',
        'title': 'US Smartphone Tariff (50%)',
        'section': 'legislation'
    })
    
    # Add each section from company data
    for section_type, items in sections.items():
        for i, item in enumerate(items):
            title = item.get('title', f'{section_type}_{i}')
            text = item.get('text', '')
            filing_type = item.get('filing_type', 'N/A')
            filing_date = item.get('filing_date', 'N/A')
            
            # Create section text
            section_text = f"{section_type.title()}: {title} (from {filing_type} dated {filing_date}). {text}"
            texts_to_embed.append(section_text)
            text_metadata.append({
                'type': 'filing_section',
                'section_type': section_type,
                'title': title,
                'filing_type': filing_type,
                'filing_date': filing_date
            })
    
    # Generate embeddings
    logger.info(f"[INFO] Generating embeddings for {len(texts_to_embed)} texts...")
    embeddings = embedding_generator.generate_embeddings(texts_to_embed)
    
    # Legislation embedding is first
    legislation_embedding = embeddings[0]
    
    # Calculate similarity for each section
    similarities = []
    for i, metadata in enumerate(text_metadata[1:], start=1):  # Skip legislation (index 0)
        section_embedding = embeddings[i]
        
        # Cosine similarity (1 - cosine distance)
        similarity = 1 - cosine(legislation_embedding, section_embedding)
        
        similarities.append({
            'section_type': metadata.get('section_type'),
            'title': metadata.get('title'),
            'filing_type': metadata.get('filing_type'),
            'filing_date': metadata.get('filing_date'),
            'similarity': float(similarity),
            'text_preview': texts_to_embed[i][:200] + '...' if len(texts_to_embed[i]) > 200 else texts_to_embed[i]
        })
    
    # Sort by similarity (highest first)
    similarities.sort(key=lambda x: x['similarity'], reverse=True)
    
    # Calculate statistics
    similarity_values = [s['similarity'] for s in similarities]
    avg_similarity = np.mean(similarity_values) if similarity_values else 0.0
    max_similarity = max(similarity_values) if similarity_values else 0.0
    
    # Group by section type
    by_section_type = {}
    for sim in similarities:
        section_type = sim['section_type']
        if section_type not in by_section_type:
            by_section_type[section_type] = []
        by_section_type[section_type].append(sim)
    
    # Calculate average similarity per section type
    section_type_stats = {}
    for section_type, sims in by_section_type.items():
        section_type_stats[section_type] = {
            'count': len(sims),
            'avg_similarity': float(np.mean([s['similarity'] for s in sims])),
            'max_similarity': float(max([s['similarity'] for s in sims]))
        }
    
    # Build analysis results
    results = {
        'legislation_text': legislation_text.strip(),
        'company': aggregated_data.get('company_name', 'AAPL'),
        'ticker': aggregated_data.get('ticker', 'AAPL'),
        'total_sections': len(similarities),
        'average_similarity': float(avg_similarity),
        'max_similarity': float(max_similarity),
        'section_type_statistics': section_type_stats,
        'similarities_by_section': similarities,
        'top_similar_sections': similarities[:10],  # Top 10 most similar
        'knowledge_graph_triples_count': len(aggregated_data.get('knowledge_graph', [])),
        'entities_count': {
            k: len(v) if isinstance(v, list) else 0
            for k, v in aggregated_data.get('entities', {}).items()
        }
    }
    
    logger.info(f"[OK] Similarity analysis complete")
    logger.info(f"  Average similarity: {avg_similarity:.4f}")
    logger.info(f"  Maximum similarity: {max_similarity:.4f}")
    logger.info(f"  Sections analyzed: {len(similarities)}")
    
    return results


def print_analysis_results(results: Dict[str, Any]):
    """Print formatted analysis results."""
    print("\n" + "="*80)
    print("SIMILARITY ANALYSIS RESULTS")
    print("="*80)
    
    print(f"\nCompany: {results['company']} ({results['ticker']})")
    print(f"Legislation: US Smartphone Tariff (50%)")
    print(f"\nOverall Statistics:")
    print(f"  Total sections analyzed: {results['total_sections']}")
    print(f"  Average similarity: {results['average_similarity']:.4f}")
    print(f"  Maximum similarity: {results['max_similarity']:.4f}")
    
    print(f"\nKnowledge Graph:")
    print(f"  Triples in KG: {results['knowledge_graph_triples_count']}")
    print(f"  Entities:")
    for entity_type, count in results['entities_count'].items():
        if count > 0:
            print(f"    {entity_type}: {count}")
    
    print(f"\nSimilarity by Section Type:")
    for section_type, stats in results['section_type_statistics'].items():
        print(f"  {section_type}:")
        print(f"    Sections: {stats['count']}")
        print(f"    Avg similarity: {stats['avg_similarity']:.4f}")
        print(f"    Max similarity: {stats['max_similarity']:.4f}")
    
    print(f"\nTop 10 Most Similar {'Sentences' if any('sentence_idx' in s for s in results['top_similar_sections']) else 'Sections'}:")
    for i, item in enumerate(results['top_similar_sections'], 1):
        print(f"\n  {i}. {item['title']} (similarity: {item['similarity']:.4f})")
        print(f"     Section type: {item['section_type']}")
        print(f"     Filing: {item['filing_type']} from {item['filing_date']}")
        
        # Show sentence-level info if available
        if 'sentence_idx' in item:
            print(f"     Sentence {item['sentence_idx'] + 1} of {item['total_sentences']} in section")
            print(f"     Original sentence: {item.get('original_sentence', '')[:200]}...")
        else:
            print(f"     Preview: {item['text_preview'][:150]}...")
    
    print("\n" + "="*80)


def main():
    """Main test function."""
    parser = argparse.ArgumentParser(description='Test AAPL pipeline with legislation similarity')
    parser.add_argument('--skip-embeddings', action='store_true', help='Skip embedding generation')
    parser.add_argument('--no-contextual-enrichment', action='store_true', help='Disable contextual enrichment')
    parser.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'])
    
    args = parser.parse_args()
    
    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    try:
        # Step 1: Process AAPL through pipeline
        logger.info("STEP 1: Processing AAPL through pipeline...")
        pipeline_results = process_aapl_pipeline(
            enable_embeddings=not args.skip_embeddings,
            use_contextual_enrichment=not args.no_contextual_enrichment
        )
        
        aggregated_data = pipeline_results['aggregated_data']
        
        # Step 2: Generate embeddings and analyze similarity
        if not args.skip_embeddings:
            logger.info("STEP 2: Analyzing similarity with legislation...")
            
            # Check if embeddings already exist from pipeline
            s3_client = get_s3_client()
            ticker = aggregated_data.get('ticker', 'AAPL')
            existing_embeddings_key = f'embeddings/{ticker}_embedded.json'
            
            try:
                # Try to load existing embeddings
                existing_embeddings = s3_client.read_json(existing_embeddings_key)
                logger.info(f"[OK] Using existing embeddings from {existing_embeddings_key}")
                
                # Use existing embeddings for similarity analysis
                legislation_text = create_legislation_text()
                similarity_results = analyze_similarity_with_existing_embeddings(
                    aggregated_data,
                    legislation_text,
                    existing_embeddings
                )
                
            except Exception as e:
                logger.warning(f"[WARN] Could not load existing embeddings: {e}")
                logger.info("[INFO] Generating new embeddings for similarity analysis...")
                
                # Initialize embedding generator
                embedding_generator = EmbeddingGenerator(
                    model_name='allenai/longformer-base-4096',
                    device='cpu'  # Use CPU for testing, change to 'cuda' if GPU available
                )
                
                # Create legislation text
                legislation_text = create_legislation_text()
                
                # Analyze similarity
                similarity_results = analyze_similarity(
                    aggregated_data,
                    legislation_text,
                    embedding_generator
                )
            
            # Save results
            output_file = Path('output/aapl_legislation_similarity.json')
            output_file.parent.mkdir(exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(similarity_results, f, indent=2, ensure_ascii=False)
            
            logger.info(f"[OK] Results saved to: {output_file}")
            
            # Print results
            print_analysis_results(similarity_results)
        else:
            logger.info("Skipping embedding and similarity analysis (--skip-embeddings)")
            logger.info(f"AAPL aggregated data available at: {pipeline_results['aggregated_key']}")
        
        logger.info("\n" + "="*80)
        logger.info("TEST COMPLETE")
        logger.info("="*80)
        
    except Exception as e:
        logger.error(f"[ERROR] Test failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()

