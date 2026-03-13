"""Deductibility checker for expense categorization by user type.

Two-tier approach:
1. Rule engine: clear-cut cases get an immediate yes/no
2. AI analysis: ambiguous cases (e.g. groceries for self-employed) are sent
   to the LLM which examines the actual invoice items, merchant, and user's
   business type to produce a definitive judgment + actionable tax tip.
"""
import json
import logging
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)


class UserType(str, Enum):
    EMPLOYEE = "employee"
    SELF_EMPLOYED = "self_employed"
    LANDLORD = "landlord"
    MIXED = "mixed"
    GMBH = "gmbh"


class ExpenseCategory(str, Enum):
    GROCERIES = "groceries"
    OTHER = "other"
    COMMUTING = "commuting"
    HOME_OFFICE = "home_office"
    OFFICE_SUPPLIES = "office_supplies"
    EQUIPMENT = "equipment"
    TRAVEL = "travel"
    MARKETING = "marketing"
    PROFESSIONAL_SERVICES = "professional_services"
    MAINTENANCE = "maintenance"
    PROPERTY_TAX = "property_tax"
    LOAN_INTEREST = "loan_interest"
    INSURANCE = "insurance"
    UTILITIES = "utilities"
    VEHICLE = "vehicle"
    TELECOM = "telecom"
    RENT = "rent"
    BANK_FEES = "bank_fees"
    SVS_CONTRIBUTIONS = "svs_contributions"
    DEPRECIATION = "depreciation"


class DeductibilityResult:
    """Result of deductibility check"""

    def __init__(
        self,
        is_deductible: bool,
        reason: str,
        tax_tip: Optional[str] = None,
        requires_review: bool = False,
        max_amount: Optional[float] = None,
    ):
        self.is_deductible = is_deductible
        self.reason = reason
        self.tax_tip = tax_tip  # AI-generated actionable advice for the user
        self.requires_review = requires_review
        self.max_amount = max_amount

    def __repr__(self):
        return f"<DeductibilityResult(deductible={self.is_deductible}, reason={self.reason})>"


# ---------------------------------------------------------------------------
# Rule tables: (is_deductible, reason, max_amount | None)
#
# "NEEDS_AI" sentinel — the category is *potentially* deductible for this
# user type but the final call depends on what's actually on the invoice.
# ---------------------------------------------------------------------------
_NEEDS_AI = "NEEDS_AI"

_EMPLOYEE = {
    ExpenseCategory.COMMUTING: (True, "Pendlerpauschale – commuting allowance for employees", None),
    ExpenseCategory.HOME_OFFICE: (True, "Home-office-Pauschale up to €300/year", 300.0),
    ExpenseCategory.GROCERIES: (False, "Private Lebensführung – not deductible for employees", None),
    ExpenseCategory.OFFICE_SUPPLIES: (False, "Employer responsibility", None),
    ExpenseCategory.EQUIPMENT: (False, "Employer responsibility", None),
    ExpenseCategory.TRAVEL: (False, "Use Pendlerpauschale", None),
    ExpenseCategory.INSURANCE: (False, "Not deductible for employees", None),
    ExpenseCategory.UTILITIES: (False, "Not deductible for employees", None),
    ExpenseCategory.OTHER: (False, "Not deductible for employees", None),
    ExpenseCategory.VEHICLE: (False, "Use Pendlerpauschale", None),
    ExpenseCategory.TELECOM: (False, "Not deductible for employees", None),
    ExpenseCategory.RENT: (False, "Not deductible for employees", None),
    ExpenseCategory.BANK_FEES: (False, "Not deductible for employees", None),
    ExpenseCategory.SVS_CONTRIBUTIONS: (False, "Handled by employer", None),
    ExpenseCategory.MARKETING: (False, "Not deductible for employees", None),
    ExpenseCategory.PROFESSIONAL_SERVICES: (False, "Not deductible for employees", None),
    ExpenseCategory.MAINTENANCE: (False, "Not deductible for employees", None),
    ExpenseCategory.PROPERTY_TAX: (False, "Not deductible for employees", None),
    ExpenseCategory.LOAN_INTEREST: (False, "Not deductible for employees", None),
    ExpenseCategory.DEPRECIATION: (False, "Not deductible for employees", None),
}

