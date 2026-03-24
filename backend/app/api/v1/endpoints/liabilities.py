"""Liability management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.base import get_db
from app.models.recurring_transaction import RecurringTransaction
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.liability import (
    LiabilityCreate,
    LiabilityDetailResponse,
    LiabilityListResponse,
    LiabilityResponse,
    LiabilitySummaryResponse,
    LiabilityUpdate,
)
from app.services.liability_service import LiabilityService

router = APIRouter()


def _raise_liability_service_error(exc: ValueError) -> None:
    detail = str(exc)
    if detail == "Liability not found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc


@router.get("", response_model=LiabilityListResponse)
def list_liabilities(
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = LiabilityService(db)
    items = service.list_liabilities(current_user.id, include_inactive=include_inactive)
    return LiabilityListResponse(
        items=[LiabilityResponse.model_validate(item) for item in items],
        total=len(items),
        active_count=sum(1 for item in items if item.is_active),
    )


@router.get("/summary", response_model=LiabilitySummaryResponse)
def get_liability_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = LiabilityService(db)
    return LiabilitySummaryResponse(**service.get_summary(current_user.id))


@router.post("", response_model=LiabilityResponse, status_code=status.HTTP_201_CREATED)
def create_liability(
    payload: LiabilityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = LiabilityService(db)
    try:
        liability = service.create_liability(
            current_user.id,
            liability_type=payload.liability_type,
            display_name=payload.display_name,
            currency=payload.currency,
            lender_name=payload.lender_name,
            principal_amount=payload.principal_amount,
            outstanding_balance=payload.outstanding_balance,
            start_date=payload.start_date,
            interest_rate=payload.interest_rate,
            end_date=payload.end_date,
            monthly_payment=payload.monthly_payment,
            tax_relevant=payload.tax_relevant,
            tax_relevance_reason=payload.tax_relevance_reason,
            report_category=payload.report_category,
            linked_property_id=payload.linked_property_id,
            source_document_id=payload.source_document_id,
            notes=payload.notes,
            create_recurring_plan=payload.create_recurring_plan,
            recurring_day_of_month=payload.recurring_day_of_month,
        )
        return LiabilityResponse.model_validate(liability)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{liability_id}", response_model=LiabilityDetailResponse)
def get_liability(
    liability_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = LiabilityService(db)
    liability = service.get_liability(liability_id, current_user.id)
    if not liability:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Liability not found")

    related_transactions = (
        db.query(Transaction)
        .filter(Transaction.user_id == current_user.id, Transaction.liability_id == liability_id)
        .order_by(Transaction.transaction_date.desc(), Transaction.id.desc())
        .limit(20)
        .all()
    )
    related_recurring = (
        db.query(RecurringTransaction)
        .filter(RecurringTransaction.user_id == current_user.id, RecurringTransaction.liability_id == liability_id)
        .order_by(RecurringTransaction.created_at.desc(), RecurringTransaction.id.desc())
        .all()
    )

    response = LiabilityDetailResponse.model_validate(liability)
    response.related_transactions = [
        {
            "id": tx.id,
            "type": tx.type.value if hasattr(tx.type, "value") else str(tx.type),
            "amount": tx.amount,
            "transaction_date": tx.transaction_date,
            "description": tx.description,
        }
        for tx in related_transactions
    ]
    response.related_recurring_transactions = [
        {
            "id": recurring.id,
            "recurring_type": recurring.recurring_type.value if hasattr(recurring.recurring_type, "value") else str(recurring.recurring_type),
            "description": recurring.description,
            "amount": recurring.amount,
            "frequency": recurring.frequency.value if hasattr(recurring.frequency, "value") else str(recurring.frequency),
            "is_active": recurring.is_active,
            "next_generation_date": recurring.next_generation_date,
        }
        for recurring in related_recurring
    ]
    return response


@router.put("/{liability_id}", response_model=LiabilityResponse)
def update_liability(
    liability_id: int,
    payload: LiabilityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = LiabilityService(db)
    try:
        liability = service.update_liability(
            liability_id,
            current_user.id,
            payload.model_dump(exclude_unset=True),
        )
        return LiabilityResponse.model_validate(liability)
    except ValueError as exc:
        _raise_liability_service_error(exc)


@router.delete("/{liability_id}", response_model=LiabilityResponse)
def delete_liability(
    liability_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = LiabilityService(db)
    try:
        liability = service.soft_delete_liability(liability_id, current_user.id)
        return LiabilityResponse.model_validate(liability)
    except ValueError as exc:
        _raise_liability_service_error(exc)
