"""
AI Orchestrator — Central dispatch layer for all AI-powered features.

Routes user requests to the appropriate service based on intent detection:
- Tax Q&A (RAG)
- Tax calculation (engine)
- Document analysis (OCR + LLM extraction)
- Transaction classification
- Tax optimization suggestions
- Deduction eligibility checks
- What-if simulation

Uses function-calling style: detects intent → selects tool → executes → formats response.
"""
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Intent definitions
# ---------------------------------------------------------------------------

class UserIntent(str, Enum):
    """Detected user intent categories."""
    TAX_QA = "tax_qa"                        # General tax question → RAG
    CALCULATE_TAX = "calculate_tax"          # "How much tax do I owe?" → engine
    CALCULATE_VAT = "calculate_vat"          # VAT calculation
    CALCULATE_SVS = "calculate_svs"          # SVS social insurance
    CALCULATE_KEST = "calculate_kest"        # Capital gains tax
    CALCULATE_IMMOEST = "calculate_immoest"  # Real estate gains tax
    CLASSIFY_TRANSACTION = "classify_tx"     # "Is this deductible?"
    CHECK_DEDUCTIBILITY = "check_deduct"     # Deductibility check
    OPTIMIZE_TAX = "optimize_tax"            # Tax optimization suggestions
    WHAT_IF = "what_if"                      # What-if simulation
    EXPLAIN_DOCUMENT = "explain_doc"         # Explain an OCR result
    SUMMARIZE_STATUS = "summarize_status"    # "What's my tax situation?"
    SYSTEM_HELP = "system_help"              # "How do I use this?" → built-in guide
    UNKNOWN = "unknown"                      # Fallback → RAG


@dataclass
class IntentResult:
    intent: UserIntent
    confidence: float
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrchestratorResponse:
    """Unified response from the orchestrator."""
    text: str
    intent: UserIntent
    data: Optional[Dict[str, Any]] = None  # structured payload (calculations, etc.)
    suggestions: Optional[List[str]] = None  # follow-up suggestions
    show_disclaimer: bool = False  # whether frontend should show tax disclaimer
    source_tier: Optional[str] = None  # rag | llm | lightweight | rule_based


# ---------------------------------------------------------------------------
# Intent detection — keyword + regex based (fast, no LLM needed)
# ---------------------------------------------------------------------------

# Patterns per intent: list of (regex_pattern, weight) tuples
# NOTE: \b doesn't work with CJK chars, so CJK patterns use plain substring matching.
_INTENT_PATTERNS: Dict[UserIntent, List[tuple]] = {
    UserIntent.CALCULATE_TAX: [
        (r"(berechn|calculat|rechne|ausrechn).*(steuer|tax|einkommensteuer)", 0.95),
        (r"(steuer|tax|einkommensteuer).*(berechn|calculat|rechne)", 0.95),
        (r"计算.*(所得税|税|steuer|tax)", 0.95),
        (r"(所得税|税).*(计算|算)", 0.95),
        (r"(wie\s?viel|how\s?much|多少).*(steuer|tax|zahlen|pay|税|缴)", 0.90),
        (r"(steuerlast|tax burden|tax liability|纳税额)", 0.90),
        (r"(netto|net income|到手|净收入).*(einkommen|income|收入)", 0.85),
        (r"(交多少税|要交.*税|缴.*税)", 0.90),
    ],
    UserIntent.CALCULATE_VAT: [
        (r"(ust|umsatzsteuer|vat|mehrwertsteuer).*(berechn|calculat|计算)", 0.95),
        (r"(berechn|calculat|计算).*(ust|umsatzsteuer|vat|mehrwertsteuer|增值税)", 0.95),
        (r"增值税.*(计算|算)", 0.95),
        (r"计算.*增值税", 0.95),
        (r"(kleinunternehmer|small business|小企业)", 0.90),
        (r"(vorsteuer|input.?vat|umsatzsteuer)", 0.85),
    ],
    UserIntent.CALCULATE_SVS: [
        (r"(svs|sozialversicherung).*(berechn|calculat|beitr)", 0.95),
        (r"(berechn|calculat).*(svs|sozialversicherung)", 0.95),
        (r"(计算|算).*svs", 0.95),
        (r"svs.*(计算|算|社保)", 0.95),
        (r"(社保|sozialversicherung).*(计算|berechn)", 0.90),
        (r"计算.*社保", 0.90),
        (r"social insurance.*(calculat|contribut)", 0.85),
    ],
    UserIntent.CALCULATE_KEST: [
        (r"(kest|kapitalertragsteuer).*(berechn|calculat)", 0.95),
        (r"(berechn|calculat).*(kest|kapitalertrag)", 0.95),
        (r"(计算|算).*(kest|资本利得税|资本.*税)", 0.95),
        (r"capital gains? tax", 0.95),
        (r"(dividende|dividend|股息).*(steuer|tax|税)", 0.90),
        (r"(steuer|tax|税).*(dividende|dividend|股息)", 0.90),
        (r"资本利得税", 0.95),
        (r"\bkest\b", 0.90),
    ],
    UserIntent.CALCULATE_IMMOEST: [
        (r"(immoest|immobilienertragsteuer)", 0.95),
        (r"real estate.*(tax|gain)", 0.95),
        (r"房产.*税", 0.95),
        (r"(grundstück|immobilie|property|房产|不动产).*(verkauf|sale|sell|卖|出售).*(steuer|tax|税)", 0.90),
        (r"(verkauf|sale|卖).*(wohnung|haus|house|apartment|房).*(steuer|tax|steuerpflicht)", 0.85),
        (r"property.*(sale|sell).*(tax|gain)", 0.90),
    ],
    UserIntent.CLASSIFY_TRANSACTION: [
        (r"(kategori|classif|einordnen|zuordnen).*(transaktion|transaction|buchung|rechnung|expense)", 0.90),
        (r"(分类|归类).*(交易|buchung|transaction)", 0.90),
        (r"(welche kategorie|which category|什么类别)", 0.85),
        (r"classif.*(this|diese|expense|rechnung)", 0.90),
        (r"(klassifizier|kategorisier).*(rechnung|ausgabe|beleg)", 0.90),
    ],
    UserIntent.CHECK_DEDUCTIBILITY: [
        (r"(absetzbar|deductible|absetzen|abzugsfähig)", 0.90),
        (r"(可以抵扣|能抵税|可以扣除|能抵扣|可以抵税|抵税)", 0.90),
        (r"(kann ich|can i|darf ich).*(absetz|deduct|abzieh)", 0.90),
        (r"(能不能|可不可以).*(抵扣|扣除)", 0.90),
        (r"(werbungskosten|sonderausgaben|außergewöhnliche belastung)", 0.80),
    ],
    UserIntent.OPTIMIZE_TAX: [
        (r"(optimier|optimiz).*(steuer|tax)", 0.90),
        (r"(steuer|tax).*(optimier|optimiz|spar|tipps|tips)", 0.90),
        (r"(spar|save).*(steuer|tax)", 0.90),
        (r"(steuer|tax).*(spar|save)", 0.90),
        (r"(节税|省税|减税|税.*优化|优化.*税)", 0.90),
        (r"(节税建议|税务.*建议|steueroptimierung)", 0.85),
        (r"tax optimization", 0.85),
    ],
    UserIntent.WHAT_IF: [
        (r"was wäre wenn", 0.90),
        (r"what if", 0.90),
        (r"(假如|如果.*会怎)", 0.90),
        (r"(simulat|scenario|szenarien|模拟|场景)", 0.85),
        (r"(wenn ich|if i|如果我).*(mehr|weniger|more|less|多|少)", 0.80),
        (r"\bvs\b", 0.80),
    ],
    UserIntent.EXPLAIN_DOCUMENT: [
        (r"(erklär|explain).*(dokument|document|beleg|receipt)", 0.90),
        (r"(解释|说明).*(文档|发票|收据|dokument)", 0.90),
        (r"(was steht|what does).*(dokument|document|rechnung|invoice)", 0.85),
        (r"(was bedeut|what do).*(kz|kennzahl|feld|field)", 0.90),
        (r"(kz|kennzahl).*(bedeut|mean|heißt|是什么)", 0.90),
        (r"(lohnzettel|l16|l1k?|e1[abk]?|u1|u30|jahresabschluss|svs|grundsteuer|kontoauszug).*(erklär|explain|解释|说明|是什么)", 0.85),
        (r"(erklär|explain|解释|说明).*(lohnzettel|l16|l1k?|e1[abk]?|u1|u30|jahresabschluss|svs|grundsteuer|kontoauszug)", 0.85),
    ],
    UserIntent.SUMMARIZE_STATUS: [
        (r"(zusammenfass|summary|überblick|overview).*(steuer|tax)", 0.90),
        (r"(总结|概况|情况).*(steuer|tax|税)", 0.90),
        (r"(steuer|tax|税).*(总结|概况|zusammenfass|summary|überblick|overview)", 0.90),
        (r"(meine|my|我的).*(steuer.*situation|tax.*situation|税务.*情况)", 0.90),
        (r"(wie stehe ich|where do i stand).*(steuer|tax)", 0.85),
        (r"(wie stehe ich steuerlich|税务情况|税务状况)", 0.85),
    ],
    UserIntent.SYSTEM_HELP: [
        # Chinese: "在哪里/怎么/如何" + system action keywords
        (r"(在哪|在哪里|哪里可以|怎么|如何|怎样).*(添加|新增|创建|上传|导入|导出|删除|修改|编辑|查看|管理|设置|配置)", 0.95),
        (r"(添加|新增|创建|上传|导入|导出|删除|修改|编辑|查看|管理|设置|配置).*(在哪|在哪里|怎么|如何|怎样)", 0.95),
        (r"(在哪|怎么|如何).*(资产|房产|交易|文档|发票|收据|报告|报表|合同|贷款)", 0.95),
        (r"(资产|房产|交易|文档|发票|收据|报告|报表|合同|贷款).*(在哪|怎么.*[添删改查])", 0.95),
        (r"(怎么用|如何使用|使用方法|操作指南|帮助|功能介绍|系统.*怎么)", 0.95),
        (r"(这个系统|这个平台|这个app|taxja).*(怎么|如何|能做什么|有什么功能)", 0.95),
        (r"(教我|告诉我).*(怎么用|如何|怎么操作)", 0.90),
        # German: "wo/wie" + system action keywords
        (r"(wo kann ich|wo finde ich|wie kann ich|wie geht|wie lade ich|wie erstelle ich|wie lösche ich|wie bearbeite ich).*(hinzufügen|erstellen|hochladen|hoch|löschen|bearbeiten|anzeigen|verwalten|einstellen)", 0.95),
        (r"(wo|wie).*(immobilie|transaktion|dokument|rechnung|beleg|bericht|vertrag|kredit).*(hinzufügen|erstellen|hochladen|anlegen)", 0.95),
        (r"(wie funktioniert|wie benutze ich|anleitung|hilfe|funktionen)", 0.95),
        # English: "where/how" + system action keywords
        (r"(where can i|where do i|how can i|how do i|how to).*(add|create|upload|delete|edit|view|manage|set up|configure)", 0.95),
        (r"(where|how).*(property|transaction|document|invoice|receipt|report|contract|loan).*(add|create|upload)", 0.95),
        (r"(how does.*work|how to use|help|tutorial|guide|features)", 0.90),
        (r"(what can.*do|what features|show me how)", 0.90),
    ],
}