# Self-employed: almost everything is a Betriebsausgabe, but groceries/other
# need AI to decide whether it's genuinely business-related.
_SELF_EMPLOYED = {
    ExpenseCategory.OFFICE_SUPPLIES: (True, "Betriebsausgabe", None),
    ExpenseCategory.EQUIPMENT: (True, "Betriebsausgabe (AfA for items >€1,000)", None),
    ExpenseCategory.TRAVEL: (True, "Betriebsausgabe – business travel", None),
    ExpenseCategory.MARKETING: (True, "Betriebsausgabe – marketing", None),
    ExpenseCategory.PROFESSIONAL_SERVICES: (True, "Betriebsausgabe – Steuerberater/Rechtsanwalt", None),
    ExpenseCategory.INSURANCE: (True, "Betriebsausgabe – business insurance", None),
    ExpenseCategory.UTILITIES: (True, "Betriebsausgabe – business utilities", None),
    ExpenseCategory.HOME_OFFICE: (True, "Betriebsausgabe – home office", None),
    ExpenseCategory.VEHICLE: (True, "Betriebsausgabe – KFZ-Aufwand", None),
    ExpenseCategory.TELECOM: (True, "Betriebsausgabe – Nachrichtenaufwand", None),
    ExpenseCategory.RENT: (True, "Betriebsausgabe – Mietaufwand", None),
    ExpenseCategory.BANK_FEES: (True, "Betriebsausgabe – Spesen des Geldverkehrs", None),
    ExpenseCategory.SVS_CONTRIBUTIONS: (True, "SVS/SVA Pflichtbeiträge", None),
    ExpenseCategory.DEPRECIATION: (True, "AfA", None),
    ExpenseCategory.COMMUTING: (True, "Betriebsausgabe – Fahrtkosten", None),
    ExpenseCategory.MAINTENANCE: (True, "Betriebsausgabe – Instandhaltung", None),
    ExpenseCategory.PROPERTY_TAX: (True, "Betriebsausgabe – Grundsteuer", None),
    ExpenseCategory.LOAN_INTEREST: (True, "Betriebsausgabe – Zinsen", None),
    ExpenseCategory.GROCERIES: (_NEEDS_AI, "Depends on business purpose – AI will analyze", None),
    ExpenseCategory.OTHER: (_NEEDS_AI, "Depends on business relevance – AI will analyze", None),
}

_LANDLORD = {
    ExpenseCategory.MAINTENANCE: (True, "Werbungskosten – Instandhaltung", None),
    ExpenseCategory.PROPERTY_TAX: (True, "Werbungskosten – Grundsteuer", None),
    ExpenseCategory.LOAN_INTEREST: (True, "Werbungskosten – Kreditzinsen", None),
    ExpenseCategory.INSURANCE: (True, "Werbungskosten – Gebäudeversicherung", None),
    ExpenseCategory.UTILITIES: (True, "Werbungskosten – Betriebskosten", None),
    ExpenseCategory.PROFESSIONAL_SERVICES: (True, "Werbungskosten – Hausverwaltung/Rechtsanwalt", None),
    ExpenseCategory.OFFICE_SUPPLIES: (True, "Werbungskosten – Büromaterial", None),
    ExpenseCategory.TELECOM: (True, "Werbungskosten – Nachrichtenaufwand", None),
    ExpenseCategory.BANK_FEES: (True, "Werbungskosten – Bankspesen", None),
    ExpenseCategory.SVS_CONTRIBUTIONS: (True, "SVS/SVA Pflichtbeiträge", None),
    ExpenseCategory.DEPRECIATION: (True, "AfA – Gebäudeabschreibung", None),
    ExpenseCategory.VEHICLE: (True, "Werbungskosten – KFZ für Objektbetreuung", None),
    ExpenseCategory.EQUIPMENT: (True, "Werbungskosten – Ausstattung", None),
    ExpenseCategory.TRAVEL: (True, "Werbungskosten – Fahrtkosten Objektbetreuung", None),
    ExpenseCategory.MARKETING: (True, "Werbungskosten – Inserate", None),
    ExpenseCategory.GROCERIES: (False, "Private Lebensführung", None),
    ExpenseCategory.OTHER: (_NEEDS_AI, "Depends on property relevance – AI will analyze", None),
    ExpenseCategory.RENT: (False, "Not deductible for landlords", None),
    ExpenseCategory.COMMUTING: (False, "Not deductible for landlords", None),
    ExpenseCategory.HOME_OFFICE: (False, "Not deductible for landlords", None),
}

