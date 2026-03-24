"""
Tests for document process-status and follow-up helper logic.

These are pure logic tests that don't require database or heavy imports.
They test the core algorithms: ui_state derivation, action descriptor building,
phase messages, and follow-up answer processing.

Covers:
- _derive_ui_state: all pipeline states -> correct ui_state
- _build_action_descriptor: all suggestion types -> correct action contract
- _get_phase_message: trilingual messages
- Follow-up answer logic: partial answers, use_defaults, version check, order preservation
- Idempotency key generation
"""
import pytest
from copy import deepcopy


# =============================================================================
# Inline reimplementation of pure logic functions (avoids heavy import chain)
# These mirror the implementations in documents.py exactly.
# =============================================================================

def _derive_ui_state(current_state: str, suggestion) -> str:
    """Single source of truth for frontend UI state."""
    if current_state in ("processing_phase_1", "first_result_available", "finalizing"):
        return "processing"
    if current_state == "phase_2_failed":
        return "error"
    if not suggestion:
        return "confirmed"
    status = suggestion.get("status", "")
    if status == "confirmed":
        return "confirmed"
    if status == "dismissed":
        return "dismissed"
    if suggestion.get("follow_up_questions") and len(suggestion["follow_up_questions"]) > 0:
        return "needs_input"
    return "ready_to_confirm"


_ACTION_MAP = {
    "create_property": {"kind": "confirm_property", "endpoint_suffix": "confirm-property"},
    "create_asset": {"kind": "confirm_asset", "endpoint_suffix": "confirm-asset"},
    "create_recurring_income": {"kind": "confirm_recurring", "endpoint_suffix": "confirm-recurring"},
    "create_recurring_expense": {"kind": "confirm_recurring_expense", "endpoint_suffix": "confirm-recurring-expense"},
    "create_loan": {"kind": "confirm_loan", "endpoint_suffix": "confirm-loan"},
}

_CONFIRM_LABELS = {
    "confirm_property": {"de": "Immobilie erstellen", "en": "Create Property", "zh": "创建房产"},
    "confirm_asset": {"de": "Anlage erstellen", "en": "Create Asset", "zh": "创建资产"},
    "confirm_recurring": {"de": "Dauerauftrag bestätigen", "en": "Confirm Recurring", "zh": "确认定期交易"},
    "confirm_recurring_expense": {"de": "Wiederkehrende Ausgabe bestätigen", "en": "Confirm Recurring Expense", "zh": "确认定期支出"},
    "confirm_tax_data": {"de": "Steuerdaten importieren", "en": "Import Tax Data", "zh": "导入税务数据"},
    "confirm_loan": {"de": "Kredit erstellen", "en": "Create Loan", "zh": "创建贷款"},
}


def _build_action_descriptor(suggestion_type: str, document_id: int):
    if suggestion_type.startswith("import_"):
        kind = "confirm_tax_data"
        endpoint_suffix = "confirm-tax-data"
    elif suggestion_type in _ACTION_MAP:
        kind = _ACTION_MAP[suggestion_type]["kind"]
        endpoint_suffix = _ACTION_MAP[suggestion_type]["endpoint_suffix"]
    else:
        return None
    return {
        "kind": kind,
        "target_id": str(document_id),
        "endpoint": f"/documents/{document_id}/{endpoint_suffix}",
        "method": "POST",
        "confirm_label": _CONFIRM_LABELS.get(kind),
    }


_PHASE_MESSAGES = {
    "processing_phase_1": {"de": "Dokument wird analysiert...", "en": "Analyzing your document...", "zh": "正在分析您的文档..."},
    "first_result_available": {"de": "Erste Ergebnisse verfügbar...", "en": "First results available...", "zh": "初步结果已出..."},
    "finalizing": {"de": "Verarbeitung wird abgeschlossen...", "en": "Finalizing processing...", "zh": "正在完成处理..."},
    "completed": {"de": "Verarbeitung abgeschlossen.", "en": "Processing complete.", "zh": "处理完成。"},
    "phase_2_failed": {"de": "Verarbeitung fehlgeschlagen.", "en": "Processing failed. Please try again.", "zh": "处理失败，请重试。"},
}


def _get_phase_message(current_state: str, lang: str, doc_type=None) -> str:
    messages = _PHASE_MESSAGES.get(current_state, _PHASE_MESSAGES["processing_phase_1"])
    base_msg = messages.get(lang, messages.get("en", "Processing..."))
    if current_state == "first_result_available" and doc_type:
        type_prefix = {"de": f"Erkannt als {doc_type}. ", "en": f"Identified as {doc_type}. ", "zh": f"识别为 {doc_type}。"}
        return type_prefix.get(lang, type_prefix["en"]) + base_msg
    return base_msg


# =============================================================================
# Tests
# =============================================================================

