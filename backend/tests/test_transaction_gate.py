"""Tests for the transaction creation gate service."""

from app.models.document import DocumentType
from app.services.contract_role_service import TransactionDirectionResolution
from app.services.transaction_gate_service import (
    TransactionGateDecision,
    evaluate_transaction_gate,
)


def _make_direction(
    candidate="expense", confidence=0.94, semantics="standard_invoice", is_reversal=False,
):
    return TransactionDirectionResolution(
        candidate=candidate,
        confidence=confidence,
        source="party_name_match",
        evidence=[],
        semantics=semantics,
        is_reversal=is_reversal,
        mode="shadow",
    )


# ---------------------------------------------------------------------------
# Receipt tests (lower thresholds, no direction required)
# ---------------------------------------------------------------------------

class TestReceiptGate:
    def test_high_confidence_receipt_auto_creates(self):
        result = evaluate_transaction_gate(
            document_type=DocumentType.RECEIPT.value,
            ocr_confidence=0.92,
            classification_confidence=0.88,
            ocr_data={"amount": 48.70, "date": "2026-03-20"},
        )
        assert result.decision == TransactionGateDecision.AUTO_CREATE
        assert result.should_create_transaction is True
        assert result.needs_review is False
        assert result.reviewed is True

    def test_medium_confidence_receipt_pending_review(self):
        result = evaluate_transaction_gate(
            document_type=DocumentType.RECEIPT.value,
            ocr_confidence=0.78,
            classification_confidence=0.72,
            ocr_data={"amount": 23.45, "date": "2026-03-18"},
        )
        assert result.decision == TransactionGateDecision.PENDING_REVIEW
        assert result.should_create_transaction is True
        assert result.needs_review is True
        assert result.reviewed is False

    def test_low_confidence_receipt_manual_required(self):
        result = evaluate_transaction_gate(
            document_type=DocumentType.RECEIPT.value,
            ocr_confidence=0.55,
            classification_confidence=0.60,
            ocr_data={"amount": 15.00, "date": "2026-03-15"},
        )
        assert result.decision == TransactionGateDecision.MANUAL_REQUIRED
        assert result.should_create_transaction is False

    def test_receipt_missing_amount_blocks(self):
        result = evaluate_transaction_gate(
            document_type=DocumentType.RECEIPT.value,
            ocr_confidence=0.95,
            classification_confidence=0.90,
            ocr_data={"date": "2026-03-20"},  # no amount
        )
        assert result.decision == TransactionGateDecision.MANUAL_REQUIRED
        assert "missing_amount" in result.reasons


# ---------------------------------------------------------------------------
# Invoice tests (higher thresholds, direction required)
# ---------------------------------------------------------------------------

class TestInvoiceGate:
    def test_high_confidence_with_direction_auto_creates(self):
        result = evaluate_transaction_gate(
            document_type=DocumentType.INVOICE.value,
            ocr_confidence=0.93,
            classification_confidence=0.91,
            direction_resolution=_make_direction(candidate="expense", confidence=0.94),
            ocr_data={"amount": 3500.0, "date": "2026-03-20"},
        )
        assert result.decision == TransactionGateDecision.AUTO_CREATE

    def test_high_ocr_but_unknown_direction_degrades(self):
        result = evaluate_transaction_gate(
            document_type=DocumentType.INVOICE.value,
            ocr_confidence=0.95,
            classification_confidence=0.92,
            direction_resolution=_make_direction(candidate="unknown", confidence=0.30),
            ocr_data={"amount": 1500.0, "date": "2026-03-15"},
        )
        # Direction unknown forces composite below auto-create
        assert result.decision in (
            TransactionGateDecision.PENDING_REVIEW,
            TransactionGateDecision.MANUAL_REQUIRED,
        )
        assert "direction_unknown" in result.reasons

    def test_invoice_without_direction_resolution_degrades(self):
        result = evaluate_transaction_gate(
            document_type=DocumentType.INVOICE.value,
            ocr_confidence=0.92,
            classification_confidence=0.90,
            direction_resolution=None,  # not resolved
            ocr_data={"amount": 500.0, "date": "2026-03-10"},
        )
        assert result.decision != TransactionGateDecision.AUTO_CREATE
        assert "direction_not_resolved" in result.reasons

    def test_invoice_medium_confidence_pending(self):
        result = evaluate_transaction_gate(
            document_type=DocumentType.INVOICE.value,
            ocr_confidence=0.82,
            classification_confidence=0.78,
            direction_resolution=_make_direction(confidence=0.82),
            ocr_data={"amount": 900.0, "date": "2026-03-12"},
        )
        assert result.decision == TransactionGateDecision.PENDING_REVIEW

    def test_invoice_low_confidence_manual(self):
        result = evaluate_transaction_gate(
            document_type=DocumentType.INVOICE.value,
            ocr_confidence=0.55,
            classification_confidence=0.60,
            direction_resolution=_make_direction(confidence=0.50),
            ocr_data={"amount": 200.0, "date": "2026-03-01"},
        )
        assert result.decision == TransactionGateDecision.MANUAL_REQUIRED


