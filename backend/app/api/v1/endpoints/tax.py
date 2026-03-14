"""
Tax Calculation API Endpoints

Provides tax calculation services including employee refund calculation,
tax simulation, and flat-rate comparison.
"""

from typing import Optional, List
from decimal import Decimal
from datetime import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Body, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import extract
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from app.db.base import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.services.employee_refund_calculator import (
    EmployeeRefundCalculator,
    LohnzettelData,
)

router = APIRouter()




class LohnzettelRequest(BaseModel):
    gross_income: float = Field(..., description="Gross annual income (Brutto)")
    withheld_tax: float = Field(..., description="Withheld income tax (Lohnsteuer)")
    withheld_svs: float = Field(default=0.0, description="Withheld social insurance contributions")
    employer_name: str = Field(..., description="Employer name")
    tax_year: int = Field(..., description="Tax year")


class AdditionalDeductionsRequest(BaseModel):
    donations: Optional[float] = Field(None, description="Charitable donations")
    church_tax: Optional[float] = Field(None, description="Church tax")
    other: Optional[float] = Field(None, description="Other deductible expenses")


class RefundCalculationRequest(BaseModel):
    lohnzettel: LohnzettelRequest
    additional_deductions: Optional[AdditionalDeductionsRequest] = None


# --- Helper: simple progressive tax calculation (2026 USP) ---
def _calc_progressive_tax(taxable_income: Decimal) -> Decimal:
    """Calculate Austrian progressive income tax for 2026.

    Brackets (after exemption of \u20ac13,539):
      \u20ac0 \u2013 \u20ac8,453   -> 20%   (= \u20ac13,539\u2013\u20ac21,992)
      \u20ac8,453 \u2013 \u20ac22,919  -> 30%   (= \u20ac21,992\u2013\u20ac36,458)
      \u20ac22,919 \u2013 \u20ac56,826 -> 40%   (= \u20ac36,458\u2013\u20ac70,365)
      \u20ac56,826 \u2013 \u20ac91,320 -> 48%   (= \u20ac70,365\u2013\u20ac104,859)
      \u20ac91,320 \u2013 \u20ac986,461 -> 50%  (= \u20ac104,859\u2013\u20ac1,000,000)
      \u20ac986,461+           -> 55%
    """
    if taxable_income <= 0:
        return Decimal("0")
    brackets = [
        (Decimal("0"), Decimal("8453"), Decimal("0.20")),
        (Decimal("8453"), Decimal("22919"), Decimal("0.30")),
        (Decimal("22919"), Decimal("56826"), Decimal("0.40")),
        (Decimal("56826"), Decimal("91320"), Decimal("0.48")),
        (Decimal("91320"), Decimal("986461"), Decimal("0.50")),
        (Decimal("986461"), None, Decimal("0.55")),
    ]
    tax = Decimal("0")
    remaining = taxable_income
    for lower, upper, rate in brackets:
        if remaining <= 0:
            break
        width = (upper - lower) if upper else remaining
        chunk = min(remaining, width)
        tax += chunk * rate
        remaining -= chunk
    return tax.quantize(Decimal("0.01"))


EXEMPTION = Decimal("13539")  # 2026 tax-free amount


