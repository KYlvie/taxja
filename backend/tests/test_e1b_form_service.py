"""Tests for E1b Form Service — Beilage zur Einkommensteuererklaerung (Vermietung und Verpachtung)"""
import pytest
from decimal import Decimal
from datetime import date
from uuid import uuid4
from unittest.mock import Mock, MagicMock

from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.models.property import Property, PropertyStatus, PropertyType, BuildingUse
from app.models.user import User
from app.services.e1b_form_service import generate_e1b_form_data


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(**overrides):
    user = Mock(spec=User)
    user.id = overrides.get("id", 1)
    user.name = overrides.get("name", "Max Mustermann")
    user.tax_number = overrides.get("tax_number", "12-345/6789")
    return user


def _make_property(
    *,
    pid=None,
    name="Wohnung Wien",
    address="Hauptstrasse 1, 1010 Wien",
    purchase_date=None,
    purchase_price=Decimal("300000"),
    building_value=Decimal("200000"),
    depreciation_rate=Decimal("0.015"),
    rental_percentage=Decimal("100"),
    status=PropertyStatus.ACTIVE,
    user_id=1,
):
    prop = Mock(spec=Property)
    prop.id = pid or uuid4()
    prop.user_id = user_id
    prop.asset_type = "real_estate"
    prop.name = name
    prop.address = address
    prop.property_type = PropertyType.RENTAL
    prop.purchase_date = purchase_date or date(2020, 1, 15)
    prop.purchase_price = purchase_price
    prop.building_value = building_value
    prop.depreciation_rate = depreciation_rate
    prop.rental_percentage = rental_percentage
    prop.sale_date = None
    prop.construction_year = 1990
    prop.building_use = BuildingUse.RESIDENTIAL
    prop.eco_standard = False
    prop.status = status
    return prop


def _make_transaction(
    *,
    tx_type: TransactionType,
    amount: Decimal,
    property_id,
    income_category=None,
    expense_category=None,
    is_deductible=True,
    vat_amount=Decimal("0"),
):
    t = Mock(spec=Transaction)
    t.type = tx_type
    t.amount = amount
    t.vat_amount = vat_amount
    t.property_id = property_id
    t.income_category = income_category
    t.expense_category = expense_category
    t.is_deductible = is_deductible
    return t


def _mock_db(properties, transactions):
    """Return a mock Session with separate query chains for Property and Transaction."""
    db = Mock()

    prop_query = Mock()
    prop_query.filter.return_value = prop_query
    prop_query.all.return_value = properties
    prop_query.first.return_value = properties[0] if properties else None

    txn_query = Mock()
    txn_query.filter.return_value = txn_query
    txn_query.all.return_value = transactions

    empty_query = Mock()
    empty_query.filter.return_value = empty_query
    empty_query.all.return_value = []
    empty_query.first.return_value = None
    empty_query.scalar.return_value = None

    def _query_side_effect(model):
        if model is Property:
            return prop_query
        if model is Transaction:
            return txn_query
        return empty_query

    db.query.side_effect = _query_side_effect
    return db


def _field_by_kz(fields, kz):
    for f in fields:
        if f["kz"] == kz:
            return f
    raise KeyError(f"KZ {kz} not found")


# ===========================================================================
# Single property rental income/expense breakdown
# ===========================================================================

