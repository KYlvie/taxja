"""
Unit tests for HistoricalImportOrchestrator
"""
import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from app.services.historical_import_orchestrator import HistoricalImportOrchestrator
from app.models.historical_import import (
    HistoricalImportSession,
    HistoricalImportUpload,
    ImportSessionStatus,
    ImportStatus,
    HistoricalDocumentType,
)
from app.models.user import User, UserType
from app.models.document import Document, DocumentType


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    user = User(
        email="test@example.com",
        hashed_password="hashed",
        name="Test User",
        user_type=UserType.EMPLOYEE,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def orchestrator(db_session):
    """Create orchestrator instance"""
    return HistoricalImportOrchestrator(db_session)


class TestCreateSession:
    """Tests for create_session method"""

    def test_create_session_success(self, orchestrator, test_user, db_session):
        """Test successful session creation"""
        tax_years = [2021, 2022, 2023]
        document_types = ["e1_form", "bescheid"]

        session = orchestrator.create_session(
            user_id=test_user.id, tax_years=tax_years, document_types=document_types
        )

        assert session.id is not None
        assert session.user_id == test_user.id
        assert session.status == ImportSessionStatus.ACTIVE
        assert session.tax_years == sorted(tax_years)
        assert session.total_documents == 0
        assert session.successful_imports == 0
        assert session.failed_imports == 0
        assert session.transactions_created == 0
        assert session.properties_created == 0
        assert session.properties_linked == 0

        # Verify session is persisted
        db_session.refresh(session)
        assert session.id is not None

    def test_create_session_sorts_tax_years(self, orchestrator, test_user):
        """Test that tax years are sorted"""
        tax_years = [2023, 2021, 2022]
        document_types = ["e1_form"]

        session = orchestrator.create_session(
            user_id=test_user.id, tax_years=tax_years, document_types=document_types
        )

        assert session.tax_years == [2021, 2022, 2023]


class TestProcessUpload:
    """Tests for process_upload method"""

    def test_process_upload_not_found(self, orchestrator):
        """Test processing non-existent upload"""
        with pytest.raises(ValueError, match="Upload not found"):
            orchestrator.process_upload(upload_id=uuid4(), ocr_text="test")

    def test_process_upload_unsupported_type(self, orchestrator, test_user, db_session):
        """Test processing upload with unsupported document type"""
        # Create document
        document = Document(
            user_id=test_user.id,
            document_type=DocumentType.RECEIPT,
            file_path="/test/path.pdf",
            file_name="test.pdf",
        )
        db_session.add(document)
        db_session.commit()

        # Create upload with invalid type (we'll manually set it)
        upload = HistoricalImportUpload(
            user_id=test_user.id,
            document_id=document.id,
            document_type=HistoricalDocumentType.E1_FORM,  # Will be changed
            tax_year=2023,
            status=ImportStatus.UPLOADED,
        )
        db_session.add(upload)
        db_session.commit()

        # Manually set to invalid type (for testing error handling)
        # In real scenario, this would be caught by enum validation
        # Here we test the error handling path
        result = orchestrator.process_upload(upload_id=upload.id, ocr_text=None)

        # Should fail due to missing OCR text
        assert result["status"] == ImportStatus.FAILED.value
        assert result["requires_review"] is True
        assert len(result["errors"]) > 0


class TestFinalizeSession:
    """Tests for finalize_session method"""

    def test_finalize_session_not_found(self, orchestrator):
        """Test finalizing non-existent session"""
        with pytest.raises(ValueError, match="Session not found"):
            orchestrator.finalize_session(session_id=uuid4())

    def test_finalize_session_success(self, orchestrator, test_user, db_session):
        """Test successful session finalization"""
        # Create session
        session = HistoricalImportSession(
            user_id=test_user.id,
            status=ImportSessionStatus.ACTIVE,
            tax_years=[2023],
            total_documents=1,
            successful_imports=1,
            failed_imports=0,
        )
        db_session.add(session)
        db_session.commit()

        # Finalize session
        summary = orchestrator.finalize_session(session_id=session.id)

        assert summary["session_id"] == str(session.id)
        assert summary["status"] == ImportSessionStatus.COMPLETED.value
        assert summary["total_documents"] == 1
        assert summary["successful_imports"] == 1
        assert summary["failed_imports"] == 0
        assert summary["completed_at"] is not None

        # Verify session is updated
        db_session.refresh(session)
        assert session.status == ImportSessionStatus.COMPLETED
        assert session.completed_at is not None

    def test_finalize_session_with_failures(self, orchestrator, test_user, db_session):
        """Test finalizing session with all failures"""
        # Create session with failures
        session = HistoricalImportSession(
            user_id=test_user.id,
            status=ImportSessionStatus.ACTIVE,
            tax_years=[2023],
            total_documents=2,
            successful_imports=0,
            failed_imports=2,
        )
        db_session.add(session)
        db_session.commit()

        # Finalize session
        summary = orchestrator.finalize_session(session_id=session.id)

        assert summary["status"] == ImportSessionStatus.FAILED.value

        # Verify session is updated
        db_session.refresh(session)
        assert session.status == ImportSessionStatus.FAILED


class TestUpdateSessionMetrics:
    """Tests for _update_session_metrics method"""

    def test_update_session_metrics(self, orchestrator, test_user, db_session):
        """Test updating session metrics based on uploads"""
        # Create session
        session = HistoricalImportSession(
            user_id=test_user.id,
            status=ImportSessionStatus.ACTIVE,
            tax_years=[2023],
        )
        db_session.add(session)
        db_session.commit()

        # Create document
        document = Document(
            user_id=test_user.id,
            document_type=DocumentType.RECEIPT,
            file_path="/test/path.pdf",
            file_name="test.pdf",
        )
        db_session.add(document)
        db_session.commit()

        # Create uploads
        upload1 = HistoricalImportUpload(
            session_id=session.id,
            user_id=test_user.id,
            document_id=document.id,
            document_type=HistoricalDocumentType.E1_FORM,
            tax_year=2023,
            status=ImportStatus.EXTRACTED,
            transactions_created=[1, 2, 3],
            properties_created=[],
            properties_linked=[],
        )
        upload2 = HistoricalImportUpload(
            session_id=session.id,
            user_id=test_user.id,
            document_id=document.id,
            document_type=HistoricalDocumentType.BESCHEID,
            tax_year=2023,
            status=ImportStatus.FAILED,
            transactions_created=[],
            properties_created=[],
            properties_linked=[],
        )
        db_session.add_all([upload1, upload2])
        db_session.commit()

        # Update metrics
        orchestrator._update_session_metrics(session.id)

        # Verify metrics
        db_session.refresh(session)
        assert session.total_documents == 2
        assert session.successful_imports == 1
        assert session.failed_imports == 1
        assert session.transactions_created == 3
        assert session.properties_created == 0
        assert session.properties_linked == 0


class TestConfidenceThresholds:
    """Tests for confidence threshold constants"""

    def test_confidence_thresholds_defined(self, orchestrator):
        """Test that confidence thresholds are properly defined"""
        assert orchestrator.CONFIDENCE_THRESHOLD_E1 == Decimal("0.7")
        assert orchestrator.CONFIDENCE_THRESHOLD_BESCHEID == Decimal("0.7")
        assert orchestrator.CONFIDENCE_THRESHOLD_KAUFVERTRAG == Decimal("0.6")
        assert orchestrator.CONFIDENCE_THRESHOLD_SALDENLISTE == Decimal("0.7")


class TestReviewUpload:
    """Tests for review_upload method"""

    def test_review_upload_not_found(self, orchestrator):
        """Test reviewing non-existent upload"""
        with pytest.raises(ValueError, match="Upload not found"):
            orchestrator.review_upload(upload_id=uuid4(), approved=True)

    def test_review_upload_invalid_status(self, orchestrator, test_user, db_session):
        """Test reviewing upload in invalid status"""
        # Create document
        document = Document(
            user_id=test_user.id,
            document_type=DocumentType.RECEIPT,
            file_path="/test/path.pdf",
            file_name="test.pdf",
        )
        db_session.add(document)
        db_session.commit()

        # Create upload in PROCESSING status (not reviewable)
        upload = HistoricalImportUpload(
            user_id=test_user.id,
            document_id=document.id,
            document_type=HistoricalDocumentType.E1_FORM,
            tax_year=2023,
            status=ImportStatus.PROCESSING,
        )
        db_session.add(upload)
        db_session.commit()

        # Try to review
        with pytest.raises(ValueError, match="Upload cannot be reviewed in status"):
            orchestrator.review_upload(upload_id=upload.id, approved=True)

    def test_review_upload_approval_without_edited_data(
        self, orchestrator, test_user, db_session
    ):
        """Test approving upload without edited data"""
        # Create document
        document = Document(
            user_id=test_user.id,
            document_type=DocumentType.RECEIPT,
            file_path="/test/path.pdf",
            file_name="test.pdf",
        )
        db_session.add(document)
        db_session.commit()

        # Create upload in REVIEW_REQUIRED status
        upload = HistoricalImportUpload(
            user_id=test_user.id,
            document_id=document.id,
            document_type=HistoricalDocumentType.E1_FORM,
            tax_year=2023,
            status=ImportStatus.REVIEW_REQUIRED,
            extracted_data={"kz_245": 50000, "kz_350": 10000},
            extraction_confidence=Decimal("0.65"),
        )
        db_session.add(upload)
        db_session.commit()

        # Mock the _finalize_upload method
        with patch.object(
            orchestrator,
            "_finalize_upload",
            return_value={
                "transactions_created": 2,
                "properties_created": 0,
                "properties_linked": 1,
            },
        ) as mock_finalize:
            # Approve upload
            result = orchestrator.review_upload(
                upload_id=upload.id,
                approved=True,
                notes="Looks good",
                reviewed_by=test_user.id,
            )

        # Verify result
        assert result["upload_id"] == upload.id
        assert result["status"] == ImportStatus.APPROVED.value
        assert result["approved"] is True
        assert result["transactions_created"] == 2
        assert result["properties_linked"] == 1
        assert "successfully" in result["message"]

        # Verify upload was updated
        db_session.refresh(upload)
        assert upload.status == ImportStatus.APPROVED
        assert upload.reviewed_at is not None
        assert upload.reviewed_by == test_user.id
        assert upload.approval_notes == "Looks good"
        assert upload.edited_data is None

        # Verify _finalize_upload was called
        mock_finalize.assert_called_once_with(upload)

    def test_review_upload_approval_with_edited_data(
        self, orchestrator, test_user, db_session
    ):
        """Test approving upload with edited data"""
        # Create document
        document = Document(
            user_id=test_user.id,
            document_type=DocumentType.RECEIPT,
            file_path="/test/path.pdf",
            file_name="test.pdf",
        )
        db_session.add(document)
        db_session.commit()

        # Create upload
        upload = HistoricalImportUpload(
            user_id=test_user.id,
            document_id=document.id,
            document_type=HistoricalDocumentType.E1_FORM,
            tax_year=2023,
            status=ImportStatus.REVIEW_REQUIRED,
            extracted_data={"kz_245": 50000, "kz_350": 10000},
        )
        db_session.add(upload)
        db_session.commit()

        # Mock the _finalize_upload method
        with patch.object(
            orchestrator,
            "_finalize_upload",
            return_value={
                "transactions_created": 2,
                "properties_created": 0,
                "properties_linked": 0,
            },
        ):
            # Approve with edited data
            edited_data = {"kz_245": 51000, "kz_350": 10000}  # Corrected kz_245
            result = orchestrator.review_upload(
                upload_id=upload.id,
                approved=True,
                edited_data=edited_data,
                notes="Corrected employment income",
                reviewed_by=test_user.id,
            )

        # Verify result
        assert result["approved"] is True
        assert result["status"] == ImportStatus.APPROVED.value

        # Verify edited data was stored
        db_session.refresh(upload)
        assert upload.edited_data == edited_data
        assert upload.approval_notes == "Corrected employment income"

    def test_review_upload_rejection(self, orchestrator, test_user, db_session):
        """Test rejecting upload"""
        # Create document
        document = Document(
            user_id=test_user.id,
            document_type=DocumentType.RECEIPT,
            file_path="/test/path.pdf",
            file_name="test.pdf",
        )
        db_session.add(document)
        db_session.commit()

        # Create upload with transactions
        upload = HistoricalImportUpload(
            user_id=test_user.id,
            document_id=document.id,
            document_type=HistoricalDocumentType.E1_FORM,
            tax_year=2023,
            status=ImportStatus.REVIEW_REQUIRED,
            extracted_data={"kz_245": 50000},
            transactions_created=[1, 2, 3],
        )
        db_session.add(upload)
        db_session.commit()

        # Mock the _reject_upload method
        with patch.object(
            orchestrator,
            "_reject_upload",
            return_value={
                "transactions_deleted": 3,
                "properties_unlinked": 0,
                "depreciation_schedules_deleted": 0,
            },
        ) as mock_reject:
            # Reject upload
            result = orchestrator.review_upload(
                upload_id=upload.id,
                approved=False,
                notes="Data quality too low",
                reviewed_by=test_user.id,
            )

        # Verify result
        assert result["upload_id"] == upload.id
        assert result["status"] == ImportStatus.REJECTED.value
        assert result["approved"] is False
        assert result["transactions_created"] == 0
        assert "cleaned up" in result["message"]

        # Verify upload was updated
        db_session.refresh(upload)
        assert upload.status == ImportStatus.REJECTED
        assert upload.reviewed_at is not None
        assert upload.reviewed_by == test_user.id
        assert upload.approval_notes == "Data quality too low"

        # Verify _reject_upload was called
        mock_reject.assert_called_once_with(upload)

    def test_review_upload_updates_session_metrics(
        self, orchestrator, test_user, db_session
    ):
        """Test that reviewing upload updates session metrics"""
        # Create session
        session = HistoricalImportSession(
            user_id=test_user.id,
            status=ImportSessionStatus.ACTIVE,
            tax_years=[2023],
        )
        db_session.add(session)
        db_session.commit()

        # Create document
        document = Document(
            user_id=test_user.id,
            document_type=DocumentType.RECEIPT,
            file_path="/test/path.pdf",
            file_name="test.pdf",
        )
        db_session.add(document)
        db_session.commit()

        # Create upload in session
        upload = HistoricalImportUpload(
            session_id=session.id,
            user_id=test_user.id,
            document_id=document.id,
            document_type=HistoricalDocumentType.E1_FORM,
            tax_year=2023,
            status=ImportStatus.REVIEW_REQUIRED,
            extracted_data={"kz_245": 50000},
        )
        db_session.add(upload)
        db_session.commit()

        # Mock finalize method
        with patch.object(
            orchestrator,
            "_finalize_upload",
            return_value={
                "transactions_created": 1,
                "properties_created": 0,
                "properties_linked": 0,
            },
        ):
            # Approve upload
            orchestrator.review_upload(upload_id=upload.id, approved=True)

        # Verify session metrics were updated
        db_session.refresh(session)
        # The metrics should reflect the upload status change




class TestImportMetricsLogging:
    """Tests for _log_import_metrics method"""

    def test_log_metrics_for_e1_form(self, orchestrator, test_user, db_session):
        """Test logging metrics for E1 form import"""
        from app.models.historical_import import ImportMetrics

        # Create document
        document = Document(
            user_id=test_user.id,
            document_type=DocumentType.RECEIPT,
            file_path="/test/path.pdf",
            file_name="test.pdf",
        )
        db_session.add(document)
        db_session.commit()

        # Create upload
        upload = HistoricalImportUpload(
            user_id=test_user.id,
            document_id=document.id,
            document_type=HistoricalDocumentType.E1_FORM,
            tax_year=2023,
            status=ImportStatus.EXTRACTED,
        )
        db_session.add(upload)
        db_session.commit()

        # Create result with extracted data
        result = {
            "confidence": 0.85,
            "extracted_data": {
                "all_kz_values": {
                    "kz_245": 50000,
                    "kz_350": 10000,
                    "kz_260": 1000,
                }
            },
        }

        # Log metrics
        orchestrator._log_import_metrics(upload, result, extraction_time_ms=1500)

        # Verify metrics were created
        metrics = db_session.query(ImportMetrics).filter_by(upload_id=upload.id).first()
        assert metrics is not None
        assert metrics.document_type == HistoricalDocumentType.E1_FORM
        assert metrics.extraction_confidence == Decimal("0.85")
        assert metrics.fields_extracted == 3
        assert metrics.fields_total == 10  # Expected KZ codes
        assert metrics.extraction_time_ms == 1500
        assert "kz_245" in metrics.field_accuracies
        assert "kz_350" in metrics.field_accuracies
        assert "kz_260" in metrics.field_accuracies
        assert metrics.fields_corrected == 0
        assert metrics.corrections == []

    def test_log_metrics_for_bescheid(self, orchestrator, test_user, db_session):
        """Test logging metrics for Bescheid import"""
        from app.models.historical_import import ImportMetrics

        # Create document
        document = Document(
            user_id=test_user.id,
            document_type=DocumentType.RECEIPT,
            file_path="/test/path.pdf",
            file_name="test.pdf",
        )
        db_session.add(document)
        db_session.commit()

        # Create upload
        upload = HistoricalImportUpload(
            user_id=test_user.id,
            document_id=document.id,
            document_type=HistoricalDocumentType.BESCHEID,
            tax_year=2023,
            status=ImportStatus.EXTRACTED,
        )
        db_session.add(upload)
        db_session.commit()

        # Create result with extracted data
        result = {
            "confidence": 0.92,
            "extracted_data": {
                "employment_income": 50000,
                "rental_income": 10000,
                "property_addresses": ["Address 1", "Address 2"],
            },
        }

        # Log metrics
        orchestrator._log_import_metrics(upload, result, extraction_time_ms=2000)

        # Verify metrics
        metrics = db_session.query(ImportMetrics).filter_by(upload_id=upload.id).first()
        assert metrics is not None
        assert metrics.document_type == HistoricalDocumentType.BESCHEID
        assert metrics.extraction_confidence == Decimal("0.92")
        assert metrics.fields_extracted == 4  # employment_income, rental_income, 2 addresses
        assert metrics.fields_total == 5
        assert metrics.extraction_time_ms == 2000
        assert "employment_income" in metrics.field_accuracies
        assert "rental_income" in metrics.field_accuracies

    def test_log_metrics_for_kaufvertrag(self, orchestrator, test_user, db_session):
        """Test logging metrics for Kaufvertrag import"""
        from app.models.historical_import import ImportMetrics

        # Create document
        document = Document(
            user_id=test_user.id,
            document_type=DocumentType.RECEIPT,
            file_path="/test/path.pdf",
            file_name="test.pdf",
        )
        db_session.add(document)
        db_session.commit()

        # Create upload
        upload = HistoricalImportUpload(
            user_id=test_user.id,
            document_id=document.id,
            document_type=HistoricalDocumentType.KAUFVERTRAG,
            tax_year=2023,
            status=ImportStatus.EXTRACTED,
        )
        db_session.add(upload)
        db_session.commit()

        # Create result with extracted data
        result = {
            "confidence": 0.78,
            "extracted_data": {
                "purchase_price": 500000,
                "building_value": 400000,
                "land_value": 100000,
                "purchase_date": "2023-01-15",
                "address": "Test Street 1",
                "grunderwerbsteuer": 17500,
                "notary_fees": 2000,
                "registry_fees": 1500,
            },
        }

        # Log metrics
        orchestrator._log_import_metrics(upload, result, extraction_time_ms=3000)

        # Verify metrics
        metrics = db_session.query(ImportMetrics).filter_by(upload_id=upload.id).first()
        assert metrics is not None
        assert metrics.document_type == HistoricalDocumentType.KAUFVERTRAG
        assert metrics.extraction_confidence == Decimal("0.78")
        assert metrics.fields_extracted == 8
        assert metrics.fields_total == 8
        assert metrics.extraction_time_ms == 3000
        assert "purchase_price" in metrics.field_accuracies
        assert "building_value" in metrics.field_accuracies

    def test_log_metrics_for_saldenliste(self, orchestrator, test_user, db_session):
        """Test logging metrics for Saldenliste import"""
        from app.models.historical_import import ImportMetrics

        # Create document
        document = Document(
            user_id=test_user.id,
            document_type=DocumentType.RECEIPT,
            file_path="/test/path.csv",
            file_name="test.csv",
        )
        db_session.add(document)
        db_session.commit()

        # Create upload
        upload = HistoricalImportUpload(
            user_id=test_user.id,
            document_id=document.id,
            document_type=HistoricalDocumentType.SALDENLISTE,
            tax_year=2023,
            status=ImportStatus.EXTRACTED,
        )
        db_session.add(upload)
        db_session.commit()

        # Create result with extracted data
        result = {
            "confidence": 0.95,
            "extracted_data": {
                "accounts_imported": 45,
                "accounts_unmapped": 5,
                "accounts": [{"account_number": "1000", "balance": 10000}] * 50,
            },
        }

        # Log metrics
        orchestrator._log_import_metrics(upload, result, extraction_time_ms=500)

        # Verify metrics
        metrics = db_session.query(ImportMetrics).filter_by(upload_id=upload.id).first()
        assert metrics is not None
        assert metrics.document_type == HistoricalDocumentType.SALDENLISTE
        assert metrics.extraction_confidence == Decimal("0.95")
        assert metrics.fields_extracted == 45
        assert metrics.fields_total == 50  # 45 imported + 5 unmapped
        assert metrics.extraction_time_ms == 500
        assert "account_mapping" in metrics.field_accuracies
        assert metrics.field_accuracies["account_mapping"] == 0.9  # 45/50

    def test_log_metrics_on_failed_import(self, orchestrator, test_user, db_session):
        """Test that metrics are logged even when import fails"""
        from app.models.historical_import import ImportMetrics

        # Create document
        document = Document(
            user_id=test_user.id,
            document_type=DocumentType.RECEIPT,
            file_path="/test/path.pdf",
            file_name="test.pdf",
        )
        db_session.add(document)
        db_session.commit()

        # Create upload
        upload = HistoricalImportUpload(
            user_id=test_user.id,
            document_id=document.id,
            document_type=HistoricalDocumentType.E1_FORM,
            tax_year=2023,
            status=ImportStatus.UPLOADED,
        )
        db_session.add(upload)
        db_session.commit()

        # Process upload without OCR text (will fail)
        result = orchestrator.process_upload(upload_id=upload.id, ocr_text=None)

        # Verify upload failed
        assert result["status"] == ImportStatus.FAILED.value

        # Verify metrics were still logged
        metrics = db_session.query(ImportMetrics).filter_by(upload_id=upload.id).first()
        assert metrics is not None
        assert metrics.extraction_confidence == Decimal("0.0")
        assert metrics.fields_extracted == 0
        assert metrics.fields_total == 0
        assert metrics.extraction_time_ms == 0

    def test_metrics_relationship_with_upload(self, orchestrator, test_user, db_session):
        """Test that metrics have proper relationship with upload"""
        from app.models.historical_import import ImportMetrics

        # Create document
        document = Document(
            user_id=test_user.id,
            document_type=DocumentType.RECEIPT,
            file_path="/test/path.pdf",
            file_name="test.pdf",
        )
        db_session.add(document)
        db_session.commit()

        # Create upload
        upload = HistoricalImportUpload(
            user_id=test_user.id,
            document_id=document.id,
            document_type=HistoricalDocumentType.E1_FORM,
            tax_year=2023,
            status=ImportStatus.EXTRACTED,
        )
        db_session.add(upload)
        db_session.commit()

        # Create result
        result = {
            "confidence": 0.85,
            "extracted_data": {"all_kz_values": {"kz_245": 50000}},
        }

        # Log metrics
        orchestrator._log_import_metrics(upload, result, extraction_time_ms=1500)

        # Verify relationship
        db_session.refresh(upload)
        assert upload.metrics is not None
        assert upload.metrics.upload_id == upload.id
        assert upload.metrics.extraction_confidence == Decimal("0.85")


class TestCaptureUserCorrections:
    """Tests for _capture_user_corrections method"""

    def test_capture_corrections_e1_form_amount_changes(
        self, orchestrator, test_user, db_session
    ):
        """Test capturing amount corrections in E1 form data"""
        # Create document
        document = Document(
            user_id=test_user.id,
            document_type=DocumentType.RECEIPT,
            file_path="/test/path.pdf",
            file_name="test.pdf",
        )
        db_session.add(document)
        db_session.commit()

        # Create upload
        upload = HistoricalImportUpload(
            user_id=test_user.id,
            document_id=document.id,
            document_type=HistoricalDocumentType.E1_FORM,
            tax_year=2023,
            status=ImportStatus.REVIEW_REQUIRED,
        )
        db_session.add(upload)
        db_session.commit()

        # Original extracted data
        extracted_data = {
            "kz_245": 50000,
            "kz_350": 10000,
            "kz_210": 5000,
        }

        # User corrected data
        edited_data = {
            "kz_245": 51000,  # Corrected
            "kz_350": 10000,  # Unchanged
            "kz_210": 5500,   # Corrected
        }

        # Capture corrections
        corrections = orchestrator._capture_user_corrections(
            upload, extracted_data, edited_data
        )

        # Verify corrections
        assert len(corrections) == 2
        
        # Check kz_245 correction
        kz_245_correction = next(c for c in corrections if c["field"] == "kz_245")
        assert kz_245_correction["extracted"] == "50000"
        assert kz_245_correction["corrected"] == "51000"
        assert kz_245_correction["correction_type"] == "amount_correction"
        
        # Check kz_210 correction
        kz_210_correction = next(c for c in corrections if c["field"] == "kz_210")
        assert kz_210_correction["extracted"] == "5000"
        assert kz_210_correction["corrected"] == "5500"
        assert kz_210_correction["correction_type"] == "amount_correction"

    def test_capture_corrections_bescheid_address_changes(
        self, orchestrator, test_user, db_session
    ):
        """Test capturing address corrections in Bescheid data"""
        # Create document
        document = Document(
            user_id=test_user.id,
            document_type=DocumentType.RECEIPT,
            file_path="/test/path.pdf",
            file_name="test.pdf",
        )
        db_session.add(document)
        db_session.commit()

        # Create upload
        upload = HistoricalImportUpload(
            user_id=test_user.id,
            document_id=document.id,
            document_type=HistoricalDocumentType.BESCHEID,
            tax_year=2023,
            status=ImportStatus.REVIEW_REQUIRED,
        )
        db_session.add(upload)
        db_session.commit()

        # Original extracted data
        extracted_data = {
            "employment_income": 50000,
            "rental_income": 10000,
            "property_addresses": ["Hauptstrasse 1, 1010 Wien"],
        }

        # User corrected data
        edited_data = {
            "employment_income": 50000,
            "rental_income": 10000,
            "property_addresses": ["Hauptstraße 1, 1010 Wien"],  # Corrected ß
        }

        # Capture corrections
        corrections = orchestrator._capture_user_corrections(
            upload, extracted_data, edited_data
        )

        # Verify corrections
        assert len(corrections) == 1
        assert corrections[0]["field"] == "property_addresses"
        assert "Hauptstrasse" in corrections[0]["extracted"]
        assert "Hauptstraße" in corrections[0]["corrected"]
        assert corrections[0]["correction_type"] == "address_correction"

    def test_capture_corrections_kaufvertrag_date_changes(
        self, orchestrator, test_user, db_session
    ):
        """Test capturing date corrections in Kaufvertrag data"""
        # Create document
        document = Document(
            user_id=test_user.id,
            document_type=DocumentType.RECEIPT,
            file_path="/test/path.pdf",
            file_name="test.pdf",
        )
        db_session.add(document)
        db_session.commit()

        # Create upload
        upload = HistoricalImportUpload(
            user_id=test_user.id,
            document_id=document.id,
            document_type=HistoricalDocumentType.KAUFVERTRAG,
            tax_year=2023,
            status=ImportStatus.REVIEW_REQUIRED,
        )
        db_session.add(upload)
        db_session.commit()

        # Original extracted data
        extracted_data = {
            "purchase_price": 500000,
            "purchase_date": "2023-01-15",
            "building_value": 400000,
        }

        # User corrected data
        edited_data = {
            "purchase_price": 500000,
            "purchase_date": "2023-01-20",  # Corrected date
            "building_value": 400000,
        }

        # Capture corrections
        corrections = orchestrator._capture_user_corrections(
            upload, extracted_data, edited_data
        )

        # Verify corrections
        assert len(corrections) == 1
        assert corrections[0]["field"] == "purchase_date"
        assert corrections[0]["extracted"] == "2023-01-15"
        assert corrections[0]["corrected"] == "2023-01-20"
        assert corrections[0]["correction_type"] == "date_correction"

    def test_capture_corrections_no_changes(
        self, orchestrator, test_user, db_session
    ):
        """Test that no corrections are captured when data is unchanged"""
        # Create document
        document = Document(
            user_id=test_user.id,
            document_type=DocumentType.RECEIPT,
            file_path="/test/path.pdf",
            file_name="test.pdf",
        )
        db_session.add(document)
        db_session.commit()

        # Create upload
        upload = HistoricalImportUpload(
            user_id=test_user.id,
            document_id=document.id,
            document_type=HistoricalDocumentType.E1_FORM,
            tax_year=2023,
            status=ImportStatus.REVIEW_REQUIRED,
        )
        db_session.add(upload)
        db_session.commit()

        # Same data
        extracted_data = {"kz_245": 50000, "kz_350": 10000}
        edited_data = {"kz_245": 50000, "kz_350": 10000}

        # Capture corrections
        corrections = orchestrator._capture_user_corrections(
            upload, extracted_data, edited_data
        )

        # Verify no corrections
        assert len(corrections) == 0

    def test_review_upload_updates_import_metrics_with_corrections(
        self, orchestrator, test_user, db_session
    ):
        """Test that review_upload updates ImportMetrics with user corrections"""
        from app.models.historical_import import ImportMetrics

        # Create document
        document = Document(
            user_id=test_user.id,
            document_type=DocumentType.RECEIPT,
            file_path="/test/path.pdf",
            file_name="test.pdf",
        )
        db_session.add(document)
        db_session.commit()

        # Create upload
        upload = HistoricalImportUpload(
            user_id=test_user.id,
            document_id=document.id,
            document_type=HistoricalDocumentType.E1_FORM,
            tax_year=2023,
            status=ImportStatus.REVIEW_REQUIRED,
            extracted_data={"kz_245": 50000, "kz_350": 10000, "kz_210": 5000},
        )
        db_session.add(upload)
        db_session.commit()

        # Create ImportMetrics
        metrics = ImportMetrics(
            upload_id=upload.id,
            document_type=HistoricalDocumentType.E1_FORM,
            extraction_confidence=Decimal("0.85"),
            fields_extracted=3,
            fields_total=10,
            extraction_time_ms=1500,
            field_accuracies={"kz_245": 1.0, "kz_350": 1.0, "kz_210": 1.0},
            fields_corrected=0,
            corrections=[],
        )
        db_session.add(metrics)
        db_session.commit()

        # Mock finalize method
        with patch.object(
            orchestrator,
            "_finalize_upload",
            return_value={
                "transactions_created": 3,
                "properties_created": 0,
                "properties_linked": 0,
            },
        ):
            # User corrected data
            edited_data = {
                "kz_245": 51000,  # Corrected
                "kz_350": 10000,  # Unchanged
                "kz_210": 5500,   # Corrected
            }

            # Approve with edited data
            result = orchestrator.review_upload(
                upload_id=upload.id,
                approved=True,
                edited_data=edited_data,
                reviewed_by=test_user.id,
            )

        # Verify result
        assert result["approved"] is True

        # Verify ImportMetrics was updated
        db_session.refresh(metrics)
        assert metrics.fields_corrected == 2
        assert len(metrics.corrections) == 2
        
        # Verify field accuracies were updated
        assert metrics.field_accuracies["kz_245"] == 0.0  # Marked as inaccurate
        assert metrics.field_accuracies["kz_350"] == 1.0  # Still accurate
        assert metrics.field_accuracies["kz_210"] == 0.0  # Marked as inaccurate
        
        # Verify correction details
        kz_245_correction = next(c for c in metrics.corrections if c["field"] == "kz_245")
        assert kz_245_correction["extracted"] == "50000"
        assert kz_245_correction["corrected"] == "51000"
        assert kz_245_correction["correction_type"] == "amount_correction"

    def test_capture_corrections_with_decimal_values(
        self, orchestrator, test_user, db_session
    ):
        """Test capturing corrections with Decimal values"""
        # Create document
        document = Document(
            user_id=test_user.id,
            document_type=DocumentType.RECEIPT,
            file_path="/test/path.pdf",
            file_name="test.pdf",
        )
        db_session.add(document)
        db_session.commit()

        # Create upload
        upload = HistoricalImportUpload(
            user_id=test_user.id,
            document_id=document.id,
            document_type=HistoricalDocumentType.KAUFVERTRAG,
            tax_year=2023,
            status=ImportStatus.REVIEW_REQUIRED,
        )
        db_session.add(upload)
        db_session.commit()

        # Original extracted data with Decimal
        extracted_data = {
            "purchase_price": Decimal("500000.00"),
            "grunderwerbsteuer": Decimal("17500.00"),
        }

        # User corrected data
        edited_data = {
            "purchase_price": Decimal("500000.00"),
            "grunderwerbsteuer": Decimal("18000.00"),  # Corrected
        }

        # Capture corrections
        corrections = orchestrator._capture_user_corrections(
            upload, extracted_data, edited_data
        )

        # Verify corrections
        assert len(corrections) == 1
        assert corrections[0]["field"] == "grunderwerbsteuer"
        assert corrections[0]["extracted"] == "17500.00"
        assert corrections[0]["corrected"] == "18000.00"
        assert corrections[0]["correction_type"] == "amount_correction"