@router.post("/tax/calculate-refund")
def calculate_employee_refund(
    request: RefundCalculationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Calculate employee tax refund (Arbeitnehmerveranlagung)."""
    try:
        calculator = EmployeeRefundCalculator()
        lohnzettel_data = LohnzettelData(
            gross_income=Decimal(str(request.lohnzettel.gross_income)),
            withheld_tax=Decimal(str(request.lohnzettel.withheld_tax)),
            withheld_svs=Decimal(str(request.lohnzettel.withheld_svs)),
            employer_name=request.lohnzettel.employer_name,
            tax_year=request.lohnzettel.tax_year,
        )
        additional_deductions = None
        if request.additional_deductions:
            additional_deductions = {}
            if request.additional_deductions.donations:
                additional_deductions["donations"] = Decimal(str(request.additional_deductions.donations))
            if request.additional_deductions.church_tax:
                additional_deductions["church_tax"] = Decimal(str(request.additional_deductions.church_tax))
            if request.additional_deductions.other:
                additional_deductions["other"] = Decimal(str(request.additional_deductions.other))
        result = calculator.calculate_refund(lohnzettel_data, current_user, additional_deductions)
        return result.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tax/calculate-refund-from-transactions")
def calculate_refund_from_transactions(
    tax_year: int = Body(..., description="Tax year"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Calculate employee tax refund from employment transactions."""
    try:
        calculator = EmployeeRefundCalculator()
        employment_transactions = (
            db.query(Transaction)
            .filter(
                Transaction.user_id == current_user.id,
                Transaction.type == TransactionType.INCOME,
                Transaction.income_category == IncomeCategory.EMPLOYMENT,
                extract("year", Transaction.transaction_date) == tax_year,
            )
            .all()
        )
        if not employment_transactions:
            raise HTTPException(status_code=404, detail=f"No employment income found for {tax_year}")
        result = calculator.calculate_refund_from_transactions(current_user, tax_year, employment_transactions)
        return result.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tax/refund-estimate")
def estimate_refund_potential(
    tax_year: int = Query(..., description="Tax year"),
    estimated_gross_income: Optional[float] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Estimate refund potential without Lohnzettel."""
    try:
        calculator = EmployeeRefundCalculator()
        if estimated_gross_income is None:
            txns = (
                db.query(Transaction)
                .filter(
                    Transaction.user_id == current_user.id,
                    Transaction.type == TransactionType.INCOME,
                    Transaction.income_category == IncomeCategory.EMPLOYMENT,
                    extract("year", Transaction.transaction_date) == tax_year,
                )
                .all()
            )
            if txns:
                estimated_gross_income = sum(float(t.amount) for t in txns)
            else:
                return {
                    "estimated_refund": 0.0,
                    "is_refund": False,
                    "confidence": "none",
                    "suggestions": ["Upload your Lohnzettel or add employment income to calculate refund"],
                    "message": "No income data available for estimation",
                }

        # Wrap user with UserLike-compatible attributes
        class _UserAdapter:
            def __init__(self, user):
                self.id = user.id
                self.email = user.email
                ci = getattr(user, "commuting_info", None) or {}
                self.commuting_distance = ci.get("distance_km") if isinstance(ci, dict) else None
                self.public_transport_available = ci.get("public_transport_available") if isinstance(ci, dict) else None
                fi = getattr(user, "family_info", None) or {}
                if isinstance(fi, dict) and fi:
                    from app.services.employee_refund_calculator import FamilyInfo
                    self.family_info = FamilyInfo(
                        num_children=fi.get("num_children", 0),
                        is_single_parent=fi.get("is_single_parent", False),
                    )
                else:
                    self.family_info = None

        estimate = calculator.estimate_refund_potential(
            _UserAdapter(current_user), tax_year, Decimal(str(estimated_gross_income))
        )
        return estimate
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# AI classification helper for What-If Simulator
# ---------------------------------------------------------------------------
_CLASSIFY_SYSTEM_PROMPT = """\
You are an Austrian tax classification expert. Given a description of income or expense,
classify it according to Austrian tax law (EStG / UStG).

CRITICAL: You MUST reply in the SAME LANGUAGE as the user's description.
If the description is in Chinese, reply in Chinese. If German, reply in German. Etc.

For INCOME, determine which Einkunftsart (§2 EStG) it belongs to:
- agriculture (§21 Land- und Forstwirtschaft)
- self_employment (§22 Selbständige Arbeit / Freiberufler)
- business (§23 Gewerbebetrieb)
- employment (§25 Nichtselbständige Arbeit)
- capital_gains (§27 Kapitalvermögen)
- rental (§28 Vermietung und Verpachtung)
- other_income (§29 Sonstige Einkünfte)

For EXPENSE, determine the expense category and whether it is tax-deductible.

IMPORTANT VAT RULES (UStG):
- Short-term accommodation rental (Airbnb, Ferienwohnung, hotel-like) = 10% VAT
  (§10 Abs 2 Z 4 UStG — Beherbergung / accommodation)
- Long-term residential rental (Wohnungsvermietung) = 10% VAT (§10 Abs 2 Z 4 UStG)
- Commercial property rental = 20% VAT (§10 Abs 1 UStG)
- Kleinunternehmerregelung: if annual turnover ≤ €55,000 (since 2025), VAT exemption applies
  (§6 Abs 1 Z 27 UStG) — note this in vat_note when relevant

INCOME TAX classification for short-term rental:
- With hotel-like services (cleaning, linens, breakfast, check-in) = §23 Gewerbebetrieb
- Without hotel-like services (just keys + apartment) = §28 Vermietung und Verpachtung

Respond ONLY with valid JSON (no markdown, no explanation outside JSON):
{
  "category": "<category_key>",
  "category_type": "income" or "expense",
  "legal_basis": "<§ reference and short explanation — in user's language>",
  "is_deductible": true/false (for expenses),
  "vat_rate": <decimal like 0.10 or 0.20 or null>,
  "vat_note": "<brief VAT explanation in user's language, or null>",
  "confidence": <0.0-1.0>,
  "explanation": "<1-2 sentence explanation in the SAME LANGUAGE as the description>"
}"""

_VERIFY_SYSTEM_PROMPT = """\
You are a senior Austrian tax auditor reviewing a classification made by a junior colleague.
Given the original description and the proposed classification, verify whether it is correct.

CRITICAL: You MUST reply in the SAME LANGUAGE as the original description.
If the description is in Chinese, ALL text fields must be in Chinese. Same for German, English, etc.

Check:
1. Is the Einkunftsart (income type) or expense category correct per EStG?
2. Is the legal basis (§ reference) accurate?
3. Is the VAT rate correct? Key Austrian VAT rates:
   - Accommodation / short-term rental (Beherbergung): 10% (§10 Abs 2 Z 4 UStG)
   - Long-term residential rental: 10% (§10 Abs 2 Z 4 UStG)
   - Commercial property rental: 20% (§10 Abs 1 UStG)
   - Kleinunternehmerregelung (≤ €55,000/year since 2025): VAT exempt (§6 Abs 1 Z 27 UStG)
4. Is the deductibility assessment correct?
5. Are there any edge cases or nuances the classifier may have missed?

If the classification is correct, return the SAME JSON with confidence raised (if appropriate).
If incorrect, return a CORRECTED JSON with the right values and explain the correction.

IMPORTANT: Respond ONLY with valid JSON (no markdown):
{
  "category": "<category_key>",
  "category_type": "income" or "expense",
  "legal_basis": "<§ reference — in user's language>",
  "is_deductible": true/false (for expenses),
  "vat_rate": <decimal like 0.10 or 0.20 or null>,
  "vat_note": "<brief VAT explanation in user's language, or null>",
  "confidence": <0.0-1.0>,
  "explanation": "<1-2 sentence explanation in the SAME LANGUAGE as the original description>",
  "verified": true,
  "correction_note": "<null if no correction, otherwise brief note in user's language>"
}"""


def _parse_llm_json(raw: str) -> Optional[dict]:
    """Parse JSON from LLM response, stripping markdown fences if present."""
    import json as _json

    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    text = text.strip()
    try:
        return _json.loads(text)
    except (ValueError, TypeError):
        return None


def _classify_with_ai(
    description: str,
    amount: float,
    change_type: str,
    user_type: str,
) -> Optional[dict]:
    """
    Two-pass AI classification using Groq LLM + RAG:
      Pass 1 — Classify: determine category, legal basis, VAT, deductibility
      Pass 2 — Verify: a second LLM call reviews and corrects the classification

    Returns a dict with category, legal_basis, is_deductible, vat_rate, explanation, etc.
    Returns None if LLM is unavailable or classification fails.
    """
    import json as _json

    try:
        from app.services.llm_service import get_llm_service
        from app.services.rag_retrieval_service import get_rag_retrieval_service

        llm = get_llm_service()
        if not (llm.is_available() if callable(llm.is_available) else llm.is_available):
            logger.info("LLM service not available — skipping AI classification")
            return None

        # ---- RAG context retrieval ----
        # Detect language from description for RAG retrieval
        def _detect_lang(text: str) -> str:
            """Simple language detection: Chinese chars → zh, else de (tax law is in German)."""
            for ch in text:
                if "\u4e00" <= ch <= "\u9fff":
                    return "zh"
            # Default to German for Austrian tax law context
            return "de"

        desc_lang = _detect_lang(description)
        rag = get_rag_retrieval_service()
        # Retrieve in user's language first, then fallback to German for completeness
        rag_results = rag.retrieve_context(query=description, language=desc_lang, top_k=3)
        if desc_lang != "de":
            # Also retrieve German context (most comprehensive)
            rag_de = rag.retrieve_context(query=description, language="de", top_k=2)
            rag_results.extend(rag_de)
        rag_context = ""
        if rag_results:
            snippets = [r["document"] for r in rag_results[:3]]
            rag_context = (
                "\n\n=== Relevant Austrian tax law context ===\n"
                + "\n---\n".join(snippets)
            )

        type_label = {
            "add_income": "INCOME",
            "add_expense": "EXPENSE",
            "remove_expense": "EXPENSE (being removed)",
        }.get(change_type, "UNKNOWN")

        user_prompt = (
            f"Type: {type_label}\n"
            f"Amount: €{amount:,.2f}\n"
            f"Description: {description}\n"
            f"User type: {user_type}\n"
            f"{rag_context}"
        )

        # ---- Pass 1: Classify ----
        logger.info("AI classification pass 1 (classify) for: %s", description[:80])
        raw1 = llm.generate_simple(
            system_prompt=_CLASSIFY_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.1,
            max_tokens=500,
        )

        classification = _parse_llm_json(raw1)
        if not classification or "category" not in classification:
            logger.warning("AI pass 1 failed to parse: %s", raw1[:200])
            return None

        logger.info(
            "AI pass 1 result: category=%s, confidence=%.2f",
            classification.get("category"),
            classification.get("confidence", 0),
        )

        # ---- Pass 2: Verify ----
        verify_prompt = (
            f"Original description: {description}\n"
            f"Type: {type_label}\n"
            f"Amount: €{amount:,.2f}\n"
            f"User type: {user_type}\n"
            f"{rag_context}\n\n"
            f"=== Classification to verify ===\n"
            f"{_json.dumps(classification, ensure_ascii=False, indent=2)}"
        )

        logger.info("AI classification pass 2 (verify)")
        raw2 = llm.generate_simple(
            system_prompt=_VERIFY_SYSTEM_PROMPT,
            user_prompt=verify_prompt,
            temperature=0.1,
            max_tokens=500,
        )

        verified = _parse_llm_json(raw2)
        if verified and "category" in verified:
            correction = verified.get("correction_note")
            if correction:
                logger.info("AI pass 2 corrected: %s", correction)
            else:
                logger.info("AI pass 2 confirmed classification")
            verified["verified"] = True
            return verified

        # Verification parse failed — return original classification anyway
        logger.warning("AI pass 2 parse failed, using pass 1 result")
        classification["verified"] = False
        return classification

    except Exception as exc:
        logger.warning("AI classification failed (non-fatal): %s", exc)
        return None


@router.post("/tax/simulate")
def simulate_tax_scenario(
    scenario: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Simulate tax impact of adding/removing income or expenses.

    Flow:
    1. If description provided, call LLM+RAG to classify the income/expense
       (determine category, deductibility, VAT implications, legal basis)
    2. Use TaxCalculationEngine (DB-backed tax rates) for proper calculation
    3. Return classification + tax comparison

    Accepts: {changeType, amount, description, category?, tax_year?}
    Returns: current vs simulated tax comparison + AI classification.
    """
    tax_year = scenario.get("tax_year", datetime.now().year)
    change_type = scenario.get("changeType", scenario.get("type", "add_expense"))
    change_amount = Decimal(str(scenario.get("amount", 0)))
    description = scenario.get("description", "")

    user_type = (
        current_user.user_type.value
        if hasattr(current_user.user_type, "value")
        else str(current_user.user_type)
    )
    is_gmbh = user_type == "gmbh"

    # ------------------------------------------------------------------
    # Step 1: AI classification via LLM + RAG (if description provided)
    # ------------------------------------------------------------------
    ai_classification = None
    if description.strip():
        ai_classification = _classify_with_ai(
            description=description,
            amount=float(change_amount),
            change_type=change_type,
            user_type=user_type,
        )

    # Use AI-suggested category or user-provided category
    suggested_category = None
    is_deductible = change_type != "add_income"  # default: expenses deductible
    if ai_classification:
        suggested_category = ai_classification.get("category")
        if ai_classification.get("is_deductible") is not None:
            is_deductible = ai_classification["is_deductible"]

    # ------------------------------------------------------------------
    # Step 2: Calculate current tax using TaxCalculationEngine (DB rates)
    # ------------------------------------------------------------------
    from app.services.tax_calculation_engine import TaxCalculationEngine

    engine = TaxCalculationEngine(db=db)

    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == current_user.id,
            extract("year", Transaction.transaction_date) == tax_year,
        )
        .all()
    )

    current_income = sum(
        t.amount for t in transactions if t.type == TransactionType.INCOME
    ) or Decimal("0")
    current_expenses = sum(
        t.amount for t in transactions if t.type == TransactionType.EXPENSE
    ) or Decimal("0")

    current_net = current_income - current_expenses

    if is_gmbh:
        from app.services.koest_calculator import KoEstCalculator

        koest_calc = KoEstCalculator()
        current_tax = koest_calc.calculate(profit=current_net).effective_koest
    else:
        calc, _vat_calc, _svs, _ded, _se = engine._get_calculators_for_year(tax_year)
        current_taxable = calc.apply_exemption(current_net)
        current_tax = calc.calculate_progressive_tax(current_taxable, tax_year).total_tax

    # ------------------------------------------------------------------
    # Step 3: Apply scenario and calculate simulated tax
    # ------------------------------------------------------------------
    sim_income = current_income
    sim_expenses = current_expenses

    if change_type == "add_income":
        sim_income += change_amount
    elif change_type == "add_expense":
        if is_deductible:
            sim_expenses += change_amount
        else:
            # Non-deductible expense: no tax impact, but affects net income
            sim_expenses += change_amount
    elif change_type == "remove_expense":
        sim_expenses = max(Decimal("0"), sim_expenses - change_amount)

    sim_net = sim_income - sim_expenses

    if is_gmbh:
        sim_tax = koest_calc.calculate(profit=sim_net).effective_koest
    else:
        sim_taxable = calc.apply_exemption(sim_net)
        sim_tax = calc.calculate_progressive_tax(sim_taxable, tax_year).total_tax

    tax_diff = float(sim_tax - current_tax)
    current_net_income = float(current_income - current_tax)
    sim_net_income = float(sim_income - sim_tax)

    # ------------------------------------------------------------------
    # Step 4: Build explanation (use AI explanation if available)
    # ------------------------------------------------------------------
    if ai_classification and ai_classification.get("explanation"):
        explanation = ai_classification["explanation"]
    elif change_type == "add_expense":
        explanation = (
            f"Adding a deductible expense of €{float(change_amount):,.2f} "
            f"reduces your taxable income, saving you €{abs(tax_diff):,.2f} in taxes."
            if tax_diff < 0
            else "This expense does not change your tax liability "
            "(income below exemption threshold)."
        )
    elif change_type == "add_income":
        explanation = (
            f"Adding €{float(change_amount):,.2f} in income "
            f"increases your tax by €{tax_diff:,.2f}."
        )
    else:
        explanation = (
            f"Removing €{float(change_amount):,.2f} in expenses "
            f"increases your taxable income by that amount."
        )

    result = {
        "scenario_type": change_type,
        "tax_year": tax_year,
        "currentTax": float(current_tax),
        "simulatedTax": float(sim_tax),
        "taxDifference": tax_diff,
        "currentNetIncome": current_net_income,
        "simulatedNetIncome": sim_net_income,
        "netIncomeDifference": sim_net_income - current_net_income,
        "explanation": explanation,
    }

    # Attach AI classification if available
    if ai_classification:
        result["classification"] = ai_classification

    return result




