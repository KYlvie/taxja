from types import SimpleNamespace

from app.services.final_transaction_type_service import (
    materialize_final_transaction_type,
    resolve_final_transaction_type,
)


def test_resolve_final_transaction_type_prefers_linked_transaction():
    transaction = SimpleNamespace(type="income")

    resolved, source = resolve_final_transaction_type(
        ocr_result={
            "transaction_suggestion": {"transaction_type": "expense"},
            "document_transaction_direction": "expense",
        },
        transaction=transaction,
    )

    assert resolved == "income"
    assert source == "linked_transaction"


def test_resolve_final_transaction_type_prefers_suggestion_over_legacy_direction():
    resolved, source = resolve_final_transaction_type(
        ocr_result={
            "transaction_suggestion": {"transaction_type": "income"},
            "document_transaction_direction": "expense",
        },
    )

    assert resolved == "income"
    assert source == "transaction_suggestion"


def test_materialize_final_transaction_type_falls_back_to_legacy_direction():
    ocr_result = {
        "document_transaction_direction": "expense",
    }

    resolved = materialize_final_transaction_type(ocr_result=ocr_result)

    assert resolved == "expense"
    assert ocr_result["final_transaction_type"] == "expense"
    assert ocr_result["final_transaction_type_source"] == "document_transaction_direction"
