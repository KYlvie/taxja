"""Unit tests for historical import OCR task"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4
from decimal import Decimal
from datetime import datetime
from celery.exceptions import Retry as CeleryRetry

from app.models.historical_import import (
    HistoricalImportUpload,
    ImportStatus,
    HistoricalDocumentType,
)
from app.models.document import Document


@pytest.fixture
def mock_db():
    """Mock database session"""
    db = Mock()
    db.commit = Mock()
    db.rollback = Mock()
    db.close = Mock()
    db.query = Mock()
    return db


@pytest.fixture
def mock_upload():
    """Mock HistoricalImportUpload record"""
    upload = Mock(spec=HistoricalImportUpload)
    upload.id = uuid4()
    upload.document_id = 1
    upload.document_type = HistoricalDocumentType.E1_FORM
    upload.tax_year = 2023
    upload.status = ImportStatus.UPLOADED
    upload.ocr_task_id = None
    upload.extracted_data = None
    upload.extraction_confidence = None
    upload.requires_review = False
    upload.errors = []
    return upload


@pytest.fixture
def mock_document():
    """Mock Document record"""
    document = Mock(spec=Document)
    document.id = 1
    document.file_path = "test/path/document.pdf"
    document.file_name = "document.pdf"
    return document


@pytest.fixture
def mock_task():
    """Mock bound Celery task instance."""
    task = Mock()
    task.request = Mock()
    task.request.id = "test-task-id"
    task.request.retries = 0
    task.max_retries = 3
    task.retry = Mock(side_effect=CeleryRetry("Retry triggered"))
    return task


def invoke_historical_import_ocr(task, upload_id: str):
    """Call the bound historical import OCR task with an explicit fake task object."""
    from app.tasks.ocr_tasks import process_historical_import_ocr

    return process_historical_import_ocr.run.__func__(task, upload_id)


class TestProcessHistoricalImportOCR:
    """Test suite for process_historical_import_ocr task"""

    @patch("app.db.base.SessionLocal")
    @patch("app.services.storage_service.StorageService")
    @patch("app.tasks.ocr_tasks.OCREngine")
    @patch("app.services.e1_form_extractor.E1FormExtractor")
    def test_successful_e1_form_extraction(
        self, mock_e1_extractor, mock_ocr_engine, mock_storage, mock_session, mock_upload, mock_document, mock_task
    ):
        """Test successful E1 form OCR and extraction"""
        # Setup mocks
        db = Mock()
        mock_session.return_value = db

        # Mock database queries
        db.query.return_value.filter.return_value.first.side_effect = [
            mock_upload,  # First call for upload
            mock_document,  # Second call for document
        ]

        # Mock storage service
        storage_instance = Mock()
        storage_instance.download_file.return_value = b"fake_pdf_bytes"
        mock_storage.return_value = storage_instance

        # Mock OCR engine
        ocr_instance = Mock()
        ocr_result = Mock()
        ocr_result.raw_text = "E1 form text with KZ values"
        ocr_result.confidence_score = 0.85
        ocr_instance.process_document.return_value = ocr_result
        mock_ocr_engine.return_value = ocr_instance

        # Mock E1 extractor
        extractor_instance = Mock()
        e1_data = Mock()
        e1_data.confidence = 0.85
        extractor_instance.extract.return_value = e1_data
        extractor_instance.to_dict.return_value = {
            "tax_year": 2023,
            "kz_245": "50000.00",
            "confidence": 0.85,
        }
        mock_e1_extractor.return_value = extractor_instance

        # Execute task
        result = invoke_historical_import_ocr(mock_task, str(mock_upload.id))

        # Verify result
        assert result["upload_id"] == str(mock_upload.id)
        assert result["status"] == ImportStatus.EXTRACTED.value
        assert result["confidence"] == 0.85
        assert result["requires_review"] is False
        assert result["document_type"] == HistoricalDocumentType.E1_FORM.value

        # Verify upload was updated
        assert mock_upload.status == ImportStatus.EXTRACTED
        assert mock_upload.extraction_confidence == Decimal("0.85")
        assert mock_upload.requires_review is False

    @patch("app.db.base.SessionLocal")
    @patch("app.services.storage_service.StorageService")
    @patch("app.tasks.ocr_tasks.OCREngine")
    @patch("app.services.bescheid_extractor.BescheidExtractor")
    def test_low_confidence_requires_review(
        self, mock_bescheid_extractor, mock_ocr_engine, mock_storage, mock_session, mock_upload, mock_document, mock_task
    ):
        """Test that low confidence extraction triggers review requirement"""
        # Setup mocks
        db = Mock()
        mock_session.return_value = db
        mock_upload.document_type = HistoricalDocumentType.BESCHEID

        db.query.return_value.filter.return_value.first.side_effect = [
            mock_upload,
            mock_document,
        ]

        storage_instance = Mock()
        storage_instance.download_file.return_value = b"fake_pdf_bytes"
        mock_storage.return_value = storage_instance

        ocr_instance = Mock()
        ocr_result = Mock()
        ocr_result.raw_text = "Bescheid text"
        ocr_result.confidence_score = 0.65
        ocr_instance.process_document.return_value = ocr_result
        mock_ocr_engine.return_value = ocr_instance

        # Mock low confidence extraction
        extractor_instance = Mock()
        bescheid_data = Mock()
        bescheid_data.confidence = 0.65  # Below 0.7 threshold
        extractor_instance.extract.return_value = bescheid_data
        extractor_instance.to_dict.return_value = {
            "tax_year": 2023,
            "confidence": 0.65,
        }
        mock_bescheid_extractor.return_value = extractor_instance

        # Execute task
        result = invoke_historical_import_ocr(mock_task, str(mock_upload.id))

        # Verify review is required
        assert result["requires_review"] is True
        assert result["status"] == ImportStatus.REVIEW_REQUIRED.value
        assert mock_upload.status == ImportStatus.REVIEW_REQUIRED
        assert mock_upload.requires_review is True

    @patch("app.db.base.SessionLocal")
    @patch("app.services.storage_service.StorageService")
    @patch("app.tasks.ocr_tasks.OCREngine")
    @patch("app.services.kaufvertrag_extractor.KaufvertragExtractor")
    def test_kaufvertrag_extraction(
        self, mock_kaufvertrag_extractor, mock_ocr_engine, mock_storage, mock_session, mock_upload, mock_document, mock_task
    ):
        """Test Kaufvertrag extraction with lower confidence threshold"""
        # Setup mocks
        db = Mock()
        mock_session.return_value = db
        mock_upload.document_type = HistoricalDocumentType.KAUFVERTRAG

        db.query.return_value.filter.return_value.first.side_effect = [
            mock_upload,
            mock_document,
        ]

        storage_instance = Mock()
        storage_instance.download_file.return_value = b"fake_pdf_bytes"
        mock_storage.return_value = storage_instance

        ocr_instance = Mock()
        ocr_result = Mock()
        ocr_result.raw_text = "Kaufvertrag text"
        ocr_result.confidence_score = 0.65
        ocr_instance.process_document.return_value = ocr_result
        mock_ocr_engine.return_value = ocr_instance

        # Mock Kaufvertrag extraction with 0.65 confidence (above 0.6 threshold)
        extractor_instance = Mock()
        kaufvertrag_data = Mock()
        kaufvertrag_data.confidence = 0.65
        extractor_instance.extract.return_value = kaufvertrag_data
        extractor_instance.to_dict.return_value = {
            "purchase_price": "300000.00",
            "confidence": 0.65,
        }
        mock_kaufvertrag_extractor.return_value = extractor_instance

        # Execute task
        result = invoke_historical_import_ocr(mock_task, str(mock_upload.id))

        # Verify Kaufvertrag passes with 0.65 confidence (threshold is 0.6)
        assert result["requires_review"] is False
        assert result["status"] == ImportStatus.EXTRACTED.value

    @patch("app.db.base.SessionLocal")
    def test_saldenliste_skips_ocr(self, mock_session, mock_upload, mock_document, mock_task):
        """Test that Saldenliste skips OCR and marks as extracted"""
        # Setup mocks
        db = Mock()
        mock_session.return_value = db
        mock_upload.document_type = HistoricalDocumentType.SALDENLISTE

        db.query.return_value.filter.return_value.first.side_effect = [
            mock_upload,
            mock_document,
        ]

        # Mock storage service (should not be called for Saldenliste)
        with patch("app.services.storage_service.StorageService") as mock_storage:
            storage_instance = Mock()
            storage_instance.download_file.return_value = b"fake_csv_bytes"
            mock_storage.return_value = storage_instance

            # Execute task
            result = invoke_historical_import_ocr(mock_task, str(mock_upload.id))

            # Verify Saldenliste is marked as extracted with high confidence
            assert result["status"] == ImportStatus.EXTRACTED.value
            assert result["confidence"] == 1.0
            assert result["requires_review"] is False
            assert "file_path" in result["extracted_data"]

    @patch("app.db.base.SessionLocal")
    def test_invalid_upload_id(self, mock_session, mock_task):
        """Test handling of invalid upload_id format"""
        db = Mock()
        mock_session.return_value = db

        # Execute task with invalid UUID
        result = invoke_historical_import_ocr(mock_task, "invalid-uuid")

        # Verify error response
        assert "error" in result
        assert result["error"] == "Invalid upload_id format"

    @patch("app.db.base.SessionLocal")
    def test_upload_not_found(self, mock_session, mock_task):
        """Test handling of non-existent upload"""
        db = Mock()
        mock_session.return_value = db
        db.query.return_value.filter.return_value.first.return_value = None

        upload_id = str(uuid4())

        # Execute task
        result = invoke_historical_import_ocr(mock_task, upload_id)

        # Verify error response
        assert "error" in result
        assert result["error"] == "Upload not found"

    @patch("app.db.base.SessionLocal")
    @patch("app.services.storage_service.StorageService")
    def test_storage_error_with_retry(self, mock_storage, mock_session, mock_upload, mock_document):
        """Test retry logic for transient storage errors"""
        # Setup mocks
        db = Mock()
        mock_session.return_value = db

        db.query.return_value.filter.return_value.first.side_effect = [
            mock_upload,
            mock_document,
        ]

        # Mock storage failure
        storage_instance = Mock()
        storage_instance.download_file.side_effect = Exception("Transient storage error")
        mock_storage.return_value = storage_instance

        # Create mock task with retry capability
        mock_task = Mock()
        mock_task.request = Mock()
        mock_task.request.retries = 0
        mock_task.max_retries = 3
        mock_task.retry = Mock(side_effect=CeleryRetry("Retry triggered"))

        # Execute task and expect retry
        with pytest.raises(CeleryRetry):
            invoke_historical_import_ocr(mock_task, str(mock_upload.id))

        # Verify retry was called
        mock_task.retry.assert_called_once()

    @patch("app.db.base.SessionLocal")
    @patch("app.services.storage_service.StorageService")
    @patch("app.tasks.ocr_tasks.OCREngine")
    def test_ocr_failure_updates_status(
        self, mock_ocr_engine, mock_storage, mock_session, mock_upload, mock_document
    ):
        """Test that OCR failure updates upload status to FAILED"""
        # Setup mocks
        db = Mock()
        mock_session.return_value = db

        db.query.return_value.filter.return_value.first.side_effect = [
            mock_upload,
            mock_document,
        ]

        storage_instance = Mock()
        storage_instance.download_file.return_value = b"fake_pdf_bytes"
        mock_storage.return_value = storage_instance

        # Mock OCR failure
        ocr_instance = Mock()
        ocr_instance.process_document.side_effect = Exception("OCR engine failed")
        mock_ocr_engine.return_value = ocr_instance

        # Create mock task that exhausted retries
        mock_task = Mock()
        mock_task.request.retries = 3
        mock_task.max_retries = 3

        # Execute task
        result = invoke_historical_import_ocr(mock_task, str(mock_upload.id))

        # Verify upload status was updated to FAILED
        assert mock_upload.status == ImportStatus.FAILED
        assert len(mock_upload.errors) > 0
        assert "OCR processing failed" in result["error"]

    @patch("app.db.base.SessionLocal")
    @patch("app.services.storage_service.StorageService")
    @patch("app.tasks.ocr_tasks.OCREngine")
    @patch("app.services.e1_form_extractor.E1FormExtractor")
    def test_extraction_failure_updates_status(
        self, mock_e1_extractor, mock_ocr_engine, mock_storage, mock_session, mock_upload, mock_document, mock_task
    ):
        """Test that extraction failure updates upload status to FAILED"""
        # Setup mocks
        db = Mock()
        mock_session.return_value = db

        db.query.return_value.filter.return_value.first.side_effect = [
            mock_upload,
            mock_document,
        ]

        storage_instance = Mock()
        storage_instance.download_file.return_value = b"fake_pdf_bytes"
        mock_storage.return_value = storage_instance

        ocr_instance = Mock()
        ocr_result = Mock()
        ocr_result.raw_text = "E1 form text"
        ocr_result.confidence_score = 0.85
        ocr_instance.process_document.return_value = ocr_result
        mock_ocr_engine.return_value = ocr_instance

        # Mock extraction failure
        extractor_instance = Mock()
        extractor_instance.extract.side_effect = Exception("Extraction failed")
        mock_e1_extractor.return_value = extractor_instance

        # Execute task
        result = invoke_historical_import_ocr(mock_task, str(mock_upload.id))

        # Verify upload status was updated to FAILED
        assert mock_upload.status == ImportStatus.FAILED
        assert len(mock_upload.errors) > 0
        assert "Data extraction failed" in result["error"]

    @patch("app.db.base.SessionLocal")
    @patch("app.services.storage_service.StorageService")
    @patch("app.tasks.ocr_tasks.OCREngine")
    @patch("app.services.e1_form_extractor.E1FormExtractor")
    def test_task_id_stored_in_upload(
        self, mock_e1_extractor, mock_ocr_engine, mock_storage, mock_session, mock_upload, mock_document
    ):
        """Test that Celery task ID is stored in upload record"""
        # Setup mocks
        db = Mock()
        mock_session.return_value = db

        db.query.return_value.filter.return_value.first.side_effect = [
            mock_upload,
            mock_document,
        ]

        storage_instance = Mock()
        storage_instance.download_file.return_value = b"fake_pdf_bytes"
        mock_storage.return_value = storage_instance

        ocr_instance = Mock()
        ocr_result = Mock()
        ocr_result.raw_text = "E1 form text"
        ocr_result.confidence_score = 0.85
        ocr_instance.process_document.return_value = ocr_result
        mock_ocr_engine.return_value = ocr_instance

        extractor_instance = Mock()
        e1_data = Mock()
        e1_data.confidence = 0.85
        extractor_instance.extract.return_value = e1_data
        extractor_instance.to_dict.return_value = {"confidence": 0.85}
        mock_e1_extractor.return_value = extractor_instance

        # Create mock task with ID
        mock_task = Mock()
        mock_task.request.id = "test-task-id-12345"

        # Execute task
        invoke_historical_import_ocr(mock_task, str(mock_upload.id))

        # Verify task ID was stored
        assert mock_upload.ocr_task_id == "test-task-id-12345"
