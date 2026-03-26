from unittest.mock import MagicMock, patch

from app.models.document import DocumentType as DBDocumentType
from app.services.document_pipeline_orchestrator import DocumentPipelineOrchestrator, PipelineResult
from app.services.transaction_gate_service import TransactionGateDecision


def test_build_transaction_suggestions_rolls_back_after_non_critical_creation_failure():
    orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
    orchestrator.db = MagicMock()

    document = MagicMock()
    document.id = 325
    document.user_id = 46

    result = PipelineResult(
        document_id=325,
        extracted_data={"amount": 64.03, "date": "2024-10-16", "merchant": "INTERSPAR"},
    )
    result.ocr_confidence_score = 0.85

    suggestion = {
        "amount": "64.03",
        "date": "2024-10-16",
        "description": "INTERSPAR",
        "confidence": 0.85,
    }
    service = MagicMock()
    service.create_split_suggestions.return_value = [suggestion]
    service.create_transaction_from_suggestion_with_result.side_effect = RuntimeError("missing bank_reconciled column")

    with patch("app.services.ocr_transaction_service.OCRTransactionService", return_value=service):
        suggestions = orchestrator._build_transaction_suggestions(
            document,
            DBDocumentType.RECEIPT,
            result,
        )

    assert suggestions[0]["status"] == "pending"
    orchestrator.db.rollback.assert_called_once()


def test_build_transaction_suggestions_prefers_current_ocr_confidence_over_stale_document_value():
    orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
    orchestrator.db = MagicMock()

    document = MagicMock()
    document.id = 326
    document.user_id = 46
    document.confidence_score = 0.10

    result = PipelineResult(
        document_id=326,
        extracted_data={"amount": 64.03, "date": "2024-10-16", "merchant": "INTERSPAR"},
    )
    result.ocr_confidence_score = 0.95

    suggestion = {
        "amount": "64.03",
        "date": "2024-10-16",
        "description": "INTERSPAR",
        "confidence": 0.95,
    }
    creation_result = MagicMock(
        transaction=MagicMock(id=9001),
        created=True,
    )
    service = MagicMock()
    service.create_split_suggestions.return_value = [suggestion]
    service.create_transaction_from_suggestion_with_result.return_value = creation_result

    with patch("app.services.ocr_transaction_service.OCRTransactionService", return_value=service):
        suggestions = orchestrator._build_transaction_suggestions(
            document,
            DBDocumentType.RECEIPT,
            result,
        )

    assert suggestions[0]["status"] == "auto-created"
    assert suggestions[0]["reviewed"] is True
    service.create_transaction_from_suggestion_with_result.assert_called_once()


def test_build_transaction_suggestions_recovers_missing_date_before_gate():
    orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
    orchestrator.db = MagicMock()

    document = MagicMock()
    document.id = 327
    document.user_id = 46

    result = PipelineResult(
        document_id=327,
        extracted_data={"amount": 64.03, "merchant": "INTERSPAR"},
        raw_text="Receipt text with amount and date",
    )
    result.ocr_confidence_score = 0.92

    suggestion = {
        "amount": "64.03",
        "date": None,
        "description": "INTERSPAR",
        "confidence": 0.90,
    }
    creation_result = MagicMock(
        transaction=MagicMock(id=9002),
        created=True,
    )
    service = MagicMock()
    service.create_split_suggestions.return_value = [suggestion]
    service.create_transaction_from_suggestion_with_result.return_value = creation_result

    with (
        patch("app.services.ocr_transaction_service.OCRTransactionService", return_value=service),
        patch.object(
            DocumentPipelineOrchestrator,
            "_recover_missing_invoice_transaction_fields",
            return_value={"date": "2024-10-16"},
        ) as recover_mock,
    ):
        suggestions = orchestrator._build_transaction_suggestions(
            document,
            DBDocumentType.RECEIPT,
            result,
        )

    assert suggestions[0]["date"] == "2024-10-16"
    assert suggestions[0]["field_recovery"] == {
        "applied": True,
        "fields": ["date"],
    }
    assert suggestions[0]["gate_decision"] in {
        TransactionGateDecision.AUTO_CREATE.value,
        TransactionGateDecision.PENDING_REVIEW.value,
    }
    recover_mock.assert_called_once()
    service.create_transaction_from_suggestion_with_result.assert_called_once()


def test_build_transaction_suggestions_keeps_missing_date_manual_when_recovery_fails():
    orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
    orchestrator.db = MagicMock()

    document = MagicMock()
    document.id = 328
    document.user_id = 46

    result = PipelineResult(
        document_id=328,
        extracted_data={"amount": 64.03, "merchant": "INTERSPAR"},
        raw_text="Receipt text with no usable date",
    )
    result.ocr_confidence_score = 0.92

    suggestion = {
        "amount": "64.03",
        "date": None,
        "description": "INTERSPAR",
        "confidence": 0.90,
    }
    service = MagicMock()
    service.create_split_suggestions.return_value = [suggestion]

    with (
        patch("app.services.ocr_transaction_service.OCRTransactionService", return_value=service),
        patch.object(
            DocumentPipelineOrchestrator,
            "_recover_missing_invoice_transaction_fields",
            return_value={},
        ) as recover_mock,
    ):
        suggestions = orchestrator._build_transaction_suggestions(
            document,
            DBDocumentType.RECEIPT,
            result,
        )

    assert suggestions[0]["status"] == "manual-review-required"
    assert suggestions[0]["gate_decision"] == TransactionGateDecision.MANUAL_REQUIRED.value
    assert "missing_date" in suggestions[0]["gate_reasons"]
    recover_mock.assert_called_once()
    service.create_transaction_from_suggestion_with_result.assert_not_called()