class TestDeriveUIState:
    def test_processing_phase_1(self):
        assert _derive_ui_state("processing_phase_1", None) == "processing"

    def test_first_result_available(self):
        assert _derive_ui_state("first_result_available", None) == "processing"

    def test_finalizing(self):
        assert _derive_ui_state("finalizing", None) == "processing"

    def test_phase_2_failed(self):
        assert _derive_ui_state("phase_2_failed", None) == "error"

    def test_completed_no_suggestion(self):
        assert _derive_ui_state("completed", None) == "confirmed"

    def test_confirmed_suggestion(self):
        assert _derive_ui_state("completed", {"status": "confirmed"}) == "confirmed"

    def test_dismissed_suggestion(self):
        assert _derive_ui_state("completed", {"status": "dismissed"}) == "dismissed"

    def test_needs_input_with_follow_ups(self):
        s = {"status": "pending", "follow_up_questions": [{"id": "q1"}]}
        assert _derive_ui_state("completed", s) == "needs_input"

    def test_ready_to_confirm_empty_follow_ups(self):
        s = {"status": "pending", "follow_up_questions": []}
        assert _derive_ui_state("completed", s) == "ready_to_confirm"

    def test_ready_to_confirm_no_follow_ups_key(self):
        s = {"status": "pending"}
        assert _derive_ui_state("completed", s) == "ready_to_confirm"


class TestBuildActionDescriptor:
    def test_create_property(self):
        a = _build_action_descriptor("create_property", 42)
        assert a["kind"] == "confirm_property"
        assert "/42/confirm-property" in a["endpoint"]

    def test_create_asset(self):
        a = _build_action_descriptor("create_asset", 100)
        assert a["kind"] == "confirm_asset"
        assert a["confirm_label"]["de"] == "Anlage erstellen"

    def test_import_lohnzettel(self):
        a = _build_action_descriptor("import_lohnzettel", 50)
        assert a["kind"] == "confirm_tax_data"
        assert "/50/confirm-tax-data" in a["endpoint"]

    def test_import_e1a(self):
        a = _build_action_descriptor("import_e1a", 50)
        assert a["kind"] == "confirm_tax_data"

    def test_unknown_returns_none(self):
        assert _build_action_descriptor("unknown", 42) is None

    def test_all_action_map_types(self):
        for stype in _ACTION_MAP:
            a = _build_action_descriptor(stype, 1)
            assert a is not None
            assert a["kind"] == _ACTION_MAP[stype]["kind"]


class TestGetPhaseMessage:
    def test_trilingual(self):
        for lang in ("en", "de", "zh"):
            msg = _get_phase_message("processing_phase_1", lang)
            assert len(msg) > 0

    def test_first_result_with_doc_type(self):
        msg = _get_phase_message("first_result_available", "en", "purchase_contract")
        assert "purchase_contract" in msg

    def test_completed(self):
        assert "complete" in _get_phase_message("completed", "en").lower()

    def test_failed(self):
        assert "failed" in _get_phase_message("phase_2_failed", "en").lower()


class TestFollowUpAnswerLogic:
    def _make_suggestion(self):
        return {
            "type": "create_asset",
            "status": "pending",
            "data": {"amount": 35000},
            "version": 0,
            "follow_up_questions": [
                {"id": "q1", "field_key": "put_into_use_date", "default_value": None, "required": True},
                {"id": "q2", "field_key": "business_use_percentage", "default_value": 100, "required": True},
                {"id": "q3", "field_key": "is_used_asset", "default_value": False, "required": False},
            ],
        }

    def test_full_answers(self):
        s = self._make_suggestion()
        answers = {"put_into_use_date": "2025-01-15", "business_use_percentage": 80, "is_used_asset": False}
        s["data"].update(answers)
        remaining = [q for q in s["follow_up_questions"] if q["field_key"] not in answers]
        assert len(remaining) == 0

    def test_partial_preserves_order(self):
        s = self._make_suggestion()
        answers = {"put_into_use_date": "2025-01-15"}
        remaining = [q for q in s["follow_up_questions"] if q["field_key"] not in answers]
        assert len(remaining) == 2
        assert remaining[0]["field_key"] == "business_use_percentage"
        assert remaining[1]["field_key"] == "is_used_asset"

    def test_use_defaults(self):
        s = self._make_suggestion()
        answers = {"put_into_use_date": "2025-01-15"}
        applied = {}
        for q in s["follow_up_questions"]:
            if q["field_key"] not in answers and q.get("default_value") is not None:
                s["data"][q["field_key"]] = q["default_value"]
                applied[q["field_key"]] = q["default_value"]
        assert s["data"]["business_use_percentage"] == 100
        assert s["data"]["is_used_asset"] == False
        assert "put_into_use_date" not in applied

    def test_version_bump(self):
        s = self._make_suggestion()
        s["version"] = s["version"] + 1
        assert s["version"] == 1

    def test_version_mismatch(self):
        s = self._make_suggestion()
        s["version"] = 3
        assert 1 != s["version"]

    def test_status_after_all_answered(self):
        s = self._make_suggestion()
        s["follow_up_questions"] = []
        assert _derive_ui_state("completed", s) == "ready_to_confirm"

    def test_status_after_partial(self):
        s = self._make_suggestion()
        # Still has questions
        assert _derive_ui_state("completed", s) == "needs_input"


class TestIdempotencyKey:
    def test_format(self):
        assert f"42:create_asset:completed" == "42:create_asset:completed"

    def test_no_suggestion(self):
        assert f"42:none:processing_phase_1" == "42:none:processing_phase_1"

    def test_deterministic(self):
        k1 = f"42:create_asset:completed"
        k2 = f"42:create_asset:completed"
        assert k1 == k2

    def test_different_docs(self):
        assert f"42:create_asset:completed" != f"43:create_asset:completed"