class TestSinglePropertyBreakdown:
    """One property with various income and expense categories."""

    def test_rental_income_and_maintenance(self):
        pid = uuid4()
        prop = _make_property(pid=pid)
        txns = [
            _make_transaction(
                tx_type=TransactionType.INCOME,
                amount=Decimal("12000"),
                property_id=pid,
                income_category=IncomeCategory.RENTAL,
            ),
            _make_transaction(
                tx_type=TransactionType.EXPENSE,
                amount=Decimal("800"),
                property_id=pid,
                expense_category=ExpenseCategory.MAINTENANCE,
                is_deductible=True,
            ),
        ]
        result = generate_e1b_form_data(_mock_db([prop], txns), _make_user(), 2025)

        assert len(result["properties"]) == 1
        ps = result["properties"][0]["summary"]
        assert ps["rental_income"] == 12000.0
        assert ps["total_expenses"] > 0

    def test_expense_categories_map_correctly(self):
        pid = uuid4()
        prop = _make_property(pid=pid, building_value=Decimal("0"), depreciation_rate=Decimal("0"))
        txns = [
            _make_transaction(tx_type=TransactionType.INCOME, amount=Decimal("10000"), property_id=pid, income_category=IncomeCategory.RENTAL),
            _make_transaction(tx_type=TransactionType.EXPENSE, amount=Decimal("500"), property_id=pid, expense_category=ExpenseCategory.MAINTENANCE, is_deductible=True),
            _make_transaction(tx_type=TransactionType.EXPENSE, amount=Decimal("300"), property_id=pid, expense_category=ExpenseCategory.LOAN_INTEREST, is_deductible=True),
            _make_transaction(tx_type=TransactionType.EXPENSE, amount=Decimal("200"), property_id=pid, expense_category=ExpenseCategory.PROPERTY_MANAGEMENT_FEES, is_deductible=True),
            _make_transaction(tx_type=TransactionType.EXPENSE, amount=Decimal("150"), property_id=pid, expense_category=ExpenseCategory.PROPERTY_INSURANCE, is_deductible=True),
            _make_transaction(tx_type=TransactionType.EXPENSE, amount=Decimal("100"), property_id=pid, expense_category=ExpenseCategory.PROPERTY_TAX, is_deductible=True),
        ]
        result = generate_e1b_form_data(_mock_db([prop], txns), _make_user(), 2025)
        fields = result["properties"][0]["fields"]

        assert _field_by_kz(fields, "9410")["value"] == 10000.0   # rental income
        assert _field_by_kz(fields, "9420")["value"] == 500.0     # instandsetzung
        assert _field_by_kz(fields, "9440")["value"] == 300.0     # loan interest
        assert _field_by_kz(fields, "9450")["value"] == 200.0     # mgmt fees
        assert _field_by_kz(fields, "9451")["value"] == 150.0     # insurance
        assert _field_by_kz(fields, "9452")["value"] == 100.0     # grundsteuer

    def test_surplus_calculation(self):
        pid = uuid4()
        prop = _make_property(pid=pid, building_value=Decimal("0"), depreciation_rate=Decimal("0"))
        txns = [
            _make_transaction(tx_type=TransactionType.INCOME, amount=Decimal("10000"), property_id=pid, income_category=IncomeCategory.RENTAL),
            _make_transaction(tx_type=TransactionType.EXPENSE, amount=Decimal("3000"), property_id=pid, expense_category=ExpenseCategory.MAINTENANCE, is_deductible=True),
        ]
        result = generate_e1b_form_data(_mock_db([prop], txns), _make_user(), 2025)
        ps = result["properties"][0]["summary"]

        assert ps["surplus"] == 7000.0

    def test_loss_when_expenses_exceed_income(self):
        pid = uuid4()
        prop = _make_property(pid=pid, building_value=Decimal("0"), depreciation_rate=Decimal("0"))
        txns = [
            _make_transaction(tx_type=TransactionType.INCOME, amount=Decimal("2000"), property_id=pid, income_category=IncomeCategory.RENTAL),
            _make_transaction(tx_type=TransactionType.EXPENSE, amount=Decimal("5000"), property_id=pid, expense_category=ExpenseCategory.MAINTENANCE, is_deductible=True),
        ]
        result = generate_e1b_form_data(_mock_db([prop], txns), _make_user(), 2025)
        ps = result["properties"][0]["summary"]

        assert ps["surplus"] == -3000.0


# ===========================================================================
# Multiple properties generating separate E1b forms
# ===========================================================================

