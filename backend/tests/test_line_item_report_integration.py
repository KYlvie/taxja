"""Tests for line-item-aware report aggregation.

Verifies that all report services correctly use per-item category and
deductibility instead of whole-transaction amounts when line items exist.

Covers:
1. line_item_utils: shared aggregation functions
2. dashboard_service: deductible_expenses total + expense_by_cat breakdown
3. e1_form_service: _sum_by_expense_cat, _sum_deductible_expenses
4. e1a_form_service: _sum_expense
5. e1b_form_service: _sum_property_expense
6. ea_report_service: expense sections with line-item expansion
7. property_report_service: income statement expense aggregation
8. Backward compatibility: transactions without line items
"""
import pytest
from decimal import Decimal
from types import SimpleNamespace
from collections import defaultdict
from unittest.mock import MagicMock, patch
from datetime import date
from uuid import uuid4

from app.models.transaction import (
    Transaction as _RealTxn, TransactionType, ExpenseCategory, IncomeCategory,
)


# ── Lightweight test doubles ───────────────────────────────────────

class _FakeTransaction:
    """Stand-in for Transaction that carries real computed properties
    without triggering SQLAlchemy instrumentation."""
    has_line_items = _RealTxn.has_line_items
    deductible_amount = _RealTxn.deductible_amount
    non_deductible_amount = _RealTxn.non_deductible_amount
    deductible_items_by_category = _RealTxn.deductible_items_by_category

    def __init__(
        self, amount, txn_type=TransactionType.EXPENSE,
        expense_category=None, income_category=None,
        is_deductible=False, line_items=None,
        description="Test", transaction_date=None,
        property_id=None, vat_amount=None, id=1,
    ):
        self.id = id
        self.amount = Decimal(str(amount))
        self.type = txn_type
        self.expense_category = expense_category
        self.income_category = income_category
        self.is_deductible = is_deductible
        self.line_items = line_items or []
        self.description = description
        self.transaction_date = transaction_date or date(2026, 3, 15)
        self.property_id = property_id
        self.vat_amount = Decimal(str(vat_amount)) if vat_amount else None


def _li(description, amount, quantity=1, category="other",
        is_deductible=False):
    """Create a line-item-like SimpleNamespace."""
    return SimpleNamespace(
        description=description,
        amount=Decimal(str(amount)),
        quantity=quantity,
        category=category,
        is_deductible=is_deductible,
    )


# ═══════════════════════════════════════════════════════════════════
# 1. line_item_utils
# ═══════════════════════════════════════════════════════════════════

class TestSumDeductibleByCategory:
    """Test line_item_utils.sum_deductible_by_category."""

    def test_single_txn_with_mixed_line_items(self):
        from app.services.line_item_utils import sum_deductible_by_category
        txn = _FakeTransaction(
            amount=40, line_items=[
                _li("Papier", 10, 1, "office_supplies", True),
                _li("Milch", 5, 2, "groceries", False),
                _li("Toner", 20, 1, "office_supplies", True),
            ],
        )
        result = sum_deductible_by_category([txn])
        assert result == {"office_supplies": Decimal("30")}

    def test_multiple_txns_aggregate(self):
        from app.services.line_item_utils import sum_deductible_by_category
        t1 = _FakeTransaction(
            amount=15, line_items=[
                _li("Papier", 15, 1, "office_supplies", True),
            ], id=1,
        )
        t2 = _FakeTransaction(
            amount=10, line_items=[
                _li("Reiniger", 5, 2, "cleaning", True),
            ], id=2,
        )
        result = sum_deductible_by_category([t1, t2])
        assert result == {
            "office_supplies": Decimal("15"),
            "cleaning": Decimal("10"),
        }

    def test_category_filter(self):
        from app.services.line_item_utils import sum_deductible_by_category
        txn = _FakeTransaction(
            amount=30, line_items=[
                _li("Papier", 10, 1, "office_supplies", True),
                _li("Reiniger", 20, 1, "cleaning", True),
            ],
        )
        result = sum_deductible_by_category(
            [txn], categories=[ExpenseCategory.OFFICE_SUPPLIES],
        )
        assert result == {"office_supplies": Decimal("10")}
        assert "cleaning" not in result

    def test_property_id_filter(self):
        from app.services.line_item_utils import sum_deductible_by_category
        pid = uuid4()
        t1 = _FakeTransaction(
            amount=10, property_id=pid, line_items=[
                _li("Papier", 10, 1, "office_supplies", True),
            ], id=1,
        )
        t2 = _FakeTransaction(
            amount=20, property_id=uuid4(), line_items=[
                _li("Toner", 20, 1, "office_supplies", True),
            ], id=2,
        )
        result = sum_deductible_by_category([t1, t2], property_id=pid)
        assert result == {"office_supplies": Decimal("10")}

    def test_skips_income_transactions(self):
        from app.services.line_item_utils import sum_deductible_by_category
        txn = _FakeTransaction(
            amount=100, txn_type=TransactionType.INCOME,
            income_category=IncomeCategory.BUSINESS,
            line_items=[_li("Sale", 100, 1, "other", True)],
        )
        result = sum_deductible_by_category([txn])
        assert result == {}

    def test_legacy_txn_without_line_items(self):
        from app.services.line_item_utils import sum_deductible_by_category
        txn = _FakeTransaction(
            amount=50, is_deductible=True,
            expense_category=ExpenseCategory.EQUIPMENT,
        )
        result = sum_deductible_by_category([txn])
        assert result == {"equipment": Decimal("50")}

    def test_legacy_txn_not_deductible(self):
        from app.services.line_item_utils import sum_deductible_by_category
        txn = _FakeTransaction(
            amount=50, is_deductible=False,
            expense_category=ExpenseCategory.EQUIPMENT,
        )
        result = sum_deductible_by_category([txn])
        assert result == {}

    def test_empty_list(self):
        from app.services.line_item_utils import sum_deductible_by_category
        assert sum_deductible_by_category([]) == {}


