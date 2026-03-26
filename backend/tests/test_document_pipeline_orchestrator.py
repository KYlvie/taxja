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
from app.models.document import DocumentType as DBDocumentType
from app.services.document_classifier import DocumentType as OCRDocumentType
from app.services.ocr_engine import OCREngine, OCRResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_orchestrator_llm_cache():
    cache = getattr(DocumentPipelineOrchestrator, "_llm_classification_cache", None)
    if cache is not None:
        cache.clear()
    yield
    cache = getattr(DocumentPipelineOrchestrator, "_llm_classification_cache", None)
    if cache is not None:
        cache.clear()

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


@patch("sqlalchemy.orm.attributes.flag_modified")
def test_bank_statement_import_suggestion_persists_direction_metadata_without_polluting_payload(
    _mock_flag_modified,
):
    orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
    orchestrator.db = MagicMock()
    document = _make_document(
        file_name="kontoauszug.pdf",
        doc_type=DBDocumentType.BANK_STATEMENT,
        ocr_result={
            "bank_name": "Bank Austria",
            "iban": "AT421200051588776655",
            "_seed_eval": {"sample_key": "bank-statement"},
        },
    )
    result = PipelineResult(document_id=1, raw_text="Kontoauszug Soll Haben")

    with patch.object(
        orchestrator,
        "_build_bank_statement_direction_metadata",
        return_value={
            "document_transaction_direction": "unknown",
            "document_transaction_direction_source": "statement_mixed_flow",
            "document_transaction_direction_confidence": 0.2,
            "transaction_direction_resolution": {
                "candidate": "unknown",
                "gate_enabled": False,
            },
            "commercial_document_semantics": "unknown",
            "is_reversal": False,
        },
    ):
        suggestion = orchestrator._build_bank_statement_import_suggestion(document, result)

    assert suggestion is not None
    assert suggestion["type"] == "import_bank_statement"
    assert suggestion["data"]["bank_name"] == "Bank Austria"
    assert "document_transaction_direction" not in suggestion["data"]
    assert document.ocr_result["document_transaction_direction"] == "unknown"
    assert document.ocr_result["transaction_direction_resolution"]["gate_enabled"] is False


def test_finalize_keeps_bank_statement_import_out_of_transaction_tax_analysis():
    orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
    orchestrator.db = MagicMock()

    document = _make_document(
        file_name="kontoauszug.pdf",
        doc_type=DBDocumentType.BANK_STATEMENT,
        ocr_result={
            "transaction_suggestion": {"type": "create_transaction"},
            "tax_analysis": {"items": [{"description": "stale"}]},
        },
    )
    result = PipelineResult(
        document_id=1,
        stage_reached=PipelineStage.SUGGEST,
        classification=ClassificationResult(
            document_type="bank_statement",
            confidence=0.82,
            method="regex",
        ),
        extracted_data={"transactions": [{"date": "2025-01-01", "amount": "-12.50"}]},
        raw_text="Kontoauszug Soll Haben",
        confidence_level=ConfidenceLevel.MEDIUM,
        suggestions=[
            {
                "type": "import_bank_statement",
                "status": "pending",
                "data": {
                    "transactions": [
                        {"date": "2025-01-01", "amount": "-12.50", "counterparty": "Utility"}
                    ]
                },
            }
        ],
        current_state="completed",
        needs_review=False,
    )

    orchestrator._finalize(
        result=result,
        document=document,
        start_time=datetime.utcnow(),
    )

    assert document.ocr_result["import_suggestion"]["type"] == "import_bank_statement"
    assert "transaction_suggestion" not in document.ocr_result
    assert "tax_analysis" not in document.ocr_result