@router.get("/tax/flat-rate-compare")
def compare_flat_rate_tax(
    tax_year: Optional[int] = Query(None, description="Tax year"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Compare actual accounting vs flat-rate (Basispauschalierung) tax system.

    Per WKO / § 17 EStG, Basispauschalierung is ONLY for:
    - § 22 Selbständige Arbeit (freelancers)
    - § 23 Gewerbebetrieb (business owners)

    NOT for: employees, GmbH, landlords (§ 28 rental income).

    For mixed users (self-employed + landlord): Basispauschalierung applies
    ONLY to the self-employment/business portion. Rental income is always
    calculated via actual accounting (Einnahmen-Ausgaben-Rechnung).

    Rates are read from TaxConfiguration DB table (deduction_config.self_employed).
    """
    from app.models.tax_configuration import TaxConfiguration

    if tax_year is None:
        tax_year = datetime.now().year

    # --- Load rates from DB ---
    tax_config = (
        db.query(TaxConfiguration)
        .filter(TaxConfiguration.tax_year == tax_year)
        .first()
    )

    if tax_config and tax_config.deduction_config:
        se_config = tax_config.deduction_config.get("self_employed", {})
        flat_rate_pct = Decimal(str(se_config.get("flat_rate_general", "0.12")))
        max_turnover = Decimal(str(se_config.get("flat_rate_turnover_limit", "220000")))
        # max deduction = turnover_limit * rate (WKO rule)
        max_deduction = max_turnover * flat_rate_pct
    else:
        # Fallback if no DB config
        flat_rate_pct = Decimal("0.12")
        max_turnover = Decimal("220000")
        max_deduction = Decimal("26400")

    pct_display = float(flat_rate_pct * 100)

    # --- Load transactions ---
    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == current_user.id,
            extract("year", Transaction.transaction_date) == tax_year,
        )
        .all()
    )

    user_type = (
        current_user.user_type.value
        if hasattr(current_user.user_type, "value")
        else str(current_user.user_type)
    )

    # --- Split income by source for mixed users ---
    # Basispauschalierung-eligible categories: self_employment, business
    eligible_income_cats = {"self_employment", "business"}

    business_income = Decimal("0")
    rental_income = Decimal("0")
    other_income = Decimal("0")
    business_expenses = Decimal("0")
    rental_expenses = Decimal("0")
    other_expenses = Decimal("0")

    for t in transactions:
        cat = t.income_category.value if t.income_category and hasattr(t.income_category, "value") else (str(t.income_category) if t.income_category else None)
        ecat = t.expense_category.value if t.expense_category and hasattr(t.expense_category, "value") else None

        if t.type == TransactionType.INCOME:
            if cat in eligible_income_cats:
                business_income += t.amount
            elif cat == "rental":
                rental_income += t.amount
            else:
                other_income += t.amount
        elif t.type == TransactionType.EXPENSE and t.is_deductible:
            # Assign expenses: property-related → rental, else → business
            if ecat in ("property_maintenance", "property_insurance", "property_management",
                        "mortgage_interest", "depreciation"):
                rental_expenses += t.amount
            elif cat == "rental" or (t.property_id is not None):
                rental_expenses += t.amount
            else:
                business_expenses += t.amount

    gross_income = business_income + rental_income + other_income
    actual_expenses = business_expenses + rental_expenses

    # --- Eligibility ---
    is_eligible = business_income <= max_turnover
    if user_type == "employee":
        is_eligible = False
        reason = "not_available_employee"
    elif user_type == "gmbh":
        is_eligible = False
        reason = "not_available_gmbh"
    elif user_type == "landlord":
        # Pure landlord — no business income to apply flat rate to
        is_eligible = False
        reason = "not_available_landlord"
    elif business_income == 0:
        is_eligible = False
        reason = "no_business_income"
    elif not is_eligible:
        reason = "turnover_exceeds_limit"
    else:
        reason = "eligible"

    # --- Actual accounting (all income types) ---
    actual_taxable = max(Decimal("0"), gross_income - actual_expenses - EXEMPTION)
    actual_tax = _calc_progressive_tax(actual_taxable)
    actual_net = gross_income - actual_tax

    # --- Flat-rate method ---
    # Only business income gets flat-rate deduction; rental uses actual expenses
    flat_biz_deduction = min(business_income * flat_rate_pct, max_deduction)
    flat_taxable = max(
        Decimal("0"),
        (business_income - flat_biz_deduction)
        + (rental_income - rental_expenses)
        + other_income
        - EXEMPTION,
    )
    flat_tax = _calc_progressive_tax(flat_taxable)
    flat_net = gross_income - flat_tax

    savings = float(actual_tax - flat_tax)
    recommendation = "flat_rate" if savings > 0 and is_eligible else "actual"

    return {
        "tax_year": tax_year,
        "actualAccounting": {
            "grossIncome": float(gross_income),
            "deductibleExpenses": float(actual_expenses),
            "taxableIncome": float(actual_taxable),
            "incomeTax": float(actual_tax),
            "netIncome": float(actual_net),
        },
        "flatRate": {
            "grossIncome": float(gross_income),
            "flatRateDeduction": float(flat_biz_deduction),
            "flatRatePercentage": pct_display,
            "taxableIncome": float(flat_taxable),
            "incomeTax": float(flat_tax),
            "netIncome": float(flat_net),
        },
        "savings": savings,
        "recommendation": recommendation,
        "eligibility": {
            "isEligible": is_eligible,
            "reason": reason,
            "maxProfit": float(max_turnover),
        },
    }



@router.get("/tax/koest-vs-est")
def compare_koest_vs_est(
    tax_year: Optional[int] = Query(None, description="Tax year"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Compare GmbH (KoeSt 23% + KESt 27.5%) vs Einzelunternehmen (ESt progressive).

    Helps users decide whether GmbH structure is tax-advantageous.
    """
    if tax_year is None:
        tax_year = datetime.now().year

    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == current_user.id,
            extract("year", Transaction.transaction_date) == tax_year,
        )
        .all()
    )

    gross_income = sum(
        t.amount for t in transactions if t.type == TransactionType.INCOME
    ) or Decimal("0")
    deductible_expenses = sum(
        t.amount for t in transactions
        if t.type == TransactionType.EXPENSE and t.is_deductible
    ) or Decimal("0")

    profit = gross_income - deductible_expenses

    # ESt calculation
    est_taxable = max(Decimal("0"), profit - EXEMPTION)
    est_tax = _calc_progressive_tax(est_taxable)

    # KoeSt calculation
    from app.services.koest_calculator import KoEstCalculator
    koest_calc = KoEstCalculator()
    comparison = koest_calc.compare_with_est(profit=profit, est_tax=est_tax)
    comparison["tax_year"] = tax_year

    return comparison


