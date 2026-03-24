"""Loan API endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.base import get_db
from app.models.user import User
from app.schemas.loan import (
    AnnualInterestCertificateApplyRequest,
    AnnualInterestCertificateApplyResponse,
    LoanInstallmentListResponse,
    LoanInstallmentResponse,
    LoanSummaryResponse,
)
from app.services.loan_service import LoanService


router = APIRouter()


@router.get("/{loan_id}/summary", response_model=LoanSummaryResponse)
def get_loan_summary(
    loan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return an aggregate summary for one property loan."""
    service = LoanService(db)

    try:
        return service.get_loan_summary(loan_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{loan_id}/installments", response_model=LoanInstallmentListResponse)
def list_loan_installments(
    loan_id: int,
    tax_year: Optional[int] = Query(None, ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List canonical principal/interest installment rows for a loan."""
    service = LoanService(db)

    try:
        installments = service.list_installments(loan_id, current_user.id, tax_year=tax_year)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return LoanInstallmentListResponse(
        loan_id=loan_id,
        total=len(installments),
        tax_year=tax_year,
        installments=[LoanInstallmentResponse.model_validate(i) for i in installments],
    )


@router.post(
    "/{loan_id}/annual-interest-certificate",
    response_model=AnnualInterestCertificateApplyResponse,
)
def apply_annual_interest_certificate(
    loan_id: int,
    payload: AnnualInterestCertificateApplyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reconcile one tax year using a Zinsbescheinigung total."""
    service = LoanService(db)

    try:
        installments = service.apply_annual_interest_certificate(
            loan_id,
            current_user.id,
            payload.tax_year,
            payload.annual_interest_amount,
            source_document_id=payload.source_document_id,
            actual_payment_date=payload.actual_payment_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return AnnualInterestCertificateApplyResponse(
        loan_id=loan_id,
        tax_year=payload.tax_year,
        annual_interest_amount=payload.annual_interest_amount,
        installments_updated=len(installments),
        installments=[LoanInstallmentResponse.model_validate(i) for i in installments],
    )

