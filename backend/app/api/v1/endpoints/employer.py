"""Employer-light month endpoints."""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.base import get_db
from app.models.user import User
from app.schemas.employer import (
    EmployerAnnualArchiveConfirm,
    EmployerAnnualArchiveDetectionResponse,
    EmployerAnnualArchiveResponse,
    EmployerDocumentReviewContextResponse,
    EmployerDocumentDetectionResponse,
    EmployerMonthConfirmNoPayroll,
    EmployerMonthConfirmPayroll,
    EmployerMonthResponse,
    EmployerMonthSummaryUpdate,
    EmployerOverviewResponse,
)
from app.services.employer_month_service import EmployerMonthService

router = APIRouter()


def _serialize_month(month) -> EmployerMonthResponse:
    return EmployerMonthResponse(
        id=month.id,
        year_month=month.year_month,
        status=month.status,
        source_type=month.source_type,
        payroll_signal=month.payroll_signal,
        confidence=month.confidence,
        employee_count=month.employee_count,
        gross_wages=month.gross_wages,
        net_paid=month.net_paid,
        employer_social_cost=month.employer_social_cost,
        lohnsteuer=month.lohnsteuer,
        db_amount=month.db_amount,
        dz_amount=month.dz_amount,
        kommunalsteuer=month.kommunalsteuer,
        special_payments=month.special_payments,
        notes=month.notes,
        confirmed_at=month.confirmed_at,
        last_signal_at=month.last_signal_at,
        documents=[
            {
                "document_id": link.document_id,
                "file_name": link.document.file_name,
                "document_type": (
                    link.document.document_type.value
                    if hasattr(link.document.document_type, "value")
                    else str(link.document.document_type)
                ),
                "relation_type": link.relation_type,
            }
            for link in month.document_links
            if link.document is not None
        ],
    )


def _serialize_annual_archive(archive) -> EmployerAnnualArchiveResponse:
    return EmployerAnnualArchiveResponse(
        id=archive.id,
        tax_year=archive.tax_year,
        status=archive.status,
        source_type=archive.source_type,
        archive_signal=archive.archive_signal,
        confidence=archive.confidence,
        employer_name=archive.employer_name,
        gross_income=archive.gross_income,
        withheld_tax=archive.withheld_tax,
        notes=archive.notes,
        confirmed_at=archive.confirmed_at,
        last_signal_at=archive.last_signal_at,
        documents=[
            {
                "document_id": link.document_id,
                "file_name": link.document.file_name,
                "document_type": (
                    link.document.document_type.value
                    if hasattr(link.document.document_type, "value")
                    else str(link.document.document_type)
                ),
                "relation_type": link.relation_type,
            }
            for link in archive.document_links
            if link.document is not None
        ],
    )