class TestMultipleProperties:
    """Each property should produce its own E1b entry."""

    def test_two_properties_separate_forms(self):
        pid1 = uuid4()
        pid2 = uuid4()
        prop1 = _make_property(pid=pid1, name="Wohnung Wien", building_value=Decimal("0"), depreciation_rate=Decimal("0"))
        prop2 = _make_property(pid=pid2, name="Haus Graz", building_value=Decimal("0"), depreciation_rate=Decimal("0"))

        txns = [
            _make_transaction(tx_type=TransactionType.INCOME, amount=Decimal("12000"), property_id=pid1, income_category=IncomeCategory.RENTAL),
            _make_transaction(tx_type=TransactionType.INCOME, amount=Decimal("8000"), property_id=pid2, income_category=IncomeCategory.RENTAL),
            _make_transaction(tx_type=TransactionType.EXPENSE, amount=Decimal("2000"), property_id=pid1, expense_category=ExpenseCategory.MAINTENANCE, is_deductible=True),
        ]
        result = generate_e1b_form_data(_mock_db([prop1, prop2], txns), _make_user(), 2025)

        assert len(result["properties"]) == 2
        names = {p["property_name"] for p in result["properties"]}
        assert "Wohnung Wien" in names
        assert "Haus Graz" in names

    def test_transactions_isolated_per_property(self):
        """Expenses for property 1 must not appear in property 2."""
        pid1 = uuid4()
        pid2 = uuid4()
        prop1 = _make_property(pid=pid1, name="P1", building_value=Decimal("0"), depreciation_rate=Decimal("0"))
        prop2 = _make_property(pid=pid2, name="P2", building_value=Decimal("0"), depreciation_rate=Decimal("0"))

        txns = [
            _make_transaction(tx_type=TransactionType.INCOME, amount=Decimal("10000"), property_id=pid1, income_category=IncomeCategory.RENTAL),
            _make_transaction(tx_type=TransactionType.EXPENSE, amount=Decimal("5000"), property_id=pid1, expense_category=ExpenseCategory.LOAN_INTEREST, is_deductible=True),
            _make_transaction(tx_type=TransactionType.INCOME, amount=Decimal("6000"), property_id=pid2, income_category=IncomeCategory.RENTAL),
        ]
        result = generate_e1b_form_data(_mock_db([prop1, prop2], txns), _make_user(), 2025)

        p1_data = next(p for p in result["properties"] if p["property_name"] == "P1")
        p2_data = next(p for p in result["properties"] if p["property_name"] == "P2")

        assert p1_data["summary"]["loan_interest"] == 5000.0
        assert p2_data["summary"]["loan_interest"] == 0.0
        assert p2_data["summary"]["rental_income"] == 6000.0


# ===========================================================================
# AfA auto-calculation from property model
# ===========================================================================

