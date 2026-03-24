"""Transaction CRUD endpoints"""
from typing import Optional
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, extract
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
from app.core.error_messages import get_error_message
from app.services.transaction_classifier import TransactionClassifier
from app.services.deductibility_checker import DeductibilityChecker
from app.services.credit_service import CreditService, InsufficientCreditsError
from app.services.posting_line_utils import (
    derive_parent_deductibility,
    normalize_line_item_payloads,
    replace_transaction_line_items,
)
from app.services.transaction_rule_materializer import (
    build_auto_materialized_line_items,
    get_transaction_rule_context,
    recompute_rule_bucket,
)
from app.services.user_classification_service import normalize_description
from app.services.user_deductibility_service import (
    UserDeductibilityService,
    compose_deductibility_rule_description,
)
import math

router = APIRouter()

TRANSACTION_EXPORT_LABELS = {
    "en": {
        "title": "Transaction export",
        "generated": "Generated",
        "filters": "Filters",
        "date": "Date",
        "type": "Type",
        "description": "Description",
        "category": "Category",
        "amount": "Amount",
        "deductible": "Deductible",
        "yes": "Yes",
        "no": "No",
        "no_transactions": "No transactions matched the selected filters.",
    },
    "de": {
        "title": "Transaktions-Export",
        "generated": "Erstellt",
        "filters": "Filter",
        "date": "Datum",
        "type": "Typ",
        "description": "Beschreibung",
        "category": "Kategorie",
        "amount": "Betrag",
        "deductible": "Absetzbar",
        "yes": "Ja",
        "no": "Nein",
        "no_transactions": "Keine Transaktionen entsprechen den gewählten Filtern.",
    },
    "zh": {
        "title": "交易导出",
        "generated": "生成时间",
        "filters": "筛选条件",
        "date": "日期",
        "type": "类型",
        "description": "描述",
        "category": "分类",
        "amount": "金额",
        "deductible": "可抵扣",
        "yes": "是",
        "no": "否",
        "no_transactions": "没有符合当前筛选条件的交易。",
    },
    "fr": {
        "title": "Export des transactions",
        "generated": "Généré le",
        "filters": "Filtres",
        "date": "Date",
        "type": "Type",
        "description": "Description",
        "category": "Catégorie",
        "amount": "Montant",
        "deductible": "Déductible",
        "yes": "Oui",
        "no": "Non",
        "no_transactions": "Aucune transaction ne correspond aux filtres sélectionnés.",
    },
    "ru": {
        "title": "Экспорт операций",
        "generated": "Создано",
        "filters": "Фильтры",
        "date": "Дата",
        "type": "Тип",
        "description": "Описание",
        "category": "Категория",
        "amount": "Сумма",
        "deductible": "Вычитается",
        "yes": "Да",
        "no": "Нет",
        "no_transactions": "Нет операций, соответствующих выбранным фильтрам.",
    },
    "hu": {
        "title": "Tranzakcióexport",
        "generated": "Létrehozva",
        "filters": "Szűrők",
        "date": "Dátum",
        "type": "Típus",
        "description": "Leírás",
        "category": "Kategória",
        "amount": "Összeg",
        "deductible": "Levonható",
        "yes": "Igen",
        "no": "Nem",
        "no_transactions": "Nincs tranzakció a kiválasztott szűrőkhöz.",
    },
    "pl": {
        "title": "Eksport transakcji",
        "generated": "Wygenerowano",
        "filters": "Filtry",
        "date": "Data",
        "type": "Typ",
        "description": "Opis",
        "category": "Kategoria",
        "amount": "Kwota",
        "deductible": "Odliczalne",
        "yes": "Tak",
        "no": "Nie",
        "no_transactions": "Brak transakcji spełniających wybrane filtry.",
    },
    "tr": {
        "title": "İşlem dışa aktarımı",
        "generated": "Oluşturulma",
        "filters": "Filtreler",
        "date": "Tarih",
        "type": "Tür",
        "description": "Açıklama",
        "category": "Kategori",
        "amount": "Tutar",
        "deductible": "İndirilebilir",
        "yes": "Evet",
        "no": "Hayır",
        "no_transactions": "Seçili filtrelere uyan işlem bulunamadı.",
    },
    "bs": {
        "title": "Izvoz transakcija",
        "generated": "Generisano",
        "filters": "Filteri",
        "date": "Datum",
        "type": "Tip",
        "description": "Opis",
        "category": "Kategorija",
        "amount": "Iznos",
        "deductible": "Odbitno",
        "yes": "Da",
        "no": "Ne",
        "no_transactions": "Nema transakcija za odabrane filtere.",
    },
}

