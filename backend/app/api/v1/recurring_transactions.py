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
    RecurringTransactionUpdateAndRegenerate,
    ConvertToRecurringRequest,
)
from app.services.recurring_transaction_service import RecurringTransactionService

router = APIRouter()


def _invalidate_dashboard_cache(user_id: int) -> None:
    """Best-effort dashboard cache invalidation for sync endpoints."""
    try:
        import asyncio
        from app.core.cache import cache

        async def _clear_cache() -> None:
            await cache.delete_pattern(f"dashboard:{user_id}:*")

        asyncio.run(_clear_cache())
    except Exception:
        pass


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
    
    # Convert ORM objects to response models, resolving source document IDs
    # Use direct queries to avoid relationship loading issues with encrypted fields
    import logging
    logger = logging.getLogger(__name__)
    from app.models.property import Property
    from app.models.property_loan import PropertyLoan

    # Batch-fetch property doc IDs (keep as UUID objects for proper filtering)
    property_ids = [item.property_id for item in items if item.property_id]
    prop_doc_map: dict = {}
    if property_ids:
        props = db.query(Property.id, Property.mietvertrag_document_id, Property.kaufvertrag_document_id).filter(
            Property.id.in_(property_ids)
        ).all()
        for p in props:
            prop_doc_map[str(p.id)] = p.mietvertrag_document_id or p.kaufvertrag_document_id

    # Batch-fetch loan doc IDs
    loan_ids = [item.loan_id for item in items if item.loan_id]
    loan_doc_map = {}
    if loan_ids:
        loans = db.query(PropertyLoan.id, PropertyLoan.loan_contract_document_id).filter(
            PropertyLoan.id.in_(loan_ids)
        ).all()
        for l in loans:
            loan_doc_map[l.id] = l.loan_contract_document_id

    response_items = []
    for item in items:
        resp = RecurringTransactionResponse.model_validate(item)
        # Prefer direct source_document_id; fall back to property/loan lookup for legacy records
        if item.source_document_id:
            resp.source_document_id = item.source_document_id
        elif item.property_id:
            resp.source_document_id = prop_doc_map.get(str(item.property_id))
        elif item.loan_id:
            resp.source_document_id = loan_doc_map.get(item.loan_id)
        response_items.append(resp)
    
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
    """Manually trigger generation of due recurring transactions for current user"""
    from datetime import date
    service = RecurringTransactionService(db)
    generated = service.generate_due_transactions(
        target_date=date.today(),
        user_id=current_user.id,
    )
    _invalidate_dashboard_cache(current_user.id)
    return {
        "generated_count": len(generated),
        "transactions": [
            {
                "id": t.id,
                "amount": str(t.amount),
                "date": str(t.transaction_date),
                "description": t.description,
            }
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
    from datetime import date as date_type

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
        # Set unit_percentage if provided
        if data.unit_percentage is not None:
            recurring.unit_percentage = data.unit_percentage
            db.commit()
            # Recalculate property rental percentage
            try:
                from app.services.property_service import PropertyService
                ps = PropertyService(db)
                ps.recalculate_rental_percentage(data.property_id, current_user.id)
            except Exception:
                pass
        service.generate_due_transactions(target_date=date_type.today(), user_id=current_user.id)
        db.refresh(recurring)
        _invalidate_dashboard_cache(current_user.id)
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
    from datetime import date as date_type

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
        service.generate_due_transactions(target_date=date_type.today(), user_id=current_user.id)
        db.refresh(recurring)
        _invalidate_dashboard_cache(current_user.id)
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
    
    # Auto-generate all due transactions from start_date up to today
    service = RecurringTransactionService(db)
    service.generate_due_transactions(target_date=date_type.today(), user_id=current_user.id)
    db.refresh(recurring)
    _invalidate_dashboard_cache(current_user.id)
    
    return recurring


@router.put("/{recurring_id}", response_model=RecurringTransactionResponse)
def update_recurring_transaction(
    recurring_id: int,
    data: RecurringTransactionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a recurring transaction. If end_date is set in the past, deactivate and delete future transactions."""
    import logging
    from datetime import date as date_type
    from sqlalchemy import or_
    from app.models.transaction import Transaction

    logger = logging.getLogger(__name__)

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
    
    # If end_date is in the past (or today), deactivate and clean up future transactions
    if recurring.end_date and recurring.end_date <= date_type.today():
        recurring.is_active = False
        recurring.next_generation_date = None
        # Delete system-generated transactions after the end_date
        # Match by description pattern OR parent_recurring_id
        deleted = db.query(Transaction).filter(
            Transaction.user_id == current_user.id,
            Transaction.is_system_generated == True,
            Transaction.transaction_date > recurring.end_date,
            or_(
                Transaction.source_recurring_id == recurring_id,
                Transaction.description.ilike(f"%recurring #{recurring_id}%"),
                Transaction.parent_recurring_id == recurring_id,
            ),
        ).delete(synchronize_session="fetch")
        logger.info(
            f"Updated recurring #{recurring_id}: end_date={recurring.end_date}, "
            f"is_active=False, deleted {deleted} future transactions"
        )
    
    db.commit()
    db.refresh(recurring)
    _invalidate_dashboard_cache(current_user.id)

    # Recalculate property rental_percentage when unit_percentage changes
    if "unit_percentage" in update_data and recurring.property_id:
        try:
            from app.services.property_service import PropertyService
            ps = PropertyService(db)
            ps.recalculate_rental_percentage(recurring.property_id, current_user.id)
        except Exception as e:
            logger.warning(f"Failed to recalculate rental percentage: {e}")

    return recurring


@router.put("/{recurring_id}/update-and-regenerate", response_model=RecurringTransactionResponse)
def update_and_regenerate(
    recurring_id: int,
    data: RecurringTransactionUpdateAndRegenerate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a recurring transaction template and regenerate future transactions.
    
    Changes to amount, description, category etc. will be applied to the template,
    and all system-generated transactions from apply_from date onwards will be
    deleted and regenerated with the new values.
    """
    service = RecurringTransactionService(db)

    update_fields = data.model_dump(exclude_unset=True, exclude={"apply_from"})
    if not update_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )

    try:
        recurring = service.update_and_regenerate(
            recurring_id=recurring_id,
            user_id=current_user.id,
            update_data=update_fields,
            apply_from=data.apply_from,
        )
        _invalidate_dashboard_cache(current_user.id)
        return recurring
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post("/convert-from-transaction", response_model=RecurringTransactionResponse, status_code=status.HTTP_201_CREATED)
def convert_transaction_to_recurring(
    transaction_id: int,
    data: ConvertToRecurringRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Convert a single transaction into a recurring transaction template."""
    service = RecurringTransactionService(db)

    try:
        recurring = service.convert_transaction_to_recurring(
            transaction_id=transaction_id,
            user_id=current_user.id,
            frequency=data.frequency.value,
            start_date=data.start_date,
            end_date=data.end_date,
            day_of_month=data.day_of_month,
            notes=data.notes,
        )
        # Generate past-due transactions from start_date up to today
        from datetime import date as date_type
        service.generate_due_transactions(target_date=date_type.today(), user_id=current_user.id)
        db.refresh(recurring)
        _invalidate_dashboard_cache(current_user.id)
        return recurring
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


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
        recurring = service.pause_recurring_transaction(recurring_id)
        _invalidate_dashboard_cache(current_user.id)
        return recurring
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
        recurring = service.resume_recurring_transaction(recurring_id)
        _invalidate_dashboard_cache(current_user.id)
        return recurring
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
        recurring = service.stop_recurring_transaction(recurring_id)
        _invalidate_dashboard_cache(current_user.id)
        return recurring
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
    _invalidate_dashboard_cache(current_user.id)
    
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
    from datetime import date as date_type
    service = RecurringTransactionService(db)
    service.generate_due_transactions(target_date=date_type.today(), user_id=current_user.id)
    db.refresh(recurring)
    _invalidate_dashboard_cache(current_user.id)
    
    return recurring
