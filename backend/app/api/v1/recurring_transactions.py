"""API endpoints for recurring transactions"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.recurring_transaction import RecurringTransaction
from app.schemas.recurring_transaction import (
    RecurringTransactionCreate,
    RecurringTransactionUpdate,
    RecurringTransactionResponse,
    RecurringTransactionListResponse,
    RentalIncomeRecurringCreate,
    LoanInterestRecurringCreate,
    TemplateRecurringCreate,
)
from app.services.recurring_transaction_service import RecurringTransactionService

router = APIRouter()


@router.get("", response_model=RecurringTransactionListResponse)
def list_recurring_transactions(
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all recurring transactions for current user"""
    service = RecurringTransactionService(db)
    
    items = service.get_user_recurring_transactions(
        user_id=current_user.id,
        active_only=active_only
    )
    
    total = len(items)
    active_count = sum(1 for item in items if item.is_active)
    paused_count = total - active_count
    
    # Convert ORM objects to response models explicitly
    response_items = [RecurringTransactionResponse.model_validate(item) for item in items]
    
    return RecurringTransactionListResponse(
        items=response_items,
        total=total,
        active_count=active_count,
        paused_count=paused_count
    )


@router.post("/generate")
def generate_recurring_transactions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger generation of all due recurring transactions"""
    from datetime import date
    service = RecurringTransactionService(db)
    generated = service.generate_due_transactions(target_date=date.today())
    return {
        "generated_count": len(generated),
        "transactions": [
            {"id": t.id, "amount": str(t.amount), "date": str(t.date), "description": t.description}
            for t in generated
        ],
    }


@router.get("/{recurring_id}", response_model=RecurringTransactionResponse)
def get_recurring_transaction(
    recurring_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific recurring transaction"""
    recurring = db.query(RecurringTransaction).filter(
        RecurringTransaction.id == recurring_id,
        RecurringTransaction.user_id == current_user.id
    ).first()
    
    if not recurring:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recurring transaction not found"
        )
    
    return recurring


