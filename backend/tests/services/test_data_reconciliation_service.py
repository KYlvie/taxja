"""Unit tests for DataReconciliationService"""
import pytest
from decimal import Decimal
from uuid import uuid4
from datetime import datetime
from sqlalchemy.orm import Session
from app.services.data_reconciliation_service import DataReconciliationService
from app.models.historical_import import (
    HistoricalImportSession,
    HistoricalImportUpload,
    ImportConflict,
    HistoricalDocumentType,
    ImportStatus,
    ImportSessionStatus,
)
from app.models.user import User
from app.models.document import Document


@pytest.fixture
def reconciliation_service(db_session: Session):
    """Create DataReconciliationService instance"""
    return DataReconciliationService(db_session)


@pytest.fixture
def test_user(db_session: Session):
    """Create test user"""
    user = User(
        email="test@example.com",
        hashed_password="hashed",
        first_name="Test",
        last_name="User",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_session(db_session: Session, test_user: User):
    """Create test import session"""
    session = HistoricalImportSession(
        user_id=test_user.id,
        status=ImportSessionStatus.ACTIVE,
        tax_years=[2023],
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


@pytest.fixture
def test_document(db_session: Session, test_user: User):
    """Create test document"""
    doc = Document(
        user_id=test_user.id,
        filename="test.pdf",
        file_path="/test/test.pdf",
        file_type="application/pdf",
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    return doc


class TestDetectConflicts:
    """Tests for detect_conflicts method"""

    def test_detect_employment_income_conflict(
        self,
        db_session: Session,
        reconciliation_service: DataReconciliationService,
        test_session: HistoricalImportSession,
        test_user: User,
        test_document: Document,
    ):
        """Test detection of employment income conflict between E1 and Bescheid"""
        # Create E1 upload with employment income
        e1_upload = HistoricalImportUpload(
            session_id=test_session.id,
            user_id=test_user.id,
            document_id=test_document.id,
            document_type=HistoricalDocumentType.E1_FORM,
            tax_year=2023,
            status=ImportStatus.EXTRACTED,
            extraction_confidence=Decimal("0.85"),
            extracted_data={"kz_245": "50000.00"},
        )
        db_session.add(e1_upload)

        # Create Bescheid upload with different employment income (>1% difference)
        bescheid_upload = HistoricalImportUpload(
            session_id=test_session.id,
            user_id=test_user.id,
            document_id=test_document.id,
            document_type=HistoricalDocumentType.BESCHEID,
            tax_year=2023,
            status=ImportStatus.EXTRACTED,
            extraction_confidence=Decimal("0.90"),
            extracted_data={"employment_income": "51000.00"},
        )
        db_session.add(bescheid_upload)
        db_session.commit()

        # Detect conflicts
        conflicts = reconciliation_service.detect_conflicts(str(test_session.id))

        # Verify conflict detected
        assert len(conflicts) == 1
        conflict = conflicts[0]
        assert conflict.conflict_type == "conflicting_amount"
        assert conflict.field_name == "Employment Income"
        assert conflict.value_1 == "50000.00"
        assert conflict.value_2 == "51000.00"
        assert conflict.resolution in ["keep_first", "keep_second", "manual_merge"]

    def test_no_conflict_within_threshold(
        self,
        db_session: Session,
        reconciliation_service: DataReconciliationService,
        test_session: HistoricalImportSession,
        test_user: User,
        test_document: Document,
    ):
        """Test no conflict when difference is within 1% threshold"""
        # Create E1 upload
        e1_upload = HistoricalImportUpload(
            session_id=test_session.id,
            user_id=test_user.id,
            document_id=test_document.id,
            document_type=HistoricalDocumentType.E1_FORM,
            tax_year=2023,
            status=ImportStatus.EXTRACTED,
            extraction_confidence=Decimal("0.85"),
            extracted_data={"kz_245": "50000.00"},
        )
        db_session.add(e1_upload)

        # Create Bescheid upload with similar amount (within 1%)
        bescheid_upload = HistoricalImportUpload(
            session_id=test_session.id,
            user_id=test_user.id,
            document_id=test_document.id,
            document_type=HistoricalDocumentType.BESCHEID,
            tax_year=2023,
            status=ImportStatus.EXTRACTED,
            extraction_confidence=Decimal("0.90"),
            extracted_data={"employment_income": "50400.00"},  # 0.8% difference
        )
        db_session.add(bescheid_upload)
        db_session.commit()

        # Detect conflicts
        conflicts = reconciliation_service.detect_conflicts(str(test_session.id))

        # Verify no conflict detected
        assert len(conflicts) == 0

    def test_detect_rental_income_conflict(
        self,
        db_session: Session,
        reconciliation_service: DataReconciliationService,
        test_session: HistoricalImportSession,
        test_user: User,
        test_document: Document,
    ):
        """Test detection of rental income conflict"""
        # Create E1 upload with rental income
        e1_upload = HistoricalImportUpload(
            session_id=test_session.id,
            user_id=test_user.id,
            document_id=test_document.id,
            document_type=HistoricalDocumentType.E1_FORM,
            tax_year=2023,
            status=ImportStatus.EXTRACTED,
            extraction_confidence=Decimal("0.80"),
            extracted_data={"kz_350": "12000.00"},
        )
        db_session.add(e1_upload)

        # Create Bescheid upload with different rental income
        bescheid_upload = HistoricalImportUpload(
            session_id=test_session.id,
            user_id=test_user.id,
            document_id=test_document.id,
            document_type=HistoricalDocumentType.BESCHEID,
            tax_year=2023,
            status=ImportStatus.EXTRACTED,
            extraction_confidence=Decimal("0.85"),
            extracted_data={"rental_income": "13000.00"},
        )
        db_session.add(bescheid_upload)
        db_session.commit()

        # Detect conflicts
        conflicts = reconciliation_service.detect_conflicts(str(test_session.id))

        # Verify conflict detected
        assert len(conflicts) == 1
        assert conflicts[0].field_name == "Rental Income"

    def test_no_conflict_different_tax_years(
        self,
        db_session: Session,
        reconciliation_service: DataReconciliationService,
        test_session: HistoricalImportSession,
        test_user: User,
        test_document: Document,
    ):
        """Test no conflict when documents are from different tax years"""
        # Create E1 upload for 2023
        e1_upload = HistoricalImportUpload(
            session_id=test_session.id,
            user_id=test_user.id,
            document_id=test_document.id,
            document_type=HistoricalDocumentType.E1_FORM,
            tax_year=2023,
            status=ImportStatus.EXTRACTED,
            extraction_confidence=Decimal("0.85"),
            extracted_data={"kz_245": "50000.00"},
        )
        db_session.add(e1_upload)

        # Create Bescheid upload for 2022
        bescheid_upload = HistoricalImportUpload(
            session_id=test_session.id,
            user_id=test_user.id,
            document_id=test_document.id,
            document_type=HistoricalDocumentType.BESCHEID,
            tax_year=2022,
            status=ImportStatus.EXTRACTED,
            extraction_confidence=Decimal("0.90"),
            extracted_data={"employment_income": "51000.00"},
        )
        db_session.add(bescheid_upload)
        db_session.commit()

        # Detect conflicts
        conflicts = reconciliation_service.detect_conflicts(str(test_session.id))

        # Verify no conflict (different years)
        assert len(conflicts) == 0

    def test_no_conflict_missing_data(
        self,
        db_session: Session,
        reconciliation_service: DataReconciliationService,
        test_session: HistoricalImportSession,
        test_user: User,
        test_document: Document,
    ):
        """Test no conflict when extracted data is missing"""
        # Create E1 upload without extracted data
        e1_upload = HistoricalImportUpload(
            session_id=test_session.id,
            user_id=test_user.id,
            document_id=test_document.id,
            document_type=HistoricalDocumentType.E1_FORM,
            tax_year=2023,
            status=ImportStatus.EXTRACTED,
            extraction_confidence=Decimal("0.85"),
            extracted_data=None,
        )
        db_session.add(e1_upload)

        # Create Bescheid upload
        bescheid_upload = HistoricalImportUpload(
            session_id=test_session.id,
            user_id=test_user.id,
            document_id=test_document.id,
            document_type=HistoricalDocumentType.BESCHEID,
            tax_year=2023,
            status=ImportStatus.EXTRACTED,
            extraction_confidence=Decimal("0.90"),
            extracted_data={"employment_income": "51000.00"},
        )
        db_session.add(bescheid_upload)
        db_session.commit()

        # Detect conflicts
        conflicts = reconciliation_service.detect_conflicts(str(test_session.id))

        # Verify no conflict (missing data)
        assert len(conflicts) == 0


class TestReconcileIncomeAmounts:
    """Tests for reconcile_income_amounts method"""

    def test_reconcile_within_threshold(
        self, reconciliation_service: DataReconciliationService
    ):
        """Test reconciliation when amounts are within threshold"""
        result = reconciliation_service.reconcile_income_amounts(
            e1_amount=Decimal("50000.00"),
            bescheid_amount=Decimal("50400.00"),
            category="employment",
        )

        assert result["recommended_amount"] == Decimal("50400.00")
        assert result["source"] == "bescheid"
        assert result["requires_review"] is False
        assert result["percentage_diff"] <= Decimal("0.01")

    def test_reconcile_above_threshold(
        self, reconciliation_service: DataReconciliationService
    ):
        """Test reconciliation when amounts differ significantly"""
        result = reconciliation_service.reconcile_income_amounts(
            e1_amount=Decimal("50000.00"),
            bescheid_amount=Decimal("55000.00"),
            category="employment",
        )

        assert result["recommended_amount"] == Decimal("55000.00")
        assert result["source"] == "bescheid"
        assert result["requires_review"] is True
        assert result["percentage_diff"] > Decimal("0.01")

    def test_reconcile_zero_amounts(
        self, reconciliation_service: DataReconciliationService
    ):
        """Test reconciliation with zero amounts"""
        result = reconciliation_service.reconcile_income_amounts(
            e1_amount=Decimal("0.00"),
            bescheid_amount=Decimal("0.00"),
            category="rental",
        )

        assert result["recommended_amount"] == Decimal("0")
        assert result["source"] == "both"
        assert result["requires_review"] is False


class TestSuggestResolution:
    """Tests for suggest_resolution method"""

    def test_suggest_bescheid_priority(
        self,
        db_session: Session,
        reconciliation_service: DataReconciliationService,
        test_session: HistoricalImportSession,
        test_user: User,
        test_document: Document,
    ):
        """Test that Bescheid is prioritized over E1"""
        # Create E1 upload
        e1_upload = HistoricalImportUpload(
            session_id=test_session.id,
            user_id=test_user.id,
            document_id=test_document.id,
            document_type=HistoricalDocumentType.E1_FORM,
            tax_year=2023,
            status=ImportStatus.EXTRACTED,
            extraction_confidence=Decimal("0.85"),
        )
        db_session.add(e1_upload)

        # Create Bescheid upload
        bescheid_upload = HistoricalImportUpload(
            session_id=test_session.id,
            user_id=test_user.id,
            document_id=test_document.id,
            document_type=HistoricalDocumentType.BESCHEID,
            tax_year=2023,
            status=ImportStatus.EXTRACTED,
            extraction_confidence=Decimal("0.80"),
        )
        db_session.add(bescheid_upload)
        db_session.commit()

        # Create conflict
        conflict = ImportConflict(
            session_id=test_session.id,
            upload_id_1=e1_upload.id,
            upload_id_2=bescheid_upload.id,
            conflict_type="conflicting_amount",
            field_name="Employment Income",
            value_1="50000.00",
            value_2="51000.00",
        )
        db_session.add(conflict)
        db_session.commit()

        # Get resolution suggestion
        resolution = reconciliation_service.suggest_resolution(conflict)

        # Bescheid should be prioritized
        assert resolution == "keep_second"

    def test_suggest_higher_confidence(
        self,
        db_session: Session,
        reconciliation_service: DataReconciliationService,
        test_session: HistoricalImportSession,
        test_user: User,
        test_document: Document,
    ):
        """Test resolution based on confidence when no Bescheid"""
        # Create two E1 uploads with different confidence
        e1_upload_1 = HistoricalImportUpload(
            session_id=test_session.id,
            user_id=test_user.id,
            document_id=test_document.id,
            document_type=HistoricalDocumentType.E1_FORM,
            tax_year=2023,
            status=ImportStatus.EXTRACTED,
            extraction_confidence=Decimal("0.95"),
        )
        db_session.add(e1_upload_1)

        e1_upload_2 = HistoricalImportUpload(
            session_id=test_session.id,
            user_id=test_user.id,
            document_id=test_document.id,
            document_type=HistoricalDocumentType.E1_FORM,
            tax_year=2023,
            status=ImportStatus.EXTRACTED,
            extraction_confidence=Decimal("0.75"),
        )
        db_session.add(e1_upload_2)
        db_session.commit()

        # Create conflict
        conflict = ImportConflict(
            session_id=test_session.id,
            upload_id_1=e1_upload_1.id,
            upload_id_2=e1_upload_2.id,
            conflict_type="conflicting_amount",
            field_name="Rental Income",
            value_1="12000.00",
            value_2="13000.00",
        )
        db_session.add(conflict)
        db_session.commit()

        # Get resolution suggestion
        resolution = reconciliation_service.suggest_resolution(conflict)

        # Higher confidence should be preferred
        assert resolution == "keep_first"

    def test_suggest_manual_merge_similar_confidence(
        self,
        db_session: Session,
        reconciliation_service: DataReconciliationService,
        test_session: HistoricalImportSession,
        test_user: User,
        test_document: Document,
    ):
        """Test manual merge when confidence is similar"""
        # Create two uploads with similar confidence
        upload_1 = HistoricalImportUpload(
            session_id=test_session.id,
            user_id=test_user.id,
            document_id=test_document.id,
            document_type=HistoricalDocumentType.E1_FORM,
            tax_year=2023,
            status=ImportStatus.EXTRACTED,
            extraction_confidence=Decimal("0.85"),
        )
        db_session.add(upload_1)

        upload_2 = HistoricalImportUpload(
            session_id=test_session.id,
            user_id=test_user.id,
            document_id=test_document.id,
            document_type=HistoricalDocumentType.E1_FORM,
            tax_year=2023,
            status=ImportStatus.EXTRACTED,
            extraction_confidence=Decimal("0.87"),
        )
        db_session.add(upload_2)
        db_session.commit()

        # Create conflict
        conflict = ImportConflict(
            session_id=test_session.id,
            upload_id_1=upload_1.id,
            upload_id_2=upload_2.id,
            conflict_type="conflicting_amount",
            field_name="Special Expenses",
            value_1="5000.00",
            value_2="5500.00",
        )
        db_session.add(conflict)
        db_session.commit()

        # Get resolution suggestion
        resolution = reconciliation_service.suggest_resolution(conflict)

        # Should require manual merge
        assert resolution == "manual_merge"