# ---------------------------------------------------------------------------
# Semantic blockers
# ---------------------------------------------------------------------------

class TestSemanticBlockers:
    def test_proforma_invoice_blocked(self):
        result = evaluate_transaction_gate(
            document_type=DocumentType.INVOICE.value,
            ocr_confidence=0.95,
            classification_confidence=0.92,
            direction_resolution=_make_direction(semantics="proforma", confidence=0.94),
            ocr_data={"amount": 5000.0, "date": "2026-03-20"},
        )
        assert result.decision == TransactionGateDecision.MANUAL_REQUIRED
        assert "blocked_semantics:proforma" in result.reasons

    def test_delivery_note_blocked(self):
        result = evaluate_transaction_gate(
            document_type=DocumentType.INVOICE.value,
            ocr_confidence=0.92,
            classification_confidence=0.90,
            direction_resolution=_make_direction(semantics="delivery_note", confidence=0.91),
            ocr_data={"amount": 1200.0, "date": "2026-03-15"},
        )
        assert result.decision == TransactionGateDecision.MANUAL_REQUIRED

    def test_reversal_downgrades(self):
        result = evaluate_transaction_gate(
            document_type=DocumentType.INVOICE.value,
            ocr_confidence=0.92,
            classification_confidence=0.90,
            direction_resolution=_make_direction(is_reversal=True, confidence=0.88),
            ocr_data={"amount": 300.0, "date": "2026-03-10"},
        )
        # Reversal adds a 0.60 factor, which pulls composite below auto-create
        assert result.decision != TransactionGateDecision.AUTO_CREATE


# ---------------------------------------------------------------------------
# Lohnzettel / Payslip (standardised income)
# ---------------------------------------------------------------------------

class TestLohnzettelGate:
    def test_high_confidence_lohnzettel(self):
        result = evaluate_transaction_gate(
            document_type=DocumentType.LOHNZETTEL.value,
            ocr_confidence=0.90,
            classification_confidence=0.88,
            ocr_data={"amount": 2800.0, "date": "2026-03-01"},
        )
        assert result.decision == TransactionGateDecision.AUTO_CREATE

    def test_medium_confidence_lohnzettel(self):
        result = evaluate_transaction_gate(
            document_type=DocumentType.LOHNZETTEL.value,
            ocr_confidence=0.75,
            classification_confidence=0.70,
            ocr_data={"amount": 2800.0, "date": "2026-03-01"},
        )
        assert result.decision == TransactionGateDecision.PENDING_REVIEW


# ---------------------------------------------------------------------------
# Missing fields
# ---------------------------------------------------------------------------

class TestMissingFields:
    def test_missing_date_downgrades(self):
        result = evaluate_transaction_gate(
            document_type=DocumentType.RECEIPT.value,
            ocr_confidence=0.92,
            classification_confidence=0.90,
            ocr_data={"amount": 50.0},  # no date
        )
        # Missing date adds 0.50 factor, composite becomes 0.50 < 0.65
        assert result.decision == TransactionGateDecision.MANUAL_REQUIRED
        assert "missing_date" in result.reasons

    def test_zero_amount_allowed(self):
        """Zero is a valid amount (e.g., fully discounted receipt)."""
        result = evaluate_transaction_gate(
            document_type=DocumentType.RECEIPT.value,
            ocr_confidence=0.95,
            classification_confidence=0.92,
            ocr_data={"amount": 0, "date": "2026-03-20"},
        )
        # Zero amount should NOT be treated as missing
        assert result.decision == TransactionGateDecision.AUTO_CREATE
        assert "missing_amount" not in result.reasons

    def test_empty_string_amount_blocks(self):
        result = evaluate_transaction_gate(
            document_type=DocumentType.RECEIPT.value,
            ocr_confidence=0.95,
            classification_confidence=0.92,
            ocr_data={"amount": "", "date": "2026-03-20"},
        )
        assert result.decision == TransactionGateDecision.MANUAL_REQUIRED
        assert "missing_amount" in result.reasons

    def test_none_amount_blocks(self):
        result = evaluate_transaction_gate(
            document_type=DocumentType.RECEIPT.value,
            ocr_confidence=0.95,
            classification_confidence=0.92,
            ocr_data={"amount": None, "date": "2026-03-20"},
        )
        assert result.decision == TransactionGateDecision.MANUAL_REQUIRED
        assert "missing_amount" in result.reasons

    def test_negative_amount_allowed(self):
        """Negative amounts (refunds/credit notes) should not be blocked."""
        result = evaluate_transaction_gate(
            document_type=DocumentType.RECEIPT.value,
            ocr_confidence=0.90,
            classification_confidence=0.88,
            ocr_data={"amount": -50.0, "date": "2026-03-20"},
        )
        assert "missing_amount" not in result.reasons
        assert result.should_create_transaction is True

    def test_ocr_data_none_treated_as_missing_amount(self):
        result = evaluate_transaction_gate(
            document_type=DocumentType.RECEIPT.value,
            ocr_confidence=0.95,
            classification_confidence=0.92,
            ocr_data=None,
        )
        assert result.decision == TransactionGateDecision.MANUAL_REQUIRED
        assert "missing_amount" in result.reasons


