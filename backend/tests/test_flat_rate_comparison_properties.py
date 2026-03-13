"""
Property-Based Tests for Flat-Rate Tax Comparison

Property 22: Flat-rate tax comparison calculation
Validates Requirements 31.1, 31.2, 31.3, 31.4
"""

import pytest
from decimal import Decimal
from datetime import date
from hypothesis import given, strategies as st, assume, settings
from sqlalchemy.orm import Session

from app.models.user import User, UserType
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.services.flat_rate_tax_comparator import FlatRateTaxComparator


# Strategies
@st.composite
def valid_income(draw):
    """Generate valid income amounts for flat-rate eligibility"""
    # Must result in profit <= €33,000
    return Decimal(str(draw(st.floats(min_value=1000.0, max_value=50000.0))))


@st.composite
def valid_expenses(draw, income: Decimal):
    """Generate expenses that keep profit within limits"""
    # Ensure profit <= €33,000
    max_expenses = income - Decimal("1000.00")  # Keep some profit
    min_expenses = max(Decimal("0"), income - Decimal("33000.00"))
    
    if min_expenses >= max_expenses:
        return min_expenses
    
    return Decimal(str(draw(st.floats(
        min_value=float(min_expenses),
        max_value=float(max_expenses)
    ))))


class TestFlatRateComparisonProperties:
    """Property-based tests for flat-rate tax comparison"""

    @pytest.fixture
    def test_user(self, db: Session):
        """Create self-employed test user"""
        user = User(
            email="test@example.com",
            hashed_password="hashed",
            user_type=UserType.SELF_EMPLOYED,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @pytest.fixture
    def comparator(self, db: Session):
        """Create comparator instance"""
        return FlatRateTaxComparator(db)

    @given(
        income=valid_income(),
    )
    @settings(max_examples=50, deadline=None)
    def test_property_22_flat_rate_reduces_taxable_income(
        self, db: Session, test_user: User, comparator: FlatRateTaxComparator, income
    ):
        """
        Property 22: Flat-rate system reduces taxable income
        
        Deemed expenses under flat-rate should be at least 6% or 12% of turnover.
        """
        tax_year = 2026
        
        # Add income
        txn = Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=income,
            date=date(tax_year, 6, 1),
            description="Self-employment income",
            income_category=IncomeCategory.SELF_EMPLOYMENT,
        )
        db.add(txn)
        
        # Add minimal expenses to stay under profit threshold
        expense_amount = max(Decimal("100.00"), income - Decimal("30000.00"))
        expense = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=expense_amount,
            date=date(tax_year, 6, 15),
            description="Business expense",
            expense_category=ExpenseCategory.OFFICE_SUPPLIES,
            is_deductible=True,
        )
        db.add(expense)
        db.commit()
        
        # Compare methods
        result = comparator.compare_methods(test_user.id, tax_year)
        
        if not result["eligible"]:
            # Skip if not eligible
            return
        
        # Property: 6% flat-rate deemed expenses should be at least 6% of income
        flat_6 = result["flat_rate_6_percent"]
        expected_deemed_6 = income * Decimal("0.06")
        assert Decimal(str(flat_6["deemed_expenses"])) == expected_deemed_6.quantize(
            Decimal("0.01")
        ), f"6% deemed expenses should be {expected_deemed_6}"
        
        # Property: 13.5% flat-rate deemed expenses should be 13.5% of income
        flat_13_5 = result["flat_rate_13_5_percent"]
        expected_deemed_13_5 = income * Decimal("0.135")
        assert Decimal(str(flat_13_5["deemed_expenses"])) == expected_deemed_13_5.quantize(
            Decimal("0.01")
        ), f"13.5% deemed expenses should be {expected_deemed_13_5}"

    def test_property_22_basic_exemption_capped(
        self, db: Session, test_user: User, comparator: FlatRateTaxComparator
    ):
        """
        Property 22: Basic exemption is capped at €4,950
        
        15% basic exemption should not exceed €4,950.
        """
        tax_year = 2026
        
        # Add high income to test cap
        income = Decimal("50000.00")
        txn = Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=income,
            date=date(tax_year, 6, 1),
            description="Self-employment income",
            income_category=IncomeCategory.SELF_EMPLOYMENT,
        )
        db.add(txn)
        
        # Add expenses to keep profit under threshold
        expense = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("20000.00"),
            date=date(tax_year, 6, 15),
            description="Business expense",
            expense_category=ExpenseCategory.OFFICE_SUPPLIES,
            is_deductible=True,
        )
        db.add(expense)
        db.commit()
        
        # Compare methods
        result = comparator.compare_methods(test_user.id, tax_year)
        
        if not result["eligible"]:
            return
        
        # Property: Basic exemption should not exceed €4,950
        max_exemption = Decimal("4950.00")
        
        flat_6 = result["flat_rate_6_percent"]
        assert Decimal(str(flat_6["basic_exemption"])) <= max_exemption, (
            f"Basic exemption should not exceed €{max_exemption}"
        )
        
        flat_13_5 = result["flat_rate_13_5_percent"]
        assert Decimal(str(flat_13_5["basic_exemption"])) <= max_exemption, (
            f"Basic exemption should not exceed €{max_exemption}"
        )

    def test_property_22_profit_threshold_enforcement(
        self, db: Session, test_user: User, comparator: FlatRateTaxComparator
    ):
        """
        Property 22: Profit threshold enforcement
        
        Users with profit > €33,000 should not be eligible for flat-rate.
        """
        tax_year = 2026
        
        # Add income and minimal expenses to exceed profit threshold
        income = Decimal("50000.00")
        txn = Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=income,
            date=date(tax_year, 6, 1),
            description="Self-employment income",
            income_category=IncomeCategory.SELF_EMPLOYMENT,
        )
        db.add(txn)
        
        # Add small expense to ensure profit > €33,000
        expense = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("5000.00"),
            date=date(tax_year, 6, 15),
            description="Business expense",
            expense_category=ExpenseCategory.OFFICE_SUPPLIES,
            is_deductible=True,
        )
        db.add(expense)
        db.commit()
        
        # Compare methods
        result = comparator.compare_methods(test_user.id, tax_year)
        
        # Calculate actual profit
        profit = income - Decimal("5000.00")
        
        # Property: If profit > €33,000, should not be eligible
        if profit > Decimal("33000.00"):
            assert not result["eligible"], (
                f"Should not be eligible with profit {profit} > €33,000"
            )
            assert "reason" in result

    def test_property_22_comparison_consistency(
        self, db: Session, test_user: User, comparator: FlatRateTaxComparator
    ):
        """
        Property 22: Comparison consistency
        
        The recommended method should have the lowest total tax.
        """
        tax_year = 2026
        
        # Add income and expenses
        income = Decimal("30000.00")
        txn = Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=income,
            date=date(tax_year, 6, 1),
            description="Self-employment income",
            income_category=IncomeCategory.SELF_EMPLOYMENT,
        )
        db.add(txn)
        
        expense = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("5000.00"),
            date=date(tax_year, 6, 15),
            description="Business expense",
            expense_category=ExpenseCategory.OFFICE_SUPPLIES,
            is_deductible=True,
        )
        db.add(expense)
        db.commit()
        
        # Compare methods
        result = comparator.compare_methods(test_user.id, tax_year)
        
        if not result["eligible"]:
            return
        
        # Get all tax amounts
        actual_tax = Decimal(str(result["actual_accounting"]["total_tax"]))
        flat_6_tax = Decimal(str(result["flat_rate_6_percent"]["total_tax"]))
        flat_13_5_tax = Decimal(str(result["flat_rate_13_5_percent"]["total_tax"]))
        
        # Get recommended method
        recommended = result["recommendation"]
        recommended_tax = Decimal(str(recommended["total_tax"]))
        
        # Property: Recommended method should have lowest tax
        min_tax = min(actual_tax, flat_6_tax, flat_13_5_tax)
        assert recommended_tax == min_tax, (
            f"Recommended method tax ({recommended_tax}) should be "
            f"the minimum ({min_tax})"
        )

    def test_property_22_employee_not_eligible(
        self, db: Session, comparator: FlatRateTaxComparator
    ):
        """
        Property 22: Employee eligibility
        
        Employees should not be eligible for flat-rate tax.
        """
        # Create employee user
        employee = User(
            email="employee@example.com",
            hashed_password="hashed",
            user_type=UserType.EMPLOYEE,
        )
        db.add(employee)
        db.commit()
        db.refresh(employee)
        
        tax_year = 2026
        
        # Add income
        income = Transaction(
            user_id=employee.id,
            type=TransactionType.INCOME,
            amount=Decimal("30000.00"),
            date=date(tax_year, 6, 1),
            description="Salary",
            income_category=IncomeCategory.EMPLOYMENT,
        )
        db.add(income)
        db.commit()
        
        # Compare methods
        result = comparator.compare_methods(employee.id, tax_year)
        
        # Property: Employees should not be eligible
        assert not result["eligible"], "Employees should not be eligible for flat-rate tax"
        assert "only available for self-employed" in result["reason"].lower()
