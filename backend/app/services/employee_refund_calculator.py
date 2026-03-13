"""
Employee Tax Refund Calculator (Arbeitnehmerveranlagung)

This module calculates potential tax refunds for employees by comparing
withheld tax (Lohnsteuer) from Lohnzettel with actual tax liability after
applying all available deductions.

Requirements: 37.1, 37.2, 37.3, 37.4, 37.5, 37.6, 37.7
"""

from decimal import Decimal
from typing import Dict, Any, Optional, List, Protocol
from datetime import datetime

from app.services.income_tax_calculator import IncomeTaxCalculator
from app.services.deduction_calculator import DeductionCalculator


class FamilyInfo:
    """Family information for deduction calculation"""

    def __init__(self, num_children: int = 0, is_single_parent: bool = False):
        self.num_children = num_children
        self.is_single_parent = is_single_parent


class UserLike(Protocol):
    """Protocol for user-like objects (duck typing)"""

    id: int
    email: str
    commuting_distance: Optional[int]
    public_transport_available: Optional[bool]
    family_info: Optional[FamilyInfo]


class LohnzettelData:
    """Data extracted from Lohnzettel (wage tax card)"""

    def __init__(
        self,
        gross_income: Decimal,
        withheld_tax: Decimal,
        withheld_svs: Decimal,
        employer_name: str,
        tax_year: int,
    ):
        self.gross_income = gross_income
        self.withheld_tax = withheld_tax
        self.withheld_svs = withheld_svs
        self.employer_name = employer_name
        self.tax_year = tax_year


class RefundResult:
    """Result of refund calculation"""

    def __init__(
        self,
        gross_income: Decimal,
        withheld_tax: Decimal,
        actual_tax_liability: Decimal,
        refund_amount: Decimal,
        is_refund: bool,
        deductions_applied: Dict[str, Decimal],
        explanation: str,
        breakdown: Dict[str, Any],
    ):
        self.gross_income = gross_income
        self.withheld_tax = withheld_tax
        self.actual_tax_liability = actual_tax_liability
        self.refund_amount = refund_amount
        self.is_refund = is_refund
        self.deductions_applied = deductions_applied
        self.explanation = explanation
        self.breakdown = breakdown

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return {
            "gross_income": float(self.gross_income),
            "withheld_tax": float(self.withheld_tax),
            "actual_tax_liability": float(self.actual_tax_liability),
            "refund_amount": float(self.refund_amount),
            "is_refund": self.is_refund,
            "deductions_applied": {
                k: float(v) for k, v in self.deductions_applied.items()
            },
            "explanation": self.explanation,
            "breakdown": self.breakdown,
        }


