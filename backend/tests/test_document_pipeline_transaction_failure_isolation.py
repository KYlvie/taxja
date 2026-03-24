from unittest.mock import MagicMock, patch

from app.models.document import DocumentType as DBDocumentType
from app.services.document_pipeline_orchestrator import DocumentPipelineOrchestrator, PipelineResult


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

    suggestion = {"amount": "64.03", "date": "2024-10-16", "description": "INTERSPAR"}
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
