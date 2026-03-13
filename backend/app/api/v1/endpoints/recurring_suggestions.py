"""API endpoints for recurring transaction suggestions"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.dismissed_suggestion import DismissedSuggestion
from app.services.recurring_pattern_detector import RecurringPatternDetector, RecurringPattern
from app.services.recurring_transaction_service import RecurringTransactionService

router = APIRouter()


class RecurringPatternResponse(BaseModel):
    """Response schema for detected pattern"""
    description: str
    amount: float
    transaction_type: str
    category: str
    frequency: str
    occurrences: int
    confidence: float
    suggested_day_of_month: int
    property_id: str | None = None
    already_automated: bool = False


class AcceptSuggestionRequest(BaseModel):
    """Request to accept a recurring suggestion"""
    description: str
    amount: float
    transaction_type: str
    category: str
    frequency: str
    suggested_day_of_month: int
    property_id: str | None = None


@router.get("/suggestions", response_model=List[RecurringPatternResponse])
def get_recurring_suggestions(
    lookback_months: int = 6,
    min_confidence: float = 0.7,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get intelligent suggestions for recurring transactions based on user's history.
    
    The system analyzes transaction patterns and suggests automation.
    Dismissed suggestions are filtered out.
    """
    detector = RecurringPatternDetector(db)
    
    # Detect patterns
    patterns = detector.detect_patterns(
        user_id=current_user.id,
        lookback_months=lookback_months,
        min_confidence=min_confidence
    )
    
    # Load dismissed suggestions for this user
    dismissed = (
        db.query(DismissedSuggestion)
        .filter(DismissedSuggestion.user_id == current_user.id)
        .all()
    )
    dismissed_keys = {(d.description, d.amount, d.category) for d in dismissed}
    
    # Convert to response format, filter dismissed, check if already automated
    suggestions = []
    for pattern in patterns:
        key = (pattern.description, float(pattern.amount), pattern.category)
        if key in dismissed_keys:
            continue
        
        already_automated = detector.check_if_already_automated(
            user_id=current_user.id,
            pattern=pattern
        )
        
        suggestions.append(RecurringPatternResponse(
            description=pattern.description,
            amount=float(pattern.amount),
            transaction_type=pattern.transaction_type,
            category=pattern.category,
            frequency=pattern.frequency.value,
            occurrences=pattern.occurrences,
            confidence=pattern.confidence,
            suggested_day_of_month=pattern.suggested_day_of_month,
            property_id=pattern.property_id,
            already_automated=already_automated
        ))
    
    return suggestions


@router.post("/suggestions/accept", status_code=status.HTTP_201_CREATED)
def accept_suggestion(
    data: AcceptSuggestionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Accept a recurring transaction suggestion and create automation.
    """
    from app.models.recurring_transaction import (
        RecurringTransaction,
        RecurrenceFrequency,
        RecurringTransactionType
    )
    from datetime import date
    from decimal import Decimal
    
    # Determine recurring type
    if data.property_id and data.category == "rental":
        recurring_type = RecurringTransactionType.RENTAL_INCOME
    elif data.category == "loan_interest":
        recurring_type = RecurringTransactionType.LOAN_INTEREST
    elif data.transaction_type == "income":
        recurring_type = RecurringTransactionType.OTHER_INCOME
    else:
        recurring_type = RecurringTransactionType.OTHER_EXPENSE
    
    # Create recurring transaction
    recurring = RecurringTransaction(
        user_id=current_user.id,
        recurring_type=recurring_type,
        property_id=data.property_id,
        description=data.description,
        amount=Decimal(str(data.amount)),
        transaction_type=data.transaction_type,
        category=data.category,
        frequency=RecurrenceFrequency(data.frequency),
        start_date=date.today(),
        day_of_month=data.suggested_day_of_month,
        is_active=True,
        next_generation_date=date.today(),
        notes="Auto-created from pattern detection"
    )
    
    db.add(recurring)
    db.commit()
    db.refresh(recurring)
    
    return {
        "message": "Recurring transaction created successfully",
        "recurring_id": recurring.id
    }


class DismissSuggestionRequest(BaseModel):
    """Request to dismiss a recurring suggestion"""
    description: str
    amount: float
    category: str


@router.post("/suggestions/dismiss", status_code=status.HTTP_204_NO_CONTENT)
def dismiss_suggestion(
    data: DismissSuggestionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Dismiss a recurring transaction suggestion so it won't be shown again.
    """
    dismissed = DismissedSuggestion(
        user_id=current_user.id,
        description=data.description,
        amount=data.amount,
        category=data.category,
    )
    db.add(dismissed)
    db.commit()
    return None
