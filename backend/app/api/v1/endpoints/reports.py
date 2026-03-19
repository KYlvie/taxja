"""Report generation endpoints"""
import io
import json
import logging
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from pydantic import BaseModel
from typing import Optional

from app.db.base import get_db
from app.core.security import get_current_user
from app.api.deps import require_feature
from app.services.feature_gate_service import Feature
from app.services.credit_service import CreditService, InsufficientCreditsError
from app.models.user import User
from app.models.transaction import Transaction, TransactionType
from app.models.document import Document

logger = logging.getLogger(__name__)

router = APIRouter()


class ReportRequest(BaseModel):
    tax_year: int
    report_type: str = "pdf"
    language: str = "de"


def _deduct_report_credits(
    db: Session,
    user_id: int,
    operation: str = "e1_generation",
):
    """Deduct credits for a report-generation request or raise HTTP 402."""
    credit_service = CreditService(db, redis_client=None)
    try:
        deduction = credit_service.check_and_deduct(
            user_id=user_id,
            operation=operation,
        )
    except InsufficientCreditsError as e:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient credits: {e.required} required, {e.available} available",
        ) from e

    return deduction


def _set_credit_header(response: Response, deduction) -> None:
    """Expose remaining balance on billed responses."""
    if response is None:
        return
    response.headers["X-Credits-Remaining"] = str(
        deduction.balance_after.available_without_overage
    )


def _get_transactions_for_year(db: Session, user_id: int, tax_year: int):
    """Get all transactions for a user in a given tax year."""
    return db.query(Transaction).filter(
        Transaction.user_id == user_id,
        extract("year", Transaction.transaction_date) == tax_year
    ).order_by(Transaction.transaction_date).all()


def _build_summary(transactions):
    """Build a summary dict from transactions."""
    total_income = Decimal("0")
    total_expenses = Decimal("0")
    total_deductible = Decimal("0")
    total_vat = Decimal("0")

    for t in transactions:
        amt = t.amount or Decimal("0")
        if t.type == TransactionType.INCOME:
            total_income += amt
        else:
            total_expenses += amt
            if t.is_deductible:
                total_deductible += amt
        if t.vat_amount:
            total_vat += t.vat_amount

    return {
        "total_income": total_income,
        "total_expenses": total_expenses,
        "total_deductible": total_deductible,
        "total_vat": total_vat,
        "net_income": total_income - total_expenses,
        "transaction_count": len(transactions),
    }