ALLOWED_SORT_FIELDS = {"transaction_date", "amount", "created_at", "description"}
CLASSIFIED_TRANSACTION_TYPES = {
    TransactionType.INCOME,
    TransactionType.EXPENSE,
}


def _build_recurring_blueprint(
    transaction: Transaction,
):
    """Map a transaction to its recurring template semantics."""
    from app.models.recurring_transaction import RecurringTransactionType

    if transaction.type == TransactionType.INCOME:
        category = (
            transaction.income_category.value
            if transaction.income_category
            else "other_income"
        )
        return RecurringTransactionType.OTHER_INCOME, category

    if transaction.type == TransactionType.EXPENSE:
        category = (
            transaction.expense_category.value
            if transaction.expense_category
            else "other"
        )
        return RecurringTransactionType.OTHER_EXPENSE, category

    return RecurringTransactionType.MANUAL, transaction.type.value


def _transaction_category_token(transaction: Transaction) -> Optional[str]:
    """Return the category token that should be exposed for exports/UI bridges."""
    if transaction.income_category:
        return transaction.income_category.value
    if transaction.expense_category:
        return transaction.expense_category.value
    return transaction.type.value if transaction.type not in CLASSIFIED_TRANSACTION_TYPES else None


async def _invalidate_dashboard_cache(user_id: int) -> None:
    """Clear cached dashboard data for a user after transaction changes."""
    try:
        from app.core.cache import cache
        await cache.delete_pattern(f"dashboard:{user_id}:*")
    except Exception:
        pass  # cache miss is acceptable


def _sync_parent_line_item_flags(
    transaction: Transaction,
    normalized_line_items: list[dict],
) -> None:
    """Derive compatibility flags on the parent transaction from canonical lines."""
    is_deductible, deduction_reason = derive_parent_deductibility(normalized_line_items)
    transaction.is_deductible = is_deductible
    transaction.deduction_reason = deduction_reason


def _replace_transaction_line_items(
    db: Session,
    transaction: Transaction,
    normalized_line_items: list[dict],
) -> None:
    """Replace all stored line items for a transaction with canonical rows."""
    replace_transaction_line_items(db, transaction, normalized_line_items)


def _unique_rule_contexts(contexts):
    """Deduplicate rule recomputation scopes while preserving order."""
    seen = set()
    ordered = []
    for context in contexts:
        if context is None:
            continue
        key = (context.tax_year, context.rule_bucket)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(context)
    return ordered


def _expense_category_value(transaction: Transaction) -> Optional[str]:
    category = getattr(transaction, "expense_category", None)
    normalized = coerce_expense_category(getattr(category, "value", category))
    return normalized.value if normalized is not None else getattr(category, "value", category)


def _income_category_value(transaction: Transaction) -> Optional[str]:
    category = getattr(transaction, "income_category", None)
    normalized = coerce_income_category(getattr(category, "value", category))
    return normalized.value if normalized is not None else getattr(category, "value", category)


def _line_item_posting_type_value(item: dict) -> Optional[str]:
    posting_type = item.get("posting_type")
    raw_value = getattr(posting_type, "value", posting_type)
    if raw_value is None:
        return None
    token = str(raw_value).strip()
    return token.lower() or None


def _line_item_category_value(item: dict) -> Optional[str]:
    category = item.get("category")
    if category is None:
        return None

    posting_type = _line_item_posting_type_value(item)
    raw_value = getattr(category, "value", category)
    token = str(raw_value).strip()
    if not token:
        return None

    if posting_type == TransactionType.EXPENSE.value:
        normalized = coerce_expense_category(token)
        if normalized is not None:
            return normalized.value
    elif posting_type == TransactionType.INCOME.value:
        normalized = coerce_income_category(token)
        if normalized is not None:
            return normalized.value
    else:
        normalized_expense = coerce_expense_category(token)
        if normalized_expense is not None:
            return normalized_expense.value
        normalized_income = coerce_income_category(token)
        if normalized_income is not None:
            return normalized_income.value

    return token.lower()


def _cascade_parent_category_to_line_items(
    transaction_type: TransactionType,
    normalized_line_items: list[dict],
    previous_category: Optional[str],
    next_category: Optional[str],
) -> None:
    """Keep mirrored line-item categories aligned with a manual parent correction."""
    if not next_category or next_category == previous_category:
        return

    expected_posting_type = (
        TransactionType.INCOME.value
        if transaction_type == TransactionType.INCOME
        else TransactionType.EXPENSE.value
        if transaction_type == TransactionType.EXPENSE
        else None
    )
    if expected_posting_type is None:
        return

    candidate_items = [
        item
        for item in normalized_line_items
        if _line_item_posting_type_value(item) in (None, expected_posting_type)
    ]
    if not candidate_items:
        return

    previous_token = str(previous_category or "").strip()
    category_tokens = [str(_line_item_category_value(item) or "").strip() for item in candidate_items]
    if not all((not token) or token == previous_token for token in category_tokens):
        return

    for item in candidate_items:
        item["category"] = next_category