# Mixed = employee + self-employed/landlord activity.
# Business-related categories are deductible; personal ones are not.
# Groceries and other ambiguous items → AI decides.
_MIXED = {
    ExpenseCategory.COMMUTING: (True, "Pendlerpauschale", None),
    ExpenseCategory.HOME_OFFICE: (True, "Home-office-Pauschale / Betriebsausgabe", None),
    ExpenseCategory.OFFICE_SUPPLIES: (True, "Betriebsausgabe / Werbungskosten", None),
    ExpenseCategory.EQUIPMENT: (True, "Betriebsausgabe (AfA for items >€1,000)", None),
    ExpenseCategory.TRAVEL: (True, "Betriebsausgabe – business travel", None),
    ExpenseCategory.MARKETING: (True, "Betriebsausgabe – marketing", None),
    ExpenseCategory.PROFESSIONAL_SERVICES: (True, "Betriebsausgabe – Steuerberater/Rechtsanwalt", None),
    ExpenseCategory.INSURANCE: (True, "Betriebsausgabe / Werbungskosten", None),
    ExpenseCategory.UTILITIES: (True, "Betriebsausgabe / Werbungskosten", None),
    ExpenseCategory.MAINTENANCE: (True, "Werbungskosten – Instandhaltung", None),
    ExpenseCategory.PROPERTY_TAX: (True, "Werbungskosten – Grundsteuer", None),
    ExpenseCategory.LOAN_INTEREST: (True, "Werbungskosten / Betriebsausgabe – Zinsen", None),
    ExpenseCategory.VEHICLE: (True, "Betriebsausgabe – KFZ-Aufwand", None),
    ExpenseCategory.TELECOM: (True, "Betriebsausgabe – Nachrichtenaufwand", None),
    ExpenseCategory.RENT: (True, "Betriebsausgabe – Mietaufwand", None),
    ExpenseCategory.BANK_FEES: (True, "Betriebsausgabe – Bankspesen", None),
    ExpenseCategory.SVS_CONTRIBUTIONS: (True, "SVS/SVA Pflichtbeiträge", None),
    ExpenseCategory.DEPRECIATION: (True, "AfA", None),
    ExpenseCategory.GROCERIES: (_NEEDS_AI, "Depends on business purpose – AI will analyze", None),
    ExpenseCategory.OTHER: (_NEEDS_AI, "Depends on business relevance – AI will analyze", None),
}