def test_finalize_materializes_document_year_fields_for_bank_statement():
    orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
    orchestrator.db = MagicMock()

    document = _make_document(
        file_name="kontoauszug.pdf",
        doc_type=DBDocumentType.BANK_STATEMENT,
        ocr_result={},
    )

    result = PipelineResult(
        document_id=1,
        stage_reached=PipelineStage.SUGGEST,
        classification=ClassificationResult(
            document_type="bank_statement",
            confidence=0.93,
            method="regex",
        ),
        extracted_data={
            "statement_period": {
                "start": "2024-06-26",
                "end": "2024-12-19",
            },
            "transactions": [
                {"date": "2024-06-26", "amount": "-33.00"},
                {"date": "2024-12-19", "amount": "-62.23"},
            ],
        },
        raw_text="Kontoauszug",
        current_state="completed",
        needs_review=False,
    )

    orchestrator._finalize(
        result=result,
        document=document,
        start_time=datetime.utcnow(),
    )

    assert document.document_date == date(2024, 6, 26)
    assert document.document_year == 2024
    assert document.year_basis == "statement_period_start"
    assert float(document.year_confidence) == 1.0
    assert document.ocr_result["document_year"] == 2024
    assert document.ocr_result["year_basis"] == "statement_period_start"


def test_finalize_materializes_document_year_fields_for_tax_year_documents():
    orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
    orchestrator.db = MagicMock()

    document = _make_document(
        file_name="bescheid.pdf",
        doc_type=DBDocumentType.EINKOMMENSTEUERBESCHEID,
        ocr_result={},
    )

    result = PipelineResult(
        document_id=1,
        stage_reached=PipelineStage.SUGGEST,
        classification=ClassificationResult(
            document_type="einkommensteuerbescheid",
            confidence=0.98,
            method="regex",
        ),
        extracted_data={
            "tax_year": 2024,
            "assessment_amount": 123.45,
        },
        raw_text="Einkommensteuerbescheid 2024",
        current_state="completed",
        needs_review=False,
    )

    orchestrator._finalize(
        result=result,
        document=document,
        start_time=datetime.utcnow(),
    )

    assert document.document_date is None
    assert document.document_year == 2024
    assert document.year_basis == "tax_year"


def test_finalize_persists_full_transaction_suggestion_metadata_in_tax_analysis():
    orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
    orchestrator.db = MagicMock()

    document = _make_document(
        file_name="split-receipt.pdf",
        doc_type=DBDocumentType.RECEIPT,
        ocr_result={},
    )

    result = PipelineResult(
        document_id=1,
        stage_reached=PipelineStage.SUGGEST,
        classification=ClassificationResult(
            document_type="receipt",
            confidence=0.83,
            method="regex",
        ),
        extracted_data={"merchant": "BILLA", "amount": 11.50, "date": "2025-01-15"},
        raw_text="BILLA split receipt",
        current_state="completed",
        needs_review=True,
        suggestions=[
            {
                "amount": "8.50",
                "date": "2025-01-15",
                "description": "BILLA groceries",
                "status": "pending-review",
                "needs_review": True,
                "reviewed": False,
                "gate_decision": "pending_review",
                "confidence": 0.81,
            },
            {
                "amount": "3.00",
                "date": "2025-01-15",
                "description": "BILLA bakery",
                "status": "manual-review-required",
                "needs_review": True,
                "reviewed": False,
                "gate_decision": "manual_required",
                "confidence": 0.42,
            },
        ],
    )

    orchestrator._finalize(
        result=result,
        document=document,
        start_time=datetime.utcnow(),
    )

    items = document.ocr_result["tax_analysis"]["items"]
    assert len(items) == 2
    assert items[0]["status"] == "pending-review"
    assert items[0]["needs_review"] is True
    assert items[0]["reviewed"] is False
    assert items[0]["gate_decision"] == "pending_review"
    assert items[1]["status"] == "manual-review-required"
    assert items[1]["gate_decision"] == "manual_required"


# ---------------------------------------------------------------------------
# Classification tests (unchanged — still valid)
# ---------------------------------------------------------------------------