class TestSumDeductibleExpenses:
    """Test line_item_utils.sum_deductible_expenses."""

    def test_sums_across_categories(self):
        from app.services.line_item_utils import sum_deductible_expenses
        txn = _FakeTransaction(
            amount=30, line_items=[
                _li("A", 10, 1, "office_supplies", True),
                _li("B", 5, 2, "cleaning", True),
                _li("C", 10, 1, "groceries", False),
            ],
        )
        assert sum_deductible_expenses([txn]) == Decimal("20")

    def test_with_category_filter(self):
        from app.services.line_item_utils import sum_deductible_expenses
        txn = _FakeTransaction(
            amount=30, line_items=[
                _li("A", 10, 1, "office_supplies", True),
                _li("B", 20, 1, "cleaning", True),
            ],
        )
        result = sum_deductible_expenses(
            [txn], categories=[ExpenseCategory.CLEANING],
        )
        assert result == Decimal("20")

    def test_legacy_txn(self):
        from app.services.line_item_utils import sum_deductible_expenses
        txn = _FakeTransaction(
            amount=100, is_deductible=True,
            expense_category=ExpenseCategory.TRAVEL,
        )
        assert sum_deductible_expenses([txn]) == Decimal("100")


class TestSumExpensesByCategory:
    """Test line_item_utils.sum_expenses_by_category."""

    def test_includes_non_deductible_by_default(self):
        from app.services.line_item_utils import sum_expenses_by_category
        txn = _FakeTransaction(
            amount=25, line_items=[
                _li("Papier", 15, 1, "office_supplies", True),
                _li("Milch", 10, 1, "groceries", False),
            ],
        )
        result = sum_expenses_by_category([txn])
        assert result == {
            "office_supplies": Decimal("15"),
            "groceries": Decimal("10"),
        }

    def test_deductible_only_flag(self):
        from app.services.line_item_utils import sum_expenses_by_category
        txn = _FakeTransaction(
            amount=25, line_items=[
                _li("Papier", 15, 1, "office_supplies", True),
                _li("Milch", 10, 1, "groceries", False),
            ],
        )
        result = sum_expenses_by_category([txn], deductible_only=True)
        assert result == {"office_supplies": Decimal("15")}

    def test_legacy_txn_all_expenses(self):
        from app.services.line_item_utils import sum_expenses_by_category
        txn = _FakeTransaction(
            amount=50, is_deductible=False,
            expense_category=ExpenseCategory.MARKETING,
        )
        result = sum_expenses_by_category([txn])
        assert result == {"marketing": Decimal("50")}

    def test_legacy_txn_deductible_only(self):
        from app.services.line_item_utils import sum_expenses_by_category
        txn = _FakeTransaction(
            amount=50, is_deductible=False,
            expense_category=ExpenseCategory.MARKETING,
        )
        result = sum_expenses_by_category([txn], deductible_only=True)
        assert result == {}

    def test_quantity_multiplied(self):
        from app.services.line_item_utils import sum_expenses_by_category
        txn = _FakeTransaction(
            amount=30, line_items=[
                _li("Stifte", 5, 6, "office_supplies", True),
            ],
        )
        result = sum_expenses_by_category([txn])
        assert result == {"office_supplies": Decimal("30")}



