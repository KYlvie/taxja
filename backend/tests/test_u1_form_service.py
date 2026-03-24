"""Tests for U1 Form Service — Umsatzsteuererklaerung (Annual VAT Return)"""
import pytest
from decimal import Decimal
from datetime import date
from unittest.mock import Mock, MagicMock, patch

from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.services.u1_form_service import (
    _classify_vat_rate,
    generate_u1_form_data,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(**overrides):
    user = Mock(spec=User)
    user.id = overrides.get("id", 1)
    user.name = overrides.get("name", "Max Mustermann")
    user.tax_number = overrides.get("tax_number", "12-345/6789")
    user.vat_number = overrides.get("vat_number", "ATU12345678")
    return user


def _make_transaction(
    *,
    tx_type: TransactionType,
    amount: Decimal,
    vat_amount: Decimal = Decimal("0"),
):
    t = Mock(spec=Transaction)
    t.type = tx_type
    t.amount = amount
    t.vat_amount = vat_amount
    return t


def _mock_db(transactions):
    """Return a Mock(spec=Session) whose query chain yields *transactions*."""
    db = Mock()
    q = Mock()
    db.query.return_value = q
    q.filter.return_value = q
    q.all.return_value = transactions
    return db


def _field_by_kz(fields, kz):
    """Return the field dict for a given Kennzahl."""
    for f in fields:
        if f["kz"] == kz:
            return f
    raise KeyError(f"KZ {kz} not found")


# ===========================================================================
# _classify_vat_rate
# ===========================================================================

class TestClassifyVatRate:
    """Unit tests for the VAT-rate classification helper."""

    def test_20_percent(self):
        # 20% VAT: vat/net >= 0.18
        assert _classify_vat_rate(Decimal("20"), Decimal("100")) == "20"

    def test_13_percent(self):
        assert _classify_vat_rate(Decimal("13"), Decimal("100")) == "13"

    def test_10_percent(self):
        assert _classify_vat_rate(Decimal("10"), Decimal("100")) == "10"

    def test_exempt(self):
        # ratio <= 0.01 -> exempt
        assert _classify_vat_rate(Decimal("0"), Decimal("100")) == "exempt"
        assert _classify_vat_rate(Decimal("0.50"), Decimal("100")) == "exempt"

    def test_zero_net_returns_unknown(self):
        assert _classify_vat_rate(Decimal("5"), Decimal("0")) == "unknown"

    def test_negative_net_returns_unknown(self):
        assert _classify_vat_rate(Decimal("5"), Decimal("-10")) == "unknown"

    def test_borderline_20_percent(self):
        # Exactly 0.18 ratio -> should classify as 20%
        assert _classify_vat_rate(Decimal("18"), Decimal("100")) == "20"

    def test_borderline_13_percent(self):
        # Exactly 0.11 ratio -> should classify as 13%
        assert _classify_vat_rate(Decimal("11"), Decimal("100")) == "13"

    def test_borderline_10_percent(self):
        # Exactly 0.08 ratio -> should classify as 10%
        assert _classify_vat_rate(Decimal("8"), Decimal("100")) == "10"

    def test_gap_between_exempt_and_10(self):
        # ratio = 0.05 — above exempt (<=0.01) but below 10% (>=0.08)
        assert _classify_vat_rate(Decimal("5"), Decimal("100")) == "unknown"


# ===========================================================================
# Revenue classification by VAT rate
# ===========================================================================

class TestRevenueClassification:
    """Revenue split into 20%, 13%, 10%, and exempt buckets."""

    def test_single_income_20_percent(self):
        # gross 120 = net 100 + VAT 20 -> 20% bucket
        txns = [_make_transaction(
            tx_type=TransactionType.INCOME,
            amount=Decimal("120"),
            vat_amount=Decimal("20"),
        )]
        result = generate_u1_form_data(_mock_db(txns), _make_user(), 2025)

        assert result["summary"]["revenue_20"] == 100.0
        assert result["summary"]["vat_20"] == 20.0
        assert result["summary"]["revenue_10"] == 0.0
        assert result["summary"]["revenue_13"] == 0.0
        assert result["summary"]["revenue_exempt"] == 0.0

    def test_single_income_10_percent(self):
        # gross 110 = net 100 + VAT 10
        txns = [_make_transaction(
            tx_type=TransactionType.INCOME,
            amount=Decimal("110"),
            vat_amount=Decimal("10"),
        )]
        result = generate_u1_form_data(_mock_db(txns), _make_user(), 2025)

        assert result["summary"]["revenue_10"] == 100.0
        assert result["summary"]["vat_10"] == 10.0

    def test_single_income_13_percent(self):
        # gross 113 = net 100 + VAT 13
        txns = [_make_transaction(
            tx_type=TransactionType.INCOME,
            amount=Decimal("113"),
            vat_amount=Decimal("13"),
        )]
        result = generate_u1_form_data(_mock_db(txns), _make_user(), 2025)

        assert result["summary"]["revenue_13"] == 100.0
        assert result["summary"]["vat_13"] == 13.0

    def test_exempt_income_no_vat(self):
        txns = [_make_transaction(
            tx_type=TransactionType.INCOME,
            amount=Decimal("500"),
            vat_amount=Decimal("0"),
        )]
        result = generate_u1_form_data(_mock_db(txns), _make_user(), 2025)

        assert result["summary"]["revenue_exempt"] == 500.0
        assert result["summary"]["revenue_20"] == 0.0

    def test_multiple_rates(self):
        """Mix of 20%, 10%, and exempt income."""
        txns = [
            _make_transaction(tx_type=TransactionType.INCOME, amount=Decimal("120"), vat_amount=Decimal("20")),
            _make_transaction(tx_type=TransactionType.INCOME, amount=Decimal("110"), vat_amount=Decimal("10")),
            _make_transaction(tx_type=TransactionType.INCOME, amount=Decimal("200"), vat_amount=Decimal("0")),
        ]
        result = generate_u1_form_data(_mock_db(txns), _make_user(), 2025)

        assert result["summary"]["revenue_20"] == 100.0
        assert result["summary"]["revenue_10"] == 100.0
        assert result["summary"]["revenue_exempt"] == 200.0
        assert result["summary"]["total_revenue"] == 400.0


# ===========================================================================
# Vorsteuer (Input VAT) aggregation
# ===========================================================================

class TestVorsteuer:
    """Vorsteuer from expense transactions."""

    def test_single_expense_with_vat(self):
        txns = [_make_transaction(
            tx_type=TransactionType.EXPENSE,
            amount=Decimal("60"),
            vat_amount=Decimal("10"),
        )]
        result = generate_u1_form_data(_mock_db(txns), _make_user(), 2025)

        assert result["summary"]["vorsteuer"] == 10.0

    def test_multiple_expenses(self):
        txns = [
            _make_transaction(tx_type=TransactionType.EXPENSE, amount=Decimal("60"), vat_amount=Decimal("10")),
            _make_transaction(tx_type=TransactionType.EXPENSE, amount=Decimal("120"), vat_amount=Decimal("20")),
        ]
        result = generate_u1_form_data(_mock_db(txns), _make_user(), 2025)

        assert result["summary"]["vorsteuer"] == 30.0

    def test_expense_without_vat_not_counted(self):
        txns = [_make_transaction(
            tx_type=TransactionType.EXPENSE,
            amount=Decimal("100"),
            vat_amount=Decimal("0"),
        )]
        result = generate_u1_form_data(_mock_db(txns), _make_user(), 2025)

        assert result["summary"]["vorsteuer"] == 0.0

    def test_income_vat_not_counted_as_vorsteuer(self):
        """Income VAT goes into vat_20/10/13, not vorsteuer."""
        txns = [_make_transaction(
            tx_type=TransactionType.INCOME,
            amount=Decimal("120"),
            vat_amount=Decimal("20"),
        )]
        result = generate_u1_form_data(_mock_db(txns), _make_user(), 2025)

        assert result["summary"]["vorsteuer"] == 0.0
        assert result["summary"]["vat_20"] == 20.0


# ===========================================================================
# Zahllast calculation
# ===========================================================================

class TestZahllast:
    """Zahllast = total_vat - vorsteuer."""

    def test_positive_zahllast(self):
        """More output VAT than input VAT -> owe money."""
        txns = [
            _make_transaction(tx_type=TransactionType.INCOME, amount=Decimal("120"), vat_amount=Decimal("20")),
            _make_transaction(tx_type=TransactionType.EXPENSE, amount=Decimal("60"), vat_amount=Decimal("5")),
        ]
        result = generate_u1_form_data(_mock_db(txns), _make_user(), 2025)

        assert result["summary"]["total_vat"] == 20.0
        assert result["summary"]["vorsteuer"] == 5.0
        assert result["summary"]["zahllast"] == 15.0

    def test_negative_zahllast_refund(self):
        """More input VAT than output VAT -> refund."""
        txns = [
            _make_transaction(tx_type=TransactionType.INCOME, amount=Decimal("110"), vat_amount=Decimal("10")),
            _make_transaction(tx_type=TransactionType.EXPENSE, amount=Decimal("240"), vat_amount=Decimal("40")),
        ]
        result = generate_u1_form_data(_mock_db(txns), _make_user(), 2025)

        assert result["summary"]["zahllast"] == -30.0

    def test_zero_zahllast(self):
        txns = [
            _make_transaction(tx_type=TransactionType.INCOME, amount=Decimal("120"), vat_amount=Decimal("20")),
            _make_transaction(tx_type=TransactionType.EXPENSE, amount=Decimal("120"), vat_amount=Decimal("20")),
        ]
        result = generate_u1_form_data(_mock_db(txns), _make_user(), 2025)

        assert result["summary"]["zahllast"] == 0.0


# ===========================================================================
# Zero transactions
# ===========================================================================

class TestZeroTransactions:
    """No transactions for the year."""

    def test_empty_returns_all_zeros(self):
        result = generate_u1_form_data(_mock_db([]), _make_user(), 2025)

        s = result["summary"]
        assert s["total_revenue"] == 0.0
        assert s["total_vat"] == 0.0
        assert s["vorsteuer"] == 0.0
        assert s["zahllast"] == 0.0

    def test_form_metadata_present(self):
        result = generate_u1_form_data(_mock_db([]), _make_user(), 2025)

        assert result["form_type"] == "U1"
        assert result["tax_year"] == 2025
        assert result["user_name"] == "Max Mustermann"
        assert result["tax_number"] == "12-345/6789"
        assert len(result["fields"]) > 0


# ===========================================================================
# Mixed income/expense transactions
# ===========================================================================

class TestMixedTransactions:
    """Realistic scenarios with both income and expense at different rates."""

    def test_full_year_scenario(self):
        """Multiple incomes at different rates + multiple expenses."""
        txns = [
            # Income 20%: gross 1200, VAT 200, net 1000
            _make_transaction(tx_type=TransactionType.INCOME, amount=Decimal("1200"), vat_amount=Decimal("200")),
            # Income 10%: gross 550, VAT 50, net 500
            _make_transaction(tx_type=TransactionType.INCOME, amount=Decimal("550"), vat_amount=Decimal("50")),
            # Income exempt
            _make_transaction(tx_type=TransactionType.INCOME, amount=Decimal("300"), vat_amount=Decimal("0")),
            # Expense with VAT
            _make_transaction(tx_type=TransactionType.EXPENSE, amount=Decimal("600"), vat_amount=Decimal("100")),
            # Expense without VAT (no vorsteuer)
            _make_transaction(tx_type=TransactionType.EXPENSE, amount=Decimal("200"), vat_amount=Decimal("0")),
        ]
        result = generate_u1_form_data(_mock_db(txns), _make_user(), 2025)

        s = result["summary"]
        assert s["revenue_20"] == 1000.0
        assert s["vat_20"] == 200.0
        assert s["revenue_10"] == 500.0
        assert s["vat_10"] == 50.0
        assert s["revenue_exempt"] == 300.0
        assert s["total_vat"] == 250.0
        assert s["vorsteuer"] == 100.0
        assert s["zahllast"] == 150.0
        assert s["total_revenue"] == 1800.0

    def test_fields_kz_mapping(self):
        """Kennzahlen in the fields list match the summary values."""
        txns = [
            _make_transaction(tx_type=TransactionType.INCOME, amount=Decimal("120"), vat_amount=Decimal("20")),
            _make_transaction(tx_type=TransactionType.EXPENSE, amount=Decimal("60"), vat_amount=Decimal("10")),
        ]
        result = generate_u1_form_data(_mock_db(txns), _make_user(), 2025)
        fields = result["fields"]

        assert _field_by_kz(fields, "000")["value"] == 100.0   # revenue 20%
        assert _field_by_kz(fields, "022")["value"] == 20.0    # VAT 20%
        assert _field_by_kz(fields, "060")["value"] == 10.0    # Vorsteuer
        assert _field_by_kz(fields, "095")["value"] == 10.0    # Zahllast

    def test_zahllast_equals_kz095(self):
        """KZ 095 field must equal the summary zahllast."""
        txns = [
            _make_transaction(tx_type=TransactionType.INCOME, amount=Decimal("113"), vat_amount=Decimal("13")),
        ]
        result = generate_u1_form_data(_mock_db(txns), _make_user(), 2025)

        kz095 = _field_by_kz(result["fields"], "095")["value"]
        assert kz095 == result["summary"]["zahllast"]
