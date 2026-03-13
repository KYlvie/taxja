"""
Unit tests for SaldenlisteImportService.
Tests import functionality, transaction creation, account mapping, and multi-year continuity.
"""
import csv
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models.historical_import import (
    HistoricalImportUpload,
    ImportStatus,
    HistoricalDocumentType,
)
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.models.user import User, UserType
from app.services.saldenliste_import_service import SaldenlisteImportService
from app.services.saldenliste_parser import AccountBalance
from app.services.saldenliste_service import KONTENPLAN_EA, KONTENPLAN_GMBH


@pytest.fixture
def db_session(mocker):
    """Mock database session."""
    return mocker.MagicMock(spec=Session)


@pytest.fixture
def import_service(db_session):
    """Create a SaldenlisteImportService instance."""
    return SaldenlisteImportService(db_session)


@pytest.fixture
def test_user_ea():
    """Create a test EA user."""
    user = User(
        id=1,
        name="Test EA User",
        email="ea@test.com",
        user_type=UserType.SELF_EMPLOYED,
    )
    return user


@pytest.fixture
def test_user_gmbh():
    """Create a test GmbH user."""
    user = User(
        id=2,
        name="Test GmbH User",
        email="gmbh@test.com",
        user_type=UserType.GMBH,
    )
    return user


