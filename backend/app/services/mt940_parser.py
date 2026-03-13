"""
MT940 Parser for Bank Statements

MT940 is a SWIFT standard format for electronic bank statements.
This parser extracts transaction details from MT940 files.

Format specification: SWIFT MT940 (ISO 15022)
"""

import re
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional


class MT940Parser:
    """Parser for MT940 format bank statements"""
    
    def __init__(self):
        """Initialize MT940 parser"""
        self.current_year = datetime.now().year
    
    def parse(self, mt940_content: str) -> List[Dict[str, Any]]:
        """
        Parse MT940 content and extract transactions
        
        Args:
            mt940_content: MT940 file content as string
        
        Returns:
            List of parsed transaction dictionaries
        """
        transactions = []
        
        # Split into individual statements (separated by :20: tag)
        statements = self._split_statements(mt940_content)
        
        for statement in statements:
            statement_transactions = self._parse_statement(statement)
            transactions.extend(statement_transactions)
        
        return transactions
    
    def _split_statements(self, content: str) -> List[str]:
        """Split MT940 content into individual statements"""
        
        # Remove any leading/trailing whitespace
        content = content.strip()
        
        # Split by :20: tag (Transaction Reference Number)
        # Keep the :20: tag with each statement
        parts = re.split(r'(?=:20:)', content)
        
        # Filter out empty parts
        return [part.strip() for part in parts if part.strip()]
    
    def _parse_statement(self, statement: str) -> List[Dict[str, Any]]:
        """Parse a single MT940 statement"""
        
        transactions = []
        
        # Extract statement metadata
        account_number = self._extract_account_number(statement)
        statement_number = self._extract_statement_number(statement)
        opening_balance = self._extract_opening_balance(statement)
        
        # Extract transaction blocks (:61: and :86: tags)
        transaction_blocks = self._extract_transaction_blocks(statement)
        
        for block in transaction_blocks:
            try:
                transaction = self._parse_transaction_block(block)
                if transaction:
                    transaction["account_number"] = account_number
                    transaction["statement_number"] = statement_number
                    transactions.append(transaction)
            except Exception as e:
                print(f"Warning: Failed to parse transaction block: {e}")
                continue
        
        return transactions
    
    def _extract_account_number(self, statement: str) -> Optional[str]:
        """Extract account number from :25: tag"""
        
        match = re.search(r':25:([^\n]+)', statement)
        if match:
            return match.group(1).strip()
        return None
    
    def _extract_statement_number(self, statement: str) -> Optional[str]:
        """Extract statement number from :28C: tag"""
        
        match = re.search(r':28C?:([^\n]+)', statement)
        if match:
            return match.group(1).strip()
        return None
    
    def _extract_opening_balance(self, statement: str) -> Optional[Dict[str, Any]]:
        """Extract opening balance from :60F: tag"""
        
        # :60F:C/D YYMMDD CUR Amount
        match = re.search(r':60F:([CD])(\d{6})([A-Z]{3})([\d,\.]+)', statement)
        if match:
            debit_credit = match.group(1)
            date_str = match.group(2)
            currency = match.group(3)
            amount_str = match.group(4)
            
            return {
                "type": "credit" if debit_credit == "C" else "debit",
                "date": self._parse_short_date(date_str),
                "currency": currency,
                "amount": self._parse_amount(amount_str),
            }
        return None
    
    def _extract_transaction_blocks(self, statement: str) -> List[Dict[str, str]]:
        """
        Extract transaction blocks (pairs of :61: and :86: tags)
        
        :61: = Transaction details (date, amount, type)
        :86: = Additional information (description)
        """
        
        blocks = []
        
        # Find all :61: tags
        transaction_lines = re.findall(r':61:([^\n]+(?:\n(?!:)\S[^\n]+)*)', statement)
        
        # Find all :86: tags
        info_lines = re.findall(r':86:([^\n]+(?:\n(?!:)[^\n]+)*)', statement)
        
        # Pair them up
        for i, trans_line in enumerate(transaction_lines):
            info_line = info_lines[i] if i < len(info_lines) else ""
            blocks.append({
                "transaction": trans_line.strip(),
                "information": info_line.strip(),
            })
        
        return blocks
    
    def _parse_transaction_block(self, block: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """Parse a single transaction block"""
        
        trans_line = block["transaction"]
        info_line = block["information"]
        
        # Parse :61: line
        # Format: YYMMDD[MMDD][C/D][F/R]Amount[Transaction Type][Reference]
        # Example: 2612310101DR1234,56NMSCNONREF
        
        # Extract date (YYMMDD)
        date_match = re.match(r'(\d{6})', trans_line)
        if not date_match:
            return None
        
        date_str = date_match.group(1)
        value_date = self._parse_short_date(date_str)
        
        # Extract debit/credit indicator and amount
        # Look for C or D followed by amount
        amount_match = re.search(r'([CD])([FR]?)([\d,\.]+)', trans_line)
        if not amount_match:
            return None
        
        debit_credit = amount_match.group(1)
        funds_code = amount_match.group(2)  # F=Final, R=Reversal
        amount_str = amount_match.group(3)
        
        amount = self._parse_amount(amount_str)
        
        # Debit transactions are negative
        if debit_credit == "D":
            amount = -amount
        
        # Extract transaction type code (3 letters after amount)
        type_match = re.search(r'([CD][FR]?[\d,\.]+)([A-Z]{3,4})', trans_line)
        transaction_type = type_match.group(2) if type_match else None
        
        # Extract reference
        reference_match = re.search(r'([A-Z]{3,4})(.+)$', trans_line)
        reference = reference_match.group(2).strip() if reference_match else None
        
        # Parse :86: information line
        description = self._parse_information_line(info_line)
        
        return {
            "date": value_date,
            "amount": amount,
            "description": description,
            "reference": reference,
            "transaction_type": transaction_type,
            "debit_credit": "credit" if debit_credit == "C" else "debit",
            "funds_code": funds_code,
            "raw_transaction": trans_line,
            "raw_information": info_line,
        }
    
    def _parse_information_line(self, info_line: str) -> str:
        """
        Parse :86: information line to extract description
        
        Format varies by bank, but typically contains:
        - Structured codes (e.g., ?00, ?10, ?20, etc.)
        - Transaction description
        - Counterparty information
        """
        
        if not info_line:
            return ""
        
        # Remove structured codes (e.g., ?00, ?10, ?20)
        # These are bank-specific codes
        cleaned = re.sub(r'\?\d{2}', ' ', info_line)
        
        # Remove extra whitespace
        cleaned = ' '.join(cleaned.split())
        
        return cleaned.strip()
    
    def _parse_short_date(self, date_str: str) -> datetime:
        """
        Parse short date format (YYMMDD)
        
        Assumes dates are in current century
        """
        
        if len(date_str) != 6:
            raise ValueError(f"Invalid date format: {date_str}")
        
        year = int(date_str[:2])
        month = int(date_str[2:4])
        day = int(date_str[4:6])
        
        # Determine century (assume 2000s for years 00-99)
        # Adjust if year is in the future
        full_year = 2000 + year
        if full_year > self.current_year + 1:
            full_year = 1900 + year
        
        return datetime(full_year, month, day)
    
    def _parse_amount(self, amount_str: str) -> Decimal:
        """
        Parse amount string from MT940 format
        
        MT940 uses comma as decimal separator: 1234,56
        """
        
        # Remove any spaces
        amount_str = amount_str.replace(" ", "")
        
        # Replace comma with dot for Decimal parsing
        amount_str = amount_str.replace(",", ".")
        
        return Decimal(amount_str)
    
    def validate_mt940(self, mt940_content: str) -> Dict[str, Any]:
        """
        Validate MT940 file before parsing
        
        Returns:
            Dictionary with validation results
        """
        
        try:
            # Check for required tags
            required_tags = [":20:", ":25:", ":60F:", ":61:"]
            missing_tags = [tag for tag in required_tags if tag not in mt940_content]
            
            if missing_tags:
                return {
                    "valid": False,
                    "error": f"Missing required tags: {', '.join(missing_tags)}",
                }
            
            # Try to parse
            transactions = self.parse(mt940_content)
            
            return {
                "valid": True,
                "transaction_count": len(transactions),
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