# --- Einkommensteuerbescheid Import ---


class BescheidImportRequest(BaseModel):
    """Request to import data from Einkommensteuerbescheid OCR text"""
    ocr_text: str = Field(..., description="OCR-extracted text from Steuerberechnung document")
    document_id: Optional[int] = Field(None, description="Linked document ID if uploaded via OCR")


@router.post("/tax/import-bescheid")
def import_einkommensteuerbescheid(
    request: BescheidImportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Import data from an Einkommensteuerbescheid (annual income tax assessment).

    Extracts structured tax data from OCR text and creates transactions:
    - Employment income (KZ 245)
    - Rental income/loss (V+V from E1b)
    - Deductions (Werbungskosten, Telearbeitspauschale)
    - Updates user profile (tax number, children, etc.)

    Returns extracted data summary and list of created transactions.
    """
    from app.services.bescheid_import_service import BescheidImportService

    if not request.ocr_text or len(request.ocr_text.strip()) < 50:
        raise HTTPException(
            status_code=400,
            detail="OCR text is too short to be a valid Einkommensteuerbescheid",
        )

    import_service = BescheidImportService(db)

    try:
        result = import_service.import_from_ocr_text(
            text=request.ocr_text,
            user_id=current_user.id,
            document_id=request.document_id,
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse Einkommensteuerbescheid: {str(e)}",
        )

    return result


@router.post("/tax/parse-bescheid")
def parse_einkommensteuerbescheid(
    request: BescheidImportRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Parse (preview) an Einkommensteuerbescheid without creating transactions.

    Use this to show the user what data was extracted before confirming import.
    """
    from app.services.bescheid_extractor import BescheidExtractor

    if not request.ocr_text or len(request.ocr_text.strip()) < 50:
        raise HTTPException(
            status_code=400,
            detail="OCR text is too short to be a valid Einkommensteuerbescheid",
        )

    extractor = BescheidExtractor()
    data = extractor.extract(request.ocr_text)

    return extractor.to_dict(data)


@router.post("/tax/upload-bescheid")
async def upload_and_parse_bescheid(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a Bescheid PDF/image and extract text synchronously (no Celery needed).

    This endpoint:
    1. Reads the uploaded file
    2. Extracts text directly from PDF (PyMuPDF) or via Tesseract for images
    3. Parses the extracted text with BescheidExtractor
    4. Returns the parsed preview data + raw text for subsequent import

    Use this instead of the generic document upload for Bescheid imports,
    as it doesn't depend on async OCR processing.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    content = await file.read()
    if len(content) < 100:
        raise HTTPException(status_code=400, detail="File is too small")
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    raw_text = ""

    # Try PDF text extraction first (digital PDFs from FinanzOnline)
    if content[:5] == b"%PDF-":
        try:
            import fitz

            doc = fitz.open(stream=content, filetype="pdf")
            text_parts = []
            for i in range(min(len(doc), 5)):
                page_text = doc[i].get_text()
                if page_text:
                    text_parts.append(page_text)
            doc.close()
            raw_text = "\n".join(text_parts).strip()
        except Exception as e:
            logger.warning(f"PDF text extraction failed: {e}")

    # If PDF text extraction yielded nothing, try OCR
    if not raw_text or len(raw_text) < 30:
        try:
            from app.services.ocr_engine import OCREngine

            ocr = OCREngine()
            result = ocr.process_document(content)
            raw_text = result.raw_text or ""
        except Exception as e:
            logger.warning(f"OCR processing failed: {e}")

    if not raw_text or len(raw_text.strip()) < 30:
        raise HTTPException(
            status_code=400,
            detail="Could not extract text from the uploaded file. "
            "Please ensure it is a readable PDF or a clear image.",
        )

    # Parse with BescheidExtractor
    from app.services.bescheid_extractor import BescheidExtractor

    extractor = BescheidExtractor()
    data = extractor.extract(raw_text)
    parsed = extractor.to_dict(data)
    parsed["raw_text"] = raw_text

    return parsed


# --- E1 Form Import ---


class E1FormImportRequest(BaseModel):
    """Request to import data from E1 tax declaration form OCR text"""
    ocr_text: str = Field(..., description="OCR-extracted text from E1 form")
    document_id: Optional[int] = Field(None, description="Linked document ID if uploaded")


@router.post("/tax/import-e1-form")
def import_e1_form(
    request: E1FormImportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Import data from an E1 tax declaration form (Einkommensteuererklärung).

    Extracts structured tax data from OCR text and creates transactions:
    - Income by KZ codes (245, 210, 220, 350, 370, 390)
    - Deductions (260, 261, 263, 450, 458, 459)
    - Updates user profile (tax number, children, etc.)

    Returns extracted data summary and list of created transactions.
    """
    from app.services.e1_form_import_service import E1FormImportService

    if not request.ocr_text or len(request.ocr_text.strip()) < 50:
        raise HTTPException(
            status_code=400,
            detail="OCR text is too short to be a valid E1 form",
        )

    import_service = E1FormImportService(db)

    try:
        result = import_service.import_from_ocr_text(
            text=request.ocr_text,
            user_id=current_user.id,
            document_id=request.document_id,
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse E1 form: {str(e)}",
        )

    return result


@router.post("/tax/parse-e1-form")
def parse_e1_form(
    request: E1FormImportRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Parse (preview) an E1 form without creating transactions.

    Use this to show the user what data was extracted before confirming import.
    """
    from app.services.e1_form_extractor import E1FormExtractor

    if not request.ocr_text or len(request.ocr_text.strip()) < 50:
        raise HTTPException(
            status_code=400,
            detail="OCR text is too short to be a valid E1 form",
        )

    extractor = E1FormExtractor()
    data = extractor.extract(request.ocr_text)

    return extractor.to_dict(data)


@router.post("/tax/upload-e1-form")
async def upload_and_parse_e1_form(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Upload an E1 form PDF and extract text synchronously.

    This endpoint:
    1. Reads the uploaded file
    2. Extracts text directly from PDF (PyMuPDF)
    3. Parses the extracted text with E1FormExtractor
    4. Returns the parsed preview data + raw text for subsequent import
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    content = await file.read()
    if len(content) < 100:
        raise HTTPException(status_code=400, detail="File is too small")
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    raw_text = ""

    # Try PDF text extraction first
    if content[:5] == b"%PDF-":
        try:
            import fitz

            doc = fitz.open(stream=content, filetype="pdf")
            text_parts = []
            for i in range(min(len(doc), 10)):  # E1 forms can be longer
                page_text = doc[i].get_text()
                if page_text:
                    text_parts.append(page_text)
            doc.close()
            raw_text = "\n".join(text_parts).strip()
        except Exception as e:
            logger.warning(f"PDF text extraction failed: {e}")

    # If PDF text extraction yielded nothing, try OCR
    if not raw_text or len(raw_text) < 30:
        try:
            from app.services.ocr_engine import OCREngine

            ocr = OCREngine()
            result = ocr.process_document(content)
            raw_text = result.raw_text or ""
        except Exception as e:
            logger.warning(f"OCR processing failed: {e}")

    if not raw_text or len(raw_text.strip()) < 30:
        raise HTTPException(
            status_code=400,
            detail="Could not extract text from the uploaded file. "
            "Please ensure it is a readable PDF or a clear image.",
        )

    # Parse with E1FormExtractor
    from app.services.e1_form_extractor import E1FormExtractor

    extractor = E1FormExtractor()
    data = extractor.extract(raw_text)
    parsed = extractor.to_dict(data)
    parsed["raw_text"] = raw_text

    return parsed


# ------------------------------------------------------------------
# Knowledge Base: Auto-scrape official Austrian tax law sources
# ------------------------------------------------------------------
@router.post("/tax/refresh-knowledge-base")
async def refresh_knowledge_base(
    source_ids: Optional[List[str]] = Body(None, description="Source IDs to scrape, or null for all"),
    current_user: User = Depends(get_current_user),
):
    """
    Scrape official Austrian tax law sources (WKO, USP, BMF),
    extract structured knowledge via LLM, and update the vector DB.

    This replaces manual knowledge base maintenance with automated,
    source-verified data from official government websites.

    Admin-only endpoint. First request may be slow (~60s) due to
    web fetching + LLM extraction.
    """
    from app.services.tax_law_scraper import TaxLawScraper

    scraper = TaxLawScraper()
    try:
        result = await scraper.scrape_and_update(source_ids=source_ids)
    except Exception as e:
        logger.error(f"Knowledge base refresh failed: {e}")
        raise HTTPException(status_code=500, detail=f"Scrape failed: {str(e)}")

    return result


@router.get("/tax/knowledge-base-status")
async def knowledge_base_status(
    current_user: User = Depends(get_current_user),
):
    """Check the current state of the knowledge base collections."""
    from app.services.vector_db_service import get_vector_db_service

    vdb = get_vector_db_service()
    collections = {}
    for name in ["austrian_tax_law", "usp_2026_tax_tables", "tax_faq", "scraped_tax_law"]:
        try:
            coll = vdb._get_collection(name)
            collections[name] = {"count": coll.count()}
        except Exception:
            collections[name] = {"count": 0, "status": "not_initialized"}

    return {"collections": collections}