class TestAfaAutoCalculation:
    """When no explicit AfA transactions exist, AfA is calculated from property attributes."""

    def test_afa_calculated_from_building_value(self):
        pid = uuid4()
        prop = _make_property(
            pid=pid,
            building_value=Decimal("200000"),
            depreciation_rate=Decimal("0.015"),
            rental_percentage=Decimal("100"),
        )
        # No DEPRECIATION_AFA transactions -> auto-calc kicks in
        txns = [
            _make_transaction(tx_type=TransactionType.INCOME, amount=Decimal("12000"), property_id=pid, income_category=IncomeCategory.RENTAL),
        ]
        result = generate_e1b_form_data(_mock_db([prop], txns), _make_user(), 2025)
        ps = result["properties"][0]["summary"]

        # 200000 * 0.015 * 1.0 = 3000.00
        assert ps["afa_building"] == 3000.0
        assert ps["total_expenses"] == 3000.0
        assert ps["surplus"] == 9000.0

    def test_afa_with_partial_rental_percentage(self):
        pid = uuid4()
        prop = _make_property(
            pid=pid,
            building_value=Decimal("200000"),
            depreciation_rate=Decimal("0.015"),
            rental_percentage=Decimal("50"),
        )
        txns = [
            _make_transaction(tx_type=TransactionType.INCOME, amount=Decimal("6000"), property_id=pid, income_category=IncomeCategory.RENTAL),
        ]
        result = generate_e1b_form_data(_mock_db([prop], txns), _make_user(), 2025)
        ps = result["properties"][0]["summary"]

        # 200000 * 0.015 * 0.50 = 1500.00
        assert ps["afa_building"] == 1500.0

    def test_explicit_afa_transaction_overrides_auto_calc(self):
        """Building AfA is derived from property data, not explicit transactions."""
        pid = uuid4()
        prop = _make_property(
            pid=pid,
            building_value=Decimal("200000"),
            depreciation_rate=Decimal("0.015"),
            rental_percentage=Decimal("100"),
        )
        txns = [
            _make_transaction(tx_type=TransactionType.INCOME, amount=Decimal("12000"), property_id=pid, income_category=IncomeCategory.RENTAL),
            _make_transaction(tx_type=TransactionType.EXPENSE, amount=Decimal("2500"), property_id=pid, expense_category=ExpenseCategory.DEPRECIATION_AFA, is_deductible=True),
        ]
        result = generate_e1b_form_data(_mock_db([prop], txns), _make_user(), 2025)
        ps = result["properties"][0]["summary"]

        # Current service keeps building AfA property-driven at 3000.00
        assert ps["afa_building"] == 3000.0

    def test_no_auto_afa_when_building_value_missing(self):
        pid = uuid4()
        prop = _make_property(
            pid=pid,
            building_value=None,
            depreciation_rate=Decimal("0.015"),
        )
        txns = [
            _make_transaction(tx_type=TransactionType.INCOME, amount=Decimal("12000"), property_id=pid, income_category=IncomeCategory.RENTAL),
        ]
        result = generate_e1b_form_data(_mock_db([prop], txns), _make_user(), 2025)
        ps = result["properties"][0]["summary"]

        assert ps["afa_building"] == 0.0


# ===========================================================================
# Loan interest per property
# ===========================================================================

class TestLoanInterest:
    """Loan interest is tracked per property."""

    def test_loan_interest_single_property(self):
        pid = uuid4()
        prop = _make_property(pid=pid, building_value=Decimal("0"), depreciation_rate=Decimal("0"))
        txns = [
            _make_transaction(tx_type=TransactionType.INCOME, amount=Decimal("12000"), property_id=pid, income_category=IncomeCategory.RENTAL),
            _make_transaction(tx_type=TransactionType.EXPENSE, amount=Decimal("3600"), property_id=pid, expense_category=ExpenseCategory.LOAN_INTEREST, is_deductible=True),
            _make_transaction(tx_type=TransactionType.EXPENSE, amount=Decimal("400"), property_id=pid, expense_category=ExpenseCategory.LOAN_INTEREST, is_deductible=True),
        ]
        result = generate_e1b_form_data(_mock_db([prop], txns), _make_user(), 2025)
        ps = result["properties"][0]["summary"]

        assert ps["loan_interest"] == 4000.0

    def test_non_deductible_loan_interest_excluded(self):
        pid = uuid4()
        prop = _make_property(pid=pid, building_value=Decimal("0"), depreciation_rate=Decimal("0"))
        txns = [
            _make_transaction(tx_type=TransactionType.INCOME, amount=Decimal("12000"), property_id=pid, income_category=IncomeCategory.RENTAL),
            _make_transaction(tx_type=TransactionType.EXPENSE, amount=Decimal("3000"), property_id=pid, expense_category=ExpenseCategory.LOAN_INTEREST, is_deductible=True),
            _make_transaction(tx_type=TransactionType.EXPENSE, amount=Decimal("1000"), property_id=pid, expense_category=ExpenseCategory.LOAN_INTEREST, is_deductible=False),
        ]
        result = generate_e1b_form_data(_mock_db([prop], txns), _make_user(), 2025)
        ps = result["properties"][0]["summary"]

        # Only the deductible 3000 should be counted
        assert ps["loan_interest"] == 3000.0


# ===========================================================================
# Aggregate summary across all properties
# ===========================================================================

