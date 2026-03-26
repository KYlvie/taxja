from decimal import Decimal

from app.models.transaction import ExpenseCategory, TransactionType
from app.models.transaction_line_item import LineItemPostingType
from app.services.posting_line_utils import normalize_line_item_payloads


def test_normalize_line_item_payloads_derives_unit_amount_from_total_and_quantity():
    line_items = normalize_line_item_payloads(
        transaction_type=TransactionType.EXPENSE,
        transaction_amount="18,00",
        description="Office supplies",
        expense_category=ExpenseCategory.OTHER,
        line_items=[
            {
                "description": "Printer paper",
                "total_price": "18,00",
                "quantity": "2 Stück",
                "vat_rate": "20 %",
                "is_deductible": "ja",
                "currency": "EUR",
            }
        ],
    )

    assert len(line_items) == 1
    line = line_items[0]
    assert line["amount"] == Decimal("9.00")
    assert line["quantity"] == 2
    assert line["vat_rate"] == Decimal("0.20")
    assert line["is_deductible"] is True
    assert line["currency"] == "EUR"


def test_normalize_line_item_payloads_keeps_fractional_quantities_safe():
    line_items = normalize_line_item_payloads(
        transaction_type=TransactionType.EXPENSE,
        transaction_amount="150,00",
        description="Consulting",
        expense_category=ExpenseCategory.OTHER,
        line_items=[
            {
                "description": "Consulting hours",
                "total_price": "150,00",
                "quantity": "1,5 Std",
                "posting_type": "expense",
                "is_deductible": "yes",
            }
        ],
    )

    assert len(line_items) == 1
    line = line_items[0]
    assert line["quantity"] == 1
    assert line["amount"] == Decimal("150.00")
    assert line["posting_type"] == LineItemPostingType.EXPENSE


def test_normalize_line_item_payloads_extracts_semantic_flags():
    line_items = normalize_line_item_payloads(
        transaction_type=TransactionType.EXPENSE,
        transaction_amount="50,00",
        description="Credit note",
        expense_category=ExpenseCategory.OTHER,
        line_items=[
            {
                "description": "Refund / Gutschrift",
                "amount": "50,00",
                "status": "storniert",
                "quantity": 1,
            }
        ],
    )

    assert line_items[0]["semantic_flags"] == ["cancelled", "credit_note", "refund"]