# ═══════════════════════════════════════════════════════════════════
# 2. dashboard_service: deductible_expenses + expense_by_cat
# ═══════════════════════════════════════════════════════════════════

class TestDashboardServiceLineItems:
    """Test that DashboardService.get_dashboard_data uses line items."""

    def _make_dashboard(self, transactions):
        """Create a DashboardService with mocked DB returning given transactions."""
        from app.services.dashboard_service import DashboardService

        db = MagicMock()
        # Mock the transaction query chain
        db.query.return_value.filter.return_value.all.return_value = transactions
        # Mock TaxConfiguration query for tax brackets
        db.query.return_value.filter.return_value.first.return_value = None

        with patch.object(DashboardService, "_init_redis"):
            svc = DashboardService(db)
            svc._redis_client = None
        return svc, db

    def test_deductible_expenses_uses_line_items(self):
        """deductibleExpenses should sum deductible_amount from line items."""
        txn = _FakeTransaction(
            amount=25, line_items=[
                _li("Papier", 15, 1, "office_supplies", True),
                _li("Milch", 10, 1, "groceries", False),
            ],
        )
        svc, db = self._make_dashboard([txn])
        result = svc.get_dashboard_data(user_id=1, tax_year=2026)
        assert result["deductibleExpenses"] == 15.0

    def test_expense_by_cat_expands_line_items(self):
        """expenseCategoryData should have separate entries per line-item category."""
        txn = _FakeTransaction(
            amount=25, line_items=[
                _li("Papier", 15, 1, "office_supplies", True),
                _li("Milch", 10, 1, "groceries", False),
            ],
        )
        svc, db = self._make_dashboard([txn])
        result = svc.get_dashboard_data(user_id=1, tax_year=2026)
        cat_data = {d["category"]: d["amount"] for d in result["expenseCategoryData"]}
        assert cat_data.get("office_supplies") == 15.0
        assert cat_data.get("groceries") == 10.0

    def test_legacy_txn_still_works(self):
        """Transaction without line items should use expense_category."""
        txn = _FakeTransaction(
            amount=50, is_deductible=True,
            expense_category=ExpenseCategory.EQUIPMENT,
        )
        svc, db = self._make_dashboard([txn])
        result = svc.get_dashboard_data(user_id=1, tax_year=2026)
        assert result["deductibleExpenses"] == 50.0
        cat_data = {d["category"]: d["amount"] for d in result["expenseCategoryData"]}
        assert cat_data.get("equipment") == 50.0

    def test_mixed_txns_with_and_without_line_items(self):
        """Mix of line-item and legacy transactions."""
        t1 = _FakeTransaction(
            amount=25, id=1, line_items=[
                _li("Papier", 15, 1, "office_supplies", True),
                _li("Milch", 10, 1, "groceries", False),
            ],
        )
        t2 = _FakeTransaction(
            amount=30, id=2, is_deductible=True,
            expense_category=ExpenseCategory.TRAVEL,
        )
        svc, db = self._make_dashboard([t1, t2])
        result = svc.get_dashboard_data(user_id=1, tax_year=2026)
        # Deductible: 15 (papier) + 30 (travel) = 45
        assert result["deductibleExpenses"] == 45.0


# ═══════════════════════════════════════════════════════════════════
# 3. e1_form_service: _sum_by_expense_cat, _sum_deductible_expenses
# ═══════════════════════════════════════════════════════════════════