@pytest.fixture
def sample_csv_file():
    """Create a temporary CSV file with sample Saldenliste data."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Konto", "Bezeichnung", "Saldo"])
        writer.writerow(["4000", "Einkünfte aus Land- und Forstwirtschaft", "10000.00"])
        writer.writerow(["4400", "Einkünfte aus nichtselbständiger Arbeit", "50000.00"])
        writer.writerow(["7010", "Aufwendungen für Material und Waren", "5000.00"])
        writer.writerow(["7100", "Rechts- und Beratungsaufwand", "2000.00"])
        return f.name


class TestSaldenlisteImportService:
    """Test suite for SaldenlisteImportService."""

    def test_import_saldenliste_success(self, import_service, db_session, test_user_ea, sample_csv_file):
        """Test successful Saldenliste import."""
        # Mock database queries
        db_session.query.return_value.filter.return_value.first.return_value = test_user_ea
        db_session.commit.return_value = None
        
        # Perform import
        result = import_service.import_saldenliste(
            file_path=sample_csv_file,
            user_id=test_user_ea.id,
            tax_year=2023,
        )
        
        # Verify results
        assert "transactions_created" in result
        assert "accounts_imported" in result
        assert "accounts_unmapped" in result
        assert "confidence" in result
        assert result["accounts_imported"] > 0
        assert result["confidence"] > 0.0
        
        # Cleanup
        Path(sample_csv_file).unlink()

    def test_import_saldenliste_user_not_found(self, import_service, db_session, sample_csv_file):
        """Test import fails when user not found."""
        # Mock database query to return None
        db_session.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(ValueError, match="User not found"):
            import_service.import_saldenliste(
                file_path=sample_csv_file,
                user_id=999,
                tax_year=2023,
            )
        
        # Cleanup
        Path(sample_csv_file).unlink()

    def test_import_saldenliste_invalid_file_format(self, import_service, db_session, test_user_ea):
        """Test import fails with unsupported file format."""
        # Mock database query
        db_session.query.return_value.filter.return_value.first.return_value = test_user_ea
        
        with pytest.raises(ValueError, match="Unsupported file format"):
            import_service.import_saldenliste(
                file_path="test.txt",
                user_id=test_user_ea.id,
                tax_year=2023,
            )

    def test_create_opening_balance_transactions(self, import_service, db_session, test_user_ea):
        """Test creation of opening balance transactions."""
        # Prepare account data
        accounts = [
            {
                "account_number": "4000",
                "account_name": "Agriculture Income",
                "balance": Decimal("10000.00"),
                "account_def": KONTENPLAN_EA[0],  # Agriculture income account
            },
            {
                "account_number": "7010",
                "account_name": "Material Expenses",
                "balance": Decimal("5000.00"),
                "account_def": KONTENPLAN_EA[7],  # Material expenses account
            },
        ]
        
        # Mock database operations
        db_session.add.return_value = None
        db_session.commit.return_value = None
        
        # Create transactions
        transactions = import_service.create_opening_balance_transactions(
            accounts=accounts,
            user_id=test_user_ea.id,
            tax_year=2023,
        )
        
        # Verify transactions
        assert len(transactions) == 2
        
        # Check income transaction
        income_txn = transactions[0]
        assert income_txn.type == TransactionType.INCOME
        assert income_txn.amount == Decimal("10000.00")
        assert income_txn.transaction_date == date(2023, 1, 1)
        assert income_txn.income_category == IncomeCategory.AGRICULTURE
        assert income_txn.import_source == "saldenliste"
        assert income_txn.is_system_generated is True
        
        # Check expense transaction
        expense_txn = transactions[1]
        assert expense_txn.type == TransactionType.EXPENSE
        assert expense_txn.amount == Decimal("5000.00")
        assert expense_txn.expense_category == ExpenseCategory.GROCERIES

    def test_create_opening_balance_transactions_skip_zero_balance(self, import_service, db_session, test_user_ea):
        """Test that accounts with zero balance are skipped."""
        accounts = [
            {
                "account_number": "4000",
                "account_name": "Agriculture Income",
                "balance": Decimal("0.00"),
                "account_def": KONTENPLAN_EA[0],
            },
        ]
        
        db_session.commit.return_value = None
        
        transactions = import_service.create_opening_balance_transactions(
            accounts=accounts,
            user_id=test_user_ea.id,
            tax_year=2023,
        )
        
        # Should create no transactions for zero balance
        assert len(transactions) == 0

    def test_map_accounts_to_kontenplan_exact_match(self, import_service):
        """Test account mapping with exact account number match."""
        accounts = [
            AccountBalance(
                account_number="4000",
                account_name="Agriculture Income",
                balance=Decimal("10000.00"),
                kontenklasse=4,
            ),
        ]
        
        mapped, unmapped = import_service._map_accounts_to_kontenplan(
            accounts, KONTENPLAN_EA
        )
        
        assert len(mapped) == 1
        assert len(unmapped) == 0
        assert mapped[0]["account_number"] == "4000"
        assert mapped[0]["account_def"].konto == "4000"

    def test_map_accounts_to_kontenplan_fuzzy_match(self, import_service):
        """Test account mapping with fuzzy match by Kontenklasse."""
        accounts = [
            AccountBalance(
                account_number="4999",  # Non-standard account in Kontenklasse 4
                account_name="Other Income",
                balance=Decimal("5000.00"),
                kontenklasse=4,
            ),
        ]
        
        mapped, unmapped = import_service._map_accounts_to_kontenplan(
            accounts, KONTENPLAN_EA
        )
        
        # Should map to first account in Kontenklasse 4
        assert len(mapped) == 1
        assert mapped[0]["account_def"].kontenklasse == 4

    def test_map_accounts_to_kontenplan_unmapped(self, import_service):
        """Test account mapping with unmappable accounts."""
        accounts = [
            AccountBalance(
                account_number="9999",
                account_name="Unknown Account",
                balance=Decimal("1000.00"),
                kontenklasse=None,  # No Kontenklasse
            ),
        ]
        
        mapped, unmapped = import_service._map_accounts_to_kontenplan(
            accounts, KONTENPLAN_EA
        )
        
        assert len(mapped) == 0
        assert len(unmapped) == 1
        assert unmapped[0].account_number == "9999"

    def test_determine_transaction_type_income(self, import_service):
        """Test transaction type determination for income accounts."""
        account_def = KONTENPLAN_EA[0]  # Agriculture income (Kontenklasse 4)
        balance = Decimal("10000.00")
        
        txn_type, income_cat, expense_cat = import_service._determine_transaction_type(
            account_def, balance
        )
        
        assert txn_type == TransactionType.INCOME
        assert income_cat == IncomeCategory.AGRICULTURE
        assert expense_cat is None

    def test_determine_transaction_type_expense(self, import_service):
        """Test transaction type determination for expense accounts."""
        account_def = KONTENPLAN_EA[7]  # Material expenses (Kontenklasse 7)
        balance = Decimal("5000.00")
        
        txn_type, income_cat, expense_cat = import_service._determine_transaction_type(
            account_def, balance
        )
        
        assert txn_type == TransactionType.EXPENSE
        assert income_cat is None
        assert expense_cat == ExpenseCategory.GROCERIES

    def test_determine_transaction_type_balance_sheet_positive(self, import_service):
        """Test transaction type for balance sheet accounts with positive balance."""
        account_def = KONTENPLAN_GMBH[0]  # Assets (Kontenklasse 0)
        balance = Decimal("10000.00")
        
        txn_type, income_cat, expense_cat = import_service._determine_transaction_type(
            account_def, balance
        )
        
        # Positive balance sheet account treated as income
        assert txn_type == TransactionType.INCOME
        assert income_cat == IncomeCategory.OTHER_INCOME

    def test_determine_transaction_type_balance_sheet_negative(self, import_service):
        """Test transaction type for balance sheet accounts with negative balance."""
        account_def = KONTENPLAN_GMBH[0]  # Assets (Kontenklasse 0)
        balance = Decimal("-5000.00")
        
        txn_type, income_cat, expense_cat = import_service._determine_transaction_type(
            account_def, balance
        )
        
        # Negative balance sheet account treated as expense
        assert txn_type == TransactionType.EXPENSE
        assert expense_cat == ExpenseCategory.OTHER

    def test_validate_multi_year_continuity_valid(self, import_service, db_session):
        """Test multi-year continuity validation with valid data."""
        # Mock closing balance for 2022
        db_session.query.return_value.filter.return_value.scalar.side_effect = [
            Decimal("10000.00"),  # Income 2022
            Decimal("5000.00"),   # Expense 2022
            Decimal("5000.00"),   # Income opening 2023
            Decimal("0.00"),      # Expense opening 2023
        ]
        
        result = import_service.validate_multi_year_continuity(
            user_id=1,
            years=[2022, 2023],
        )
        
        assert result["valid"] is True
        assert len(result["discrepancies"]) == 0

    def test_validate_multi_year_continuity_discrepancy(self, import_service, db_session):
        """Test multi-year continuity validation with discrepancy."""
        # Mock mismatched balances
        db_session.query.return_value.filter.return_value.scalar.side_effect = [
            Decimal("10000.00"),  # Income 2022
            Decimal("5000.00"),   # Expense 2022
            Decimal("4000.00"),   # Income opening 2023 (mismatch!)
            Decimal("0.00"),      # Expense opening 2023
        ]
        
        result = import_service.validate_multi_year_continuity(
            user_id=1,
            years=[2022, 2023],
        )
        
        assert result["valid"] is False
        assert len(result["discrepancies"]) == 1
        assert result["discrepancies"][0]["year_n"] == 2022
        assert result["discrepancies"][0]["year_n_plus_1"] == 2023

    def test_validate_multi_year_continuity_non_consecutive(self, import_service, db_session):
        """Test multi-year continuity validation with non-consecutive years."""
        result = import_service.validate_multi_year_continuity(
            user_id=1,
            years=[2020, 2023],  # Non-consecutive
        )
        
        assert result["valid"] is False
        assert len(result["discrepancies"]) == 1
        assert "not consecutive" in result["discrepancies"][0]["issue"]

    def test_validate_multi_year_continuity_single_year(self, import_service, db_session):
        """Test multi-year continuity validation with single year."""
        result = import_service.validate_multi_year_continuity(
            user_id=1,
            years=[2023],
        )
        
        assert result["valid"] is True
        assert len(result["discrepancies"]) == 0
        assert "at least 2 years" in result["message"]

    def test_update_upload_error(self, import_service, db_session):
        """Test updating HistoricalImportUpload with error."""
        upload_id = uuid4()
        upload = HistoricalImportUpload(
            id=upload_id,
            user_id=1,
            document_id=1,
            document_type=HistoricalDocumentType.SALDENLISTE,
            tax_year=2023,
            status=ImportStatus.PROCESSING,
            errors=[],
        )
        
        db_session.query.return_value.filter.return_value.first.return_value = upload
        db_session.commit.return_value = None
        
        import_service._update_upload_error(upload_id, "Test error message")
        
        assert upload.status == ImportStatus.FAILED
        assert len(upload.errors) == 1
        assert upload.errors[0]["type"] == "parsing_error"
        assert "Test error message" in upload.errors[0]["message"]

    def test_update_upload_success_high_confidence(self, import_service, db_session):
        """Test updating HistoricalImportUpload with successful import (high confidence)."""
        from app.services.saldenliste_parser import SaldenlisteData, SaldenlisteFormat
        
        upload_id = uuid4()
        upload = HistoricalImportUpload(
            id=upload_id,
            user_id=1,
            document_id=1,
            document_type=HistoricalDocumentType.SALDENLISTE,
            tax_year=2023,
            status=ImportStatus.PROCESSING,
            errors=[],
        )
        
        db_session.query.return_value.filter.return_value.first.return_value = upload
        db_session.commit.return_value = None
        
        saldenliste_data = SaldenlisteData(
            tax_year=2023,
            company_name="Test Company",
            accounts=[],
            confidence=0.95,
            format_detected=SaldenlisteFormat.BMD,
        )
        
        transactions = []
        unmapped_accounts = []
        
        import_service._update_upload_success(
            upload_id, saldenliste_data, transactions, unmapped_accounts
        )
        
        assert upload.status == ImportStatus.APPROVED
        assert upload.extraction_confidence == Decimal("0.95")
        assert upload.requires_review is False

    def test_update_upload_success_low_confidence(self, import_service, db_session):
        """Test updating HistoricalImportUpload with low confidence (requires review)."""
        from app.services.saldenliste_parser import SaldenlisteData, SaldenlisteFormat
        
        upload_id = uuid4()
        upload = HistoricalImportUpload(
            id=upload_id,
            user_id=1,
            document_id=1,
            document_type=HistoricalDocumentType.SALDENLISTE,
            tax_year=2023,
            status=ImportStatus.PROCESSING,
            errors=[],
        )
        
        db_session.query.return_value.filter.return_value.first.return_value = upload
        db_session.commit.return_value = None
        
        saldenliste_data = SaldenlisteData(
            tax_year=2023,
            company_name="Test Company",
            accounts=[],
            confidence=0.5,  # Low confidence
            format_detected=SaldenlisteFormat.CUSTOM,
        )
        
        transactions = []
        unmapped_accounts = []
        
        import_service._update_upload_success(
            upload_id, saldenliste_data, transactions, unmapped_accounts
        )
        
        assert upload.status == ImportStatus.REVIEW_REQUIRED
        assert upload.requires_review is True

    def test_update_upload_success_with_unmapped_accounts(self, import_service, db_session):
        """Test updating HistoricalImportUpload with unmapped accounts."""
        from app.services.saldenliste_parser import SaldenlisteData, SaldenlisteFormat, AccountBalance
        
        upload_id = uuid4()
        upload = HistoricalImportUpload(
            id=upload_id,
            user_id=1,
            document_id=1,
            document_type=HistoricalDocumentType.SALDENLISTE,
            tax_year=2023,
            status=ImportStatus.PROCESSING,
            errors=[],
        )
        
        db_session.query.return_value.filter.return_value.first.return_value = upload
        db_session.commit.return_value = None
        
        saldenliste_data = SaldenlisteData(
            tax_year=2023,
            company_name="Test Company",
            accounts=[],
            confidence=0.95,
            format_detected=SaldenlisteFormat.BMD,
        )
        
        transactions = []
        unmapped_accounts = [
            AccountBalance(
                account_number="9999",
                account_name="Unknown Account",
                balance=Decimal("1000.00"),
                kontenklasse=None,
            )
        ]
        
        import_service._update_upload_success(
            upload_id, saldenliste_data, transactions, unmapped_accounts
        )
        
        assert upload.status == ImportStatus.REVIEW_REQUIRED
        assert upload.requires_review is True
        assert len(upload.errors) == 1
        assert upload.errors[0]["type"] == "unmapped_accounts"

    def test_get_year_closing_balance(self, import_service, db_session):
        """Test getting year closing balance."""
        # Mock database queries
        db_session.query.return_value.filter.return_value.scalar.side_effect = [
            Decimal("50000.00"),  # Income sum
            Decimal("30000.00"),  # Expense sum
        ]
        
        closing_balance = import_service._get_year_closing_balance(user_id=1, year=2023)
        
        assert closing_balance == Decimal("20000.00")  # 50000 - 30000

    def test_get_year_opening_balance(self, import_service, db_session):
        """Test getting year opening balance."""
        # Mock database queries
        db_session.query.return_value.filter.return_value.scalar.side_effect = [
            Decimal("10000.00"),  # Income opening
            Decimal("5000.00"),   # Expense opening
        ]
        
        opening_balance = import_service._get_year_opening_balance(user_id=1, year=2023)
        
        assert opening_balance == Decimal("5000.00")  # 10000 - 5000

    def test_import_saldenliste_with_upload_id(self, import_service, db_session, test_user_ea, sample_csv_file):
        """Test Saldenliste import with HistoricalImportUpload tracking."""
        upload_id = uuid4()
        upload = HistoricalImportUpload(
            id=upload_id,
            user_id=test_user_ea.id,
            document_id=1,
            document_type=HistoricalDocumentType.SALDENLISTE,
            tax_year=2023,
            status=ImportStatus.PROCESSING,
            errors=[],
        )
        
        # Mock database queries
        db_session.query.return_value.filter.return_value.first.side_effect = [
            test_user_ea,  # User query
            upload,        # Upload query for update
        ]
        db_session.commit.return_value = None
        
        result = import_service.import_saldenliste(
            file_path=sample_csv_file,
            user_id=test_user_ea.id,
            tax_year=2023,
            upload_id=upload_id,
        )
        
        assert "transactions_created" in result
        assert result["accounts_imported"] > 0
        
        # Cleanup
        Path(sample_csv_file).unlink()
