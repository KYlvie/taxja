"""Transaction CRUD endpoints"""
from typing import Optional
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.db.base import get_db
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.models.user import User
from app.schemas.transaction import (
    TransactionCreate,
    TransactionUpdate,
    TransactionResponse,
    TransactionListResponse
)
from app.core.security import get_current_user
from app.services.transaction_classifier import TransactionClassifier
from app.services.deductibility_checker import DeductibilityChecker
import math

router = APIRouter()


def format_validation_error(exc: ValidationError) -> dict:
    """Format Pydantic validation errors into user-friendly messages"""
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])
        message = error["msg"]
        error_type = error["type"]
        
        # Customize error messages
        if error_type == "missing":
            errors.append(f"Field '{field}' is required but was not provided")
        elif error_type == "value_error":
            errors.append(f"Invalid value for '{field}': {message}")
        elif error_type == "type_error":
            errors.append(f"Invalid type for '{field}': {message}")
        else:
            errors.append(f"Validation error for '{field}': {message}")
    
    return {
        "detail": "Validation failed",
        "errors": errors
    }


@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    transaction_data: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new transaction record with automatic classification.
    
    **Required fields:**
    - **type**: Transaction type (income or expense)
    - **amount**: Transaction amount (must be positive, max 2 decimal places)
    - **transaction_date**: Date of the transaction (cannot be in the future)
    - **description**: Transaction description (cannot be empty)
    
    **Optional fields (auto-classified if not provided):**
    - **income_category**: Income category (auto-classified if not provided)
    - **expense_category**: Expense category (auto-classified if not provided)
    - **is_deductible**: Whether the expense is tax deductible (auto-determined if not provided)
    - **deduction_reason**: Reason for deductibility (auto-generated if not provided)
    - **vat_rate**: VAT rate if applicable (0.0 to 1.0)
    - **vat_amount**: VAT amount if applicable
    - **document_id**: Associated document ID if available
    
    **Auto-classification:**
    - If category is not provided, the system will automatically classify the transaction
    - Classification uses a hybrid approach (rule-based + ML)
    - Low-confidence classifications are marked for review
    - Deductibility is automatically determined based on user type and category
    
    **Validation rules:**
    1. Amount must be positive
    2. Date cannot be in the future
    3. Description cannot be empty
    """
    
    # Initialize classifiers
    classifier = TransactionClassifier(db=db)
    deductibility_checker = DeductibilityChecker()
    
    # Create a temporary transaction object for classification
    temp_transaction = Transaction(
        type=transaction_data.type,
        amount=transaction_data.amount,
        transaction_date=transaction_data.transaction_date,
        description=transaction_data.description
    )
    
    # Auto-classify if category not provided
    classification_confidence = None
    needs_review = False
    
    if transaction_data.type == TransactionType.INCOME:
        if not transaction_data.income_category:
            # Auto-classify income
            result = classifier.classify_transaction(temp_transaction)
            if result.category:
                try:
                    transaction_data.income_category = IncomeCategory(result.category)
                    classification_confidence = result.confidence
                    needs_review = result.confidence < Decimal('0.7')
                except ValueError:
                    # Invalid category from classifier, use default
                    transaction_data.income_category = IncomeCategory.EMPLOYMENT
                    needs_review = True
            else:
                # No classification, use default
                transaction_data.income_category = IncomeCategory.EMPLOYMENT
                needs_review = True
    else:
        if not transaction_data.expense_category:
            # Auto-classify expense
            result = classifier.classify_transaction(temp_transaction)
            if result.category:
                try:
                    transaction_data.expense_category = ExpenseCategory(result.category)
                    classification_confidence = result.confidence
                    needs_review = result.confidence < Decimal('0.7')
                except ValueError:
                    # Invalid category from classifier, use default
                    transaction_data.expense_category = ExpenseCategory.OTHER
                    needs_review = True
            else:
                # No classification, use default
                transaction_data.expense_category = ExpenseCategory.OTHER
                needs_review = True
    
    # Auto-determine deductibility if not provided
    if transaction_data.type == TransactionType.EXPENSE:
        if transaction_data.is_deductible is None:
            # Check deductibility
            category = transaction_data.expense_category.value
            user_type = current_user.user_type.value
            
            deductibility_result = deductibility_checker.check(category, user_type)
            transaction_data.is_deductible = deductibility_result.is_deductible
            
            if not transaction_data.deduction_reason:
                transaction_data.deduction_reason = deductibility_result.reason
            
            # Mark for review if deductibility requires review
            if deductibility_result.requires_review:
                needs_review = True
    
    # Create transaction
    db_transaction = Transaction(
        user_id=current_user.id,
        type=transaction_data.type,
        amount=transaction_data.amount,
        transaction_date=transaction_data.transaction_date,
        description=transaction_data.description,
        income_category=transaction_data.income_category,
        expense_category=transaction_data.expense_category,
        is_deductible=transaction_data.is_deductible or False,
        deduction_reason=transaction_data.deduction_reason,
        vat_rate=transaction_data.vat_rate,
        vat_amount=transaction_data.vat_amount,
        document_id=transaction_data.document_id,
        property_id=transaction_data.property_id,
        classification_confidence=classification_confidence,
        needs_review=needs_review,
        import_source="manual",
        # Recurring fields
        is_recurring=transaction_data.is_recurring,
        recurring_frequency=transaction_data.recurring_frequency,
        recurring_start_date=transaction_data.recurring_start_date,
        recurring_end_date=transaction_data.recurring_end_date,
        recurring_day_of_month=transaction_data.recurring_day_of_month,
        recurring_is_active=True if transaction_data.is_recurring else False,
        recurring_next_date=transaction_data.recurring_start_date if transaction_data.is_recurring else None,
    )
    
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    
    return db_transaction


@router.get("", response_model=TransactionListResponse)
def get_transactions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    # Pagination
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    # Filters
    type: Optional[TransactionType] = Query(None, description="Filter by transaction type"),
    income_category: Optional[IncomeCategory] = Query(None, description="Filter by income category"),
    expense_category: Optional[ExpenseCategory] = Query(None, description="Filter by expense category"),
    is_deductible: Optional[bool] = Query(None, description="Filter by deductibility"),
    is_recurring: Optional[bool] = Query(None, description="Filter by recurring status"),
    date_from: Optional[date] = Query(None, description="Filter transactions from this date"),
    date_to: Optional[date] = Query(None, description="Filter transactions until this date"),
    min_amount: Optional[Decimal] = Query(None, ge=0, description="Minimum transaction amount"),
    max_amount: Optional[Decimal] = Query(None, ge=0, description="Maximum transaction amount"),
    search: Optional[str] = Query(None, max_length=100, description="Search in description"),
    tax_year: Optional[int] = Query(None, ge=1900, le=2100, description="Filter by tax year (e.g., 2026)"),
    # Sorting
    sort_by: str = Query("transaction_date", description="Sort by field (transaction_date, amount, created_at)"),
    sort_order: str = Query("desc", description="Sort order (asc or desc)")
):
    """
    Get all transactions for the current user with filtering and pagination.
    
    **Filters:**
    - **type**: Filter by transaction type (income/expense)
    - **income_category**: Filter by income category
    - **expense_category**: Filter by expense category
    - **is_deductible**: Filter by deductibility status
    - **date_from**: Start date for date range filter
    - **date_to**: End date for date range filter
    - **min_amount**: Minimum transaction amount
    - **max_amount**: Maximum transaction amount
    - **search**: Search text in description
    - **tax_year**: Filter by tax year (e.g., 2026) - isolates data to specific year boundaries
    
    **Pagination:**
    - **page**: Page number (default: 1)
    - **page_size**: Items per page (default: 50, max: 100)
    
    **Sorting:**
    - **sort_by**: Field to sort by (transaction_date, amount, created_at)
    - **sort_order**: Sort order (asc or desc)
    
    **Multi-Year Data Isolation:**
    When tax_year is specified, only transactions within that calendar year are returned.
    This ensures proper year boundary isolation for tax calculations and reporting.
    """
    
    # Build query
    query = db.query(Transaction).filter(Transaction.user_id == current_user.id)
    
    # Apply filters
    if type:
        query = query.filter(Transaction.type == type)
    
    if income_category:
        query = query.filter(Transaction.income_category == income_category)
    
    if expense_category:
        query = query.filter(Transaction.expense_category == expense_category)
    
    if is_deductible is not None:
        query = query.filter(Transaction.is_deductible == is_deductible)
    
    if is_recurring is not None:
        query = query.filter(Transaction.is_recurring == is_recurring)
    
    if date_from:
        query = query.filter(Transaction.transaction_date >= date_from)
    
    if date_to:
        query = query.filter(Transaction.transaction_date <= date_to)
    
    if min_amount is not None:
        query = query.filter(Transaction.amount >= min_amount)
    
    if max_amount is not None:
        query = query.filter(Transaction.amount <= max_amount)
    
    if search:
        query = query.filter(Transaction.description.ilike(f"%{search}%"))
    
    # Multi-year data isolation: Filter by tax year if specified
    if tax_year is not None:
        # Tax year boundaries: January 1 to December 31 of the specified year
        year_start = date(tax_year, 1, 1)
        year_end = date(tax_year, 12, 31)
        query = query.filter(
            Transaction.transaction_date >= year_start,
            Transaction.transaction_date <= year_end
        )
    
    # Get total count before pagination
    total = query.count()
    
    # Apply sorting
    sort_field = getattr(Transaction, sort_by, Transaction.transaction_date)
    if sort_order.lower() == "asc":
        query = query.order_by(sort_field.asc())
    else:
        query = query.order_by(sort_field.desc())
    
    # Apply pagination
    offset = (page - 1) * page_size
    transactions = query.offset(offset).limit(page_size).all()
    
    # Calculate total pages
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    
    return TransactionListResponse(
        total=total,
        transactions=transactions,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.post("/import")
async def import_transactions_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Import transactions from a CSV file.

    Expected CSV columns: date, type, amount, description, category
    """
    import csv
    import io

    content = await file.read()
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    imported = []
    errors_list = []
    duplicates = 0
    row_num = 0

    classifier = TransactionClassifier(db=db)
    deductibility_checker = DeductibilityChecker()

    for row in reader:
        row_num += 1
        try:
            txn_type_str = (row.get("type") or "expense").strip().lower()
            txn_type = TransactionType.INCOME if txn_type_str == "income" else TransactionType.EXPENSE

            amount_str = (row.get("amount") or "0").strip().replace(",", ".")
            amount = Decimal(amount_str).quantize(Decimal("0.01"))
            if amount <= 0:
                errors_list.append({"row": row_num, "error": "Amount must be positive"})
                continue

            date_str = (row.get("date") or "").strip()
            try:
                txn_date = date.fromisoformat(date_str)
            except ValueError:
                errors_list.append({"row": row_num, "error": f"Invalid date: {date_str}"})
                continue

            description = (row.get("description") or "").strip()
            if not description:
                errors_list.append({"row": row_num, "error": "Description is required"})
                continue

            category_str = (row.get("category") or "").strip()

            # Auto-classify if no category
            income_cat = None
            expense_cat = None
            is_deductible = False
            confidence = None

            if category_str:
                if txn_type == TransactionType.INCOME:
                    try:
                        income_cat = IncomeCategory(category_str)
                    except ValueError:
                        income_cat = None
                else:
                    try:
                        expense_cat = ExpenseCategory(category_str)
                    except ValueError:
                        expense_cat = None

            if not income_cat and not expense_cat:
                temp = Transaction(
                    type=txn_type, amount=amount,
                    transaction_date=txn_date, description=description,
                )
                result = classifier.classify_transaction(temp, current_user)
                if result and result.category:
                    if txn_type == TransactionType.INCOME:
                        try:
                            income_cat = IncomeCategory(result.category)
                        except ValueError:
                            pass
                    else:
                        try:
                            expense_cat = ExpenseCategory(result.category)
                        except ValueError:
                            pass
                    confidence = result.confidence

            cat_value = (income_cat.value if income_cat else expense_cat.value if expense_cat else None)
            if cat_value:
                user_type = current_user.user_type.value if hasattr(current_user.user_type, "value") else str(current_user.user_type)
                deduct = deductibility_checker.check(cat_value, user_type)
                is_deductible = deduct.is_deductible

            transaction = Transaction(
                user_id=current_user.id,
                type=txn_type,
                amount=amount,
                transaction_date=txn_date,
                description=description,
                income_category=income_cat,
                expense_category=expense_cat,
                is_deductible=is_deductible,
                classification_confidence=Decimal(str(confidence)) if confidence else None,
                import_source="csv",
            )
            db.add(transaction)
            db.flush()
            imported.append({
                "id": transaction.id,
                "type": txn_type.value,
                "amount": float(amount),
                "date": txn_date.isoformat(),
                "description": description,
                "category": cat_value or "other",
                "is_deductible": is_deductible,
            })
        except Exception as e:
            errors_list.append({"row": row_num, "error": str(e)})

    db.commit()

    return {
        "success": len(imported),
        "failed": len(errors_list),
        "duplicates": duplicates,
        "transactions": imported,
        "errors": errors_list,
    }