class TestE1FormServiceLineItems:
    """Test e1_form_service helper functions with line items."""

    def test_sum_by_expense_cat_with_line_items(self):
        from app.services.e1_form_service import _sum_by_expense_cat
        txn = _FakeTransaction(
            amount=30, line_items=[
                _li("Papier", 10, 1, "office_supplies", True),
                _li("Reiniger", 5, 2, "cleaning", True),
                _li("Milch", 10, 1, "groceries", False),
            ],
        )
        result = _sum_by_expense_cat(
            [txn],
            [ExpenseCategory.OFFICE_SUPPLIES, ExpenseCategory.CLEANING],
            deductible_only=True,
        )
        # office_supplies: 10, cleaning: 5*2=10
        assert result == Decimal("20")

    def test_sum_by_expense_cat_legacy(self):
        from app.services.e1_form_service import _sum_by_expense_cat
        txn = _FakeTransaction(
            amount=50, is_deductible=True,
            expense_category=ExpenseCategory.OFFICE_SUPPLIES,
        )
        result = _sum_by_expense_cat(
            [txn], [ExpenseCategory.OFFICE_SUPPLIES], deductible_only=True,
        )
        assert result == Decimal("50")

    def test_sum_by_expense_cat_filters_non_deductible_items(self):
        from app.services.e1_form_service import _sum_by_expense_cat
        txn = _FakeTransaction(
            amount=20, line_items=[
                _li("Papier", 10, 1, "office_supplies", True),
                _li("Snack", 10, 1, "office_supplies", False),
            ],
        )
        result = _sum_by_expense_cat(
            [txn], [ExpenseCategory.OFFICE_SUPPLIES], deductible_only=True,
        )
        assert result == Decimal("10")

    def test_sum_by_expense_cat_no_deductible_filter(self):
        from app.services.e1_form_service import _sum_by_expense_cat
        txn = _FakeTransaction(
            amount=20, line_items=[
                _li("Papier", 10, 1, "office_supplies", True),
                _li("Snack", 10, 1, "office_supplies", False),
            ],
        )
        result = _sum_by_expense_cat(
            [txn], [ExpenseCategory.OFFICE_SUPPLIES], deductible_only=False,
        )
        assert result == Decimal("20")

    def test_sum_deductible_expenses_with_line_items(self):
        from app.services.e1_form_service import _sum_deductible_expenses
        txn = _FakeTransaction(
            amount=30, line_items=[
                _li("Papier", 10, 1, "office_supplies", True),
                _li("Milch", 5, 2, "groceries", False),
                _li("Toner", 10, 1, "office_supplies", True),
            ],
        )
        # deductible_amount = 10 + 10 = 20
        assert _sum_deductible_expenses([txn]) == Decimal("20")

    def test_sum_deductible_expenses_legacy(self):
        from app.services.e1_form_service import _sum_deductible_expenses
        txn = _FakeTransaction(
            amount=100, is_deductible=True,
            expense_category=ExpenseCategory.EQUIPMENT,
        )
        assert _sum_deductible_expenses([txn]) == Decimal("100")

    def test_sum_deductible_expenses_not_deductible_legacy(self):
        from app.services.e1_form_service import _sum_deductible_expenses
        txn = _FakeTransaction(
            amount=100, is_deductible=False,
            expense_category=ExpenseCategory.EQUIPMENT,
        )
        assert _sum_deductible_expenses([txn]) == Decimal("0")

    def test_sum_by_expense_cat_skips_income(self):
        from app.services.e1_form_service import _sum_by_expense_cat
        txn = _FakeTransaction(
            amount=100, txn_type=TransactionType.INCOME,
            income_category=IncomeCategory.BUSINESS,
        )
        result = _sum_by_expense_cat(
            [txn], [ExpenseCategory.OFFICE_SUPPLIES], deductible_only=False,
        )
        assert result == Decimal("0")


# ═══════════════════════════════════════════════════════════════════
# 4. e1a_form_service: _sum_expense
# ═══════════════════════════════════════════════════════════════════

