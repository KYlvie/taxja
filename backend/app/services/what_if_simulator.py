"""
What-If Tax Simulator Service

Simulates tax impact of adding/removing transactions or changing income.
Validates Requirement 34.4.
"""

from decimal import Decimal
from typing import List, Optional, Dict, Any
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.services.tax_calculation_engine import TaxCalculationEngine
from app.schemas.transaction import TransactionCreate


class WhatIfSimulator:
    """Simulates tax scenarios for what-if analysis"""

    def __init__(self, db: Session):
        self.db = db
        self.tax_engine = TaxCalculationEngine(db)

    def simulate_add_expense(
        self,
        user_id: int,
        tax_year: int,
        expense: TransactionCreate,
    ) -> Dict[str, Any]:
        """
        Simulate adding an expense and calculate tax difference.

        Args:
            user_id: User ID
            tax_year: Tax year
            expense: Expense transaction to simulate

        Returns:
            Simulation result with tax difference and explanation
        """
        # Calculate current tax
        current_result = self.tax_engine.calculate_total_tax(user_id, tax_year)

        # Create temporary expense (not saved to DB)
        temp_expense = Transaction(
            user_id=user_id,
            type=TransactionType.EXPENSE,
            amount=expense.amount,
            date=expense.date,
            description=expense.description,
            expense_category=expense.expense_category,
            is_deductible=expense.is_deductible,
            vat_rate=expense.vat_rate,
            vat_amount=expense.vat_amount,
        )

        # Calculate tax with simulated expense
        simulated_result = self.tax_engine.calculate_total_tax(
            user_id, tax_year, additional_transactions=[temp_expense]
        )

        # Calculate difference
        tax_difference = simulated_result.total_tax - current_result.total_tax
        savings = -tax_difference if tax_difference < 0 else Decimal("0")

        return {
            "scenario": "add_expense",
            "current_tax": float(current_result.total_tax),
            "simulated_tax": float(simulated_result.total_tax),
            "tax_difference": float(tax_difference),
            "savings": float(savings),
            "expense_amount": float(expense.amount),
            "explanation": self._generate_expense_explanation(
                expense, tax_difference, savings
            ),
            "breakdown": {
                "current": {
                    "income_tax": float(current_result.income_tax),
                    "vat": float(current_result.vat),
                    "svs": float(current_result.svs_contributions),
                },
                "simulated": {
                    "income_tax": float(simulated_result.income_tax),
                    "vat": float(simulated_result.vat),
                    "svs": float(simulated_result.svs_contributions),
                },
            },
        }

    def simulate_remove_expense(
        self, user_id: int, tax_year: int, transaction_id: int
    ) -> Dict[str, Any]:
        """
        Simulate removing an expense and calculate tax difference.

        Args:
            user_id: User ID
            tax_year: Tax year
            transaction_id: Transaction ID to remove

        Returns:
            Simulation result with tax difference and explanation
        """
        # Get the transaction
        transaction = (
            self.db.query(Transaction)
            .filter(
                Transaction.id == transaction_id,
                Transaction.user_id == user_id,
                Transaction.type == TransactionType.EXPENSE,
            )
            .first()
        )

        if not transaction:
            raise ValueError("Transaction not found or not an expense")

        # Calculate current tax
        current_result = self.tax_engine.calculate_total_tax(user_id, tax_year)

        # Calculate tax without this expense
        simulated_result = self.tax_engine.calculate_total_tax(
            user_id, tax_year, exclude_transaction_ids=[transaction_id]
        )

        # Calculate difference
        tax_difference = simulated_result.total_tax - current_result.total_tax
        additional_tax = tax_difference if tax_difference > 0 else Decimal("0")

        return {
            "scenario": "remove_expense",
            "current_tax": float(current_result.total_tax),
            "simulated_tax": float(simulated_result.total_tax),
            "tax_difference": float(tax_difference),
            "additional_tax": float(additional_tax),
            "expense_amount": float(transaction.amount),
            "explanation": self._generate_remove_explanation(
                transaction, tax_difference, additional_tax
            ),
            "breakdown": {
                "current": {
                    "income_tax": float(current_result.income_tax),
                    "vat": float(current_result.vat),
                    "svs": float(current_result.svs_contributions),
                },
                "simulated": {
                    "income_tax": float(simulated_result.income_tax),
                    "vat": float(simulated_result.vat),
                    "svs": float(simulated_result.svs_contributions),
                },
            },
        }

    def simulate_income_change(
        self, user_id: int, tax_year: int, income_change: Decimal
    ) -> Dict[str, Any]:
        """
        Simulate income change and calculate tax difference.

        Args:
            user_id: User ID
            tax_year: Tax year
            income_change: Income change amount (positive or negative)

        Returns:
            Simulation result with tax difference and explanation
        """
        # Calculate current tax
        current_result = self.tax_engine.calculate_total_tax(user_id, tax_year)

        # Create temporary income transaction
        temp_income = Transaction(
            user_id=user_id,
            type=TransactionType.INCOME,
            amount=abs(income_change),
            date=datetime(tax_year, 12, 31),
            description=f"Simulated income change: {income_change:+.2f}",
            income_category=None,  # Will be determined by classifier
        )

        # Calculate tax with simulated income change
        if income_change > 0:
            simulated_result = self.tax_engine.calculate_total_tax(
                user_id, tax_year, additional_transactions=[temp_income]
            )
        else:
            # For negative income change, we need to reduce income
            # This is more complex and requires adjusting existing income
            simulated_result = self._simulate_income_reduction(
                user_id, tax_year, abs(income_change)
            )

        # Calculate difference
        tax_difference = simulated_result.total_tax - current_result.total_tax

        return {
            "scenario": "income_change",
            "current_tax": float(current_result.total_tax),
            "simulated_tax": float(simulated_result.total_tax),
            "tax_difference": float(tax_difference),
            "income_change": float(income_change),
            "current_income": float(current_result.total_income),
            "simulated_income": float(simulated_result.total_income),
            "explanation": self._generate_income_change_explanation(
                income_change, tax_difference, current_result, simulated_result
            ),
            "breakdown": {
                "current": {
                    "income_tax": float(current_result.income_tax),
                    "vat": float(current_result.vat),
                    "svs": float(current_result.svs_contributions),
                },
                "simulated": {
                    "income_tax": float(simulated_result.income_tax),
                    "vat": float(simulated_result.vat),
                    "svs": float(simulated_result.svs_contributions),
                },
            },
        }

    def _simulate_income_reduction(
        self, user_id: int, tax_year: int, reduction_amount: Decimal
    ):
        """Simulate income reduction by proportionally reducing all income transactions"""
        # This is a simplified implementation
        # In practice, you might want to reduce specific income sources
        return self.tax_engine.calculate_total_tax(
            user_id, tax_year, income_adjustment=-reduction_amount
        )

    def _generate_expense_explanation(
        self, expense: TransactionCreate, tax_difference: Decimal, savings: Decimal
    ) -> str:
        """Generate explanation for expense simulation"""
        if savings > 0:
            return (
                f"Adding this €{expense.amount:.2f} expense would save you "
                f"€{savings:.2f} in taxes. "
                f"{'This expense is tax-deductible.' if expense.is_deductible else 'This expense is not deductible but may affect VAT calculations.'}"
            )
        else:
            return (
                f"Adding this €{expense.amount:.2f} expense would not reduce your taxes. "
                f"{'Consider if this expense is correctly categorized as deductible.' if expense.is_deductible else 'This expense is not tax-deductible.'}"
            )

    def _generate_remove_explanation(
        self, transaction: Transaction, tax_difference: Decimal, additional_tax: Decimal
    ) -> str:
        """Generate explanation for expense removal simulation"""
        if additional_tax > 0:
            return (
                f"Removing this €{transaction.amount:.2f} expense would increase "
                f"your taxes by €{additional_tax:.2f}. "
                f"This expense is currently reducing your tax liability."
            )
        else:
            return (
                f"Removing this €{transaction.amount:.2f} expense would not affect "
                f"your taxes. This expense is not currently providing tax benefits."
            )

    def _generate_income_change_explanation(
        self,
        income_change: Decimal,
        tax_difference: Decimal,
        current_result,
        simulated_result,
    ) -> str:
        """Generate explanation for income change simulation"""
        if income_change > 0:
            effective_rate = (
                (tax_difference / income_change * 100)
                if income_change != 0
                else Decimal("0")
            )
            return (
                f"Increasing your income by €{income_change:.2f} would increase "
                f"your taxes by €{tax_difference:.2f} "
                f"(effective rate: {effective_rate:.1f}%). "
                f"Your net gain would be €{income_change - tax_difference:.2f}."
            )
        else:
            return (
                f"Decreasing your income by €{abs(income_change):.2f} would decrease "
                f"your taxes by €{abs(tax_difference):.2f}. "
                f"Your net loss would be €{abs(income_change) - abs(tax_difference):.2f}."
            )