@patch("app.services.storage_service.StorageService")
def test_stage_ocr_passes_document_provider_override_to_engine(mock_storage_class):
    mock_storage = mock_storage_class.return_value
    mock_storage.download_file.return_value = b"fake-image"

    orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
    orchestrator.db = MagicMock()
    orchestrator.ocr_engine = MagicMock()
    orchestrator._log_audit = MagicMock()

    expected_result = _make_ocr_result()
    orchestrator.ocr_engine.process_document.return_value = expected_result

    document = _make_document(
        ocr_result={"_pipeline": {"ocr_provider_override": "anthropic"}}
    )
    result = PipelineResult(document_id=1)

    actual = orchestrator._stage_ocr(document, result)

    assert actual is expected_result
    orchestrator.ocr_engine.process_document.assert_called_once_with(
        b"fake-image",
        mime_type=document.mime_type,
        vision_provider_preference="anthropic",
        reprocess_mode=None,
        document_type_hint=document.document_type,
    )


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

    def test_filename_loan_variants(self):
        orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        orchestrator.db = MagicMock()
        from app.models.document import DocumentType as DBDocumentType

        for fname in [
            "kreditvertrag.pdf",
            "B04_Kredit_Zinsbescheinigung.pdf",
            "wohnbaukredit_2024.pdf",
            "darlehen_erste_bank.pdf",
        ]:
            result = orchestrator._classify_by_filename(fname)
            assert result == DBDocumentType.LOAN_CONTRACT, f"Failed for {fname}"

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
            raw_text=(
                "BILLA Supermarkt Wien Filiale 123 Einkaufsbeleg "
                "Summe EUR 42.50 MwSt 3.86 Kartenzahlung Danke fuer Ihren Einkauf"
            )
        )
        result = PipelineResult(document_id=1)

        db_type = orchestrator._stage_classify(document, ocr_result, result)
        assert db_type == DBDocumentType.RECEIPT
        assert result.classification.method == "llm"
        mock_llm.assert_called_once()

    @patch("app.services.document_pipeline_orchestrator.DocumentPipelineOrchestrator._try_llm_classification")
    def test_receipt_like_docs_skip_llm_when_confidence_is_good_enough(self, mock_llm):
        db = MagicMock()
        orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        orchestrator.db = db

        document = _make_document(file_name="scan.pdf")
        ocr_result = _make_ocr_result(
            doc_type=OCRDocumentType.INVOICE,
            confidence=0.70,
            raw_text=(
                "RECHNUNG Nr 2026-001 Lieferant Muster GmbH Summe EUR 42.50 "
                "UID ATU12345678 Zahlungsziel 31.03.2026 Danke fuer Ihren Einkauf"
            ),
        )
        result = PipelineResult(document_id=1)

        db_type = orchestrator._stage_classify(document, ocr_result, result)

        assert db_type == DBDocumentType.INVOICE
        assert result.classification.method == "regex"
        mock_llm.assert_not_called()

    @patch("app.services.document_pipeline_orchestrator.DocumentPipelineOrchestrator._try_llm_classification")
    def test_route_sensitive_docs_keep_llm_arbitration_when_confidence_is_low(self, mock_llm):
        from app.models.document import DocumentType as DBDocumentType

        mock_llm.return_value = DBDocumentType.PURCHASE_CONTRACT

        db = MagicMock()
        orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        orchestrator.db = db

        document = _make_document(file_name="scan.pdf")
        ocr_result = _make_ocr_result(
            doc_type=OCRDocumentType.KAUFVERTRAG,
            confidence=0.70,
            raw_text=(
                "Kaufvertrag ueber eine Eigentumswohnung in Wien. Kaufpreis EUR 350000. "
                "Kaeufer Max Mustermann, Verkaeufer Erika Beispiel, Grundbuchseinlage 123."
            ),
        )
        result = PipelineResult(document_id=1)

        db_type = orchestrator._stage_classify(document, ocr_result, result)

        assert db_type == DBDocumentType.PURCHASE_CONTRACT
        assert result.classification.method == "regex+llm"
        mock_llm.assert_called_once()

    def test_keyword_override_when_loan_terms_present(self):
        """Loan-specific OCR text should promote OTHER to LOAN_CONTRACT."""
        db = MagicMock()
        orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        orchestrator.db = db

        document = _make_document(file_name="scan_loan.pdf")
        ocr_result = _make_ocr_result(
            doc_type=OCRDocumentType.UNKNOWN,
            confidence=0.21,
            raw_text=(
                "Erste Bank Kreditkonto 515-112233 Kreditnehmer: Mag. Thomas Gruber "
                "Wohnbaukredit ETW Thenneberg Zinsaufwand 2024 EUR 3.840,00 "
                "Tilgung 2024 EUR 4.392,00"
            ),
        )
        result = PipelineResult(document_id=1)

        from app.models.document import DocumentType as DBDocumentType
        db_type = orchestrator._stage_classify(document, ocr_result, result)

        assert db_type == DBDocumentType.LOAN_CONTRACT
        assert result.classification.method == "keyword"
        assert result.classification.confidence >= 0.62

    def test_ocr_type_mapping(self):
        from app.models.document import DocumentType as DBDocumentType
        assert OCR_TO_DB_TYPE_MAP[OCRDocumentType.KAUFVERTRAG] == DBDocumentType.PURCHASE_CONTRACT
        assert OCR_TO_DB_TYPE_MAP[OCRDocumentType.MIETVERTRAG] == DBDocumentType.RENTAL_CONTRACT
        assert OCR_TO_DB_TYPE_MAP[OCRDocumentType.E1_FORM] == DBDocumentType.E1_FORM
        assert OCR_TO_DB_TYPE_MAP[OCRDocumentType.UNKNOWN] == DBDocumentType.OTHER