@router.post("/rental-income", response_model=RecurringTransactionResponse, status_code=status.HTTP_201_CREATED)
def create_rental_income_recurring(
    data: RentalIncomeRecurringCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a recurring transaction for rental income"""
    service = RecurringTransactionService(db)
    
    try:
        recurring = service.create_rental_income_recurring(
            user_id=current_user.id,
            property_id=data.property_id,
            monthly_rent=data.monthly_rent,
            start_date=data.start_date,
            end_date=data.end_date,
            day_of_month=data.day_of_month
        )
        return recurring
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/loan-interest", response_model=RecurringTransactionResponse, status_code=status.HTTP_201_CREATED)
def create_loan_interest_recurring(
    data: LoanInterestRecurringCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a recurring transaction for loan interest"""
    service = RecurringTransactionService(db)
    
    try:
        recurring = service.create_loan_interest_recurring(
            user_id=current_user.id,
            loan_id=data.loan_id,
            monthly_interest=data.monthly_interest,
            start_date=data.start_date,
            end_date=data.end_date,
            day_of_month=data.day_of_month
        )
        return recurring
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("", response_model=RecurringTransactionResponse, status_code=status.HTTP_201_CREATED)
def create_recurring_transaction(
    data: RecurringTransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a manual recurring transaction"""
    from datetime import date as date_type
    
    recurring = RecurringTransaction(
        user_id=current_user.id,
        recurring_type=data.recurring_type,
        property_id=data.property_id,
        loan_id=data.loan_id,
        description=data.description,
        amount=data.amount,
        transaction_type=data.transaction_type,
        category=data.category,
        frequency=data.frequency,
        start_date=data.start_date,
        end_date=data.end_date,
        day_of_month=data.day_of_month,
        notes=data.notes,
        is_active=True,
        next_generation_date=data.start_date
    )
    
    db.add(recurring)
    db.commit()
    db.refresh(recurring)
    
    return recurring


@router.put("/{recurring_id}", response_model=RecurringTransactionResponse)
def update_recurring_transaction(
    recurring_id: int,
    data: RecurringTransactionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a recurring transaction"""
    recurring = db.query(RecurringTransaction).filter(
        RecurringTransaction.id == recurring_id,
        RecurringTransaction.user_id == current_user.id
    ).first()
    
    if not recurring:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recurring transaction not found"
        )
    
    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(recurring, field, value)
    
    db.commit()
    db.refresh(recurring)
    
    return recurring


@router.post("/{recurring_id}/pause", response_model=RecurringTransactionResponse)
def pause_recurring_transaction(
    recurring_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pause a recurring transaction"""
    service = RecurringTransactionService(db)
    
    # Verify ownership
    recurring = db.query(RecurringTransaction).filter(
        RecurringTransaction.id == recurring_id,
        RecurringTransaction.user_id == current_user.id
    ).first()
    
    if not recurring:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recurring transaction not found"
        )
    
    try:
        return service.pause_recurring_transaction(recurring_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{recurring_id}/resume", response_model=RecurringTransactionResponse)
def resume_recurring_transaction(
    recurring_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resume a paused recurring transaction"""
    service = RecurringTransactionService(db)
    
    # Verify ownership
    recurring = db.query(RecurringTransaction).filter(
        RecurringTransaction.id == recurring_id,
        RecurringTransaction.user_id == current_user.id
    ).first()
    
    if not recurring:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recurring transaction not found"
        )
    
    try:
        return service.resume_recurring_transaction(recurring_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{recurring_id}/stop", response_model=RecurringTransactionResponse)
def stop_recurring_transaction(
    recurring_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stop a recurring transaction"""
    service = RecurringTransactionService(db)
    
    # Verify ownership
    recurring = db.query(RecurringTransaction).filter(
        RecurringTransaction.id == recurring_id,
        RecurringTransaction.user_id == current_user.id
    ).first()
    
    if not recurring:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recurring transaction not found"
        )
    
    try:
        return service.stop_recurring_transaction(recurring_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{recurring_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recurring_transaction(
    recurring_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a recurring transaction"""
    recurring = db.query(RecurringTransaction).filter(
        RecurringTransaction.id == recurring_id,
        RecurringTransaction.user_id == current_user.id
    ).first()
    
    if not recurring:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recurring transaction not found"
        )
    
    db.delete(recurring)
    db.commit()
    
    return None


@router.get("/property/{property_id}", response_model=List[RecurringTransactionResponse])
def get_property_recurring_transactions(
    property_id: str,
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all recurring transactions for a specific property"""
    service = RecurringTransactionService(db)
    
    # Verify property ownership
    from app.models.property import Property
    property_obj = db.query(Property).filter(
        Property.id == property_id,
        Property.user_id == current_user.id
    ).first()
    
    if not property_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    
    return service.get_property_recurring_transactions(
        property_id=property_id,
        active_only=active_only
    )



@router.get("/templates/all", response_model=List[dict])
def get_all_templates(
    current_user: User = Depends(get_current_user),
):
    """Get all available recurring transaction templates"""
    from app.services.recurring_templates import get_all_templates
    from app.schemas.recurring_transaction import RecurringTemplateResponse
    
    templates = get_all_templates()
    return [
        RecurringTemplateResponse(
            id=t.id,
            name_de=t.name_de,
            name_en=t.name_en,
            name_zh=t.name_zh,
            description_de=t.description_de,
            description_en=t.description_en,
            description_zh=t.description_zh,
            transaction_type=t.transaction_type,
            category=t.category,
            frequency=t.frequency.value,
            default_day_of_month=t.default_day_of_month,
            icon=t.icon,
            priority=t.priority
        ).model_dump()
        for t in templates
    ]


@router.post("/from-template", response_model=RecurringTransactionResponse, status_code=status.HTTP_201_CREATED)
def create_from_template(
    data: 'TemplateRecurringCreate',
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a recurring transaction from a template"""
    from app.services.recurring_templates import get_template_by_id
    from app.schemas.recurring_transaction import TemplateRecurringCreate
    from app.models.recurring_transaction import RecurringTransactionType
    
    # Get template
    template = get_template_by_id(data.template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{data.template_id}' not found"
        )
    
    # Determine recurring type based on transaction type
    if template.transaction_type == "income":
        recurring_type = RecurringTransactionType.OTHER_INCOME
    else:
        recurring_type = RecurringTransactionType.OTHER_EXPENSE
    
    # Use template day_of_month if not provided
    day_of_month = data.day_of_month if data.day_of_month else template.default_day_of_month
    
    # Create recurring transaction
    recurring = RecurringTransaction(
        user_id=current_user.id,
        recurring_type=recurring_type,
        template=template.id,
        description=template.name_de,  # Default to German name
        amount=data.amount,
        transaction_type=template.transaction_type,
        category=template.category,
        frequency=template.frequency,
        start_date=data.start_date,
        end_date=data.end_date,
        day_of_month=day_of_month,
        notes=data.notes,
        is_active=True,
        next_generation_date=data.start_date
    )
    
    db.add(recurring)
    db.commit()
    db.refresh(recurring)
    
    return recurring
