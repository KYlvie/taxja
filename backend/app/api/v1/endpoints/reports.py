"""Report generation endpoints"""
import io
import json
import logging
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from pydantic import BaseModel
from typing import Optional

from app.db.base import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.transaction import Transaction, TransactionType
from app.models.document import Document

logger = logging.getLogger(__name__)

router = APIRouter()


class ReportRequest(BaseModel):
    tax_year: int
    report_type: str = "pdf"
    language: str = "de"


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



@router.post("/ea-report")
def generate_ea_report_endpoint(
    request: ReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate Einnahmen-Ausgaben-Rechnung (E/A report)."""
    from app.services.ea_report_service import generate_ea_report

    return generate_ea_report(db, current_user, request.tax_year, request.language)


@router.post("/tax-form")
def generate_tax_form_endpoint(
    request: ReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate pre-filled E1/L1 tax form data."""
    from app.services.e1_form_service import generate_tax_form_data

    return generate_tax_form_data(db, current_user, request.tax_year)


@router.post("/tax-form-pdf")
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

    form_type = form_data.get("form_type", "E1")
    filename = f"Taxja-{form_type}-{request.tax_year}.pdf"

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/ea-report-pdf")
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


@router.post("/bilanz-report")
def generate_bilanz_report_endpoint(
    request: ReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate Bilanz (Balance Sheet) + GuV (P&L) report."""
    from app.services.bilanz_report_service import generate_bilanz_report

    return generate_bilanz_report(db, current_user, request.tax_year, request.language)


@router.post("/saldenliste")
def generate_saldenliste_endpoint(
    request: ReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate Saldenliste mit Vorjahresvergleich (trial balance with prior year comparison)."""
    from app.services.saldenliste_service import generate_saldenliste

    return generate_saldenliste(db, current_user, request.tax_year, request.language)


@router.post("/periodensaldenliste")
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