@patch("app.services.llm_extractor.get_llm_extractor")
def test_try_llm_classification_uses_versioned_memory_cache(mock_get_llm_extractor):
    orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
    orchestrator.db = MagicMock()

    extractor = MagicMock()
    extractor.is_available = True
    extractor.classify_document.return_value = "invoice"
    extractor.llm = MagicMock()
    extractor.llm.model = "gpt-4o-mini"
    extractor.llm.anthropic_model = "claude-opus"
    extractor.llm.groq_model = "llama-3.3"
    extractor.llm.gpt_oss_model = "gpt-oss-120b"
    mock_get_llm_extractor.return_value = extractor

    first = orchestrator._try_llm_classification("BILLA   SUMME EUR 23,45")
    second = orchestrator._try_llm_classification("billa summe eur 23,45")

    assert first == DBDocumentType.INVOICE
    assert second == DBDocumentType.INVOICE
    assert extractor.classify_document.call_count == 1


def test_llm_cache_key_changes_when_provider_fingerprint_changes():
    orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
    orchestrator.db = MagicMock()

    extractor_a = MagicMock()
    extractor_a.llm = MagicMock()
    extractor_a.llm.model = "gpt-4o-mini"
    extractor_a.llm.anthropic_model = "claude-opus"
    extractor_a.llm.groq_model = None
    extractor_a.llm.gpt_oss_model = None

    extractor_b = MagicMock()
    extractor_b.llm = MagicMock()
    extractor_b.llm.model = "gpt-4.1-mini"
    extractor_b.llm.anthropic_model = "claude-opus"
    extractor_b.llm.groq_model = None
    extractor_b.llm.gpt_oss_model = None

    key_a = orchestrator._build_llm_classification_cache_key(
        "BILLA SUMME EUR 23,45", extractor_a
    )
    key_b = orchestrator._build_llm_classification_cache_key(
        "BILLA SUMME EUR 23,45", extractor_b
    )

    assert key_a != key_b


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

    def test_european_amount_is_normalized_during_validation(self):
        """European decimal commas should be normalized instead of rejected."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {"amount": "96,00", "merchant": "Notion", "date": "2024-01-02"}
        validation = orchestrator._stage_validate(DBDocumentType.INVOICE, data, result)

        assert not any("Invalid amount value" in issue.issue for issue in validation.issues)
        assert validation.corrected_fields.get("amount") == 96.0

    def test_named_month_date_is_normalized_during_validation(self):
        """Named-month European dates should be normalized to ISO."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {"amount": 42.5, "merchant": "Test", "date": "19. Dez. 2024"}
        validation = orchestrator._stage_validate(DBDocumentType.INVOICE, data, result)

        assert validation.corrected_fields.get("date") == "2024-12-19"

    def test_percent_vat_rate_is_normalized(self):
        """VAT rates like '20 %' should be normalized before VAT calculation."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {
            "amount": "120,00",
            "vat_rate": "20 %",
            "merchant": "Test",
            "date": "2024-01-02",
        }
        validation = orchestrator._stage_validate(DBDocumentType.INVOICE, data, result)

        assert validation.corrected_fields.get("vat_rate") == 20.0
        assert validation.corrected_fields.get("vat_amount") == 20.0

    def test_reverse_charge_invoice_skips_austrian_vat_fallback(self):
        """Reverse-charge invoices must not be backfilled with Austrian 20% VAT."""
        from app.models.document import DocumentType as DBDocumentType
        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {
            "amount": 96.0,
            "merchant": "Notion Labs Inc.",
            "date": "2024-01-02",
            "description": "Reverse Charge — Steuerschuldnerschaft des Leistungsempfängers",
            "raw_text": "Rechnungsbetrag: EUR 96,00 Reverse Charge - Steuerschuldnerschaft des Leistungsempfängers",
        }
        validation = orchestrator._stage_validate(DBDocumentType.INVOICE, data, result)

        assert "vat_rate" not in validation.corrected_fields
        assert "vat_amount" not in validation.corrected_fields
        assert any("reverse-charge indicators detected" in issue.issue for issue in validation.issues)

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

    def test_asset_kaufvertrag_does_not_autofill_property_fields(self):
        """Asset-oriented purchase contracts must not get property placeholders."""
        from app.models.document import DocumentType as DBDocumentType

        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {
            "purchase_contract_kind": "asset",
            "purchase_price": 13800,
            "asset_type": "vehicle",
        }
        validation = orchestrator._stage_validate(DBDocumentType.PURCHASE_CONTRACT, data, result)

        assert validation.is_valid
        assert "property_address" not in validation.corrected_fields
        assert "building_value" not in validation.corrected_fields
        assert "land_value" not in validation.corrected_fields

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


# ---------------------------------------------------------------------------
# Kreditvertrag validation and suggestion tests
# ---------------------------------------------------------------------------

class TestKreditvertragValidation:
    """Tests for Kreditvertrag (loan contract) validation and suggestion building."""

    def _make_orchestrator(self):
        o = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        o.db = MagicMock()
        return o

    def test_kreditvertrag_missing_loan_amount_is_error(self):
        """Kreditvertrag without loan_amount is a genuine error."""
        from app.models.document import DocumentType as DBDocumentType

        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {"interest_rate": 3.5}
        validation = orchestrator._stage_validate(DBDocumentType.LOAN_CONTRACT, data, result)
        assert not validation.is_valid
        assert any(i.field == "loan_amount" and i.severity == "error" for i in validation.issues)

    def test_kreditvertrag_missing_interest_rate_is_error(self):
        """Kreditvertrag without interest_rate is a genuine error."""
        from app.models.document import DocumentType as DBDocumentType

        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {"loan_amount": 200000}
        validation = orchestrator._stage_validate(DBDocumentType.LOAN_CONTRACT, data, result)
        assert not validation.is_valid
        assert any(
            i.field == "interest_rate" and i.severity == "error" for i in validation.issues
        )

    def test_kreditvertrag_missing_both_fields_is_error(self):
        """Kreditvertrag without both loan_amount and interest_rate has two errors."""
        from app.models.document import DocumentType as DBDocumentType

        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {"lender_name": "Bank Austria"}
        validation = orchestrator._stage_validate(DBDocumentType.LOAN_CONTRACT, data, result)
        assert not validation.is_valid
        error_fields = [i.field for i in validation.issues if i.severity == "error"]
        assert "loan_amount" in error_fields
        assert "interest_rate" in error_fields

    def test_kreditvertrag_valid_passes(self):
        """Kreditvertrag with both loan_amount and interest_rate is valid."""
        from app.models.document import DocumentType as DBDocumentType

        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {"loan_amount": 200000, "interest_rate": 3.5, "monthly_payment": 950}
        validation = orchestrator._stage_validate(DBDocumentType.LOAN_CONTRACT, data, result)
        assert validation.is_valid

    def test_kreditvertrag_low_amount_is_info(self):
        """Unusually low loan amount is informational — don't block."""
        from app.models.document import DocumentType as DBDocumentType

        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {"loan_amount": 500, "interest_rate": 3.5}
        validation = orchestrator._stage_validate(DBDocumentType.LOAN_CONTRACT, data, result)
        amount_issues = [i for i in validation.issues if i.field == "loan_amount"]
        assert any("low" in i.issue for i in amount_issues)
        assert all(i.severity == "info" for i in amount_issues)

    def test_kreditvertrag_high_rate_is_info(self):
        """Unusually high interest rate is informational — don't block."""
        from app.models.document import DocumentType as DBDocumentType

        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {"loan_amount": 200000, "interest_rate": 25}
        validation = orchestrator._stage_validate(DBDocumentType.LOAN_CONTRACT, data, result)
        rate_issues = [i for i in validation.issues if i.field == "interest_rate"]
        assert any("high" in i.issue for i in rate_issues)
        assert all(i.severity == "info" for i in rate_issues)

    def test_kreditvertrag_negative_rate_is_warning(self):
        """Negative interest rate is a warning."""
        from app.models.document import DocumentType as DBDocumentType

        orchestrator = self._make_orchestrator()
        result = PipelineResult(document_id=1)

        data = {"loan_amount": 200000, "interest_rate": -1.5}
        validation = orchestrator._stage_validate(DBDocumentType.LOAN_CONTRACT, data, result)
        rate_issues = [i for i in validation.issues if i.field == "interest_rate"]
        assert any(i.severity == "warning" for i in rate_issues)


