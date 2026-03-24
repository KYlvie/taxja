"""Deductibility checker for expense categorization by user type.

Two-tier approach:
1. Rule engine: clear-cut cases get an immediate yes/no
2. AI analysis: ambiguous cases (e.g. groceries for self-employed) are sent
   to the LLM which examines the actual invoice items, merchant, and user's
   business type to produce a definitive judgment + actionable tax tip.

AI results are cached so the same (category, user_type, industry, merchant)
combination only calls the LLM once.
"""
import hashlib
import json
import logging
from typing import Optional
from enum import Enum
from sqlalchemy.orm import Session

from app.core.transaction_enum_coercion import coerce_enum_member

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
    CLEANING = "cleaning"
    CLOTHING = "clothing"
    SOFTWARE = "software"
    SHIPPING = "shipping"
    FUEL = "fuel"
    EDUCATION = "education"


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
    ExpenseCategory.CLEANING: (False, "Not deductible for employees", None),
    ExpenseCategory.CLOTHING: (False, "Not deductible for employees (private Lebensführung)", None),
    ExpenseCategory.SOFTWARE: (False, "Not deductible for employees", None),
    ExpenseCategory.SHIPPING: (False, "Not deductible for employees", None),
    ExpenseCategory.FUEL: (False, "Use Pendlerpauschale", None),
    ExpenseCategory.EDUCATION: (True, "Werbungskosten – Fortbildung (job-related)", None),
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
    ExpenseCategory.CLEANING: (True, "Betriebsausgabe – Reinigungsmittel", None),
    ExpenseCategory.CLOTHING: (_NEEDS_AI, "Depends on whether it's work clothing – AI will analyze", None),
    ExpenseCategory.SOFTWARE: (True, "Betriebsausgabe – Software-Lizenzen", None),
    ExpenseCategory.SHIPPING: (True, "Betriebsausgabe – Versandkosten", None),
    ExpenseCategory.FUEL: (True, "Betriebsausgabe – Treibstoff", None),
    ExpenseCategory.EDUCATION: (True, "Betriebsausgabe – Fortbildung", None),
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
    ExpenseCategory.CLEANING: (True, "Werbungskosten – Reinigung", None),
    ExpenseCategory.CLOTHING: (False, "Private Lebensführung", None),
    ExpenseCategory.SOFTWARE: (True, "Werbungskosten – Software", None),
    ExpenseCategory.SHIPPING: (False, "Not deductible for landlords", None),
    ExpenseCategory.FUEL: (True, "Werbungskosten – Treibstoff für Objektbetreuung", None),
    ExpenseCategory.EDUCATION: (False, "Not deductible for landlords", None),
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
    ExpenseCategory.CLEANING: (True, "Betriebsausgabe – Reinigungsmittel", None),
    ExpenseCategory.CLOTHING: (_NEEDS_AI, "Depends on work clothing – AI will analyze", None),
    ExpenseCategory.SOFTWARE: (True, "Betriebsausgabe – Software-Lizenzen", None),
    ExpenseCategory.SHIPPING: (True, "Betriebsausgabe – Versandkosten", None),
    ExpenseCategory.FUEL: (True, "Betriebsausgabe – Treibstoff", None),
    ExpenseCategory.EDUCATION: (True, "Betriebsausgabe – Fortbildung", None),
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
    ExpenseCategory.CLEANING: (True, "Betriebsausgabe – Reinigungsmittel", None),
    ExpenseCategory.CLOTHING: (_NEEDS_AI, "Depends on business purpose – AI will analyze", None),
    ExpenseCategory.SOFTWARE: (True, "Betriebsausgabe – Software-Lizenzen", None),
    ExpenseCategory.SHIPPING: (True, "Betriebsausgabe – Versandkosten", None),
    ExpenseCategory.FUEL: (True, "Betriebsausgabe – Treibstoff", None),
    ExpenseCategory.EDUCATION: (True, "Betriebsausgabe – Fortbildung", None),
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