class TestE1aFormServiceLineItems:
    """Test e1a_form_service._sum_expense with line items."""

    def test_sum_expense_with_line_items(self):
        from app.services.e1a_form_service import _sum_expense
        txn = _FakeTransaction(
            amount=30, line_items=[
                _li("Papier", 10, 1, "office_supplies", True),
                _li("Milch", 5, 2, "groceries", True),
                _li("Snack", 10, 1, "office_supplies", False),
            ],
        )
        # deductible_only=True by default
        # office_supplies deductible: 10, groceries deductible: 5*2=10
        result = _sum_expense(
            [txn], [ExpenseCategory.OFFICE_SUPPLIES, ExpenseCategory.GROCERIES],
        )
        assert result == Decimal("20")

    def test_sum_expense_legacy(self):
        from app.services.e1a_form_service import _sum_expense
        txn = _FakeTransaction(
            amount=50, is_deductible=True,
            expense_category=ExpenseCategory.TRAVEL,
        )
        result = _sum_expense([txn], [ExpenseCategory.TRAVEL])
        assert result == Decimal("50")

    def test_sum_expense_filters_categories(self):
        from app.services.e1a_form_service import _sum_expense
        txn = _FakeTransaction(
            amount=30, line_items=[
                _li("Papier", 10, 1, "office_supplies", True),
                _li("Reiniger", 20, 1, "cleaning", True),
            ],
        )
        result = _sum_expense([txn], [ExpenseCategory.OFFICE_SUPPLIES])
        assert result == Decimal("10")

    def test_sum_expense_skips_non_deductible_items(self):
        from app.services.e1a_form_service import _sum_expense
        txn = _FakeTransaction(
            amount=20, line_items=[
                _li("Papier", 10, 1, "office_supplies", True),
                _li("Snack", 10, 1, "office_supplies", False),
            ],
        )
        result = _sum_expense([txn], [ExpenseCategory.OFFICE_SUPPLIES])
        assert result == Decimal("10")

    def test_sum_expense_skips_income(self):
        from app.services.e1a_form_service import _sum_expense
        txn = _FakeTransaction(
            amount=100, txn_type=TransactionType.INCOME,
            income_category=IncomeCategory.BUSINESS,
        )
        result = _sum_expense([txn], [ExpenseCategory.OFFICE_SUPPLIES])
        assert result == Decimal("0")

    def test_sum_expense_quantity_multiplied(self):
        from app.services.e1a_form_service import _sum_expense
        txn = _FakeTransaction(
            amount=30, line_items=[
                _li("Stifte", 5, 6, "office_supplies", True),
            ],
        )
        result = _sum_expense([txn], [ExpenseCategory.OFFICE_SUPPLIES])
        assert result == Decimal("30")


# ═══════════════════════════════════════════════════════════════════
# 5. e1b_form_service: _sum_property_expense
# ═══════════════════════════════════════════════════════════════════

class TestE1bFormServiceLineItems:
    """Test e1b_form_service._sum_property_expense with line items."""

    def test_sum_property_expense_with_line_items(self):
        from app.services.e1b_form_service import _sum_property_expense
        pid = uuid4()
        txn = _FakeTransaction(
            amount=30, property_id=pid, line_items=[
                _li("Farbe", 10, 1, "maintenance", True),
                _li("Milch", 5, 2, "groceries", False),
                _li("Werkzeug", 10, 1, "maintenance", True),
            ],
        )
        result = _sum_property_expense(
            [txn], pid, [ExpenseCategory.MAINTENANCE],
        )
        assert result == Decimal("20")

    def test_sum_property_expense_legacy(self):
        from app.services.e1b_form_service import _sum_property_expense
        pid = uuid4()
        txn = _FakeTransaction(
            amount=50, property_id=pid, is_deductible=True,
            expense_category=ExpenseCategory.LOAN_INTEREST,
        )
        result = _sum_property_expense(
            [txn], pid, [ExpenseCategory.LOAN_INTEREST],
        )
        assert result == Decimal("50")

    def test_filters_by_property_id(self):
        from app.services.e1b_form_service import _sum_property_expense
        pid1 = uuid4()
        pid2 = uuid4()
        t1 = _FakeTransaction(
            amount=10, property_id=pid1, is_deductible=True,
            expense_category=ExpenseCategory.MAINTENANCE, id=1,
        )
        t2 = _FakeTransaction(
            amount=20, property_id=pid2, is_deductible=True,
            expense_category=ExpenseCategory.MAINTENANCE, id=2,
        )
        result = _sum_property_expense(
            [t1, t2], pid1, [ExpenseCategory.MAINTENANCE],
        )
        assert result == Decimal("10")

    def test_skips_non_deductible_line_items(self):
        from app.services.e1b_form_service import _sum_property_expense
        pid = uuid4()
        txn = _FakeTransaction(
            amount=20, property_id=pid, line_items=[
                _li("Farbe", 10, 1, "maintenance", True),
                _li("Deko", 10, 1, "maintenance", False),
            ],
        )
        result = _sum_property_expense(
            [txn], pid, [ExpenseCategory.MAINTENANCE],
        )
        assert result == Decimal("10")

    def test_skips_income_transactions(self):
        from app.services.e1b_form_service import _sum_property_expense
        pid = uuid4()
        txn = _FakeTransaction(
            amount=100, property_id=pid,
            txn_type=TransactionType.INCOME,
            income_category=IncomeCategory.RENTAL,
        )
        result = _sum_property_expense(
            [txn], pid, [ExpenseCategory.MAINTENANCE],
        )
        assert result == Decimal("0")

    def test_legacy_not_deductible_skipped(self):
        from app.services.e1b_form_service import _sum_property_expense
        pid = uuid4()
        txn = _FakeTransaction(
            amount=50, property_id=pid, is_deductible=False,
            expense_category=ExpenseCategory.MAINTENANCE,
        )
        result = _sum_property_expense(
            [txn], pid, [ExpenseCategory.MAINTENANCE],
        )
        assert result == Decimal("0")


