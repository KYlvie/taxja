"""
Savings Suggestion Generator Service

Generates personalized tax savings suggestions.
Validates Requirement 34.5.

④ Enhancement: AI-powered spending pattern analysis generates additional
   personalised suggestions by examining expense categories, seasonal
   patterns, and missing deduction opportunities via LLM.
"""

from decimal import Decimal
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import logging

from sqlalchemy.orm import Session
from sqlalchemy import extract, func

from app.models.user import User, UserType
from app.models.transaction import Transaction, TransactionType
from app.services.deduction_calculator import DeductionCalculator
from app.services.flat_rate_tax_comparator import FlatRateTaxComparator
from app.services.tax_calculation_engine import TaxCalculationEngine

logger = logging.getLogger(__name__)


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
        # TaxCalculationEngine and FlatRateTaxComparator accept Session directly.
        # DeductionCalculator expects Optional[Dict], NOT a Session — passing a
        # Session would cause AttributeError on .get().  Use None to get 2026
        # defaults, or load config from TaxCalculationEngine which already
        # handles the db→config resolution.
        self.tax_engine = TaxCalculationEngine(db)
        self.flat_rate_comparator = FlatRateTaxComparator(db)
        self.deduction_calc = DeductionCalculator(
            self.tax_engine.tax_config.get("deduction_config")
        )

    def _get_marginal_rate(self, taxable_income: Decimal) -> Decimal:
        """Look up the actual marginal tax rate from Austrian tax brackets.

        Falls back to 30 % if brackets are unavailable.
        """
        brackets = self.tax_engine.tax_config.get("tax_brackets", [])
        if not brackets:
            return Decimal("0.30")

        marginal_rate = Decimal("0")
        remaining = taxable_income
        for bracket in brackets:
            if remaining <= 0:
                break
            lower = Decimal(str(bracket.get("lower", bracket.get("min", 0))))
            raw_upper = bracket.get("upper", bracket.get("max"))
            upper = Decimal(str(raw_upper)) if raw_upper is not None else None
            rate = Decimal(str(bracket["rate"]))
            if rate > 1:
                rate = rate / Decimal("100")

            if upper is None:
                # Last bracket — income falls here
                marginal_rate = rate
                break
            bracket_width = upper - lower
            if remaining <= bracket_width:
                marginal_rate = rate
                break
            remaining -= bracket_width
            marginal_rate = rate

        return marginal_rate

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

        # Compute user's approximate annual income for marginal rate lookup
        try:
            total_income = (
                self.db.query(func.coalesce(func.sum(Transaction.amount), 0))
                .filter(
                    Transaction.user_id == user_id,
                    extract("year", Transaction.transaction_date) == tax_year,
                    Transaction.type == TransactionType.INCOME,
                )
                .scalar()
            )
            marginal_rate = self._get_marginal_rate(Decimal(str(total_income or 0)))
        except Exception:
            marginal_rate = Decimal("0.30")

        suggestions = []

        # Check commuting allowance
        commuting_suggestion = self._check_commuting_allowance(user, tax_year, marginal_rate)
        if commuting_suggestion:
            suggestions.append(commuting_suggestion)

        # Check home office deduction
        home_office_suggestion = self._check_home_office_deduction(
            user, tax_year, marginal_rate
        )
        if home_office_suggestion:
            suggestions.append(home_office_suggestion)

        # Check flat-rate tax comparison (self-employed only)
        if user.user_type in [UserType.SELF_EMPLOYED, UserType.MIXED]:
            flat_rate_suggestion = self._check_flat_rate_tax(user_id, tax_year)
            if flat_rate_suggestion:
                suggestions.append(flat_rate_suggestion)

        # Check family deductions
        family_suggestion = self._check_family_deductions(user, tax_year, marginal_rate)
        if family_suggestion:
            suggestions.append(family_suggestion)

        # Check SVS deductibility
        svs_suggestion = self._check_svs_deductibility(user_id, tax_year, marginal_rate)
        if svs_suggestion:
            suggestions.append(svs_suggestion)

        # ④ AI-powered spending pattern suggestions
        existing_titles = [s.title for s in suggestions]
        ai_suggestions = self._ai_spending_analysis(user, tax_year, language, existing_titles)
        suggestions.extend(ai_suggestions)

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
        self, user: User, tax_year: int, marginal_rate: Decimal = Decimal("0.30")
    ) -> Optional[SavingsSuggestion]:
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

        # Estimate tax savings using actual marginal rate
        estimated_savings = deduction_result.amount * marginal_rate

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
        self, user: User, tax_year: int, marginal_rate: Decimal = Decimal("0.30")
    ) -> Optional[SavingsSuggestion]:
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

        # Estimate tax savings using actual marginal rate
        estimated_savings = home_office_deduction * marginal_rate

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
    ) -> Optional[SavingsSuggestion]:
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
        self, user: User, tax_year: int, marginal_rate: Decimal = Decimal("0.30")
    ) -> Optional[SavingsSuggestion]:
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

        # Estimate tax savings using actual marginal rate
        estimated_savings = deduction_result.amount * marginal_rate

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
        self, user_id: int, tax_year: int, marginal_rate: Decimal = Decimal("0.30")
    ) -> Optional[SavingsSuggestion]:
        """Check if SVS contributions are being deducted"""
        # Get tax calculation
        tax_result = self.tax_engine.calculate_total_tax(user_id, tax_year)

        # Check if SVS contributions exist
        if tax_result.svs_contributions == 0:
            return None

        # SVS contributions are automatically deductible
        # Estimate tax savings using actual marginal rate
        estimated_savings = tax_result.svs_contributions * marginal_rate

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

    # ------------------------------------------------------------------
    # ④ AI-powered spending pattern analysis
    # ------------------------------------------------------------------

    _AI_SUGGESTION_PROMPT = (
        "You are an Austrian tax advisor AI. Analyse the following user "
        "spending profile and suggest up to 3 ADDITIONAL tax-saving "
        "opportunities the user may be missing. Only suggest things that "
        "are legally available under Austrian tax law (EStG 2026).\n\n"
        "User type: {user_type}\n"
        "Tax year: {tax_year}\n"
        "Expense breakdown (category → total €):\n{expense_breakdown}\n"
        "Income: €{total_income}\n"
        "Already suggested: {existing_titles}\n\n"
        "Return a JSON array of objects with keys: "
        '"title", "description", "estimated_savings_eur", "action_required". '
        "Return ONLY the JSON array, no markdown."
    )

    def _ai_spending_analysis(
        self,
        user: User,
        tax_year: int,
        language: str,
        existing_titles: Optional[List[str]] = None,
    ) -> List[SavingsSuggestion]:
        """Use LLM to find additional saving opportunities from spending data."""
        try:
            from app.services.llm_service import get_llm_service
        except ImportError:
            return []

        llm = get_llm_service()
        if not llm.is_available:
            return []

        # Build spending profile
        transactions = (
            self.db.query(Transaction)
            .filter(
                Transaction.user_id == user.id,
                extract("year", Transaction.transaction_date) == tax_year,
            )
            .all()
        )

        if len(transactions) < 5:
            return []  # Not enough data for meaningful analysis

        expense_cats: Dict[str, Decimal] = {}
        total_income = Decimal("0")
        for t in transactions:
            if t.type == TransactionType.EXPENSE and t.expense_category:
                cat = t.expense_category.value
                expense_cats[cat] = expense_cats.get(cat, Decimal("0")) + t.amount
            if t.type == TransactionType.INCOME:
                total_income += t.amount

        if not expense_cats:
            return []

        expense_text = "\n".join(
            f"  {cat}: €{amt:,.2f}" for cat, amt in expense_cats.items()
        )
        user_type = user.user_type.value if user.user_type else "employee"

        # Collect titles of already-generated suggestions so LLM doesn't repeat
        titles_str = ", ".join(existing_titles) if existing_titles else "none"

        prompt = self._AI_SUGGESTION_PROMPT.format(
            user_type=user_type,
            tax_year=tax_year,
            expense_breakdown=expense_text,
            total_income=f"{total_income:,.2f}",
            existing_titles=titles_str,
        )

        try:
            raw = llm.generate_response(
                user_message=prompt,
                language="en",
                context_chunks=[],
                user_financial_summary="",
                conversation_history=[],
            )
            return self._parse_ai_suggestions(raw)
        except Exception as exc:
            logger.warning("AI spending analysis failed: %s", exc)
            return []

    @staticmethod
    def _parse_ai_suggestions(raw: str) -> List["SavingsSuggestion"]:
        """Parse LLM JSON response into SavingsSuggestion objects."""
        # Strip potential markdown fences
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)

        try:
            items = json.loads(text)
        except json.JSONDecodeError:
            return []

        if not isinstance(items, list):
            return []

        suggestions = []
        for item in items[:3]:  # max 3
            if not isinstance(item, dict):
                continue
            title = item.get("title", "")
            description = item.get("description", "")
            savings = item.get("estimated_savings_eur", 0)
            action = item.get("action_required", "")
            if not title or not description:
                continue
            try:
                savings_dec = Decimal(str(savings))
            except Exception:
                savings_dec = Decimal("0")
            suggestions.append(SavingsSuggestion(
                title=title,
                description=description,
                potential_savings=savings_dec,
                category="ai_suggestion",
                priority=4,
                action_required=action or "Review with tax advisor",
            ))
        return suggestions
