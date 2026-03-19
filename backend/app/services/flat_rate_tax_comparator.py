"""
Flat-Rate Tax Comparison Service

Compares actual accounting (Einnahmen-Ausgaben-Rechnung) vs flat-rate system (Pauschalierung).
Validates Requirements 31.1-31.6.
"""

from decimal import Decimal
from typing import Dict, Any, Optional
from enum import Enum

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.models.user import User, UserType
from app.models.transaction import Transaction, TransactionType
from app.services.tax_calculation_engine import TaxCalculationEngine
class FlatRateType(str, Enum):
    """Flat-rate tax types"""

    BASIC_6 = "basic_6"  # 6% of turnover
    BASIC_13_5 = "basic_13_5"  # 13.5% of turnover (2025+)
    NOT_ELIGIBLE = "not_eligible"


class FlatRateTaxComparator:
    """Compares actual accounting vs flat-rate tax system"""

    # Flat-rate thresholds and rates
    PROFIT_THRESHOLD = Decimal("33000.00")  # €33,000 profit limit
    TURNOVER_THRESHOLD = Decimal("320000.00")  # €320,000 turnover limit for Basispauschalierung
    BASIC_EXEMPTION_RATE = Decimal("0.15")  # 15% basic exemption
    MAX_BASIC_EXEMPTION = Decimal("4950.00")  # Max €4,950
    FLAT_RATE_6_PERCENT = Decimal("0.06")
    FLAT_RATE_13_5_PERCENT = Decimal("0.135")
    CENTS = Decimal("0.01")

    def __init__(self, db: Session):
        self.db = db
        self.tax_engine = TaxCalculationEngine(db)
        self.income_tax_calc = self.tax_engine.income_tax_calculator

    def compare_methods(
        self, user_id: int, tax_year: int
    ) -> Dict[str, Any]:
        """
        Compare actual accounting vs flat-rate tax methods.

        Args:
            user_id: User ID
            tax_year: Tax year

        Returns:
            Comparison result with recommendations
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        # Check eligibility
        eligibility = self._check_eligibility(user, user_id, tax_year)
        if not eligibility["eligible"]:
            return {
                "eligible": False,
                "reason": eligibility["reason"],
                "actual_accounting": self._calculate_actual_accounting(
                    user_id, tax_year
                ),
            }

        # Calculate both methods
        actual_result = self._calculate_actual_accounting(user_id, tax_year)
        flat_rate_6_result = self._calculate_flat_rate(
            user_id, tax_year, FlatRateType.BASIC_6
        )
        flat_rate_13_5_result = self._calculate_flat_rate(
            user_id, tax_year, FlatRateType.BASIC_13_5
        )

        # Determine best method
        best_method = self._determine_best_method(
            actual_result, flat_rate_6_result, flat_rate_13_5_result
        )

        return {
            "eligible": True,
            "tax_year": tax_year,
            "actual_accounting": actual_result,
            "flat_rate_6_percent": flat_rate_6_result,
            "flat_rate_13_5_percent": flat_rate_13_5_result,
            "recommendation": best_method,
            "comparison_summary": self._generate_comparison_summary(
                actual_result, flat_rate_6_result, flat_rate_13_5_result, best_method
            ),
        }

    def _check_eligibility(
        self, user: User, user_id: int, tax_year: int
    ) -> Dict[str, Any]:
        """Check if user is eligible for flat-rate tax"""
        # Only self-employed can use flat-rate
        if user.user_type not in [UserType.SELF_EMPLOYED, UserType.MIXED]:
            return {
                "eligible": False,
                "reason": "Flat-rate tax is only available for self-employed individuals",
            }

        turnover, deductible_expenses = self._get_income_and_expenses(user_id, tax_year)
        profit = turnover - deductible_expenses

        # Check turnover threshold for Basispauschalierung
        if turnover > self.TURNOVER_THRESHOLD:
            return {
                "eligible": False,
                "reason": f"Turnover (€{turnover:.2f}) exceeds €{self.TURNOVER_THRESHOLD:.2f} threshold for Basispauschalierung",
            }

        # Check profit threshold
        if profit > self.PROFIT_THRESHOLD:
            return {
                "eligible": False,
                "reason": f"Profit (€{profit:.2f}) exceeds €{self.PROFIT_THRESHOLD:.2f} threshold",
            }

        return {"eligible": True, "profit": float(profit)}

    def _calculate_actual_accounting(
        self, user_id: int, tax_year: int
    ) -> Dict[str, Any]:
        """Calculate tax under actual accounting (Einnahmen-Ausgaben-Rechnung)"""
        turnover, deductible_expenses = self._get_income_and_expenses(user_id, tax_year)
        profit = max(turnover - deductible_expenses, Decimal("0.00"))
        income_tax = self.income_tax_calc.calculate_progressive_tax(profit, tax_year)
        total_tax = income_tax.total_tax

        return {
            "method": "Einnahmen-Ausgaben-Rechnung (Actual Accounting)",
            "total_income": float(turnover.quantize(self.CENTS)),
            "total_expenses": float(deductible_expenses.quantize(self.CENTS)),
            "profit": float(profit.quantize(self.CENTS)),
            "income_tax": float(income_tax.total_tax.quantize(self.CENTS)),
            "vat": 0.0,
            "svs": 0.0,
            "total_tax": float(total_tax.quantize(self.CENTS)),
            "net_income": float((turnover - total_tax).quantize(self.CENTS)),
        }

    def _calculate_flat_rate(
        self, user_id: int, tax_year: int, flat_rate_type: FlatRateType
    ) -> Dict[str, Any]:
        """Calculate tax under flat-rate system (Pauschalierung)"""
        # Get total turnover (income)
        turnover, _ = self._get_income_and_expenses(user_id, tax_year)

        # Determine flat rate
        if flat_rate_type == FlatRateType.BASIC_6:
            flat_rate = self.FLAT_RATE_6_PERCENT
            rate_label = "6%"
        else:
            flat_rate = self.FLAT_RATE_13_5_PERCENT
            rate_label = "13.5%"

        # Calculate deemed expenses
        deemed_expenses = turnover * flat_rate

        # Calculate profit
        profit = turnover - deemed_expenses

        # Apply basic exemption (15% of profit, max €4,950)
        basic_exemption = min(
            profit * self.BASIC_EXEMPTION_RATE, self.MAX_BASIC_EXEMPTION
        )
        taxable_profit = max(profit - basic_exemption, Decimal("0.00"))

        # Calculate income tax on taxable profit
        tax_result = self.income_tax_calc.calculate_progressive_tax(
            taxable_profit, tax_year
        )

        # Keep this comparator focused on income-tax comparison until VAT/SVS
        # are modeled consistently for the current user/profile schema.
        svs = Decimal("0.00")
        vat = Decimal("0.00")

        total_tax = tax_result.total_tax + svs + vat
        net_income = turnover - total_tax

        return {
            "method": f"Pauschalierung ({rate_label} Flat-Rate)",
            "flat_rate_percentage": rate_label,
            "total_income": float(turnover.quantize(self.CENTS)),
            "deemed_expenses": float(deemed_expenses.quantize(self.CENTS)),
            "profit": float(profit.quantize(self.CENTS)),
            "basic_exemption": float(basic_exemption.quantize(self.CENTS)),
            "taxable_profit": float(taxable_profit.quantize(self.CENTS)),
            "income_tax": float(tax_result.total_tax.quantize(self.CENTS)),
            "vat": float(vat),
            "svs": float(svs),
            "total_tax": float(total_tax.quantize(self.CENTS)),
            "net_income": float(net_income.quantize(self.CENTS)),
        }

    def _get_income_and_expenses(
        self, user_id: int, tax_year: int
    ) -> tuple[Decimal, Decimal]:
        """Aggregate annual turnover and deductible expenses from transactions."""
        turnover = self.db.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.INCOME,
            extract("year", Transaction.transaction_date) == tax_year,
        ).scalar()

        deductible_expenses = self.db.query(
            func.coalesce(func.sum(Transaction.amount), 0)
        ).filter(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.EXPENSE,
            Transaction.is_deductible.is_(True),
            extract("year", Transaction.transaction_date) == tax_year,
        ).scalar()

        return Decimal(str(turnover or 0)), Decimal(str(deductible_expenses or 0))

    def _determine_best_method(
        self,
        actual: Dict[str, Any],
        flat_6: Dict[str, Any],
        flat_12: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Determine which method results in lowest tax"""
        methods = [
            {"name": "actual_accounting", "data": actual},
            {"name": "flat_rate_6", "data": flat_6},
            {"name": "flat_rate_13_5", "data": flat_12},
        ]

        # Sort by total tax (ascending)
        methods.sort(key=lambda x: x["data"]["total_tax"])

        best = methods[0]
        savings_vs_actual = actual["total_tax"] - best["data"]["total_tax"]

        return {
            "best_method": best["name"],
            "method_label": best["data"]["method"],
            "total_tax": best["data"]["total_tax"],
            "net_income": best["data"]["net_income"],
            "savings_vs_actual": float(savings_vs_actual),
            "explanation": self._generate_recommendation_explanation(
                best["name"], savings_vs_actual, actual, best["data"]
            ),
        }

    def _generate_recommendation_explanation(
        self,
        best_method: str,
        savings: Decimal,
        actual: Dict[str, Any],
        best: Dict[str, Any],
    ) -> str:
        """Generate explanation for recommendation"""
        if best_method == "actual_accounting":
            return (
                f"Actual accounting (Einnahmen-Ausgaben-Rechnung) is recommended. "
                f"Your actual expenses (€{actual['total_expenses']:.2f}) provide "
                f"better tax benefits than flat-rate deductions."
            )
        elif best_method == "flat_rate_6":
            return (
                f"6% flat-rate system is recommended. "
                f"You would save €{savings:.2f} compared to actual accounting. "
                f"Deemed expenses (€{best['deemed_expenses']:.2f}) exceed your "
                f"actual expenses (€{actual['total_expenses']:.2f})."
            )
        else:
            return (
                f"13.5% flat-rate system is recommended. "
                f"You would save €{savings:.2f} compared to actual accounting. "
                f"Deemed expenses (€{best['deemed_expenses']:.2f}) exceed your "
                f"actual expenses (€{actual['total_expenses']:.2f})."
            )

    def _generate_comparison_summary(
        self,
        actual: Dict[str, Any],
        flat_6: Dict[str, Any],
        flat_12: Dict[str, Any],
        recommendation: Dict[str, Any],
    ) -> str:
        """Generate comparison summary"""
        return (
            f"Tax Comparison Summary:\n"
            f"- Actual Accounting: €{actual['total_tax']:.2f} tax, "
            f"€{actual['net_income']:.2f} net income\n"
            f"- 6% Flat-Rate: €{flat_6['total_tax']:.2f} tax, "
            f"€{flat_6['net_income']:.2f} net income\n"
            f"- 13.5% Flat-Rate: €{flat_12['total_tax']:.2f} tax, "
            f"€{flat_12['net_income']:.2f} net income\n\n"
            f"Recommendation: {recommendation['method_label']}\n"
            f"{recommendation['explanation']}"
        )
