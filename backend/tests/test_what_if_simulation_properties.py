"""
Property-Based Tests for What-If Simulation

Property 24: What-if simulation consistency
Validates Requirement 34.4
"""

import pytest
from decimal import Decimal
from datetime import datetime, date
from hypothesis import HealthCheck, given, strategies as st, assume, settings
from sqlalchemy.orm import Session

from app.models.user import User, UserType
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.services.what_if_simulator import WhatIfSimulator
from app.schemas.transaction import TransactionCreate


# Strategies
@st.composite
def transaction_amount(draw):
    """Generate valid transaction amounts"""
    return Decimal(str(draw(st.floats(min_value=0.01, max_value=100000.0))))


@st.composite
def expense_transaction(draw, tax_year: int):
    """Generate expense transaction for simulation"""
    return TransactionCreate(
        type=TransactionType.EXPENSE,
        amount=draw(transaction_amount()),
        transaction_date=date(tax_year, draw(st.integers(min_value=1, max_value=3)), 1),
        description=draw(st.text(min_size=5, max_size=50)),
        expense_category=draw(st.sampled_from(list(ExpenseCategory))),
        is_deductible=draw(st.booleans()),
        vat_rate=Decimal("0.20") if draw(st.booleans()) else None,
        vat_amount=None,
    )