class _DeductibilityCache:
    """
    Simple in-memory cache for AI deductibility decisions.

    Key = hash(category, user_type, business_industry, merchant_normalized).
    This avoids calling the LLM repeatedly for the same combination.
    TTL = 7 days (same as classification cache).
    """

    def __init__(self, ttl: int = 7 * 86400, max_size: int = 5_000):
        import threading
        import time as _time
        self._ttl = ttl
        self._max_size = max_size
        self._store: dict = {}
        self._lock = threading.Lock()
        self._time = _time

    @staticmethod
    def _make_key(
        category: str, user_type: str, business_industry: str, merchant: str,
    ) -> str:
        raw = f"{category}|{user_type}|{business_industry}|{merchant}".lower()
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def get(self, key: str) -> Optional["DeductibilityResult"]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if self._time.monotonic() > expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: "DeductibilityResult") -> None:
        with self._lock:
            if len(self._store) >= self._max_size:
                # evict oldest quarter
                items = sorted(self._store.items(), key=lambda kv: kv[1][1])
                for k, _ in items[: self._max_size // 4]:
                    del self._store[k]
            self._store[key] = (value, self._time.monotonic() + self._ttl)

    def stats(self) -> dict:
        with self._lock:
            now = self._time.monotonic()
            active = sum(1 for _, (__, exp) in self._store.items() if now <= exp)
            return {"total": len(self._store), "active": active}


# Module-level singleton so the cache persists across requests
_deductibility_cache = _DeductibilityCache()


class DeductibilityChecker:
    """
    Two-tier deductibility checker:
    1. Rule engine for clear-cut cases
    2. LLM analysis for ambiguous cases (NEEDS_AI) — with caching
    """

    def __init__(self, db: Optional[Session] = None):
        self.db = db
        if db is not None:
            from app.services.user_deductibility_service import UserDeductibilityService

            self._user_svc = UserDeductibilityService(db)
        else:
            self._user_svc = None

    def check(
        self,
        expense_category: str,
        user_type: str,
        ocr_data: Optional[dict] = None,
        description: str = "",
        business_type: Optional[str] = None,
        business_industry: Optional[str] = None,
        user_id: Optional[int] = None,
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
            business_type: SelfEmployedType value (e.g. "freiberufler", "gewerbetreibende")
                          Only relevant for self_employed and mixed user types.
            business_industry: Specific industry slug (e.g. "gastronomie", "it_dienstleistung")
                              Takes priority over business_type for deductibility rules.
        """
        try:
            ut = UserType(user_type.lower())
        except ValueError:
            return DeductibilityResult(False, f"Unknown user type: {user_type}")

        cat = coerce_enum_member(ExpenseCategory, expense_category)
        if cat is None:
            return DeductibilityResult(
                False, f"Unknown category: {expense_category}", requires_review=True
            )

        user_override = self._try_user_override(
            user_id=user_id,
            description=description,
            expense_category=cat.value,
        )
        if user_override is not None:
            return user_override

        # Check business-type-specific overrides first (self-employed / mixed)
        if (business_type or business_industry) and ut in (UserType.SELF_EMPLOYED, UserType.MIXED):
            override = self._check_business_type_override(business_type, cat, business_industry)
            if override is not None:
                return override

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

        # NEEDS_AI — ambiguous case (check cache first, then LLM)
        if ocr_data or description:
            merchant = (ocr_data or {}).get("merchant", "") or description[:50]
            cache_key = _deductibility_cache._make_key(
                cat.value, ut.value, business_industry or "", merchant,
            )
            cached = _deductibility_cache.get(cache_key)
            if cached is not None:
                logger.info(
                    "Deductibility cache hit: %s/%s → %s",
                    cat.value, ut.value, cached.is_deductible,
                )
                return cached

            ai_result = self._ai_analyze(ut, cat, ocr_data or {}, description, business_type, business_industry)
            if ai_result:
                _deductibility_cache.set(cache_key, ai_result)
                return ai_result

        # Fallback when AI is unavailable: for business user types, default to
        # deductible with a generic tip; for employees, default to not deductible.
        # ALWAYS mark as requires_review so the system does not silently commit
        # a directional tax conclusion without human confirmation.
        if ut in (UserType.SELF_EMPLOYED, UserType.MIXED, UserType.GMBH):
            return DeductibilityResult(
                True,
                "Betriebsausgabe (AI unavailable – default for business user)",
                tax_tip="Bitte Belege und Geschäftszweck dokumentieren.",
                requires_review=True,
            )
        return DeductibilityResult(False, "Not deductible (default)", requires_review=True)

    def _try_user_override(
        self,
        *,
        user_id: Optional[int],
        description: str,
        expense_category: str,
    ) -> Optional[DeductibilityResult]:
        user_service = getattr(self, "_user_svc", None)
        if user_service is None or not user_id or not description:
            return None

        rule = user_service.lookup(
            user_id=user_id,
            description=description,
            expense_category=expense_category,
        )
        if rule is None:
            return None

        user_service.record_hit(rule)
        return DeductibilityResult(
            is_deductible=bool(getattr(rule, "is_deductible", False)),
            reason=getattr(rule, "reason", None) or "Learned from your previous correction",
        )

    def _check_business_type_override(
        self,
        business_type: str,
        category: ExpenseCategory,
        business_industry: Optional[str] = None,
    ) -> Optional[DeductibilityResult]:
        """Check if the business sub-type has a specific override for this category."""
        try:
            from app.services.business_deductibility_rules import get_business_type_override
            override = get_business_type_override(business_type, category.value, business_industry=business_industry)
            if not override:
                return None

            is_deductible = override["is_deductible"]
            reason = override["reason"]
            max_amount = override.get("max_amount")
            deductible_pct = override.get("deductible_pct")

            # Clear yes/no
            if is_deductible is True:
                tip = None
                if deductible_pct and deductible_pct < 1.0:
                    tip = f"Nur {int(deductible_pct * 100)}% absetzbar (Repräsentationsaufwand)"
                return DeductibilityResult(True, reason, tax_tip=tip, max_amount=max_amount)
            if is_deductible is False:
                return DeductibilityResult(False, reason)

            # NEEDS_AI — return None to fall through to base rules + AI
            return None

        except ImportError:
            return None

    def _ai_analyze(
        self,
        user_type: UserType,
        category: ExpenseCategory,
        ocr_data: dict,
        description: str,
        business_type: Optional[str] = None,
        business_industry: Optional[str] = None,
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

            # Enrich user type label with business sub-type AND industry
            business_type_context = ""
            if business_type and user_type in (UserType.SELF_EMPLOYED, UserType.MIXED):
                try:
                    from app.services.business_deductibility_rules import BUSINESS_TYPE_CONTEXTS, INDUSTRY_CONTEXTS
                    from app.models.user import SelfEmployedType
                    bt = SelfEmployedType(business_type)
                    ctx = BUSINESS_TYPE_CONTEXTS.get(bt, {})
                    business_type_context = (
                        f"\nBusiness sub-type: {ctx.get('description_de', business_type)}\n"
                        f"Typical expenses for this type: {', '.join(ctx.get('typical_expenses', []))}\n"
                    )
                    # Add industry-specific context (highest specificity)
                    if business_industry:
                        ind_ctx = INDUSTRY_CONTEXTS.get(business_industry.lower(), {})
                        if ind_ctx:
                            business_type_context += (
                                f"Specific industry: {ind_ctx.get('description_de', business_industry)}\n"
                                f"Industry-typical expenses: {', '.join(ind_ctx.get('typical_expenses', []))}\n"
                                f"IMPORTANT: For this industry ({ind_ctx.get('description_de', '')}), "
                                f"evaluate whether items on this receipt are plausible business expenses.\n"
                            )
                except (ValueError, ImportError):
                    pass

            # Build industry-aware system prompt
            # Industry context is a STRONG PRIOR but not a hard rule:
            # if receipt content contradicts industry expectation, content wins.
            industry_rules_block = ""
            if business_industry:
                try:
                    from app.services.business_deductibility_rules import INDUSTRY_CONTEXTS
                    ind_ctx = INDUSTRY_CONTEXTS.get(business_industry.lower(), {})
                    if ind_ctx:
                        industry_rules_block = (
                            f"\n## Branchenkontext (starke Vorannahme, aber Beleginhalt hat Vorrang)\n"
                            f"Branche: {ind_ctx.get('description_de', business_industry)}\n"
                            f"Branchentypische Betriebsausgaben: {', '.join(ind_ctx.get('typical_expenses', []))}\n"
                            f"REGEL: Wenn der Beleg Artikel zeigt, die fuer diese Branche typisch sind "
                            f"(z.B. Lebensmittel fuer Gastronomie = Wareneinsatz), dann als absetzbar bewerten.\n"
                            f"ABER: Wenn der Beleg eindeutig private Artikel zeigt (Kosmetik, Kleidung, "
                            f"Spielzeug, Heimdekoration), dann NICHT absetzbar — auch wenn der Benutzer "
                            f"in einer Branche ist, wo aehnliche Artikel manchmal beruflich genutzt werden.\n"
                            f"Bei Mischbelegen: Betriebliche Positionen absetzbar, private nicht. Tipp geben.\n"
                        )
                except ImportError:
                    pass

            system_prompt = (
                "Du bist ein oesterreichischer Steuerberater. "
                "Analysiere diese Ausgabe und bestimme die steuerliche Absetzbarkeit.\n\n"
                "GRUNDREGELN fuer Geschaeftskunden (Selbstaendige/GmbH/Mixed):\n"
                "- Einkauf bei Grosshandel (METRO etc.) = typischerweise Betriebsausgabe\n"
                "- Kaffee, Getraenke, Snacks fuer Buero/Kunden = Bewirtungsaufwand (absetzbar)\n"
                "- Reinigungsmittel, Papier = Betriebsausgabe (absetzbar)\n"
                "- Catering/Event-Bedarf in Grossmengen = Bewirtungsaufwand (absetzbar)\n"
                "- Rein private Lebensmittel (taegliches Essen) = NICHT absetzbar\n"
                "- Mischbelege: wenn betriebliche Positionen ueberwiegen, als absetzbar mit Hinweis\n"
                f"{industry_rules_block}\n"
                "Antworte NUR mit JSON: "
                '{"deductible": true/false, "reason": "kurze Begruendung auf Deutsch", '
                '"tax_tip": "konkreter Tipp auf Deutsch fuer den Benutzer"}'
            )

            user_prompt = (
                f"User type: {user_type_labels.get(user_type, str(user_type.value))}\n"
                f"{business_type_context}"
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

    def is_deductible(self, expense_category: str, user_type: str, business_type: Optional[str] = None, business_industry: Optional[str] = None) -> bool:
        return self.check(expense_category, user_type, business_type=business_type, business_industry=business_industry).is_deductible

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

    def ai_split_analyze(
        self,
        user_type: str,
        ocr_data: dict,
        description: str = "",
        business_type: Optional[str] = None,
        business_industry: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Ask AI to split a mixed receipt into deductible vs non-deductible items.

        Returns dict like:
        {
            "has_split": True/False,
            "deductible_amount": 12.50,
            "non_deductible_amount": 8.30,
            "deductible_items": "Druckerpapier A4, Kugelschreiber",
            "non_deductible_items": "Milch, Butter, Toastbrot",
            "deductible_reason": "...",
            "non_deductible_reason": "...",
            "tax_tip": "..."
        }
        Returns None if AI unavailable or no line items to split.
        """
        line_items = ocr_data.get("line_items", [])
        if not line_items or not isinstance(line_items, list) or len(line_items) < 2:
            return None

        try:
            from app.services.llm_service import get_llm_service

            llm = get_llm_service()
            if not llm.is_available:
                return None

            ut_labels = {
                "self_employed": "Selbständig/Einzelunternehmer",
                "mixed": "Angestellt + selbständige Nebentätigkeit",
                "gmbh": "GmbH-Geschäftsführer",
                "landlord": "Vermieter",
                "employee": "Angestellter",
            }

            merchant = ocr_data.get("merchant", "unknown")
            items_text = "\n".join(
                f"- {it.get('name', '?')} €{it.get('total_price', '?')}"
                for it in line_items[:20]
            )

            # Build industry-specific context for smarter split analysis
            industry_context = ""
            if business_industry or business_type:
                try:
                    from app.services.business_deductibility_rules import INDUSTRY_CONTEXTS, BUSINESS_TYPE_CONTEXTS
                    if business_industry:
                        ind_ctx = INDUSTRY_CONTEXTS.get(business_industry.lower(), {})
                        if ind_ctx:
                            industry_context = (
                                f"\nUser's specific industry: {ind_ctx.get('description_de', business_industry)}\n"
                                f"Industry-typical deductible expenses: {', '.join(ind_ctx.get('typical_expenses', []))}\n"
                                f"CRITICAL: For {ind_ctx.get('description_de', '')}, items like "
                                f"{', '.join(ind_ctx.get('typical_expenses', [])[:3])} are business expenses (Wareneinsatz/Betriebsausgabe).\n"
                            )
                    elif business_type:
                        from app.models.user import SelfEmployedType
                        bt = SelfEmployedType(business_type)
                        bt_ctx = BUSINESS_TYPE_CONTEXTS.get(bt, {})
                        if bt_ctx:
                            industry_context = (
                                f"\nUser's business type: {bt_ctx.get('description_de', business_type)}\n"
                                f"Typical expenses: {', '.join(bt_ctx.get('typical_expenses', []))}\n"
                            )
                except (ValueError, ImportError):
                    pass

            # Build industry-aware split prompt
            # Industry is a STRONG PRIOR but receipt content can override
            industry_split_block = ""
            if business_industry:
                try:
                    from app.services.business_deductibility_rules import INDUSTRY_CONTEXTS
                    ind_ctx = INDUSTRY_CONTEXTS.get(business_industry.lower(), {})
                    if ind_ctx:
                        industry_split_block = (
                            f"\n## Branchenkontext (starke Vorannahme)\n"
                            f"Branche: {ind_ctx.get('description_de', business_industry)}\n"
                            f"Branchentypischer Wareneinsatz: {', '.join(ind_ctx.get('typical_expenses', []))}\n"
                            f"Fuer diese Branche gilt: Wenn Artikel branchentypisch sind, "
                            f"dann als Betriebsausgabe/Wareneinsatz werten.\n"
                            f"ABER: Eindeutig private Artikel (Kosmetik fuer Privatgebrauch, "
                            f"Spielzeug, Heimdekoration) bleiben NICHT absetzbar.\n"
                        )
                except ImportError:
                    pass

            system_prompt = (
                "Du bist ein oesterreichischer Steuerberater. Ein Geschaeftskunde hat "
                "mehrere Artikel auf einem Beleg. Klassifiziere JEDEN Artikel als "
                "absetzbar (betrieblich) oder nicht absetzbar (privat).\n\n"
                "Grundregeln:\n"
                "- Buerobedarf, Reinigungsmittel, Druckerpapier = absetzbar\n"
                "- Kaffee, Getraenke, Snacks fuer Buero/Kunden = absetzbar (Bewirtung)\n"
                "- Private Lebensmittel (Brot, Milch, Butter, Fleisch) = NICHT absetzbar\n"
                "- Hygieneartikel fuer Privatgebrauch = NICHT absetzbar\n"
                "- Wenn ALLE Artikel einer Kategorie angehoeren, setze has_split=false\n"
                f"{industry_split_block}\n"
                "WICHTIG: Betraege durch SUMMIERUNG der gezeigten Preise berechnen. "
                "deductible_amount + non_deductible_amount MUSS die Belegsumme ergeben.\n\n"
                "Antworte NUR mit JSON:\n"
                '{"has_split": true/false, '
                '"deductible_amount": Zahl, "non_deductible_amount": Zahl, '
                '"deductible_items": "kommagetrennte Artikelnamen", '
                '"non_deductible_items": "kommagetrennte Artikelnamen", '
                '"deductible_reason": "kurze Begruendung auf Deutsch", '
                '"non_deductible_reason": "kurze Begruendung auf Deutsch", '
                '"tax_tip": "konkreter Tipp auf Deutsch"}'
            )

            user_prompt = (
                f"User type: {ut_labels.get(user_type.lower(), user_type)}\n"
                f"{industry_context}"
                f"Merchant: {merchant}\n"
                f"Items:\n{items_text}\n"
                f"\nClassify each item and calculate split amounts."
            )

            response = llm.generate_simple(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.1,
                max_tokens=400,
            )

            return self._parse_split_response(response)

        except Exception as e:
            logger.warning("AI split analysis failed: %s", e)
            return None

    def _parse_split_response(self, response: str) -> Optional[dict]:
        """Parse the split analysis JSON from AI."""
        try:
            text = response.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
            text = text.strip()

            start = text.find("{")
            end = text.rfind("}") + 1
            if start < 0 or end <= start:
                return None

            data = json.loads(text[start:end])

            # Validate required fields
            if "has_split" not in data:
                return None

            return {
                "has_split": bool(data.get("has_split", False)),
                "deductible_amount": float(data.get("deductible_amount", 0)),
                "non_deductible_amount": float(data.get("non_deductible_amount", 0)),
                "deductible_items": str(data.get("deductible_items", "")),
                "non_deductible_items": str(data.get("non_deductible_items", "")),
                "deductible_reason": str(data.get("deductible_reason", "")),
                "non_deductible_reason": str(data.get("non_deductible_reason", "")),
                "tax_tip": str(data.get("tax_tip", "")),
            }
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            logger.warning("Failed to parse AI split response: %s", e)
            return None