_GMBH = {
    ExpenseCategory.OFFICE_SUPPLIES: (True, "Betriebsausgabe", None),
    ExpenseCategory.EQUIPMENT: (True, "Betriebsausgabe (AfA for items >€1,000)", None),
    ExpenseCategory.TRAVEL: (True, "Betriebsausgabe – Reisekosten", None),
    ExpenseCategory.MARKETING: (True, "Betriebsausgabe – Werbung", None),
    ExpenseCategory.PROFESSIONAL_SERVICES: (True, "Betriebsausgabe", None),
    ExpenseCategory.INSURANCE: (True, "Betriebsausgabe", None),
    ExpenseCategory.UTILITIES: (True, "Betriebsausgabe", None),
    ExpenseCategory.MAINTENANCE: (True, "Betriebsausgabe – Instandhaltung", None),
    ExpenseCategory.PROPERTY_TAX: (True, "Betriebsausgabe – Grundsteuer", None),
    ExpenseCategory.LOAN_INTEREST: (True, "Betriebsausgabe – Zinsen", None),
    ExpenseCategory.VEHICLE: (True, "Betriebsausgabe – KFZ-Aufwand", None),
    ExpenseCategory.TELECOM: (True, "Betriebsausgabe – Nachrichtenaufwand", None),
    ExpenseCategory.RENT: (True, "Betriebsausgabe – Mietaufwand", None),
    ExpenseCategory.BANK_FEES: (True, "Betriebsausgabe – Bankspesen", None),
    ExpenseCategory.SVS_CONTRIBUTIONS: (True, "SVS/SVA Pflichtbeiträge", None),
    ExpenseCategory.DEPRECIATION: (True, "AfA", None),
    ExpenseCategory.HOME_OFFICE: (True, "Betriebsausgabe – Home Office", None),
    ExpenseCategory.COMMUTING: (False, "Personal commuting – not a GmbH expense", None),
    ExpenseCategory.GROCERIES: (_NEEDS_AI, "Depends on business purpose – AI will analyze", None),
    ExpenseCategory.OTHER: (_NEEDS_AI, "Depends on business relevance – AI will analyze", None),
}

_RULES = {
    UserType.EMPLOYEE: _EMPLOYEE,
    UserType.SELF_EMPLOYED: _SELF_EMPLOYED,
    UserType.LANDLORD: _LANDLORD,
    UserType.MIXED: _MIXED,
    UserType.GMBH: _GMBH,
}