# ---------------------------------------------------------------------------
# Requires review flag
# ---------------------------------------------------------------------------

class TestRequiresReview:
    def test_classifier_requires_review_prevents_auto_create(self):
        result = evaluate_transaction_gate(
            document_type=DocumentType.RECEIPT.value,
            ocr_confidence=0.92,
            classification_confidence=0.90,
            ocr_data={"amount": 100.0, "date": "2026-03-20"},
            requires_review=True,
        )
        # requires_review caps composite at pending_threshold
        assert result.decision == TransactionGateDecision.PENDING_REVIEW
        assert "classifier_requires_review" in result.reasons

    def test_requires_review_at_exact_boundary(self):
        """requires_review caps composite AT pending_threshold, which still
        qualifies as PENDING_REVIEW (>=)."""
        result = evaluate_transaction_gate(
            document_type=DocumentType.RECEIPT.value,
            ocr_confidence=0.95,
            classification_confidence=0.95,
            ocr_data={"amount": 100.0, "date": "2026-03-20"},
            requires_review=True,
        )
        assert result.decision == TransactionGateDecision.PENDING_REVIEW
        assert result.composite_confidence == 0.70  # capped at receipt pending_threshold


# ---------------------------------------------------------------------------
# gate_enabled flag
# ---------------------------------------------------------------------------

class TestGateEnabled:
    def test_gate_enabled_false_skips_direction_penalty(self):
        """When direction resolution has gate_enabled=False, direction
        penalties should not be applied even with require_direction=True."""
        result = evaluate_transaction_gate(
            document_type=DocumentType.INVOICE.value,
            ocr_confidence=0.92,
            classification_confidence=0.91,
            direction_resolution=_make_direction(
                candidate="unknown", confidence=0.30,
            ),
            ocr_data={"amount": 1000.0, "date": "2026-03-20"},
        )
        # With gate_enabled=True (default), unknown direction degrades
        assert result.decision != TransactionGateDecision.AUTO_CREATE

        # Now with gate_enabled=False
        dir_no_gate = TransactionDirectionResolution(
            candidate="unknown",
            confidence=0.30,
            source="statement_mixed_flow",
            evidence=[],
            semantics="unknown",
            is_reversal=False,
            mode="shadow",
            gate_enabled=False,
        )
        result2 = evaluate_transaction_gate(
            document_type=DocumentType.INVOICE.value,
            ocr_confidence=0.92,
            classification_confidence=0.91,
            direction_resolution=dir_no_gate,
            ocr_data={"amount": 1000.0, "date": "2026-03-20"},
        )
        # gate_enabled=False skips direction penalty
        assert "direction_unknown" not in result2.reasons
        assert "direction_not_resolved" not in result2.reasons
        assert result2.decision == TransactionGateDecision.AUTO_CREATE

    def test_gate_enabled_false_skips_semantic_blocking(self):
        """Proforma semantics should NOT block when gate_enabled=False."""
        dir_no_gate = TransactionDirectionResolution(
            candidate="expense",
            confidence=0.94,
            source="party_name_match",
            evidence=[],
            semantics="proforma",
            is_reversal=False,
            mode="shadow",
            gate_enabled=False,
        )
        result = evaluate_transaction_gate(
            document_type=DocumentType.INVOICE.value,
            ocr_confidence=0.92,
            classification_confidence=0.91,
            direction_resolution=dir_no_gate,
            ocr_data={"amount": 5000.0, "date": "2026-03-20"},
        )
        assert "blocked_semantics:proforma" not in result.reasons
        assert result.decision == TransactionGateDecision.AUTO_CREATE


# ---------------------------------------------------------------------------
# Default profile (unknown document types)
# ---------------------------------------------------------------------------

class TestDefaultProfile:
    def test_unknown_doc_type_uses_default(self):
        result = evaluate_transaction_gate(
            document_type="some_unknown_type",
            ocr_confidence=0.92,
            classification_confidence=0.92,
            direction_resolution=_make_direction(confidence=0.94),
            ocr_data={"amount": 100.0, "date": "2026-03-20"},
        )
        assert result.decision == TransactionGateDecision.AUTO_CREATE