def detect_intent(message: str, user_context: Optional[Dict] = None) -> IntentResult:
    """
    Detect user intent from message text using pattern matching.

    Returns the highest-confidence match, or UNKNOWN → falls back to RAG.
    Specific intents (VAT, SVS, KESt, ImmoESt) take priority over generic CALCULATE_TAX
    when both match at the same confidence level.
    """
    msg = message.lower().strip()

    # Collect all matching intents
    matches: List[IntentResult] = []

    for intent, patterns in _INTENT_PATTERNS.items():
        for pattern, weight in patterns:
            if re.search(pattern, msg, re.IGNORECASE):
                matches.append(IntentResult(intent=intent, confidence=weight))
                break  # one match per intent is enough

    if not matches:
        best = IntentResult(intent=UserIntent.TAX_QA, confidence=0.5)
    else:
        # Sort: highest confidence first; on tie, prefer specific intents over generic
        _SPECIFIC = {
            UserIntent.CALCULATE_VAT,
            UserIntent.CALCULATE_SVS,
            UserIntent.CALCULATE_KEST,
            UserIntent.CALCULATE_IMMOEST,
            UserIntent.CHECK_DEDUCTIBILITY,
            UserIntent.OPTIMIZE_TAX,
            UserIntent.WHAT_IF,
            UserIntent.SUMMARIZE_STATUS,
            UserIntent.EXPLAIN_DOCUMENT,
            UserIntent.CLASSIFY_TRANSACTION,
            UserIntent.SYSTEM_HELP,
        }

        def _sort_key(r: IntentResult):
            # Higher confidence first, then specific > generic
            specificity = 1 if r.intent in _SPECIFIC else 0
            return (-r.confidence, -specificity)

        matches.sort(key=_sort_key)
        best = matches[0]

    # ③ LLM fallback for intent detection when regex matching is weak.
    # Only fires when no regex pattern matched at all (best came from the
    # "no matches" branch or confidence is very low).
    if best.confidence < 0.6 and best.intent == UserIntent.TAX_QA:
        llm_intent = _llm_intent_fallback(msg)
        if llm_intent is not None:
            best = llm_intent

    # If nothing matched well, default to TAX_QA (general question)
    if best.confidence < 0.5:
        best = IntentResult(intent=UserIntent.TAX_QA, confidence=0.5)

    # Extract numeric params from message for calculation intents
    if best.intent in (
        UserIntent.CALCULATE_TAX,
        UserIntent.CALCULATE_VAT,
        UserIntent.CALCULATE_SVS,
        UserIntent.CALCULATE_KEST,
    ):
        best.params = _extract_numeric_params(msg)

    return best


def _normalize_number(raw: str) -> str:
    """Normalize a number string that may use German (50.000,50) or English (50,000.50) format."""
    has_dot = "." in raw
    has_comma = "," in raw
    if has_dot and has_comma:
        # Both present: last separator is decimal
        last_dot = raw.rfind(".")
        last_comma = raw.rfind(",")
        if last_dot > last_comma:
            # English: 50,000.50
            return raw.replace(",", "")
        else:
            # German: 50.000,50
            return raw.replace(".", "").replace(",", ".")
    elif has_dot:
        # Dot only: German thousands (50.000) or English decimal (50.5)
        # If dot is followed by exactly 3 digits at end, treat as thousands separator
        if re.search(r"\.\d{3}$", raw):
            return raw.replace(".", "")
        return raw  # decimal point
    elif has_comma:
        # Comma only: English thousands (80,000) or German decimal (50,50)
        if re.search(r",\d{3}$", raw):
            return raw.replace(",", "")
        return raw.replace(",", ".")  # decimal comma
    return raw


def _extract_numeric_params(message: str) -> Dict[str, Any]:
    """Extract monetary amounts and year from message text."""
    params: Dict[str, Any] = {}

    # Extract amounts like €50000, 50.000€, 50000 Euro, 12万欧, etc.
    amount_patterns = [
        r"€\s?([\d.,]+)",
        r"([\d.,]+)\s?€",
        r"([\d.,]+)\s?(?:euro|EUR|欧元|欧)",
        r"([\d.,]+)\s?万\s?(?:欧元|欧|€|euro|EUR)",
        r"(?:einkommen|income|收入|umsatz|turnover|营业额|gehalt|salary|工资|税前)[:\s]*([\d.,]+)",
    ]
    wan_pattern = re.compile(r"([\d.,]+)\s?万", re.IGNORECASE)
    amounts = []
    for pat in amount_patterns:
        for m in re.finditer(pat, message, re.IGNORECASE):
            raw = m.group(1) if m.group(1) else m.group(0)
            raw = _normalize_number(raw)
            try:
                val = float(raw)
                # Check if this was a 万 (10k) pattern
                if "万" in pat:
                    val *= 10000
                amounts.append(val)
            except ValueError:
                pass
    # Fallback: detect 万 multiplier in standalone numbers (e.g. "7万")
    if not amounts:
        for m in wan_pattern.finditer(message):
            raw = _normalize_number(m.group(1))
            try:
                amounts.append(float(raw) * 10000)
            except ValueError:
                pass
    # Last resort: find any standalone large number
    if not amounts:
        for m in re.finditer(r"\b(\d[\d.,]{2,})\b", message):
            raw = _normalize_number(m.group(1))
            try:
                val = float(raw)
                if val >= 100:
                    amounts.append(val)
            except ValueError:
                pass
    if amounts:
        params["amount"] = amounts[0]
        if len(amounts) > 1:
            params["amounts"] = amounts

    # Extract year
    year_match = re.search(r"\b(202[0-9])\b", message)
    if year_match:
        params["year"] = int(year_match.group(1))

    return params


# ---------------------------------------------------------------------------
# ③ LLM-based intent fallback (called only when regex fails)
# ---------------------------------------------------------------------------

# Simple in-memory cache so repeated similar questions don't re-call LLM.
# Keyed on MD5 of the first 100 chars of the message (not just 5 words)
# to avoid collisions between semantically different questions.
_intent_cache: Dict[str, IntentResult] = {}
_INTENT_CACHE_MAX_SIZE = 1000

_INTENT_CLASSIFICATION_PROMPT = (
    "Classify the user's question into exactly ONE of these intents:\n"
    "- calculate_tax: Calculate income tax\n"
    "- calculate_vat: Calculate VAT / Umsatzsteuer\n"
    "- calculate_svs: Calculate social insurance (SVS/GSVG)\n"
    "- calculate_kest: Calculate capital gains tax (KESt)\n"
    "- calculate_immoest: Calculate real estate gains tax\n"
    "- classify_tx: Classify a transaction into a category\n"
    "- check_deduct: Check if an expense is tax-deductible\n"
    "- optimize_tax: Tax saving tips / optimization\n"
    "- what_if: What-if scenario / simulation\n"
    "- explain_doc: Explain a document or receipt\n"
    "- summarize_status: Summarize tax situation\n"
    "- system_help: How to use this system / app navigation / feature guide\n"
    "- tax_qa: General tax question\n\n"
    "Reply with ONLY the intent name, nothing else."
)

_INTENT_NAME_MAP = {
    "calculate_tax": UserIntent.CALCULATE_TAX,
    "calculate_vat": UserIntent.CALCULATE_VAT,
    "calculate_svs": UserIntent.CALCULATE_SVS,
    "calculate_kest": UserIntent.CALCULATE_KEST,
    "calculate_immoest": UserIntent.CALCULATE_IMMOEST,
    "classify_tx": UserIntent.CLASSIFY_TRANSACTION,
    "check_deduct": UserIntent.CHECK_DEDUCTIBILITY,
    "optimize_tax": UserIntent.OPTIMIZE_TAX,
    "what_if": UserIntent.WHAT_IF,
    "explain_doc": UserIntent.EXPLAIN_DOCUMENT,
    "summarize_status": UserIntent.SUMMARIZE_STATUS,
    "system_help": UserIntent.SYSTEM_HELP,
    "tax_qa": UserIntent.TAX_QA,
}


