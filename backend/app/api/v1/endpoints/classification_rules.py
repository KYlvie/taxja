"""User classification and deductibility memory endpoints."""

from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.base import get_db
from app.models.user import User
from app.services.user_classification_service import UserClassificationService
from app.services.user_deductibility_service import UserDeductibilityService

router = APIRouter()


def _serialize_timestamp(value) -> str | None:
    if value is None:
        return None

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)

    return value.isoformat()


def _serialize_classification_rule(rule) -> dict:
    return {
        "id": rule.id,
        "normalized_description": rule.normalized_description,
        "original_description": rule.original_description,
        "txn_type": rule.txn_type,
        "category": rule.category,
        "hit_count": rule.hit_count,
        "confidence": float(rule.confidence),
        "rule_type": rule.rule_type,
        "frozen": rule.frozen,
        "conflict_count": rule.conflict_count,
        "last_hit_at": _serialize_timestamp(rule.last_hit_at),
        "created_at": _serialize_timestamp(rule.created_at),
    }


def _serialize_deductibility_rule(rule) -> dict:
    return {
        "id": rule.id,
        "normalized_description": rule.normalized_description,
        "original_description": rule.original_description,
        "expense_category": rule.expense_category,
        "is_deductible": rule.is_deductible,
        "reason": rule.reason,
        "hit_count": rule.hit_count,
        "last_hit_at": _serialize_timestamp(rule.last_hit_at),
        "created_at": _serialize_timestamp(rule.created_at),
        "updated_at": _serialize_timestamp(rule.updated_at),
    }


@router.get("/")
def list_my_rules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all classification rules for the current user."""
    svc = UserClassificationService(db)
    rules = svc.list_rules(current_user.id)
    return [_serialize_classification_rule(rule) for rule in rules]


@router.get("/deductibility")
def list_my_deductibility_rules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all deductibility override rules for the current user."""
    svc = UserDeductibilityService(db)
    rules = svc.list_rules(current_user.id)
    return [_serialize_deductibility_rule(rule) for rule in rules]


@router.delete("/{rule_id}")
def delete_my_rule(
    rule_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a specific classification rule owned by the current user."""
    svc = UserClassificationService(db)
    deleted = svc.delete_rule(current_user.id, rule_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )
    db.commit()
    return {"deleted": True, "rule_id": rule_id}


@router.delete("/deductibility/{rule_id}")
def delete_my_deductibility_rule(
    rule_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a specific deductibility override owned by the current user."""
    svc = UserDeductibilityService(db)
    deleted = svc.delete_rule(current_user.id, rule_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )
    db.commit()
    return {"deleted": True, "rule_id": rule_id}
