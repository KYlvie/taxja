"""
Tests for DocumentPipelineOrchestrator — the AI dispatch layer for document processing.

Tests cover:
  - Classification arbitration (regex → filename → LLM fallback)
  - Cross-field validation for each document type
  - Confidence-based routing
  - Suggestion building with user confirmation gates
  - Pipeline end-to-end flow
"""
import pytest
from datetime import datetime, date
from decimal import Decimal
from unittest.mock import MagicMock, patch, PropertyMock

from app.services.document_pipeline_orchestrator import (
    DocumentPipelineOrchestrator,
    PipelineResult,
    PipelineStage,
    ConfidenceLevel,
    ClassificationResult,
    ValidationResult,
    ValidationIssue,
    OCR_TO_DB_TYPE_MAP,
    CONFIRMATION_REQUIRED_TYPES,
)
from app.services.document_classifier import DocumentType as OCRDocumentType
from app.services.ocr_engine import OCREngine, OCRResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ocr_result(
    doc_type=OCRDocumentType.INVOICE,
    confidence=0.85,
    extracted_data=None,
    raw_text="Test OCR text",
):
    return OCRResult(
        document_type=doc_type,
        extracted_data=extracted_data or {"amount": 100, "date": "2025-01-15"},
        raw_text=raw_text,
        confidence_score=confidence,
        needs_review=confidence < 0.7,
        processing_time_ms=100.0,
        suggestions=[],
    )


def _make_document(
    doc_id=1,
    user_id=1,
    file_name="rechnung.pdf",
    doc_type="other",
    ocr_result=None,
):
    """Create a mock Document object."""
    doc = MagicMock()
    doc.id = doc_id
    doc.user_id = user_id
    doc.file_name = file_name
    doc.file_path = f"docs/{file_name}"
    doc.mime_type = "application/pdf"
    doc.document_type = doc_type
    doc.ocr_result = ocr_result or {}
    doc.raw_text = None
    doc.confidence_score = None
    doc.processed_at = None
    doc.uploaded_at = datetime(2025, 1, 15)
    return doc


# ---------------------------------------------------------------------------
# Classification tests
# ---------------------------------------------------------------------------

class TestClassification:
    """Test multi-signal classification arbitration."""

    def test_regex_classification_high_confidence(self):
        """OCR engine classifies with high confidence → use it directly."""
        db = MagicMock()
        orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        orchestrator.db = db

        document = _make_document(file_name="scan.pdf")
        ocr_result = _make_ocr_result(
            doc_type=OCRDocumentType.INVOICE, confidence=0.85
        )
        result = PipelineResult(document_id=1)

        from app.models.document import DocumentType as DBDocumentType
        db_type = orchestrator._stage_classify(document, ocr_result, result)

        assert db_type == DBDocumentType.INVOICE
        assert result.classification.method == "regex"
        assert result.classification.confidence == 0.85

    def test_filename_override_when_ocr_weak(self):
        """OCR says UNKNOWN but filename says 'kaufvertrag' → use filename."""
        db = MagicMock()
        orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        orchestrator.db = db

        document = _make_document(file_name="kaufvertrag_2025.pdf")
        ocr_result = _make_ocr_result(
            doc_type=OCRDocumentType.UNKNOWN, confidence=0.3
        )
        result = PipelineResult(document_id=1)

        from app.models.document import DocumentType as DBDocumentType
        db_type = orchestrator._stage_classify(document, ocr_result, result)

        assert db_type == DBDocumentType.PURCHASE_CONTRACT
        assert result.classification.method == "filename"

    def test_filename_mietvertrag_variants(self):
        """Filename with 'miete' or 'pacht' → rental contract."""
        orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        orchestrator.db = MagicMock()

        from app.models.document import DocumentType as DBDocumentType

        for fname in ["mietvertrag.pdf", "miete_jan2025.pdf", "pachtvertrag.pdf"]:
            result = orchestrator._classify_by_filename(fname)
            assert result == DBDocumentType.RENTAL_CONTRACT, f"Failed for {fname}"

    def test_filename_no_match(self):
        """Generic filename → no override."""
        orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        orchestrator.db = MagicMock()

        result = orchestrator._classify_by_filename("IMG_20250115.jpg")
        assert result is None

    @patch("app.services.document_pipeline_orchestrator.DocumentPipelineOrchestrator._try_llm_classification")
    def test_llm_fallback_when_still_unknown(self, mock_llm):
        """OCR=UNKNOWN, filename=generic → try LLM classification."""
        from app.models.document import DocumentType as DBDocumentType
        mock_llm.return_value = DBDocumentType.RECEIPT

        db = MagicMock()
        orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        orchestrator.db = db

        document = _make_document(file_name="IMG_20250115.jpg")
        ocr_result = _make_ocr_result(
            doc_type=OCRDocumentType.UNKNOWN, confidence=0.2,
            raw_text="BILLA Supermarkt Summe EUR 42.50"
        )
        result = PipelineResult(document_id=1)

        db_type = orchestrator._stage_classify(document, ocr_result, result)

        assert db_type == DBDocumentType.RECEIPT
        assert result.classification.method == "llm"
        assert result.classification.needs_llm_arbitration is True

    def test_ocr_type_mapping(self):
        """All OCR types map correctly to DB types."""
        from app.models.document import DocumentType as DBDocumentType

        assert OCR_TO_DB_TYPE_MAP[OCRDocumentType.KAUFVERTRAG] == DBDocumentType.PURCHASE_CONTRACT
        assert OCR_TO_DB_TYPE_MAP[OCRDocumentType.MIETVERTRAG] == DBDocumentType.RENTAL_CONTRACT
        assert OCR_TO_DB_TYPE_MAP[OCRDocumentType.E1_FORM] == DBDocumentType.E1_FORM
        assert OCR_TO_DB_TYPE_MAP[OCRDocumentType.UNKNOWN] == DBDocumentType.OTHER


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

