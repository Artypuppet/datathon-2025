"""
Neo4j population pipeline using Gemini entity extraction.

Reads filings from Snowflake, extracts entities using Gemini, and populates Neo4j graph.
"""

import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.db.snowflake_client import SnowflakeClient
from src.db.neo4j_client import Neo4jClient
from src.llm.gemini_client import GeminiClient

logger = logging.getLogger(__name__)


class Neo4jPopulationPipeline:
    """
    Pipeline for populating Neo4j knowledge graph from SEC filings.
    
    Steps:
    1. Retrieve company chunks from Snowflake
    2. Extract entities using Gemini
    3. Create nodes and relationships in Neo4j
    """
    
    def __init__(
        self,
        snowflake_client: Optional[SnowflakeClient] = None,
        neo4j_client: Optional[Neo4jClient] = None,
        gemini_client: Optional[GeminiClient] = None
    ):
        """
        Initialize population pipeline.
        
        Args:
            snowflake_client: SnowflakeClient instance
            neo4j_client: Neo4jClient instance
            gemini_client: GeminiClient instance
        """
        self.snowflake_client = snowflake_client or SnowflakeClient()
        self.neo4j_client = neo4j_client or Neo4jClient()
        self.gemini_client = gemini_client or GeminiClient()
        
        logger.info("[OK] Neo4jPopulationPipeline initialized")
    
    def populate_company(
        self,
        ticker: str,
        company_name: Optional[str] = None,
        sector: Optional[str] = None,
        industry: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Populate Neo4j graph for a company.
        
        Args:
            ticker: Company ticker
            company_name: Company name (retrieved from Snowflake if not provided)
            sector: Sector (optional)
            industry: Industry (optional)
        
        Returns:
            Dictionary with population results
        """
        logger.info(f"[INFO] Populating Neo4j for {ticker}")
        
        try:
            # Step 1: Get company chunks from Snowflake
            chunks = self.snowflake_client.get_company_chunks(ticker)
            
            if not chunks:
                logger.warning(f"[WARN] No chunks found for {ticker} in Snowflake")
                return {
                    'success': False,
                    'error': 'No chunks found'
                }
            
            # Extract company name from first chunk if not provided
            if not company_name:
                company_name = chunks[0].get('company_name', ticker)
            
            # Step 2: Combine chunk text for entity extraction
            # Focus on Item 1A (Risk Factors) and Item 1 (Business) sections
            relevant_chunks = [
                c for c in chunks
                if c.get('section_type') in ['item_1a', 'item_1']
            ]
            
            if not relevant_chunks:
                # Fallback to all chunks
                relevant_chunks = chunks[:20]  # Limit to first 20 chunks
            
            # Combine text
            combined_text = "\n\n".join([
                c.get('original_sentence', c.get('text', ''))
                for c in relevant_chunks
            ])
            
            # Step 3: Extract entities using Gemini
            logger.info(f"[INFO] Extracting entities for {ticker} using Gemini")
            entities = self.gemini_client.extract_entities(
                filing_text=combined_text,
                ticker=ticker,
                company_name=company_name
            )
            
            # Step 4: Create company node
            self.neo4j_client.create_company_node(
                ticker=ticker,
                company_name=company_name,
                sector=sector,
                industry=industry
            )
            
            # Step 5: Create sector node and link if provided
            if sector:
                self.neo4j_client.create_sector_node(sector)
                self.neo4j_client.create_relationships(
                    ticker=ticker,
                    relationships=[{
                        'type': 'OPERATES_IN',
                        'target': sector,
                        'target_label': 'Sector',
                        'properties': {}
                    }]
                )
            
            # Step 6: Create supplier nodes and relationships
            suppliers = entities.get('suppliers', [])
            supplier_relationships = []
            for supplier in suppliers[:20]:  # Limit to top 20 suppliers
                self.neo4j_client.create_supplier_node(supplier)
                supplier_relationships.append({
                    'type': 'SUPPLIES_TO',
                    'target': supplier,
                    'target_label': 'Supplier',
                    'properties': {}
                })
            
            if supplier_relationships:
                self.neo4j_client.create_relationships(
                    ticker=ticker,
                    relationships=supplier_relationships
                )
            
            # Step 7: Create country/region nodes and relationships
            countries = entities.get('countries', [])
            country_relationships = []
            for country in countries[:20]:  # Limit to top 20 countries
                # Create Country node (reuse Sector node structure for simplicity)
                self.neo4j_client.create_sector_node(country)  # Using Sector as generic location node
                country_relationships.append({
                    'type': 'OPERATES_IN',
                    'target': country,
                    'target_label': 'Sector',  # Using Sector as generic location
                    'properties': {}
                })
            
            if country_relationships:
                self.neo4j_client.create_relationships(
                    ticker=ticker,
                    relationships=country_relationships
                )
            
            # Step 8: Create relationships from extracted relationships
            extracted_rels = entities.get('relationships', [])
            if extracted_rels:
                formatted_rels = []
                for rel in extracted_rels[:20]:  # Limit relationships
                    rel_type = rel.get('type', '').upper()
                    target = rel.get('target', '')
                    
                    # Determine target label based on relationship type
                    if 'SUPPLIER' in rel_type:
                        target_label = 'Supplier'
                        self.neo4j_client.create_supplier_node(target)
                    elif 'COUNTRY' in rel_type or 'OPERATES' in rel_type:
                        target_label = 'Sector'  # Using Sector as generic location
                        self.neo4j_client.create_sector_node(target)
                    else:
                        continue
                    
                    formatted_rels.append({
                        'type': rel_type,
                        'target': target,
                        'target_label': target_label,
                        'properties': {
                            'evidence': rel.get('evidence', '')
                        }
                    })
                
                if formatted_rels:
                    self.neo4j_client.create_relationships(
                        ticker=ticker,
                        relationships=formatted_rels
                    )
            
            logger.info(f"[OK] Populated Neo4j for {ticker}: {len(suppliers)} suppliers, {len(countries)} countries")
            
            return {
                'success': True,
                'ticker': ticker,
                'company_name': company_name,
                'suppliers': len(suppliers),
                'countries': len(countries),
                'relationships': len(extracted_rels)
            }
            
        except Exception as e:
            logger.error(f"[ERROR] Population failed for {ticker}: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def populate_all_companies(
        self,
        tickers: List[str]
    ) -> Dict[str, Any]:
        """
        Populate Neo4j for multiple companies.
        
        Args:
            tickers: List of company tickers
        
        Returns:
            Dictionary with results for each company
        """
        logger.info(f"[INFO] Populating Neo4j for {len(tickers)} companies")
        
        results = {}
        
        for ticker in tickers:
            result = self.populate_company(ticker)
            results[ticker] = result
        
        successful = len([r for r in results.values() if r.get('success')])
        logger.info(f"[OK] Populated Neo4j for {successful}/{len(tickers)} companies")
        
        return results


def main():
    """CLI entry point for Neo4j population."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Populate Neo4j knowledge graph from Snowflake filings"
    )
    
    parser.add_argument(
        '--tickers',
        type=str,
        nargs='+',
        help='List of tickers to process (required)'
    )
    
    parser.add_argument(
        '--ticker',
        type=str,
        help='Process single ticker (alternative to --tickers)'
    )
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='[%(levelname)s] %(message)s'
    )
    
    # Get tickers
    if args.ticker:
        tickers = [args.ticker.upper()]
    elif args.tickers:
        tickers = [t.upper() for t in args.tickers]
    else:
        parser.error("Must provide --ticker or --tickers")
    
    # Initialize pipeline
    pipeline = Neo4jPopulationPipeline()
    
    # Populate
    results = pipeline.populate_all_companies(tickers)
    
    # Print summary
    print(f"\nNeo4j Population Summary:")
    for ticker, result in results.items():
        if result.get('success'):
            print(f"  {ticker}: {result.get('suppliers', 0)} suppliers, {result.get('countries', 0)} countries")
        else:
            print(f"  {ticker}: FAILED - {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    main()