# ═══════════════════════════════════════════════════════════════════
# 6. ea_report_service: expense sections with line-item expansion
# ═══════════════════════════════════════════════════════════════════

class TestEAReportServiceLineItems:
    """Test ea_report_service.generate_ea_report with line items."""

    def _make_user(self):
        user = MagicMock()
        user.id = 1
        user.name = "Test User"
        user.user_type = MagicMock()
        user.user_type.value = "self_employed"
        user.tax_number = "12-345/6789"
        return user

    def _generate(self, transactions, user=None):
        from app.services.ea_report_service import generate_ea_report
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = transactions
        return generate_ea_report(db, user or self._make_user(), 2026)

    def test_line_items_expand_into_separate_rows(self):
        """Each line item should become its own row in the correct expense group."""
        txn = _FakeTransaction(
            amount=25, description="BILLA Wien", line_items=[
                _li("Papier", 15, 1, "office_supplies", True),
                _li("Milch", 10, 1, "groceries", False),
            ],
        )
        report = self._generate([txn])
        sections = {s["key"]: s for s in report["expense_sections"]}

        # office_supplies → bueromaterial group
        assert "bueromaterial" in sections
        bm = sections["bueromaterial"]
        assert len(bm["items"]) == 1
        assert bm["items"][0]["amount"] == 15.0
        assert bm["items"][0]["is_deductible"] is True
        assert "Papier" in bm["items"][0]["description"]

        # groceries → materialaufwand group
        assert "materialaufwand" in sections
        ma = sections["materialaufwand"]
        assert len(ma["items"]) == 1
        assert ma["items"][0]["amount"] == 10.0
        assert ma["items"][0]["is_deductible"] is False

    def test_deductible_subtotals_correct(self):
        txn = _FakeTransaction(
            amount=25, description="BILLA", line_items=[
                _li("Papier", 15, 1, "office_supplies", True),
                _li("Milch", 10, 1, "groceries", False),
            ],
        )
        report = self._generate([txn])
        assert report["summary"]["total_deductible"] == 15.0
        assert report["summary"]["total_expenses"] == 25.0

    def test_legacy_txn_goes_to_correct_group(self):
        txn = _FakeTransaction(
            amount=50, is_deductible=True,
            expense_category=ExpenseCategory.TRAVEL,
            description="Zugticket",
        )
        report = self._generate([txn])
        sections = {s["key"]: s for s in report["expense_sections"]}
        assert "reisekosten" in sections
        assert sections["reisekosten"]["items"][0]["amount"] == 50.0

    def test_mixed_txns(self):
        """Mix of line-item and legacy transactions."""
        t1 = _FakeTransaction(
            amount=25, id=1, description="BILLA", line_items=[
                _li("Papier", 15, 1, "office_supplies", True),
                _li("Milch", 10, 1, "groceries", False),
            ],
        )
        t2 = _FakeTransaction(
            amount=30, id=2, is_deductible=True,
            expense_category=ExpenseCategory.TRAVEL,
            description="Zugticket",
        )
        report = self._generate([t1, t2])
        assert report["summary"]["total_expenses"] == 55.0
        assert report["summary"]["total_deductible"] == 45.0  # 15 + 30

    def test_quantity_multiplied_in_report(self):
        txn = _FakeTransaction(
            amount=30, description="Bürobedarf", line_items=[
                _li("Stifte", 5, 6, "office_supplies", True),
            ],
        )
        report = self._generate([txn])
        sections = {s["key"]: s for s in report["expense_sections"]}
        assert sections["bueromaterial"]["items"][0]["amount"] == 30.0

    def test_empty_transactions(self):
        report = self._generate([])
        assert report["summary"]["total_expenses"] == 0.0
        assert report["summary"]["total_deductible"] == 0.0
        assert report["expense_sections"] == []