@router.get("/overview", response_model=EmployerOverviewResponse)
def get_employer_overview(
    year: int = Query(..., ge=2020, le=2100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return a lightweight yearly overview for employer-related months."""
    service = EmployerMonthService(db)
    return service.get_overview(current_user.id, year, current_user.employer_mode or "none")


@router.get("/months", response_model=list[EmployerMonthResponse])
def list_employer_months(
    year: int = Query(..., ge=2020, le=2100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List employer-related months for a given year."""
    service = EmployerMonthService(db)
    months = service.list_months(current_user.id, year)
    return [_serialize_month(month) for month in months]


@router.get("/annual-archives", response_model=list[EmployerAnnualArchiveResponse])
def list_employer_annual_archives(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List historical annual payroll archives for the current user."""
    service = EmployerMonthService(db)
    archives = service.list_annual_archives(current_user.id)
    return [_serialize_annual_archive(archive) for archive in archives]


@router.get(
    "/documents/{document_id}/review-context",
    response_model=EmployerDocumentReviewContextResponse,
)
def get_employer_document_review_context(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return document-level employer review context without mutating month/archive state."""
    service = EmployerMonthService(db)

    try:
        context = service.get_document_review_context(current_user, document_id)
        return EmployerDocumentReviewContextResponse(
            supported=context["supported"],
            reason=context.get("reason"),
            document_id=context["document_id"],
            document_type=context["document_type"],
            candidate_year_month=context.get("candidate_year_month"),
            candidate_tax_year=context.get("candidate_tax_year"),
            month=_serialize_month(context["month"]) if context.get("month") is not None else None,
            annual_archive=(
                _serialize_annual_archive(context["annual_archive"])
                if context.get("annual_archive") is not None
                else None
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/documents/{document_id}/detect", response_model=EmployerDocumentDetectionResponse)
def detect_employer_month_from_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or update a payroll month signal from a processed document."""
    service = EmployerMonthService(db)

    try:
        detected, month, reason = service.detect_from_document(current_user, document_id)
        if month is not None:
            db.commit()
            db.refresh(month)
        return EmployerDocumentDetectionResponse(
            detected=detected,
            reason=reason,
            month=_serialize_month(month) if month is not None else None,
        )
    except ValueError as exc:
        db.rollback()
        status_code = status.HTTP_404_NOT_FOUND if str(exc) == "Document not found" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post(
    "/documents/{document_id}/detect-annual-archive",
    response_model=EmployerAnnualArchiveDetectionResponse,
)
def detect_employer_annual_archive_from_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or update a historical annual payroll archive signal from a processed document."""
    service = EmployerMonthService(db)

    try:
        detected, archive, reason = service.detect_annual_archive_from_document(current_user, document_id)
        if archive is not None:
            db.commit()
            db.refresh(archive)
        return EmployerAnnualArchiveDetectionResponse(
            detected=detected,
            reason=reason,
            archive=_serialize_annual_archive(archive) if archive is not None else None,
        )
    except ValueError as exc:
        db.rollback()
        status_code = status.HTTP_404_NOT_FOUND if str(exc) == "Document not found" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post("/months/confirm-payroll", response_model=EmployerMonthResponse)
def confirm_employer_month_payroll(
    payload: EmployerMonthConfirmPayroll,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a month as payroll-relevant and optionally attach a supporting document."""
    service = EmployerMonthService(db)
    summary = payload.model_dump(
        include={
            "employee_count",
            "gross_wages",
            "net_paid",
            "employer_social_cost",
            "lohnsteuer",
            "db_amount",
            "dz_amount",
            "kommunalsteuer",
            "special_payments",
            "notes",
        },
        exclude_none=True,
    )

    try:
        month = service.mark_payroll_detected(
            current_user.id,
            payload.year_month,
            document_id=payload.document_id,
            source_type=payload.source_type,
            payroll_signal=payload.payroll_signal,
            confidence=payload.confidence,
            summary=summary,
        )
        db.commit()
        db.refresh(month)
        return _serialize_month(month)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/annual-archives/confirm", response_model=EmployerAnnualArchiveResponse)
def confirm_employer_annual_archive(
    payload: EmployerAnnualArchiveConfirm,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Confirm a historical payroll year archive without rebuilding monthly payroll data."""
    service = EmployerMonthService(db)
    summary = payload.model_dump(
        include={"employer_name", "gross_income", "withheld_tax", "notes"},
        exclude_none=True,
    )

    try:
        archive = service.confirm_annual_archive(
            current_user.id,
            payload.tax_year,
            document_id=payload.document_id,
            archive_signal=payload.archive_signal,
            source_type=payload.source_type,
            confidence=payload.confidence,
            summary=summary,
        )
        db.commit()
        db.refresh(archive)
        return _serialize_annual_archive(archive)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/months/confirm-no-payroll", response_model=EmployerMonthResponse)
def confirm_employer_month_no_payroll(
    payload: EmployerMonthConfirmNoPayroll,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Confirm that a month has no payroll despite reminders or prior hints."""
    service = EmployerMonthService(db)
    month = service.confirm_no_payroll(current_user.id, payload.year_month, payload.note)
    db.commit()
    db.refresh(month)
    return _serialize_month(month)


@router.post("/months/mark-missing-confirmation", response_model=EmployerMonthResponse)
def mark_employer_month_missing_confirmation(
    payload: EmployerMonthConfirmPayroll,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a month as needing confirmation, typically after AI/document detection."""
    service = EmployerMonthService(db)

    try:
        month = service.mark_missing_confirmation(
            current_user.id,
            payload.year_month,
            payroll_signal=payload.payroll_signal,
            document_id=payload.document_id,
            source_type=payload.source_type,
            confidence=payload.confidence,
        )
        db.commit()
        db.refresh(month)
        return _serialize_month(month)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put("/months/{year_month}", response_model=EmployerMonthResponse)
def update_employer_month_summary(
    year_month: str,
    payload: EmployerMonthSummaryUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update lightweight monthly payroll summary fields."""
    service = EmployerMonthService(db)
    try:
        month = service.update_summary(
            current_user.id,
            year_month,
            payload.model_dump(exclude_none=True),
        )
        db.commit()
        db.refresh(month)
        return _serialize_month(month)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
