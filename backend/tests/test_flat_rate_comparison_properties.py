"""
Property-based tests for flat-rate tax comparison.

Property 22: flat-rate tax comparison calculation.
Validates Requirements 31.1, 31.2, 31.3, 31.4.
"""

from datetime import date
from decimal import Decimal

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st
from sqlalchemy.orm import Session

from app.models.transaction import (
    ExpenseCategory,
    IncomeCategory,
    Transaction,
    TransactionType,
)
from app.models.user import User, UserType
from app.services.flat_rate_tax_comparator import FlatRateTaxComparator


@st.composite
def valid_income(draw):
    """Generate valid income amounts aligned to DB cents precision."""
    return draw(
        st.decimals(
            min_value=Decimal("1000.00"),
            max_value=Decimal("50000.00"),
            places=2,
        )
    )


@st.composite
def valid_expenses(draw, income: Decimal):
    """Generate expenses that keep profit within limits."""
    max_expenses = income - Decimal("1000.00")
    min_expenses = max(Decimal("0.00"), income - Decimal("33000.00"))

    if min_expenses >= max_expenses:
        return min_expenses.quantize(Decimal("0.01"))

    return draw(
        st.decimals(
            min_value=min_expenses.quantize(Decimal("0.01")),
            max_value=max_expenses.quantize(Decimal("0.01")),
            places=2,
        )
    )


