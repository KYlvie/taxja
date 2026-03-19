"""Quality-gate authority for persistence branching decisions."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.asset_recognition import (
    AssetRecognitionDecision,
    AssetRecognitionResult,
    DuplicateStatus,
    PolicyOutcome,
)
from app.services.document_normalization_service import NormalizedDocument


class QualityGateDecision(str, Enum):
    NO_ACTION = "no_action"
    DUPLICATE_WARNING = "duplicate_warning"
    MANUAL_REVIEW = "manual_review"
    SUGGESTION_REQUIRED = "suggestion_required"
    AUTO_CREATE = "auto_create"


class QualityGateResult(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    decision: QualityGateDecision
    policy_outcome: PolicyOutcome
    blocks_side_effects: bool
    requires_user_confirmation: bool
    reason_codes: list[str] = Field(default_factory=list)
    review_reasons: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    duplicate_status: DuplicateStatus | None = None


class DocumentQualityGateService:
    """Central persistence-branching authority for the asset path."""

    def evaluate_asset_decision(
        self,
        normalized_document: NormalizedDocument,
        recognition_result: AssetRecognitionResult,
    ) -> QualityGateResult:
        duplicate_status = recognition_result.duplicate.duplicate_status
        reason_codes = [getattr(code, "value", code) for code in recognition_result.reason_codes]
        review_reasons = [getattr(reason, "value", reason) for reason in recognition_result.review_reasons]
        missing_fields = list(
            dict.fromkeys(
                list(recognition_result.missing_fields)
                + list(normalized_document.tax_profile_completeness.missing_fields)
            )
        )

        if duplicate_status and duplicate_status != DuplicateStatus.NONE:
            return QualityGateResult(
                decision=QualityGateDecision.DUPLICATE_WARNING,
                policy_outcome=PolicyOutcome.DUPLICATE_WARNING,
                blocks_side_effects=True,
                requires_user_confirmation=True,
                reason_codes=reason_codes,
                review_reasons=review_reasons,
                missing_fields=missing_fields,
                duplicate_status=duplicate_status,
            )

        if recognition_result.decision == AssetRecognitionDecision.EXPENSE_ONLY:
            return QualityGateResult(
                decision=QualityGateDecision.NO_ACTION,
                policy_outcome=PolicyOutcome.EXPENSE_ONLY,
                blocks_side_effects=True,
                requires_user_confirmation=False,
                reason_codes=reason_codes,
                review_reasons=review_reasons,
                missing_fields=missing_fields,
                duplicate_status=duplicate_status,
            )

        if recognition_result.decision == AssetRecognitionDecision.MANUAL_REVIEW:
            return QualityGateResult(
                decision=QualityGateDecision.MANUAL_REVIEW,
                policy_outcome=PolicyOutcome.MANUAL_REVIEW,
                blocks_side_effects=True,
                requires_user_confirmation=True,
                reason_codes=reason_codes,
                review_reasons=review_reasons,
                missing_fields=missing_fields,
                duplicate_status=duplicate_status,
            )

        if (
            not normalized_document.tax_profile_completeness.is_complete_for_asset_automation
            or missing_fields
            or review_reasons
            or recognition_result.decision != AssetRecognitionDecision.CREATE_ASSET_AUTO
        ):
            return QualityGateResult(
                decision=QualityGateDecision.SUGGESTION_REQUIRED,
                policy_outcome=PolicyOutcome.SUGGESTION_REQUIRED,
                blocks_side_effects=True,
                requires_user_confirmation=True,
                reason_codes=reason_codes,
                review_reasons=review_reasons,
                missing_fields=missing_fields,
                duplicate_status=duplicate_status,
            )

        return QualityGateResult(
            decision=QualityGateDecision.AUTO_CREATE,
            policy_outcome=PolicyOutcome.AUTO_CREATE,
            blocks_side_effects=False,
            requires_user_confirmation=False,
            reason_codes=reason_codes,
            review_reasons=review_reasons,
            missing_fields=missing_fields,
            duplicate_status=duplicate_status,
        )