class EmployeeRefundCalculator:
    """
    Calculate employee tax refunds (Arbeitnehmerveranlagung)

    Compares withheld tax from Lohnzettel with actual tax liability
    after applying all available deductions.
    """

    def __init__(self):
        self.income_tax_calculator = IncomeTaxCalculator()
        self.deduction_calculator = DeductionCalculator()

    def calculate_refund(
        self,
        lohnzettel_data: LohnzettelData,
        user: UserLike,
        additional_deductions: Optional[Dict[str, Decimal]] = None,
    ) -> RefundResult:
        """
        Calculate tax refund for employee

        Args:
            lohnzettel_data: Data from Lohnzettel
            user: User object with family and commuting info
            additional_deductions: Optional additional deductions (e.g., donations)

        Returns:
            RefundResult with refund amount and explanation
        """
        tax_year = lohnzettel_data.tax_year
        gross_income = lohnzettel_data.gross_income
        withheld_tax = lohnzettel_data.withheld_tax

        # Calculate all applicable deductions
        deductions_applied = {}
        total_deductions = Decimal("0.00")

        # 1. Commuting allowance (Pendlerpauschale)
        if user.commuting_distance and user.commuting_distance >= 20:
            commuting_deduction = self.deduction_calculator.calculate_commuting_allowance(
                distance_km=user.commuting_distance,
                public_transport_available=user.public_transport_available or False,
                working_days_per_year=220,
            )
            if commuting_deduction.amount > 0:
                deductions_applied["commuting_allowance"] = commuting_deduction.amount
                total_deductions += commuting_deduction.amount

        # 2. Home office deduction
        home_office_deduction = self.deduction_calculator.calculate_home_office_deduction()
        if home_office_deduction.amount > 0:
            deductions_applied["home_office"] = home_office_deduction.amount
            total_deductions += home_office_deduction.amount

        # 3. Family deductions (Kinderabsetzbetrag, single parent)
        if user.family_info:
            family_deduction = self.deduction_calculator.calculate_family_deductions(
                user.family_info
            )
            if family_deduction.amount > 0:
                deductions_applied["family_deductions"] = family_deduction.amount
                total_deductions += family_deduction.amount

        # 4. Social insurance contributions (Sonderausgaben)
        # Already withheld, but can be claimed as deduction
        if lohnzettel_data.withheld_svs > 0:
            deductions_applied["social_insurance"] = lohnzettel_data.withheld_svs
            total_deductions += lohnzettel_data.withheld_svs

        # 5. Additional deductions (if provided)
        if additional_deductions:
            for key, value in additional_deductions.items():
                deductions_applied[key] = value
                total_deductions += value

        # Calculate taxable income after deductions
        taxable_income = gross_income - total_deductions

        # Calculate actual tax liability
        tax_result = self.income_tax_calculator.calculate_progressive_tax(
            taxable_income=taxable_income, tax_year=tax_year
        )

        actual_tax_liability = tax_result.total_tax

        # Calculate refund or additional payment
        refund_amount = withheld_tax - actual_tax_liability
        is_refund = refund_amount > 0

        # Generate explanation
        explanation = self._generate_explanation(
            gross_income=gross_income,
            withheld_tax=withheld_tax,
            actual_tax_liability=actual_tax_liability,
            refund_amount=refund_amount,
            is_refund=is_refund,
            deductions_applied=deductions_applied,
        )

        # Create breakdown
        breakdown = {
            "gross_income": float(gross_income),
            "total_deductions": float(total_deductions),
            "taxable_income": float(taxable_income),
            "tax_calculation": {
                "total_tax": float(tax_result.total_tax),
                "effective_rate": float(tax_result.effective_rate),
                "breakdown": tax_result.breakdown,
            },
            "withheld_tax": float(withheld_tax),
            "difference": float(refund_amount),
        }

        return RefundResult(
            gross_income=gross_income,
            withheld_tax=withheld_tax,
            actual_tax_liability=actual_tax_liability,
            refund_amount=abs(refund_amount),
            is_refund=is_refund,
            deductions_applied=deductions_applied,
            explanation=explanation,
            breakdown=breakdown,
        )

    def calculate_refund_from_transactions(
        self,
        user: UserLike,
        tax_year: int,
        employment_transactions: List[Any],  # List of Transaction-like objects
    ) -> RefundResult:
        """
        Calculate refund from employment transactions

        This method aggregates employment income and withheld tax from
        transactions (e.g., monthly payslips) instead of a single Lohnzettel.

        Args:
            user: User object
            tax_year: Tax year
            employment_transactions: List of employment income transactions

        Returns:
            RefundResult
        """
        # Aggregate gross income and withheld tax
        total_gross_income = Decimal("0.00")
        total_withheld_tax = Decimal("0.00")
        total_withheld_svs = Decimal("0.00")

        for txn in employment_transactions:
            total_gross_income += txn.amount

            # Extract withheld tax from transaction metadata
            if txn.metadata and "withheld_tax" in txn.metadata:
                total_withheld_tax += Decimal(str(txn.metadata["withheld_tax"]))

            if txn.metadata and "withheld_svs" in txn.metadata:
                total_withheld_svs += Decimal(str(txn.metadata["withheld_svs"]))

        # Create synthetic Lohnzettel data
        lohnzettel_data = LohnzettelData(
            gross_income=total_gross_income,
            withheld_tax=total_withheld_tax,
            withheld_svs=total_withheld_svs,
            employer_name="Aggregated from transactions",
            tax_year=tax_year,
        )

        return self.calculate_refund(lohnzettel_data, user)

    def _generate_explanation(
        self,
        gross_income: Decimal,
        withheld_tax: Decimal,
        actual_tax_liability: Decimal,
        refund_amount: Decimal,
        is_refund: bool,
        deductions_applied: Dict[str, Decimal],
    ) -> str:
        """Generate human-readable explanation of refund calculation"""

        if is_refund:
            explanation = f"Good news! You are entitled to a tax refund of €{refund_amount:,.2f}.\n\n"
            explanation += f"Your employer withheld €{withheld_tax:,.2f} in income tax (Lohnsteuer) from your gross income of €{gross_income:,.2f}. "
            explanation += f"However, after applying all available deductions, your actual tax liability is only €{actual_tax_liability:,.2f}.\n\n"
        else:
            explanation = f"Based on your deductions, you need to pay an additional €{refund_amount:,.2f} in taxes.\n\n"
            explanation += f"Your employer withheld €{withheld_tax:,.2f} in income tax (Lohnsteuer) from your gross income of €{gross_income:,.2f}. "
            explanation += f"After applying all available deductions, your actual tax liability is €{actual_tax_liability:,.2f}.\n\n"

        if deductions_applied:
            explanation += "Deductions applied:\n"
            for key, value in deductions_applied.items():
                explanation += f"  - {key.replace('_', ' ').title()}: €{value:,.2f}\n"

        explanation += "\n"
        explanation += "To claim this refund, file an Arbeitnehmerveranlagung (employee tax assessment) with FinanzOnline before June 30.\n"
        explanation += "⚠️ This is an estimate only. Final refund amount may vary based on FinanzOnline calculation."

        return explanation

    def estimate_refund_potential(
        self, user: UserLike, tax_year: int, estimated_gross_income: Decimal
    ) -> Dict[str, Any]:
        """
        Estimate refund potential without Lohnzettel

        Useful for dashboard widget to show potential refund.

        Args:
            user: User object
            tax_year: Tax year
            estimated_gross_income: Estimated annual gross income

        Returns:
            Dictionary with estimated refund and suggestions
        """
        # Estimate withheld tax (rough approximation)
        # Assume employer withholds based on gross income without deductions
        tax_config = TaxConfiguration.get_by_year(tax_year)
        estimated_withheld_result = self.income_tax_calculator.calculate_progressive_tax(
            taxable_income=estimated_gross_income, tax_year=tax_year
        )
        estimated_withheld_tax = estimated_withheld_result.total_tax

        # Create synthetic Lohnzettel data
        lohnzettel_data = LohnzettelData(
            gross_income=estimated_gross_income,
            withheld_tax=estimated_withheld_tax,
            withheld_svs=Decimal("0.00"),  # Not included in this estimate
            employer_name="Estimated",
            tax_year=tax_year,
        )

        # Calculate refund
        refund_result = self.calculate_refund(lohnzettel_data, user)

        # Generate suggestions
        suggestions = []
        if not user.commuting_distance or user.commuting_distance < 20:
            suggestions.append(
                "Add your commuting distance (if ≥20km) to claim Pendlerpauschale"
            )

        if not user.family_info or user.family_info.num_children == 0:
            suggestions.append(
                "Add family information to claim Kinderabsetzbetrag (child deduction)"
            )

        return {
            "estimated_refund": float(refund_result.refund_amount),
            "is_refund": refund_result.is_refund,
            "confidence": "low",  # Low confidence without actual Lohnzettel
            "suggestions": suggestions,
            "message": "Upload your Lohnzettel for accurate refund calculation",
        }
