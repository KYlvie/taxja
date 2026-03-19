"""
Employee Tax Refund Calculator (Arbeitnehmerveranlagung)

This module calculates potential tax refunds for employees by comparing
withheld tax (Lohnsteuer) from Lohnzettel with actual tax liability after
applying all available deductions and tax credits (Absetzbeträge).

Correct calculation flow (§33 EStG):
1. gross_income - income_deductions = taxable_income
2. tax_before_credits = progressive_tax(taxable_income)
3. tax_credits = VAB + Zuschlag + Familienbonus + AVAB/AEAB + ...
4. final_tax = max(0, tax_before_credits - tax_credits)
5. refund = withheld_tax - final_tax

Requirements: 37.1, 37.2, 37.3, 37.4, 37.5, 37.6, 37.7
"""

from decimal import Decimal
from typing import Dict, Any, Optional, List, Protocol
from datetime import datetime

from app.services.income_tax_calculator import IncomeTaxCalculator
from app.services.deduction_calculator import DeductionCalculator, FamilyInfo as DeductionFamilyInfo


class FamilyInfo:
    """Family information for deduction calculation"""

    def __init__(
        self,
        num_children: int = 0,
        is_single_parent: bool = False,
        children_under_18: int = 0,
        children_18_to_24: int = 0,
        is_sole_earner: bool = False,
    ):
        self.num_children = num_children
        self.is_single_parent = is_single_parent
        self.children_under_18 = children_under_18
        self.children_18_to_24 = children_18_to_24
        self.is_sole_earner = is_sole_earner


class UserLike(Protocol):
    """Protocol for user-like objects (duck typing)"""

    id: int
    email: str
    commuting_distance: Optional[int]
    public_transport_available: Optional[bool]
    family_info: Optional[FamilyInfo]
    telearbeit_days: Optional[int]
    employer_telearbeit_pauschale: Optional[Decimal]


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
        tax_credits_applied: Dict[str, Decimal],
        explanation: str,
        breakdown: Dict[str, Any],
    ):
        self.gross_income = gross_income
        self.withheld_tax = withheld_tax
        self.actual_tax_liability = actual_tax_liability
        self.refund_amount = refund_amount
        self.is_refund = is_refund
        self.deductions_applied = deductions_applied
        self.tax_credits_applied = tax_credits_applied
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
            "tax_credits_applied": {
                k: float(v) for k, v in self.tax_credits_applied.items()
            },
            "explanation": self.explanation,
            "breakdown": self.breakdown,
        }