# ═══════════════════════════════════════════════════════════════════
# 7. property_report_service: income statement expense aggregation
# ═══════════════════════════════════════════════════════════════════

class TestPropertyReportServiceLineItems:
    """Test PropertyReportService.generate_income_statement with line items."""

    def test_income_statement_expands_line_items(self):
        """Line items should be expanded into per-category expense totals."""
        from app.services.property_report_service import PropertyReportService

        pid = uuid4()
        txn = _FakeTransaction(
            amount=30, property_id=pid, line_items=[
                _li("Farbe", 10, 1, "maintenance", True),
                _li("Reiniger", 5, 2, "cleaning", True),
                _li("Milch", 10, 1, "groceries", False),
            ],
        )

        db = MagicMock()
        # Mock property query
        mock_prop = MagicMock()
        mock_prop.id = pid
        mock_prop.address = "Teststr. 1"
        mock_prop.purchase_date = date(2020, 1, 1)
        mock_prop.building_value = Decimal("200000")
        db.query.return_value.filter.return_value.first.return_value = mock_prop

        # Mock expense transactions query
        db.query.return_value.filter.return_value.all.return_value = [txn]

        # Mock rental income scalar
        db.query.return_value.filter.return_value.scalar.return_value = Decimal("1000")

        with patch.object(PropertyReportService, "_init_redis"):
            svc = PropertyReportService(db)
            svc._redis_client = None
            # Mock AfA calculator
            svc.afa_calculator = MagicMock()
            svc.afa_calculator.calculate_annual_depreciation.return_value = Decimal("0")

        result = svc.generate_income_statement(str(pid))
        by_cat = result["expenses"]["by_category"]

        assert by_cat.get("maintenance") == 10.0
        assert by_cat.get("cleaning") == 10.0  # 5*2
        assert by_cat.get("groceries") == 10.0

    def test_income_statement_legacy_txn(self):
        """Legacy transaction without line items uses expense_category."""
        from app.services.property_report_service import PropertyReportService

        pid = uuid4()
        txn = _FakeTransaction(
            amount=50, property_id=pid, is_deductible=True,
            expense_category=ExpenseCategory.MAINTENANCE,
        )

        db = MagicMock()
        mock_prop = MagicMock()
        mock_prop.id = pid
        mock_prop.address = "Teststr. 1"
        mock_prop.purchase_date = date(2020, 1, 1)
        mock_prop.building_value = Decimal("200000")
        db.query.return_value.filter.return_value.first.return_value = mock_prop
        db.query.return_value.filter.return_value.all.return_value = [txn]
        db.query.return_value.filter.return_value.scalar.return_value = Decimal("1000")

        with patch.object(PropertyReportService, "_init_redis"):
            svc = PropertyReportService(db)
            svc._redis_client = None
            svc.afa_calculator = MagicMock()
            svc.afa_calculator.calculate_annual_depreciation.return_value = Decimal("0")

        result = svc.generate_income_statement(str(pid))
        assert result["expenses"]["by_category"].get("maintenance") == 50.0


# ═══════════════════════════════════════════════════════════════════
# 8. Backward compatibility: all functions with legacy transactions
# ═══════════════════════════════════════════════════════════════════

