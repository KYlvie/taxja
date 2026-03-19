"""Phase-2 processing decision contracts for the document pipeline."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import DocumentType as DBDocumentType


class ProcessingPhase(str, Enum):
    """Explicit business-processing phases for the pipeline."""

    PHASE_1 = "phase_1_first_result"
    PHASE_2 = "phase_2_persistence_branch"


class ProcessingAction(str, Enum):
    """Phase-2 actions the orchestrator may execute."""

    PURCHASE_CONTRACT = "purchase_contract"
    RENTAL_CONTRACT = "rental_contract"
    LOAN_CONTRACT = "loan_contract"
    INSURANCE_RECURRING = "insurance_recurring"
    TAX_FORM_IMPORT = "tax_form_import"
    TRANSACTION_SUGGESTIONS = "transaction_suggestions"
    ASSET_SUGGESTION = "asset_suggestion"


class ProcessingDecision(BaseModel):
    """Explicit Phase-2 execution plan for a classified document."""

    model_config = ConfigDict(use_enum_values=True)

    phase: ProcessingPhase = ProcessingPhase.PHASE_2
    document_type: str
    primary_actions: list[ProcessingAction] = Field(default_factory=list)
    secondary_actions: list[ProcessingAction] = Field(default_factory=list)
    normalized_input_required: bool = False
    quality_gate_required: bool = False
    asset_persistence_baseline: str = "property"


class ProcessingDecisionService:
    """Translate classified document types into explicit Phase-2 actions.

    Note: quality-gate authority currently applies only to the asset path.
    The wider document pipeline still contains document-type-specific branches.
    """

    def build_phase_two_decision(
        self,
        db_type: DBDocumentType,
        *,
        tax_form_types: set[DBDocumentType],
    ) -> ProcessingDecision:
        primary_actions: list[ProcessingAction]
        secondary_actions: list[ProcessingAction] = []

        if db_type == DBDocumentType.PURCHASE_CONTRACT:
            primary_actions = [ProcessingAction.PURCHASE_CONTRACT]
            secondary_actions = [ProcessingAction.ASSET_SUGGESTION]
        elif db_type == DBDocumentType.RENTAL_CONTRACT:
            primary_actions = [ProcessingAction.RENTAL_CONTRACT]
        elif db_type == DBDocumentType.LOAN_CONTRACT:
            primary_actions = [ProcessingAction.LOAN_CONTRACT]
        elif db_type == DBDocumentType.VERSICHERUNGSBESTAETIGUNG:
            primary_actions = [ProcessingAction.INSURANCE_RECURRING]
        elif db_type in tax_form_types:
            primary_actions = [ProcessingAction.TAX_FORM_IMPORT]
        else:
            primary_actions = [ProcessingAction.TRANSACTION_SUGGESTIONS]
            secondary_actions = [ProcessingAction.ASSET_SUGGESTION]

        asset_path_enabled = ProcessingAction.ASSET_SUGGESTION in (
            primary_actions + secondary_actions
        )

        return ProcessingDecision(
            document_type=db_type.value if hasattr(db_type, "value") else str(db_type),
            primary_actions=primary_actions,
            secondary_actions=secondary_actions,
            normalized_input_required=asset_path_enabled,
            quality_gate_required=asset_path_enabled,
        )