def _llm_intent_fallback(message: str) -> Optional[IntentResult]:
    """
    Use a cheap LLM call to classify intent when regex patterns fail.

    Results are cached by SHA-256 of the first 100 characters of the message
    to avoid collisions between semantically different questions while
    still deduplicating identical or near-identical inputs.
    """
    import hashlib
    cache_key = hashlib.sha256(message[:100].lower().strip().encode()).hexdigest()[:16]

    if cache_key in _intent_cache:
        return _intent_cache[cache_key]

    try:
        from app.services.llm_service import get_llm_service
        llm = get_llm_service()
        if not llm.is_available:
            return None

        response = llm.generate_simple(
            system_prompt=_INTENT_CLASSIFICATION_PROMPT,
            user_prompt=message[:200],
            temperature=0.0,
            max_tokens=20,
        )

        if not response:
            return None

        intent_name = response.strip().lower().replace('"', "").replace("'", "")
        intent = _INTENT_NAME_MAP.get(intent_name)
        if intent is None:
            # Try partial match
            for key, val in _INTENT_NAME_MAP.items():
                if key in intent_name:
                    intent = val
                    break

        if intent is None or intent == UserIntent.TAX_QA:
            return None  # Don't override with TAX_QA — that's already the default

        result = IntentResult(intent=intent, confidence=0.80)
        # Evict cache if it grows too large
        if len(_intent_cache) >= _INTENT_CACHE_MAX_SIZE:
            _intent_cache.clear()
        _intent_cache[cache_key] = result
        logger.info("LLM intent fallback: '%s' → %s", message[:50], intent.value)
        return result

    except Exception as e:
        logger.debug("LLM intent fallback failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Tool registry — wraps existing services as callable tools
# ---------------------------------------------------------------------------

class ToolRegistry:
    """Registry of available tools the orchestrator can invoke."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id

    # -- Tax calculation ------------------------------------------------

    def calculate_income_tax(
        self, gross_income: float, year: int = 2026, **kwargs
    ) -> Dict[str, Any]:
        """Run the full tax calculation engine."""
        from app.services.tax_calculation_engine import TaxCalculationEngine
        from app.services.svs_calculator import UserType
        from app.models.user import User

        # Determine user_type from DB
        user = self.db.query(User).filter(User.id == self.user_id).first()
        user_type_str = getattr(user, "user_type", "EMPLOYEE") if user else "EMPLOYEE"
        if hasattr(user_type_str, "value"):
            user_type_str = user_type_str.value
        type_map = {
            "EMPLOYEE": UserType.EMPLOYEE,
            "SELF_EMPLOYED": UserType.GSVG,
            "LANDLORD": UserType.EMPLOYEE,
            "SMALL_BUSINESS": UserType.GSVG,
            "MIXED": UserType.GSVG,
        }
        user_type = type_map.get(str(user_type_str).upper(), UserType.EMPLOYEE)

        engine = TaxCalculationEngine(self.db)
        breakdown = engine.generate_tax_breakdown(
            gross_income=Decimal(str(gross_income)),
            tax_year=year,
            user_type=user_type,
            user_id=self.user_id,
            **kwargs,
        )
        return breakdown

    # -- VAT calculation ------------------------------------------------

    def calculate_vat(
        self, revenue: float, year: int = 2026, vat_rate: float = 20.0
    ) -> Dict[str, Any]:
        """Calculate VAT for given revenue."""
        from app.services.vat_calculator import VATCalculator

        calc = VATCalculator()
        result = calc.calculate_vat(
            revenue=Decimal(str(revenue)),
            vat_rate=Decimal(str(vat_rate)),
            tax_year=year,
        )
        return {
            "revenue": float(revenue),
            "vat_rate": float(vat_rate),
            "vat_amount": float(result.vat_amount),
            "total_with_vat": float(result.total_with_vat),
            "is_small_business": result.is_small_business,
            "small_business_threshold": float(result.small_business_threshold),
            "year": year,
        }

    # -- SVS calculation ------------------------------------------------

    def calculate_svs(
        self, annual_income: float, year: int = 2026
    ) -> Dict[str, Any]:
        """Calculate SVS social insurance contributions."""
        from app.services.svs_calculator import SVSCalculator

        calc = SVSCalculator()
        result = calc.calculate_svs(
            annual_income=Decimal(str(annual_income)),
            tax_year=year,
        )
        return {
            "annual_income": float(annual_income),
            "health_insurance": float(result.health_insurance),
            "pension_insurance": float(result.pension_insurance),
            "accident_insurance": float(result.accident_insurance),
            "self_employed_provision": float(result.self_employed_provision),
            "total_contributions": float(result.total_contributions),
            "year": year,
        }

    # -- KESt calculation -----------------------------------------------

    def calculate_kest(self, items: List[Dict]) -> Dict[str, Any]:
        """Calculate capital gains tax (KESt)."""
        from app.services.kest_calculator import calculate_kest, KEStItem

        kest_items = []
        for item in items:
            kest_items.append(KEStItem(
                income_type=item.get("income_type", "dividends"),
                gross_amount=Decimal(str(item.get("amount", 0))),
                already_withheld=Decimal(str(item.get("withheld", 0))),
            ))
        result = calculate_kest(kest_items)
        return {
            "total_gross": float(result.total_gross),
            "total_tax": float(result.total_tax),
            "total_already_withheld": float(result.total_already_withheld),
            "remaining_tax_due": float(result.remaining_tax_due),
            "line_items": [
                {
                    "type": li.income_type,
                    "gross": float(li.gross_amount),
                    "rate": float(li.tax_rate),
                    "tax": float(li.tax_amount),
                }
                for li in result.line_items
            ],
        }

    # -- Deductibility check --------------------------------------------

    def check_deductibility(
        self, description: str, amount: float, category: Optional[str] = None
    ) -> Dict[str, Any]:
        """Check if an expense is tax-deductible."""
        from app.services.deductibility_checker import DeductibilityChecker

        checker = DeductibilityChecker()
        # Build a minimal transaction-like object
        class _FakeTx:
            pass
        tx = _FakeTx()
        tx.description = description
        tx.amount = Decimal(str(amount))
        tx.expense_category = category
        tx.type = "expense"

        result = checker.check(tx)
        return {
            "description": description,
            "amount": float(amount),
            "is_deductible": result.is_deductible,
            "deduction_type": result.deduction_type,
            "max_deductible": float(result.max_deductible) if result.max_deductible else None,
            "explanation": result.explanation,
        }

    # -- Transaction classification -------------------------------------

    def classify_transaction(
        self, description: str, amount: float, tx_type: str = "expense"
    ) -> Dict[str, Any]:
        """Classify a transaction with user context for LLM fallback."""
        from app.services.transaction_classifier import TransactionClassifier
        from app.models.user import User

        classifier = TransactionClassifier(db=self.db)

        class _FakeTx:
            pass

        tx = _FakeTx()
        tx.description = description
        tx.amount = Decimal(str(amount))
        tx.type = tx_type
        tx.id = 0
        tx.user_id = self.user_id

        # Load user for context-aware classification
        user = self.db.query(User).filter(User.id == self.user_id).first()

        result = classifier.classify_transaction(tx, user)
        return {
            "description": description,
            "predicted_category": result.category,
            "confidence": float(result.confidence),
            "method": result.method,
        }

    # -- Financial summary ----------------------------------------------

    def get_financial_summary(self, year: int = 2026) -> Dict[str, Any]:
        """Get user's financial summary for a tax year."""
        from app.services.rag_service import RAGService
        from app.models.user import User

        user = self.db.query(User).filter(User.id == self.user_id).first()
        if not user:
            return {"error": "User not found"}

        rag = RAGService(self.db)
        summary_text = rag._build_financial_summary(user, year, "en")
        return {"year": year, "summary": summary_text}

    # -- What-if simulation ---------------------------------------------

    def run_what_if(
        self, base_income: float, scenario_income: float, year: int = 2026
    ) -> Dict[str, Any]:
        """Run a what-if tax comparison."""
        base = self.calculate_income_tax(base_income, year)
        scenario = self.calculate_income_tax(scenario_income, year)
        diff = (scenario.get("total_tax", 0) or 0) - (base.get("total_tax", 0) or 0)
        return {
            "base_income": base_income,
            "scenario_income": scenario_income,
            "base_tax": base.get("total_tax"),
            "scenario_tax": scenario.get("total_tax"),
            "tax_difference": diff,
            "year": year,
        }


# ---------------------------------------------------------------------------
# Response formatters — turn tool output into user-friendly text
# ---------------------------------------------------------------------------

_LANG = Dict[str, str]


def _format_income_tax(data: Dict, language: str) -> str:
    """Format income tax calculation result."""
    total = data.get("total_tax", 0)
    gross = data.get("gross_income", 0)
    net = data.get("net_income", gross - total if gross and total else 0)
    # effective_tax_rate is a decimal (e.g. 0.1246 = 12.46%)
    rate = data.get("effective_tax_rate", 0) * 100
    year = data.get("tax_year", 2026)

    templates: _LANG = {
        "de": (
            f"📊 Einkommensteuerberechnung {year}:\n"
            f"• Bruttoeinkommen: €{gross:,.2f}\n"
            f"• Einkommensteuer: €{total:,.2f}\n"
            f"• Effektiver Steuersatz: {rate:.1f}%\n"
            f"• Nettoeinkommen: €{net:,.2f}"
        ),
        "en": (
            f"📊 Income Tax Calculation {year}:\n"
            f"• Gross income: €{gross:,.2f}\n"
            f"• Income tax: €{total:,.2f}\n"
            f"• Effective rate: {rate:.1f}%\n"
            f"• Net income: €{net:,.2f}"
        ),
        "zh": (
            f"📊 {year}年所得税计算：\n"
            f"• 总收入：€{gross:,.2f}\n"
            f"• 所得税：€{total:,.2f}\n"
            f"• 有效税率：{rate:.1f}%\n"
            f"• 净收入：€{net:,.2f}"
        ),
        "fr": (
            f"📊 Calcul de l'impôt sur le revenu {year} :\n"
            f"• Revenu brut : €{gross:,.2f}\n"
            f"• Impôt sur le revenu : €{total:,.2f}\n"
            f"• Taux effectif : {rate:.1f}%\n"
            f"• Revenu net : €{net:,.2f}"
        ),
        "ru": (
            f"📊 Расчёт подоходного налога {year}:\n"
            f"• Валовой доход: €{gross:,.2f}\n"
            f"• Подоходный налог: €{total:,.2f}\n"
            f"• Эффективная ставка: {rate:.1f}%\n"
            f"• Чистый доход: €{net:,.2f}"
        ),
        "hu": (
            f"📊 Jövedelemadó-számítás {year}:\n"
            f"• Bruttó jövedelem: €{gross:,.2f}\n"
            f"• Jövedelemadó: €{total:,.2f}\n"
            f"• Effektív adókulcs: {rate:.1f}%\n"
            f"• Nettó jövedelem: €{net:,.2f}"
        ),
        "pl": (
            f"📊 Obliczenie podatku dochodowego {year}:\n"
            f"• Dochód brutto: €{gross:,.2f}\n"
            f"• Podatek dochodowy: €{total:,.2f}\n"
            f"• Efektywna stawka: {rate:.1f}%\n"
            f"• Dochód netto: €{net:,.2f}"
        ),
        "tr": (
            f"📊 Gelir Vergisi Hesaplaması {year}:\n"
            f"• Brüt gelir: €{gross:,.2f}\n"
            f"• Gelir vergisi: €{total:,.2f}\n"
            f"• Efektif oran: {rate:.1f}%\n"
            f"• Net gelir: €{net:,.2f}"
        ),
        "bs": (
            f"📊 Obračun poreza na dohodak {year}:\n"
            f"• Bruto prihod: €{gross:,.2f}\n"
            f"• Porez na dohodak: €{total:,.2f}\n"
            f"• Efektivna stopa: {rate:.1f}%\n"
            f"• Neto prihod: €{net:,.2f}"
        ),
    }
    return templates.get(language, templates["de"])


def _format_vat(data: Dict, language: str) -> str:
    """Format VAT calculation result."""
    templates: _LANG = {
        "de": (
            f"📊 USt-Berechnung:\n"
            f"• Umsatz: €{data['revenue']:,.2f}\n"
            f"• USt-Satz: {data['vat_rate']}%\n"
            f"• USt-Betrag: €{data['vat_amount']:,.2f}\n"
            f"• Gesamt (brutto): €{data['total_with_vat']:,.2f}\n"
            f"• Kleinunternehmerregelung: {'Ja ✅' if data['is_small_business'] else 'Nein ❌'}"
        ),
        "en": (
            f"📊 VAT Calculation:\n"
            f"• Revenue: €{data['revenue']:,.2f}\n"
            f"• VAT rate: {data['vat_rate']}%\n"
            f"• VAT amount: €{data['vat_amount']:,.2f}\n"
            f"• Total (gross): €{data['total_with_vat']:,.2f}\n"
            f"• Small business exemption: {'Yes ✅' if data['is_small_business'] else 'No ❌'}"
        ),
        "zh": (
            f"📊 增值税计算：\n"
            f"• 营业额：€{data['revenue']:,.2f}\n"
            f"• 增值税率：{data['vat_rate']}%\n"
            f"• 增值税额：€{data['vat_amount']:,.2f}\n"
            f"• 含税总额：€{data['total_with_vat']:,.2f}\n"
            f"• 小企业免税：{'是 ✅' if data['is_small_business'] else '否 ❌'}"
        ),
        "fr": (
            f"📊 Calcul de la TVA :\n"
            f"• Chiffre d'affaires : €{data['revenue']:,.2f}\n"
            f"• Taux de TVA : {data['vat_rate']}%\n"
            f"• Montant de TVA : €{data['vat_amount']:,.2f}\n"
            f"• Total (TTC) : €{data['total_with_vat']:,.2f}\n"
            f"• Exonération petite entreprise : {'Oui ✅' if data['is_small_business'] else 'Non ❌'}"
        ),
        "ru": (
            f"📊 Расчёт НДС:\n"
            f"• Выручка: €{data['revenue']:,.2f}\n"
            f"• Ставка НДС: {data['vat_rate']}%\n"
            f"• Сумма НДС: €{data['vat_amount']:,.2f}\n"
            f"• Итого (с НДС): €{data['total_with_vat']:,.2f}\n"
            f"• Освобождение малого бизнеса: {'Да ✅' if data['is_small_business'] else 'Нет ❌'}"
        ),
        "hu": (
            f"📊 ÁFA-számítás:\n"
            f"• Árbevétel: €{data['revenue']:,.2f}\n"
            f"• ÁFA-kulcs: {data['vat_rate']}%\n"
            f"• ÁFA összeg: €{data['vat_amount']:,.2f}\n"
            f"• Összesen (bruttó): €{data['total_with_vat']:,.2f}\n"
            f"• Kisvállalkozói mentesség: {'Igen ✅' if data['is_small_business'] else 'Nem ❌'}"
        ),
        "pl": (
            f"📊 Obliczenie VAT:\n"
            f"• Przychód: €{data['revenue']:,.2f}\n"
            f"• Stawka VAT: {data['vat_rate']}%\n"
            f"• Kwota VAT: €{data['vat_amount']:,.2f}\n"
            f"• Razem (brutto): €{data['total_with_vat']:,.2f}\n"
            f"• Zwolnienie dla małych firm: {'Tak ✅' if data['is_small_business'] else 'Nie ❌'}"
        ),
        "tr": (
            f"📊 KDV Hesaplaması:\n"
            f"• Gelir: €{data['revenue']:,.2f}\n"
            f"• KDV oranı: {data['vat_rate']}%\n"
            f"• KDV tutarı: €{data['vat_amount']:,.2f}\n"
            f"• Toplam (brüt): €{data['total_with_vat']:,.2f}\n"
            f"• Küçük işletme muafiyeti: {'Evet ✅' if data['is_small_business'] else 'Hayır ❌'}"
        ),
        "bs": (
            f"📊 Obračun PDV-a:\n"
            f"• Prihod: €{data['revenue']:,.2f}\n"
            f"• Stopa PDV-a: {data['vat_rate']}%\n"
            f"• Iznos PDV-a: €{data['vat_amount']:,.2f}\n"
            f"• Ukupno (bruto): €{data['total_with_vat']:,.2f}\n"
            f"• Oslobođenje za mala preduzeća: {'Da ✅' if data['is_small_business'] else 'Ne ❌'}"
        ),
    }
    return templates.get(language, templates["de"])


def _format_svs(data: Dict, language: str) -> str:
    """Format SVS calculation result."""
    templates: _LANG = {
        "de": (
            f"📊 SVS-Beiträge:\n"
            f"• Jahreseinkommen: €{data['annual_income']:,.2f}\n"
            f"• Krankenversicherung: €{data['health_insurance']:,.2f}\n"
            f"• Pensionsversicherung: €{data['pension_insurance']:,.2f}\n"
            f"• Unfallversicherung: €{data['accident_insurance']:,.2f}\n"
            f"• Selbständigenvorsorge: €{data['self_employed_provision']:,.2f}\n"
            f"• Gesamt: €{data['total_contributions']:,.2f}"
        ),
        "en": (
            f"📊 SVS Contributions:\n"
            f"• Annual income: €{data['annual_income']:,.2f}\n"
            f"• Health insurance: €{data['health_insurance']:,.2f}\n"
            f"• Pension insurance: €{data['pension_insurance']:,.2f}\n"
            f"• Accident insurance: €{data['accident_insurance']:,.2f}\n"
            f"• Self-employed provision: €{data['self_employed_provision']:,.2f}\n"
            f"• Total: €{data['total_contributions']:,.2f}"
        ),
        "zh": (
            f"📊 SVS社保缴费：\n"
            f"• 年收入：€{data['annual_income']:,.2f}\n"
            f"• 医疗保险：€{data['health_insurance']:,.2f}\n"
            f"• 养老保险：€{data['pension_insurance']:,.2f}\n"
            f"• 意外保险：€{data['accident_insurance']:,.2f}\n"
            f"• 自雇预备金：€{data['self_employed_provision']:,.2f}\n"
            f"• 合计：€{data['total_contributions']:,.2f}"
        ),
        "fr": (
            f"📊 Cotisations SVS :\n"
            f"• Revenu annuel : €{data['annual_income']:,.2f}\n"
            f"• Assurance maladie : €{data['health_insurance']:,.2f}\n"
            f"• Assurance retraite : €{data['pension_insurance']:,.2f}\n"
            f"• Assurance accident : €{data['accident_insurance']:,.2f}\n"
            f"• Prévoyance indépendant : €{data['self_employed_provision']:,.2f}\n"
            f"• Total : €{data['total_contributions']:,.2f}"
        ),
        "ru": (
            f"📊 Взносы SVS:\n"
            f"• Годовой доход: €{data['annual_income']:,.2f}\n"
            f"• Медицинское страхование: €{data['health_insurance']:,.2f}\n"
            f"• Пенсионное страхование: €{data['pension_insurance']:,.2f}\n"
            f"• Страхование от несчастных случаев: €{data['accident_insurance']:,.2f}\n"
            f"• Резерв самозанятого: €{data['self_employed_provision']:,.2f}\n"
            f"• Итого: €{data['total_contributions']:,.2f}"
        ),
        "hu": (
            f"📊 SVS-járulékok:\n"
            f"• Éves jövedelem: €{data['annual_income']:,.2f}\n"
            f"• Egészségbiztosítás: €{data['health_insurance']:,.2f}\n"
            f"• Nyugdíjbiztosítás: €{data['pension_insurance']:,.2f}\n"
            f"• Balesetbiztosítás: €{data['accident_insurance']:,.2f}\n"
            f"• Önfoglalkoztatói tartalék: €{data['self_employed_provision']:,.2f}\n"
            f"• Összesen: €{data['total_contributions']:,.2f}"
        ),
        "pl": (
            f"📊 Składki SVS:\n"
            f"• Roczny dochód: €{data['annual_income']:,.2f}\n"
            f"• Ubezpieczenie zdrowotne: €{data['health_insurance']:,.2f}\n"
            f"• Ubezpieczenie emerytalne: €{data['pension_insurance']:,.2f}\n"
            f"• Ubezpieczenie wypadkowe: €{data['accident_insurance']:,.2f}\n"
            f"• Rezerwa samozatrudnionego: €{data['self_employed_provision']:,.2f}\n"
            f"• Razem: €{data['total_contributions']:,.2f}"
        ),
        "tr": (
            f"📊 SVS Primleri:\n"
            f"• Yıllık gelir: €{data['annual_income']:,.2f}\n"
            f"• Sağlık sigortası: €{data['health_insurance']:,.2f}\n"
            f"• Emeklilik sigortası: €{data['pension_insurance']:,.2f}\n"
            f"• Kaza sigortası: €{data['accident_insurance']:,.2f}\n"
            f"• Serbest meslek karşılığı: €{data['self_employed_provision']:,.2f}\n"
            f"• Toplam: €{data['total_contributions']:,.2f}"
        ),
        "bs": (
            f"📊 SVS doprinosi:\n"
            f"• Godišnji prihod: €{data['annual_income']:,.2f}\n"
            f"• Zdravstveno osiguranje: €{data['health_insurance']:,.2f}\n"
            f"• Penzijsko osiguranje: €{data['pension_insurance']:,.2f}\n"
            f"• Osiguranje od nezgoda: €{data['accident_insurance']:,.2f}\n"
            f"• Rezerva za samozaposlene: €{data['self_employed_provision']:,.2f}\n"
            f"• Ukupno: €{data['total_contributions']:,.2f}"
        ),
    }
    return templates.get(language, templates["de"])


def _format_kest(data: Dict, language: str) -> str:
    """Format KESt calculation result."""
    templates: _LANG = {
        "de": (
            f"📊 KESt-Berechnung:\n"
            f"• Kapitalerträge brutto: €{data['total_gross']:,.2f}\n"
            f"• KESt gesamt: €{data['total_tax']:,.2f}\n"
            f"• Bereits einbehalten: €{data['total_already_withheld']:,.2f}\n"
            f"• Noch zu zahlen: €{data['remaining_tax_due']:,.2f}"
        ),
        "en": (
            f"📊 KESt Calculation:\n"
            f"• Gross capital income: €{data['total_gross']:,.2f}\n"
            f"• Total KESt: €{data['total_tax']:,.2f}\n"
            f"• Already withheld: €{data['total_already_withheld']:,.2f}\n"
            f"• Remaining due: €{data['remaining_tax_due']:,.2f}"
        ),
        "zh": (
            f"📊 资本利得税(KESt)计算：\n"
            f"• 资本收入总额：€{data['total_gross']:,.2f}\n"
            f"• KESt总额：€{data['total_tax']:,.2f}\n"
            f"• 已预扣：€{data['total_already_withheld']:,.2f}\n"
            f"• 待缴纳：€{data['remaining_tax_due']:,.2f}"
        ),
        "fr": (
            f"📊 Calcul KESt :\n"
            f"• Revenus du capital bruts : €{data['total_gross']:,.2f}\n"
            f"• KESt total : €{data['total_tax']:,.2f}\n"
            f"• Déjà retenu : €{data['total_already_withheld']:,.2f}\n"
            f"• Reste à payer : €{data['remaining_tax_due']:,.2f}"
        ),
        "ru": (
            f"📊 Расчёт KESt:\n"
            f"• Валовой доход от капитала: €{data['total_gross']:,.2f}\n"
            f"• Итого KESt: €{data['total_tax']:,.2f}\n"
            f"• Уже удержано: €{data['total_already_withheld']:,.2f}\n"
            f"• К оплате: €{data['remaining_tax_due']:,.2f}"
        ),
        "hu": (
            f"📊 KESt-számítás:\n"
            f"• Bruttó tőkejövedelem: €{data['total_gross']:,.2f}\n"
            f"• KESt összesen: €{data['total_tax']:,.2f}\n"
            f"• Már levonva: €{data['total_already_withheld']:,.2f}\n"
            f"• Fizetendő: €{data['remaining_tax_due']:,.2f}"
        ),
        "pl": (
            f"📊 Obliczenie KESt:\n"
            f"• Dochód kapitałowy brutto: €{data['total_gross']:,.2f}\n"
            f"• KESt łącznie: €{data['total_tax']:,.2f}\n"
            f"• Już potrącono: €{data['total_already_withheld']:,.2f}\n"
            f"• Do zapłaty: €{data['remaining_tax_due']:,.2f}"
        ),
        "tr": (
            f"📊 KESt Hesaplaması:\n"
            f"• Brüt sermaye geliri: €{data['total_gross']:,.2f}\n"
            f"• Toplam KESt: €{data['total_tax']:,.2f}\n"
            f"• Zaten kesilen: €{data['total_already_withheld']:,.2f}\n"
            f"• Kalan borç: €{data['remaining_tax_due']:,.2f}"
        ),
        "bs": (
            f"📊 Obračun KESt:\n"
            f"• Bruto prihod od kapitala: €{data['total_gross']:,.2f}\n"
            f"• Ukupno KESt: €{data['total_tax']:,.2f}\n"
            f"• Već zadržano: €{data['total_already_withheld']:,.2f}\n"
            f"• Preostalo za uplatu: €{data['remaining_tax_due']:,.2f}"
        ),
    }
    return templates.get(language, templates["de"])


def _format_deductibility(data: Dict, language: str) -> str:
    """Format deductibility check result."""
    is_ded = data.get("is_deductible", False)
    desc = data.get("description", "")
    expl = data.get("explanation", "")
    templates: _LANG = {
        "de": (
            f"{'✅ Absetzbar' if is_ded else '❌ Nicht absetzbar'}: {desc}\n"
            f"{expl}"
        ),
        "en": (
            f"{'✅ Deductible' if is_ded else '❌ Not deductible'}: {desc}\n"
            f"{expl}"
        ),
        "zh": (
            f"{'✅ 可抵扣' if is_ded else '❌ 不可抵扣'}：{desc}\n"
            f"{expl}"
        ),
        "fr": (
            f"{'✅ Déductible' if is_ded else '❌ Non déductible'} : {desc}\n"
            f"{expl}"
        ),
        "ru": (
            f"{'✅ Вычитается' if is_ded else '❌ Не вычитается'}: {desc}\n"
            f"{expl}"
        ),
        "hu": (
            f"{'✅ Levonható' if is_ded else '❌ Nem vonható le'}: {desc}\n"
            f"{expl}"
        ),
        "pl": (
            f"{'✅ Podlega odliczeniu' if is_ded else '❌ Nie podlega odliczeniu'}: {desc}\n"
            f"{expl}"
        ),
        "tr": (
            f"{'✅ Düşülebilir' if is_ded else '❌ Düşülemez'}: {desc}\n"
            f"{expl}"
        ),
        "bs": (
            f"{'✅ Odbitno' if is_ded else '❌ Nije odbitno'}: {desc}\n"
            f"{expl}"
        ),
    }
    return templates.get(language, templates["de"])


def _format_classification(data: Dict, language: str) -> str:
    """Format transaction classification result."""
    cat = data.get("predicted_category", "unknown")
    conf = data.get("confidence", 0)
    method = data.get("method", "unknown")
    templates: _LANG = {
        "de": (
            f"🏷️ Klassifizierung: {cat}\n"
            f"• Konfidenz: {conf:.0%}\n"
            f"• Methode: {method}"
        ),
        "en": (
            f"🏷️ Classification: {cat}\n"
            f"• Confidence: {conf:.0%}\n"
            f"• Method: {method}"
        ),
        "zh": (
            f"🏷️ 分类结果：{cat}\n"
            f"• 置信度：{conf:.0%}\n"
            f"• 方法：{method}"
        ),
        "fr": (
            f"🏷️ Classification : {cat}\n"
            f"• Confiance : {conf:.0%}\n"
            f"• Méthode : {method}"
        ),
        "ru": (
            f"🏷️ Классификация: {cat}\n"
            f"• Уверенность: {conf:.0%}\n"
            f"• Метод: {method}"
        ),
        "hu": (
            f"🏷️ Besorolás: {cat}\n"
            f"• Megbízhatóság: {conf:.0%}\n"
            f"• Módszer: {method}"
        ),
        "pl": (
            f"🏷️ Klasyfikacja: {cat}\n"
            f"• Pewność: {conf:.0%}\n"
            f"• Metoda: {method}"
        ),
        "tr": (
            f"🏷️ Sınıflandırma: {cat}\n"
            f"• Güven: {conf:.0%}\n"
            f"• Yöntem: {method}"
        ),
        "bs": (
            f"🏷️ Klasifikacija: {cat}\n"
            f"• Pouzdanost: {conf:.0%}\n"
            f"• Metoda: {method}"
        ),
    }
    return templates.get(language, templates["de"])


def _format_what_if(data: Dict, language: str) -> str:
    """Format what-if simulation result."""
    diff = data.get("tax_difference", 0)
    direction = "+" if diff > 0 else ""
    templates: _LANG = {
        "de": (
            f"🔮 Was-wäre-wenn Simulation:\n"
            f"• Aktuell (€{data['base_income']:,.0f}): Steuer €{data['base_tax']:,.2f}\n"
            f"• Szenario (€{data['scenario_income']:,.0f}): Steuer €{data['scenario_tax']:,.2f}\n"
            f"• Differenz: {direction}€{diff:,.2f}"
        ),
        "en": (
            f"🔮 What-if Simulation:\n"
            f"• Current (€{data['base_income']:,.0f}): Tax €{data['base_tax']:,.2f}\n"
            f"• Scenario (€{data['scenario_income']:,.0f}): Tax €{data['scenario_tax']:,.2f}\n"
            f"• Difference: {direction}€{diff:,.2f}"
        ),
        "zh": (
            f"🔮 假设模拟：\n"
            f"• 当前（€{data['base_income']:,.0f}）：税额 €{data['base_tax']:,.2f}\n"
            f"• 假设（€{data['scenario_income']:,.0f}）：税额 €{data['scenario_tax']:,.2f}\n"
            f"• 差额：{direction}€{diff:,.2f}"
        ),
        "fr": (
            f"🔮 Simulation hypothétique :\n"
            f"• Actuel (€{data['base_income']:,.0f}) : Impôt €{data['base_tax']:,.2f}\n"
            f"• Scénario (€{data['scenario_income']:,.0f}) : Impôt €{data['scenario_tax']:,.2f}\n"
            f"• Différence : {direction}€{diff:,.2f}"
        ),
        "ru": (
            f"🔮 Моделирование «что если»:\n"
            f"• Текущий (€{data['base_income']:,.0f}): Налог €{data['base_tax']:,.2f}\n"
            f"• Сценарий (€{data['scenario_income']:,.0f}): Налог €{data['scenario_tax']:,.2f}\n"
            f"• Разница: {direction}€{diff:,.2f}"
        ),
        "hu": (
            f"🔮 Mi lenne, ha szimuláció:\n"
            f"• Jelenlegi (€{data['base_income']:,.0f}): Adó €{data['base_tax']:,.2f}\n"
            f"• Forgatókönyv (€{data['scenario_income']:,.0f}): Adó €{data['scenario_tax']:,.2f}\n"
            f"• Különbség: {direction}€{diff:,.2f}"
        ),
        "pl": (
            f'🔮 Symulacja „co jeśli":\n'
            f"• Obecny (€{data['base_income']:,.0f}): Podatek €{data['base_tax']:,.2f}\n"
            f"• Scenariusz (€{data['scenario_income']:,.0f}): Podatek €{data['scenario_tax']:,.2f}\n"
            f"• Różnica: {direction}€{diff:,.2f}"
        ),
        "tr": (
            f"🔮 Ya olsaydı simülasyonu:\n"
            f"• Mevcut (€{data['base_income']:,.0f}): Vergi €{data['base_tax']:,.2f}\n"
            f"• Senaryo (€{data['scenario_income']:,.0f}): Vergi €{data['scenario_tax']:,.2f}\n"
            f"• Fark: {direction}€{diff:,.2f}"
        ),
        "bs": (
            f'🔮 Simulacija „šta ako":\n'
            f"• Trenutno (€{data['base_income']:,.0f}): Porez €{data['base_tax']:,.2f}\n"
            f"• Scenarij (€{data['scenario_income']:,.0f}): Porez €{data['scenario_tax']:,.2f}\n"
            f"• Razlika: {direction}€{diff:,.2f}"
        ),
    }
    return templates.get(language, templates["de"])


# Map intents to formatters
_FORMATTERS = {
    UserIntent.CALCULATE_TAX: _format_income_tax,
    UserIntent.CALCULATE_VAT: _format_vat,
    UserIntent.CALCULATE_SVS: _format_svs,
    UserIntent.CALCULATE_KEST: _format_kest,
    UserIntent.CHECK_DEDUCTIBILITY: _format_deductibility,
    UserIntent.CLASSIFY_TRANSACTION: _format_classification,
    UserIntent.WHAT_IF: _format_what_if,
}


# ---------------------------------------------------------------------------
# Follow-up suggestion generator
# ---------------------------------------------------------------------------

_SUGGESTIONS: Dict[UserIntent, Dict[str, List[str]]] = {
    UserIntent.CALCULATE_TAX: {
        "de": ["SVS-Beiträge berechnen", "Absetzbeträge prüfen", "Was-wäre-wenn Simulation"],
        "en": ["Calculate SVS contributions", "Check deductions", "What-if simulation"],
        "zh": ["计算SVS社保", "检查抵扣项", "假设模拟"],
        "fr": ["Calculer les cotisations SVS", "Vérifier les déductions", "Simulation hypothétique"],
        "ru": ["Рассчитать взносы SVS", "Проверить вычеты", "Моделирование «что если»"],
        "hu": ["SVS-járulékok kiszámítása", "Levonások ellenőrzése", "Mi lenne, ha szimuláció"],
        "pl": ["Oblicz składki SVS", "Sprawdź odliczenia", 'Symulacja „co jeśli"'],
        "tr": ["SVS primlerini hesapla", "Kesintileri kontrol et", "Ya olsaydı simülasyonu"],
        "bs": ["Izračunaj SVS doprinose", "Provjeri odbitke", 'Simulacija „šta ako"'],
    },
    UserIntent.CALCULATE_VAT: {
        "de": ["Einkommensteuer berechnen", "Kleinunternehmerregelung erklärt"],
        "en": ["Calculate income tax", "Small business exemption explained"],
        "zh": ["计算所得税", "小企业免税规则说明"],
        "fr": ["Calculer l'impôt sur le revenu", "Exonération petite entreprise expliquée"],
        "ru": ["Рассчитать подоходный налог", "Освобождение малого бизнеса"],
        "hu": ["Jövedelemadó kiszámítása", "Kisvállalkozói mentesség magyarázata"],
        "pl": ["Oblicz podatek dochodowy", "Wyjaśnienie zwolnienia dla małych firm"],
        "tr": ["Gelir vergisini hesapla", "Küçük işletme muafiyeti açıklaması"],
        "bs": ["Izračunaj porez na dohodak", "Objašnjenje oslobođenja za mala preduzeća"],
    },
    UserIntent.CALCULATE_SVS: {
        "de": ["Einkommensteuer berechnen", "Gewinnfreibetrag prüfen"],
        "en": ["Calculate income tax", "Check profit allowance"],
        "zh": ["计算所得税", "检查利润免税额"],
        "fr": ["Calculer l'impôt sur le revenu", "Vérifier l'abattement sur les bénéfices"],
        "ru": ["Рассчитать подоходный налог", "Проверить льготу на прибыль"],
        "hu": ["Jövedelemadó kiszámítása", "Nyereségkedvezmény ellenőrzése"],
        "pl": ["Oblicz podatek dochodowy", "Sprawdź ulgę od zysku"],
        "tr": ["Gelir vergisini hesapla", "Kâr muafiyetini kontrol et"],
        "bs": ["Izračunaj porez na dohodak", "Provjeri olakšicu za dobit"],
    },
    UserIntent.CHECK_DEDUCTIBILITY: {
        "de": ["Alle Absetzbeträge anzeigen", "Steuer berechnen"],
        "en": ["Show all deductions", "Calculate tax"],
        "zh": ["显示所有抵扣项", "计算税额"],
        "fr": ["Afficher toutes les déductions", "Calculer l'impôt"],
        "ru": ["Показать все вычеты", "Рассчитать налог"],
        "hu": ["Összes levonás megjelenítése", "Adó kiszámítása"],
        "pl": ["Pokaż wszystkie odliczenia", "Oblicz podatek"],
        "tr": ["Tüm kesintileri göster", "Vergiyi hesapla"],
        "bs": ["Prikaži sve odbitke", "Izračunaj porez"],
    },
    UserIntent.SUMMARIZE_STATUS: {
        "de": ["Steuer berechnen", "Optimierungsvorschläge", "Dokumente hochladen"],
        "en": ["Calculate tax", "Optimization suggestions", "Upload documents"],
        "zh": ["计算税额", "优化建议", "上传文档"],
        "fr": ["Calculer l'impôt", "Suggestions d'optimisation", "Télécharger des documents"],
        "ru": ["Рассчитать налог", "Предложения по оптимизации", "Загрузить документы"],
        "hu": ["Adó kiszámítása", "Optimalizálási javaslatok", "Dokumentumok feltöltése"],
        "pl": ["Oblicz podatek", "Propozycje optymalizacji", "Prześlij dokumenty"],
        "tr": ["Vergiyi hesapla", "Optimizasyon önerileri", "Belge yükle"],
        "bs": ["Izračunaj porez", "Prijedlozi za optimizaciju", "Učitaj dokumente"],
    },
    UserIntent.EXPLAIN_DOCUMENT: {
        "de": ["Was bedeuten die KZ-Felder?", "Ist dieses Dokument korrekt?", "Steuer berechnen"],
        "en": ["What do the KZ fields mean?", "Is this document correct?", "Calculate tax"],
        "zh": ["KZ字段是什么意思？", "这个文档正确吗？", "计算税额"],
        "fr": ["Que signifient les champs KZ ?", "Ce document est-il correct ?", "Calculer l'impôt"],
        "ru": ["Что означают поля KZ?", "Этот документ правильный?", "Рассчитать налог"],
        "hu": ["Mit jelentenek a KZ mezők?", "Helyes ez a dokumentum?", "Adó kiszámítása"],
        "pl": ["Co oznaczają pola KZ?", "Czy ten dokument jest poprawny?", "Oblicz podatek"],
        "tr": ["KZ alanları ne anlama geliyor?", "Bu belge doğru mu?", "Vergiyi hesapla"],
        "bs": ["Šta znače KZ polja?", "Je li ovaj dokument ispravan?", "Izračunaj porez"],
    },
    UserIntent.SYSTEM_HELP: {
        "de": ["Wie lade ich Dokumente hoch?", "Wie berechne ich meine Steuer?", "Wie verwalte ich Immobilien?"],
        "en": ["How do I upload documents?", "How do I calculate my tax?", "How do I manage properties?"],
        "zh": ["怎么上传文档？", "怎么计算税额？", "怎么管理房产？"],
        "fr": ["Comment télécharger des documents ?", "Comment calculer mon impôt ?", "Comment gérer mes biens immobiliers ?"],
        "ru": ["Как загрузить документы?", "Как рассчитать налог?", "Как управлять недвижимостью?"],
        "hu": ["Hogyan tölthetek fel dokumentumokat?", "Hogyan számíthatom ki az adómat?", "Hogyan kezelhetem az ingatlanokat?"],
        "pl": ["Jak przesłać dokumenty?", "Jak obliczyć mój podatek?", "Jak zarządzać nieruchomościami?"],
        "tr": ["Belgeleri nasıl yüklerim?", "Vergimi nasıl hesaplarım?", "Mülkleri nasıl yönetirim?"],
        "bs": ["Kako da učitam dokumente?", "Kako da izračunam porez?", "Kako da upravljam nekretninama?"],
    },
}


def _get_suggestions(intent: UserIntent, language: str) -> List[str]:
    """Get follow-up suggestions for an intent."""
    intent_suggestions = _SUGGESTIONS.get(intent, {})
    return intent_suggestions.get(language, intent_suggestions.get("de", []))


# ---------------------------------------------------------------------------
# Disclaimers
# ---------------------------------------------------------------------------

DISCLAIMERS = {
    "de": (
        "\n\n⚠️ **Haftungsausschluss**: Diese Antwort dient nur zu Informationszwecken "
        "und stellt keine Steuerberatung dar. Bitte verwenden Sie FinanzOnline für die "
        "endgültige Steuererklärung."
    ),
    "en": (
        "\n\n⚠️ **Disclaimer**: This response is for informational purposes only and "
        "does not constitute tax advice. Please use FinanzOnline for final tax filing."
    ),
    "zh": (
        "\n\n⚠️ **免责声明**：本回答仅供参考，不构成税务咨询。"
        "请以FinanzOnline最终结果为准。"
    ),
    "fr": (
        "\n\n⚠️ **Avertissement** : Cette réponse est fournie à titre informatif uniquement et "
        "ne constitue pas un conseil fiscal. Veuillez utiliser FinanzOnline pour la déclaration fiscale définitive."
    ),
    "ru": (
        "\n\n⚠️ **Отказ от ответственности**: Этот ответ предназначен только для информационных целей и "
        "не является налоговой консультацией. Для окончательной подачи налоговой декларации используйте FinanzOnline."
    ),
    "hu": (
        "\n\n⚠️ **Felelősségkizárás**: Ez a válasz kizárólag tájékoztató jellegű, és "
        "nem minősül adótanácsadásnak. A végleges adóbevalláshoz kérjük, használja a FinanzOnline-t."
    ),
    "pl": (
        "\n\n⚠️ **Zastrzeżenie**: Ta odpowiedź ma charakter wyłącznie informacyjny i "
        "nie stanowi porady podatkowej. Do ostatecznego rozliczenia podatkowego proszę użyć FinanzOnline."
    ),
    "tr": (
        "\n\n⚠️ **Sorumluluk Reddi**: Bu yanıt yalnızca bilgilendirme amaçlıdır ve "
        "vergi danışmanlığı niteliği taşımaz. Nihai vergi beyannamesi için lütfen FinanzOnline'ı kullanın."
    ),
    "bs": (
        "\n\n⚠️ **Odricanje odgovornosti**: Ovaj odgovor služi samo u informativne svrhe i "
        "ne predstavlja porezno savjetovanje. Za konačnu poreznu prijavu koristite FinanzOnline."
    ),
}


# ---------------------------------------------------------------------------
# System Help — fallback overview (detailed help handled by AI triage/Groq)
# ---------------------------------------------------------------------------

_SYSTEM_OVERVIEW: Dict[str, str] = {
    "zh": (
        "👋 **欢迎使用 Taxja！**\n\n"
        "这是一个奥地利税务管理平台，主要功能：\n\n"
        "📄 **文档** — 上传发票、收据、合同，AI 自动识别和分类\n"
        "💰 **交易** — 管理收入和支出，AI 自动分类税务类别\n"
        "🏠 **房产** — 管理不动产和其他资产，自动计算折旧\n"
        "🧮 **税务工具** — 所得税、增值税、社保计算和模拟\n"
        "📊 **报告** — 自动生成税务报告\n"
        "🤖 **AI 助手** — 就是我！可以回答税务问题和操作指导\n\n"
        "有什么具体想了解的吗？"
    ),
    "de": (
        "👋 **Willkommen bei Taxja!**\n\n"
        "Eine Steuerverwaltungsplattform für Österreich:\n\n"
        "📄 **Dokumente** — Rechnungen, Belege, Verträge hochladen (KI-Erkennung)\n"
        "💰 **Transaktionen** — Einnahmen/Ausgaben verwalten (KI-Klassifizierung)\n"
        "🏠 **Immobilien** — Immobilien & Anlagen verwalten (automatische AfA)\n"
        "🧮 **Steuer-Tools** — ESt, USt, SVS berechnen & simulieren\n"
        "📊 **Berichte** — Automatische Steuerberichte\n"
        "🤖 **KI-Assistent** — Das bin ich! Steuerfragen & Bedienungshilfe\n\n"
        "Was möchten Sie wissen?"
    ),
    "en": (
        "👋 **Welcome to Taxja!**\n\n"
        "An Austrian tax management platform:\n\n"
        "📄 **Documents** — Upload invoices, receipts, contracts (AI recognition)\n"
        "💰 **Transactions** — Manage income/expenses (AI classification)\n"
        "🏠 **Properties** — Manage real estate & assets (auto depreciation)\n"
        "🧮 **Tax Tools** — Income tax, VAT, SVS calculations & simulations\n"
        "📊 **Reports** — Auto-generated tax reports\n"
        "🤖 **AI Assistant** — That's me! Tax questions & usage guidance\n\n"
        "What would you like to know?"
    ),
    "fr": (
        "👋 **Bienvenue sur Taxja !**\n\n"
        "Une plateforme de gestion fiscale autrichienne :\n\n"
        "📄 **Documents** — Téléchargez factures, reçus, contrats (reconnaissance IA)\n"
        "💰 **Transactions** — Gérez revenus/dépenses (classification IA)\n"
        "🏠 **Biens immobiliers** — Gérez immeubles et actifs (amortissement automatique)\n"
        "🧮 **Outils fiscaux** — Calculs et simulations : impôt, TVA, SVS\n"
        "📊 **Rapports** — Rapports fiscaux générés automatiquement\n"
        "🤖 **Assistant IA** — C'est moi ! Questions fiscales et aide à l'utilisation\n\n"
        "Que souhaitez-vous savoir ?"
    ),
    "ru": (
        "👋 **Добро пожаловать в Taxja!**\n\n"
        "Австрийская платформа управления налогами:\n\n"
        "📄 **Документы** — Загружайте счета, квитанции, договоры (распознавание ИИ)\n"
        "💰 **Транзакции** — Управляйте доходами/расходами (классификация ИИ)\n"
        "🏠 **Недвижимость** — Управляйте недвижимостью и активами (автоамортизация)\n"
        "🧮 **Налоговые инструменты** — Расчёты и моделирование: налог, НДС, SVS\n"
        "📊 **Отчёты** — Автоматически сформированные налоговые отчёты\n"
        "🤖 **ИИ-ассистент** — Это я! Налоговые вопросы и помощь по использованию\n\n"
        "Что вы хотели бы узнать?"
    ),
    "hu": (
        "👋 **Üdvözöljük a Taxja-ban!**\n\n"
        "Osztrák adókezelő platform:\n\n"
        "📄 **Dokumentumok** — Számlák, nyugták, szerződések feltöltése (AI felismerés)\n"
        "💰 **Tranzakciók** — Bevételek/kiadások kezelése (AI besorolás)\n"
        "🏠 **Ingatlanok** — Ingatlanok és eszközök kezelése (automatikus értékcsökkenés)\n"
        "🧮 **Adóeszközök** — Jövedelemadó, ÁFA, SVS számítások és szimulációk\n"
        "📊 **Jelentések** — Automatikusan generált adójelentések\n"
        "🤖 **AI asszisztens** — Ez én vagyok! Adókérdések és használati útmutató\n\n"
        "Mit szeretne tudni?"
    ),
    "pl": (
        "👋 **Witamy w Taxja!**\n\n"
        "Austriacka platforma zarządzania podatkami:\n\n"
        "📄 **Dokumenty** — Przesyłaj faktury, paragony, umowy (rozpoznawanie AI)\n"
        "💰 **Transakcje** — Zarządzaj przychodami/wydatkami (klasyfikacja AI)\n"
        "🏠 **Nieruchomości** — Zarządzaj nieruchomościami i aktywami (automatyczna amortyzacja)\n"
        "🧮 **Narzędzia podatkowe** — Obliczenia i symulacje: podatek, VAT, SVS\n"
        "📊 **Raporty** — Automatycznie generowane raporty podatkowe\n"
        "🤖 **Asystent AI** — To ja! Pytania podatkowe i pomoc w obsłudze\n\n"
        "Co chciałbyś wiedzieć?"
    ),
    "tr": (
        "👋 **Taxja'ya Hoş Geldiniz!**\n\n"
        "Avusturya vergi yönetim platformu:\n\n"
        "📄 **Belgeler** — Fatura, makbuz, sözleşme yükleyin (AI tanıma)\n"
        "💰 **İşlemler** — Gelir/giderleri yönetin (AI sınıflandırma)\n"
        "🏠 **Mülkler** — Gayrimenkul ve varlıkları yönetin (otomatik amortisman)\n"
        "🧮 **Vergi Araçları** — Gelir vergisi, KDV, SVS hesaplamaları ve simülasyonlar\n"
        "📊 **Raporlar** — Otomatik oluşturulan vergi raporları\n"
        "🤖 **AI Asistan** — Benim! Vergi soruları ve kullanım rehberliği\n\n"
        "Ne öğrenmek istersiniz?"
    ),
    "bs": (
        "👋 **Dobrodošli u Taxja!**\n\n"
        "Austrijska platforma za upravljanje porezima:\n\n"
        "📄 **Dokumenti** — Učitajte fakture, račune, ugovore (AI prepoznavanje)\n"
        "💰 **Transakcije** — Upravljajte prihodima/rashodima (AI klasifikacija)\n"
        "🏠 **Nekretnine** — Upravljajte nekretninama i imovinom (automatska amortizacija)\n"
        "🧮 **Porezni alati** — Porez na dohodak, PDV, SVS izračuni i simulacije\n"
        "📊 **Izvještaji** — Automatski generirani porezni izvještaji\n"
        "🤖 **AI asistent** — To sam ja! Porezna pitanja i upute za korištenje\n\n"
        "Šta biste željeli znati?"
    ),
}



# ---------------------------------------------------------------------------
# Main orchestrator class
# ---------------------------------------------------------------------------

class AIOrchestrator:
    """
    Central AI dispatch layer.

    Flow:
    1. detect_intent(message) → UserIntent + params
    2. If intent maps to a tool → execute tool → format result
    3. If intent is Q&A / unknown → delegate to RAG / LLM
    4. Append disclaimer + follow-up suggestions
    """

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self.tools = ToolRegistry(db, user_id)

    def handle_message(
        self,
        message: str,
        language: str = "de",
        conversation_history: Optional[List[Dict[str, str]]] = None,
        tax_year: Optional[int] = None,
    ) -> OrchestratorResponse:
        """
        Main entry point — single Groq call handles everything.

        Flow:
        1. AI triage (one Groq call) → classifies + answers system help
           OR returns tax intent with params.
        2. If tax intent returned → dispatch directly (no second LLM call needed).
        3. Fallback to regex detect_intent if triage fails.
        """
        if tax_year is None:
            tax_year = datetime.now().year

        # ① Single Groq call: triage + classify + answer system help
        triage_available = True
        try:
            from app.services.local_ai_triage import get_ai_triage
            triage = get_ai_triage()
            result = triage.process(message, language, conversation_history)

            if result["type"] == "general_chat":
                # Casual/off-topic: return as-is, no disclaimer, no tax framing
                return OrchestratorResponse(
                    text=result["answer"],
                    intent=UserIntent.UNKNOWN,
                    suggestions=[],
                )

            if result["type"] == "system_help":
                return OrchestratorResponse(
                    text=result["answer"],
                    intent=UserIntent.SYSTEM_HELP,
                    suggestions=_get_suggestions(UserIntent.SYSTEM_HELP, language),
                )

            if result["type"] == "tax":
                # Groq already classified the intent — map to UserIntent
                intent_name = result.get("intent", "tax_qa")
                from app.services.local_ai_triage import get_intent_map
                intent = get_intent_map().get(intent_name, UserIntent.TAX_QA)
                params = result.get("params", {})
                # Normalize param keys — LLM may return "income" instead of "amount"
                if "amount" not in params:
                    for alias in ("income", "einkommen", "收入", "revenue", "umsatz"):
                        if alias in params:
                            params["amount"] = params.pop(alias)
                            break
                intent_result = IntentResult(
                    intent=intent, confidence=0.90, params=params
                )
                logger.info(
                    "AI triage intent: %s (params=%s)", intent.value, params
                )
                try:
                    return self._dispatch(
                        intent_result, message, language,
                        conversation_history or [], tax_year,
                    )
                except Exception as exc:
                    logger.exception("Dispatch failed after triage: %s", exc)
                    return self._handle_rag(
                        message, language, conversation_history or [], tax_year
                    )

            # Triage returned "fallback" — LLM worked but couldn't classify.
            # Go directly to RAG; do NOT fall through to regex (regex has
            # higher false-positive rate than an LLM that responded).
            logger.info("Triage returned fallback, routing directly to RAG")
            return self._handle_rag(
                message, language, conversation_history or [], tax_year
            )

        except Exception as e:
            # LLM completely unavailable — fall through to regex as last resort
            triage_available = False
            logger.debug("AI triage unavailable: %s", e)

        # ② Last resort: regex intent detection (only when LLM is completely down)
        if not triage_available:
            intent_result = detect_intent(message)
            logger.info(
                "Intent detected (regex fallback): %s (confidence=%.2f, params=%s)",
                intent_result.intent.value,
                intent_result.confidence,
                intent_result.params,
            )
            try:
                return self._dispatch(
                    intent_result, message, language, conversation_history or [], tax_year
                )
            except Exception as exc:
                logger.exception("Orchestrator dispatch failed: %s", exc)

        return self._handle_rag(message, language, conversation_history or [], tax_year)

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def _dispatch(
        self,
        intent: IntentResult,
        message: str,
        language: str,
        history: List[Dict[str, str]],
        year: int,
    ) -> OrchestratorResponse:
        """Route to the correct handler based on intent."""

        handlers = {
            UserIntent.CALCULATE_TAX: self._handle_calculate_tax,
            UserIntent.CALCULATE_VAT: self._handle_calculate_vat,
            UserIntent.CALCULATE_SVS: self._handle_calculate_svs,
            UserIntent.CALCULATE_KEST: self._handle_calculate_kest,
            UserIntent.CALCULATE_IMMOEST: self._handle_calculate_immoest,
            UserIntent.CHECK_DEDUCTIBILITY: self._handle_check_deductibility,
            UserIntent.CLASSIFY_TRANSACTION: self._handle_classify_transaction,
            UserIntent.OPTIMIZE_TAX: self._handle_optimize_tax,
            UserIntent.WHAT_IF: self._handle_what_if,
            UserIntent.SUMMARIZE_STATUS: self._handle_summarize,
            UserIntent.EXPLAIN_DOCUMENT: self._handle_explain_document,
            UserIntent.SYSTEM_HELP: self._handle_system_help,
        }

        handler = handlers.get(intent.intent)
        if handler:
            return handler(intent, message, language, history, year)

        # TAX_QA or UNKNOWN → RAG
        return self._handle_rag(message, language, history, year)

    # ------------------------------------------------------------------
    # Tool handlers
    # ------------------------------------------------------------------

    def _handle_calculate_tax(
        self, intent: IntentResult, message: str, lang: str, history: list, year: int
    ) -> OrchestratorResponse:
        amount = intent.params.get("amount")
        yr = intent.params.get("year", year)
        if not amount:
            # Re-try extraction from raw message
            fallback = _extract_numeric_params(message)
            amount = fallback.get("amount")
            yr = fallback.get("year", yr)
        if not amount:
            # No amount found — ask LLM to extract or ask user
            return self._ask_for_params(
                lang,
                "Please provide your gross income, e.g. 'Calculate tax for €50,000'.",
                UserIntent.CALCULATE_TAX,
            )
        data = self.tools.calculate_income_tax(amount, yr)
        text = _format_income_tax(data, lang)
        return self._build_response(text, UserIntent.CALCULATE_TAX, data, lang)

    def _handle_calculate_vat(
        self, intent: IntentResult, message: str, lang: str, history: list, year: int
    ) -> OrchestratorResponse:
        amount = intent.params.get("amount")
        yr = intent.params.get("year", year)
        if not amount:
            fallback = _extract_numeric_params(message)
            amount = fallback.get("amount")
            yr = fallback.get("year", yr)
        if not amount:
            return self._ask_for_params(
                lang,
                "Please provide your revenue, e.g. 'Calculate VAT for €40,000'.",
                UserIntent.CALCULATE_VAT,
            )
        data = self.tools.calculate_vat(amount, yr)
        text = _format_vat(data, lang)
        return self._build_response(text, UserIntent.CALCULATE_VAT, data, lang)

    def _handle_calculate_svs(
        self, intent: IntentResult, message: str, lang: str, history: list, year: int
    ) -> OrchestratorResponse:
        amount = intent.params.get("amount")
        yr = intent.params.get("year", year)
        if not amount:
            fallback = _extract_numeric_params(message)
            amount = fallback.get("amount")
            yr = fallback.get("year", yr)
        if not amount:
            return self._ask_for_params(
                lang,
                "Please provide your annual income, e.g. 'Calculate SVS for €60,000'.",
                UserIntent.CALCULATE_SVS,
            )
        data = self.tools.calculate_svs(amount, yr)
        text = _format_svs(data, lang)
        return self._build_response(text, UserIntent.CALCULATE_SVS, data, lang)

    def _handle_calculate_kest(
        self, intent: IntentResult, message: str, lang: str, history: list, year: int
    ) -> OrchestratorResponse:
        amount = intent.params.get("amount")
        if not amount:
            fallback = _extract_numeric_params(message)
            amount = fallback.get("amount")
        if not amount:
            return self._ask_for_params(
                lang,
                "Please provide your capital income, e.g. 'Calculate KESt for €10,000 dividends'.",
                UserIntent.CALCULATE_KEST,
            )
        # Detect income type from message
        msg_lower = message.lower()
        if any(w in msg_lower for w in ["zins", "interest", "利息", "sparbuch", "savings"]):
            income_type = "savings_interest"
        elif any(w in msg_lower for w in ["anleihe", "bond", "债券"]):
            income_type = "bond_interest"
        else:
            income_type = "dividends"
        items = [{"income_type": income_type, "amount": amount, "withheld": 0}]
        data = self.tools.calculate_kest(items)
        text = _format_kest(data, lang)
        return self._build_response(text, UserIntent.CALCULATE_KEST, data, lang)

    def _handle_calculate_immoest(
        self, intent: IntentResult, message: str, lang: str, history: list, year: int
    ) -> OrchestratorResponse:
        # ImmoESt requires complex params — delegate to RAG with context
        return self._handle_rag(message, lang, history, year, extra_context=(
            "The user is asking about ImmoESt (Immobilienertragsteuer). "
            "Explain the 30% flat rate, exemptions (Hauptwohnsitzbefreiung, Herstellerbefreiung), "
            "and that old properties (acquired before 2002-04-01) use 4.2% of sale price."
        ))

    def _handle_check_deductibility(
        self, intent: IntentResult, message: str, lang: str, history: list, year: int
    ) -> OrchestratorResponse:
        # Extract the item being asked about from the message
        amount = intent.params.get("amount", 100)
        data = self.tools.check_deductibility(message, amount)
        text = _format_deductibility(data, lang)
        return self._build_response(text, UserIntent.CHECK_DEDUCTIBILITY, data, lang)

    def _handle_classify_transaction(
        self, intent: IntentResult, message: str, lang: str, history: list, year: int
    ) -> OrchestratorResponse:
        amount = intent.params.get("amount", 0)
        data = self.tools.classify_transaction(message, amount)
        text = _format_classification(data, lang)
        return self._build_response(text, UserIntent.CLASSIFY_TRANSACTION, data, lang)

    def _handle_optimize_tax(
        self, intent: IntentResult, message: str, lang: str, history: list, year: int
    ) -> OrchestratorResponse:
        # Get user's financial summary, then ask LLM for optimization advice
        summary = self.tools.get_financial_summary(year)
        extra = (
            f"User's financial summary:\n{summary.get('summary', 'No data')}\n\n"
            "Please provide specific, actionable tax optimization suggestions for this user. "
            "Consider: Gewinnfreibetrag, Pendlerpauschale, Home-Office, Familienbonus, "
            "Sonderausgaben, Kirchenbeitrag, Spenden, SVS optimization."
        )
        return self._handle_rag(message, lang, history, year, extra_context=extra)

    def _handle_what_if(
        self, intent: IntentResult, message: str, lang: str, history: list, year: int
    ) -> OrchestratorResponse:
        amounts = intent.params.get("amounts", [])
        amount = intent.params.get("amount")
        if len(amounts) >= 2:
            base, scenario = amounts[0], amounts[1]
        elif amount:
            # Use user's actual income as base from transaction history
            try:
                from sqlalchemy import func as sa_func, extract as sa_extract
                from app.models.transaction import Transaction, TransactionType

                actual_income = (
                    self.tools.db.query(
                        sa_func.coalesce(sa_func.sum(Transaction.amount), 0)
                    )
                    .filter(
                        Transaction.user_id == self.tools.user_id,
                        sa_extract("year", Transaction.transaction_date) == year,
                        Transaction.type == TransactionType.INCOME,
                    )
                    .scalar()
                )
                base = float(actual_income) if actual_income else amount * 0.8
            except Exception:
                base = amount * 0.8
            scenario = amount
        else:
            return self._ask_for_params(
                lang,
                "Please provide two amounts, e.g. 'What if: €40,000 vs €60,000'.",
                UserIntent.WHAT_IF,
            )
        yr = intent.params.get("year", year)
        data = self.tools.run_what_if(base, scenario, yr)
        text = _format_what_if(data, lang)
        return self._build_response(text, UserIntent.WHAT_IF, data, lang)

    def _handle_summarize(
        self, intent: IntentResult, message: str, lang: str, history: list, year: int
    ) -> OrchestratorResponse:
        summary = self.tools.get_financial_summary(year)
        extra = (
            f"User's financial data:\n{summary.get('summary', 'No data')}\n\n"
            "Provide a clear, concise summary of the user's tax situation for this year."
        )
        return self._handle_rag(message, lang, history, year, extra_context=extra)

    def _handle_explain_document(
        self, intent: IntentResult, message: str, lang: str, history: list, year: int
    ) -> OrchestratorResponse:
        # Try to load document data from conversation context or message
        extra = None
        try:
            # Check if a documentId was passed in the conversation history context
            doc_id = None
            for h in reversed(history):
                content = h.get("content", "")
                if "documentId:" in content:
                    import re as _re
                    m = _re.search(r"documentId:\s*(\d+)", content)
                    if m:
                        doc_id = int(m.group(1))
                        break

            if doc_id:
                from app.models.document import Document as DocModel
                doc = (
                    self.db.query(DocModel)
                    .filter(DocModel.id == doc_id, DocModel.user_id == self.user_id)
                    .first()
                )
                if doc and doc.ocr_result:
                    import json
                    ocr_data = doc.ocr_result
                    if isinstance(ocr_data, str):
                        ocr_data = json.loads(ocr_data)
                    # Build a compact summary of the extracted data
                    doc_type = doc.document_type.value if doc.document_type else "unknown"
                    suggestion = ocr_data.get("import_suggestion", {})
                    suggestion_type = suggestion.get("type", "")
                    suggestion_data = suggestion.get("data", {})
                    # Filter out internal keys
                    display_data = {
                        k: v for k, v in suggestion_data.items()
                        if k not in ("raw_fields", "status") and v is not None
                    }
                    extra = (
                        f"Document type: {doc_type}\n"
                        f"Suggestion type: {suggestion_type}\n"
                        f"Extracted data: {json.dumps(display_data, ensure_ascii=False, default=str)[:1500]}\n\n"
                        "Please explain what this document contains, what the extracted fields mean "
                        "in the context of Austrian tax law, and what the user should do with it."
                    )
        except Exception as exc:
            logger.debug("Failed to load document for explain: %s", exc)

        return self._handle_rag(message, lang, history, year, extra_context=extra)

    # ------------------------------------------------------------------
    # System Help (built-in usage guide)
    # ------------------------------------------------------------------

    def _handle_system_help(
        self,
        intent: IntentResult,
        message: str,
        language: str,
        history: List[Dict[str, str]],
        year: int,
    ) -> OrchestratorResponse:
        """Fallback system help — returns overview. Detailed help is handled by AI triage."""
        text = _SYSTEM_OVERVIEW.get(language, _SYSTEM_OVERVIEW["de"])
        return OrchestratorResponse(
            text=text,
            intent=UserIntent.SYSTEM_HELP,
            suggestions=_get_suggestions(UserIntent.SYSTEM_HELP, language),
        )

    # ------------------------------------------------------------------
    # RAG fallback (general Q&A)
    # ------------------------------------------------------------------

    def _handle_rag(
        self,
        message: str,
        language: str,
        history: List[Dict[str, str]],
        year: int,
        extra_context: Optional[str] = None,
    ) -> OrchestratorResponse:
        """Delegate to RAG service for general tax Q&A."""
        from app.models.user import User

        user = self.db.query(User).filter(User.id == self.user_id).first()

        # Try full RAG first, then direct LLM, then lightweight, then rule-based
        text = None

        from app.services.llm_service import get_llm_service
        llm = get_llm_service()

        source_tier = None

        # 1. Full RAG (LLM + vector search) — skip for Ollama-only (too slow on CPU)
        if llm.is_available and user and not llm.is_ollama_mode:
            try:
                from app.services.rag_service import RAGService
                rag = RAGService(self.db)

                if extra_context:
                    augmented_msg = f"{message}\n\n[System context: {extra_context}]"
                else:
                    augmented_msg = message

                text = rag.answer(user, augmented_msg, language, year)
                source_tier = "rag"
            except Exception as exc:
                logger.warning("Full RAG failed: %s", exc, exc_info=True)

        # 2. Direct LLM call (no vector search, just LLM with user data)
        #    Used when Full RAG fails (e.g. ChromaDB/SentenceTransformer not available)
        if text is None and llm.is_available and not llm.is_ollama_mode:
            try:
                financial_summary = ""
                if user:
                    try:
                        from app.services.rag_service import RAGService
                        rag = RAGService(self.db)
                        financial_summary = rag._build_financial_summary(user, year, language)
                    except Exception:
                        self.db.rollback()

                context_chunks = []
                if extra_context:
                    context_chunks.append(extra_context)

                text = llm.generate_response(
                    user_message=message,
                    language=language,
                    context_chunks=context_chunks,
                    user_financial_summary=financial_summary,
                    conversation_history=history,
                )
                source_tier = "llm"
                logger.info("Direct LLM call succeeded (no RAG retrieval)")
            except Exception as exc:
                logger.warning("Direct LLM call failed: %s", exc)

        # 3. Lightweight local RAG (Ollama-based, CPU)
        if text is None and llm.is_ollama_mode:
            try:
                from app.services.lightweight_rag_service import get_lightweight_tax_rag
                lightweight = get_lightweight_tax_rag()
                if lightweight.available:
                    user_ctx = ""
                    if user:
                        try:
                            from app.services.rag_service import RAGService
                            rag = RAGService(self.db)
                            user_ctx = rag._build_financial_summary(user, year, language)
                        except Exception:
                            self.db.rollback()
                    text = lightweight.answer_tax_question(
                        question=message,
                        language=language,
                        tax_year=year,
                        user_context=user_ctx,
                    )
                    source_tier = "lightweight"
            except Exception as exc:
                logger.warning("Lightweight RAG failed: %s", exc)

        # 4. Rule-based fallback
        if text is None:
            from app.api.v1.endpoints.ai_assistant import _generate_rule_based_response
            text = _generate_rule_based_response(message, language, {})
            source_tier = "rule_based"

        return OrchestratorResponse(
            text=text,
            intent=UserIntent.TAX_QA,
            suggestions=_get_suggestions(UserIntent.TAX_QA, language),
            show_disclaimer=True,
            source_tier=source_tier,
        )


    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_response(
        self,
        text: str,
        intent: UserIntent,
        data: Dict,
        language: str,
        source_tier: Optional[str] = None,
    ) -> OrchestratorResponse:
        """Build a standard response with disclaimer flag and suggestions."""
        return OrchestratorResponse(
            text=text,
            intent=intent,
            data=data,
            suggestions=_get_suggestions(intent, language),
            show_disclaimer=True,
            source_tier=source_tier,
        )

    def _ask_for_params(
        self, language: str, messages, intent: UserIntent
    ) -> OrchestratorResponse:
        """Ask user to provide missing parameters.

        `messages` can be:
          - Dict[str, str]: legacy per-language dict (used as-is)
          - str: English template, auto-translated via LLM for non-en/de/zh
        """
        if isinstance(messages, str):
            # For de/en/zh use simple hardcoded translations to save LLM calls
            text = messages
            if language not in ("en", "de", "zh"):
                try:
                    from app.services.llm_service import get_llm_service
                    llm = get_llm_service()
                    lang_names = {
                        "fr": "French", "ru": "Russian", "hu": "Hungarian",
                        "pl": "Polish", "tr": "Turkish", "bs": "Bosnian",
                    }
                    lang_name = lang_names.get(language, language)
                    text = llm.generate_simple(
                        system_prompt=f"Translate to {lang_name}. Return ONLY the translation, nothing else.",
                        user_prompt=messages,
                        temperature=0.1,
                        max_tokens=200,
                    )
                except Exception:
                    pass  # Fall back to English
        else:
            text = messages.get(language, messages.get("en", messages.get("de", "")))
        return OrchestratorResponse(
            text=text,
            intent=intent,
            suggestions=[],
        )