class TestBackwardCompatNoLineItems:
    """Verify all aggregation functions work with legacy transactions (no line items)."""

    def test_line_item_utils_all_functions(self):
        from app.services.line_item_utils import (
            sum_deductible_by_category,
            sum_deductible_expenses,
            sum_expenses_by_category,
        )
        txn = _FakeTransaction(
            amount=100, is_deductible=True,
            expense_category=ExpenseCategory.EQUIPMENT,
        )
        assert sum_deductible_by_category([txn]) == {"equipment": Decimal("100")}
        assert sum_deductible_expenses([txn]) == Decimal("100")
        assert sum_expenses_by_category([txn]) == {"equipment": Decimal("100")}

    def test_e1_helpers(self):
        from app.services.e1_form_service import _sum_by_expense_cat, _sum_deductible_expenses
        txn = _FakeTransaction(
            amount=75, is_deductible=True,
            expense_category=ExpenseCategory.TRAVEL,
        )
        assert _sum_by_expense_cat([txn], [ExpenseCategory.TRAVEL], True) == Decimal("75")
        assert _sum_deductible_expenses([txn]) == Decimal("75")

    def test_e1a_helper(self):
        from app.services.e1a_form_service import _sum_expense
        txn = _FakeTransaction(
            amount=60, is_deductible=True,
            expense_category=ExpenseCategory.TELECOM,
        )
        assert _sum_expense([txn], [ExpenseCategory.TELECOM]) == Decimal("60")

    def test_e1b_helper(self):
        from app.services.e1b_form_service import _sum_property_expense
        pid = uuid4()
        txn = _FakeTransaction(
            amount=40, property_id=pid, is_deductible=True,
            expense_category=ExpenseCategory.INSURANCE,
        )
        assert _sum_property_expense([txn], pid, [ExpenseCategory.INSURANCE]) == Decimal("40")

    def test_ea_report_legacy_only(self):
        from app.services.ea_report_service import generate_ea_report
        db = MagicMock()
        user = MagicMock()
        user.id = 1
        user.name = "Test"
        user.user_type = MagicMock()
        user.user_type.value = "self_employed"
        user.tax_number = ""

        t1 = _FakeTransaction(
            amount=100, id=1, is_deductible=True,
            expense_category=ExpenseCategory.OFFICE_SUPPLIES,
            description="Bürobedarf",
        )
        t2 = _FakeTransaction(
            amount=50, id=2, is_deductible=False,
            expense_category=ExpenseCategory.GROCERIES,
            description="Lebensmittel",
        )
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [t1, t2]

        report = generate_ea_report(db, user, 2026)
        assert report["summary"]["total_expenses"] == 150.0
        assert report["summary"]["total_deductible"] == 100.0


# ═══════════════════════════════════════════════════════════════════
# 9. Edge cases
# ═══════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Edge cases for line-item-aware aggregation."""

    def test_line_item_with_zero_amount(self):
        from app.services.line_item_utils import sum_deductible_by_category
        txn = _FakeTransaction(
            amount=10, line_items=[
                _li("Free sample", 0, 1, "office_supplies", True),
                _li("Papier", 10, 1, "office_supplies", True),
            ],
        )
        result = sum_deductible_by_category([txn])
        assert result == {"office_supplies": Decimal("10")}

    def test_line_item_with_no_category_defaults_to_other(self):
        from app.services.line_item_utils import sum_expenses_by_category
        txn = _FakeTransaction(
            amount=10, line_items=[
                SimpleNamespace(
                    description="Mystery", amount=Decimal("10"),
                    quantity=1, category=None, is_deductible=True,
                ),
            ],
        )
        result = sum_expenses_by_category([txn])
        assert result == {"other": Decimal("10")}

    def test_all_line_items_non_deductible(self):
        from app.services.line_item_utils import sum_deductible_by_category
        txn = _FakeTransaction(
            amount=20, line_items=[
                _li("Milch", 10, 1, "groceries", False),
                _li("Brot", 10, 1, "groceries", False),
            ],
        )
        assert sum_deductible_by_category([txn]) == {}

    def test_single_line_item_same_as_transaction(self):
        """A transaction with one line item should behave like the line item."""
        from app.services.line_item_utils import sum_deductible_by_category
        txn = _FakeTransaction(
            amount=50, line_items=[
                _li("Toner", 50, 1, "office_supplies", True),
            ],
        )
        result = sum_deductible_by_category([txn])
        assert result == {"office_supplies": Decimal("50")}

    def test_large_quantity(self):
        from app.services.line_item_utils import sum_expenses_by_category
        txn = _FakeTransaction(
            amount=500, line_items=[
                _li("Stifte", "0.50", 1000, "office_supplies", True),
            ],
        )
        result = sum_expenses_by_category([txn])
        assert result == {"office_supplies": Decimal("500")}
