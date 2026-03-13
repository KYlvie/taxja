"""
CSV Parser for Austrian Bank Statements

Supports common Austrian bank CSV formats:
- Raiffeisen
- Erste Bank
- Sparkasse
- Bank Austria
- Generic CSV formats

Handles various date formats and decimal separators.
"""

import csv
import io
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional
from enum import Enum


class BankFormat(str, Enum):
    """Supported Austrian bank CSV formats"""
    RAIFFEISEN = "raiffeisen"
    ERSTE_BANK = "erste_bank"
    SPARKASSE = "sparkasse"
    BANK_AUSTRIA = "bank_austria"
    GENERIC = "generic"


class CSVParser:
    """Parser for Austrian bank statement CSV files"""
    
    # Common date formats in Austrian banks
    DATE_FORMATS = [
        "%d.%m.%Y",      # 31.12.2026
        "%d/%m/%Y",      # 31/12/2026
        "%Y-%m-%d",      # 2026-12-31
        "%d-%m-%Y",      # 31-12-2026
        "%d.%m.%y",      # 31.12.26
    ]
    
    # Bank-specific column mappings
    BANK_MAPPINGS = {
        BankFormat.RAIFFEISEN: {
            "date": ["Buchungsdatum", "Datum", "Date"],
            "amount": ["Betrag", "Amount"],
            "description": ["Buchungstext", "Text", "Description"],
            "reference": ["Referenz", "Reference"],
        },
        BankFormat.ERSTE_BANK: {
            "date": ["Valutadatum", "Buchungsdatum", "Datum"],
            "amount": ["Betrag", "Umsatz"],
            "description": ["Buchungstext", "Verwendungszweck"],
            "reference": ["Belegnummer"],
        },
        BankFormat.SPARKASSE: {
            "date": ["Buchungstag", "Datum"],
            "amount": ["Betrag"],
            "description": ["Verwendungszweck", "Text"],
            "reference": ["Referenz"],
        },
        BankFormat.BANK_AUSTRIA: {
            "date": ["Buchungsdatum"],
            "amount": ["Betrag"],
            "description": ["Buchungstext"],
            "reference": ["Referenznummer"],
        },
    }
    
    def __init__(self, bank_format: Optional[BankFormat] = None):
        """
        Initialize CSV parser
        
        Args:
            bank_format: Specific bank format to use, or None for auto-detection
        """
        self.bank_format = bank_format
    
    def parse(self, csv_content: str, encoding: str = "utf-8") -> List[Dict[str, Any]]:
        """
        Parse CSV content and extract transactions
        
        Args:
            csv_content: CSV file content as string
            encoding: File encoding (default: utf-8)
        
        Returns:
            List of parsed transaction dictionaries
        """
        # Try different delimiters
        delimiters = [";", ",", "\t"]
        
        for delimiter in delimiters:
            try:
                transactions = self._parse_with_delimiter(csv_content, delimiter)
                if transactions:
                    return transactions
            except Exception:
                continue
        
        raise ValueError("Could not parse CSV file with any known delimiter")
    
    def _parse_with_delimiter(
        self,
        csv_content: str,
        delimiter: str
    ) -> List[Dict[str, Any]]:
        """Parse CSV with specific delimiter"""
        
        reader = csv.DictReader(io.StringIO(csv_content), delimiter=delimiter)
        
        # Auto-detect bank format if not specified
        if not self.bank_format:
            self.bank_format = self._detect_bank_format(reader.fieldnames)
        
        transactions = []
        
        for row in reader:
            try:
                transaction = self._parse_row(row)
                if transaction:
                    transactions.append(transaction)
            except Exception as e:
                # Skip invalid rows but continue parsing
                print(f"Warning: Skipping row due to error: {e}")
                continue
        
        return transactions
    
    def _detect_bank_format(self, fieldnames: List[str]) -> BankFormat:
        """Auto-detect bank format from CSV headers"""
        
        if not fieldnames:
            return BankFormat.GENERIC
        
        fieldnames_lower = [f.lower() for f in fieldnames]
        
        # Check for Raiffeisen-specific headers
        if any("raiffeisen" in f for f in fieldnames_lower):
            return BankFormat.RAIFFEISEN
        
        # Check for Erste Bank-specific headers
        if "valutadatum" in fieldnames_lower or "belegnummer" in fieldnames_lower:
            return BankFormat.ERSTE_BANK
        
        # Check for Sparkasse-specific headers
        if "buchungstag" in fieldnames_lower:
            return BankFormat.SPARKASSE
        
        # Check for Bank Austria-specific headers
        if "referenznummer" in fieldnames_lower:
            return BankFormat.BANK_AUSTRIA
        
        return BankFormat.GENERIC
    
    def _parse_row(self, row: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """Parse a single CSV row into transaction data"""
        
        # Get column mappings for detected bank format
        mappings = self.BANK_MAPPINGS.get(
            self.bank_format,
            {
                "date": ["date", "datum", "buchungsdatum"],
                "amount": ["amount", "betrag", "umsatz"],
                "description": ["description", "text", "verwendungszweck", "buchungstext"],
                "reference": ["reference", "referenz"],
            }
        )
        
        # Extract date
        date = self._extract_field(row, mappings["date"])
        if not date:
            return None
        parsed_date = self._parse_date(date)
        if not parsed_date:
            return None
        
        # Extract amount
        amount_str = self._extract_field(row, mappings["amount"])
        if not amount_str:
            return None
        amount = self._parse_amount(amount_str)
        if amount is None:
            return None
        
        # Extract description
        description = self._extract_field(row, mappings["description"]) or ""
        
        # Extract reference (optional)
        reference = self._extract_field(row, mappings["reference"])
        
        return {
            "date": parsed_date,
            "amount": amount,
            "description": description.strip(),
            "reference": reference,
            "raw_data": row,
        }
    
    def _extract_field(
        self,
        row: Dict[str, str],
        possible_names: List[str]
    ) -> Optional[str]:
        """Extract field value from row using possible column names"""
        
        # Try exact match first
        for name in possible_names:
            if name in row and row[name]:
                return row[name].strip()
        
        # Try case-insensitive match
        row_lower = {k.lower(): v for k, v in row.items()}
        for name in possible_names:
            name_lower = name.lower()
            if name_lower in row_lower and row_lower[name_lower]:
                return row_lower[name_lower].strip()
        
        return None
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string with multiple format attempts"""
        
        date_str = date_str.strip()
        
        for date_format in self.DATE_FORMATS:
            try:
                return datetime.strptime(date_str, date_format)
            except ValueError:
                continue
        
        return None
    
    def _parse_amount(self, amount_str: str) -> Optional[Decimal]:
        """
        Parse amount string handling Austrian decimal formats
        
        Austrian format: 1.234,56 (thousands separator: ., decimal: ,)
        International format: 1,234.56 (thousands separator: ,, decimal: .)
        """
        
        amount_str = amount_str.strip()
        
        # Remove currency symbols
        amount_str = amount_str.replace("€", "").replace("EUR", "").strip()
        
        # Remove whitespace
        amount_str = amount_str.replace(" ", "")
        
        # Detect format based on last separator
        if "," in amount_str and "." in amount_str:
            # Both separators present
            last_comma = amount_str.rfind(",")
            last_dot = amount_str.rfind(".")
            
            if last_comma > last_dot:
                # Austrian format: 1.234,56
                amount_str = amount_str.replace(".", "").replace(",", ".")
            else:
                # International format: 1,234.56
                amount_str = amount_str.replace(",", "")
        elif "," in amount_str:
            # Only comma - assume Austrian decimal separator
            # Check if it's likely a thousands separator (more than 2 digits after)
            parts = amount_str.split(",")
            if len(parts) == 2 and len(parts[1]) == 2:
                # Likely decimal: 123,45
                amount_str = amount_str.replace(",", ".")
            else:
                # Likely thousands: 1,234
                amount_str = amount_str.replace(",", "")
        elif "." in amount_str:
            # Only dot - could be thousands or decimal
            parts = amount_str.split(".")
            if len(parts) == 2 and len(parts[1]) == 2:
                # Likely decimal: 123.45 (already correct)
                pass
            else:
                # Likely thousands: 1.234
                amount_str = amount_str.replace(".", "")
        
        try:
            return Decimal(amount_str)
        except Exception:
            return None
    
    def validate_csv(self, csv_content: str) -> Dict[str, Any]:
        """
        Validate CSV file before parsing
        
        Returns:
            Dictionary with validation results
        """
        
        try:
            transactions = self.parse(csv_content)
            
            return {
                "valid": True,
                "transaction_count": len(transactions),
                "detected_format": self.bank_format.value if self.bank_format else "unknown",
                "date_range": {
                    "start": min(t["date"] for t in transactions) if transactions else None,
                    "end": max(t["date"] for t in transactions) if transactions else None,
                },
                "total_amount": sum(t["amount"] for t in transactions) if transactions else Decimal("0"),
            }
        except Exception as e:
            return {
                "valid": False,
                "error": str(e),
            }
