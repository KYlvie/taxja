"""
What-If Tax Simulator Service

Simulates tax impact of adding/removing transactions or changing income.
Validates Requirement 34.4.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict

from sqlalchemy import extract
from sqlalchemy.orm import Session

from app.models.transaction import IncomeCategory, Transaction, TransactionType
from app.models.transaction_line_item import LineItemPostingType
from app.schemas.transaction import TransactionCreate
from app.services.posting_line_utils import sum_postings, transaction_has_deductible_expense
from app.services.tax_calculation_engine import TaxCalculationEngine


@dataclass
class SimulationSnapshot:
    """Minimal snapshot for what-if comparisons."""

    total_tax: Decimal
    total_income: Decimal
    deductible_expenses: Decimal
    vat: Decimal = Decimal("0.00")
    svs: Decimal = Decimal("0.00")


class WhatIfSimulator:
    """Simulates tax scenarios for what-if analysis."""

    def __init__(self, db: Session):
        self.db = db
        self.tax_engine = TaxCalculationEngine(db)

    def _calculate_snapshot(
        self,
        user_id: int,
        tax_year: int,
        *,
        additional_transactions: list[Transaction] | None = None,
        exclude_transaction_ids: list[int] | None = None,
        income_adjustment: Decimal = Decimal("0.00"),
    ) -> SimulationSnapshot:
        """Calculate a lightweight income-tax-only snapshot for a user/year."""
        query = self.db.query(Transaction).filter(
            Transaction.user_id == user_id,
            extract("year", Transaction.transaction_date) == tax_year,
        )
        if exclude_transaction_ids:
            query = query.filter(~Transaction.id.in_(exclude_transaction_ids))

        transactions = list(query.all())
        if additional_transactions:
            transactions.extend(additional_transactions)

        total_income = sum_postings(
            transactions,
            posting_types={LineItemPostingType.INCOME},
            include_private_use=False,
        ) + Decimal(str(income_adjustment))
        if total_income < Decimal("0.00"):
            total_income = Decimal("0.00")

        deductible_expenses = sum_postings(
            transactions,
            posting_types={LineItemPostingType.EXPENSE},
            deductible_only=True,
            include_private_use=False,
        )

        taxable_income = max(total_income - deductible_expenses, Decimal("0.00"))
        income_tax_calc, _, _, _, _ = self.tax_engine._get_calculators_for_year(tax_year)
        income_tax = income_tax_calc.calculate_tax_with_exemption(taxable_income, tax_year)

        return SimulationSnapshot(
            total_tax=income_tax.total_tax,
            total_income=total_income,
            deductible_expenses=deductible_expenses,
        )

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
        current_result = self._calculate_snapshot(user_id, tax_year)

        temp_expense = Transaction(
            user_id=user_id,
            type=TransactionType.EXPENSE,
            amount=expense.amount,
            transaction_date=expense.transaction_date,
            description=expense.description,
            expense_category=expense.expense_category,
            is_deductible=expense.is_deductible,
            vat_rate=expense.vat_rate,
            vat_amount=expense.vat_amount,
        )

        simulated_result = self._calculate_snapshot(
            user_id,
            tax_year,
            additional_transactions=[temp_expense],
        )

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
                    "income_tax": float(current_result.total_tax),
                    "vat": float(current_result.vat),
                    "svs": float(current_result.svs),
                },
                "simulated": {
                    "income_tax": float(simulated_result.total_tax),
                    "vat": float(simulated_result.vat),
                    "svs": float(simulated_result.svs),
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
        transaction = (
            self.db.query(Transaction)
            .filter(
                Transaction.id == transaction_id,
                Transaction.user_id == user_id,
            )
            .first()
        )

        if not transaction or not (
            transaction.type == TransactionType.EXPENSE
            or transaction_has_deductible_expense(transaction)
        ):
            raise ValueError("Transaction not found or not an expense")

        current_result = self._calculate_snapshot(user_id, tax_year)
        simulated_result = self._calculate_snapshot(
            user_id,
            tax_year,
            exclude_transaction_ids=[transaction_id],
        )

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
                    "income_tax": float(current_result.total_tax),
                    "vat": float(current_result.vat),
                    "svs": float(current_result.svs),
                },
                "simulated": {
                    "income_tax": float(simulated_result.total_tax),
                    "vat": float(simulated_result.vat),
                    "svs": float(simulated_result.svs),
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
        current_result = self._calculate_snapshot(user_id, tax_year)

        temp_income = Transaction(
            user_id=user_id,
            type=TransactionType.INCOME,
            amount=abs(income_change),
            transaction_date=datetime(tax_year, 12, 31).date(),
            description=f"Simulated income change: {income_change:+.2f}",
            income_category=IncomeCategory.OTHER_INCOME,
        )

        if income_change > 0:
            simulated_result = self._calculate_snapshot(
                user_id,
                tax_year,
                additional_transactions=[temp_income],
            )
        else:
            simulated_result = self._simulate_income_reduction(
                user_id, tax_year, abs(income_change)
            )

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
                    "income_tax": float(current_result.total_tax),
                    "vat": float(current_result.vat),
                    "svs": float(current_result.svs),
                },
                "simulated": {
                    "income_tax": float(simulated_result.total_tax),
                    "vat": float(simulated_result.vat),
                    "svs": float(simulated_result.svs),
                },
            },
        }

    def _simulate_income_reduction(
        self, user_id: int, tax_year: int, reduction_amount: Decimal
    ) -> SimulationSnapshot:
        """Simulate income reduction by lowering the current-year income base."""
        return self._calculate_snapshot(
            user_id,
            tax_year,
            income_adjustment=-reduction_amount,
        )

    def _generate_expense_explanation(
        self, expense: TransactionCreate, tax_difference: Decimal, savings: Decimal
    ) -> str:
        """Generate explanation for expense simulation."""
        if savings > 0:
            return (
                f"Adding this â‚¬{expense.amount:.2f} expense would save you "
                f"â‚¬{savings:.2f} in taxes. "
                f"{'This expense is tax-deductible.' if expense.is_deductible else 'This expense is not deductible but may affect VAT calculations.'}"
            )
        return (
            f"Adding this â‚¬{expense.amount:.2f} expense would not reduce your taxes. "
            f"{'Consider if this expense is correctly categorized as deductible.' if expense.is_deductible else 'This expense is not tax-deductible.'}"
        )

    def _generate_remove_explanation(
        self, transaction: Transaction, tax_difference: Decimal, additional_tax: Decimal
    ) -> str:
        """Generate explanation for expense removal simulation."""
        if additional_tax > 0:
            return (
                f"Removing this â‚¬{transaction.amount:.2f} expense would increase "
                f"your taxes by â‚¬{additional_tax:.2f}. "
                f"This expense is currently reducing your tax liability."
            )
        return (
            f"Removing this â‚¬{transaction.amount:.2f} expense would not affect "
            f"your taxes. This expense is not currently providing tax benefits."
        )

    def _generate_income_change_explanation(
        self,
        income_change: Decimal,
        tax_difference: Decimal,
        current_result: SimulationSnapshot,
        simulated_result: SimulationSnapshot,
    ) -> str:
        """Generate explanation for income change simulation."""
        if income_change > 0:
            effective_rate = (
                (tax_difference / income_change * 100)
                if income_change != 0
                else Decimal("0")
            )
            return (
                f"Increasing your income by â‚¬{income_change:.2f} would increase "
                f"your taxes by â‚¬{tax_difference:.2f} "
                f"(effective rate: {effective_rate:.1f}%). "
                f"Your net gain would be â‚¬{income_change - tax_difference:.2f}."
            )
        return (
            f"Decreasing your income by â‚¬{abs(income_change):.2f} would decrease "
            f"your taxes by â‚¬{abs(tax_difference):.2f}. "
            f"Your net loss would be â‚¬{abs(income_change) - abs(tax_difference):.2f}."
        )
