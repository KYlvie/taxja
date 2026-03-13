"""
Saldenliste Import Service
Imports Saldenliste balance list data and creates opening balance transactions.
Supports multi-year continuity validation.
"""
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.historical_import import HistoricalImportUpload, ImportStatus
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.models.user import User, UserType
from app.services.saldenliste_parser import SaldenlisteParser, SaldenlisteData, AccountBalance
from app.services.saldenliste_service import (
    get_account_plan,
    KONTENPLAN_EA,
    KONTENPLAN_GMBH,
    AccountDef,
)


class SaldenlisteImportService:
    """Import Saldenliste balance list data into the system."""

    def __init__(self, db: Session):
        self.db = db
        self.parser = SaldenlisteParser()

    def import_saldenliste(
        self,
        file_path: str,
        user_id: int,
        tax_year: int,
        upload_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Import Saldenliste and create opening balance transactions.

        Args:
            file_path: Path to the Saldenliste file (CSV or Excel)
            user_id: User ID for the import
            tax_year: Tax year for the Saldenliste
            upload_id: Optional HistoricalImportUpload ID for tracking

        Returns:
            Dict with import results:
            - transactions_created: List of transaction IDs
            - accounts_imported: Number of accounts imported
            - accounts_unmapped: Number of accounts that couldn't be mapped
            - unmapped_accounts: List of unmapped account details
            - confidence: Overall confidence score
            - errors: List of error messages

        Raises:
            ValueError: If file cannot be parsed or user not found
        """
        # Get user
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User not found: {user_id}")

        # Parse the file
        path = Path(file_path)
        suffix = path.suffix.lower()

        try:
            if suffix == ".csv":
                saldenliste_data = self.parser.parse_csv(file_path, tax_year)
            elif suffix in [".xlsx", ".xls"]:
                saldenliste_data = self.parser.parse_excel(file_path, tax_year)
            else:
                raise ValueError(f"Unsupported file format: {suffix}")
        except Exception as e:
            error_msg = f"Failed to parse Saldenliste file: {str(e)}"
            if upload_id:
                self._update_upload_error(upload_id, error_msg)
            raise ValueError(error_msg) from e

        # Map accounts to Kontenplan
        account_plan = get_account_plan(user.user_type)
        mapped_accounts, unmapped_accounts = self._map_accounts_to_kontenplan(
            saldenliste_data.accounts, account_plan
        )

        # Create opening balance transactions
        transactions = self.create_opening_balance_transactions(
            mapped_accounts, user_id, tax_year
        )

        # Update HistoricalImportUpload if provided
        if upload_id:
            self._update_upload_success(
                upload_id,
                saldenliste_data,
                transactions,
                unmapped_accounts,
            )

        return {
            "transactions_created": [txn.id for txn in transactions],
            "accounts_imported": len(mapped_accounts),
            "accounts_unmapped": len(unmapped_accounts),
            "unmapped_accounts": [
                {
                    "account_number": acc.account_number,
                    "account_name": acc.account_name,
                    "balance": float(acc.balance),
                }
                for acc in unmapped_accounts
            ],
            "confidence": saldenliste_data.confidence,
            "errors": [],
        }

    def create_opening_balance_transactions(
        self, accounts: List[Dict[str, Any]], user_id: int, tax_year: int
    ) -> List[Transaction]:
        """
        Create transactions to establish opening balances for accounts.

        Args:
            accounts: List of account dicts with mapped Kontenplan data
            user_id: User ID for the transactions
            tax_year: Tax year for the transactions

        Returns:
            List of created Transaction objects
        """
        transactions = []
        opening_date = date(tax_year, 1, 1)

        for account_data in accounts:
            balance = account_data["balance"]
            account_def = account_data["account_def"]

            # Skip accounts with zero balance
            if balance == Decimal("0"):
                continue

            # Determine transaction type and category based on account definition
            txn_type, income_cat, expense_cat = self._determine_transaction_type(
                account_def, balance
            )

            # Create transaction
            transaction = Transaction(
                user_id=user_id,
                type=txn_type,
                amount=abs(balance),
                transaction_date=opening_date,
                description=f"Opening balance: {account_def.label_de} ({account_def.konto})",
                income_category=income_cat,
                expense_category=expense_cat,
                is_deductible=False,
                is_system_generated=True,
                import_source="saldenliste",
                classification_confidence=Decimal("1.0"),
                needs_review=False,
            )

            self.db.add(transaction)
            transactions.append(transaction)

        # Commit all transactions
        self.db.commit()

        return transactions

    def validate_multi_year_continuity(
        self, user_id: int, years: List[int]
    ) -> Dict[str, Any]:
        """
        Validate multi-year continuity: closing balance of year N should equal
        opening balance of year N+1.

        Args:
            user_id: User ID to validate
            years: List of years to validate (should be consecutive)

        Returns:
            Dict with validation results:
            - valid: Boolean indicating if continuity is valid
            - discrepancies: List of discrepancies found
            - message: Human-readable message
        """
        if len(years) < 2:
            return {
                "valid": True,
                "discrepancies": [],
                "message": "Need at least 2 years to validate continuity",
            }

        # Sort years
        sorted_years = sorted(years)

        discrepancies = []

        for i in range(len(sorted_years) - 1):
            year_n = sorted_years[i]
            year_n_plus_1 = sorted_years[i + 1]

            # Check if years are consecutive
            if year_n_plus_1 != year_n + 1:
                discrepancies.append(
                    {
                        "year_n": year_n,
                        "year_n_plus_1": year_n_plus_1,
                        "issue": "Years are not consecutive",
                    }
                )
                continue

            # Get closing balance for year N (sum of all transactions in year N)
            closing_balance_n = self._get_year_closing_balance(user_id, year_n)

            # Get opening balance for year N+1 (transactions on Jan 1 of year N+1)
            opening_balance_n_plus_1 = self._get_year_opening_balance(
                user_id, year_n_plus_1
            )

            # Compare balances (allow small rounding differences)
            difference = abs(closing_balance_n - opening_balance_n_plus_1)
            tolerance = Decimal("0.01")  # 1 cent tolerance

            if difference > tolerance:
                discrepancies.append(
                    {
                        "year_n": year_n,
                        "year_n_plus_1": year_n_plus_1,
                        "closing_balance_n": float(closing_balance_n),
                        "opening_balance_n_plus_1": float(opening_balance_n_plus_1),
                        "difference": float(difference),
                        "issue": "Closing balance does not match opening balance",
                    }
                )

        valid = len(discrepancies) == 0

        return {
            "valid": valid,
            "discrepancies": discrepancies,
            "message": (
                "Multi-year continuity validated successfully"
                if valid
                else f"Found {len(discrepancies)} continuity discrepancies"
            ),
        }

    def _map_accounts_to_kontenplan(
        self, accounts: List[AccountBalance], account_plan: List[AccountDef]
    ) -> tuple[List[Dict[str, Any]], List[AccountBalance]]:
        """
        Map imported accounts to the Kontenplan (EA or GmbH based on user type).

        Args:
            accounts: List of AccountBalance from parsed Saldenliste
            account_plan: The Kontenplan to map to (EA or GmbH)

        Returns:
            Tuple of (mapped_accounts, unmapped_accounts)
            - mapped_accounts: List of dicts with account data and matched AccountDef
            - unmapped_accounts: List of AccountBalance that couldn't be mapped
        """
        mapped = []
        unmapped = []

        # Create lookup dict for account plan by account number
        account_plan_dict = {acct.konto: acct for acct in account_plan}

        for account in accounts:
            # Try exact match first
            account_def = account_plan_dict.get(account.account_number)

            if account_def:
                mapped.append(
                    {
                        "account_number": account.account_number,
                        "account_name": account.account_name,
                        "balance": account.balance,
                        "account_def": account_def,
                    }
                )
            else:
                # Try fuzzy matching by Kontenklasse
                if account.kontenklasse is not None:
                    # Find first account in the same Kontenklasse
                    for acct_def in account_plan:
                        if acct_def.kontenklasse == account.kontenklasse:
                            mapped.append(
                                {
                                    "account_number": account.account_number,
                                    "account_name": account.account_name,
                                    "balance": account.balance,
                                    "account_def": acct_def,
                                }
                            )
                            break
                    else:
                        # No match found in Kontenklasse
                        unmapped.append(account)
                else:
                    # No Kontenklasse, cannot map
                    unmapped.append(account)

        return mapped, unmapped

    def _determine_transaction_type(
        self, account_def: AccountDef, balance: Decimal
    ) -> tuple[TransactionType, Optional[IncomeCategory], Optional[ExpenseCategory]]:
        """
        Determine transaction type and category based on account definition and balance.

        Args:
            account_def: The AccountDef from Kontenplan
            balance: The account balance

        Returns:
            Tuple of (transaction_type, income_category, expense_category)
        """
        # Kontenklasse 4 = Income (Erträge)
        if account_def.kontenklasse == 4:
            # Use the first income category if available
            income_cat = (
                account_def.income_categories[0]
                if account_def.income_categories
                else IncomeCategory.OTHER_INCOME
            )
            return TransactionType.INCOME, income_cat, None

        # Kontenklasse 5, 6, 7, 8 = Expenses (Aufwendungen)
        if account_def.kontenklasse in [5, 6, 7, 8]:
            # Use the first expense category if available
            expense_cat = (
                account_def.expense_categories[0]
                if account_def.expense_categories
                else ExpenseCategory.OTHER
            )
            return TransactionType.EXPENSE, None, expense_cat

        # For balance sheet accounts (0, 1, 2, 3, 9), determine by balance sign
        # Positive balance = asset/income, negative = liability/expense
        if balance >= 0:
            return TransactionType.INCOME, IncomeCategory.OTHER_INCOME, None
        else:
            return TransactionType.EXPENSE, None, ExpenseCategory.OTHER

    def _get_year_closing_balance(self, user_id: int, year: int) -> Decimal:
        """
        Get the closing balance for a year (sum of all transactions in that year).

        Args:
            user_id: User ID
            year: Tax year

        Returns:
            Closing balance as Decimal
        """
        from sqlalchemy import extract, func

        # Sum all income transactions
        income_sum = (
            self.db.query(func.coalesce(func.sum(Transaction.amount), 0))
            .filter(
                Transaction.user_id == user_id,
                Transaction.type == TransactionType.INCOME,
                extract("year", Transaction.transaction_date) == year,
            )
            .scalar()
        )

        # Sum all expense transactions
        expense_sum = (
            self.db.query(func.coalesce(func.sum(Transaction.amount), 0))
            .filter(
                Transaction.user_id == user_id,
                Transaction.type == TransactionType.EXPENSE,
                extract("year", Transaction.transaction_date) == year,
            )
            .scalar()
        )

        # Closing balance = income - expenses
        return Decimal(str(income_sum)) - Decimal(str(expense_sum))

    def _get_year_opening_balance(self, user_id: int, year: int) -> Decimal:
        """
        Get the opening balance for a year (sum of opening balance transactions on Jan 1).

        Args:
            user_id: User ID
            year: Tax year

        Returns:
            Opening balance as Decimal
        """
        from sqlalchemy import func

        opening_date = date(year, 1, 1)

        # Sum all income opening balance transactions
        income_sum = (
            self.db.query(func.coalesce(func.sum(Transaction.amount), 0))
            .filter(
                Transaction.user_id == user_id,
                Transaction.type == TransactionType.INCOME,
                Transaction.transaction_date == opening_date,
                Transaction.import_source == "saldenliste",
            )
            .scalar()
        )

        # Sum all expense opening balance transactions
        expense_sum = (
            self.db.query(func.coalesce(func.sum(Transaction.amount), 0))
            .filter(
                Transaction.user_id == user_id,
                Transaction.type == TransactionType.EXPENSE,
                Transaction.transaction_date == opening_date,
                Transaction.import_source == "saldenliste",
            )
            .scalar()
        )

        # Opening balance = income - expenses
        return Decimal(str(income_sum)) - Decimal(str(expense_sum))

    def _update_upload_error(self, upload_id: UUID, error_msg: str) -> None:
        """Update HistoricalImportUpload with error information."""
        upload = (
            self.db.query(HistoricalImportUpload)
            .filter(HistoricalImportUpload.id == upload_id)
            .first()
        )
        if upload:
            upload.status = ImportStatus.FAILED
            upload.errors = upload.errors or []
            upload.errors.append(
                {"type": "parsing_error", "message": error_msg, "timestamp": str(date.today())}
            )
            self.db.commit()

    def _update_upload_success(
        self,
        upload_id: UUID,
        saldenliste_data: SaldenlisteData,
        transactions: List[Transaction],
        unmapped_accounts: List[AccountBalance],
    ) -> None:
        """Update HistoricalImportUpload with success information."""
        upload = (
            self.db.query(HistoricalImportUpload)
            .filter(HistoricalImportUpload.id == upload_id)
            .first()
        )
        if upload:
            # Determine if review is required
            requires_review = (
                saldenliste_data.confidence < 0.7 or len(unmapped_accounts) > 0
            )

            upload.status = (
                ImportStatus.REVIEW_REQUIRED if requires_review else ImportStatus.APPROVED
            )
            upload.extraction_confidence = Decimal(str(saldenliste_data.confidence))
            upload.extracted_data = {
                "tax_year": saldenliste_data.tax_year,
                "company_name": saldenliste_data.company_name,
                "accounts_count": len(saldenliste_data.accounts),
                "format_detected": saldenliste_data.format_detected.value,
            }
            upload.transactions_created = [txn.id for txn in transactions]
            upload.requires_review = requires_review

            if unmapped_accounts:
                upload.errors = upload.errors or []
                upload.errors.append(
                    {
                        "type": "unmapped_accounts",
                        "message": f"{len(unmapped_accounts)} accounts could not be mapped to Kontenplan",
                        "accounts": [
                            {
                                "account_number": acc.account_number,
                                "account_name": acc.account_name,
                                "balance": float(acc.balance),
                            }
                            for acc in unmapped_accounts
                        ],
                    }
                )

            self.db.commit()