def _derive_parent_category_from_line_items(
    transaction_type: TransactionType,
    normalized_line_items: list[dict],
    fallback_category: Optional[str],
) -> Optional[str]:
    """Derive a stable parent category from edited line items."""
    expected_posting_type = (
        TransactionType.INCOME.value
        if transaction_type == TransactionType.INCOME
        else TransactionType.EXPENSE.value
        if transaction_type == TransactionType.EXPENSE
        else None
    )
    if expected_posting_type is None:
        return fallback_category

    categories = [
        category
        for category in (
            _line_item_category_value(item)
            for item in normalized_line_items
            if _line_item_posting_type_value(item) in (None, expected_posting_type)
        )
        if category
    ]

    if not categories:
        return fallback_category

    unique_categories = []
    for category in categories:
        if category not in unique_categories:
            unique_categories.append(category)

    if len(unique_categories) == 1:
        return unique_categories[0]

    if fallback_category and fallback_category in unique_categories:
        return fallback_category

    return unique_categories[0]


def _learn_parent_deductibility_override(
    db: Session,
    transaction: Transaction,
    user_id: int,
) -> None:
    if transaction.type != TransactionType.EXPENSE or not transaction.description:
        return

    category = _expense_category_value(transaction)
    if not category:
        return

    UserDeductibilityService(db).upsert_rule(
        user_id=user_id,
        description=transaction.description,
        expense_category=category,
        is_deductible=bool(transaction.is_deductible),
        reason=transaction.deduction_reason,
    )


def _learn_line_item_deductibility_overrides(
    db: Session,
    transaction: Transaction,
    user_id: int,
    normalized_line_items: list[dict],
) -> None:
    if transaction.type != TransactionType.EXPENSE:
        return

    fallback_category = _expense_category_value(transaction)
    parent_description = transaction.description or ""
    service = UserDeductibilityService(db)

    expense_items = [
        item
        for item in normalized_line_items
        if getattr(item.get("posting_type"), "value", item.get("posting_type")) in (None, "expense")
    ]

    service.learn_from_line_items(
        user_id=user_id,
        parent_description=parent_description,
        fallback_category=fallback_category,
        line_items=expense_items,
    )

    if (
        parent_description
        and fallback_category
        and expense_items
        and len({bool(item.get("is_deductible")) for item in expense_items}) == 1
    ):
        parent_norm = normalize_description(parent_description)
        parent_category = service._normalize_expense_category(fallback_category)
        has_parent_like_item_rule = any(
            normalize_description(
                compose_deductibility_rule_description(
                    parent_description,
                    str(item.get("description") or "").strip(),
                )
            )
            == parent_norm
            and service._normalize_expense_category(
                str(item.get("category") or fallback_category or "").strip()
            )
            == parent_category
            for item in expense_items
            if str(item.get("description") or "").strip()
        )
        if has_parent_like_item_rule:
            return

        first_item = expense_items[0]
        service.upsert_rule(
            user_id=user_id,
            description=parent_description,
            expense_category=fallback_category,
            is_deductible=bool(first_item.get("is_deductible")),
            reason=str(first_item.get("deduction_reason") or transaction.deduction_reason or "").strip() or None,
        )


def _auto_materialize_transaction_without_explicit_lines(
    db: Session,
    transaction: Transaction,
    current_user: User,
):
    """Apply automatic split rules or fall back to a canonical mirror line."""
    normalized_line_items, rule_context = build_auto_materialized_line_items(
        transaction,
        current_user,
    )
    if normalized_line_items is not None:
        _replace_transaction_line_items(db, transaction, normalized_line_items)
        return rule_context

    if rule_context is not None:
        recompute_rule_bucket(db, current_user.id, rule_context)
        return rule_context

    normalized_line_items = normalize_line_item_payloads(
        transaction_type=transaction.type,
        transaction_amount=transaction.amount,
        description=transaction.description,
        income_category=transaction.income_category,
        expense_category=transaction.expense_category,
        is_deductible=bool(transaction.is_deductible),
        deduction_reason=transaction.deduction_reason,
        vat_rate=transaction.vat_rate,
        vat_amount=transaction.vat_amount,
        line_items=None,
    )
    _replace_transaction_line_items(db, transaction, normalized_line_items)
    return None


