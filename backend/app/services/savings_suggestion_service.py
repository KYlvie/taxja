"""
Savings Suggestion Generator Service

Generates personalized tax savings suggestions.
Validates Requirement 34.5.
"""

from decimal import Decimal
from typing import List, Dict, Any
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.user import User, UserType
from app.models.transaction import Transaction
from app.services.deduction_calculator import DeductionCalculator
from app.services.flat_rate_tax_comparator import FlatRateTaxComparator
from app.services.tax_calculation_engine import TaxCalculationEngine


class SavingsSuggestion:
    """Represents a tax savings suggestion"""

    def __init__(
        self,
        title: str,
        description: str,
        potential_savings: Decimal,
        category: str,
        priority: int,
        action_required: str,
    ):
        self.title = title
        self.description = description
        self.potential_savings = potential_savings
        self.category = category
        self.priority = priority
        self.action_required = action_required

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "potential_savings": float(self.potential_savings),
            "category": self.category,
            "priority": self.priority,
            "action_required": self.action_required,
        }


class SavingsSuggestionService:
    """Generates personalized tax savings suggestions"""

    def __init__(self, db: Session):
        self.db = db
        self.deduction_calc = DeductionCalculator(db)
        self.flat_rate_comparator = FlatRateTaxComparator(db)
        self.tax_engine = TaxCalculationEngine(db)

    def generate_suggestions(
        self, user_id: int, tax_year: int, language: str = "de"
    ) -> List[Dict[str, Any]]:
        """
        Generate personalized tax savings suggestions.

        Args:
            user_id: User ID
            tax_year: Tax year
            language: Language for suggestions

        Returns:
            List of suggestions ranked by potential savings
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        suggestions = []

        # Check commuting allowance
        commuting_suggestion = self._check_commuting_allowance(user, tax_year)
        if commuting_suggestion:
            suggestions.append(commuting_suggestion)

        # Check home office deduction
        home_office_suggestion = self._check_home_office_deduction(user, tax_year)
        if home_office_suggestion:
            suggestions.append(home_office_suggestion)

        # Check flat-rate tax comparison (self-employed only)
        if user.user_type in [UserType.SELF_EMPLOYED, UserType.GSVG]:
            flat_rate_suggestion = self._check_flat_rate_tax(user_id, tax_year)
            if flat_rate_suggestion:
                suggestions.append(flat_rate_suggestion)

        # Check family deductions
        family_suggestion = self._check_family_deductions(user, tax_year)
        if family_suggestion:
            suggestions.append(family_suggestion)

        # Check SVS deductibility
        svs_suggestion = self._check_svs_deductibility(user_id, tax_year)
        if svs_suggestion:
            suggestions.append(svs_suggestion)

        # Sort by potential savings (descending)
        suggestions.sort(key=lambda x: x.potential_savings, reverse=True)

        # Convert to dict and add rank
        result = []
        for i, suggestion in enumerate(suggestions, 1):
            suggestion_dict = suggestion.to_dict()
            suggestion_dict["rank"] = i
            result.append(suggestion_dict)

        return result

    def _check_commuting_allowance(
        self, user: User, tax_year: int
    ) -> SavingsSuggestion:
        """Check if user can claim commuting allowance"""
        # Check if user has commuting info
        if not user.commuting_info:
            return None

        commuting_info = user.commuting_info
        distance = commuting_info.get("distance_km", 0)

        # Must be at least 20km
        if distance < 20:
            return None

        # Check if already claimed
        # (In practice, check if deduction is already in tax calculation)
        # For now, assume not claimed if commuting_info exists but no deduction

        # Calculate potential savings
        public_transport = commuting_info.get("public_transport_available", True)
        deduction_result = self.deduction_calc.calculate_commuting_allowance(
            distance, public_transport
        )

        # Estimate tax savings (assume 30% marginal rate)
        estimated_savings = deduction_result.amount * Decimal("0.30")

        allowance_type = (
            "Kleines Pendlerpauschale"
            if public_transport
            else "Großes Pendlerpauschale"
        )

        return SavingsSuggestion(
            title=f"Claim Commuting Allowance ({allowance_type})",
            description=(
                f"You commute {distance}km to work. You can claim "
                f"€{deduction_result.amount:.2f}/year in commuting allowance, "
                f"potentially saving €{estimated_savings:.2f} in taxes."
            ),
            potential_savings=estimated_savings,
            category="deductions",
            priority=1,
            action_required="Add commuting distance and public transport availability to your profile",
        )

    def _check_home_office_deduction(
        self, user: User, tax_year: int
    ) -> SavingsSuggestion:
        """Check if user can claim home office deduction"""
        # Check if user works from home
        # (In practice, check user profile or transaction patterns)

        # For employees and self-employed
        if user.user_type not in [UserType.EMPLOYEE, UserType.SELF_EMPLOYED]:
            return None

        # Check if already claimed
        # (In practice, check if deduction is already in tax calculation)

        # Home office deduction is €300/year
        home_office_deduction = self.deduction_calc.HOME_OFFICE_DEDUCTION

        # Estimate tax savings (assume 30% marginal rate)
        estimated_savings = home_office_deduction * Decimal("0.30")

        return SavingsSuggestion(
            title="Claim Home Office Deduction",
            description=(
                f"If you work from home, you can claim €{home_office_deduction:.2f}/year "
                f"in home office deduction, potentially saving €{estimated_savings:.2f} in taxes."
            ),
            potential_savings=estimated_savings,
            category="deductions",
            priority=2,
            action_required="Confirm that you work from home at least part-time",
        )

    def _check_flat_rate_tax(
        self, user_id: int, tax_year: int
    ) -> SavingsSuggestion:
        """Check if flat-rate tax would save money"""
        try:
            comparison = self.flat_rate_comparator.compare_methods(user_id, tax_year)

            if not comparison["eligible"]:
                return None

            # Check if flat-rate is better
            recommendation = comparison["recommendation"]
            if recommendation["best_method"] == "actual_accounting":
                return None

            savings = Decimal(str(recommendation["savings_vs_actual"]))

            return SavingsSuggestion(
                title="Consider Flat-Rate Tax System (Pauschalierung)",
                description=(
                    f"Switching to {recommendation['method_label']} could save you "
                    f"€{savings:.2f} in taxes. Your deemed expenses would exceed "
                    f"your actual expenses."
                ),
                potential_savings=savings,
                category="tax_system",
                priority=1,
                action_required="Consult with Steuerberater to switch to flat-rate system",
            )

        except Exception:
            # If comparison fails, return None
            return None

    def _check_family_deductions(
        self, user: User, tax_year: int
    ) -> SavingsSuggestion:
        """Check if user can claim family deductions"""
        if not user.family_info:
            return None

        family_info = user.family_info
        num_children = family_info.get("num_children", 0)

        if num_children == 0:
            return None

        # Check if already claimed
        # (In practice, check if deduction is already in tax calculation)

        # Calculate family deductions
        from app.schemas.user import FamilyInfo as FamilyInfoSchema

        family_info_obj = FamilyInfoSchema(**family_info)
        deduction_result = self.deduction_calc.calculate_family_deductions(
            family_info_obj
        )

        # Estimate tax savings (assume 30% marginal rate)
        estimated_savings = deduction_result.amount * Decimal("0.30")

        return SavingsSuggestion(
            title="Claim Family Deductions (Kinderabsetzbetrag)",
            description=(
                f"You have {num_children} child(ren). You can claim "
                f"€{deduction_result.amount:.2f}/year in family deductions, "
                f"potentially saving €{estimated_savings:.2f} in taxes."
            ),
            potential_savings=estimated_savings,
            category="deductions",
            priority=1,
            action_required="Ensure family information is complete in your profile",
        )

    def _check_svs_deductibility(
        self, user_id: int, tax_year: int
    ) -> SavingsSuggestion:
        """Check if SVS contributions are being deducted"""
        # Get tax calculation
        tax_result = self.tax_engine.calculate_total_tax(user_id, tax_year)

        # Check if SVS contributions exist
        if tax_result.svs_contributions == 0:
            return None

        # SVS contributions are automatically deductible
        # Estimate tax savings (assume 30% marginal rate)
        estimated_savings = tax_result.svs_contributions * Decimal("0.30")

        return SavingsSuggestion(
            title="SVS Contributions Are Tax-Deductible",
            description=(
                f"Your SVS contributions (€{tax_result.svs_contributions:.2f}) "
                f"are automatically deducted as Sonderausgaben, saving you "
                f"approximately €{estimated_savings:.2f} in taxes."
            ),
            potential_savings=estimated_savings,
            category="information",
            priority=3,
            action_required="No action required - already applied",
        )