class TestKreditvertragSuggestion:
    """Tests for _build_kreditvertrag_suggestion in ocr_tasks.py."""

    def test_builds_suggestion_with_all_fields(self):
        """Full Kreditvertrag data produces a pending create_loan suggestion."""
        from app.tasks.ocr_tasks import _build_kreditvertrag_suggestion

        db = MagicMock()
        # No existing PropertyLoan for this document
        db.query.return_value.filter.return_value.first.return_value = None
        doc = _make_document(
            file_name="kreditvertrag.pdf",
            ocr_result={
                "loan_amount": 250000,
                "interest_rate": 3.75,
                "monthly_payment": 1200,
                "lender_name": "Erste Bank",
                "start_date": "2025-01-01",
                "end_date": "2050-01-01",
            },
        )
        result = PipelineResult(document_id=1)

        out = _build_kreditvertrag_suggestion(db, doc, result)
        suggestion = out["import_suggestion"]

        assert suggestion is not None
        assert suggestion["type"] in {"create_loan", "create_loan_repayment"}
        assert suggestion["status"] == "pending"
        assert suggestion["data"]["loan_amount"] == 250000.0
        assert suggestion["data"]["interest_rate"] == 3.75
        assert suggestion["data"]["monthly_payment"] == 1200.0
        assert suggestion["data"]["lender_name"] == "Erste Bank"
        assert suggestion["data"]["start_date"] == "2025-01-01"
        assert suggestion["data"]["end_date"] == "2050-01-01"
        assert "missing_fields" not in suggestion["data"]

    def test_missing_loan_amount_sets_needs_input(self):
        """Missing loan_amount → status needs_input with missing_fields."""
        from app.tasks.ocr_tasks import _build_kreditvertrag_suggestion

        db = MagicMock()
        # No existing PropertyLoan for this document
        db.query.return_value.filter.return_value.first.return_value = None
        doc = _make_document(
            file_name="kreditvertrag.pdf",
            ocr_result={
                "interest_rate": 3.5,
                "monthly_payment": 900,
            },
        )
        result = PipelineResult(document_id=1)

        out = _build_kreditvertrag_suggestion(db, doc, result)
        suggestion = out["import_suggestion"]

        assert suggestion["status"] == "needs_input"
        assert "loan_amount" in suggestion["data"]["missing_fields"]

    def test_missing_interest_rate_sets_needs_input(self):
        """Missing interest_rate → status needs_input with missing_fields."""
        from app.tasks.ocr_tasks import _build_kreditvertrag_suggestion

        db = MagicMock()
        # No existing PropertyLoan for this document
        db.query.return_value.filter.return_value.first.return_value = None
        doc = _make_document(
            file_name="kreditvertrag.pdf",
            ocr_result={
                "loan_amount": 200000,
                "monthly_payment": 900,
            },
        )
        result = PipelineResult(document_id=1)

        out = _build_kreditvertrag_suggestion(db, doc, result)
        suggestion = out["import_suggestion"]

        assert suggestion["status"] == "needs_input"
        assert "interest_rate" in suggestion["data"]["missing_fields"]

    def test_missing_both_critical_fields(self):
        """Missing both loan_amount and interest_rate → both in missing_fields."""
        from app.tasks.ocr_tasks import _build_kreditvertrag_suggestion

        db = MagicMock()
        # No existing PropertyLoan for this document
        db.query.return_value.filter.return_value.first.return_value = None
        doc = _make_document(
            file_name="kreditvertrag.pdf",
            ocr_result={"lender_name": "Bank Austria"},
        )
        result = PipelineResult(document_id=1)

        out = _build_kreditvertrag_suggestion(db, doc, result)
        suggestion = out["import_suggestion"]

        assert suggestion["status"] == "needs_input"
        assert "loan_amount" in suggestion["data"]["missing_fields"]
        assert "interest_rate" in suggestion["data"]["missing_fields"]

    def test_property_id_from_upload_context(self):
        """Upload context property_id is resolved and included in suggestion."""
        from app.tasks.ocr_tasks import _build_kreditvertrag_suggestion
        from app.models.property import Property as PropertyModel, PropertyStatus

        mock_property = MagicMock()
        mock_property.id = 42
        mock_property.user_id = 1
        mock_property.status = PropertyStatus.ACTIVE

        db = MagicMock()
        # First .first() call = PropertyLoan check (no existing loan)
        # Second .first() call = Property lookup (found)
        db.query.return_value.filter.return_value.first.side_effect = [None, mock_property]

        doc = _make_document(
            file_name="kreditvertrag.pdf",
            ocr_result={
                "loan_amount": 200000,
                "interest_rate": 3.5,
                "_upload_context": {"property_id": 42},
            },
        )
        result = PipelineResult(document_id=1)

        out = _build_kreditvertrag_suggestion(db, doc, result)
        suggestion = out["import_suggestion"]

        assert suggestion["data"]["matched_property_id"] == "42"

    def test_no_upload_context_no_property(self):
        """Without upload context, matched_property_id is None."""
        from app.tasks.ocr_tasks import _build_kreditvertrag_suggestion

        db = MagicMock()
        # No existing PropertyLoan for this document
        db.query.return_value.filter.return_value.first.return_value = None
        doc = _make_document(
            file_name="kreditvertrag.pdf",
            ocr_result={
                "loan_amount": 200000,
                "interest_rate": 3.5,
            },
        )
        result = PipelineResult(document_id=1)

        out = _build_kreditvertrag_suggestion(db, doc, result)
        suggestion = out["import_suggestion"]

        assert suggestion["data"]["matched_property_id"] is None

    def test_property_address_fallback_matches_existing_property(self):
        """Loan suggestions should link a property by OCR address when upload context is absent."""
        from types import SimpleNamespace
        from unittest.mock import patch

        from app.tasks.ocr_tasks import _build_kreditvertrag_suggestion

        mock_property = MagicMock()
        mock_property.id = 84
        mock_property.address = "Argentinierstrasse 21, 1234 Wien"

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        doc = _make_document(
            file_name="kreditvertrag.pdf",
            user_id=1,
            ocr_result={
                "loan_amount": 200000,
                "interest_rate": 3.5,
                "property_address": "Argentinierstrasse 21, 1234 Wien",
            },
        )
        result = PipelineResult(document_id=1)

        with patch("app.services.address_matcher.AddressMatcher") as matcher_cls:
            matcher = matcher_cls.return_value
            matcher.match_address.return_value = [
                SimpleNamespace(property=mock_property, confidence=0.92)
            ]

            out = _build_kreditvertrag_suggestion(db, doc, result)

        suggestion = out["import_suggestion"]
        assert suggestion["type"] == "create_loan"
        assert suggestion["data"]["matched_property_id"] == "84"
        assert suggestion["data"]["matched_property_address"] == "Argentinierstrasse 21, 1234 Wien"
        assert suggestion["data"]["no_property_match"] is False

    def test_invalid_ocr_result_still_returns_needs_input_suggestion(self):
        """Non-dict ocr_result now degrades to a visible needs-input suggestion."""
        from app.tasks.ocr_tasks import _build_kreditvertrag_suggestion

        db = MagicMock()
        # No existing PropertyLoan for this document
        db.query.return_value.filter.return_value.first.return_value = None
        doc = _make_document(file_name="kreditvertrag.pdf", ocr_result="invalid")
        result = PipelineResult(document_id=1)

        out = _build_kreditvertrag_suggestion(db, doc, result)
        suggestion = out["import_suggestion"]
        assert suggestion is not None
        assert suggestion["status"] == "needs_input"
        assert suggestion["type"] == "create_loan_repayment"
        assert set(suggestion["data"]["missing_fields"]) == {"loan_amount", "interest_rate"}