class DeductibilityChecker:
    """
    Two-tier deductibility checker:
    1. Rule engine for clear-cut cases
    2. LLM analysis for ambiguous cases (NEEDS_AI)
    """

    def check(
        self,
        expense_category: str,
        user_type: str,
        ocr_data: Optional[dict] = None,
        description: str = "",
    ) -> DeductibilityResult:
        """
        Check deductibility. For ambiguous cases, if ocr_data is provided,
        calls AI for a smart judgment; otherwise falls back to a conservative
        rule-based default.

        Args:
            expense_category: e.g. "groceries"
            user_type: e.g. "self_employed", "mixed"
            ocr_data: OCR extracted data (merchant, line_items, amount, etc.)
            description: transaction description text
        """
        try:
            ut = UserType(user_type.lower())
        except ValueError:
            return DeductibilityResult(False, f"Unknown user type: {user_type}")

        try:
            cat = ExpenseCategory(expense_category.lower())
        except ValueError:
            return DeductibilityResult(
                False, f"Unknown category: {expense_category}", requires_review=True
            )

        rules = _RULES.get(ut, {})
        rule = rules.get(cat)

        if not rule:
            return DeductibilityResult(
                False, f"{expense_category} not in rules for {user_type}", requires_review=True
            )

        deductible, reason, max_amount = rule

        # Clear-cut yes
        if deductible is True:
            return DeductibilityResult(True, reason, max_amount=max_amount)

        # Clear-cut no
        if deductible is False:
            return DeductibilityResult(False, reason)

        # NEEDS_AI — ambiguous case
        if ocr_data or description:
            ai_result = self._ai_analyze(ut, cat, ocr_data or {}, description)
            if ai_result:
                return ai_result

        # Fallback when AI is unavailable: for business user types, default to
        # deductible with a generic tip; for employees, default to not deductible.
        if ut in (UserType.SELF_EMPLOYED, UserType.MIXED, UserType.GMBH):
            return DeductibilityResult(
                True,
                "Betriebsausgabe (AI unavailable – default for business user)",
                tax_tip="Bitte Belege und Geschäftszweck dokumentieren.",
            )
        return DeductibilityResult(False, "Not deductible (default)")

    def _ai_analyze(
        self,
        user_type: UserType,
        category: ExpenseCategory,
        ocr_data: dict,
        description: str,
    ) -> Optional[DeductibilityResult]:
        """Call LLM to analyze whether this specific expense is deductible."""
        try:
            from app.services.llm_service import get_llm_service

            llm = get_llm_service()
            if not llm.is_available:
                return None

            # Build context for the AI
            merchant = ocr_data.get("merchant", "unknown")
            amount = ocr_data.get("amount", "unknown")
            line_items = ocr_data.get("line_items", [])
            date = ocr_data.get("date", "")

            items_text = ""
            if line_items and isinstance(line_items, list):
                items_text = "\n".join(
                    f"- {it.get('name', '?')} x{it.get('quantity', 1)} = €{it.get('total_price', '?')}"
                    for it in line_items[:15]  # limit to 15 items
                )

            user_type_labels = {
                UserType.SELF_EMPLOYED: "Selbständig/Einzelunternehmer",
                UserType.MIXED: "Angestellt + selbständige Nebentätigkeit",
                UserType.GMBH: "GmbH-Geschäftsführer",
                UserType.LANDLORD: "Vermieter",
                UserType.EMPLOYEE: "Angestellter",
            }

            system_prompt = (
                "You are an Austrian tax expert (Steuerberater). "
                "Analyze this expense for a business user and determine tax deductibility.\n\n"
                "IMPORTANT rules for business users (Selbständige/GmbH/Mixed):\n"
                "- Purchases at wholesale stores (METRO, etc.) are typically business supplies\n"
                "- Coffee, drinks, snacks for office/clients = Bewirtungsaufwand (deductible)\n"
                "- Cleaning supplies, paper goods = Betriebsausgabe (deductible)\n"
                "- Catering/event supplies in bulk = Bewirtungsaufwand (deductible)\n"
                "- Pure personal groceries (daily food for private meals) = not deductible\n"
                "- Mixed purchases: if business items dominate, mark deductible with tip to separate\n\n"
                "Reply ONLY with JSON: "
                '{"deductible": true/false, "reason": "short reason in German", '
                '"tax_tip": "actionable advice in German for the user"}'
            )

            user_prompt = (
                f"User type: {user_type_labels.get(user_type, str(user_type.value))}\n"
                f"Merchant: {merchant}\n"
                f"Amount: €{amount}\n"
                f"Date: {date}\n"
                f"Description: {description[:200]}\n"
            )
            if items_text:
                user_prompt += f"Line items:\n{items_text}\n"

            user_prompt += "\nIs this expense deductible for this business user?"

            response = llm.generate_simple(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.1,
                max_tokens=300,
            )

            return self._parse_ai_response(response)

        except Exception as e:
            logger.warning("AI deductibility analysis failed: %s", e)
            return None

    def _parse_ai_response(self, response: str) -> Optional[DeductibilityResult]:
        """Parse the JSON response from the AI."""
        try:
            # Strip markdown code fences if present
            text = response.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
            text = text.strip()

            # Find JSON object
            start = text.find("{")
            end = text.rfind("}") + 1
            if start < 0 or end <= start:
                return None

            data = json.loads(text[start:end])
            is_deductible = bool(data.get("deductible", False))
            reason = data.get("reason", "AI analysis")
            tax_tip = data.get("tax_tip", "")

            return DeductibilityResult(
                is_deductible=is_deductible,
                reason=reason,
                tax_tip=tax_tip,
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("Failed to parse AI deductibility response: %s", e)
            return None

    # ---- Convenience methods (backward compat) ----

    def is_deductible(self, expense_category: str, user_type: str) -> bool:
        return self.check(expense_category, user_type).is_deductible

    def get_deduction_rules(self, user_type: str) -> dict:
        try:
            ut = UserType(user_type.lower())
            return _RULES.get(ut, {})
        except ValueError:
            return {}

    def explain_deductibility(self, expense_category: str, user_type: str) -> str:
        result = self.check(expense_category, user_type)
        lines = [
            f"Category: {expense_category}",
            f"User Type: {user_type}",
            f"Deductible: {'Yes' if result.is_deductible else 'No'}",
            f"Reason: {result.reason}",
        ]
        if result.tax_tip:
            lines.append(f"Tip: {result.tax_tip}")
        if result.max_amount:
            lines.append(f"Max amount: €{result.max_amount:.2f}")
        return "\n".join(lines)