@router.get("/export")
def export_transactions_csv(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    type: Optional[TransactionType] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export transactions as CSV."""
    import csv
    import io

    query = db.query(Transaction).filter(Transaction.user_id == current_user.id)
    if start_date:
        query = query.filter(Transaction.transaction_date >= start_date)
    if end_date:
        query = query.filter(Transaction.transaction_date <= end_date)
    if type:
        query = query.filter(Transaction.type == type)

    transactions = query.order_by(Transaction.transaction_date.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "type", "amount", "description", "category", "is_deductible"])

    for t in transactions:
        cat = (
            t.income_category.value if t.income_category
            else t.expense_category.value if t.expense_category
            else "other"
        )
        writer.writerow([
            t.transaction_date.isoformat(),
            t.type.value,
            str(t.amount),
            t.description,
            cat,
            str(t.is_deductible),
        ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=transactions.csv"},
    )


# --- Routes with path parameters MUST come after /import and /export ---

@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific transaction by ID."""
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == current_user.id
    ).first()
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction with id {transaction_id} not found"
        )
    return transaction


@router.put("/{transaction_id}", response_model=TransactionResponse)
def update_transaction(
    transaction_id: int,
    transaction_data: TransactionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an existing transaction. Only provided fields will be updated."""
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == current_user.id
    ).first()
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction with id {transaction_id} not found"
        )

    update_data = transaction_data.model_dump(exclude_unset=True)
    new_type = update_data.get('type', transaction.type)

    if new_type == TransactionType.INCOME:
        new_income_category = update_data.get('income_category', transaction.income_category)
        if not new_income_category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "income_category is required for income transactions",
                    "valid_categories": [c.value for c in IncomeCategory]
                }
            )
        if 'expense_category' not in update_data:
            update_data['expense_category'] = None
    elif new_type == TransactionType.EXPENSE:
        new_expense_category = update_data.get('expense_category', transaction.expense_category)
        if not new_expense_category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "expense_category is required for expense transactions",
                    "valid_categories": [c.value for c in ExpenseCategory]
                }
            )
        if 'income_category' not in update_data:
            update_data['income_category'] = None

    for field, value in update_data.items():
        setattr(transaction, field, value)

    db.commit()
    db.refresh(transaction)
    return transaction


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a transaction."""
    from app.models.document import Document

    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == current_user.id
    ).first()
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction with id {transaction_id} not found"
        )

    # Clear document references to this transaction to avoid FK violation
    docs = db.query(Document).filter(Document.transaction_id == transaction_id).all()
    for doc in docs:
        doc.transaction_id = None

    # Clear transaction's own document_id reference
    transaction.document_id = None
    db.flush()

    db.delete(transaction)
    db.commit()
    return None



