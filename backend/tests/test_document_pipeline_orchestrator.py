"""
Tests for DocumentPipelineOrchestrator — auto-everything AI dispatch layer.

Tests cover:
  - Classification arbitration (regex → filename → LLM fallback)
  - Auto-fix validation (negative→abs, missing→defaults, VAT→calculate)
  - Confidence assessment (lenient — only errors drop to LOW)
  - Auto-creation for ALL document types
  - User-friendly notification messages
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
# Classification tests (unchanged — still valid)
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
        orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        orchestrator.db = MagicMock()
        from app.models.document import DocumentType as DBDocumentType

        for fname in ["mietvertrag.pdf", "miete_jan2025.pdf", "pachtvertrag.pdf"]:
            result = orchestrator._classify_by_filename(fname)
            assert result == DBDocumentType.RENTAL_CONTRACT, f"Failed for {fname}"

    def test_filename_no_match(self):
        orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        orchestrator.db = MagicMock()
        result = orchestrator._classify_by_filename("IMG_20250115.jpg")
        assert result is None

    @patch("app.services.document_pipeline_orchestrator.DocumentPipelineOrchestrator._try_llm_classification")
    def test_llm_fallback_when_still_unknown(self, mock_llm):
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

    def test_ocr_type_mapping(self):
        from app.models.document import DocumentType as DBDocumentType
        assert OCR_TO_DB_TYPE_MAP[OCRDocumentType.KAUFVERTRAG] == DBDocumentType.PURCHASE_CONTRACT
        assert OCR_TO_DB_TYPE_MAP[OCRDocumentType.MIETVERTRAG] == DBDocumentType.RENTAL_CONTRACT
        assert OCR_TO_DB_TYPE_MAP[OCRDocumentType.E1_FORM] == DBDocumentType.E1_FORM
        assert OCR_TO_DB_TYPE_MAP[OCRDocumentType.UNKNOWN] == DBDocumentType.OTHER


# ---------------------------------------------------------------------------
# Auto-fix validation tests
# ---------------------------------------------------------------------------

class TestAutoFixValidation:
    """Test that validation auto-corrects instead of just flagging."""

    def _make_orchestrator(self):
        o = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        o.db = MagicMock()
        return o

    def test_negative_amount_auto_corrected(self):
        """Negative amount → auto-corrected to absolute value."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {"amount": -50.0, "date": "2025-03-15"}
        validation = orchestrator._stage_validate(DBDocumentType.RECEIPT, data, result)

        # Should auto-correct, not error
        assert "amount" in validation.corrected_fields
        assert validation.corrected_fields["amount"] == 50.0
        # Should be info, not warning/error
        amount_issues = [i for i in validation.issues if i.field == "amount"]
        assert all(i.severity == "info" for i in amount_issues)

    def test_unparseable_date_auto_set_to_today(self):
        """Unparseable date → auto-set to today."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {"amount": 100, "date": "not-a-date"}
        validation = orchestrator._stage_validate(DBDocumentType.INVOICE, data, result)

        assert "date" in validation.corrected_fields
        assert validation.corrected_fields["date"] == date.today().isoformat()

    def test_missing_date_auto_filled(self):
        """No date at all → auto-set to today."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {"amount": 100, "merchant": "Test"}
        validation = orchestrator._stage_validate(DBDocumentType.INVOICE, data, result)

        assert "date" in validation.corrected_fields
        assert validation.corrected_fields["date"] == date.today().isoformat()

    def test_missing_merchant_auto_filled(self):
        """Receipt without merchant → auto-set to 'Unbekannt'."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {"amount": 42.50, "date": "2025-03-15"}
        validation = orchestrator._stage_validate(DBDocumentType.RECEIPT, data, result)

        assert validation.corrected_fields.get("merchant") == "Unbekannt"

    def test_missing_vat_rate_defaults_to_20(self):
        """Invoice without VAT rate → auto-set to 20% (Austrian standard)."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {"amount": 120.0, "merchant": "Test", "date": "2025-03-15"}
        validation = orchestrator._stage_validate(DBDocumentType.INVOICE, data, result)

        assert validation.corrected_fields.get("vat_rate") == 20
        # VAT amount should also be calculated
        assert "vat_amount" in validation.corrected_fields

    def test_vat_mismatch_auto_corrected(self):
        """VAT amount doesn't match rate → auto-corrected to calculated value."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {
            "amount": 120.0,
            "vat_amount": 50.0,  # Wrong — should be 20
            "vat_rate": 20,
            "merchant": "Test",
            "date": "2025-03-15",
        }
        validation = orchestrator._stage_validate(DBDocumentType.INVOICE, data, result)

        # Should auto-correct VAT amount
        assert "vat_amount" in validation.corrected_fields
        assert abs(validation.corrected_fields["vat_amount"] - 20.0) < 0.01

    def test_kaufvertrag_auto_fills_building_land_split(self):
        """Kaufvertrag without building/land values → auto-set 70/30 split."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {
            "purchase_price": 300000,
            "property_address": "Wien 1010",
            "date": "2025-01-15",
        }
        validation = orchestrator._stage_validate(DBDocumentType.PURCHASE_CONTRACT, data, result)

        assert validation.corrected_fields.get("building_value") == 210000.0
        assert validation.corrected_fields.get("land_value") == 90000.0

    def test_kaufvertrag_auto_calculates_grest(self):
        """Kaufvertrag without GrESt → auto-calculate 3.5%."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {
            "purchase_price": 200000,
            "property_address": "Wien",
            "date": "2025-01-15",
        }
        validation = orchestrator._stage_validate(DBDocumentType.PURCHASE_CONTRACT, data, result)

        assert validation.corrected_fields.get("grunderwerbsteuer") == 7000.0

    def test_kaufvertrag_auto_fills_missing_address(self):
        """Kaufvertrag without address → placeholder."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {"purchase_price": 300000, "date": "2025-01-15"}
        validation = orchestrator._stage_validate(DBDocumentType.PURCHASE_CONTRACT, data, result)

        assert "property_address" in validation.corrected_fields

    def test_mietvertrag_auto_fills_missing_address(self):
        """Mietvertrag without address → placeholder."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {"monthly_rent": 800, "date": "2025-01-15"}
        validation = orchestrator._stage_validate(DBDocumentType.RENTAL_CONTRACT, data, result)

        assert "property_address" in validation.corrected_fields

    def test_receipt_auto_calculates_total_from_line_items(self):
        """Receipt without total but with line items → auto-calculate."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {
            "merchant": "BILLA",
            "date": "2025-03-15",
            "line_items": [
                {"name": "Milk", "amount": 1.50},
                {"name": "Bread", "amount": 2.30},
            ],
        }
        validation = orchestrator._stage_validate(DBDocumentType.RECEIPT, data, result)

        assert validation.corrected_fields.get("amount") == 3.80
        assert validation.is_valid  # Not an error anymore

    def test_receipt_no_amount_no_items_is_error(self):
        """Receipt with no amount AND no line items → genuine error."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {"merchant": "BILLA", "date": "2025-03-15"}
        validation = orchestrator._stage_validate(DBDocumentType.RECEIPT, data, result)

        assert not validation.is_valid
        assert validation.error_count > 0

    def test_kaufvertrag_missing_price_still_error(self):
        """Kaufvertrag without purchase_price is still a genuine error."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {"property_address": "Wien 1010"}
        validation = orchestrator._stage_validate(DBDocumentType.PURCHASE_CONTRACT, data, result)
        assert not validation.is_valid

    def test_mietvertrag_missing_rent_still_error(self):
        """Mietvertrag without monthly_rent is still a genuine error."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {"property_address": "Wien 1010"}
        validation = orchestrator._stage_validate(DBDocumentType.RENTAL_CONTRACT, data, result)
        assert not validation.is_valid

    def test_empty_data_is_error(self):
        """No extracted data → validation error."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        validation = orchestrator._stage_validate(DBDocumentType.RECEIPT, {}, result)
        assert not validation.is_valid
        assert validation.error_count == 1

    def test_valid_invoice_passes(self):
        """Invoice with all correct fields passes cleanly."""
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

    def test_future_date_is_info_not_warning(self):
        """Future dates are informational — don't block auto-creation."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {"amount": 100, "date": "2099-12-31"}
        validation = orchestrator._stage_validate(DBDocumentType.RECEIPT, data, result)

        date_issues = [i for i in validation.issues if i.field == "date"]
        assert all(i.severity == "info" for i in date_issues)
        assert validation.is_valid  # Future date doesn't block

    def test_low_rent_is_info_not_warning(self):
        """Unusual rent is informational — don't block auto-creation."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {"monthly_rent": 50, "property_address": "Wien"}
        validation = orchestrator._stage_validate(DBDocumentType.RENTAL_CONTRACT, data, result)

        rent_issues = [i for i in validation.issues if i.field == "monthly_rent"]
        assert any("low" in i.issue for i in rent_issues)
        assert all(i.severity == "info" for i in rent_issues)


