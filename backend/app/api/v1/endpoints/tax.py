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
        estimate = calculator.estimate_refund_potential(current_user, tax_year, Decimal(str(estimated_gross_income)))
        return estimate
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tax/simulate")
def simulate_tax_scenario(
    scenario: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Simulate tax impact of adding/removing income or expenses.

    Accepts: {changeType, amount, description, category?, tax_year?}
    Returns: current vs simulated tax comparison.
    """
    tax_year = scenario.get("tax_year", datetime.now().year)
    change_type = scenario.get("changeType", scenario.get("type", "add_expense"))
    change_amount = Decimal(str(scenario.get("amount", 0)))
    description = scenario.get("description", "")

    # Check if GmbH user
    user_type = current_user.user_type.value if hasattr(current_user.user_type, "value") else str(current_user.user_type)
    is_gmbh = user_type == "gmbh"

    # Fetch current transactions
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
    current_deductible = sum(
        t.amount for t in transactions
        if t.type == TransactionType.EXPENSE and t.is_deductible
    ) or Decimal("0")

    current_net = current_income - current_expenses

    if is_gmbh:
        from app.services.koest_calculator import KoEstCalculator
        koest_calc = KoEstCalculator()
        current_tax = koest_calc.calculate(profit=current_net).effective_koest
    else:
        current_taxable = max(Decimal("0"), current_net - EXEMPTION)
        current_tax = _calc_progressive_tax(current_taxable)

    # Apply scenario
    sim_income = current_income
    sim_expenses = current_expenses
    sim_deductible = current_deductible

    if change_type == "add_income":
        sim_income += change_amount
    elif change_type == "add_expense":
        sim_expenses += change_amount
        sim_deductible += change_amount  # assume deductible
    elif change_type == "remove_expense":
        sim_expenses = max(Decimal("0"), sim_expenses - change_amount)
        sim_deductible = max(Decimal("0"), sim_deductible - change_amount)

    sim_net = sim_income - sim_expenses
    if is_gmbh:
        sim_tax = koest_calc.calculate(profit=sim_net).effective_koest
    else:
        sim_taxable = max(Decimal("0"), sim_net - EXEMPTION)
        sim_tax = _calc_progressive_tax(sim_taxable)

    tax_diff = float(sim_tax - current_tax)
    current_net_income = float(current_income - current_tax)
    sim_net_income = float(sim_income - sim_tax)

    # Build explanation
    if change_type == "add_expense":
        explanation = (
            f"Adding a deductible expense of \u20ac{float(change_amount):,.2f} "
            f"reduces your taxable income, saving you \u20ac{abs(tax_diff):,.2f} in taxes."
            if tax_diff < 0
            else f"This expense does not change your tax liability (income below exemption threshold)."
        )
    elif change_type == "add_income":
        explanation = (
            f"Adding \u20ac{float(change_amount):,.2f} in income increases your tax by \u20ac{tax_diff:,.2f}."
        )
    else:
        explanation = (
            f"Removing \u20ac{float(change_amount):,.2f} in expenses increases your taxable income by that amount."
        )

    return {
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


@router.get("/tax/flat-rate-compare")
def compare_flat_rate_tax(
    tax_year: Optional[int] = Query(None, description="Tax year"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Compare actual accounting vs flat-rate (Pauschalierung) tax system.

    Austrian flat-rate: 12% of gross turnover (max ?220,000 turnover, max ?26,400 deduction).
    Only for self-employed / small business with turnover ? ?220,000.
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
    actual_expenses = sum(
        t.amount for t in transactions
        if t.type == TransactionType.EXPENSE and t.is_deductible
    ) or Decimal("0")

    # Eligibility check
    max_turnover = Decimal("220000")
    is_eligible = gross_income <= max_turnover
    user_type = current_user.user_type.value if hasattr(current_user.user_type, "value") else str(current_user.user_type)
    if user_type == "employee":
        is_eligible = False
        reason = "Flat-rate taxation is not available for employees (Arbeitnehmer)."
    elif user_type == "gmbh":
        is_eligible = False
        reason = "Flat-rate taxation (Pauschalierung) is not available for GmbH. GmbH must use Bilanzierung."
    elif not is_eligible:
        reason = f"Turnover \u20ac{float(gross_income):,.2f} exceeds the \u20ac220,000 limit."
    else:
        reason = "You are eligible for flat-rate taxation (Basispauschalierung)."

    # --- Actual accounting method ---
    actual_taxable = max(Decimal("0"), gross_income - actual_expenses - EXEMPTION)
    actual_tax = _calc_progressive_tax(actual_taxable)
    actual_net = gross_income - actual_tax

    # --- Flat-rate method ---
    flat_rate_pct = Decimal("0.12")
    flat_rate_deduction = min(gross_income * flat_rate_pct, Decimal("26400"))
    flat_taxable = max(Decimal("0"), gross_income - flat_rate_deduction - EXEMPTION)
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
            "flatRateDeduction": float(flat_rate_deduction),
            "flatRatePercentage": 12,
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
        "explanation": (
            f"With actual accounting, your tax is \u20ac{float(actual_tax):,.2f}. "
            f"With flat-rate (12%), your tax would be \u20ac{float(flat_tax):,.2f}. "
            + (f"You could save \u20ac{abs(savings):,.2f} with {'flat-rate' if savings > 0 else 'actual accounting'}."
               if is_eligible else "Flat-rate is not available for your situation.")
        ),
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
