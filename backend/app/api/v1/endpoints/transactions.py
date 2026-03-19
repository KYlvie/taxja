"""Transaction CRUD endpoints"""
from typing import Optional
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status, UploadFile, File
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
from app.core.transaction_enum_coercion import (
    coerce_expense_category,
    coerce_income_category,
    coerce_transaction_type,
)
from app.core.security import get_current_user
from app.services.transaction_classifier import TransactionClassifier
from app.services.deductibility_checker import DeductibilityChecker
from app.services.credit_service import CreditService, InsufficientCreditsError
import math

router = APIRouter()


async def _invalidate_dashboard_cache(user_id: int) -> None:
    """Clear cached dashboard data for a user after transaction changes."""
    try:
        from app.core.cache import cache
        await cache.delete_pattern(f"dashboard:{user_id}:*")
    except Exception:
        pass  # cache miss is acceptable


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


@router.post(
    "",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_transaction(
    transaction_data: TransactionCreate,
    response: Response,
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
    
    # --- Credit deduction ---
    credit_service = CreditService(db, redis_client=None)
    try:
        deduction = credit_service.check_and_deduct(
            user_id=current_user.id,
            operation="transaction_entry",
        )
    except InsufficientCreditsError as e:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient credits: {e.required} required, {e.available} available",
        )

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
    classification_method = None
    needs_review = False
    
    if transaction_data.type == TransactionType.INCOME:
        if not transaction_data.income_category:
            # Auto-classify income (pass user context for LLM fallback)
            result = classifier.classify_transaction(temp_transaction, current_user)
            if result.category:
                normalized_category = coerce_income_category(result.category)
                if normalized_category:
                    transaction_data.income_category = normalized_category
                    classification_confidence = result.confidence
                    classification_method = result.method
                    needs_review = result.confidence < Decimal('0.7')
                else:
                    transaction_data.income_category = IncomeCategory.EMPLOYMENT
                    needs_review = True
            else:
                transaction_data.income_category = IncomeCategory.EMPLOYMENT
                needs_review = True
        else:
            classification_method = "manual"
    else:
        if not transaction_data.expense_category:
            # Auto-classify expense (pass user context for LLM fallback)
            result = classifier.classify_transaction(temp_transaction, current_user)
            if result.category:
                normalized_category = coerce_expense_category(result.category)
                if normalized_category:
                    transaction_data.expense_category = normalized_category
                    classification_confidence = result.confidence
                    classification_method = result.method
                    needs_review = result.confidence < Decimal('0.7')
                else:
                    transaction_data.expense_category = ExpenseCategory.OTHER
                    needs_review = True
            else:
                transaction_data.expense_category = ExpenseCategory.OTHER
                needs_review = True
        else:
            classification_method = "manual"
    
    # Auto-determine deductibility if not provided
    if transaction_data.type == TransactionType.EXPENSE:
        if transaction_data.is_deductible is None:
            # Check deductibility
            category = transaction_data.expense_category.value
            user_type = current_user.user_type.value
            
            deductibility_result = deductibility_checker.check(
                category,
                user_type,
                description=transaction_data.description,
                business_type=getattr(current_user, 'business_type', None),
                business_industry=getattr(current_user, 'business_industry', None),
            )
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
        classification_method=classification_method,
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

    # Sync line items from linked document OCR data (if document has multi-item receipt)
    if transaction_data.document_id:
        try:
            from app.services.ocr_transaction_service import OCRTransactionService
            ocr_svc = OCRTransactionService(db)
            ocr_svc._sync_line_items_from_document(
                db_transaction, {"document_id": transaction_data.document_id}
            )
        except Exception:
            import logging
            logging.getLogger(__name__).debug(
                "Line item sync skipped for transaction %s", db_transaction.id, exc_info=True
            )

    # If recurring is enabled, also create a RecurringTransaction entry
    # so it appears in the "高级管理" recurring transactions list
    if transaction_data.is_recurring:
        try:
            from app.services.recurring_transaction_service import RecurringTransactionService
            from app.models.recurring_transaction import RecurringTransaction as RT, RecurringTransactionType, RecurrenceFrequency

            freq_map = {
                "monthly": RecurrenceFrequency.MONTHLY,
                "quarterly": RecurrenceFrequency.QUARTERLY,
                "yearly": RecurrenceFrequency.ANNUALLY,
                "annually": RecurrenceFrequency.ANNUALLY,
                "weekly": RecurrenceFrequency.WEEKLY,
                "biweekly": RecurrenceFrequency.BIWEEKLY,
            }
            freq = freq_map.get(transaction_data.recurring_frequency or "monthly", RecurrenceFrequency.MONTHLY)

            if db_transaction.type == TransactionType.INCOME:
                rec_type = RecurringTransactionType.OTHER_INCOME
                category = db_transaction.income_category.value if db_transaction.income_category else "other_income"
            else:
                rec_type = RecurringTransactionType.OTHER_EXPENSE
                category = db_transaction.expense_category.value if db_transaction.expense_category else "other"

            start = transaction_data.recurring_start_date or db_transaction.transaction_date
            recurring_entry = RT(
                user_id=current_user.id,
                recurring_type=rec_type,
                property_id=db_transaction.property_id,
                description=db_transaction.description,
                amount=db_transaction.amount,
                transaction_type=db_transaction.type.value,
                category=category,
                frequency=freq,
                start_date=start,
                end_date=transaction_data.recurring_end_date,
                day_of_month=transaction_data.recurring_day_of_month or start.day,
                is_active=True,
                next_generation_date=start,
            )
            db.add(recurring_entry)
            db.commit()
            db.refresh(recurring_entry)

            # Link original transaction to the recurring entry
            db_transaction.source_recurring_id = recurring_entry.id
            db.commit()

            # Generate past-due transactions
            service = RecurringTransactionService(db)
            service.generate_due_transactions(target_date=date.today(), user_id=current_user.id)
            db.refresh(db_transaction)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Failed to create RecurringTransaction from transaction create")

    await _invalidate_dashboard_cache(current_user.id)

    response.headers["X-Credits-Remaining"] = str(
        deduction.balance_after.available_without_overage
    )

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
    needs_review: Optional[bool] = Query(None, description="Filter by review status"),
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

    if needs_review is not None:
        if needs_review:
            query = query.filter(Transaction.needs_review == True, Transaction.reviewed == False)
        else:
            query = query.filter(
                (Transaction.needs_review == False) | (Transaction.reviewed == True)
            )

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
    response: Response = None,
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
            txn_type = (
                coerce_transaction_type(row.get("type"), default=TransactionType.EXPENSE)
                or TransactionType.EXPENSE
            )

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
            cls_method = None

            if category_str:
                if txn_type == TransactionType.INCOME:
                    income_cat = coerce_income_category(category_str)
                    if income_cat:
                        cls_method = "csv"
                else:
                    expense_cat = coerce_expense_category(category_str)
                    if expense_cat:
                        cls_method = "csv"

            if not income_cat and not expense_cat:
                temp = Transaction(
                    type=txn_type, amount=amount,
                    transaction_date=txn_date, description=description,
                )
                result = classifier.classify_transaction(temp, current_user)
                if result and result.category:
                    if txn_type == TransactionType.INCOME:
                        income_cat = coerce_income_category(result.category)
                    else:
                        expense_cat = coerce_expense_category(result.category)
                    confidence = result.confidence
                    cls_method = result.method

            cat_value = (income_cat.value if income_cat else expense_cat.value if expense_cat else None)
            if cat_value:
                user_type = current_user.user_type.value if hasattr(current_user.user_type, "value") else str(current_user.user_type)
                deduct = deductibility_checker.check(
                    cat_value, user_type,
                    business_type=getattr(current_user, 'business_type', None),
                    business_industry=getattr(current_user, 'business_industry', None),
                )
                is_deductible = deduct.is_deductible

            # Determine review flag based on confidence (matching manual creation logic)
            needs_review = False
            ai_review_notes = None
            if confidence is not None and confidence < Decimal("0.7"):
                needs_review = True
                ai_review_notes = f"CSV import: low classification confidence ({float(confidence):.0%})"
            elif not cat_value:
                needs_review = True
                ai_review_notes = "CSV import: could not determine category"

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
                classification_method=cls_method,
                import_source="csv",
                needs_review=needs_review,
                ai_review_notes=ai_review_notes,
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

    deduction = None
    if imported:
        credit_service = CreditService(db, redis_client=None)
        try:
            deduction = credit_service.check_and_deduct(
                user_id=current_user.id,
                operation="transaction_entry",
                quantity=len(imported),
            )
        except InsufficientCreditsError as e:
            db.rollback()
            raise HTTPException(
                status_code=402,
                detail=f"Insufficient credits: {e.required} required, {e.available} available",
            ) from e

    db.commit()

    if response is not None and deduction is not None:
        response.headers["X-Credits-Remaining"] = str(
            deduction.balance_after.available_without_overage
        )

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


# --- Routes with path parameters MUST come after /import, /export, /batch-delete ---


@router.post("/batch-delete", status_code=status.HTTP_200_OK)
async def batch_delete_transactions(
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete multiple transactions at once.

    Supports a pre-check flow via the ``force`` body parameter:
    - ``force=False`` (default): categorise each transaction into
      *blocked*, *needs_confirmation*, or *safe* and return the
      classification **without** deleting anything.
    - ``force=True``: delete *safe* + *needs_confirmation* transactions
      (skip *blocked* ones) and return the result.

    When every transaction is safe and ``force=False`` the pre-check
    result is still returned so the frontend can decide to proceed.
    """
    from app.models.document import Document

    ids = body.get("ids", [])
    force = body.get("force", False)

    if not ids or not isinstance(ids, list):
        raise HTTPException(status_code=400, detail="ids must be a non-empty list")
    if len(ids) > 500:
        raise HTTPException(status_code=400, detail="Cannot delete more than 500 at once")

    txns = db.query(Transaction).filter(
        Transaction.id.in_(ids),
        Transaction.user_id == current_user.id,
    ).all()

    # --- Categorise each transaction via association check ---
    blocked = []
    needs_confirmation = []
    safe_ids = []

    for txn in txns:
        check = _check_transaction_associations(txn, db)
        if check["warning_type"] == "document_only":
            blocked.append({
                "id": txn.id,
                "reason": "document_only",
                "document_name": check.get("document_name"),
            })
        elif check["warning_type"] in ("document_multi", "recurring"):
            needs_confirmation.append({
                "id": txn.id,
                "warning_type": check["warning_type"],
                "document_name": check.get("document_name"),
                "linked_count": check.get("linked_transaction_count"),
            })
        else:
            safe_ids.append(txn.id)

    # --- Pre-check mode (force=False) ---
    # Always return the classification so the frontend can decide.
    # This covers both "has associations" and "all safe" scenarios.
    if not force:
        return {
            "blocked": blocked,
            "needs_confirmation": needs_confirmation,
            "safe": safe_ids,
        }

    # --- Force mode (force=True): delete safe + needs_confirmation ---
    deletable_ids = set(safe_ids) | {item["id"] for item in needs_confirmation}
    deleted_ids = []

    for txn in txns:
        if txn.id not in deletable_ids:
            continue
        docs = db.query(Document).filter(Document.transaction_id == txn.id).all()
        for doc in docs:
            doc.transaction_id = None
        txn.document_id = None
        db.flush()
        db.delete(txn)
        deleted_ids.append(txn.id)

    db.commit()
    await _invalidate_dashboard_cache(current_user.id)

    return {
        "deleted": deleted_ids,
        "blocked": [{"id": b["id"], "reason": b["reason"]} for b in blocked],
        "count": len(deleted_ids),
    }


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
async def update_transaction(
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

    # Snapshot original category before applying changes (for learning)
    original_expense_cat = (
        transaction.expense_category.value
        if transaction.expense_category and hasattr(transaction.expense_category, "value")
        else str(transaction.expense_category) if transaction.expense_category else None
    )
    original_income_cat = (
        transaction.income_category.value
        if transaction.income_category and hasattr(transaction.income_category, "value")
        else str(transaction.income_category) if transaction.income_category else None
    )

    # Extract line_items from update_data (handled separately)
    line_items_data = update_data.pop("line_items", None)

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

    # Handle recurring activation/deactivation
    if 'is_recurring' in update_data:
        if update_data['is_recurring']:
            transaction.recurring_is_active = True
            transaction.recurring_next_date = (
                update_data.get('recurring_start_date') or transaction.recurring_start_date
            )

            # Also create a RecurringTransaction entry so it appears in 高级管理
            try:
                from app.services.recurring_transaction_service import RecurringTransactionService
                from app.models.recurring_transaction import (
                    RecurringTransaction as RT,
                    RecurringTransactionType,
                    RecurrenceFrequency,
                )

                # Check if a RecurringTransaction already exists for this transaction
                existing_rt = None
                if transaction.source_recurring_id:
                    existing_rt = db.query(RT).filter(RT.id == transaction.source_recurring_id).first()

                if not existing_rt:
                    freq_map = {
                        "monthly": RecurrenceFrequency.MONTHLY,
                        "quarterly": RecurrenceFrequency.QUARTERLY,
                        "yearly": RecurrenceFrequency.ANNUALLY,
                        "annually": RecurrenceFrequency.ANNUALLY,
                        "weekly": RecurrenceFrequency.WEEKLY,
                        "biweekly": RecurrenceFrequency.BIWEEKLY,
                    }
                    freq_str = update_data.get('recurring_frequency') or transaction.recurring_frequency or "monthly"
                    freq = freq_map.get(freq_str, RecurrenceFrequency.MONTHLY)

                    if transaction.type == TransactionType.INCOME:
                        rec_type = RecurringTransactionType.OTHER_INCOME
                        category = transaction.income_category.value if transaction.income_category else "other_income"
                    else:
                        rec_type = RecurringTransactionType.OTHER_EXPENSE
                        category = transaction.expense_category.value if transaction.expense_category else "other"

                    start = (
                        update_data.get('recurring_start_date')
                        or transaction.recurring_start_date
                        or transaction.transaction_date
                    )
                    end = update_data.get('recurring_end_date') or transaction.recurring_end_date
                    dom = update_data.get('recurring_day_of_month') or transaction.recurring_day_of_month
                    if not dom and start:
                        dom = start.day if hasattr(start, 'day') else 1

                    recurring_entry = RT(
                        user_id=current_user.id,
                        recurring_type=rec_type,
                        property_id=transaction.property_id,
                        description=transaction.description,
                        amount=transaction.amount,
                        transaction_type=transaction.type.value,
                        category=category,
                        frequency=freq,
                        start_date=start,
                        end_date=end,
                        day_of_month=dom or 1,
                        is_active=True,
                        next_generation_date=start,
                    )
                    db.add(recurring_entry)
                    db.flush()

                    transaction.source_recurring_id = recurring_entry.id

                    db.commit()
                    db.refresh(recurring_entry)

                    # Generate past-due transactions
                    service = RecurringTransactionService(db)
                    service.generate_due_transactions(
                        target_date=date.today(), user_id=current_user.id
                    )
            except Exception:
                import logging
                logging.getLogger(__name__).exception(
                    "Failed to create RecurringTransaction from transaction update"
                )
        else:
            transaction.recurring_is_active = False
            transaction.recurring_next_date = None

    # ── Learn from category correction ──────────────────────────────
    try:
        new_expense_cat = (
            transaction.expense_category.value
            if transaction.expense_category and hasattr(transaction.expense_category, "value")
            else str(transaction.expense_category) if transaction.expense_category else None
        )
        new_income_cat = (
            transaction.income_category.value
            if transaction.income_category and hasattr(transaction.income_category, "value")
            else str(transaction.income_category) if transaction.income_category else None
        )
        category_changed = (
            (new_expense_cat != original_expense_cat and original_expense_cat is not None)
            or (new_income_cat != original_income_cat and original_income_cat is not None)
        )
        if category_changed and transaction.description:
            classifier = TransactionClassifier(db=db)
            correct_cat = new_expense_cat or new_income_cat
            if correct_cat:
                classifier.learn_from_correction(
                    transaction, correct_cat, current_user.id,
                )
    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            "Failed to store classification correction for txn %s", transaction_id, exc_info=True,
        )

    # ── Handle line item updates (full replacement) ─────────────────
    if line_items_data is not None:
        from app.models.transaction_line_item import TransactionLineItem

        # Delete existing line items
        db.query(TransactionLineItem).filter(
            TransactionLineItem.transaction_id == transaction.id,
        ).delete()
        db.flush()

        # Create new line items
        for idx, li_data in enumerate(line_items_data):
            li = TransactionLineItem(
                transaction_id=transaction.id,
                description=li_data["description"],
                amount=li_data["amount"],
                quantity=li_data.get("quantity", 1),
                category=li_data.get("category"),
                is_deductible=li_data.get("is_deductible", False),
                deduction_reason=li_data.get("deduction_reason"),
                vat_rate=li_data.get("vat_rate"),
                vat_amount=li_data.get("vat_amount"),
                sort_order=li_data.get("sort_order", idx),
            )
            db.add(li)

        deductible_items = [li for li in line_items_data if li.get("is_deductible") is True]
        non_deductible_items = [li for li in line_items_data if li.get("is_deductible") is False]

        transaction.is_deductible = bool(deductible_items)
        transaction.reviewed = True
        transaction.locked = True
        transaction.needs_review = False

        if deductible_items and non_deductible_items:
            transaction.deduction_reason = "Mixed deductibility confirmed at line-item level"
        elif deductible_items:
            transaction.deduction_reason = next(
                (li.get("deduction_reason") for li in deductible_items if li.get("deduction_reason")),
                transaction.deduction_reason,
            )
        elif non_deductible_items:
            transaction.deduction_reason = next(
                (li.get("deduction_reason") for li in non_deductible_items if li.get("deduction_reason")),
                transaction.deduction_reason,
            )

    db.commit()
    db.refresh(transaction)
    await _invalidate_dashboard_cache(current_user.id)
    return transaction


@router.post("/{transaction_id}/review", response_model=TransactionResponse)
async def mark_transaction_reviewed(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark a transaction as reviewed by the user."""
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == current_user.id
    ).first()
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction with id {transaction_id} not found"
        )

    transaction.reviewed = True
    transaction.needs_review = False
    db.commit()
    db.refresh(transaction)
    await _invalidate_dashboard_cache(current_user.id)
    return transaction


