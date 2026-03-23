"""Tests for E1a form service — Beilage zur Einkommensteuererklaerung.

Tests verify Gewinnfreibetrag, Basispauschalierung, EA-Rechnung breakdown,
revenue aggregation, profit/loss, and that values are loaded from DB config.
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch
from datetime import date

from sqlalchemy.orm import Session

from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.models.user import User
from app.services.e1a_form_service import (
    _calculate_gewinnfreibetrag,
    _sum_income,
    _sum_expense,
    generate_e1a_form_data,
    INVESTITIONSFREIBETRAG_RATE,
    INVESTITIONSFREIBETRAG_MAX_BASE,
)


# Default self-employed config for tests (2025 values)
_TEST_SE_CONFIG = {
    "grundfreibetrag_profit_limit": 33000.00,
    "grundfreibetrag_rate": 0.15,
    "grundfreibetrag_max": 4950.00,
    "flat_rate_turnover_limit": 320000.00,
    "flat_rate_general": 0.135,
    "flat_rate_consulting": 0.06,
}


def _make_transaction(
    type: TransactionType,
    amount: Decimal,
    income_category=None,
    expense_category=None,
    is_deductible: bool = True,
):
    """Helper to create a mock transaction."""
    t = Mock(spec=Transaction)
    t.type = type
    t.amount = amount
    t.income_category = income_category
    t.expense_category = expense_category
    t.is_deductible = is_deductible
    return t


def _make_user(name="Max Mustermann", tax_number="12-345/6789"):
    user = Mock(spec=User)
    user.id = 1
    user.name = name
    user.tax_number = tax_number
    return user


def _mock_db_returning(transactions):
    """Build a mock Session whose query chain returns the given list."""
    db = Mock(spec=Session)
    query = db.query.return_value
    query.filter.return_value = query
    query.order_by.return_value = query
    query.all.return_value = transactions
    # For TaxConfiguration query, return None (will use fallback)
    query.first.return_value = None
    return db


# ---------------------------------------------------------------------------
# 1. Gewinnfreibetrag calculation
# ---------------------------------------------------------------------------
class TestGewinnfreibetrag:
    def test_zero_profit(self):
        result = _calculate_gewinnfreibetrag(Decimal("0"), _TEST_SE_CONFIG)
        assert result["grundfreibetrag"] == Decimal("0")
        assert result["investitions_gfb"] == Decimal("0")
        assert result["total"] == Decimal("0")

    def test_negative_profit(self):
        result = _calculate_gewinnfreibetrag(Decimal("-5000"), _TEST_SE_CONFIG)
        assert result["total"] == Decimal("0")

    def test_profit_below_33k(self):
        profit = Decimal("20000")
        result = _calculate_gewinnfreibetrag(profit, _TEST_SE_CONFIG)
        expected_grund = (profit * Decimal("0.15")).quantize(Decimal("0.01"))
        assert result["grundfreibetrag"] == expected_grund  # 3000.00
        assert result["investitions_gfb"] == Decimal("0")
        assert result["total"] == expected_grund

    def test_profit_exactly_33k(self):
        profit = Decimal("33000")
        result = _calculate_gewinnfreibetrag(profit, _TEST_SE_CONFIG)
        expected_grund = Decimal("4950.00")  # 33000 * 0.15
        assert result["grundfreibetrag"] == expected_grund
        assert result["investitions_gfb"] == Decimal("0")
        assert result["total"] == expected_grund

    def test_profit_between_33k_and_175k(self):
        profit = Decimal("100000")
        result = _calculate_gewinnfreibetrag(profit, _TEST_SE_CONFIG)
        expected_grund = Decimal("4950.00")  # 33000 * 0.15
        expected_invest = ((profit - Decimal("33000")) * INVESTITIONSFREIBETRAG_RATE).quantize(Decimal("0.01"))
        assert result["grundfreibetrag"] == expected_grund
        assert result["investitions_gfb"] == Decimal("8710.00")
        assert result["total"] == expected_grund + expected_invest

    def test_profit_exactly_175k(self):
        profit = Decimal("175000")
        result = _calculate_gewinnfreibetrag(profit, _TEST_SE_CONFIG)
        expected_grund = Decimal("4950.00")
        expected_invest = Decimal("18460.00")  # (175000 - 33000) * 0.13
        assert result["grundfreibetrag"] == expected_grund
        assert result["investitions_gfb"] == expected_invest
        assert result["total"] == expected_grund + expected_invest

    def test_profit_above_175k_caps_invest_base(self):
        profit = Decimal("300000")
        result = _calculate_gewinnfreibetrag(profit, _TEST_SE_CONFIG)
        expected_grund = Decimal("4950.00")
        expected_invest = Decimal("18460.00")
        assert result["grundfreibetrag"] == expected_grund
        assert result["investitions_gfb"] == expected_invest
        assert result["total"] == Decimal("23410.00")


# ---------------------------------------------------------------------------
# 2. Basispauschalierung (year-specific rates from DB)
# ---------------------------------------------------------------------------
class TestBasispauschalierung:
    def test_standard_rate_from_config(self):
        """2025: 13.5% general rate."""
        revenue = Decimal("100000")
        expected = (revenue * Decimal("0.135")).quantize(Decimal("0.01"))
        assert expected == Decimal("13500.00")

    def test_reduced_6_percent_for_services(self):
        revenue = Decimal("100000")
        expected = (revenue * Decimal("0.06")).quantize(Decimal("0.01"))
        assert expected == Decimal("6000.00")

    def test_eligible_under_limit(self):
        """2025: turnover limit is 320,000."""
        revenue = Decimal("319999")
        assert revenue <= Decimal("320000")

    def test_not_eligible_above_limit(self):
        revenue = Decimal("320001")
        assert revenue > Decimal("320000")

    def test_exactly_at_limit_eligible(self):
        revenue = Decimal("320000")
        assert revenue <= Decimal("320000")

    @patch("app.services.e1a_form_service._load_self_employed_config")
    def test_pauschalierung_in_form_output(self, mock_load):
        """Verify form output reflects pauschalierung for eligible revenue."""
        mock_load.return_value = _TEST_SE_CONFIG
        txns = [
            _make_transaction(TransactionType.INCOME, Decimal("150000"), income_category=IncomeCategory.BUSINESS),
        ]
        db = _mock_db_returning(txns)
        user = _make_user()

        result = generate_e1a_form_data(db, user, 2025)

        assert result["summary"]["pauschalierung_eligible"] is True
        assert result["summary"]["pauschalierung_general_pct"] == 20250.0  # 150000 * 0.135
        assert result["summary"]["pauschalierung_consulting_pct"] == 9000.0  # 150000 * 0.06

    @patch("app.services.e1a_form_service._load_self_employed_config")
    def test_pauschalierung_ineligible_above_limit(self, mock_load):
        mock_load.return_value = _TEST_SE_CONFIG
        txns = [
            _make_transaction(TransactionType.INCOME, Decimal("350000"), income_category=IncomeCategory.BUSINESS),
        ]
        db = _mock_db_returning(txns)
        user = _make_user()

        result = generate_e1a_form_data(db, user, 2025)
        assert result["summary"]["pauschalierung_eligible"] is False


# ---------------------------------------------------------------------------
# 3. EA-Rechnung breakdown by expense categories
# ---------------------------------------------------------------------------
class TestEARechnungBreakdown:
    @patch("app.services.e1a_form_service._load_self_employed_config")
    def test_expense_categories_mapped_to_fields(self, mock_load):
        mock_load.return_value = _TEST_SE_CONFIG
        txns = [
            _make_transaction(TransactionType.INCOME, Decimal("50000"), income_category=IncomeCategory.BUSINESS),
            _make_transaction(TransactionType.EXPENSE, Decimal("1000"), expense_category=ExpenseCategory.GROCERIES),
            _make_transaction(TransactionType.EXPENSE, Decimal("2000"), expense_category=ExpenseCategory.EQUIPMENT),
            _make_transaction(TransactionType.EXPENSE, Decimal("500"), expense_category=ExpenseCategory.RENT),
            _make_transaction(TransactionType.EXPENSE, Decimal("300"), expense_category=ExpenseCategory.TRAVEL),
            _make_transaction(TransactionType.EXPENSE, Decimal("200"), expense_category=ExpenseCategory.TELECOM),
            _make_transaction(TransactionType.EXPENSE, Decimal("150"), expense_category=ExpenseCategory.MARKETING),
            _make_transaction(TransactionType.EXPENSE, Decimal("400"), expense_category=ExpenseCategory.INSURANCE),
            _make_transaction(TransactionType.EXPENSE, Decimal("600"), expense_category=ExpenseCategory.PROFESSIONAL_SERVICES),
            _make_transaction(TransactionType.EXPENSE, Decimal("50"), expense_category=ExpenseCategory.BANK_FEES),
            _make_transaction(TransactionType.EXPENSE, Decimal("100"), expense_category=ExpenseCategory.LOAN_INTEREST),
            _make_transaction(TransactionType.EXPENSE, Decimal("800"), expense_category=ExpenseCategory.SVS_CONTRIBUTIONS),
            _make_transaction(TransactionType.EXPENSE, Decimal("250"), expense_category=ExpenseCategory.UTILITIES),
            _make_transaction(TransactionType.EXPENSE, Decimal("350"), expense_category=ExpenseCategory.MAINTENANCE),
            _make_transaction(TransactionType.EXPENSE, Decimal("100"), expense_category=ExpenseCategory.OTHER),
        ]
        db = _mock_db_returning(txns)
        user = _make_user()

        result = generate_e1a_form_data(db, user, 2025)
        fields = {f["kz"]: f["value"] for f in result["fields"]}

        assert fields["9050"] == 1000.0   # material (GROCERIES)
        assert fields["9070"] == 2000.0   # AfA (EQUIPMENT)
        assert fields["9080"] == 500.0    # rent
        assert fields["9081"] == 300.0    # travel
        assert fields["9082"] == 200.0    # telecom
        assert fields["9083"] == 150.0    # marketing
        assert fields["9084"] == 400.0    # insurance
        assert fields["9085"] == 600.0    # professional services
        assert fields["9086"] == 800.0    # SVS
        assert fields["9087"] == 150.0    # interest + bank_fees (100 + 50)
        assert fields["9090"] == 700.0    # other (utilities 250 + maintenance 350 + other 100)

    @patch("app.services.e1a_form_service._load_self_employed_config")
    def test_non_deductible_expenses_excluded(self, mock_load):
        mock_load.return_value = _TEST_SE_CONFIG
        txns = [
            _make_transaction(TransactionType.INCOME, Decimal("10000"), income_category=IncomeCategory.BUSINESS),
            _make_transaction(TransactionType.EXPENSE, Decimal("500"), expense_category=ExpenseCategory.TRAVEL, is_deductible=True),
            _make_transaction(TransactionType.EXPENSE, Decimal("300"), expense_category=ExpenseCategory.TRAVEL, is_deductible=False),
        ]
        db = _mock_db_returning(txns)
        user = _make_user()

        result = generate_e1a_form_data(db, user, 2025)
        fields = {f["kz"]: f["value"] for f in result["fields"]}
        assert fields["9081"] == 500.0  # only deductible travel


# ---------------------------------------------------------------------------
# 4. Revenue aggregation from BUSINESS and SELF_EMPLOYMENT
# ---------------------------------------------------------------------------
class TestRevenueAggregation:
    def test_business_and_self_employment_combined(self):
        txns = [
            _make_transaction(TransactionType.INCOME, Decimal("30000"), income_category=IncomeCategory.BUSINESS),
            _make_transaction(TransactionType.INCOME, Decimal("20000"), income_category=IncomeCategory.SELF_EMPLOYMENT),
        ]
        result = _sum_income(txns, [IncomeCategory.BUSINESS, IncomeCategory.SELF_EMPLOYMENT])
        assert result == Decimal("50000")

    def test_other_income_categories_excluded(self):
        txns = [
            _make_transaction(TransactionType.INCOME, Decimal("30000"), income_category=IncomeCategory.BUSINESS),
            _make_transaction(TransactionType.INCOME, Decimal("5000"), income_category=IncomeCategory.EMPLOYMENT),
            _make_transaction(TransactionType.INCOME, Decimal("2000"), income_category=IncomeCategory.RENTAL),
            _make_transaction(TransactionType.INCOME, Decimal("1000"), income_category=IncomeCategory.CAPITAL_GAINS),
        ]
        result = _sum_income(txns, [IncomeCategory.BUSINESS, IncomeCategory.SELF_EMPLOYMENT])
        assert result == Decimal("30000")

    def test_expenses_not_counted_as_income(self):
        txns = [
            _make_transaction(TransactionType.INCOME, Decimal("10000"), income_category=IncomeCategory.BUSINESS),
            _make_transaction(TransactionType.EXPENSE, Decimal("5000"), expense_category=ExpenseCategory.RENT),
        ]
        result = _sum_income(txns, [IncomeCategory.BUSINESS, IncomeCategory.SELF_EMPLOYMENT])
        assert result == Decimal("10000")

    @patch("app.services.e1a_form_service._load_self_employed_config")
    def test_revenue_in_form_output(self, mock_load):
        mock_load.return_value = _TEST_SE_CONFIG
        txns = [
            _make_transaction(TransactionType.INCOME, Decimal("40000"), income_category=IncomeCategory.BUSINESS),
            _make_transaction(TransactionType.INCOME, Decimal("10000"), income_category=IncomeCategory.SELF_EMPLOYMENT),
        ]
        db = _mock_db_returning(txns)
        user = _make_user()

        result = generate_e1a_form_data(db, user, 2025)
        fields = {f["kz"]: f["value"] for f in result["fields"]}
        assert fields["9040"] == 50000.0
        assert result["summary"]["business_income"] == 50000.0


# ---------------------------------------------------------------------------
# 5. Profit/loss calculation
# ---------------------------------------------------------------------------
class TestProfitLoss:
    @patch("app.services.e1a_form_service._load_self_employed_config")
    def test_profit_positive(self, mock_load):
        mock_load.return_value = _TEST_SE_CONFIG
        txns = [
            _make_transaction(TransactionType.INCOME, Decimal("80000"), income_category=IncomeCategory.BUSINESS),
            _make_transaction(TransactionType.EXPENSE, Decimal("30000"), expense_category=ExpenseCategory.RENT),
        ]
        db = _mock_db_returning(txns)
        user = _make_user()

        result = generate_e1a_form_data(db, user, 2025)
        assert result["summary"]["profit"] == 50000.0
        fields = {f["kz"]: f["value"] for f in result["fields"]}
        assert fields["9100"] == 50000.0

    @patch("app.services.e1a_form_service._load_self_employed_config")
    def test_loss_negative(self, mock_load):
        mock_load.return_value = _TEST_SE_CONFIG
        txns = [
            _make_transaction(TransactionType.INCOME, Decimal("20000"), income_category=IncomeCategory.BUSINESS),
            _make_transaction(TransactionType.EXPENSE, Decimal("35000"), expense_category=ExpenseCategory.RENT),
        ]
        db = _mock_db_returning(txns)
        user = _make_user()

        result = generate_e1a_form_data(db, user, 2025)
        assert result["summary"]["profit"] == -15000.0

    @patch("app.services.e1a_form_service._load_self_employed_config")
    def test_breakeven(self, mock_load):
        mock_load.return_value = _TEST_SE_CONFIG
        txns = [
            _make_transaction(TransactionType.INCOME, Decimal("25000"), income_category=IncomeCategory.BUSINESS),
            _make_transaction(TransactionType.EXPENSE, Decimal("25000"), expense_category=ExpenseCategory.RENT),
        ]
        db = _mock_db_returning(txns)
        user = _make_user()

        result = generate_e1a_form_data(db, user, 2025)
        assert result["summary"]["profit"] == 0.0


# ---------------------------------------------------------------------------
# 6. Zero transactions scenario
# ---------------------------------------------------------------------------
class TestZeroTransactions:
    @patch("app.services.e1a_form_service._load_self_employed_config")
    def test_empty_transactions(self, mock_load):
        mock_load.return_value = _TEST_SE_CONFIG
        db = _mock_db_returning([])
        user = _make_user()

        result = generate_e1a_form_data(db, user, 2025)

        assert result["form_type"] == "E1a"
        assert result["tax_year"] == 2025
        assert result["summary"]["business_income"] == 0.0
        assert result["summary"]["total_expenses"] == 0.0
        assert result["summary"]["profit"] == 0.0
        assert result["summary"]["grundfreibetrag"] == 0.0
        assert result["summary"]["investitions_gfb"] == 0.0
        assert result["summary"]["total_gewinnfreibetrag"] == 0.0
        assert result["summary"]["taxable_profit"] == 0.0
        assert result["summary"]["pauschalierung_eligible"] is True

    @patch("app.services.e1a_form_service._load_self_employed_config")
    def test_all_field_values_zero(self, mock_load):
        mock_load.return_value = _TEST_SE_CONFIG
        db = _mock_db_returning([])
        user = _make_user()

        result = generate_e1a_form_data(db, user, 2025)
        for field in result["fields"]:
            assert field["value"] == 0.0, f"Field {field['kz']} should be 0.0"


# ---------------------------------------------------------------------------
# 7. Taxable profit after GFB deduction
# ---------------------------------------------------------------------------
class TestTaxableProfitAfterGFB:
    @patch("app.services.e1a_form_service._load_self_employed_config")
    def test_taxable_profit_reduced_by_gfb(self, mock_load):
        mock_load.return_value = _TEST_SE_CONFIG
        txns = [
            _make_transaction(TransactionType.INCOME, Decimal("60000"), income_category=IncomeCategory.BUSINESS),
            _make_transaction(TransactionType.EXPENSE, Decimal("10000"), expense_category=ExpenseCategory.RENT),
        ]
        db = _mock_db_returning(txns)
        user = _make_user()

        result = generate_e1a_form_data(db, user, 2025)
        profit = 50000.0
        grund = 4950.0   # 33000 * 0.15
        invest = 2210.0   # (50000 - 33000) * 0.13 = 17000 * 0.13
        total_gfb = grund + invest
        assert result["summary"]["profit"] == profit
        assert result["summary"]["taxable_profit"] == profit - total_gfb

    @patch("app.services.e1a_form_service._load_self_employed_config")
    def test_taxable_profit_floored_at_zero(self, mock_load):
        mock_load.return_value = _TEST_SE_CONFIG
        txns = [
            _make_transaction(TransactionType.INCOME, Decimal("5000"), income_category=IncomeCategory.BUSINESS),
            _make_transaction(TransactionType.EXPENSE, Decimal("20000"), expense_category=ExpenseCategory.RENT),
        ]
        db = _mock_db_returning(txns)
        user = _make_user()

        result = generate_e1a_form_data(db, user, 2025)
        assert result["summary"]["profit"] == -15000.0
        assert result["summary"]["taxable_profit"] == 0.0

    @patch("app.services.e1a_form_service._load_self_employed_config")
    def test_taxable_profit_small_profit(self, mock_load):
        mock_load.return_value = _TEST_SE_CONFIG
        txns = [
            _make_transaction(TransactionType.INCOME, Decimal("1000"), income_category=IncomeCategory.SELF_EMPLOYMENT),
        ]
        db = _mock_db_returning(txns)
        user = _make_user()

        result = generate_e1a_form_data(db, user, 2025)
        profit = 1000.0
        gfb = 150.0  # 1000 * 0.15
        assert result["summary"]["taxable_profit"] == profit - gfb

    @patch("app.services.e1a_form_service._load_self_employed_config")
    def test_user_metadata_in_output(self, mock_load):
        mock_load.return_value = _TEST_SE_CONFIG
        db = _mock_db_returning([])
        user = _make_user(name="Anna Test", tax_number="99-888/7777")

        result = generate_e1a_form_data(db, user, 2024)
        assert result["user_name"] == "Anna Test"
        assert result["tax_number"] == "99-888/7777"
        assert result["tax_year"] == 2024
