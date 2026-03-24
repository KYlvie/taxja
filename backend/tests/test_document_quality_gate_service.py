"""Tests for the asset quality-gate branching contract."""
from datetime import datetime
from decimal import Decimal

from app.schemas.asset_recognition import (
    AssetCandidate,
    AssetDecisionAudit,
    AssetProfileInputsUsed,
    AssetRecognitionDecision,
    AssetRecognitionResult,
    AssetTaxFlags,
    ComparisonBasis,
    DuplicateAssessment,
    DuplicateStatus,
    PolicyOutcome,
    VatRecoverableStatus,
)
from app.schemas.user import TaxProfileCompleteness
from app.services.document_normalization_service import NormalizedDocument
from app.services.document_quality_gate_service import (
    DocumentQualityGateService,
    QualityGateDecision,
)


def _normalized_document(*, complete: bool) -> NormalizedDocument:
    missing = [] if complete else ["vat_status", "gewinnermittlungsart"]
    return NormalizedDocument(
        document_id=12,
        document_type="invoice",
        raw_text="Laptop invoice",
        ocr_confidence=Decimal("0.96"),
        extracted_data={"amount": 1499.0},
        upload_timestamp=datetime(2026, 3, 19, 10, 0, 0),
        tax_profile_completeness=TaxProfileCompleteness(
            is_complete_for_asset_automation=complete,
            missing_fields=missing,
        ),
        profile_inputs_used={"vat_status": "regelbesteuert", "gewinnermittlungsart": "ea_rechnung"},
    )


def _recognition_result() -> AssetRecognitionResult:
    return AssetRecognitionResult(
        decision=AssetRecognitionDecision.CREATE_ASSET_AUTO,
        asset_candidate=AssetCandidate(
            asset_type="computer",
            asset_subtype="computer",
            asset_name="Laptop",
            vendor_name="Dell",
        ),
        tax_flags=AssetTaxFlags(
            depreciable=True,
            gwg_eligible=False,
            gwg_default_selected=False,
            gwg_election_required=False,
            comparison_basis=ComparisonBasis.NET,
            comparison_amount=Decimal("1249.17"),
            vat_recoverable_status=VatRecoverableStatus.LIKELY_YES,
            ifb_candidate=False,
            half_year_rule_applicable=False,
        ),
        reason_codes=[],
        review_reasons=[],
        missing_fields=[],
        requires_user_confirmation=False,
        policy_confidence=Decimal("0.98"),
        policy_rule_ids=["VAT-001"],
        duplicate=DuplicateAssessment(duplicate_status=DuplicateStatus.NONE),
        decision_audit=AssetDecisionAudit(
            recognition_decision=AssetRecognitionDecision.CREATE_ASSET_AUTO,
            policy_outcome=PolicyOutcome.AUTO_CREATE,
            policy_confidence=Decimal("0.98"),
            reason_codes=[],
            review_reasons=[],
            missing_fields=[],
            duplicate_status=DuplicateStatus.NONE,
            source_document_id=12,
            profile_inputs_used=AssetProfileInputsUsed(
                vat_status="regelbesteuert",
                gewinnermittlungsart="ea_rechnung",
            ),
        ),
    )


def test_quality_gate_allows_auto_create_only_for_complete_profile():
    gate = DocumentQualityGateService()

    result = gate.evaluate_asset_decision(
        _normalized_document(complete=True),
        _recognition_result(),
    )

    assert result.decision == QualityGateDecision.AUTO_CREATE
    assert result.policy_outcome == PolicyOutcome.AUTO_CREATE
    assert result.blocks_side_effects is False


def test_quality_gate_blocks_auto_create_when_tax_profile_incomplete():
    gate = DocumentQualityGateService()

    result = gate.evaluate_asset_decision(
        _normalized_document(complete=False),
        _recognition_result(),
    )

    assert result.decision == QualityGateDecision.SUGGESTION_REQUIRED
    assert result.policy_outcome == PolicyOutcome.SUGGESTION_REQUIRED
    assert result.blocks_side_effects is True
    assert result.missing_fields == ["vat_status", "gewinnermittlungsart"]