def reclassify_transactions(
    tax_year: Optional[int] = Query(None, description="Tax year to reclassify (default: all)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Re-run classification and deductibility checks on existing transactions.

    Useful after classifier or deductibility rules have been updated.
    Processes both income and expense transactions.
    """
    classifier = TransactionClassifier(db=db)
    deductibility_checker = DeductibilityChecker()

    query = db.query(Transaction).filter(
        Transaction.user_id == current_user.id,
    )
    if tax_year:
        from sqlalchemy import extract
        query = query.filter(extract("year", Transaction.transaction_date) == tax_year)

    transactions = query.all()

    updated = 0
    for t in transactions:
        result = classifier.classify_transaction(t)

        if t.type == TransactionType.INCOME:
            # Re-classify income
            if result.category:
                try:
                    new_cat = IncomeCategory(result.category)
                    t.income_category = new_cat
                    t.classification_confidence = result.confidence
                    updated += 1
                except ValueError:
                    pass
        else:
            # Re-classify expense
            new_category = None
            if result.category:
                try:
                    new_category = ExpenseCategory(result.category)
                except ValueError:
                    new_category = None

            if new_category:
                t.expense_category = new_category
                t.classification_confidence = result.confidence

            # Re-check deductibility with current rules
            category = (new_category or t.expense_category or ExpenseCategory.OTHER).value
            user_type = current_user.user_type.value
            deduct_result = deductibility_checker.check(category, user_type)
            t.is_deductible = deduct_result.is_deductible
            t.deduction_reason = deduct_result.reason
            if deduct_result.requires_review:
                t.needs_review = True
            updated += 1

    db.commit()

    return {
        "message": f"Reclassified {updated} transactions",
        "updated": updated,
    }






@router.post("/{transaction_id}/pause", response_model=TransactionResponse)
def pause_recurring_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pause a recurring transaction"""
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == current_user.id,
        Transaction.is_recurring == True,
    ).first()
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Recurring transaction not found")
    
    transaction.recurring_is_active = False
    db.commit()
    db.refresh(transaction)
    return transaction


@router.post("/{transaction_id}/resume", response_model=TransactionResponse)
def resume_recurring_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resume a paused recurring transaction"""
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == current_user.id,
        Transaction.is_recurring == True,
    ).first()
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Recurring transaction not found")
    
    transaction.recurring_is_active = True
    db.commit()
    db.refresh(transaction)
    return transaction