class TestWhatIfSimulationProperties:
    """Property-based tests for what-if simulation"""

    @pytest.fixture
    def test_user(self, db: Session):
        """Create test user"""
        user = User(
            email="test@example.com",
            name="Test User",
            hashed_password="hashed",
            user_type=UserType.SELF_EMPLOYED,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @pytest.fixture
    def simulator(self, db: Session):
        """Create simulator instance"""
        return WhatIfSimulator(db)

    @given(
        expense=expense_transaction(2026),
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_property_24_add_expense_consistency(
        self, db: Session, test_user: User, simulator: WhatIfSimulator, expense
    ):
        """
        Property 24: What-if simulation consistency
        
        Adding a deductible expense should reduce tax or keep it the same.
        Adding a non-deductible expense should not increase tax.
        """
        tax_year = 2026
        
        # Add some base income
        income = Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=Decimal("50000.00"),
            transaction_date=date(tax_year, 1, 1),
            description="Base income",
            income_category=IncomeCategory.SELF_EMPLOYMENT,
        )
        db.add(income)
        db.commit()
        
        # Simulate adding expense
        result = simulator.simulate_add_expense(test_user.id, tax_year, expense)
        
        # Assertions
        assert result["scenario"] == "add_expense"
        assert "current_tax" in result
        assert "simulated_tax" in result
        assert "tax_difference" in result
        
        current_tax = Decimal(str(result["current_tax"]))
        simulated_tax = Decimal(str(result["simulated_tax"]))
        tax_difference = simulated_tax - current_tax
        
        # Property: If expense is deductible, tax should decrease or stay same
        if expense.is_deductible:
            assert tax_difference <= 0, (
                f"Adding deductible expense should not increase tax. "
                f"Current: {current_tax}, Simulated: {simulated_tax}"
            )
        
        # Property: Tax difference should be reasonable (not exceed expense amount)
        assert abs(tax_difference) <= expense.amount, (
            f"Tax difference ({abs(tax_difference)}) should not exceed "
            f"expense amount ({expense.amount})"
        )

    @given(
        income_change=st.decimals(
            min_value=Decimal("-10000"),
            max_value=Decimal("10000"),
            places=2,
        ),
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_property_24_income_change_monotonicity(
        self, db: Session, test_user: User, simulator: WhatIfSimulator, income_change
    ):
        """
        Property 24: Income change monotonicity
        
        Increasing income should increase tax (or keep it same).
        Decreasing income should decrease tax (or keep it same).
        """
        assume(income_change != 0)
        
        tax_year = 2026
        
        # Add base income
        base_income = Decimal("50000.00")
        income = Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=base_income,
            transaction_date=date(tax_year, 1, 1),
            description="Base income",
            income_category=IncomeCategory.SELF_EMPLOYMENT,
        )
        db.add(income)
        db.commit()
        
        # Simulate income change
        result = simulator.simulate_income_change(test_user.id, tax_year, income_change)
        
        # Assertions
        assert result["scenario"] == "income_change"
        
        current_tax = Decimal(str(result["current_tax"]))
        simulated_tax = Decimal(str(result["simulated_tax"]))
        tax_difference = simulated_tax - current_tax
        
        # Property: Increasing income should increase tax
        if income_change > 0:
            assert tax_difference >= 0, (
                f"Increasing income by {income_change} should not decrease tax. "
                f"Current: {current_tax}, Simulated: {simulated_tax}"
            )
        
        # Property: Decreasing income should decrease tax
        if income_change < 0:
            assert tax_difference <= 0, (
                f"Decreasing income by {income_change} should not increase tax. "
                f"Current: {current_tax}, Simulated: {simulated_tax}"
            )

    def test_property_24_simulation_idempotence(
        self, db: Session, test_user: User, simulator: WhatIfSimulator
    ):
        """
        Property 24: Simulation idempotence
        
        Running the same simulation multiple times should produce the same result.
        """
        tax_year = 2026
        
        # Add base income
        income = Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=Decimal("50000.00"),
            transaction_date=date(tax_year, 1, 1),
            description="Base income",
            income_category=IncomeCategory.SELF_EMPLOYMENT,
        )
        db.add(income)
        db.commit()
        
        # Create expense to simulate
        expense = TransactionCreate(
            type=TransactionType.EXPENSE,
            amount=Decimal("1000.00"),
            transaction_date=date(tax_year, 3, 15),
            description="Test expense",
            expense_category=ExpenseCategory.OFFICE_SUPPLIES,
            is_deductible=True,
        )
        
        # Run simulation multiple times
        result1 = simulator.simulate_add_expense(test_user.id, tax_year, expense)
        result2 = simulator.simulate_add_expense(test_user.id, tax_year, expense)
        result3 = simulator.simulate_add_expense(test_user.id, tax_year, expense)
        
        # Property: Results should be identical
        assert result1["current_tax"] == result2["current_tax"] == result3["current_tax"]
        assert result1["simulated_tax"] == result2["simulated_tax"] == result3["simulated_tax"]
        assert result1["tax_difference"] == result2["tax_difference"] == result3["tax_difference"]

    def test_property_24_simulation_does_not_modify_db(
        self, db: Session, test_user: User, simulator: WhatIfSimulator
    ):
        """
        Property 24: Simulation does not modify database
        
        What-if simulations should not create or modify actual transactions.
        """
        tax_year = 2026
        
        # Add base income
        income = Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=Decimal("50000.00"),
            transaction_date=date(tax_year, 1, 1),
            description="Base income",
            income_category=IncomeCategory.SELF_EMPLOYMENT,
        )
        db.add(income)
        db.commit()
        
        # Count transactions before simulation
        count_before = db.query(Transaction).filter(
            Transaction.user_id == test_user.id
        ).count()
        
        # Create expense to simulate
        expense = TransactionCreate(
            type=TransactionType.EXPENSE,
            amount=Decimal("1000.00"),
            transaction_date=date(tax_year, 3, 15),
            description="Test expense",
            expense_category=ExpenseCategory.OFFICE_SUPPLIES,
            is_deductible=True,
        )
        
        # Run simulation
        simulator.simulate_add_expense(test_user.id, tax_year, expense)
        
        # Count transactions after simulation
        count_after = db.query(Transaction).filter(
            Transaction.user_id == test_user.id
        ).count()
        
        # Property: Transaction count should not change
        assert count_before == count_after, (
            "Simulation should not create actual transactions in database"
        )