@router.get("/audit-checklist")
def get_audit_checklist(
    tax_year: int = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get audit readiness checklist based on actual user data."""
    transactions = _get_transactions_for_year(db, current_user.id, tax_year)
    summary = _build_summary(transactions)

    items = []
    missing_docs = 0
    compliance_issues = 0

    # Check 1: Transaction records
    if summary["transaction_count"] > 0:
        items.append({
            "category": "transactions",
            "status": "pass",
            "message": f"{summary['transaction_count']} transactions recorded for {tax_year}",
        })
    else:
        items.append({
            "category": "transactions",
            "status": "fail",
            "message": f"No transactions found for {tax_year}",
            "details": ["Add your income and expense transactions to get started"],
        })
        compliance_issues += 1

    # Check 2: Supporting documents
    doc_count = db.query(func.count(Document.id)).filter(
        Document.user_id == current_user.id,
        extract("year", Document.uploaded_at) == tax_year,
    ).scalar() or 0

    deductible_count = sum(1 for t in transactions if t.is_deductible)
    if deductible_count > 0 and doc_count < deductible_count:
        gap = deductible_count - doc_count
        missing_docs = gap
        items.append({
            "category": "documents",
            "status": "warning",
            "message": f"{doc_count} documents uploaded, {deductible_count} deductible transactions",
            "details": [f"Consider uploading receipts for {gap} more deductible transactions"],
        })
    else:
        items.append({
            "category": "documents",
            "status": "pass",
            "message": f"{doc_count} supporting documents uploaded",
        })

    # Check 3: Deduction documentation
    undocumented = sum(1 for t in transactions if t.is_deductible and not t.document_id)
    if undocumented > 0:
        items.append({
            "category": "deductions",
            "status": "warning",
            "message": f"{undocumented} deductible transactions without linked documents",
            "details": ["Link supporting documents to deductible transactions for audit readiness"],
        })
    else:
        items.append({
            "category": "deductions",
            "status": "pass",
            "message": "All deductible transactions have supporting documents",
        })

    # Check 4: VAT
    vat_transactions = [t for t in transactions if t.vat_amount and t.vat_amount > 0]
    if summary["total_income"] > 55000:
        if vat_transactions:
            items.append({
                "category": "vat",
                "status": "pass",
                "message": f"VAT recorded on {len(vat_transactions)} transactions",
            })
        else:
            items.append({
                "category": "vat",
                "status": "warning",
                "message": "Income exceeds \u20ac55,000 threshold but no VAT recorded",
                "details": ["You may need to register for VAT (Umsatzsteuer)"],
            })
            compliance_issues += 1
    else:
        items.append({
            "category": "vat",
            "status": "pass",
            "message": "Below VAT threshold (Kleinunternehmerregelung)",
        })

    # Check 5: Data completeness
    no_category = sum(1 for t in transactions if not t.income_category and not t.expense_category)
    if no_category > 0:
        items.append({
            "category": "completeness",
            "status": "warning",
            "message": f"{no_category} transactions without category",
            "details": ["Categorize all transactions for accurate tax calculation"],
        })
    else:
        items.append({
            "category": "completeness",
            "status": "pass",
            "message": "All transactions are categorized",
        })

    # Overall status
    statuses = [item["status"] for item in items]
    if "fail" in statuses:
        overall = "not_ready"
    elif "warning" in statuses:
        overall = "needs_attention"
    else:
        overall = "ready"

    return {
        "overall_status": overall,
        "items": items,
        "missing_documents": missing_docs,
        "compliance_issues": compliance_issues,
    }



@router.post(
    "/ea-report",
    dependencies=[Depends(require_feature(Feature.ADVANCED_REPORTS))],
)
def generate_ea_report_endpoint(
    request: ReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate Einnahmen-Ausgaben-Rechnung (E/A report)."""
    from app.services.ea_report_service import generate_ea_report

    return generate_ea_report(db, current_user, request.tax_year, request.language)


@router.post(
    "/tax-form",
    dependencies=[Depends(require_feature(Feature.E1_GENERATION))],
)
def generate_tax_form_endpoint(
    request: ReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    response: Response = None,
):
    """Generate pre-filled E1/L1 tax form data."""
    from app.services.e1_form_service import generate_tax_form_data

    deduction = _deduct_report_credits(db, current_user.id)

    try:
        result = generate_tax_form_data(db, current_user, request.tax_year)
    except Exception:
        db.rollback()
        raise

    db.commit()
    _set_credit_header(response, deduction)

    return result


@router.post(
    "/tax-form-xml",
    dependencies=[Depends(require_feature(Feature.E1_GENERATION))],
)
def generate_tax_form_xml_endpoint(
    request: ReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate E1/L1/K1 tax form as FinanzOnline-compatible XML download."""
    from app.services.e1_form_service import generate_tax_form_data
    from app.services.finanzonline_xml_generator import FinanzOnlineXMLGenerator

    deduction = _deduct_report_credits(db, current_user.id)

    try:
        form_data = generate_tax_form_data(db, current_user, request.tax_year)
        generator = FinanzOnlineXMLGenerator()
        xml_string = generator.generate_from_form_data(form_data)
    except Exception:
        db.rollback()
        raise

    db.commit()

    form_type = form_data.get("form_type", "E1")
    filename = f"Taxja-{form_type}-{request.tax_year}.xml"

    streaming_response = StreamingResponse(
        io.BytesIO(xml_string.encode("utf-8")),
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
    _set_credit_header(streaming_response, deduction)
    return streaming_response


@router.post(
    "/tax-form-pdf",
    dependencies=[Depends(require_feature(Feature.E1_GENERATION))],
)
def generate_tax_form_pdf(
    request: ReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a pre-filled E1/L1 tax form as downloadable PDF.

    Strategy:
    1. If an official BMF template exists in app/templates/, fill it
    2. Otherwise, generate a replica PDF using PyMuPDF
    """
    from app.services.e1_form_service import generate_tax_form_data
    from app.services.e1_template_filler import fill_e1_from_template
    from app.services.e1_official_pdf_service import generate_official_e1_pdf

    deduction = _deduct_report_credits(db, current_user.id)

    try:
        form_data = generate_tax_form_data(db, current_user, request.tax_year)

        # Try template-based filling first
        pdf_bytes = None
        try:
            pdf_bytes = fill_e1_from_template(form_data)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(f"Template fill failed: {exc}")
            pdf_bytes = None

        if not pdf_bytes:
            # Fall back to generated replica (always works, no template dependency)
            pdf_bytes = generate_official_e1_pdf(form_data)
    except Exception:
        db.rollback()
        raise

    db.commit()

    form_type = form_data.get("form_type", "E1")
    filename = f"Taxja-{form_type}-{request.tax_year}.pdf"

    streaming_response = StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
    _set_credit_header(streaming_response, deduction)
    return streaming_response


@router.post(
    "/ea-report-pdf",
    dependencies=[Depends(require_feature(Feature.ADVANCED_REPORTS))],
)
def generate_ea_report_pdf(
    request: ReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate E/A Rechnung as downloadable PDF."""
    from app.services.ea_report_service import generate_ea_report
    from app.services.ea_pdf_service import generate_ea_pdf

    report_data = generate_ea_report(db, current_user, request.tax_year, request.language)
    pdf_bytes = generate_ea_pdf(report_data)

    filename = f"Taxja-EA-Rechnung-{request.tax_year}.pdf"

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/bilanz-report",
    dependencies=[Depends(require_feature(Feature.ADVANCED_REPORTS))],
)
def generate_bilanz_report_endpoint(
    request: ReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate Bilanz (Balance Sheet) + GuV (P&L) report."""
    from app.services.bilanz_report_service import generate_bilanz_report

    return generate_bilanz_report(db, current_user, request.tax_year, request.language)


# ═══ USt-Voranmeldung (UVA) endpoints ═══


class UVARequest(BaseModel):
    tax_year: int
    period_type: str = "quarterly"  # "monthly" or "quarterly"
    period: int = 1  # 1-12 for monthly, 1-4 for quarterly


@router.post("/uva")
def generate_uva_endpoint(
    request: UVARequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate USt-Voranmeldung (VAT advance return) data for a period."""
    from app.services.uva_service import generate_uva_data

    if request.period_type not in ("monthly", "quarterly"):
        raise HTTPException(400, "period_type must be 'monthly' or 'quarterly'")

    max_period = 12 if request.period_type == "monthly" else 4
    if request.period < 1 or request.period > max_period:
        raise HTTPException(400, f"period must be 1-{max_period} for {request.period_type}")

    return generate_uva_data(
        db, current_user, request.tax_year, request.period_type, request.period
    )


@router.post("/uva-xml")
def generate_uva_xml_endpoint(
    request: UVARequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate UVA as FinanzOnline-compatible XML download."""
    from app.services.uva_service import generate_uva_data, generate_uva_xml

    if request.period_type not in ("monthly", "quarterly"):
        raise HTTPException(400, "period_type must be 'monthly' or 'quarterly'")

    max_period = 12 if request.period_type == "monthly" else 4
    if request.period < 1 or request.period > max_period:
        raise HTTPException(400, f"period must be 1-{max_period} for {request.period_type}")

    uva_data = generate_uva_data(
        db, current_user, request.tax_year, request.period_type, request.period
    )
    xml_string = generate_uva_xml(uva_data)

    period_label = f"M{request.period:02d}" if request.period_type == "monthly" else f"Q{request.period}"
    filename = f"UVA-{request.tax_year}-{period_label}.xml"

    return StreamingResponse(
        io.BytesIO(xml_string.encode("utf-8")),
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/uva-annual")
def generate_annual_uva_endpoint(
    request: ReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate annual UVA summary (U30 Jahreserklaerung overview)."""
    from app.services.uva_service import generate_annual_uva_summary

    return generate_annual_uva_summary(db, current_user, request.tax_year)


# ═══ E1a — Sole proprietor supplement ═══

@router.post(
    "/tax-form-e1a",
    dependencies=[Depends(require_feature(Feature.E1_GENERATION))],
)
def generate_e1a_form_endpoint(
    request: ReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    response: Response = None,
):
    """Generate E1a Beilage (sole proprietor EA-Rechnung breakdown)."""
    from app.services.e1a_form_service import generate_e1a_form_data

    deduction = _deduct_report_credits(db, current_user.id)

    try:
        result = generate_e1a_form_data(db, current_user, request.tax_year)
    except Exception:
        db.rollback()
        raise

    db.commit()
    _set_credit_header(response, deduction)
    return result


# ═══ E1b — Per-property V+V supplement ═══

class E1bRequest(BaseModel):
    tax_year: int
    property_id: Optional[str] = None


@router.post(
    "/tax-form-e1b",
    dependencies=[Depends(require_feature(Feature.E1_GENERATION))],
)
def generate_e1b_form_endpoint(
    request: E1bRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    response: Response = None,
):
    """Generate E1b Beilage (per-property rental income breakdown)."""
    from app.services.e1b_form_service import generate_e1b_form_data

    deduction = _deduct_report_credits(db, current_user.id)

    try:
        result = generate_e1b_form_data(
            db, current_user, request.tax_year, request.property_id
        )
    except Exception:
        db.rollback()
        raise

    db.commit()
    _set_credit_header(response, deduction)
    return result


@router.post(
    "/tax-form-e1b-xml",
    dependencies=[Depends(require_feature(Feature.E1_GENERATION))],
)
def generate_e1b_xml_endpoint(
    request: E1bRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate E1b as FinanzOnline-compatible XML download."""
    from app.services.e1b_form_service import generate_e1b_form_data
    from app.services.finanzonline_xml_generator import FinanzOnlineXMLGenerator

    deduction = _deduct_report_credits(db, current_user.id)

    try:
        form_data = generate_e1b_form_data(
            db, current_user, request.tax_year, request.property_id
        )
        # For XML, flatten all property fields into a single form_data structure
        all_fields = []
        for prop in form_data.get("properties", []):
            for field in prop.get("fields", []):
                field["section"] = f"property_{prop['property_id']}_{field.get('section', '')}"
                all_fields.append(field)

        xml_form = {
            "form_type": "E1b",
            "tax_year": request.tax_year,
            "tax_number": form_data.get("tax_number", ""),
            "user_name": form_data.get("user_name", ""),
            "fields": all_fields,
            "summary": form_data.get("aggregate_summary", {}),
        }
        generator = FinanzOnlineXMLGenerator()
        xml_string = generator.generate_from_form_data(xml_form)
    except Exception:
        db.rollback()
        raise

    db.commit()

    filename = f"Taxja-E1b-{request.tax_year}.xml"
    streaming_response = StreamingResponse(
        io.BytesIO(xml_string.encode("utf-8")),
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
    _set_credit_header(streaming_response, deduction)
    return streaming_response


# ═══ L1k — Employee with children supplement ═══

@router.post(
    "/tax-form-l1k",
    dependencies=[Depends(require_feature(Feature.E1_GENERATION))],
)
def generate_l1k_form_endpoint(
    request: ReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    response: Response = None,
):
    """Generate L1k Beilage (employee with children — Familienbonus, Kindermehrbetrag)."""
    from app.services.l1k_form_service import generate_l1k_form_data

    deduction = _deduct_report_credits(db, current_user.id)

    try:
        result = generate_l1k_form_data(db, current_user, request.tax_year)
    except Exception:
        db.rollback()
        raise

    db.commit()
    _set_credit_header(response, deduction)
    return result


# ═══ U1 — Annual VAT return ═══

@router.post(
    "/tax-form-u1",
    dependencies=[Depends(require_feature(Feature.E1_GENERATION))],
)
def generate_u1_form_endpoint(
    request: ReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    response: Response = None,
):
    """Generate U1 Umsatzsteuererklaerung (annual VAT return)."""
    from app.services.u1_form_service import generate_u1_form_data

    deduction = _deduct_report_credits(db, current_user.id)

    try:
        result = generate_u1_form_data(db, current_user, request.tax_year)
    except Exception:
        db.rollback()
        raise

    db.commit()
    _set_credit_header(response, deduction)
    return result


@router.post(
    "/saldenliste",
    dependencies=[Depends(require_feature(Feature.ADVANCED_REPORTS))],
)
def generate_saldenliste_endpoint(
    request: ReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate Saldenliste mit Vorjahresvergleich (trial balance with prior year comparison)."""
    from app.services.saldenliste_service import generate_saldenliste

    return generate_saldenliste(db, current_user, request.tax_year, request.language)


@router.post(
    "/periodensaldenliste",
    dependencies=[Depends(require_feature(Feature.ADVANCED_REPORTS))],
)
def generate_periodensaldenliste_endpoint(
    request: ReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate Periodensaldenliste (periodic trial balance by month)."""
    from app.services.saldenliste_service import generate_periodensaldenliste

    return generate_periodensaldenliste(db, current_user, request.tax_year, request.language)


@router.post("/export-user-data")
def export_user_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export all user data as JSON (GDPR compliance).
    Returns the JSON file directly as a download."""
    from fastapi.responses import Response

    transactions = db.query(Transaction).filter(
        Transaction.user_id == current_user.id
    ).all()

    documents = db.query(Document).filter(
        Document.user_id == current_user.id
    ).all()

    export_data = {
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "name": current_user.name,
            "user_type": str(current_user.user_type.value)
            if hasattr(current_user.user_type, "value")
            else str(current_user.user_type),
            "created_at": str(current_user.created_at) if current_user.created_at else None,
        },
        "transactions": [
            {
                "id": t.id,
                "type": t.type.value if t.type else None,
                "amount": str(t.amount) if t.amount else None,
                "date": t.transaction_date.isoformat() if t.transaction_date else None,
                "description": t.description,
                "income_category": t.income_category.value if t.income_category else None,
                "expense_category": t.expense_category.value if t.expense_category else None,
                "is_deductible": t.is_deductible,
                "vat_amount": str(t.vat_amount) if t.vat_amount else None,
            }
            for t in transactions
        ],
        "documents": [
            {
                "id": d.id,
                "original_filename": d.file_name,
                "document_type": d.document_type.value
                if hasattr(d.document_type, "value")
                else str(d.document_type),
                "upload_date": str(d.uploaded_at) if d.uploaded_at else None,
                "ocr_result": d.ocr_result,
            }
            for d in documents
        ],
        "exported_at": datetime.utcnow().isoformat(),
    }

    content = json.dumps(export_data, indent=2, ensure_ascii=False)

    return Response(
        content=content,
        media_type="application/json",
        headers={
            "Content-Disposition": "attachment; filename=taxja-user-data.json",
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
# Form Eligibility — which forms does this user need?
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/eligible-forms")
async def get_eligible_forms(
    tax_year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the list of tax forms applicable to the current user.

    Returns forms filtered by user_type, family status, and properties.
    Each form includes trilingual names, descriptions, and whether a
    PDF template is available for download.
    """
    from app.services.form_eligibility_service import get_eligible_forms as _get_eligible
    from app.models.tax_form_template import TaxFormTemplate, TaxFormType

    forms = _get_eligible(current_user, db)

    # Enrich with template availability per year (gracefully handle missing table)
    if tax_year:
        try:
            available_templates = (
                db.query(TaxFormTemplate.form_type)
                .filter(TaxFormTemplate.tax_year == tax_year)
                .all()
            )
            available_set = set()
            for t in available_templates:
                val = t[0]
                # Handle both enum objects and raw strings
                if hasattr(val, "value"):
                    available_set.add(val.value)
                else:
                    available_set.add(str(val))
            for form in forms:
                form["has_template"] = form["form_type"] in available_set
                form["tax_year"] = tax_year
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("eligible-forms template check failed: %s", e)
            db.rollback()
            for form in forms:
                form["has_template"] = False
                form["tax_year"] = tax_year
    else:
        for form in forms:
            form["has_template"] = False

    return {"forms": forms, "user_type": current_user.user_type.value if hasattr(current_user.user_type, 'value') else current_user.user_type}


# ═══════════════════════════════════════════════════════════════════════════
# PDF Form Template Management + Filled PDF Download
# ═══════════════════════════════════════════════════════════════════════════

class PDFFormRequest(BaseModel):
    form_type: str  # E1, E1a, E1b, L1, L1k, K1, U1
    tax_year: int
    property_id: Optional[int] = None  # for E1b


@router.get("/tax-form-templates")
async def list_tax_form_templates(
    tax_year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List available PDF form templates."""
    from app.services.pdf_form_filler import list_available_templates
    return list_available_templates(db, tax_year)


@router.post(
    "/tax-form-pdf",
    dependencies=[Depends(require_feature(Feature.E1_GENERATION))],
)
async def download_filled_tax_form_pdf(
    request: PDFFormRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a filled PDF tax form.

    1. Computes form data via the appropriate form service
    2. Loads the blank PDF template from DB
    3. Fills AcroForm fields using the stored field_mapping
    4. Returns the filled PDF for download
    """
    from app.services.pdf_form_filler import (
        fill_tax_form_pdf, TemplateNotFoundError, PDFFillerError, PDFLibraryNotAvailable
    )

    deduction = _deduct_report_credits(db, current_user.id)

    # Check user eligibility for this form type
    from app.services.form_eligibility_service import get_eligible_form_types
    eligible = get_eligible_form_types(current_user, db)
    if request.form_type not in eligible and request.form_type.upper() not in [e.upper() for e in eligible]:
        raise HTTPException(
            status_code=403,
            detail=f"Form {request.form_type} is not applicable for your user type ({current_user.user_type.value if hasattr(current_user.user_type, 'value') else current_user.user_type})"
        )

    # Generate form data using the appropriate service
    form_data = _generate_form_data(db, current_user, request.form_type, request.tax_year, request.property_id)

    try:
        filled_pdf = fill_tax_form_pdf(db, request.form_type, request.tax_year, form_data)
    except TemplateNotFoundError:
        # No official BMF template uploaded — fallback to generated replica PDF
        logger.info(
            "No BMF template for %s %d, using generated replica",
            request.form_type, request.tax_year,
        )
        try:
            from app.services.e1_official_pdf_service import generate_official_e1_pdf
            filled_pdf = generate_official_e1_pdf(form_data)
        except Exception as fallback_err:
            logger.error("Fallback PDF generation failed: %s", fallback_err)
            raise HTTPException(
                status_code=500,
                detail=f"PDF generation failed: {fallback_err}"
            )
    except PDFLibraryNotAvailable as e:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(e))
    except PDFFillerError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    except Exception:
        db.rollback()
        raise

    filename = f"{request.form_type}_{request.tax_year}_{current_user.tax_number or 'filled'}.pdf"

    db.commit()

    streaming_response = StreamingResponse(
        io.BytesIO(filled_pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
    _set_credit_header(streaming_response, deduction)
    return streaming_response


def _generate_form_data(db: Session, user: User, form_type: str, tax_year: int, property_id=None):
    """Route to the correct form service based on form_type."""
    ft = form_type.upper()

    if ft == "E1":
        from app.services.e1_form_service import generate_tax_form_data
        return generate_tax_form_data(db, user, tax_year)
    elif ft == "E1A":
        from app.services.e1a_form_service import generate_e1a_form_data
        return generate_e1a_form_data(db, user, tax_year)
    elif ft == "E1B":
        from app.services.e1b_form_service import generate_e1b_form_data
        return generate_e1b_form_data(db, user, tax_year, property_id=property_id)
    elif ft in ("L1", "L1K"):
        from app.services.l1k_form_service import generate_l1k_form_data
        return generate_l1k_form_data(db, user, tax_year)
    elif ft == "K1":
        from app.services.e1_form_service import generate_tax_form_data
        return generate_tax_form_data(db, user, tax_year)
    elif ft == "U1":
        from app.services.u1_form_service import generate_u1_form_data
        return generate_u1_form_data(db, user, tax_year)
    elif ft == "UVA":
        from app.services.uva_service import generate_annual_uva_summary
        return generate_annual_uva_summary(db, user, tax_year)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported form type: {form_type}. "
                   f"Supported: E1, E1a, E1b, L1, L1k, K1, U1, UVA"
        )