class TestFlatRateComparisonProperties:
    """Property-based tests for flat-rate tax comparison."""

    @pytest.fixture
    def test_user(self, db: Session):
        """Create self-employed test user."""
        user = User(
            email="test@example.com",
            hashed_password="hashed",
            name="Test Self Employed User",
            user_type=UserType.SELF_EMPLOYED,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @pytest.fixture
    def comparator(self, db: Session):
        """Create comparator instance."""
        return FlatRateTaxComparator(db)

    @given(income=valid_income())
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_property_22_flat_rate_reduces_taxable_income(
        self, db: Session, test_user: User, comparator: FlatRateTaxComparator, income
    ):
        """
        Property 22: Flat-rate system reduces taxable income.

        Deemed expenses under flat-rate should be at least 6% or 13.5% of turnover.
        """
        tax_year = 2026

        db.query(Transaction).filter(Transaction.user_id == test_user.id).delete()
        db.commit()
        db.expire_all()

        txn = Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=income,
            transaction_date=date(tax_year, 6, 1),
            description="Self-employment income",
            income_category=IncomeCategory.SELF_EMPLOYMENT,
        )
        db.add(txn)

        expense_amount = max(Decimal("100.00"), income - Decimal("30000.00"))
        expense = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=expense_amount,
            transaction_date=date(tax_year, 6, 15),
            description="Business expense",
            expense_category=ExpenseCategory.OFFICE_SUPPLIES,
            is_deductible=True,
        )
        db.add(expense)
        db.commit()

        result = comparator.compare_methods(test_user.id, tax_year)

        if not result["eligible"]:
            return

        flat_6 = result["flat_rate_6_percent"]
        expected_deemed_6 = (income * Decimal("0.06")).quantize(Decimal("0.01"))
        assert Decimal(str(flat_6["deemed_expenses"])) == expected_deemed_6

        flat_13_5 = result["flat_rate_13_5_percent"]
        expected_deemed_13_5 = (income * Decimal("0.135")).quantize(Decimal("0.01"))
        assert Decimal(str(flat_13_5["deemed_expenses"])) == expected_deemed_13_5

    def test_property_22_basic_exemption_capped(
        self, db: Session, test_user: User, comparator: FlatRateTaxComparator
    ):
        """
        Property 22: Basic exemption is capped at EUR 4,950.

        15% basic exemption should not exceed the statutory maximum.
        """
        tax_year = 2026

        txn = Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=Decimal("50000.00"),
            transaction_date=date(tax_year, 6, 1),
            description="Self-employment income",
            income_category=IncomeCategory.SELF_EMPLOYMENT,
        )
        db.add(txn)

        expense = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("20000.00"),
            transaction_date=date(tax_year, 6, 15),
            description="Business expense",
            expense_category=ExpenseCategory.OFFICE_SUPPLIES,
            is_deductible=True,
        )
        db.add(expense)
        db.commit()

        result = comparator.compare_methods(test_user.id, tax_year)

        if not result["eligible"]:
            return

        max_exemption = Decimal("4950.00")
        assert Decimal(str(result["flat_rate_6_percent"]["basic_exemption"])) <= max_exemption
        assert Decimal(str(result["flat_rate_13_5_percent"]["basic_exemption"])) <= max_exemption

    def test_property_22_profit_threshold_enforcement(
        self, db: Session, test_user: User, comparator: FlatRateTaxComparator
    ):
        """
        Property 22: Profit threshold enforcement.

        Users with profit above EUR 33,000 should not be eligible for flat-rate.
        """
        tax_year = 2026

        txn = Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=Decimal("50000.00"),
            transaction_date=date(tax_year, 6, 1),
            description="Self-employment income",
            income_category=IncomeCategory.SELF_EMPLOYMENT,
        )
        db.add(txn)

        expense = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("5000.00"),
            transaction_date=date(tax_year, 6, 15),
            description="Business expense",
            expense_category=ExpenseCategory.OFFICE_SUPPLIES,
            is_deductible=True,
        )
        db.add(expense)
        db.commit()

        result = comparator.compare_methods(test_user.id, tax_year)
        profit = Decimal("50000.00") - Decimal("5000.00")

        if profit > Decimal("33000.00"):
            assert not result["eligible"]
            assert "reason" in result

    def test_property_22_comparison_consistency(
        self, db: Session, test_user: User, comparator: FlatRateTaxComparator
    ):
        """
        Property 22: Comparison consistency.

        The recommended method should have the lowest total tax.
        """
        tax_year = 2026

        txn = Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=Decimal("30000.00"),
            transaction_date=date(tax_year, 6, 1),
            description="Self-employment income",
            income_category=IncomeCategory.SELF_EMPLOYMENT,
        )
        db.add(txn)

        expense = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("5000.00"),
            transaction_date=date(tax_year, 6, 15),
            description="Business expense",
            expense_category=ExpenseCategory.OFFICE_SUPPLIES,
            is_deductible=True,
        )
        db.add(expense)
        db.commit()

        result = comparator.compare_methods(test_user.id, tax_year)

        if not result["eligible"]:
            return

        actual_tax = Decimal(str(result["actual_accounting"]["total_tax"]))
        flat_6_tax = Decimal(str(result["flat_rate_6_percent"]["total_tax"]))
        flat_13_5_tax = Decimal(str(result["flat_rate_13_5_percent"]["total_tax"]))
        recommended_tax = Decimal(str(result["recommendation"]["total_tax"]))

        assert recommended_tax == min(actual_tax, flat_6_tax, flat_13_5_tax)

    def test_property_22_employee_not_eligible(
        self, db: Session, comparator: FlatRateTaxComparator
    ):
        """
        Property 22: Employee eligibility.

        Employees should not be eligible for flat-rate tax.
        """
        employee = User(
            email="employee@example.com",
            hashed_password="hashed",
            name="Test Employee User",
            user_type=UserType.EMPLOYEE,
        )
        db.add(employee)
        db.commit()
        db.refresh(employee)

        income = Transaction(
            user_id=employee.id,
            type=TransactionType.INCOME,
            amount=Decimal("30000.00"),
            transaction_date=date(2026, 6, 1),
            description="Salary",
            income_category=IncomeCategory.EMPLOYMENT,
        )
        db.add(income)
        db.commit()

        result = comparator.compare_methods(employee.id, 2026)

        assert not result["eligible"]
        assert "only available for self-employed" in result["reason"].lower()