class EmployeeRefundCalculator:
    """
    Calculate employee tax refunds (Arbeitnehmerveranlagung)

    Compares withheld tax from Lohnzettel with actual tax liability
    after applying all available deductions AND tax credits (Absetzbeträge).

    Key distinction:
    - Income deductions (reduce taxable_income): Werbungskosten, Pendlerpauschale,
      Home Office, Sonderausgabenpauschale, SVS
    - Tax credits / Absetzbeträge (reduce tax liability): Verkehrsabsetzbetrag,
      Zuschlag zum VAB, Pendlereuro, Familienbonus Plus, AVAB/AEAB
    """

    # 2026 fallback config (matches get_2026_tax_config in tax_configuration.py)
    _DEFAULT_TAX_CONFIG = {
        "tax_year": 2026,
        "tax_brackets": [
            {"lower": 0, "upper": 13539, "rate": 0.00},
            {"lower": 13539, "upper": 21992, "rate": 0.20},
            {"lower": 21992, "upper": 36458, "rate": 0.30},
            {"lower": 36458, "upper": 70365, "rate": 0.40},
            {"lower": 70365, "upper": 104859, "rate": 0.48},
            {"lower": 104859, "upper": 1000000, "rate": 0.50},
            {"lower": 1000000, "upper": None, "rate": 0.55},
        ],
        "exemption_amount": 13539,
    }

    def __init__(self, tax_config: Optional[Dict] = None, deduction_config: Optional[Dict] = None):
        config = tax_config or self._DEFAULT_TAX_CONFIG
        self.income_tax_calculator = IncomeTaxCalculator(config)
        self.deduction_calculator = DeductionCalculator(deduction_config)

    def _to_deduction_family_info(self, family_info: FamilyInfo) -> DeductionFamilyInfo:
        """Convert local FamilyInfo to deduction_calculator's FamilyInfo dataclass."""
        return DeductionFamilyInfo(
            num_children=family_info.num_children,
            is_single_parent=family_info.is_single_parent,
            children_under_18=getattr(family_info, 'children_under_18', 0),
            children_18_to_24=getattr(family_info, 'children_18_to_24', 0),
            is_sole_earner=getattr(family_info, 'is_sole_earner', False),
        )

    def calculate_refund(
        self,
        lohnzettel_data: LohnzettelData,
        user: UserLike,
        additional_deductions: Optional[Dict[str, Decimal]] = None,
    ) -> RefundResult:
        """
        Calculate tax refund for employee.

        Follows the correct Austrian tax calculation flow:
        1. Determine income deductions (reduce taxable income)
        2. Calculate tariff tax on taxable income
        3. Apply Absetzbeträge (reduce tax liability)
        4. Compare with withheld tax

        Args:
            lohnzettel_data: Data from Lohnzettel
            user: User object with family and commuting info
            additional_deductions: Optional additional income deductions (e.g., donations)

        Returns:
            RefundResult with refund amount and explanation
        """
        tax_year = lohnzettel_data.tax_year
        gross_income = lohnzettel_data.gross_income
        withheld_tax = lohnzettel_data.withheld_tax

        # ──────────────────────────────────────────────────────────
        # STEP 1: Income deductions (reduce taxable income)
        # ──────────────────────────────────────────────────────────
        income_deductions = {}
        total_income_deductions = Decimal("0.00")

        # 1a. Werbungskostenpauschale (€132/year) — only if no higher actual Werbungskosten
        actual_werbungskosten = Decimal("0.00")
        if additional_deductions and "werbungskosten" in additional_deductions:
            actual_werbungskosten = additional_deductions.pop("werbungskosten")

        if actual_werbungskosten > self.deduction_calculator.WERBUNGSKOSTENPAUSCHALE:
            income_deductions["werbungskosten_actual"] = actual_werbungskosten
            total_income_deductions += actual_werbungskosten
        else:
            income_deductions["werbungskostenpauschale"] = self.deduction_calculator.WERBUNGSKOSTENPAUSCHALE
            total_income_deductions += self.deduction_calculator.WERBUNGSKOSTENPAUSCHALE

        # 1b. Commuting allowance (Pendlerpauschale) — income deduction
        # NOTE: Pendlerpauschale is a Werbungskosten/Freibetrag (income deduction),
        # but Pendlereuro is an Absetzbetrag (tax credit) — they must be separated.
        # Großes Pendlerpauschale starts at 2km, Kleines at 20km
        pendler_euro = Decimal("0.00")
        if user.commuting_distance and user.commuting_distance >= 2:
            commuting_result = self.deduction_calculator.calculate_commuting_allowance(
                distance_km=user.commuting_distance,
                public_transport_available=user.public_transport_available or False,
                working_days_per_year=220,
            )
            if commuting_result.amount > Decimal("0"):
                # Only Pendlerpauschale (base_annual) goes to income deductions
                base_annual = commuting_result.breakdown.get("base_annual", Decimal("0.00"))
                pendler_euro = commuting_result.breakdown.get("pendler_euro", Decimal("0.00"))
                if base_annual > Decimal("0"):
                    income_deductions["pendlerpauschale"] = base_annual
                    total_income_deductions += base_annual

        # 1c. Telearbeitspauschale / Home office — income deduction (Werbungskosten)
        # €3/day, max 100 days, minus employer's tax-free Telearbeitspauschale
        # None = legacy/unknown → flat €300 fallback; 0 = explicit zero → €0
        telearbeit_days = getattr(user, "telearbeit_days", None)
        employer_pauschale = getattr(user, "employer_telearbeit_pauschale", None)
        employer_pauschale = Decimal(str(employer_pauschale)) if employer_pauschale else Decimal("0.00")
        home_office_result = self.deduction_calculator.calculate_home_office_deduction(
            telearbeit_days=telearbeit_days,
            employer_telearbeit_pauschale=employer_pauschale,
        )
        if home_office_result.amount > Decimal("0"):
            income_deductions["telearbeit_pauschale"] = home_office_result.amount
            total_income_deductions += home_office_result.amount

        # 1d. Social insurance contributions (Sonderausgaben) — income deduction
        if lohnzettel_data.withheld_svs > Decimal("0"):
            income_deductions["social_insurance"] = lohnzettel_data.withheld_svs
            total_income_deductions += lohnzettel_data.withheld_svs

        # 1e. Sonderausgabenpauschale (§18 Abs 2 EStG) — income deduction
        # This is a Sonderausgabe (reduces taxable income), NOT a tax credit.
        sap = self.deduction_calculator.SONDERAUSGABENPAUSCHALE
        income_deductions["sonderausgabenpauschale"] = sap
        total_income_deductions += sap

        # 1f. Additional income deductions (if provided)
        if additional_deductions:
            for key, value in additional_deductions.items():
                income_deductions[key] = value
                total_income_deductions += value

        # ──────────────────────────────────────────────────────────
        # STEP 2: Calculate tariff tax on taxable income
        # ──────────────────────────────────────────────────────────
        taxable_income = max(gross_income - total_income_deductions, Decimal("0.00"))

        tax_result = self.income_tax_calculator.calculate_progressive_tax(
            taxable_income=taxable_income, tax_year=tax_year
        )
        tax_before_credits = tax_result.total_tax

        # ──────────────────────────────────────────────────────────
        # STEP 3: Apply Absetzbeträge (tax credits — reduce tax liability)
        # These are NOT income deductions. They reduce the calculated tax.
        # ──────────────────────────────────────────────────────────
        tax_credits = {}
        total_tax_credits = Decimal("0.00")

        # 3a. Verkehrsabsetzbetrag (§33 Abs 5 EStG) — all employees get this
        vab = self.deduction_calculator.VERKEHRSABSETZBETRAG
        tax_credits["verkehrsabsetzbetrag"] = vab
        total_tax_credits += vab

        # 3b. Zuschlag zum Verkehrsabsetzbetrag (low-income supplement)
        zuschlag_result = self.deduction_calculator.calculate_zuschlag_verkehrsabsetzbetrag(
            annual_income=taxable_income
        )
        if zuschlag_result.amount > Decimal("0"):
            tax_credits["zuschlag_verkehrsabsetzbetrag"] = zuschlag_result.amount
            total_tax_credits += zuschlag_result.amount

        # 3c. Pendlereuro (§33 Abs 5 EStG) — Absetzbetrag (tax credit)
        # Pendlereuro is legally a tax credit, NOT an income deduction.
        # It was calculated in Step 1b but stored separately for correct classification.
        if pendler_euro > Decimal("0"):
            tax_credits["pendlereuro"] = pendler_euro
            total_tax_credits += pendler_euro

        # 3d. Family-related tax credits
        if user.family_info and user.family_info.num_children > 0:
            dc_family = self._to_deduction_family_info(user.family_info)

            # Familienbonus Plus (§33 Abs 3a EStG) — tax credit per child
            familienbonus_result = self.deduction_calculator.calculate_familienbonus(dc_family)
            if familienbonus_result.amount > Decimal("0"):
                tax_credits["familienbonus_plus"] = familienbonus_result.amount
                total_tax_credits += familienbonus_result.amount

            # Alleinverdiener-/Alleinerzieherabsetzbetrag (§33 Abs 4 EStG)
            alleinverdiener_result = self.deduction_calculator.calculate_alleinverdiener(dc_family)
            if alleinverdiener_result.amount > Decimal("0"):
                tax_credits["alleinverdiener_aeab"] = alleinverdiener_result.amount
                total_tax_credits += alleinverdiener_result.amount

        # ──────────────────────────────────────────────────────────
        # STEP 4: Final tax = max(0, tariff_tax - tax_credits)
        # ──────────────────────────────────────────────────────────
        actual_tax_liability = max(Decimal("0.00"), tax_before_credits - total_tax_credits)

        # ──────────────────────────────────────────────────────────
        # STEP 5: Refund = withheld - actual
        # ──────────────────────────────────────────────────────────
        refund_amount = withheld_tax - actual_tax_liability
        is_refund = refund_amount > Decimal("0")

        # Generate explanation
        explanation = self._generate_explanation(
            gross_income=gross_income,
            withheld_tax=withheld_tax,
            actual_tax_liability=actual_tax_liability,
            refund_amount=refund_amount,
            is_refund=is_refund,
            income_deductions=income_deductions,
            tax_credits=tax_credits,
        )

        # Merge all deductions for backward-compatible deductions_applied dict
        all_deductions = {}
        all_deductions.update(income_deductions)

        # Create breakdown
        breakdown = {
            "gross_income": float(gross_income),
            "total_income_deductions": float(total_income_deductions),
            "taxable_income": float(taxable_income),
            "tax_calculation": {
                "total_tax": float(tax_result.total_tax),
                "effective_rate": float(tax_result.effective_rate),
                "breakdown": tax_result.breakdown,
            },
            "tax_before_credits": float(tax_before_credits),
            "total_tax_credits": float(total_tax_credits),
            "tax_credits_detail": {k: float(v) for k, v in tax_credits.items()},
            "actual_tax_liability": float(actual_tax_liability),
            "withheld_tax": float(withheld_tax),
            "difference": float(refund_amount),
        }

        return RefundResult(
            gross_income=gross_income,
            withheld_tax=withheld_tax,
            actual_tax_liability=actual_tax_liability,
            refund_amount=abs(refund_amount),
            is_refund=is_refund,
            deductions_applied=all_deductions,
            tax_credits_applied=tax_credits,
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
        income_deductions: Dict[str, Decimal],
        tax_credits: Dict[str, Decimal],
    ) -> str:
        """Generate human-readable explanation of refund calculation"""

        if is_refund:
            explanation = f"Good news! You are entitled to a tax refund of €{refund_amount:,.2f}.\n\n"
            explanation += f"Your employer withheld €{withheld_tax:,.2f} in income tax (Lohnsteuer) from your gross income of €{gross_income:,.2f}. "
            explanation += f"However, after applying all available deductions and tax credits, your actual tax liability is only €{actual_tax_liability:,.2f}.\n\n"
        else:
            explanation = f"Based on your deductions, you need to pay an additional €{abs(refund_amount):,.2f} in taxes.\n\n"
            explanation += f"Your employer withheld €{withheld_tax:,.2f} in income tax (Lohnsteuer) from your gross income of €{gross_income:,.2f}. "
            explanation += f"After applying all available deductions and tax credits, your actual tax liability is €{actual_tax_liability:,.2f}.\n\n"

        if income_deductions:
            explanation += "Income deductions (reduce taxable income):\n"
            for key, value in income_deductions.items():
                explanation += f"  - {key.replace('_', ' ').title()}: €{value:,.2f}\n"

        if tax_credits:
            explanation += "\nTax credits (Absetzbeträge — reduce tax liability):\n"
            for key, value in tax_credits.items():
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
        if not user.commuting_distance or user.commuting_distance < 2:
            suggestions.append(
                "Add your commuting distance (if ≥2km without public transport, or ≥20km with) to claim Pendlerpauschale"
            )

        if not user.family_info or user.family_info.num_children == 0:
            suggestions.append(
                "Add family information to claim Familienbonus Plus and Alleinverdienerabsetzbetrag"
            )

        return {
            "estimated_refund": float(refund_result.refund_amount),
            "is_refund": refund_result.is_refund,
            "confidence": "low",  # Low confidence without actual Lohnzettel
            "suggestions": suggestions,
            "message": "Upload your Lohnzettel for accurate refund calculation",
        }
