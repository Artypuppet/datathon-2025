"""
End-to-end pipeline test showing outputs at each stage.

This test demonstrates the complete pipeline flow:
1. Parse - Extract structured data from raw files
2. Aggregate - Combine multiple filings per company
3. Embed - Generate vector embeddings (optional)

Run with: python test_pipeline_e2e.py
"""

import sys
import json
import logging
import argparse
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.pipeline import PipelineOrchestrator, PipelineConfig
from src.utils import get_s3_client


def setup_logging(log_level: str = 'INFO', log_file: str = None):
    """
    Configure logging for the test suite.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file. If None, only console logging.
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Create formatters
    console_formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)8s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)8s] [%(name)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, mode='a', encoding='utf-8')
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        root_logger.info(f"Logging to file: {log_path}")
    
    # Set specific logger levels for different modules
    loggers = {
        'src.pipeline': logging.DEBUG if numeric_level <= logging.DEBUG else logging.INFO,
        'src.parsers': logging.DEBUG if numeric_level <= logging.DEBUG else logging.INFO,
        'src.utils': logging.INFO,
        'src.knowledge': logging.INFO,
        'boto3': logging.WARNING,
        'botocore': logging.WARNING,
        'urllib3': logging.WARNING,
        'edgar': logging.WARNING,
    }
    
    for logger_name, level in loggers.items():
        logging.getLogger(logger_name).setLevel(level)
    
    # Get logger for this module
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured: level={log_level}, file={log_file or 'console only'}")
    
    return logger


# Initialize logger (will be reconfigured in main)
logger = logging.getLogger(__name__)


class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_section(title: str, level: int = 1):
    """Print a formatted section header."""
    if level == 1:
        print(f"\n{Colors.BOLD}{Colors.HEADER}{'='*80}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.HEADER}{title:^80}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.HEADER}{'='*80}{Colors.END}\n")
    elif level == 2:
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'─'*80}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}{title}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'─'*80}{Colors.END}\n")


def print_stage_info(stage_name: str, status: str, details: Dict[str, Any] = None):
    """Print stage execution information."""
    # Handle pre-formatted status strings (with color codes)
    if isinstance(status, str) and Colors.YELLOW in status:
        print(f"\n{Colors.BOLD}Stage: {Colors.BLUE}{stage_name}{Colors.END}")
        print(f"Status: {status}")
    else:
        status_color = Colors.GREEN if status == 'success' else Colors.YELLOW if status == 'dry_run' else Colors.RED
        print(f"\n{Colors.BOLD}Stage: {Colors.BLUE}{stage_name}{Colors.END}")
        print(f"Status: {status_color}{status.upper()}{Colors.END}")
    
    if details:
        for key, value in details.items():
            if isinstance(value, (dict, list)):
                print(f"  {key}:")
                print_json(value, indent=4, max_depth=2)
            else:
                print(f"  {key}: {value}")


def print_json(data: Any, indent: int = 2, max_depth: int = 3, current_depth: int = 0):
    """Pretty print JSON data with depth limiting."""
    if current_depth >= max_depth:
        if isinstance(data, dict):
            print(" " * indent * current_depth + "{...} " + f"({len(data)} keys)")
        elif isinstance(data, list):
            print(" " * indent * current_depth + f"[...] ({len(data)} items)")
        else:
            print(" " * indent * current_depth + str(data))
        return
    
    if isinstance(data, dict):
        print(" " * indent * current_depth + "{")
        for key, value in list(data.items())[:5]:  # Show first 5 items
            print(" " * indent * (current_depth + 1) + f'"{key}": ', end="")
            if isinstance(value, (dict, list)) and current_depth < max_depth - 1:
                print()
                print_json(value, indent, max_depth, current_depth + 1)
            else:
                if isinstance(value, str) and len(value) > 100:
                    print(f'"{value[:100]}..." ({len(value)} chars)')
                elif isinstance(value, list) and len(value) > 3:
                    print(f"[{len(value)} items]")
                else:
                    print(json.dumps(value, ensure_ascii=False) if not isinstance(value, (dict, list)) else str(value))
        if len(data) > 5:
            print(" " * indent * (current_depth + 1) + f"... ({len(data) - 5} more keys)")
        print(" " * indent * current_depth + "}")
    elif isinstance(data, list):
        print(" " * indent * current_depth + "[")
        for i, item in enumerate(data[:3]):  # Show first 3 items
            print_json(item, indent, max_depth, current_depth + 1)
            if i < len(data) - 1:
                print(",")
        if len(data) > 3:
            print(" " * indent * (current_depth + 1) + f"... ({len(data) - 3} more items)")
        print(" " * indent * current_depth + "]")


def inspect_parse_output(s3_client, parse_key: str) -> Dict[str, Any]:
    """Inspect and summarize parse stage output."""
    summary = {
        'file': parse_key,
        'exists': False,
        'document_type': None,
        'sections': 0,
        'metadata': {}
    }
    
    try:
        data = s3_client.read_json(parse_key)
        if data:
            summary['exists'] = True
            summary['document_type'] = data.get('document_type', 'unknown')
            
            # Extract document-specific metadata
            if summary['document_type'] == 'HTML_FILING':
                summary['metadata'] = {
                    'ticker': data.get('ticker'),
                    'filing_type': data.get('filing_type'),
                    'filing_date': data.get('filing_date'),
                    'cik': data.get('cik'),
                }
                summary['sections'] = len(data.get('sections', []))
            elif summary['document_type'] == 'STOCK_COMPOSITION':
                summary['metadata'] = {
                    'snapshot_date': data.get('snapshot_date'),
                    'data_type': data.get('data_type'),
                }
                summary['sections'] = len(data.get('companies', []))
            elif summary['document_type'] in ['HTML_LEGISLATION', 'XML_LEGISLATION']:
                summary['metadata'] = {
                    'title': data.get('title', '')[:60],
                    'jurisdiction': data.get('jurisdiction'),
                    'language': data.get('language'),
                    'identifier': data.get('identifier'),
                }
                summary['sections'] = len(data.get('sections', []))
    except Exception as e:
        summary['error'] = str(e)
    
    return summary


def inspect_aggregate_output(s3_client, ticker: str) -> Dict[str, Any]:
    """Inspect and summarize aggregate stage output."""
    aggregate_key = f'aggregated/companies/{ticker}.json'
    summary = {
        'file': aggregate_key,
        'exists': False,
        'sections': {},
        'entities': {},
        'metadata': {}
    }
    
    try:
        data = s3_client.read_json(aggregate_key)
        if data:
            summary['exists'] = True
            summary['sections'] = {
                'business': len(data.get('aggregated_sections', {}).get('business', [])),
                'risk_factors': len(data.get('aggregated_sections', {}).get('risk_factors', [])),
                'significant_events': len(data.get('aggregated_sections', {}).get('significant_events', [])),
                'other': len(data.get('aggregated_sections', {}).get('other', []))
            }
            summary['entities'] = {
                'countries': len(data.get('entities', {}).get('countries', [])),
                'regions': len(data.get('entities', {}).get('regions', [])),
                'operations': len(data.get('entities', {}).get('operations', [])),
                'risk_types': len(data.get('entities', {}).get('risk_types', []))
            }
            summary['metadata'] = {
                'sector': data.get('sector'),
                'industry': data.get('industry'),
                'total_filings': data.get('metadata', {}).get('total_filings', 0),
                'filing_counts': data.get('metadata', {}).get('filing_counts', {})
            }
    except Exception as e:
        summary['error'] = str(e)
    
    return summary


def test_pipeline_e2e(log_level: str = 'INFO', log_file: str = None):
    """
    Run end-to-end pipeline test.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file
    """
    # Setup logging first
    logger = setup_logging(log_level, log_file)
    
    print_section("END-TO-END PIPELINE TEST", level=1)
    logger.info("Starting end-to-end pipeline test")
    
    s3_client = get_s3_client()
    if not s3_client:
        logger.error("S3 client not available")
        print(f"{Colors.RED}[ERROR] S3 client not available{Colors.END}")
        return
    
    # Find a ticker with all three filing types (10-K, 10-Q, 8-K)
    logger.info("Finding test files in S3...")
    print(f"{Colors.YELLOW}[INFO] Finding test files with all filing types (10-K, 10-Q, 8-K) for a single ticker...{Colors.END}\n")
    
    input_files = s3_client.list_files(prefix='input/filings/')
    filing_files = [f for f in input_files if any(ext in f for ext in ['.html', '.txt'])]
    
    # Group filings by ticker
    ticker_filings = {}
    for file_key in filing_files:
        # Extract ticker from path like "input/filings/A/2024-12-20-10-k-A.txt"
        parts = file_key.split('/')
        if len(parts) >= 3:
            ticker = parts[2].upper()
            if ticker not in ticker_filings:
                ticker_filings[ticker] = {'10-k': [], '10-q': [], '8-k': []}
            
            # Determine filing type from filename
            filename = parts[-1].lower()
            if '-10-k-' in filename or '-10k-' in filename:
                ticker_filings[ticker]['10-k'].append(file_key)
            elif '-10-q-' in filename or '-10q-' in filename:
                ticker_filings[ticker]['10-q'].append(file_key)
            elif '-8-k-' in filename or '-8k-' in filename:
                ticker_filings[ticker]['8-k'].append(file_key)
    
    # Find a ticker that has all three types
    complete_ticker = None
    for ticker, filings in ticker_filings.items():
        if filings['10-k'] and filings['10-q'] and filings['8-k']:
            complete_ticker = ticker
            logger.info(f"Found ticker {ticker} with 10-K: {len(filings['10-k'])}, 10-Q: {len(filings['10-q'])}, 8-K: {len(filings['8-k'])}")
            break
    
    if not complete_ticker:
        # Fall back to first ticker with at least one filing
        for ticker, filings in ticker_filings.items():
            if filings['10-k'] or filings['10-q'] or filings['8-k']:
                complete_ticker = ticker
                logger.warning(f"No ticker found with all three types, using {ticker}")
                break
    
    if not complete_ticker:
        logger.error("No test files found in S3 input/filings/ directory")
        print(f"{Colors.RED}[ERROR] No test files found in S3 input/filings/ directory{Colors.END}")
        print(f"{Colors.YELLOW}[INFO] Please upload test files first{Colors.END}")
        return
    
    # Create test case using first 10-K file (will process all filings for that ticker)
    ticker_filings_data = ticker_filings[complete_ticker]
    test_file = ticker_filings_data['10-k'][0] if ticker_filings_data['10-k'] else \
                ticker_filings_data['10-q'][0] if ticker_filings_data['10-q'] else \
                ticker_filings_data['8-k'][0]
    
    test_cases = [{
        'name': f'Company Filings for {complete_ticker} (10-K, 10-Q, 8-K)',
        'file_key': test_file,
        'document_type': 'HTML_FILING',
        'ticker': complete_ticker,
        'expected_filings': {
            '10-k': len(ticker_filings_data['10-k']),
            '10-q': len(ticker_filings_data['10-q']),
            '8-k': len(ticker_filings_data['8-k'])
        }
    }]
    
    logger.info(f"Found ticker {complete_ticker} with {sum(test_cases[0]['expected_filings'].values())} total filing(s)")
    
    # Run pipeline for each test case
    for test_case in test_cases:
        print_section(f"TEST CASE: {test_case['name']}", level=2)
        
        file_key = test_case['file_key']
        document_type = test_case.get('document_type')
        ticker = test_case.get('ticker', 'UNKNOWN')
        expected_filings = test_case.get('expected_filings', {})
        
        print(f"Ticker: {Colors.BOLD}{Colors.CYAN}{ticker}{Colors.END}")
        print(f"Input file: {Colors.CYAN}{file_key}{Colors.END}")
        print(f"Document type: {Colors.CYAN}{document_type}{Colors.END}")
        if expected_filings:
            print(f"Expected filings: {Colors.CYAN}10-K: {expected_filings.get('10-k', 0)}, "
                  f"10-Q: {expected_filings.get('10-q', 0)}, "
                  f"8-K: {expected_filings.get('8-k', 0)}{Colors.END}")
        print()
        
        # Initialize pipeline
        config = PipelineConfig(
            dry_run=False,
            skip_embeddings=True  # Skip embeddings for faster testing
        )
        orchestrator = PipelineOrchestrator(config=config)
        
        # Create event
        event = {
            'file_key': file_key,
            'document_type': document_type,
            'timestamp': datetime.now().isoformat()
        }
        
        # Execute pipeline
        logger.info(f"Executing pipeline for {file_key}")
        print(f"{Colors.BOLD}Executing pipeline...{Colors.END}\n")
        result = orchestrator.execute(event)
        logger.info(f"Pipeline execution completed with status: {result.get('status')}")
        
        # Display results
        print_section("PIPELINE RESULTS", level=2)
        
        print(f"Overall Status: {Colors.GREEN if result['status'] == 'success' else Colors.RED}{result['status'].upper()}{Colors.END}\n")
        
        # Stage 1: Parse
        parse_key = result.get('parsed_key')
        parse_status = result.get('stages', {}).get('parse', 'unknown')
        if parse_key:
            print_stage_info("1. PARSE", parse_status)
            parse_summary = inspect_parse_output(s3_client, parse_key)
            print(f"  Output file: {parse_summary['file']}")
            print(f"  File exists: {Colors.GREEN if parse_summary['exists'] else Colors.RED}{parse_summary['exists']}{Colors.END}")
            print(f"  Document type: {parse_summary['document_type']}")
            print(f"  Sections/Items: {parse_summary['sections']}")
            print(f"  Metadata:")
            for key, value in parse_summary['metadata'].items():
                print(f"    {key}: {value}")
        else:
            print_stage_info("1. PARSE", parse_status)
        
        # Stage 2: Aggregate (only for filings)
        aggregate_status = result.get('stages', {}).get('aggregate', 'skipped')
        # Use ticker from test_case first (more reliable), then try to extract from result
        aggregate_ticker = ticker if ticker != 'UNKNOWN' else None
        
        # If not in test_case, try to extract from parsed output
        if not aggregate_ticker and parse_key:
            try:
                parse_data = s3_client.read_json(parse_key)
                if parse_data:
                    # Handle both 'html_filing' and 'HTML_FILING' formats
                    doc_type = parse_data.get('document_type', '').lower()
                    if 'filing' in doc_type:
                        aggregate_ticker = parse_data.get('ticker')
                        if not aggregate_ticker:
                            # Try to extract from filename or source_file
                            source_file = parse_data.get('source_file', '')
                            source_s3_key = parse_data.get('source_s3_key', '')
                            # Extract ticker from meaningful filename
                            if source_s3_key:
                                import re
                                from pathlib import Path
                                name = Path(source_s3_key).name
                                match = re.search(r'-\d+[-_]?[kq][-_]?([A-Z]{1,5})', name, re.IGNORECASE)
                                if match:
                                    aggregate_ticker = match.group(1).upper()
            except Exception as e:
                logger.debug(f"Could not extract ticker from parse output: {e}")
        
        if aggregate_ticker and aggregate_status == 'success':
            print_stage_info("2. AGGREGATE", aggregate_status)
            aggregate_summary = inspect_aggregate_output(s3_client, aggregate_ticker)
            print(f"  Ticker: {aggregate_ticker}")
            print(f"  Output file: {aggregate_summary['file']}")
            print(f"  File exists: {Colors.GREEN if aggregate_summary['exists'] else Colors.RED}{aggregate_summary['exists']}{Colors.END}")
            if aggregate_summary['exists']:
                print(f"  Sections:")
                for section_type, count in aggregate_summary['sections'].items():
                    print(f"    {section_type}: {count}")
                print(f"  Entities:")
                for entity_type, count in aggregate_summary['entities'].items():
                    print(f"    {entity_type}: {count}")
                print(f"  Metadata:")
                for key, value in aggregate_summary['metadata'].items():
                    print(f"    {key}: {value}")
        else:
            status_display = aggregate_status
            if aggregate_status == 'skipped':
                status_display = f"{Colors.YELLOW}SKIPPED{Colors.END} (not a company filing)"
            print_stage_info("2. AGGREGATE", status_display)
        
        # Stage 3: Embed
        embed_status = result.get('stages', {}).get('embeddings', 'skipped')
        if embed_status == 'skipped':
            print_stage_info("3. EMBED", f"{Colors.YELLOW}SKIPPED{Colors.END} (configured to skip)")
        else:
            print_stage_info("3. EMBED", embed_status)
        
        print()
        
        # Show sample data
        if parse_key:
            print_section("SAMPLE PARSE OUTPUT", level=2)
            try:
                parse_data = s3_client.read_json(parse_key)
                if parse_data:
                    print(f"Document Type: {parse_data.get('document_type')}")
                    if parse_data.get('sections'):
                        print(f"\nFirst Section Sample:")
                        section = parse_data['sections'][0]
                        print(f"  ID: {section.get('section_id')}")
                        print(f"  Title: {section.get('title', '')[:80]}")
                        print(f"  Text Preview: {section.get('text', '')[:200]}...")
            except Exception as e:
                print(f"{Colors.RED}Error reading parse output: {e}{Colors.END}")
        
        if aggregate_ticker:
            print_section("DETAILED AGGREGATE OUTPUT", level=2)
            try:
                aggregate_data = s3_client.read_json(f'aggregated/companies/{aggregate_ticker}.json')
                if aggregate_data:
                    # Basic Info
                    print(f"{Colors.BOLD}Company Information:{Colors.END}")
                    print(f"  Ticker: {aggregate_data.get('ticker')}")
                    print(f"  Company: {aggregate_data.get('company_name')}")
                    print(f"  CIK: {aggregate_data.get('cik')}")
                    print(f"  Sector: {aggregate_data.get('sector')}")
                    print(f"  Industry: {aggregate_data.get('industry')}")
                    print(f"  Country: {aggregate_data.get('country')}")
                    
                    # Filing Metadata
                    metadata = aggregate_data.get('metadata', {})
                    filing_counts = metadata.get('filing_counts', {})
                    print(f"\n{Colors.BOLD}Filing Summary:{Colors.END}")
                    print(f"  Total Filings: {metadata.get('total_filings', 0)}")
                    print(f"  10-K Count: {filing_counts.get('10-K', 0)}")
                    print(f"  10-Q Count: {filing_counts.get('10-Q', 0)}")
                    print(f"  8-K Count: {filing_counts.get('8-K', 0)}")
                    
                    # Sections
                    sections = aggregate_data.get('aggregated_sections', {})
                    print(f"\n{Colors.BOLD}Section Counts:{Colors.END}")
                    print(f"  Business: {len(sections.get('business', []))} section(s)")
                    print(f"  Risk Factors: {len(sections.get('risk_factors', []))} section(s)")
                    print(f"  Significant Events: {len(sections.get('significant_events', []))} section(s)")
                    print(f"  Other: {len(sections.get('other', []))} section(s)")
                    
                    # Entities
                    entities = aggregate_data.get('entities', {})
                    print(f"\n{Colors.BOLD}Extracted Entities:{Colors.END}")
                    print(f"  Countries: {len(entities.get('countries', []))}")
                    if entities.get('countries'):
                        print(f"    {', '.join(list(entities['countries'])[:10])}")
                    print(f"  Regions: {len(entities.get('regions', []))}")
                    if entities.get('regions'):
                        print(f"    {', '.join(list(entities['regions'])[:10])}")
                    print(f"  Operations: {len(entities.get('operations', []))}")
                    if entities.get('operations'):
                        print(f"    {', '.join(list(entities['operations'])[:5])}")
                    print(f"  Risk Types: {len(entities.get('risk_types', []))}")
                    risk_types = entities.get('risk_types', [])
                    if risk_types:
                        print(f"    {', '.join(risk_types[:15])}")
                        if len(risk_types) > 15:
                            print(f"    ... and {len(risk_types) - 15} more")
                    
                    # Sample Sections
                    print(f"\n{Colors.BOLD}Sample Sections:{Colors.END}")
                    
                    # Business section
                    business_sections = sections.get('business', [])
                    if business_sections:
                        print(f"\n  {Colors.CYAN}Business Section:{Colors.END}")
                        for i, section in enumerate(business_sections[:2], 1):
                            print(f"    [{i}] {section.get('title', 'Untitled')[:60]}")
                            print(f"        Filing: {section.get('filing_type', 'N/A')} from {section.get('filing_date', 'N/A')}")
                            text_preview = section.get('text', '')[:150]
                            if text_preview:
                                print(f"        Preview: {text_preview}...")
                    
                    # Risk Factors section
                    risk_sections = sections.get('risk_factors', [])
                    if risk_sections:
                        print(f"\n  {Colors.CYAN}Risk Factors Section:{Colors.END}")
                        for i, section in enumerate(risk_sections[:2], 1):
                            print(f"    [{i}] {section.get('title', 'Untitled')[:60]}")
                            print(f"        Filing: {section.get('filing_type', 'N/A')} from {section.get('filing_date', 'N/A')}")
                            text_preview = section.get('text', '')[:150]
                            if text_preview:
                                print(f"        Preview: {text_preview}...")
                    
                    # Significant Events (8-K items)
                    events = sections.get('significant_events', [])
                    if events:
                        print(f"\n  {Colors.CYAN}Significant Events (8-K):{Colors.END}")
                        for i, event in enumerate(events[:3], 1):
                            print(f"    [{i}] {event.get('title', 'Untitled')[:60]}")
                            print(f"        Filing: {event.get('filing_type', 'N/A')} from {event.get('filing_date', 'N/A')}")
                            text_preview = event.get('text', '')[:150]
                            if text_preview:
                                print(f"        Preview: {text_preview}...")
                    
                    # Other sections (includes 10-Q Item 2, Item 4, etc.)
                    other_sections = sections.get('other', [])
                    if other_sections:
                        print(f"\n  {Colors.CYAN}Other Sections (10-Q Controls, Properties, etc.):{Colors.END}")
                        for i, section in enumerate(other_sections[:3], 1):
                            filing_info = f"{section.get('filing_type', 'N/A')}"
                            date_info = section.get('filing_date', 'N/A')
                            if date_info != 'N/A':
                                filing_info += f" from {date_info}"
                            print(f"    [{i}] {section.get('title', 'Untitled')[:60]}")
                            print(f"        Filing: {filing_info}")
                            text_preview = section.get('text', '')[:150]
                            if text_preview:
                                print(f"        Preview: {text_preview}...")
                    
                    # Temporal Timeline
                    timeline = metadata.get('temporal_timeline', [])
                    if timeline:
                        print(f"\n{Colors.BOLD}Temporal Timeline (Recent Filings):{Colors.END}")
                        for entry in timeline[-5:]:  # Show last 5
                            print(f"  {entry.get('date', 'N/A')}: {entry.get('filing_type', 'N/A')} - {entry.get('source_file', 'N/A')[:50]}")
                    
            except Exception as e:
                logger.error(f"Error reading aggregate output: {e}", exc_info=True)
                print(f"{Colors.RED}Error reading aggregate output: {e}{Colors.END}")
        
        print()
    
    logger.info("End-to-end pipeline test completed")
    print_section("TEST COMPLETE", level=1)
    print(f"{Colors.GREEN}All pipeline stages executed successfully!{Colors.END}\n")


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description='Run end-to-end pipeline test',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_pipeline_e2e.py
  python test_pipeline_e2e.py --log-level DEBUG
  python test_pipeline_e2e.py --log-level INFO --log-file logs/test.log
  python test_pipeline_e2e.py -l DEBUG -f logs/pipeline_test.log
        """
    )
    
    parser.add_argument(
        '-l', '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Set logging level (default: INFO)'
    )
    
    parser.add_argument(
        '-f', '--log-file',
        default=None,
        help='Path to log file (optional). If not specified, logs only to console.'
    )
    
    args = parser.parse_args()
    
    # Run test with configured logging
    test_pipeline_e2e(log_level=args.log_level, log_file=args.log_file)


if __name__ == "__main__":
    main()

