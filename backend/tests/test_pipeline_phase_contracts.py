from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.models.document import DocumentType as DBDocumentType
from app.services.document_metering_service import (
    DocumentMeteringService,
    PhaseCheckpointType,
)
from app.services.document_pipeline_orchestrator import (
    ClassificationResult,
    ConfidenceLevel,
    DocumentPipelineOrchestrator,
    PipelineResult,
    PipelineStage,
)
from app.services.processing_decision_service import (
    ProcessingAction,
    ProcessingDecisionService,
    ProcessingPhase,
)


def test_processing_decision_routes_generic_expense_docs_to_transactions_then_asset():
    decision = ProcessingDecisionService().build_phase_two_decision(
        DBDocumentType.RECEIPT,
        tax_form_types=set(DocumentPipelineOrchestrator.TAX_FORM_DB_TYPES),
    )

    assert decision.phase == ProcessingPhase.PHASE_2
    assert decision.primary_actions == [ProcessingAction.TRANSACTION_SUGGESTIONS]
    assert decision.secondary_actions == [ProcessingAction.ASSET_SUGGESTION]
    assert decision.normalized_input_required is True
    assert decision.quality_gate_required is True
    assert decision.asset_persistence_baseline == "property"


def test_processing_decision_routes_purchase_contract_to_property_then_asset():
    decision = ProcessingDecisionService().build_phase_two_decision(
        DBDocumentType.PURCHASE_CONTRACT,
        tax_form_types=set(DocumentPipelineOrchestrator.TAX_FORM_DB_TYPES),
    )

    assert decision.primary_actions == [ProcessingAction.PURCHASE_CONTRACT]
    assert decision.secondary_actions == [ProcessingAction.ASSET_SUGGESTION]


def test_processing_decision_routes_bank_statements_to_dedicated_import_action():
    decision = ProcessingDecisionService().build_phase_two_decision(
        DBDocumentType.BANK_STATEMENT,
        tax_form_types=set(DocumentPipelineOrchestrator.TAX_FORM_DB_TYPES),
    )

    assert decision.primary_actions == [ProcessingAction.BANK_STATEMENT_IMPORT]
    assert decision.secondary_actions == []
    assert decision.normalized_input_required is False
    assert decision.quality_gate_required is False


def test_document_metering_builds_explicit_phase_checkpoints():
    metering_service = DocumentMeteringService()

    phase_1 = metering_service.begin_phase(
        phase=ProcessingPhase.PHASE_1,
        checkpoint=PhaseCheckpointType.FIRST_RESULT,
        entry_stage=PipelineStage.CLASSIFY.value,
        metadata={"document_id": 7},
    )
    completed_phase_1 = metering_service.complete_phase(
        phase_1,
        exit_stage=PipelineStage.VALIDATE.value,
        metadata={"validation_error_count": 0},
    )

    result = PipelineResult(
        document_id=7,
        stage_reached=PipelineStage.SUGGEST,
        current_state="first_result_available",
        confidence_level=ConfidenceLevel.HIGH,
        phase_checkpoints=[completed_phase_1],
        processing_decision={"phase": "phase_2_persistence_branch"},
    )

    metadata = metering_service.build_pipeline_metadata(result=result)

    assert metadata["phase_checkpoints"][0]["phase"] == "phase_1_first_result"
    assert metadata["phase_checkpoints"][0]["checkpoint"] == "first_result"
    assert metadata["phase_checkpoints"][0]["metadata"]["validation_error_count"] == 0
    assert metadata["current_state"] == "first_result_available"
    assert metadata["processing_decision"]["phase"] == "phase_2_persistence_branch"


def test_stage_suggest_records_processing_decision_and_runs_planned_actions():
    orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
    orchestrator.db = MagicMock()

    result = PipelineResult(document_id=1)
    document = SimpleNamespace(id=1, ocr_result={}, uploaded_at=datetime.utcnow())

    with patch.object(orchestrator, "_build_transaction_suggestions", return_value=[]) as tx_mock, patch.object(
        orchestrator,
        "_build_asset_suggestion",
        return_value=None,
    ) as asset_mock:
        orchestrator._stage_suggest(
            document=document,
            db_type=DBDocumentType.RECEIPT,
            ocr_result={},
            result=result,
        )

    assert result.processing_decision is not None
    assert result.processing_decision["primary_actions"] == ["transaction_suggestions"]
    assert result.processing_decision["secondary_actions"] == ["asset_suggestion"]
    tx_mock.assert_called_once()
    asset_mock.assert_called_once()


def test_stage_suggest_routes_bank_statements_to_dedicated_import_builder():
    orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
    orchestrator.db = MagicMock()

    result = PipelineResult(document_id=2)
    document = SimpleNamespace(id=2, ocr_result={}, uploaded_at=datetime.utcnow())

    with patch.object(
        orchestrator,
        "_build_bank_statement_import_suggestion",
        return_value={"type": "import_bank_statement"},
    ) as bank_mock, patch.object(
        orchestrator,
        "_build_tax_form_suggestion",
        return_value=None,
    ) as tax_mock:
        orchestrator._stage_suggest(
            document=document,
            db_type=DBDocumentType.BANK_STATEMENT,
            ocr_result={},
            result=result,
        )

    assert result.processing_decision is not None
    assert result.processing_decision["primary_actions"] == ["bank_statement_import"]
    assert result.processing_decision["secondary_actions"] == []
    bank_mock.assert_called_once()
    tax_mock.assert_not_called()


def test_finalize_persists_processing_decision_and_phase_checkpoints():
    orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
    orchestrator.db = MagicMock()

    document = SimpleNamespace(
        ocr_result={},
        raw_text=None,
        confidence_score=None,
        processed_at=None,
    )

    result = PipelineResult(
        document_id=1,
        stage_reached=PipelineStage.SUGGEST,
        classification=ClassificationResult(
            document_type="invoice",
            confidence=0.91,
            method="regex",
        ),
        extracted_data={"amount": 1499.0},
        raw_text="Dell Laptop",
        confidence_level=ConfidenceLevel.HIGH,
        phase_checkpoints=[
            {
                "phase": "phase_1_first_result",
                "checkpoint": "first_result",
                "status": "completed",
                "entry_stage": "classify",
                "exit_stage": "validate",
                "metadata": {"document_type": "invoice"},
            }
        ],
        processing_decision={
            "phase": "phase_2_persistence_branch",
            "asset_persistence_baseline": "property",
        },
        current_state="phase_2_failed",
        needs_review=False,
    )

    orchestrator._finalize(
        result=result,
        document=document,
        start_time=datetime.utcnow(),
    )

    assert document.ocr_result["_pipeline"]["phase_checkpoints"][0]["phase"] == "phase_1_first_result"
    assert document.ocr_result["_pipeline"]["current_state"] == "phase_2_failed"
    assert (
        document.ocr_result["_pipeline"]["processing_decision"]["asset_persistence_baseline"]
        == "property"
    )