class TestKreditvertragStageDispatch:
    """Tests that _stage_suggest dispatches LOAN_CONTRACT to the Kreditvertrag branch."""

    def test_loan_contract_dispatches_to_kreditvertrag(self):
        """LOAN_CONTRACT type triggers _build_kreditvertrag_suggestion."""
        from app.models.document import DocumentType as DBDocumentType

        orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        orchestrator.db = MagicMock()

        document = _make_document(file_name="kreditvertrag.pdf")
        ocr_result = _make_ocr_result()
        result = PipelineResult(document_id=1)

        # Mock the wrapper method on the instance
        orchestrator._build_kreditvertrag_suggestion = MagicMock(
            return_value={"type": "create_loan", "status": "pending", "data": {}}
        )

        orchestrator._stage_suggest(document, DBDocumentType.LOAN_CONTRACT, ocr_result, result)

        orchestrator._build_kreditvertrag_suggestion.assert_called_once_with(document, result)

    def test_loan_contract_ignores_transaction_match_preemption(self):
        """Loan contracts should not be hijacked by generic transaction dedup matches."""
        from app.models.document import DocumentType as DBDocumentType

        db = MagicMock()
        orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        orchestrator.db = db
        orchestrator._log_audit = MagicMock()
        orchestrator._get_processing_decision_service = MagicMock()
        orchestrator._get_processing_decision_service.return_value.build_phase_two_decision.return_value = MagicMock(
            primary_actions=["loan_contract"],
            secondary_actions=[],
            model_dump=lambda mode="json": {"primary_actions": ["loan_contract"], "secondary_actions": []},
        )

        document = _make_document(
            file_name="B04_Kredit_Zinsbescheinigung.pdf",
            ocr_result={"matched_existing": {"type": "transaction", "id": 99, "reason": "old transaction match"}},
        )
        result = PipelineResult(document_id=1)
        ocr_result = _make_ocr_result(
            doc_type=OCRDocumentType.UNKNOWN,
            confidence=0.2,
            extracted_data={"loan_amount": 250000, "interest_rate": 3.1},
        )
        orchestrator._build_kreditvertrag_suggestion = MagicMock(return_value={"type": "create_loan"})

        orchestrator._stage_suggest(document, DBDocumentType.LOAN_CONTRACT, ocr_result, result)

        orchestrator._build_kreditvertrag_suggestion.assert_called_once_with(document, result)
        assert not any(s.get("type") == "link_to_existing" for s in result.suggestions)
        assert result.stage_reached == PipelineStage.SUGGEST
        assert len(result.suggestions) == 1