def _check_transaction_associations(transaction: Transaction, db: Session) -> dict:
    """Check a transaction's associations with documents and recurring transactions.

    Returns a dict describing whether the transaction can be safely deleted
    and what kind of warning (if any) should be shown to the user.
    Reusable by delete-check, single-delete, and batch-delete endpoints.
    """
    from app.models.document import Document

    result = {
        "can_delete": True,
        "warning_type": None,
        "document_id": None,
        "document_name": None,
        "linked_transaction_count": None,
        "is_from_recurring": bool(transaction.source_recurring_id),
    }

    if transaction.document_id:
        doc = db.query(Document).filter(Document.id == transaction.document_id).first()
        linked_count = (
            db.query(Transaction)
            .filter(Transaction.document_id == transaction.document_id)
            .count()
        )
        result["document_id"] = transaction.document_id
        result["document_name"] = doc.file_name if doc else None
        result["linked_transaction_count"] = linked_count

        if linked_count <= 1:
            # Only transaction for this document → block deletion
            result["can_delete"] = False
            result["warning_type"] = "document_only"
            return result
        else:
            # Multiple transactions share this document → needs confirmation
            result["can_delete"] = True
            result["warning_type"] = "document_multi"
            return result

    if transaction.source_recurring_id:
        result["warning_type"] = "recurring"
        return result

    return result