# ---------------------------------------------------------------------------
# Confidence assessment tests (updated thresholds)
# ---------------------------------------------------------------------------

class TestConfidenceAssessment:
    """Test lenient confidence assessment."""

    def _make_orchestrator(self):
        o = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        o.db = MagicMock()
        return o

    def test_high_confidence(self):
        """Score >= 0.6 → HIGH (lenient threshold)."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        validation = ValidationResult(is_valid=True)

        level = orchestrator._assess_confidence(0.7, DBDocumentType.INVOICE, validation)
        assert level == ConfidenceLevel.HIGH

    def test_medium_confidence(self):
        """Score 0.3-0.6 → MEDIUM."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        validation = ValidationResult(is_valid=True)

        level = orchestrator._assess_confidence(0.4, DBDocumentType.INVOICE, validation)
        assert level == ConfidenceLevel.MEDIUM

    def test_low_confidence(self):
        """Score < 0.3 → LOW."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        validation = ValidationResult(is_valid=True)

        level = orchestrator._assess_confidence(0.2, DBDocumentType.INVOICE, validation)
        assert level == ConfidenceLevel.LOW

    def test_errors_reduce_confidence(self):
        """Validation errors push confidence down."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        validation = ValidationResult(
            is_valid=False,
            issues=[ValidationIssue(field="amount", issue="invalid", severity="error")],
        )

        # 0.7 * 0.4 = 0.28 → LOW
        level = orchestrator._assess_confidence(0.7, DBDocumentType.INVOICE, validation)
        assert level == ConfidenceLevel.LOW

    def test_warnings_dont_affect_confidence(self):
        """Warnings should NOT reduce confidence (auto-fix handles them)."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        validation = ValidationResult(
            is_valid=True,
            issues=[
                ValidationIssue(field=f"f{i}", issue="warn", severity="warning")
                for i in range(5)
            ],
        )

        level = orchestrator._assess_confidence(0.85, DBDocumentType.INVOICE, validation)
        # Warnings don't penalize anymore → still HIGH
        assert level == ConfidenceLevel.HIGH

    def test_info_issues_dont_affect_confidence(self):
        """Info issues (auto-corrections) should not affect confidence."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        validation = ValidationResult(
            is_valid=True,
            issues=[
                ValidationIssue(field="amount", issue="auto-corrected", severity="info"),
                ValidationIssue(field="date", issue="auto-set", severity="info"),
            ],
        )

        level = orchestrator._assess_confidence(0.7, DBDocumentType.INVOICE, validation)
        assert level == ConfidenceLevel.HIGH


