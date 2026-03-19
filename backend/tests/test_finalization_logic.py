"""
Tests for historical import finalization logic (Task 5.2)

Tests verify that the finalization logic:
1. Uses edited_data if available, otherwise uses extracted_data
2. Creates actual transaction records in the database
3. Links properties to transactions based on property linking suggestions
4. Marks transactions as reviewed and locked to prevent automatic modifications
5. Updates user profile with tax information (tax number, family status, etc.)
"""

import pytest
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from app.models.historical_import import (
    HistoricalImportSession,
    HistoricalImportUpload,
    ImportStatus,
    HistoricalDocumentType,
)
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.models.user import User, UserType
from app.models.property import Property, PropertyType
from app.models.document import Document, DocumentType
from app.services.historical_import_orchestrator import HistoricalImportOrchestrator


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    user = User(
        email="test@example.com",
        password_hash="hashed_password",
        name="Test User",
        user_type=UserType.EMPLOYEE,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_property(db_session, test_user):
    """Create a test property"""
    prop = Property(
        user_id=test_user.id,
        property_type=PropertyType.RENTAL,
        address="Teststrasse 1, 1010 Wien",
        street="Teststrasse 1",
        city="Wien",
        postal_code="1010",
        purchase_date=date(2020, 1, 1),
        purchase_price=Decimal("300000.00"),
        building_value=Decimal("200000.00"),
        land_value=Decimal("100000.00"),
    )
    db_session.add(prop)
    db_session.commit()
    db_session.refresh(prop)
    return prop


@pytest.fixture
def orchestrator(db_session):
    """Create orchestrator instance"""
    return HistoricalImportOrchestrator(db_session)


def _create_document(
    db_session,
    *,
    user_id: int,
    document_type: DocumentType,
    file_name: str,
) -> Document:
    document = Document(
        user_id=user_id,
        document_type=document_type,
        file_path=f"historical-import/{file_name}",
        file_name=file_name,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document


class TestFinalizeE1Form:
    """Tests for E1 form finalization"""

    def test_finalize_with_extracted_data(self, orchestrator, test_user, db_session):
        """Test finalization using extracted_data (no edits)"""
        document = _create_document(
            db_session,
            user_id=test_user.id,
            document_type=DocumentType.E1_FORM,
            file_name="e1-extracted.pdf",
        )
        # Create upload with extracted data
        upload = HistoricalImportUpload(
            user_id=test_user.id,
            document_id=document.id,
            document_type=HistoricalDocumentType.E1_FORM,
            tax_year=2023,
            status=ImportStatus.REVIEW_REQUIRED,
            extracted_data={
                "tax_year": 2023,
                "steuernummer": "12-345/6789",
                "all_kz_values": {
                    "kz_245": 50000.00,  # Employment income
                    "kz_350": 12000.00,  # Rental income
                    "kz_260": 1000.00,   # Werbungskosten
                },
            },
            extraction_confidence=Decimal("0.85"),
            requires_review=False,
        )
        db_session.add(upload)
        db_session.commit()
        db_session.refresh(upload)

        # Finalize the upload
        result = orchestrator._finalize_upload(upload)

        # Verify transactions were created
        assert result["transactions_created"] == 3
        assert result["properties_created"] == 0
        assert result["properties_linked"] == 0

        # Verify transactions in database
        transactions = db_session.query(Transaction).filter(
            Transaction.user_id == test_user.id
        ).all()
        assert len(transactions) == 3

        # Verify all transactions are marked as reviewed and locked
        for txn in transactions:
            assert txn.reviewed is True
            assert txn.locked is True
            assert txn.import_source == "e1_import"

        # Verify employment income transaction
        employment_txn = next(
            (t for t in transactions if t.income_category == IncomeCategory.EMPLOYMENT), None
        )
        assert employment_txn is not None
        assert employment_txn.type == TransactionType.INCOME
        assert employment_txn.amount == Decimal("50000.00")

        # Verify rental income transaction
        rental_txn = next(
            (t for t in transactions if t.income_category == IncomeCategory.RENTAL), None
        )
        assert rental_txn is not None
        assert rental_txn.type == TransactionType.INCOME
        assert rental_txn.amount == Decimal("12000.00")

        # Verify Werbungskosten transaction
        werbung_txn = next(
            (t for t in transactions if t.expense_category == ExpenseCategory.OTHER and t.is_deductible), None
        )
        assert werbung_txn is not None
        assert werbung_txn.type == TransactionType.EXPENSE
        assert werbung_txn.amount == Decimal("1000.00")

        # Verify user profile was updated
        db_session.refresh(test_user)
        assert test_user.tax_number is not None  # Should be encrypted

    def test_finalize_with_edited_data(self, orchestrator, test_user, db_session):
        """Test finalization using edited_data (user corrections)"""
        document = _create_document(
            db_session,
            user_id=test_user.id,
            document_type=DocumentType.E1_FORM,
            file_name="e1-edited.pdf",
        )
        # Create initial transactions (simulating initial extraction)
        initial_txn = Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=Decimal("50000.00"),
            transaction_date=date(2023, 12, 31),
            description="Initial employment income",
            income_category=IncomeCategory.EMPLOYMENT,
            import_source="e1_import",
        )
        db_session.add(initial_txn)
        db_session.commit()
        initial_txn_id = initial_txn.id

        # Create upload with both extracted and edited data
        upload = HistoricalImportUpload(
            user_id=test_user.id,
            document_id=document.id,
            document_type=HistoricalDocumentType.E1_FORM,
            tax_year=2023,
            status=ImportStatus.REVIEW_REQUIRED,
            extracted_data={
                "tax_year": 2023,
                "all_kz_values": {
                    "kz_245": 50000.00,  # Original value
                },
            },
            edited_data={
                "tax_year": 2023,
                "all_kz_values": {
                    "kz_245": 55000.00,  # Corrected value
                    "kz_260": 1500.00,   # Added deduction
                },
            },
            transactions_created=[initial_txn.id],
            extraction_confidence=Decimal("0.85"),
            requires_review=True,
        )
        db_session.add(upload)
        db_session.commit()
        db_session.refresh(upload)

        # Finalize the upload
        result = orchestrator._finalize_upload(upload)

        # Verify old transaction was deleted and new ones created
        assert result["transactions_created"] == 2

        # Verify old transaction is gone
        old_txn = db_session.query(Transaction).filter(
            Transaction.id == initial_txn_id
        ).first()
        assert old_txn is None

        # Verify new transactions with corrected values
        transactions = db_session.query(Transaction).filter(
            Transaction.user_id == test_user.id
        ).all()
        assert len(transactions) == 2

        # Verify corrected employment income
        employment_txn = next(
            (t for t in transactions if t.income_category == IncomeCategory.EMPLOYMENT), None
        )
        assert employment_txn is not None
        assert employment_txn.amount == Decimal("55000.00")  # Corrected value

        # Verify added deduction
        deduction_txn = next(
            (t for t in transactions if t.expense_category == ExpenseCategory.OTHER), None
        )
        assert deduction_txn is not None
        assert deduction_txn.amount == Decimal("1500.00")

        # All new transactions should be reviewed and locked
        for txn in transactions:
            assert txn.reviewed is True
            assert txn.locked is True

    def test_finalize_with_property_linking(self, orchestrator, test_user, test_property, db_session):
        """Test finalization with property linking suggestions"""
        document = _create_document(
            db_session,
            user_id=test_user.id,
            document_type=DocumentType.E1_FORM,
            file_name="e1-property-link.pdf",
        )
        # Create upload with rental income and property linking suggestion
        upload = HistoricalImportUpload(
            user_id=test_user.id,
            document_id=document.id,
            document_type=HistoricalDocumentType.E1_FORM,
            tax_year=2023,
            status=ImportStatus.REVIEW_REQUIRED,
            extracted_data={
                "tax_year": 2023,
                "all_kz_values": {
                    "kz_350": 12000.00,  # Rental income
                },
                "property_linking_suggestions": [
                    {
                        "action": "auto_link",
                        "matched_property_id": str(test_property.id),
                        "confidence": 0.95,
                    }
                ],
            },
            extraction_confidence=Decimal("0.85"),
            requires_review=False,
        )
        db_session.add(upload)
        db_session.commit()
        db_session.refresh(upload)

        # Finalize the upload
        result = orchestrator._finalize_upload(upload)

        # Verify property was linked
        assert result["properties_linked"] == 1
        db_session.refresh(upload)
        assert test_property.id in upload.properties_linked

        # Verify rental transaction is linked to property
        rental_txn = db_session.query(Transaction).filter(
            Transaction.user_id == test_user.id,
            Transaction.income_category == IncomeCategory.RENTAL,
        ).first()
        assert rental_txn is not None
        assert rental_txn.property_id == test_property.id
        assert rental_txn.reviewed is True
        assert rental_txn.locked is True


class TestFinalizeKaufvertrag:
    """Tests for Kaufvertrag finalization"""

    def test_finalize_kaufvertrag_with_purchase_costs(self, orchestrator, test_user, test_property, db_session):
        """Test finalization of Kaufvertrag with purchase costs"""
        document = _create_document(
            db_session,
            user_id=test_user.id,
            document_type=DocumentType.PURCHASE_CONTRACT,
            file_name="kaufvertrag.pdf",
        )
        # Create upload with Kaufvertrag data
        upload = HistoricalImportUpload(
            user_id=test_user.id,
            document_id=document.id,
            document_type=HistoricalDocumentType.KAUFVERTRAG,
            tax_year=2020,
            status=ImportStatus.REVIEW_REQUIRED,
            extracted_data={
                "property_id": str(test_property.id),
                "purchase_date": "2020-01-15",
                "purchase_price": 300000.00,
                "building_value": 200000.00,
                "grunderwerbsteuer": 10500.00,  # 3.5% property transfer tax
                "notary_fees": 3000.00,
                "registry_fees": 1200.00,
            },
            extraction_confidence=Decimal("0.90"),
            requires_review=False,
        )
        db_session.add(upload)
        db_session.commit()
        db_session.refresh(upload)

        # Finalize the upload
        result = orchestrator._finalize_upload(upload)

        # Verify purchase cost transactions were created
        assert result["transactions_created"] == 3
        assert result["properties_linked"] == 1

        # Verify transactions in database
        transactions = db_session.query(Transaction).filter(
            Transaction.user_id == test_user.id
        ).all()
        assert len(transactions) == 3

        # Verify all transactions are linked to property and locked
        for txn in transactions:
            assert txn.property_id == test_property.id
            assert txn.reviewed is True
            assert txn.locked is True
            assert txn.import_source == "kaufvertrag_import"

        # Verify Grunderwerbsteuer transaction
        grest_txn = next(
            (t for t in transactions if t.expense_category == ExpenseCategory.PROPERTY_TAX), None
        )
        assert grest_txn is not None
        assert grest_txn.amount == Decimal("10500.00")

        # Verify notary fees transaction
        notary_txn = next(
            (t for t in transactions if "Notarkosten" in t.description), None
        )
        assert notary_txn is not None
        assert notary_txn.amount == Decimal("3000.00")


class TestFinalizeSaldenliste:
    """Tests for Saldenliste finalization"""

    def test_finalize_saldenliste(self, orchestrator, test_user, db_session):
        """Test finalization of Saldenliste with opening balances"""
        document = _create_document(
            db_session,
            user_id=test_user.id,
            document_type=DocumentType.OTHER,
            file_name="saldenliste.csv",
        )
        # Create upload with Saldenliste data
        upload = HistoricalImportUpload(
            user_id=test_user.id,
            document_id=document.id,
            document_type=HistoricalDocumentType.SALDENLISTE,
            tax_year=2023,
            status=ImportStatus.REVIEW_REQUIRED,
            extracted_data={
                "tax_year": 2023,
                "accounts": [
                    {
                        "account_number": "1000",
                        "account_name": "Kassa",
                        "balance": 5000.00,
                    },
                    {
                        "account_number": "2000",
                        "account_name": "Bank",
                        "balance": 25000.00,
                    },
                    {
                        "account_number": "3000",
                        "account_name": "Verbindlichkeiten",
                        "balance": -10000.00,
                    },
                ],
            },
            extraction_confidence=Decimal("0.95"),
            requires_review=False,
        )
        db_session.add(upload)
        db_session.commit()
        db_session.refresh(upload)

        # Finalize the upload
        result = orchestrator._finalize_upload(upload)

        # Verify opening balance transactions were created
        assert result["transactions_created"] == 3

        # Verify transactions in database
        transactions = db_session.query(Transaction).filter(
            Transaction.user_id == test_user.id
        ).all()
        assert len(transactions) == 3

        # Verify all transactions are marked as reviewed and locked
        for txn in transactions:
            assert txn.reviewed is True
            assert txn.locked is True
            assert txn.import_source == "saldenliste_import"
            assert txn.transaction_date == date(2023, 1, 1)  # Opening balance date

        # Verify positive balances are income
        income_txns = [t for t in transactions if t.type == TransactionType.INCOME]
        assert len(income_txns) == 2
        assert sum(t.amount for t in income_txns) == Decimal("30000.00")

        # Verify negative balances are expenses
        expense_txns = [t for t in transactions if t.type == TransactionType.EXPENSE]
        assert len(expense_txns) == 1
        assert expense_txns[0].amount == Decimal("10000.00")


class TestUserProfileUpdate:
    """Tests for user profile updates during finalization"""

    def test_update_tax_number(self, orchestrator, test_user, db_session):
        """Test that tax number is updated from E1 data"""
        # Verify user has no tax number initially
        assert test_user.tax_number is None
        document = _create_document(
            db_session,
            user_id=test_user.id,
            document_type=DocumentType.E1_FORM,
            file_name="e1-tax-number.pdf",
        )

        # Create upload with tax number
        upload = HistoricalImportUpload(
            user_id=test_user.id,
            document_id=document.id,
            document_type=HistoricalDocumentType.E1_FORM,
            tax_year=2023,
            status=ImportStatus.REVIEW_REQUIRED,
            extracted_data={
                "tax_year": 2023,
                "steuernummer": "12-345/6789",
                "all_kz_values": {
                    "kz_245": 50000.00,
                },
            },
            extraction_confidence=Decimal("0.85"),
            requires_review=False,
        )
        db_session.add(upload)
        db_session.commit()
        db_session.refresh(upload)

        # Finalize the upload
        orchestrator._finalize_upload(upload)

        # Verify tax number was set
        db_session.refresh(test_user)
        assert test_user.tax_number is not None

    def test_do_not_overwrite_existing_tax_number(self, orchestrator, test_user, db_session):
        """Test that existing tax number is not overwritten"""
        from app.core.encryption import get_encryption
        
        # Set existing tax number
        encryption = get_encryption()
        test_user.tax_number = encryption.encrypt_field("99-999/9999")
        db_session.commit()
        document = _create_document(
            db_session,
            user_id=test_user.id,
            document_type=DocumentType.E1_FORM,
            file_name="e1-tax-number-preserve.pdf",
        )

        # Create upload with different tax number
        upload = HistoricalImportUpload(
            user_id=test_user.id,
            document_id=document.id,
            document_type=HistoricalDocumentType.E1_FORM,
            tax_year=2023,
            status=ImportStatus.REVIEW_REQUIRED,
            extracted_data={
                "tax_year": 2023,
                "steuernummer": "12-345/6789",  # Different number
                "all_kz_values": {
                    "kz_245": 50000.00,
                },
            },
            extraction_confidence=Decimal("0.85"),
            requires_review=False,
        )
        db_session.add(upload)
        db_session.commit()
        db_session.refresh(upload)

        # Finalize the upload
        orchestrator._finalize_upload(upload)

        # Verify original tax number was preserved
        db_session.refresh(test_user)
        decrypted = encryption.decrypt_field(test_user.tax_number)
        assert decrypted == "99-999/9999"


class TestTransactionLocking:
    """Tests for transaction reviewed and locked flags"""

    def test_transactions_marked_reviewed_and_locked(self, orchestrator, test_user, db_session):
        """Test that all finalized transactions are marked as reviewed and locked"""
        document = _create_document(
            db_session,
            user_id=test_user.id,
            document_type=DocumentType.E1_FORM,
            file_name="e1-locking.pdf",
        )
        # Create upload
        upload = HistoricalImportUpload(
            user_id=test_user.id,
            document_id=document.id,
            document_type=HistoricalDocumentType.E1_FORM,
            tax_year=2023,
            status=ImportStatus.REVIEW_REQUIRED,
            extracted_data={
                "tax_year": 2023,
                "all_kz_values": {
                    "kz_245": 50000.00,
                    "kz_350": 12000.00,
                    "kz_260": 1000.00,
                },
            },
            extraction_confidence=Decimal("0.85"),
            requires_review=False,
        )
        db_session.add(upload)
        db_session.commit()
        db_session.refresh(upload)

        # Finalize the upload
        orchestrator._finalize_upload(upload)

        # Verify all transactions are reviewed and locked
        transactions = db_session.query(Transaction).filter(
            Transaction.user_id == test_user.id
        ).all()
        
        assert len(transactions) > 0
        for txn in transactions:
            assert txn.reviewed is True, f"Transaction {txn.id} not marked as reviewed"
            assert txn.locked is True, f"Transaction {txn.id} not marked as locked"
