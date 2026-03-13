"""
Bank Import Service

Handles importing transactions from bank statements (CSV and MT940 formats).
Includes auto-classification and duplicate detection.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional
from enum import Enum

from app.services.csv_parser import CSVParser, BankFormat
from app.services.mt940_parser import MT940Parser
from app.services.transaction_classifier import TransactionClassifier
from app.services.duplicate_detector import DuplicateDetector
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.schemas.transaction import TransactionCreate


class ImportFormat(str, Enum):
    """Supported import formats"""
    CSV = "csv"
    MT940 = "mt940"


class ImportResult:
    """Result of bank import operation"""
    
    def __init__(self):
        self.total_count = 0
        self.imported_count = 0
        self.duplicate_count = 0
        self.error_count = 0
        self.transactions: List[Transaction] = []
        self.duplicates: List[Dict[str, Any]] = []
        self.errors: List[Dict[str, Any]] = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return {
            "total_count": self.total_count,
            "imported_count": self.imported_count,
            "duplicate_count": self.duplicate_count,
            "error_count": self.error_count,
            "transactions": [
                {
                    "id": t.id,
                    "date": t.date.isoformat(),
                    "amount": str(t.amount),
                    "description": t.description,
                    "category": t.income_category or t.expense_category,
                    "classification_confidence": t.classification_confidence,
                }
                for t in self.transactions
            ],
            "duplicates": self.duplicates,
            "errors": self.errors,
        }


class BankImportService:
    """Service for importing bank transactions"""
    
    def __init__(
        self,
        csv_parser: Optional[CSVParser] = None,
        mt940_parser: Optional[MT940Parser] = None,
        classifier: Optional[TransactionClassifier] = None,
        duplicate_detector: Optional[DuplicateDetector] = None,
    ):
        """Initialize bank import service"""
        self.csv_parser = csv_parser or CSVParser()
        self.mt940_parser = mt940_parser or MT940Parser()
        self.classifier = classifier or TransactionClassifier()
        self.duplicate_detector = duplicate_detector or DuplicateDetector()
    
    def import_transactions(
        self,
        file_content: str,
        import_format: ImportFormat,
        user: User,
        tax_year: int,
        auto_classify: bool = True,
        skip_duplicates: bool = True,
        bank_format: Optional[BankFormat] = None,
    ) -> ImportResult:
        """
        Import transactions from bank statement file
        
        Args:
            file_content: File content as string
            import_format: Format of the file (CSV or MT940)
            user: User importing the transactions
            tax_year: Tax year for the transactions
            auto_classify: Whether to auto-classify transactions
            skip_duplicates: Whether to skip duplicate transactions
            bank_format: Specific bank format for CSV (optional)
        
        Returns:
            ImportResult with summary and details
        """
        
        result = ImportResult()
        
        # Parse file based on format
        try:
            if import_format == ImportFormat.CSV:
                if bank_format:
                    self.csv_parser.bank_format = bank_format
                parsed_transactions = self.csv_parser.parse(file_content)
            elif import_format == ImportFormat.MT940:
                parsed_transactions = self.mt940_parser.parse(file_content)
            else:
                raise ValueError(f"Unsupported import format: {import_format}")
        except Exception as e:
            result.error_count = 1
            result.errors.append({
                "error": "Failed to parse file",
                "details": str(e),
            })
            return result
        
        result.total_count = len(parsed_transactions)
        
        # Get existing transactions for duplicate detection
        existing_transactions = self._get_existing_transactions(user.id, tax_year)
        
        # Process each parsed transaction
        for parsed_txn in parsed_transactions:
            try:
                # Check for duplicates
                if skip_duplicates:
                    is_duplicate, duplicate_info = self._check_duplicate(
                        parsed_txn,
                        existing_transactions
                    )
                    
                    if is_duplicate:
                        result.duplicate_count += 1
                        result.duplicates.append({
                            "date": parsed_txn["date"].isoformat(),
                            "amount": str(parsed_txn["amount"]),
                            "description": parsed_txn["description"],
                            "reason": duplicate_info,
                        })
                        continue
                
                # Create transaction
                transaction = self._create_transaction(
                    parsed_txn,
                    user,
                    tax_year,
                    auto_classify
                )
                
                result.imported_count += 1
                result.transactions.append(transaction)
                
                # Add to existing transactions for subsequent duplicate checks
                existing_transactions.append(transaction)
                
            except Exception as e:
                result.error_count += 1
                result.errors.append({
                    "date": parsed_txn.get("date", "").isoformat() if parsed_txn.get("date") else None,
                    "amount": str(parsed_txn.get("amount", "")),
                    "description": parsed_txn.get("description", ""),
                    "error": str(e),
                })
        
        return result
    
    def _get_existing_transactions(
        self,
        user_id: int,
        tax_year: int
    ) -> List[Transaction]:
        """Get existing transactions for duplicate detection"""
        
        # This would query the database
        # For now, return empty list (will be implemented with database integration)
        return []
    
    def _check_duplicate(
        self,
        parsed_txn: Dict[str, Any],
        existing_transactions: List[Transaction]
    ) -> tuple[bool, Optional[str]]:
        """
        Check if parsed transaction is a duplicate
        
        Returns:
            Tuple of (is_duplicate, reason)
        """
        
        # Create a temporary transaction object for duplicate detection
        temp_txn = Transaction(
            date=parsed_txn["date"],
            amount=abs(parsed_txn["amount"]),
            description=parsed_txn["description"],
        )
        
        is_duplicate = self.duplicate_detector.is_duplicate(
            temp_txn,
            existing_transactions
        )
        
        if is_duplicate:
            return True, "Same date, amount, and similar description"
        
        return False, None
    
    def _create_transaction(
        self,
        parsed_txn: Dict[str, Any],
        user: User,
        tax_year: int,
        auto_classify: bool
    ) -> Transaction:
        """Create transaction from parsed data"""
        
        amount = parsed_txn["amount"]
        
        # Determine transaction type based on amount sign
        if amount >= 0:
            transaction_type = TransactionType.INCOME
        else:
            transaction_type = TransactionType.EXPENSE
            amount = abs(amount)  # Store as positive
        
        # Create transaction object
        transaction = Transaction(
            user_id=user.id,
            date=parsed_txn["date"],
            amount=amount,
            description=parsed_txn["description"],
            type=transaction_type,
            tax_year=tax_year,
            reference=parsed_txn.get("reference"),
        )
        
        # Auto-classify if enabled
        if auto_classify:
            classification_result = self.classifier.classify_transaction(
                transaction,
                user_context={
                    "user_type": user.user_type,
                    "user_id": user.id,
                }
            )
            
            if transaction_type == TransactionType.INCOME:
                transaction.income_category = classification_result.category
            else:
                transaction.expense_category = classification_result.category
            
            transaction.is_deductible = classification_result.is_deductible
            transaction.classification_confidence = classification_result.confidence
            transaction.needs_review = classification_result.needs_review
        
        # This would save to database
        # For now, just return the transaction object
        return transaction
    
    def preview_import(
        self,
        file_content: str,
        import_format: ImportFormat,
        bank_format: Optional[BankFormat] = None,
    ) -> Dict[str, Any]:
        """
        Preview import without saving to database
        
        Returns:
            Preview information including transaction count, date range, etc.
        """
        
        try:
            if import_format == ImportFormat.CSV:
                if bank_format:
                    self.csv_parser.bank_format = bank_format
                validation = self.csv_parser.validate_csv(file_content)
            elif import_format == ImportFormat.MT940:
                validation = self.mt940_parser.validate_mt940(file_content)
            else:
                raise ValueError(f"Unsupported import format: {import_format}")
            
            if not validation["valid"]:
                return {
                    "valid": False,
                    "error": validation.get("error", "Unknown error"),
                }
            
            # Parse transactions for preview
            if import_format == ImportFormat.CSV:
                transactions = self.csv_parser.parse(file_content)
            else:
                transactions = self.mt940_parser.parse(file_content)
            
            # Generate preview summary
            income_count = sum(1 for t in transactions if t["amount"] >= 0)
            expense_count = sum(1 for t in transactions if t["amount"] < 0)
            
            total_income = sum(t["amount"] for t in transactions if t["amount"] >= 0)
            total_expenses = sum(abs(t["amount"]) for t in transactions if t["amount"] < 0)
            
            return {
                "valid": True,
                "total_count": len(transactions),
                "income_count": income_count,
                "expense_count": expense_count,
                "total_income": str(total_income),
                "total_expenses": str(total_expenses),
                "date_range": {
                    "start": min(t["date"] for t in transactions).isoformat() if transactions else None,
                    "end": max(t["date"] for t in transactions).isoformat() if transactions else None,
                },
                "detected_format": validation.get("detected_format"),
                "sample_transactions": [
                    {
                        "date": t["date"].isoformat(),
                        "amount": str(t["amount"]),
                        "description": t["description"],
                    }
                    for t in transactions[:5]  # Show first 5 transactions
                ],
            }
        except Exception as e:
            return {
                "valid": False,
                "error": str(e),
            }