@router.get("/{transaction_id}/delete-check")
async def delete_check(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pre-check whether a transaction can be safely deleted.

    Returns association info so the frontend can show the appropriate
    confirmation dialog or block the deletion entirely.
    """
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == current_user.id,
    ).first()
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction with id {transaction_id} not found",
        )

    return _check_transaction_associations(transaction, db)


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    transaction_id: int,
    force: bool = Query(False, description="Force delete even if associations exist"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a transaction.

    Performs association checks before deleting:
    - document_only: always blocked (HTTP 409)
    - document_multi / recurring: blocked unless force=True (HTTP 409)
    - no associations: deleted directly
    """
    from app.models.document import Document

    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == current_user.id,
    ).first()
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction with id {transaction_id} not found",
        )

    # --- association check ---
    check = _check_transaction_associations(transaction, db)
    warning_type = check["warning_type"]

    if warning_type == "document_only":
        # Always blocked – the document would lose its only transaction
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": (
                    f"This transaction is linked to document "
                    f"\"{check['document_name']}\". "
                    "Please modify it from Document Management."
                ),
                "warning_type": "document_only",
                "requires_confirmation": False,
                "document_id": check["document_id"],
                "document_name": check["document_name"],
                "linked_transaction_count": check["linked_transaction_count"],
                "is_from_recurring": check["is_from_recurring"],
            },
        )

    if warning_type in ("document_multi", "recurring") and not force:
        if warning_type == "document_multi":
            detail = (
                f"This transaction is from document "
                f"\"{check['document_name']}\" "
                f"({check['linked_transaction_count']} transactions total). "
                "Only this one will be deleted. Continue?"
            )
        else:
            detail = (
                "This transaction was generated by a recurring rule. "
                "It may be regenerated next cycle. Continue?"
            )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": detail,
                "warning_type": warning_type,
                "requires_confirmation": True,
                "document_id": check["document_id"],
                "document_name": check["document_name"],
                "linked_transaction_count": check["linked_transaction_count"],
                "is_from_recurring": check["is_from_recurring"],
            },
        )

    # --- proceed with deletion (no association, or force=True) ---

    # Clear document references to this transaction to avoid FK violation
    docs = db.query(Document).filter(Document.transaction_id == transaction_id).all()
    for doc in docs:
        doc.transaction_id = None

    # Clear transaction's own document_id reference
    transaction.document_id = None
    db.flush()

    db.delete(transaction)
    db.commit()
    await _invalidate_dashboard_cache(current_user.id)
    return None



@router.post("/reclassify")
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
        result = classifier.classify_transaction(t, current_user)

        if t.type == TransactionType.INCOME:
            # Re-classify income
            if result.category:
                new_cat = coerce_income_category(result.category)
                if new_cat:
                    t.income_category = new_cat
                    t.classification_confidence = result.confidence
                    t.classification_method = result.method
                    updated += 1
        else:
            # Re-classify expense
            new_category = coerce_expense_category(result.category)

            if new_category:
                t.expense_category = new_category
                t.classification_confidence = result.confidence
                t.classification_method = result.method

            # Re-check deductibility with current rules
            category = (new_category or t.expense_category or ExpenseCategory.OTHER).value
            user_type = current_user.user_type.value
            deduct_result = deductibility_checker.check(
                category, user_type,
                description=t.description,
                business_type=getattr(current_user, 'business_type', None),
                business_industry=getattr(current_user, 'business_industry', None),
            )
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