class TestValidation:
    """Test cross-field validation for extracted data."""

    def _make_orchestrator(self):
        o = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        o.db = MagicMock()
        return o

    def test_valid_invoice(self):
        """Invoice with consistent amount + VAT passes validation."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {
            "amount": 120.0,
            "vat_amount": 20.0,
            "vat_rate": 20,
            "merchant": "Test GmbH",
            "date": "2025-03-15",
        }

        validation = orchestrator._stage_validate(DBDocumentType.INVOICE, data, result)
        assert validation.is_valid
        assert validation.error_count == 0

    def test_invalid_vat_mismatch(self):
        """VAT amount doesn't match rate → warning."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {
            "amount": 120.0,
            "vat_amount": 50.0,  # Should be ~20 for 20%
            "vat_rate": 20,
            "merchant": "Test GmbH",
            "date": "2025-03-15",
        }

        validation = orchestrator._stage_validate(DBDocumentType.INVOICE, data, result)
        vat_issues = [i for i in validation.issues if i.field == "vat_amount"]
        assert len(vat_issues) == 1
        assert "doesn't match" in vat_issues[0].issue

    def test_negative_amount_warning(self):
        """Negative amount produces a warning."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {"amount": -50.0, "date": "2025-03-15"}
        validation = orchestrator._stage_validate(DBDocumentType.RECEIPT, data, result)

        amount_issues = [i for i in validation.issues if i.field == "amount"]
        assert any("Negative" in i.issue for i in amount_issues)

    def test_future_date_warning(self):
        """Date in the future produces a warning."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {"amount": 100, "date": "2099-12-31"}
        validation = orchestrator._stage_validate(DBDocumentType.RECEIPT, data, result)

        date_issues = [i for i in validation.issues if i.field == "date"]
        assert any("future" in i.issue for i in date_issues)

    def test_empty_data_is_error(self):
        """No extracted data → validation error."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        validation = orchestrator._stage_validate(DBDocumentType.RECEIPT, {}, result)
        assert not validation.is_valid
        assert validation.error_count == 1

    def test_receipt_no_amount_is_error(self):
        """Receipt without amount is an error."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {"merchant": "BILLA"}
        validation = orchestrator._stage_validate(DBDocumentType.RECEIPT, data, result)
        assert not validation.is_valid

    def test_receipt_line_items_mismatch(self):
        """Line items sum doesn't match total → warning."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {
            "amount": 100.0,
            "line_items": [
                {"name": "Item A", "amount": 30.0},
                {"name": "Item B", "amount": 25.0},
            ],
        }
        validation = orchestrator._stage_validate(DBDocumentType.RECEIPT, data, result)
        items_issues = [i for i in validation.issues if i.field == "line_items"]
        assert len(items_issues) == 1

    def test_kaufvertrag_missing_price_is_error(self):
        """Kaufvertrag without purchase_price is an error."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {"property_address": "Wien 1010"}
        validation = orchestrator._stage_validate(DBDocumentType.PURCHASE_CONTRACT, data, result)
        assert not validation.is_valid

    def test_kaufvertrag_building_land_mismatch(self):
        """Building + land value doesn't match purchase price → warning."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {
            "purchase_price": 300000,
            "building_value": 100000,
            "land_value": 100000,  # 200k != 300k
            "property_address": "Wien 1010",
            "date": "2025-01-15",
        }
        validation = orchestrator._stage_validate(DBDocumentType.PURCHASE_CONTRACT, data, result)
        building_issues = [i for i in validation.issues if i.field == "building_value"]
        assert len(building_issues) == 1

    def test_mietvertrag_missing_rent_is_error(self):
        """Mietvertrag without monthly_rent is an error."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {"property_address": "Wien 1010"}
        validation = orchestrator._stage_validate(DBDocumentType.RENTAL_CONTRACT, data, result)
        assert not validation.is_valid

    def test_mietvertrag_low_rent_warning(self):
        """Unusually low rent → warning."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {"monthly_rent": 50, "property_address": "Wien"}
        validation = orchestrator._stage_validate(DBDocumentType.RENTAL_CONTRACT, data, result)
        rent_issues = [i for i in validation.issues if i.field == "monthly_rent"]
        assert any("low" in i.issue for i in rent_issues)

    def test_mietvertrag_high_rent_warning(self):
        """Unusually high rent → warning."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {"monthly_rent": 15000, "property_address": "Wien"}
        validation = orchestrator._stage_validate(DBDocumentType.RENTAL_CONTRACT, data, result)
        rent_issues = [i for i in validation.issues if i.field == "monthly_rent"]
        assert any("high" in i.issue for i in rent_issues)

    def test_old_date_warning(self):
        """Date before 2000 → warning."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {"amount": 100, "date": "1990-05-15"}
        validation = orchestrator._stage_validate(DBDocumentType.INVOICE, data, result)
        date_issues = [i for i in validation.issues if i.field == "date"]
        assert any("too old" in i.issue for i in date_issues)


# ---------------------------------------------------------------------------
# Confidence assessment tests
# ---------------------------------------------------------------------------

class TestConfidenceAssessment:
    """Test confidence level determination."""

    def _make_orchestrator(self):
        o = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        o.db = MagicMock()
        return o

    def test_high_confidence_no_issues(self):
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        validation = ValidationResult(is_valid=True)

        level = orchestrator._assess_confidence(0.9, DBDocumentType.INVOICE, validation)
        assert level == ConfidenceLevel.HIGH

    def test_medium_confidence(self):
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        validation = ValidationResult(is_valid=True)

        level = orchestrator._assess_confidence(0.65, DBDocumentType.INVOICE, validation)
        assert level == ConfidenceLevel.MEDIUM

    def test_low_confidence(self):
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        validation = ValidationResult(is_valid=True)

        level = orchestrator._assess_confidence(0.3, DBDocumentType.INVOICE, validation)
        assert level == ConfidenceLevel.LOW

    def test_errors_reduce_confidence(self):
        """Validation errors should push confidence down."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        validation = ValidationResult(
            is_valid=False,
            issues=[ValidationIssue(field="amount", issue="invalid", severity="error")],
        )

        level = orchestrator._assess_confidence(0.9, DBDocumentType.INVOICE, validation)
        # 0.9 * 0.5 = 0.45 → LOW
        assert level == ConfidenceLevel.LOW

    def test_many_warnings_reduce_confidence(self):
        """Multiple warnings reduce confidence level."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        validation = ValidationResult(
            is_valid=True,
            issues=[
                ValidationIssue(field=f"f{i}", issue="warn", severity="warning")
                for i in range(3)
            ],
        )

        level = orchestrator._assess_confidence(0.85, DBDocumentType.INVOICE, validation)
        # 0.85 * 0.7 = 0.595 → MEDIUM
        assert level == ConfidenceLevel.MEDIUM


# ---------------------------------------------------------------------------
# Confirmation gate tests
# ---------------------------------------------------------------------------

class TestConfirmationGates:
    """Test that high-value documents require user confirmation."""

    def test_kaufvertrag_requires_confirmation(self):
        from app.models.document import DocumentType as DBDocumentType
        assert DBDocumentType.PURCHASE_CONTRACT in CONFIRMATION_REQUIRED_TYPES

    def test_mietvertrag_requires_confirmation(self):
        from app.models.document import DocumentType as DBDocumentType
        assert DBDocumentType.RENTAL_CONTRACT in CONFIRMATION_REQUIRED_TYPES

    def test_receipt_does_not_require_confirmation(self):
        from app.models.document import DocumentType as DBDocumentType
        assert DBDocumentType.RECEIPT not in CONFIRMATION_REQUIRED_TYPES

    def test_invoice_does_not_require_confirmation(self):
        from app.models.document import DocumentType as DBDocumentType
        assert DBDocumentType.INVOICE not in CONFIRMATION_REQUIRED_TYPES


# ---------------------------------------------------------------------------
# Pipeline result serialization tests
# ---------------------------------------------------------------------------

class TestPipelineResult:
    """Test PipelineResult to_dict serialization."""

    def test_basic_serialization(self):
        result = PipelineResult(
            document_id=42,
            stage_reached=PipelineStage.SUGGEST,
            extracted_data={"amount": 100},
            raw_text="test",
            needs_review=False,
            confidence_level=ConfidenceLevel.HIGH,
            processing_time_ms=250.0,
        )
        d = result.to_dict()
        assert d["document_id"] == 42
        assert d["stage_reached"] == "suggest"
        assert d["confidence_level"] == "high"
        assert d["needs_review"] is False

    def test_with_classification(self):
        result = PipelineResult(
            document_id=1,
            stage_reached=PipelineStage.CLASSIFY,
            classification=ClassificationResult(
                document_type="invoice",
                confidence=0.9,
                method="regex",
            ),
        )
        d = result.to_dict()
        assert d["classification"]["document_type"] == "invoice"
        assert d["classification"]["method"] == "regex"

    def test_with_validation(self):
        result = PipelineResult(
            document_id=1,
            stage_reached=PipelineStage.VALIDATE,
            validation=ValidationResult(
                is_valid=False,
                issues=[
                    ValidationIssue(field="amount", issue="negative", severity="error"),
                ],
            ),
        )
        d = result.to_dict()
        assert d["validation"]["is_valid"] is False
        assert len(d["validation"]["issues"]) == 1

    def test_audit_log(self):
        result = PipelineResult(document_id=1, stage_reached=PipelineStage.CLASSIFY)
        result.audit_log.append({
            "timestamp": "2025-01-15T10:00:00",
            "stage": "classify",
            "message": "test",
        })
        d = result.to_dict()
        assert len(d["audit_log"]) == 1


# ---------------------------------------------------------------------------
# End-to-end pipeline tests (mocked dependencies)
# ---------------------------------------------------------------------------

class TestPipelineEndToEnd:
    """Integration tests for the full pipeline with mocked DB + storage."""

    @patch("app.services.storage_service.StorageService")
    def test_full_pipeline_invoice(self, mock_storage_class):
        """Full pipeline for a simple invoice."""
        from app.models.document import DocumentType as DBDocumentType

        # Mock DB
        db = MagicMock()
        document = _make_document(file_name="rechnung_2025.pdf")
        document.document_type = DBDocumentType.OTHER
        db.query.return_value.filter.return_value.first.return_value = document

        # Mock storage
        mock_storage = MagicMock()
        mock_storage.download_file.return_value = b"fake pdf bytes"
        mock_storage_class.return_value = mock_storage

        # Mock OCR engine
        ocr_result = _make_ocr_result(
            doc_type=OCRDocumentType.INVOICE,
            confidence=0.85,
            extracted_data={
                "amount": 120.0,
                "vat_amount": 20.0,
                "vat_rate": 20,
                "merchant": "Test GmbH",
                "date": "2025-03-15",
            },
        )

        with patch.object(OCREngine, "process_document", return_value=ocr_result):
            orchestrator = DocumentPipelineOrchestrator(db)
            result = orchestrator.process_document(1)

        assert result.error is None
        assert result.stage_reached == PipelineStage.SUGGEST
        assert result.classification.document_type == DBDocumentType.INVOICE.value
        assert result.validation.is_valid

    @patch("app.services.storage_service.StorageService")
    def test_kaufvertrag_never_auto_creates(self, mock_storage_class):
        """Kaufvertrag should build suggestion but never auto-create property."""
        from app.models.document import DocumentType as DBDocumentType

        db = MagicMock()
        document = _make_document(file_name="kaufvertrag.pdf")
        document.document_type = DBDocumentType.OTHER
        db.query.return_value.filter.return_value.first.return_value = document

        mock_storage = MagicMock()
        mock_storage.download_file.return_value = b"fake pdf"
        mock_storage_class.return_value = mock_storage

        ocr_result = _make_ocr_result(
            doc_type=OCRDocumentType.KAUFVERTRAG,
            confidence=0.9,
            extracted_data={
                "purchase_price": 300000,
                "property_address": "Stephansplatz 1, 1010 Wien",
                "date": "2025-01-15",
            },
        )

        with patch.object(OCREngine, "process_document", return_value=ocr_result):
            orchestrator = DocumentPipelineOrchestrator(db)
            # Mock the suggestion builder to avoid importing ocr_tasks internals
            with patch.object(orchestrator, "_build_kaufvertrag_suggestion") as mock_suggest:
                mock_suggest.return_value = {
                    "type": "create_property",
                    "status": "pending",
                    "data": {"purchase_price": 300000},
                }
                result = orchestrator.process_document(1)

        # Must require review (confirmation gate)
        assert result.needs_review is True
        # Suggestion should be pending, not confirmed
        if result.suggestions:
            assert result.suggestions[0]["status"] == "pending"

    @patch("app.services.storage_service.StorageService")
    def test_document_not_found(self, mock_storage_class):
        """Non-existent document → error result."""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        orchestrator = DocumentPipelineOrchestrator(db)
        result = orchestrator.process_document(999)

        assert result.error is not None
        assert "not found" in result.error

    @patch("app.services.storage_service.StorageService")
    def test_storage_download_failure(self, mock_storage_class):
        """Storage download failure → graceful error."""
        db = MagicMock()
        document = _make_document()
        db.query.return_value.filter.return_value.first.return_value = document

        mock_storage = MagicMock()
        mock_storage.download_file.side_effect = Exception("S3 connection timeout")
        mock_storage_class.return_value = mock_storage

        orchestrator = DocumentPipelineOrchestrator(db)
        result = orchestrator.process_document(1)

        assert result.error is not None
        assert "download" in result.error.lower() or "S3" in result.error

    @patch("app.services.storage_service.StorageService")
    def test_low_confidence_forces_review(self, mock_storage_class):
        """Low OCR confidence → needs_review=True."""
        from app.models.document import DocumentType as DBDocumentType

        db = MagicMock()
        document = _make_document(file_name="blurry_scan.jpg")
        document.document_type = DBDocumentType.OTHER
        db.query.return_value.filter.return_value.first.return_value = document

        mock_storage = MagicMock()
        mock_storage.download_file.return_value = b"fake"
        mock_storage_class.return_value = mock_storage

        ocr_result = _make_ocr_result(
            doc_type=OCRDocumentType.UNKNOWN,
            confidence=0.25,
            extracted_data={"amount": 42},
        )

        with patch.object(OCREngine, "process_document", return_value=ocr_result):
            orchestrator = DocumentPipelineOrchestrator(db)
            result = orchestrator.process_document(1)

        assert result.needs_review is True
        assert result.confidence_level == ConfidenceLevel.LOW


# ---------------------------------------------------------------------------
# ValidationResult property tests
# ---------------------------------------------------------------------------

class TestValidationResultProperties:

    def test_error_count(self):
        v = ValidationResult(
            is_valid=False,
            issues=[
                ValidationIssue(field="a", issue="bad", severity="error"),
                ValidationIssue(field="b", issue="warn", severity="warning"),
                ValidationIssue(field="c", issue="bad2", severity="error"),
            ],
        )
        assert v.error_count == 2
        assert v.warning_count == 1

    def test_empty_validation(self):
        v = ValidationResult(is_valid=True)
        assert v.error_count == 0
        assert v.warning_count == 0