def _transaction_can_refresh_auto_rules(transaction: Transaction) -> bool:
    """Only replace existing multi-line transactions when rules created them."""
    line_items = list(getattr(transaction, "line_items", []) or [])
    if not line_items or len(line_items) <= 1:
        return True

    auto_sources = {
        "percentage_rule",
        "cap_rule",
    }
    return all(
        getattr(getattr(li, "allocation_source", None), "value", getattr(li, "allocation_source", None))
        in auto_sources
        for li in line_items
    )


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


def _apply_transaction_non_date_filters(
    query,
    *,
    type: Optional[TransactionType] = None,
    income_category: Optional[IncomeCategory] = None,
    expense_category: Optional[ExpenseCategory] = None,
    is_deductible: Optional[bool] = None,
    is_recurring: Optional[bool] = None,
    needs_review: Optional[bool] = None,
    min_amount: Optional[Decimal] = None,
    max_amount: Optional[Decimal] = None,
    search: Optional[str] = None,
):
    """Apply transaction filters that should not affect year quick-filter boundaries."""
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

    if min_amount is not None:
        query = query.filter(Transaction.amount >= min_amount)

    if max_amount is not None:
        query = query.filter(Transaction.amount <= max_amount)

    if search:
        query = query.filter(Transaction.description.ilike(f"%{search}%"))

    return query


def _apply_transaction_date_filters(
    query,
    *,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    tax_year: Optional[int] = None,
):
    """Apply date-specific filters to an existing transaction query."""
    if date_from:
        query = query.filter(Transaction.transaction_date >= date_from)

    if date_to:
        query = query.filter(Transaction.transaction_date <= date_to)

    if tax_year is not None:
        year_start = date(tax_year, 1, 1)
        year_end = date(tax_year, 12, 31)
        query = query.filter(
            Transaction.transaction_date >= year_start,
            Transaction.transaction_date <= year_end,
        )

    return query


def _get_available_transaction_years(query) -> list[int]:
    """Return distinct transaction years present in the filtered dataset."""
    year_expr = extract("year", Transaction.transaction_date)
    rows = (
        query.with_entities(year_expr.label("year"))
        .distinct()
        .order_by(year_expr.desc())
        .all()
    )

    years: list[int] = []
    for row in rows:
        raw_year = getattr(row, "year", row[0] if row else None)
        if raw_year is None:
            continue
        year = int(raw_year)
        if year not in years:
            years.append(year)
    return years


def _query_transactions_for_export(
    db: Session,
    current_user: User,
    *,
    type: Optional[TransactionType] = None,
    income_category: Optional[IncomeCategory] = None,
    expense_category: Optional[ExpenseCategory] = None,
    is_deductible: Optional[bool] = None,
    is_recurring: Optional[bool] = None,
    needs_review: Optional[bool] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    min_amount: Optional[Decimal] = None,
    max_amount: Optional[Decimal] = None,
    search: Optional[str] = None,
    tax_year: Optional[int] = None,
):
    query = db.query(Transaction).filter(Transaction.user_id == current_user.id)
    query = _apply_transaction_non_date_filters(
        query,
        type=type,
        income_category=income_category,
        expense_category=expense_category,
        is_deductible=is_deductible,
        is_recurring=is_recurring,
        needs_review=needs_review,
        min_amount=min_amount,
        max_amount=max_amount,
        search=search,
    )
    query = _apply_transaction_date_filters(
        query,
        date_from=date_from,
        date_to=date_to,
        tax_year=tax_year,
    )
    return query.order_by(Transaction.transaction_date.desc()).all()


