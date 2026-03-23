"""
Tax Calculation API Endpoints

Provides tax calculation services including employee refund calculation,
tax simulation, and flat-rate comparison.
"""

from typing import Any, Dict, Optional, List
from decimal import Decimal
from datetime import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Body, Response, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import extract
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from app.db.base import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.models.transaction_line_item import LineItemPostingType
from app.services.employee_refund_calculator import (
    EmployeeRefundCalculator,
    LohnzettelData,
)
from app.services.credit_service import CreditService, InsufficientCreditsError
from app.services.ifb_calculator import calculate_ifb, IFBAssetType
from app.services.what_if_simulator import WhatIfSimulator
from app.services.flat_rate_tax_comparator import FlatRateTaxComparator
from app.services.savings_suggestion_service import SavingsSuggestionService
from app.services.posting_line_utils import sum_postings

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


def _build_employee_refund_user_adapter(user: User):
    """Adapt the persisted user profile to EmployeeRefundCalculator's protocol."""

    class _UserAdapter:
        def __init__(self, wrapped_user: User):
            self.id = wrapped_user.id
            self.email = wrapped_user.email

            commuting_info = getattr(wrapped_user, "commuting_info", None) or {}
            self.commuting_distance = (
                commuting_info.get("distance_km") if isinstance(commuting_info, dict) else None
            )
            self.public_transport_available = (
                commuting_info.get("public_transport_available")
                if isinstance(commuting_info, dict)
                else None
            )

            family_info = getattr(wrapped_user, "family_info", None) or {}
            if isinstance(family_info, dict) and family_info:
                self.family_info = FamilyInfo(
                    num_children=family_info.get("num_children", 0),
                    is_single_parent=family_info.get("is_single_parent", False),
                    children_under_18=family_info.get("children_under_18", 0),
                    children_18_to_24=family_info.get("children_18_to_24", 0),
                    is_sole_earner=family_info.get("is_sole_earner", False),
                )
            else:
                self.family_info = None

            self.telearbeit_days = getattr(wrapped_user, "telearbeit_days", None)
            self.employer_telearbeit_pauschale = getattr(
                wrapped_user, "employer_telearbeit_pauschale", None
            )

    return _UserAdapter(user)


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
        result = calculator.calculate_refund(
            lohnzettel_data,
            _build_employee_refund_user_adapter(current_user),
            additional_deductions,
        )
        return result.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Employee refund calculation failed")
        raise HTTPException(status_code=500, detail="tax_calculation_error")


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
        result = calculator.calculate_refund_from_transactions(
            _build_employee_refund_user_adapter(current_user),
            tax_year,
            employment_transactions,
        )
        return result.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Refund calculation from transactions failed")
        raise HTTPException(status_code=500, detail="tax_calculation_error")


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

        estimate = calculator.estimate_refund_potential(
            _build_employee_refund_user_adapter(current_user),
            tax_year,
            Decimal(str(estimated_gross_income)),
        )
        return estimate
    except Exception as e:
        logger.exception("Refund estimate calculation failed")
        raise HTTPException(status_code=500, detail="tax_calculation_error")


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
    """Parse JSON from LLM response, handling markdown fences, think tags, etc."""
    import json as _json
    import re as _re

    text = raw.strip()
    # Remove <think>...</think> reasoning blocks (GPT-OSS, DeepSeek, Qwen)
    text = _re.sub(r"<think>.*?</think>", "", text, flags=_re.DOTALL).strip()
    # Remove markdown fences
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    text = text.strip()
    # Try direct parse
    try:
        return _json.loads(text)
    except (ValueError, TypeError):
        pass
    # Try to find JSON object in the text
    match = _re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, _re.DOTALL)
    if match:
        try:
            return _json.loads(match.group(0))
        except (ValueError, TypeError):
            pass
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
            max_tokens=1000,
        )

        classification = _parse_llm_json(raw1)
        if not classification or "category" not in classification:
            logger.warning("AI pass 1 failed to parse. Raw[0:300]: %s", raw1[:300])
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
            max_tokens=1000,
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
    response: Response = None,
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

    # --- Credit deduction ---
    credit_service = CreditService(db, redis_client=None)
    try:
        deduction = credit_service.check_and_deduct(
            user_id=current_user.id,
            operation="tax_calc",
        )
    except InsufficientCreditsError as e:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient credits: {e.required} required, {e.available} available",
        )

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
    # Step 2+3: Delegate to WhatIfSimulator for tax calculation
    # ------------------------------------------------------------------
    from app.schemas.transaction import TransactionCreate
    from datetime import date as _date

    simulator = WhatIfSimulator(db)

    try:
        if change_type == "add_expense":
            # Build a TransactionCreate for the simulator
            expense_category_val = None
            if ai_classification and ai_classification.get("category"):
                try:
                    expense_category_val = ExpenseCategory(ai_classification["category"])
                except (ValueError, KeyError):
                    expense_category_val = None

            simulation_anchor_date = min(_date(tax_year, 12, 31), _date.today())

            expense = TransactionCreate(
                type=TransactionType.EXPENSE,
                amount=change_amount,
                transaction_date=simulation_anchor_date,
                description=description or "Simulated expense",
                expense_category=expense_category_val,
                is_deductible=is_deductible,
            )
            sim_result = simulator.simulate_add_expense(
                user_id=current_user.id,
                tax_year=tax_year,
                expense=expense,
            )
        elif change_type == "add_income":
            sim_result = simulator.simulate_income_change(
                user_id=current_user.id,
                tax_year=tax_year,
                income_change=change_amount,
            )
        elif change_type == "remove_expense":
            # remove_expense by amount (no transaction_id) — use income_change
            # with negative sign to simulate the effect of removing an expense
            # (removing a deduction increases taxable income)
            sim_result = simulator.simulate_income_change(
                user_id=current_user.id,
                tax_year=tax_year,
                income_change=change_amount,  # positive = more taxable income
            )
        else:
            sim_result = simulator.simulate_income_change(
                user_id=current_user.id,
                tax_year=tax_year,
                income_change=change_amount,
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    current_tax = Decimal(str(sim_result["current_tax"]))
    sim_tax = Decimal(str(sim_result["simulated_tax"]))
    tax_diff = float(sim_result["tax_difference"])
    # Compute net incomes: simulator provides breakdown but not net income directly.
    # Use income from breakdown if available, otherwise estimate from tax values.
    breakdown = sim_result.get("breakdown", {})
    current_income_val = float(sim_result.get("current_income", 0))
    sim_income_val = float(sim_result.get("simulated_income", current_income_val))
    current_net_income = current_income_val - float(current_tax) if current_income_val else 0.0
    sim_net_income = sim_income_val - float(sim_tax) if sim_income_val else 0.0

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

    if response is not None:
        response.headers["X-Credits-Remaining"] = str(
            deduction.balance_after.available_without_overage
        )

    db.commit()
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
    """
    if tax_year is None:
        tax_year = datetime.now().year

    comparator = FlatRateTaxComparator(db)
    result = comparator.compare_methods(user_id=current_user.id, tax_year=tax_year)

    # Map service output to the existing API response shape
    if not result.get("eligible", False):
        # Ineligible — build a minimal response from actual_accounting data
        actual = result.get("actual_accounting", {})
        reason = result.get("reason", "not_eligible")
        return {
            "tax_year": tax_year,
            "actualAccounting": {
                "grossIncome": actual.get("total_income", 0.0),
                "deductibleExpenses": actual.get("total_expenses", 0.0),
                "taxableIncome": actual.get("profit", 0.0),
                "incomeTax": actual.get("income_tax", 0.0),
                "netIncome": actual.get("net_income", 0.0),
            },
            "flatRate": {
                "grossIncome": actual.get("total_income", 0.0),
                "flatRateDeduction": 0.0,
                "flatRatePercentage": 12.0,
                "basicExemption": 0.0,
                "taxableIncome": 0.0,
                "incomeTax": 0.0,
                "netIncome": 0.0,
            },
            "savings": 0.0,
            "recommendation": "actual",
            "eligibility": {
                "isEligible": False,
                "reason": reason,
                "maxProfit": float(comparator.TURNOVER_THRESHOLD),
            },
        }

    actual = result.get("actual_accounting", {})
    # Use 6% flat rate as the primary comparison (most common)
    flat6 = result.get("flat_rate_6_percent", {})
    rec = result.get("recommendation", {})
    savings = rec.get("savings_vs_actual", 0.0)
    best = rec.get("best_method", "actual_accounting")
    recommendation = "flat_rate" if best != "actual_accounting" else "actual"

    return {
        "tax_year": tax_year,
        "actualAccounting": {
            "grossIncome": actual.get("total_income", 0.0),
            "deductibleExpenses": actual.get("total_expenses", 0.0),
            "taxableIncome": actual.get("profit", 0.0),
            "incomeTax": actual.get("income_tax", 0.0),
            "netIncome": actual.get("net_income", 0.0),
        },
        "flatRate": {
            "grossIncome": flat6.get("total_income", 0.0),
            "flatRateDeduction": flat6.get("deemed_expenses", 0.0),
            "flatRatePercentage": float(flat6.get("flat_rate_percentage", "6%").replace("%", "")) if isinstance(flat6.get("flat_rate_percentage"), str) else 6.0,
            "basicExemption": flat6.get("basic_exemption", 0.0),
            "taxableIncome": flat6.get("taxable_profit", flat6.get("profit", 0.0)),
            "incomeTax": flat6.get("income_tax", 0.0),
            "netIncome": flat6.get("net_income", 0.0),
        },
        "savings": savings,
        "recommendation": recommendation,
        "eligibility": {
            "isEligible": True,
            "reason": "eligible",
            "maxProfit": float(comparator.TURNOVER_THRESHOLD),
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

    gross_income = sum_postings(
        transactions,
        posting_types={LineItemPostingType.INCOME},
        include_private_use=False,
    )
    deductible_expenses = sum_postings(
        transactions,
        posting_types={LineItemPostingType.EXPENSE},
        deductible_only=True,
        include_private_use=False,
    )

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
    edited_data: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional user-corrected tax data to persist instead of the raw parser output",
    )


def _normalize_tax_import_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalize_tax_import_value(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_normalize_tax_import_value(item) for item in value]
    if not isinstance(value, str):
        return value

    stripped = value.strip()
    if stripped == "":
        return None

    normalized = (
        stripped.replace("EUR", "")
        .replace("€", "")
        .replace(" ", "")
    )
    if normalized.count(",") == 1 and normalized.count(".") >= 1:
        normalized = normalized.replace(".", "").replace(",", ".")
    elif normalized.count(",") == 1 and normalized.count(".") == 0:
        normalized = normalized.replace(",", ".")

    try:
        numeric = float(normalized)
        return int(numeric) if numeric.is_integer() else numeric
    except ValueError:
        return stripped


def _merge_tax_import_data(
    base_data: Dict[str, Any],
    edited_data: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    import json as _json

    merged = _json.loads(_json.dumps(base_data or {}))
    if not edited_data:
        return merged

    for key, value in edited_data.items():
        normalized_value = _normalize_tax_import_value(value)
        if (
            key == "all_kz_values"
            and isinstance(normalized_value, dict)
            and isinstance(merged.get("all_kz_values"), dict)
        ):
            merged["all_kz_values"].update(normalized_value)
            continue
        merged[key] = normalized_value

    return merged


def _confirm_tax_form_data(
    *,
    db: Session,
    current_user: User,
    data_type: str,
    suggestion_type: str,
    data: Dict[str, Any],
    document_id: Optional[int],
) -> Dict[str, Any]:
    import json as _json
    from sqlalchemy.orm.attributes import flag_modified
    from app.models.tax_filing_data import TaxFilingData

    document = None
    if document_id is not None:
        document = (
            db.query(Document)
            .filter(Document.id == document_id, Document.user_id == current_user.id)
            .first()
        )
        if not document:
            raise HTTPException(status_code=404, detail="document_not_found")

    tax_year = data.get("tax_year") or data.get("year")

    tax_filing = None
    if document_id is not None:
        tax_filing = (
            db.query(TaxFilingData)
            .filter(
                TaxFilingData.user_id == current_user.id,
                TaxFilingData.source_document_id == document_id,
                TaxFilingData.data_type == data_type,
            )
            .first()
        )

    if tax_filing:
        tax_filing.tax_year = tax_year
        tax_filing.data = data
        tax_filing.status = "confirmed"
        tax_filing.confirmed_at = datetime.utcnow()
    else:
        tax_filing = TaxFilingData(
            user_id=current_user.id,
            tax_year=tax_year,
            data_type=data_type,
            source_document_id=document_id,
            data=data,
            status="confirmed",
            confirmed_at=datetime.utcnow(),
        )
        db.add(tax_filing)
        db.flush()

    steuernummer = data.get("steuernummer")
    if isinstance(steuernummer, str) and steuernummer.strip():
        current_user.tax_number = steuernummer.strip()

    if document is not None:
        updated_ocr = _json.loads(_json.dumps(document.ocr_result)) if document.ocr_result else {}
        suggestion = updated_ocr.get("import_suggestion") or {}
        suggestion.update(
            {
                "type": suggestion_type,
                "status": "confirmed",
                "data": data,
                "confidence": float(document.confidence_score or data.get("confidence") or 0.0),
                "tax_filing_data_id": tax_filing.id,
            }
        )
        updated_ocr["import_suggestion"] = suggestion
        document.ocr_result = updated_ocr
        flag_modified(document, "ocr_result")

    db.commit()

    return {
        "message": f"Tax data ({data_type}) confirmed successfully",
        "tax_filing_data_id": tax_filing.id,
        "data_type": data_type,
        "tax_year": tax_year,
        "saved_data": data,
        "document_id": document_id,
    }


@router.post("/tax/import-bescheid")
def import_einkommensteuerbescheid(
    request: BescheidImportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Confirm data from an Einkommensteuerbescheid and persist it as tax filing data.
    """
    from app.services.bescheid_extractor import BescheidExtractor

    if not request.ocr_text or len(request.ocr_text.strip()) < 50:
        raise HTTPException(
            status_code=400,
            detail="OCR text is too short to be a valid Einkommensteuerbescheid",
        )

    try:
        extractor = BescheidExtractor()
        parsed = extractor.to_dict(extractor.extract(request.ocr_text))
        confirmed_data = _merge_tax_import_data(parsed, request.edited_data)
        result = _confirm_tax_form_data(
            db=db,
            current_user=current_user,
            data_type="einkommensteuerbescheid",
            suggestion_type="import_bescheid",
            data=confirmed_data,
            document_id=request.document_id,
        )
    except Exception as e:
        logger.exception("Failed to parse Einkommensteuerbescheid")
        raise HTTPException(
            status_code=400,
            detail="tax_calculation_error",
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
    edited_data: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional user-corrected tax data to persist instead of the raw parser output",
    )


@router.post("/tax/import-e1-form")
def import_e1_form(
    request: E1FormImportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Confirm data from an E1 tax declaration form and persist it as tax filing data.
    """
    from app.services.e1_form_extractor import E1FormExtractor

    if not request.ocr_text or len(request.ocr_text.strip()) < 50:
        raise HTTPException(
            status_code=400,
            detail="OCR text is too short to be a valid E1 form",
        )

    try:
        extractor = E1FormExtractor()
        parsed = extractor.to_dict(extractor.extract(request.ocr_text))
        confirmed_data = _merge_tax_import_data(parsed, request.edited_data)
        result = _confirm_tax_form_data(
            db=db,
            current_user=current_user,
            data_type="e1_form",
            suggestion_type="import_e1",
            data=confirmed_data,
            document_id=request.document_id,
        )
    except Exception as e:
        logger.exception("Failed to parse E1 form")
        raise HTTPException(
            status_code=400,
            detail="tax_calculation_error",
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
        logger.exception("Knowledge base refresh failed")
        raise HTTPException(status_code=500, detail="tax_calculation_error")

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


# ═══ GrESt (Grunderwerbsteuer) Calculator ═══


class GrEStRequest(BaseModel):
    grundstueckswert: float = Field(..., description="Grundstueckswert (property value)")
    is_family_transfer: bool = Field(default=False, description="Family transfer (stepped rates)")


@router.post("/tax/calculate-grest")
def calculate_grest_endpoint(
    request: GrEStRequest,
    current_user: User = Depends(get_current_user),
):
    """Calculate Grunderwerbsteuer (property transfer tax).

    Standard: 3.5% flat rate.
    Family transfer (§7 Abs 1 Z 2 GrEstG): stepped rates 0.5% / 2.0% / 3.5%.
    """
    from app.services.grest_calculator import calculate_grest

    result = calculate_grest(
        grundstueckswert=Decimal(str(request.grundstueckswert)),
        is_family_transfer=request.is_family_transfer,
    )
    return {
        "grundstueckswert": float(result.grundstueckswert),
        "is_family_transfer": result.is_family_transfer,
        "tax_amount": float(result.tax_amount),
        "effective_rate": float(result.effective_rate),
        "tier_breakdown": result.tier_breakdown,
        "note": result.note,
    }


# ═══ IFB (Investitionsfreibetrag) Calculator ═══


class IFBInvestmentItem(BaseModel):
    description: str = Field(..., description="Description of the asset")
    asset_type: str = Field(default="standard", description="Asset type: standard, eco_vehicle, eco_heating, eco_insulation, eco_other")
    acquisition_cost: float = Field(..., gt=0, description="Acquisition/production cost")
    acquisition_date: Optional[str] = Field(None, description="Acquisition date (ISO format)")


class IFBRequest(BaseModel):
    investments: List[IFBInvestmentItem] = Field(..., min_length=1, description="List of qualifying investments")
    tax_year: int = Field(default=2026, description="Tax year (IFB available from 2023)")


@router.post("/tax/calculate-ifb")
def calculate_ifb_endpoint(
    request: IFBRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    response: Response = None,
):
    """Calculate Investitionsfreibetrag (§11 EStG) for qualifying investments."""
    credit_service = CreditService(db, redis_client=None)
    try:
        deduction = credit_service.check_and_deduct(
            user_id=current_user.id,
            operation="tax_calc",
        )
    except InsufficientCreditsError as e:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient credits: {e.required} required, {e.available} available",
        )

    try:
        investments = [inv.model_dump() for inv in request.investments]
        result = calculate_ifb(investments, tax_year=request.tax_year)

        if response is not None:
            response.headers["X-Credits-Remaining"] = str(
                deduction.balance_after.available_without_overage
            )

        db.commit()

        return {
            "total_eligible_investment": float(result.total_eligible_investment),
            "total_ifb": float(result.total_ifb),
            "standard_ifb": float(result.standard_ifb),
            "eco_ifb": float(result.eco_ifb),
            "capped": result.capped,
            "note": result.note,
            "line_items": [
                {
                    "description": item.description,
                    "asset_type": item.asset_type.value if hasattr(item.asset_type, "value") else str(item.asset_type),
                    "acquisition_cost": float(item.acquisition_cost),
                    "rate": float(item.rate),
                    "ifb_amount": float(item.ifb_amount),
                    "note": item.note,
                }
                for item in result.line_items
            ],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("IFB calculation failed")
        raise HTTPException(status_code=500, detail="tax_calculation_error")


# ═══ Savings Suggestions ═══


@router.get("/tax/savings-suggestions")
def get_savings_suggestions(
    tax_year: Optional[int] = Query(None, description="Tax year"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    response: Response = None,
):
    """Generate personalized tax savings suggestions."""
    if tax_year is None:
        tax_year = datetime.now().year

    credit_service = CreditService(db, redis_client=None)
    try:
        deduction = credit_service.check_and_deduct(
            user_id=current_user.id,
            operation="tax_calc",
        )
    except InsufficientCreditsError as e:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient credits: {e.required} required, {e.available} available",
        )

    try:
        service = SavingsSuggestionService(db)
        language = getattr(current_user, "language", None) or "de"
        suggestions = service.generate_suggestions(
            user_id=current_user.id,
            tax_year=tax_year,
            language=language,
        )

        if response is not None:
            response.headers["X-Credits-Remaining"] = str(
                deduction.balance_after.available_without_overage
            )

        db.commit()
        return {"tax_year": tax_year, "suggestions": suggestions}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Savings suggestion generation failed")
        raise HTTPException(status_code=500, detail="tax_calculation_error")