# ---------------------------------------------------------------------------
# Auto-create philosophy tests
# ---------------------------------------------------------------------------

class TestAutoCreatePhilosophy:
    """Test that NOTHING requires user confirmation anymore."""

    def test_nothing_requires_confirmation(self):
        """CONFIRMATION_REQUIRED_TYPES should be empty."""
        assert len(CONFIRMATION_REQUIRED_TYPES) == 0

    def test_receipt_no_confirmation(self):
        from app.models.document import DocumentType as DBDocumentType
        assert DBDocumentType.RECEIPT not in CONFIRMATION_REQUIRED_TYPES

    def test_kaufvertrag_no_confirmation(self):
        from app.models.document import DocumentType as DBDocumentType
        assert DBDocumentType.PURCHASE_CONTRACT not in CONFIRMATION_REQUIRED_TYPES

    def test_mietvertrag_no_confirmation(self):
        from app.models.document import DocumentType as DBDocumentType
        assert DBDocumentType.RENTAL_CONTRACT not in CONFIRMATION_REQUIRED_TYPES


# ---------------------------------------------------------------------------
# User message tests
# ---------------------------------------------------------------------------

class TestUserMessage:
    """Test user-friendly notification messages."""

    def test_error_message(self):
        result = PipelineResult(document_id=1, error="something broke")
        assert "nicht verarbeitet" in result.user_message

    def test_auto_created_transaction_message(self):
        result = PipelineResult(
            document_id=1,
            suggestions=[{
                "status": "auto-created",
                "transaction_id": 42,
                "amount": "120.00",
                "description": "Test GmbH",
                "is_deductible": True,
            }],
        )
        msg = result.user_message
        assert "Automatisch erstellt" in msg
        assert "120.00" in msg
        assert "absetzbar" in msg

    def test_auto_created_property_message(self):
        result = PipelineResult(
            document_id=1,
            suggestions=[{
                "type": "create_property",
                "status": "auto-created",
            }],
        )
        assert "Immobilie angelegt" in result.user_message

    def test_auto_created_recurring_message(self):
        result = PipelineResult(
            document_id=1,
            suggestions=[{
                "type": "create_recurring_income",
                "status": "auto-created",
            }],
        )
        assert "Mieteinnahme angelegt" in result.user_message

    def test_no_suggestions_message(self):
        result = PipelineResult(document_id=1, needs_review=False)
        assert "verarbeitet" in result.user_message


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
        assert "user_message" in d

    def test_with_classification(self):
        result = PipelineResult(
            document_id=1,
            classification=ClassificationResult(
                document_type="invoice", confidence=0.9, method="regex",
            ),
        )
        d = result.to_dict()
        assert d["classification"]["document_type"] == "invoice"

    def test_with_validation(self):
        result = PipelineResult(
            document_id=1,
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


# ---------------------------------------------------------------------------
# End-to-end pipeline tests (mocked dependencies)
# ---------------------------------------------------------------------------

class TestPipelineEndToEnd:
    """Integration tests for the auto pipeline."""

    @patch("app.services.storage_service.StorageService")
    def test_full_pipeline_invoice(self, mock_storage_class):
        """Invoice → auto-classify, auto-validate, auto-create."""
        from app.models.document import DocumentType as DBDocumentType

        db = MagicMock()
        document = _make_document(file_name="rechnung_2025.pdf")
        document.document_type = DBDocumentType.OTHER
        db.query.return_value.filter.return_value.first.return_value = document

        mock_storage = MagicMock()
        mock_storage.download_file.return_value = b"fake pdf bytes"
        mock_storage_class.return_value = mock_storage

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
        # Should NOT need review for a good invoice
        assert result.needs_review is False

    @patch("app.services.storage_service.StorageService")
    def test_kaufvertrag_auto_creates(self, mock_storage_class):
        """Kaufvertrag → auto-creates property (no confirmation needed)."""
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
            with patch.object(orchestrator, "_build_kaufvertrag_suggestion") as mock_suggest:
                mock_suggest.return_value = {
                    "type": "create_property",
                    "status": "auto-created",
                    "property_id": "abc-123",
                    "data": {"purchase_price": 300000},
                }
                result = orchestrator.process_document(1)

        # Should NOT need review — auto-created
        assert result.needs_review is False
        if result.suggestions:
            assert result.suggestions[0]["status"] == "auto-created"

    @patch("app.services.storage_service.StorageService")
    def test_document_not_found(self, mock_storage_class):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        orchestrator = DocumentPipelineOrchestrator(db)
        result = orchestrator.process_document(999)
        assert result.error is not None
        assert "not found" in result.error

    @patch("app.services.storage_service.StorageService")
    def test_storage_download_failure(self, mock_storage_class):
        db = MagicMock()
        document = _make_document()
        db.query.return_value.filter.return_value.first.return_value = document

        mock_storage = MagicMock()
        mock_storage.download_file.side_effect = Exception("S3 connection timeout")
        mock_storage_class.return_value = mock_storage

        orchestrator = DocumentPipelineOrchestrator(db)
        result = orchestrator.process_document(1)
        assert result.error is not None

    @patch("app.services.storage_service.StorageService")
    def test_very_low_confidence_with_error_needs_review(self, mock_storage_class):
        """Only LOW confidence + errors → needs_review=True."""
        from app.models.document import DocumentType as DBDocumentType

        db = MagicMock()
        document = _make_document(file_name="blurry_scan.jpg")
        document.document_type = DBDocumentType.OTHER
        db.query.return_value.filter.return_value.first.return_value = document

        mock_storage = MagicMock()
        mock_storage.download_file.return_value = b"fake"
        mock_storage_class.return_value = mock_storage

        # Very low confidence AND no amount → genuine error
        ocr_result = _make_ocr_result(
            doc_type=OCRDocumentType.RECEIPT,
            confidence=0.15,
            extracted_data={"merchant": "?"},
        )

        with patch.object(OCREngine, "process_document", return_value=ocr_result):
            orchestrator = DocumentPipelineOrchestrator(db)
            result = orchestrator.process_document(1)

        # 0.15 * 0.4 (error penalty) = 0.06 → LOW, and has errors
        assert result.needs_review is True

    @patch("app.services.storage_service.StorageService")
    def test_low_confidence_but_valid_data_no_review(self, mock_storage_class):
        """Low OCR confidence but valid data → still auto-create, no review needed."""
        from app.models.document import DocumentType as DBDocumentType

        db = MagicMock()
        document = _make_document(file_name="scan.jpg")
        document.document_type = DBDocumentType.OTHER
        db.query.return_value.filter.return_value.first.return_value = document

        mock_storage = MagicMock()
        mock_storage.download_file.return_value = b"fake"
        mock_storage_class.return_value = mock_storage

        ocr_result = _make_ocr_result(
            doc_type=OCRDocumentType.INVOICE,
            confidence=0.45,  # Below old threshold, but data is valid
            extracted_data={"amount": 100, "merchant": "Test", "date": "2025-03-15"},
        )

        with patch.object(OCREngine, "process_document", return_value=ocr_result):
            orchestrator = DocumentPipelineOrchestrator(db)
            result = orchestrator.process_document(1)

        # No errors → no review needed even with low confidence
        assert result.needs_review is False


# ---------------------------------------------------------------------------
# ValidationResult property tests
# ---------------------------------------------------------------------------

class TestValidationResultProperties:

    def test_error_count(self):
        v = ValidationResult(
            is_valid=False,
            issues=[
                ValidationIssue(field="a", issue="bad", severity="error"),
                ValidationIssue(field="b", issue="info", severity="info"),
                ValidationIssue(field="c", issue="bad2", severity="error"),
            ],
        )
        assert v.error_count == 2
        assert v.warning_count == 0

    def test_empty_validation(self):
        v = ValidationResult(is_valid=True)
        assert v.error_count == 0
        assert v.warning_count == 0