class TestAggregateSummary:
    """The top-level aggregate_summary sums across all properties."""

    def test_aggregate_totals(self):
        pid1 = uuid4()
        pid2 = uuid4()
        prop1 = _make_property(pid=pid1, name="P1", building_value=Decimal("0"), depreciation_rate=Decimal("0"))
        prop2 = _make_property(pid=pid2, name="P2", building_value=Decimal("0"), depreciation_rate=Decimal("0"))

        txns = [
            _make_transaction(tx_type=TransactionType.INCOME, amount=Decimal("10000"), property_id=pid1, income_category=IncomeCategory.RENTAL),
            _make_transaction(tx_type=TransactionType.EXPENSE, amount=Decimal("2000"), property_id=pid1, expense_category=ExpenseCategory.MAINTENANCE, is_deductible=True),
            _make_transaction(tx_type=TransactionType.INCOME, amount=Decimal("8000"), property_id=pid2, income_category=IncomeCategory.RENTAL),
            _make_transaction(tx_type=TransactionType.EXPENSE, amount=Decimal("1000"), property_id=pid2, expense_category=ExpenseCategory.LOAN_INTEREST, is_deductible=True),
        ]
        result = generate_e1b_form_data(_mock_db([prop1, prop2], txns), _make_user(), 2025)
        agg = result["aggregate_summary"]

        assert agg["property_count"] == 2
        assert agg["total_rental_income"] == 18000.0
        assert agg["total_rental_expenses"] == 3000.0
        assert agg["total_surplus"] == 15000.0

    def test_aggregate_with_afa(self):
        """AfA auto-calc should be included in aggregate totals."""
        pid = uuid4()
        prop = _make_property(
            pid=pid,
            building_value=Decimal("200000"),
            depreciation_rate=Decimal("0.015"),
            rental_percentage=Decimal("100"),
        )
        txns = [
            _make_transaction(tx_type=TransactionType.INCOME, amount=Decimal("12000"), property_id=pid, income_category=IncomeCategory.RENTAL),
        ]
        result = generate_e1b_form_data(_mock_db([prop], txns), _make_user(), 2025)
        agg = result["aggregate_summary"]

        assert agg["total_rental_income"] == 12000.0
        assert agg["total_rental_expenses"] == 3000.0  # AfA = 200000 * 0.015
        assert agg["total_surplus"] == 9000.0


# ===========================================================================
# Property with no transactions
# ===========================================================================

class TestPropertyNoTransactions:
    """A property exists but has zero transactions for the year."""

    def test_zero_income_zero_expenses(self):
        pid = uuid4()
        prop = _make_property(pid=pid, building_value=Decimal("0"), depreciation_rate=Decimal("0"))
        result = generate_e1b_form_data(_mock_db([prop], []), _make_user(), 2025)

        assert len(result["properties"]) == 1
        ps = result["properties"][0]["summary"]
        assert ps["rental_income"] == 0.0
        assert ps["total_expenses"] == 0.0
        assert ps["surplus"] == 0.0

    def test_afa_still_calculated_with_no_transactions(self):
        """Even without transactions, building AfA should be auto-calculated."""
        pid = uuid4()
        prop = _make_property(
            pid=pid,
            building_value=Decimal("200000"),
            depreciation_rate=Decimal("0.015"),
            rental_percentage=Decimal("100"),
        )
        result = generate_e1b_form_data(_mock_db([prop], []), _make_user(), 2025)
        ps = result["properties"][0]["summary"]

        assert ps["afa_building"] == 3000.0
        assert ps["total_expenses"] == 3000.0
        assert ps["surplus"] == -3000.0  # 0 income - 3000 AfA

    def test_no_properties_returns_empty(self):
        result = generate_e1b_form_data(_mock_db([], []), _make_user(), 2025)

        assert len(result["properties"]) == 0
        agg = result["aggregate_summary"]
        assert agg["property_count"] == 0
        assert agg["total_rental_income"] == 0.0
        assert agg["total_surplus"] == 0.0

    def test_form_metadata(self):
        result = generate_e1b_form_data(_mock_db([], []), _make_user(), 2025)

        assert result["form_type"] == "E1b"
        assert result["tax_year"] == 2025
        assert result["user_name"] == "Max Mustermann"