def _get_transaction_export_labels(language: Optional[str]) -> dict[str, str]:
    return TRANSACTION_EXPORT_LABELS.get(language or "en", TRANSACTION_EXPORT_LABELS["en"])


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
    deductibility_checker = DeductibilityChecker(db=db)
    pending_rule_contexts = []
    
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
    explicit_is_deductible = "is_deductible" in transaction_data.model_fields_set
    provided_line_items = (
        [
            li.model_dump(exclude_unset=True)
            for li in (transaction_data.line_items or [])
        ]
        if transaction_data.line_items is not None
        else None
    )
    
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
    elif transaction_data.type == TransactionType.EXPENSE:
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
    else:
        transaction_data.income_category = None
        transaction_data.expense_category = None
        classification_method = "manual"

    # Auto-determine deductibility if not provided
    if transaction_data.type == TransactionType.EXPENSE:
        if provided_line_items is None and not explicit_is_deductible:
            # Check deductibility
            category = transaction_data.expense_category.value
            user_type = current_user.user_type.value
            
            deductibility_result = deductibility_checker.check(
                category,
                user_type,
                description=transaction_data.description,
                business_type=getattr(current_user, 'business_type', None),
                business_industry=getattr(current_user, 'business_industry', None),
                user_id=current_user.id,
            )
            transaction_data.is_deductible = deductibility_result.is_deductible
            
            if not transaction_data.deduction_reason:
                transaction_data.deduction_reason = deductibility_result.reason
            
            # Mark for review if deductibility requires review
            if deductibility_result.requires_review:
                needs_review = True
    elif provided_line_items is None:
        transaction_data.is_deductible = False
        transaction_data.deduction_reason = None
    
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
    db.flush()

    explicit_rule_context = None
    if provided_line_items is not None:
        normalized_line_items = normalize_line_item_payloads(
            transaction_type=db_transaction.type,
            transaction_amount=db_transaction.amount,
            description=db_transaction.description,
            income_category=db_transaction.income_category,
            expense_category=db_transaction.expense_category,
            is_deductible=bool(transaction_data.is_deductible),
            deduction_reason=transaction_data.deduction_reason,
            vat_rate=db_transaction.vat_rate,
            vat_amount=db_transaction.vat_amount,
            line_items=provided_line_items,
        )
        _replace_transaction_line_items(db, db_transaction, normalized_line_items)
        explicit_rule_context = get_transaction_rule_context(db_transaction, current_user)

    # Sync line items from linked document OCR data (if document has multi-item receipt)
    if transaction_data.document_id and provided_line_items is None:
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

    if provided_line_items is None and not db_transaction.line_items:
        _auto_materialize_transaction_without_explicit_lines(
            db,
            db_transaction,
            current_user,
        )
    elif explicit_rule_context is not None:
        recompute_rule_bucket(db, current_user.id, explicit_rule_context)

    db.commit()
    db.refresh(db_transaction)

    if (
        db_transaction.type == TransactionType.EXPENSE
        and provided_line_items is None
        and explicit_is_deductible
    ):
        _learn_parent_deductibility_override(db, db_transaction, current_user.id)
        db.commit()
        db.refresh(db_transaction)

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

            rec_type, category = _build_recurring_blueprint(db_transaction)

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
    
    base_query = db.query(Transaction).filter(Transaction.user_id == current_user.id)
    base_query = _apply_transaction_non_date_filters(
        base_query,
        type=type,
        income_category=income_category,
        expense_category=expense_category,
        is_deductible=is_deductible,
        is_recurring=is_recurring,
        needs_review=needs_review,
        min_amount=min_amount,
        max_amount=max_amount,
        search=search,
    )

    available_years = _get_available_transaction_years(base_query)
    query = _apply_transaction_date_filters(
        base_query,
        date_from=date_from,
        date_to=date_to,
        tax_year=tax_year,
    )
    
    # Get total count before pagination
    total = query.count()

    # Apply sorting (whitelist to prevent column enumeration)
    if sort_by not in ALLOWED_SORT_FIELDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid sort_by field. Allowed: {', '.join(sorted(ALLOWED_SORT_FIELDS))}",
        )
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
        total_pages=total_pages,
        available_years=available_years,
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
    pending_rule_contexts = []

    classifier = TransactionClassifier(db=db)
    deductibility_checker = DeductibilityChecker(db=db)

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
                elif txn_type == TransactionType.EXPENSE:
                    expense_cat = coerce_expense_category(category_str)
                    if expense_cat:
                        cls_method = "csv"

            if txn_type in CLASSIFIED_TRANSACTION_TYPES and not income_cat and not expense_cat:
                temp = Transaction(
                    type=txn_type, amount=amount,
                    transaction_date=txn_date, description=description,
                )
                result = classifier.classify_transaction(temp, current_user)
                if result and result.category:
                    if txn_type == TransactionType.INCOME:
                        income_cat = coerce_income_category(result.category)
                    elif txn_type == TransactionType.EXPENSE:
                        expense_cat = coerce_expense_category(result.category)
                    confidence = result.confidence
                    cls_method = result.method

            cat_value = (income_cat.value if income_cat else expense_cat.value if expense_cat else None)
            if txn_type == TransactionType.EXPENSE and cat_value:
                user_type = current_user.user_type.value if hasattr(current_user.user_type, "value") else str(current_user.user_type)
                deduct = deductibility_checker.check(
                    cat_value, user_type,
                    business_type=getattr(current_user, 'business_type', None),
                    business_industry=getattr(current_user, 'business_industry', None),
                    user_id=current_user.id,
                )
                is_deductible = deduct.is_deductible

            # Determine review flag based on confidence (matching manual creation logic)
            needs_review = False
            ai_review_notes = None
            if txn_type in CLASSIFIED_TRANSACTION_TYPES and confidence is not None and confidence < Decimal("0.7"):
                needs_review = True
                ai_review_notes = f"CSV import: low classification confidence ({float(confidence):.0%})"
            elif txn_type in CLASSIFIED_TRANSACTION_TYPES and not cat_value:
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
            if not transaction.line_items:
                normalized_line_items, rule_context = build_auto_materialized_line_items(
                    transaction,
                    current_user,
                )
                if normalized_line_items is not None:
                    _replace_transaction_line_items(db, transaction, normalized_line_items)
                elif rule_context is not None:
                    pending_rule_contexts.append(rule_context)
                else:
                    _auto_materialize_transaction_without_explicit_lines(
                        db,
                        transaction,
                        current_user,
                    )
            imported.append({
                "id": transaction.id,
                "type": txn_type.value,
                "amount": float(amount),
                "date": txn_date.isoformat(),
                "description": description,
                "category": cat_value or txn_type.value,
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

    for rule_context in _unique_rule_contexts(pending_rule_contexts):
        recompute_rule_bucket(db, current_user.id, rule_context)

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
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    type: Optional[TransactionType] = Query(None),
    income_category: Optional[IncomeCategory] = Query(None),
    expense_category: Optional[ExpenseCategory] = Query(None),
    is_deductible: Optional[bool] = Query(None),
    is_recurring: Optional[bool] = Query(None),
    needs_review: Optional[bool] = Query(None),
    min_amount: Optional[Decimal] = Query(None, ge=0),
    max_amount: Optional[Decimal] = Query(None, ge=0),
    search: Optional[str] = Query(None, max_length=100),
    tax_year: Optional[int] = Query(None, ge=1900, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export transactions as CSV."""
    import csv
    import io

    transactions = _query_transactions_for_export(
        db,
        current_user,
        type=type,
        income_category=income_category,
        expense_category=expense_category,
        is_deductible=is_deductible,
        is_recurring=is_recurring,
        needs_review=needs_review,
        date_from=date_from,
        date_to=date_to,
        min_amount=min_amount,
        max_amount=max_amount,
        search=search,
        tax_year=tax_year,
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "type", "amount", "description", "category", "is_deductible"])

    for t in transactions:
        cat = _transaction_category_token(t) or ""
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


@router.get("/export/pdf")
def export_transactions_pdf(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    type: Optional[TransactionType] = Query(None),
    income_category: Optional[IncomeCategory] = Query(None),
    expense_category: Optional[ExpenseCategory] = Query(None),
    is_deductible: Optional[bool] = Query(None),
    is_recurring: Optional[bool] = Query(None),
    needs_review: Optional[bool] = Query(None),
    min_amount: Optional[Decimal] = Query(None, ge=0),
    max_amount: Optional[Decimal] = Query(None, ge=0),
    search: Optional[str] = Query(None, max_length=100),
    tax_year: Optional[int] = Query(None, ge=1900, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export transactions as PDF."""
    import io
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    transactions = _query_transactions_for_export(
        db,
        current_user,
        type=type,
        income_category=income_category,
        expense_category=expense_category,
        is_deductible=is_deductible,
        is_recurring=is_recurring,
        needs_review=needs_review,
        date_from=date_from,
        date_to=date_to,
        min_amount=min_amount,
        max_amount=max_amount,
        search=search,
        tax_year=tax_year,
    )

    labels = _get_transaction_export_labels(getattr(current_user, "language", "en"))
    styles = getSampleStyleSheet()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
    )

    filter_bits: list[str] = []
    if tax_year is not None:
        filter_bits.append(f"{labels['filters']}: {tax_year}")
    elif date_from or date_to:
        range_text = f"{date_from.isoformat() if date_from else '…'} - {date_to.isoformat() if date_to else '…'}"
        filter_bits.append(f"{labels['filters']}: {range_text}")
    if type:
        filter_bits.append(f"{labels['type']}: {type.value}")
    if search:
        filter_bits.append(f"Search: {search}")

    story = [
        Paragraph(labels["title"], styles["Title"]),
        Paragraph(
            f"{labels['generated']}: {date.today().isoformat()}",
            styles["Normal"],
        ),
    ]

    if filter_bits:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(" | ".join(filter_bits), styles["Italic"]))

    story.append(Spacer(1, 6 * mm))

    if not transactions:
        story.append(Paragraph(labels["no_transactions"], styles["Normal"]))
    else:
        table_data = [[
            labels["date"],
            labels["type"],
            labels["description"],
            labels["category"],
            labels["amount"],
            labels["deductible"],
        ]]

        for txn in transactions:
            table_data.append([
                txn.transaction_date.isoformat(),
                txn.type.value,
                (txn.description or "")[:70],
                _transaction_category_token(txn) or "",
                f"{txn.amount:.2f}",
                labels["yes"] if txn.is_deductible else labels["no"],
            ])

        table = Table(
            table_data,
            repeatRows=1,
            colWidths=[28 * mm, 32 * mm, 85 * mm, 40 * mm, 28 * mm, 24 * mm],
        )
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#141127")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f6ff")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9d5f7")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(table)

    doc.build(story)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=transactions.pdf"},
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

    language = getattr(current_user, 'language', 'de') or 'de'

    if not ids or not isinstance(ids, list):
        raise HTTPException(status_code=400, detail=get_error_message("ids_must_be_non_empty", language))
    if len(ids) > 500:
        raise HTTPException(status_code=400, detail=get_error_message("cannot_delete_more_than_limit", language, limit=500))

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
    affected_rule_contexts = []

    for txn in txns:
        if txn.id not in deletable_ids:
            continue
        affected_rule_contexts.append(get_transaction_rule_context(txn, current_user))
        docs = db.query(Document).filter(Document.transaction_id == txn.id).all()
        for doc in docs:
            doc.transaction_id = None
        txn.document_id = None
        db.flush()
        db.delete(txn)
        deleted_ids.append(txn.id)

    db.flush()
    for rule_context in _unique_rule_contexts(affected_rule_contexts):
        recompute_rule_bucket(db, current_user.id, rule_context)

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
    suppress_rule_learning = bool(update_data.pop("suppress_rule_learning", False))

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
    original_is_deductible = bool(transaction.is_deductible)
    original_deduction_reason = transaction.deduction_reason
    original_rule_context = get_transaction_rule_context(transaction, current_user)

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
    else:
        if 'income_category' not in update_data:
            update_data['income_category'] = None
        if 'expense_category' not in update_data:
            update_data['expense_category'] = None

    for field, value in update_data.items():
        setattr(transaction, field, value)

    # When marking as reviewed, automatically clear needs_review
    if update_data.get('reviewed') is True:
        transaction.needs_review = False
    # When explicitly clearing needs_review, mark as reviewed
    if update_data.get('needs_review') is False and 'reviewed' not in update_data:
        transaction.reviewed = True

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

                    rec_type, category = _build_recurring_blueprint(transaction)

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
    if not suppress_rule_learning:
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
                (new_expense_cat is not None and new_expense_cat != original_expense_cat)
                or (new_income_cat is not None and new_income_cat != original_income_cat)
            )
            if category_changed and transaction.description and line_items_data is None:
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
    pending_rule_context = None

    if line_items_data is not None:
        current_parent_category = (
            _income_category_value(transaction)
            if transaction.type == TransactionType.INCOME
            else _expense_category_value(transaction)
            if transaction.type == TransactionType.EXPENSE
            else None
        )
        previous_parent_category = (
            original_income_cat
            if transaction.type == TransactionType.INCOME
            else original_expense_cat
            if transaction.type == TransactionType.EXPENSE
            else None
        )
        normalized_line_items = normalize_line_item_payloads(
            transaction_type=transaction.type,
            transaction_amount=transaction.amount,
            description=transaction.description,
            income_category=transaction.income_category,
            expense_category=transaction.expense_category,
            is_deductible=bool(transaction.is_deductible),
            deduction_reason=transaction.deduction_reason,
            vat_rate=transaction.vat_rate,
            vat_amount=transaction.vat_amount,
            line_items=line_items_data,
        )
        _cascade_parent_category_to_line_items(
            transaction.type,
            normalized_line_items,
            previous_parent_category,
            current_parent_category,
        )
        derived_parent_category = _derive_parent_category_from_line_items(
            transaction.type,
            normalized_line_items,
            current_parent_category,
        )
        if transaction.type == TransactionType.EXPENSE:
            coerced_expense_category = coerce_expense_category(
                derived_parent_category,
                default=transaction.expense_category,
            )
            if coerced_expense_category is not None:
                transaction.expense_category = coerced_expense_category
            transaction.income_category = None
        elif transaction.type == TransactionType.INCOME:
            coerced_income_category = coerce_income_category(
                derived_parent_category,
                default=transaction.income_category,
            )
            if coerced_income_category is not None:
                transaction.income_category = coerced_income_category
            transaction.expense_category = None
        _sync_parent_line_item_flags(transaction, normalized_line_items)
        _replace_transaction_line_items(db, transaction, normalized_line_items)
        if not suppress_rule_learning:
            _learn_line_item_deductibility_overrides(
                db,
                transaction,
                current_user.id,
                normalized_line_items,
            )
    elif _transaction_can_refresh_auto_rules(transaction):
        auto_line_items, pending_rule_context = build_auto_materialized_line_items(
            transaction,
            current_user,
        )
        if auto_line_items is not None:
            _replace_transaction_line_items(db, transaction, auto_line_items)
        elif pending_rule_context is None:
            normalized_line_items = normalize_line_item_payloads(
                transaction_type=transaction.type,
                transaction_amount=transaction.amount,
                description=transaction.description,
                income_category=transaction.income_category,
                expense_category=transaction.expense_category,
                is_deductible=bool(transaction.is_deductible),
                deduction_reason=transaction.deduction_reason,
                vat_rate=transaction.vat_rate,
                vat_amount=transaction.vat_amount,
                line_items=None,
            )
            _replace_transaction_line_items(db, transaction, normalized_line_items)
    else:
        existing_line_items = [
            {
                "description": li.description,
                "amount": li.amount,
                "quantity": li.quantity,
                "posting_type": li.posting_type,
                "allocation_source": li.allocation_source,
                "category": li.category,
                "is_deductible": li.is_deductible,
                "deduction_reason": li.deduction_reason,
                "vat_rate": li.vat_rate,
                "vat_amount": li.vat_amount,
                "vat_recoverable_amount": li.vat_recoverable_amount,
                "rule_bucket": li.rule_bucket,
                "sort_order": li.sort_order,
            }
            for li in transaction.line_items
        ]
        _sync_parent_line_item_flags(transaction, existing_line_items)

    final_expense_cat = _expense_category_value(transaction)
    final_income_cat = _income_category_value(transaction)
    category_changed = (
        (final_expense_cat is not None and final_expense_cat != original_expense_cat)
        or (final_income_cat is not None and final_income_cat != original_income_cat)
    )
    deductibility_changed = bool(transaction.is_deductible) != original_is_deductible
    deduction_reason_changed = (
        (transaction.deduction_reason or None) != (original_deduction_reason or None)
    )

    if line_items_data is not None or category_changed or deductibility_changed or deduction_reason_changed:
        transaction.reviewed = True
        transaction.locked = True
        transaction.needs_review = False

    if (
        not suppress_rule_learning
        and category_changed
        and transaction.description
        and line_items_data is not None
    ):
        try:
            classifier = TransactionClassifier(db=db)
            correct_cat = final_expense_cat or final_income_cat
            if correct_cat:
                classifier.learn_from_correction(
                    transaction,
                    correct_cat,
                    current_user.id,
                )
        except Exception:
            import logging
            logging.getLogger(__name__).warning(
                "Failed to store classification correction for txn %s", transaction_id, exc_info=True,
            )

    updated_rule_context = pending_rule_context or get_transaction_rule_context(transaction, current_user)
    for rule_context in _unique_rule_contexts([original_rule_context, updated_rule_context]):
        recompute_rule_bucket(db, current_user.id, rule_context)

    if (
        not suppress_rule_learning
        and line_items_data is None
        and (deductibility_changed or deduction_reason_changed)
    ):
        _learn_parent_deductibility_override(db, transaction, current_user.id)

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

    affected_rule_context = get_transaction_rule_context(transaction, current_user)

    # Clear document references to this transaction to avoid FK violation
    docs = db.query(Document).filter(Document.transaction_id == transaction_id).all()
    for doc in docs:
        doc.transaction_id = None

    # Clear transaction's own document_id reference
    transaction.document_id = None
    db.flush()

    db.delete(transaction)
    db.flush()
    for rule_context in _unique_rule_contexts([affected_rule_context]):
        recompute_rule_bucket(db, current_user.id, rule_context)
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
    deductibility_checker = DeductibilityChecker(db=db)

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
        elif t.type == TransactionType.EXPENSE:
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
                user_id=current_user.id,
            )
            t.is_deductible = deduct_result.is_deductible
            t.deduction_reason = deduct_result.reason
            if deduct_result.requires_review:
                t.needs_review = True
            updated += 1
        else:
            continue

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
    language = getattr(current_user, 'language', 'de') or 'de'
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == current_user.id,
        Transaction.is_recurring == True,
    ).first()

    if not transaction:
        raise HTTPException(status_code=404, detail=get_error_message("recurring_transaction_not_found", language))

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
    language = getattr(current_user, 'language', 'de') or 'de'
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == current_user.id,
        Transaction.is_recurring == True,
    ).first()

    if not transaction:
        raise HTTPException(status_code=404, detail=get_error_message("recurring_transaction_not_found", language))

    transaction.recurring_is_active = True
    db.commit()
    db.refresh(transaction)
    return transaction
