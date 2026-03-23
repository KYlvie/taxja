from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

from app.models.transaction import TransactionType
from app.models.transaction_line_item import LineItemPostingType
from app.models.user import User, UserType
from app.services.ea_report_service import generate_ea_report
from app.services.posting_line_utils import recoverable_input_vat_for_transaction
from app.services.u1_form_service import generate_u1_form_data
from app.services.uva_service import generate_uva_data


def _make_user(**overrides):
    user = Mock(spec=User)
    user.id = overrides.get("id", 1)
    user.name = overrides.get("name", "Max Mustermann")
    user.tax_number = overrides.get("tax_number", "12-345/6789")
    user.vat_number = overrides.get("vat_number", "ATU12345678")
    user.user_type = overrides.get("user_type", UserType.SELF_EMPLOYED)
    return user


def _mock_db(transactions):
    db = Mock()
    q = Mock()
    db.query.return_value = q
    q.filter.return_value = q
    q.order_by.return_value = q
    q.all.return_value = transactions
    return db


def _line(
    *,
    posting_type,
    amount,
    category="equipment",
    vat_amount=None,
    vat_recoverable_amount=Decimal("0.00"),
    sort_order=0,
):
    return SimpleNamespace(
        description="Asset line",
        amount=Decimal(str(amount)),
        quantity=1,
        posting_type=posting_type,
        allocation_source="vat_policy",
        category=category,
        is_deductible=False,
        deduction_reason=None,
        vat_rate=Decimal("0.20") if vat_amount is not None else None,
        vat_amount=(Decimal(str(vat_amount)) if vat_amount is not None else None),
        vat_recoverable_amount=Decimal(str(vat_recoverable_amount)),
        rule_bucket=None,
        sort_order=sort_order,
    )


def _asset_acquisition_transaction(
    *,
    amount,
    vat_amount,
    vat_recoverable_amount_total,
    line_items,
):
    return SimpleNamespace(
        id=101,
        type=TransactionType.ASSET_ACQUISITION,
        amount=Decimal(str(amount)),
        vat_amount=Decimal(str(vat_amount)),
        vat_recoverable_amount_total=Decimal(str(vat_recoverable_amount_total)),
        line_items=line_items,
        transaction_date=date(2026, 3, 18),
        description="Tesla Model Y",
        expense_category=None,
        income_category=None,
        is_deductible=False,
        property_id=None,
        document_id=None,
        vat_type=None,
    )


def test_recoverable_input_vat_helper_keeps_legacy_expense_fallback():
    legacy_expense = SimpleNamespace(
        type=TransactionType.EXPENSE,
        vat_amount=Decimal("20.00"),
        vat_recoverable_amount_total=Decimal("0.00"),
        line_items=[],
    )

    assert recoverable_input_vat_for_transaction(legacy_expense) == Decimal("20.00")


def test_u1_counts_recoverable_vat_from_asset_acquisition_lines():
    tx = _asset_acquisition_transaction(
        amount=Decimal("60000.00"),
        vat_amount=Decimal("10000.00"),
        vat_recoverable_amount_total=Decimal("6667.00"),
        line_items=[
            _line(
                posting_type=LineItemPostingType.ASSET_ACQUISITION,
                amount=Decimal("53333.00"),
                vat_amount=Decimal("10000.00"),
                vat_recoverable_amount=Decimal("6667.00"),
            )
        ],
    )

    result = generate_u1_form_data(_mock_db([tx]), _make_user(), 2026)

    assert result["summary"]["vorsteuer"] == 6667.0


def test_uva_counts_recoverable_vat_from_asset_acquisition_lines():
    tx = _asset_acquisition_transaction(
        amount=Decimal("60000.00"),
        vat_amount=Decimal("10000.00"),
        vat_recoverable_amount_total=Decimal("6667.00"),
        line_items=[
            _line(
                posting_type=LineItemPostingType.ASSET_ACQUISITION,
                amount=Decimal("53333.00"),
                vat_amount=Decimal("10000.00"),
                vat_recoverable_amount=Decimal("6667.00"),
            )
        ],
    )

    result = generate_uva_data(_mock_db([tx]), _make_user(), 2026, "monthly", 3)

    assert result["summary"]["vorsteuer"] == 6667.0
    assert result["summary"]["total_vorsteuer"] == 6667.0


def test_ea_report_keeps_asset_acquisition_out_of_expenses_but_counts_recoverable_vat():
    tx = _asset_acquisition_transaction(
        amount=Decimal("1499.00"),
        vat_amount=Decimal("249.83"),
        vat_recoverable_amount_total=Decimal("199.86"),
        line_items=[
            _line(
                posting_type=LineItemPostingType.ASSET_ACQUISITION,
                amount=Decimal("999.34"),
                vat_amount=Decimal("199.86"),
                vat_recoverable_amount=Decimal("199.86"),
                sort_order=0,
            ),
            _line(
                posting_type=LineItemPostingType.PRIVATE_USE,
                amount=Decimal("299.80"),
                vat_amount=Decimal("49.97"),
                vat_recoverable_amount=Decimal("0.00"),
                sort_order=1,
            ),
        ],
    )

    result = generate_ea_report(_mock_db([tx]), _make_user(), 2026)

    assert result["summary"]["total_expenses"] == 0.0
    assert result["summary"]["total_deductible"] == 0.0
    assert result["summary"]["total_vat_paid"] == 199.86
