"""User classification rules endpoints.

Allows authenticated users to view and manage their per-user
classification override rules (description → category mappings).
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.user_classification_service import UserClassificationService

router = APIRouter()


@router.get("/")
def list_my_rules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all classification rules for the current user."""
    svc = UserClassificationService(db)
    rules = svc.list_rules(current_user.id)
    return [
        {
            "id": r.id,
            "normalized_description": r.normalized_description,
            "original_description": r.original_description,
            "txn_type": r.txn_type,
            "category": r.category,
            "hit_count": r.hit_count,
            "confidence": float(r.confidence),
            "rule_type": r.rule_type,
            "frozen": r.frozen,
            "conflict_count": r.conflict_count,
            "last_hit_at": r.last_hit_at.isoformat() if r.last_hit_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rules
    ]


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
