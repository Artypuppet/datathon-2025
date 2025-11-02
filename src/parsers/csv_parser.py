"""
CSV Parser for financial data and S&P 500 composition.
"""

import pandas as pd
from pathlib import Path
from typing import Dict, Any, List
import logging
import time
import re
from datetime import datetime

from .base import BaseParser, ParseResult, DocumentType

logger = logging.getLogger(__name__)


class CSVParser(BaseParser):
    """Parser for CSV files (composition and performance)."""
    
    def can_parse(self, file_path: Path) -> bool:
        """Check if file is a CSV."""
        return file_path.suffix.lower() == '.csv'
    
    def get_document_type(self) -> DocumentType:
        """Returns CSV financial type."""
        return DocumentType.CSV_FINANCIAL
    
    def parse(self, file_path: Path) -> ParseResult:
        """
        Parse CSV file into structured format.
        
        Args:
            file_path: Path to CSV file
            
        Returns:
            ParseResult with parsed data
        """
        try:
            logger.info(f"[INFO] Parsing CSV: {file_path.name}")
            start_time = time.time()
            
            # Detect and load CSV
            df = self._load_csv(file_path)
            
            # Normalize column names
            df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
            
            # Determine data type from filename first
            data_type = self._detect_data_type(file_path.name)
            
            # If filename detection failed, try column-based detection
            if data_type == 'unknown':
                data_type = self._detect_data_type_from_columns(df)
                if data_type != 'unknown':
                    logger.info(f"[INFO] Detected CSV type from columns: {data_type}")
            
            # Parse based on type
            if data_type == 'composition':
                companies = self._parse_composition(df)
            elif data_type == 'performance':
                companies = self._parse_performance(df)
            else:
                companies = []
                logger.warning(f"[WARN] Unknown CSV type: {file_path.name}")
            
            # Build output
            data = {
                "document_type": "csv_financial",
                "source_file": file_path.name,
                "snapshot_date": self._extract_date_from_filename(file_path.name),
                "data_type": data_type,
                "companies": companies,
                "metadata": {
                    "parsed_at": datetime.now().isoformat(),
                    "parser_version": self.parser_version,
                    "total_companies": len(companies),
                    "columns": list(df.columns)
                }
            }
            
            duration = time.time() - start_time
            logger.info(f"[OK] Parsed {len(companies)} companies in {duration:.2f}s")
            
            return ParseResult(
                success=True,
                document_type=DocumentType.CSV_FINANCIAL,
                data=data,
                metadata={"duration": duration}
            )
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to parse CSV: {e}", exc_info=True)
            return ParseResult(
                success=False,
                document_type=DocumentType.CSV_FINANCIAL,
                error=str(e)
            )
    
    def _load_csv(self, file_path: Path) -> pd.DataFrame:
        """Load CSV with proper encoding detection."""
        try:
            # Try UTF-8 first
            return pd.read_csv(file_path, encoding='utf-8')
        except UnicodeDecodeError:
            # Fallback to latin-1
            logger.warning("[WARN] UTF-8 failed, trying latin-1")
            return pd.read_csv(file_path, encoding='latin-1')
    
    def _detect_data_type(self, filename: str) -> str:
        """Detect if composition or performance CSV."""
        filename_lower = filename.lower()
        if 'composition' in filename_lower:
            return 'composition'
        elif 'performance' in filename_lower or 'stocks' in filename_lower:
            return 'performance'
        return 'unknown'
    
    def _detect_data_type_from_columns(self, df: pd.DataFrame) -> str:
        """Detect CSV type based on column names."""
        columns = set(df.columns.str.lower())
        
        # Composition files have: symbol, company, weight, price
        composition_cols = {'symbol', 'company', 'weight', 'price'}
        if composition_cols.issubset(columns):
            return 'composition'
        
        # Performance files have: symbol, company_name, market_cap, revenue, etc.
        performance_cols = {'symbol', 'company_name', 'market_cap', 'revenue'}
        if performance_cols.issubset(columns):
            return 'performance'
        
        return 'unknown'
    
    def _parse_composition(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Parse S&P 500 composition CSV."""
        companies = []
        
        for _, row in df.iterrows():
            try:
                companies.append({
                    "ticker": str(row.get('symbol', '')).strip(),
                    "company": str(row.get('company', '')).strip(),
                    "metrics": {
                        "weight": self._safe_float(row.get('weight', 0)),
                        "price": self._safe_float(row.get('price', 0))
                    }
                })
            except Exception as e:
                logger.warning(f"[WARN] Failed to parse row: {e}")
                continue
        
        return companies
    
    def _parse_performance(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Parse stock performance CSV."""
        companies = []
        
        for _, row in df.iterrows():
            try:
                companies.append({
                    "ticker": str(row.get('symbol', '')).strip(),
                    "company": str(row.get('company_name', '')).strip(),
                    "sector": str(row.get('sector', '')).strip(),
                    "metrics": {
                        "market_cap": self._safe_float(row.get('market_cap', 0)),
                        "revenue": self._safe_float(row.get('revenue', 0)),
                        "net_income": self._safe_float(row.get('net_income', 0)),
                        "eps": self._safe_float(row.get('eps', 0)),
                        "fcf": self._safe_float(row.get('fcf', 0))
                    }
                })
            except Exception as e:
                logger.warning(f"[WARN] Failed to parse row: {e}")
                continue
        
        return companies
    
    @staticmethod
    def _safe_float(value: Any) -> float:
        """
        Convert value to float, handling European decimal format.
        
        Args:
            value: Value to convert
            
        Returns:
            Float value or 0.0 if conversion fails
        """
        if pd.isna(value):
            return 0.0
        
        if isinstance(value, (int, float)):
            return float(value)
        
        if isinstance(value, str):
            # Remove quotes and whitespace
            value = value.strip().strip('"')
            # Replace comma with period (European format)
            value = value.replace(',', '.')
            try:
                return float(value)
            except ValueError:
                return 0.0
        
        return 0.0
    
    @staticmethod
    def _extract_date_from_filename(filename: str) -> str:
        """
        Extract date from filename like '2025-09-26_stocks-performance.csv'.
        
        Args:
            filename: Filename to parse
            
        Returns:
            ISO date string or empty string
        """
        match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
        return match.group(1) if match else ""

