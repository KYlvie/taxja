"""
Transaction creation gate service.

Determines whether a document should auto-create a transaction, create one
pending user review, or only store a suggestion for later manual confirmation.

Design rationale
----------------
Different document types carry different risk levels:

- Receipts are almost always expenses with a clear amount → lower bar.
- Invoices can be income OR expense, requiring direction resolution → higher bar.
- Credit notes involve reversals and sign flips → never auto-confirm.
- Lohnzettel/payslips are standardised income documents → lower bar.

The composite confidence is ``min(ocr, direction, classification)`` so that
any single weak signal prevents premature auto-creation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

from app.models.document import DocumentType
from app.services.contract_role_service import (
    BLOCKING_COMMERCIAL_SEMANTICS,
    TransactionDirectionResolution,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

class TransactionGateDecision(str, Enum):
    """Three-way decision for transaction creation from OCR."""

    AUTO_CREATE = "auto_create"
    """High confidence – create transaction AND mark confirmed."""

    PENDING_REVIEW = "pending_review"
    """Medium confidence – create transaction with needs_review=True."""

    MANUAL_REQUIRED = "manual_required"
    """Low confidence – do NOT create a transaction; store suggestion only."""


@dataclass(slots=True)
class TransactionGateResult:
    """Output of the gate evaluation."""

    decision: TransactionGateDecision
    composite_confidence: float
    reasons: list[str] = field(default_factory=list)

    # Convenience helpers
    @property
    def should_create_transaction(self) -> bool:
        return self.decision in (
            TransactionGateDecision.AUTO_CREATE,
            TransactionGateDecision.PENDING_REVIEW,
        )

    @property
    def needs_review(self) -> bool:
        return self.decision == TransactionGateDecision.PENDING_REVIEW

    @property
    def reviewed(self) -> bool:
        return self.decision == TransactionGateDecision.AUTO_CREATE


# ---------------------------------------------------------------------------
# Per-document-type gate profiles
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class _GateProfile:
    """Thresholds and flags for a specific document type."""

    auto_create_threshold: float | None
    """Composite confidence >= this → AUTO_CREATE.  None = never auto-create."""

    pending_threshold: float
    """Composite confidence >= this (and < auto_create_threshold) → PENDING_REVIEW."""

    require_direction: bool = False
    """If True, direction_confidence is included in composite; unknown direction
    causes a hard downgrade."""

    min_direction_confidence: float = 0.0
    """When require_direction=True, direction confidence below this value forces
    the composite down to at most ``pending_threshold - 0.01``."""

    require_date: bool = False
    """When True, missing date is a hard blocker after any recovery step."""


_DEFAULT_PROFILE = _GateProfile(
    auto_create_threshold=0.90,
    pending_threshold=0.70,
    require_direction=True,
    min_direction_confidence=0.90,
)

GATE_PROFILES: Dict[str, _GateProfile] = {
    # --- Simple expense documents: direction is almost always "expense" ---
    DocumentType.RECEIPT.value: _GateProfile(
        auto_create_threshold=0.85,
        pending_threshold=0.70,
        require_direction=False,
        require_date=True,
    ),

    # --- Standardised income documents ---
    DocumentType.LOHNZETTEL.value: _GateProfile(
        auto_create_threshold=0.85,
        pending_threshold=0.65,
        require_direction=False,  # Always income
    ),
    DocumentType.PAYSLIP.value: _GateProfile(
        auto_create_threshold=0.85,
        pending_threshold=0.65,
        require_direction=False,  # Always income
    ),

    # --- Invoices: can be income or expense, need direction ---
    DocumentType.INVOICE.value: _GateProfile(
        auto_create_threshold=0.85,
        pending_threshold=0.70,
        require_direction=True,
        min_direction_confidence=0.85,
        require_date=True,
    ),

    # --- Known expense-only document types ---
    DocumentType.SVS_NOTICE.value: _GateProfile(
        auto_create_threshold=0.85,
        pending_threshold=0.65,
        require_direction=False,
    ),
    DocumentType.KIRCHENBEITRAG.value: _GateProfile(
        auto_create_threshold=0.85,
        pending_threshold=0.65,
        require_direction=False,
    ),
    DocumentType.KINDERBETREUUNGSKOSTEN.value: _GateProfile(
        auto_create_threshold=0.85,
        pending_threshold=0.65,
        require_direction=False,
    ),
    DocumentType.FORTBILDUNGSKOSTEN.value: _GateProfile(
        auto_create_threshold=0.85,
        pending_threshold=0.65,
        require_direction=False,
    ),
    DocumentType.BETRIEBSKOSTENABRECHNUNG.value: _GateProfile(
        auto_create_threshold=0.85,
        pending_threshold=0.65,
        require_direction=False,
    ),
}

# Credit notes and similar high-risk reversals: never auto-create.
# They go through the invoice profile but semantics blocking will prevent
# AUTO_CREATE (see _check_semantic_blockers below).


# ---------------------------------------------------------------------------
# Composite confidence calculation
# ---------------------------------------------------------------------------

def compute_composite_confidence(
    *,
    ocr_confidence: float,
    classification_confidence: float,
    direction_resolution: TransactionDirectionResolution | None,
    profile: _GateProfile,
    ocr_data: dict[str, Any] | None = None,
) -> tuple[float, list[str]]:
    """Return (composite_confidence, [reason_strings]).

    The composite is ``min(all contributing factors)``.  Hard blockers
    (missing amount, proforma semantics, etc.) force the value to 0.
    """
    ocr_data = ocr_data or {}
    factors: list[float] = []
    reasons: list[str] = []

    # --- OCR field confidence ---
    factors.append(ocr_confidence)

    # --- Classification confidence ---
    factors.append(classification_confidence)

    # --- Direction confidence (only if profile requires it) ---
    # Respect gate_enabled: when the direction resolution explicitly disables
    # gating (e.g. bank statements), skip direction-based penalties.
    direction_gate_active = (
        profile.require_direction
        and (direction_resolution is None or direction_resolution.gate_enabled)
    )

    if direction_gate_active and direction_resolution:
        dir_conf = direction_resolution.confidence
        auto_cap = (
            max((profile.auto_create_threshold or profile.pending_threshold) - 0.01, profile.pending_threshold)
        )

        if direction_resolution.candidate == "unknown":
            reasons.append("direction_unknown")
            factors.append(auto_cap)
        elif dir_conf < profile.min_direction_confidence:
            reasons.append(
                f"direction_confidence_low ({dir_conf:.2f} < {profile.min_direction_confidence})"
            )
            factors.append(auto_cap)
        else:
            factors.append(dir_conf)

    elif direction_gate_active and direction_resolution is None:
        reasons.append("direction_not_resolved")
        factors.append(
            max((profile.auto_create_threshold or profile.pending_threshold) - 0.01, profile.pending_threshold)
        )

    # --- Hard blockers: missing critical fields ---
    amount = ocr_data.get("amount")
    if amount is None or amount == "":
        reasons.append("missing_amount")
        return 0.0, reasons

    date_val = ocr_data.get("date")
    if not date_val:
        reasons.append("missing_date")
        if profile.require_date:
            return 0.0, reasons
        factors.append(0.50)  # Strong downgrade, not a hard block

    # --- Semantic blockers (proforma, delivery note) ---
    # Only apply when the direction gate is active (gate_enabled=True)
    if direction_resolution and direction_resolution.gate_enabled:
        semantics = direction_resolution.semantics
        if semantics in BLOCKING_COMMERCIAL_SEMANTICS:
            reasons.append(f"blocked_semantics:{semantics}")
            return 0.0, reasons

        if direction_resolution.is_reversal:
            reasons.append("reversal_detected")
            factors.append(0.60)  # Strong downgrade for reversals

    # --- Classifier-level review flag ---
    # (This is set by the ML/rule classifier when it's unsure about category)
    # We don't have direct access here but it feeds into classification_confidence.

    composite = min(factors) if factors else 0.0
    return round(composite, 4), reasons


# ---------------------------------------------------------------------------
# Main gate evaluation
# ---------------------------------------------------------------------------

def evaluate_transaction_gate(
    *,
    document_type: str,
    ocr_confidence: float,
    classification_confidence: float,
    direction_resolution: TransactionDirectionResolution | None = None,
    ocr_data: dict[str, Any] | None = None,
    requires_review: bool = False,
) -> TransactionGateResult:
    """Evaluate whether a transaction should be auto-created, created pending
    review, or deferred for manual action.

    Parameters
    ----------
    document_type:
        The ``DocumentType.value`` string (e.g. ``"receipt"``, ``"invoice"``).
    ocr_confidence:
        Overall OCR extraction confidence (``document.confidence_score``).
    classification_confidence:
        Classification confidence from the classifier (``classification["confidence"]``).
    direction_resolution:
        Result of ``ContractRoleService.resolve_transaction_direction()``, if
        available.  Required for invoice-type documents.
    ocr_data:
        Extracted OCR data dict; used to check for missing critical fields.
    requires_review:
        Whether the classifier explicitly flagged this for manual review.

    Returns
    -------
    TransactionGateResult
        Contains the decision, composite confidence, and human-readable reasons.
    """
    profile = GATE_PROFILES.get(document_type, _DEFAULT_PROFILE)

    composite, reasons = compute_composite_confidence(
        ocr_confidence=ocr_confidence,
        classification_confidence=classification_confidence,
        direction_resolution=direction_resolution,
        profile=profile,
        ocr_data=ocr_data,
    )

    # Classifier-level review flag forces a downgrade
    if requires_review:
        reasons.append("classifier_requires_review")
        # Cannot be auto-created if classifier says review needed
        composite = min(composite, profile.pending_threshold)

    # --- Decision ---
    if (
        profile.auto_create_threshold is not None
        and composite >= profile.auto_create_threshold
    ):
        decision = TransactionGateDecision.AUTO_CREATE
    elif composite >= profile.pending_threshold:
        decision = TransactionGateDecision.PENDING_REVIEW
    else:
        decision = TransactionGateDecision.MANUAL_REQUIRED

    result = TransactionGateResult(
        decision=decision,
        composite_confidence=composite,
        reasons=reasons,
    )

    logger.info(
        "Transaction gate [%s]: decision=%s composite=%.4f reasons=%s",
        document_type,
        decision.value,
        composite,
        reasons or "none",
    )

    return result
