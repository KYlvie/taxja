"""Tests for transaction CRUD endpoints"""
import pytest
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import text
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.credit_balance import CreditBalance
from app.models.credit_cost_config import CreditCostConfig
from app.models.bank_statement_import import (
    BankStatementImport,
    BankStatementImportSourceType,
    BankStatementLine,
    BankStatementLineStatus,
    BankStatementSuggestedAction,
)
from app.models.recurring_transaction import RecurringTransaction, RecurringTransactionType
from app.models.transaction_line_item import (
    LineItemAllocationSource,
    LineItemPostingType,
    TransactionLineItem,
)
from app.models.user import User, UserType
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.models.user_classification_rule import UserClassificationRule
from app.models.user_deductibility_rule import UserDeductibilityRule
from app.models.usage_record import UsageRecord
from app.core.security import get_password_hash, create_access_token
from app.services.deductibility_checker import DeductibilityChecker


@pytest.fixture
def test_user(db: Session) -> User:
    """Create a test user"""
    existing_cost = (
        db.query(CreditCostConfig)
        .filter(CreditCostConfig.operation == "transaction_entry")
        .first()
    )
    if existing_cost is None:
        db.add(
            CreditCostConfig(
                operation="transaction_entry",
                credit_cost=1,
                description="Test transaction entry cost",
                is_active=True,
            )
        )

    user = User(
        email="test@example.com",
        password_hash=get_password_hash("TestPassword123"),
        name="Test User",
        user_type=UserType.EMPLOYEE
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    db.add(
        CreditBalance(
            user_id=user.id,
            plan_balance=100,
            topup_balance=0,
            overage_enabled=False,
        )
    )
    db.commit()

    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict:
    """Create authentication headers with JWT token"""
    access_token = create_access_token(data={"sub": test_user.email})
    return {"Authorization": f"Bearer {access_token}"}


def _make_bank_import_line(
    db: Session,
    user: User,
    *,
    transaction_id: int | None = None,
    review_status: BankStatementLineStatus = BankStatementLineStatus.PENDING_REVIEW,
    suggested_action: BankStatementSuggestedAction = BankStatementSuggestedAction.CREATE_NEW,
    amount: Decimal = Decimal("100.00"),
) -> BankStatementLine:
    statement_import = BankStatementImport(
        user_id=user.id,
        source_type=BankStatementImportSourceType.CSV,
        tax_year=2026,
    )
    db.add(statement_import)
    db.flush()

    line = BankStatementLine(
        import_id=statement_import.id,
        line_date=date(2026, 1, 15),
        amount=amount,
        counterparty="Test counterparty",
        purpose="Test purpose",
        raw_reference="REF-123",
        normalized_fingerprint=f"fp-{statement_import.id}-{amount}",
        review_status=review_status,
        suggested_action=suggested_action,
        linked_transaction_id=transaction_id,
        created_transaction_id=transaction_id if review_status == BankStatementLineStatus.AUTO_CREATED else None,
    )
    db.add(line)
    db.commit()
    db.refresh(line)
    return line

def test_create_income_transaction(client: TestClient, auth_headers: dict, db: Session):
    """Test creating an income transaction"""
    starting_usage_records = db.query(UsageRecord).count()
    transaction_data = {
        "type": "income",
        "amount": 3000.50,
        "transaction_date": "2026-01-15",
        "description": "Monthly salary",
        "income_category": "employment",
        "is_deductible": False
    }
    
    response = client.post(
        "/api/v1/transactions",
        json=transaction_data,
        headers=auth_headers
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "income"
    assert Decimal(data["amount"]) == Decimal("3000.50")
    assert data["income_category"] == "employment"
    assert data["description"] == "Monthly salary"
    assert "id" in data
    assert "created_at" in data
    assert "X-Credits-Remaining" in response.headers
    assert db.query(UsageRecord).count() == starting_usage_records


def test_create_expense_transaction(client: TestClient, auth_headers: dict, db: Session):
    """Test creating an expense transaction"""
    transaction_data = {
        "type": "expense",
        "amount": 150.75,
        "transaction_date": "2026-01-20",
        "description": "Office supplies",
        "expense_category": "office_supplies",
        "is_deductible": True,
        "deduction_reason": "Business expense",
        "vat_rate": 0.20,
        "vat_amount": 25.13
    }
    
    response = client.post(
        "/api/v1/transactions",
        json=transaction_data,
        headers=auth_headers
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "expense"
    assert Decimal(data["amount"]) == Decimal("150.75")
    assert data["expense_category"] == "office_supplies"
    assert data["is_deductible"] is True
    assert Decimal(data["vat_rate"]) == Decimal("0.2000")


def test_create_liability_repayment_transaction_without_categories(
    client: TestClient,
    auth_headers: dict,
    db: Session,
):
    """New liability transaction types should be creatable without income/expense categories."""
    transaction_data = {
        "type": "liability_repayment",
        "amount": 602.08,
        "transaction_date": "2026-01-20",
        "description": "Loan principal repayment",
        "is_recurring": True,
        "recurring_frequency": "monthly",
        "recurring_start_date": "2026-01-20",
    }

    response = client.post(
        "/api/v1/transactions",
        json=transaction_data,
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "liability_repayment"
    assert data["income_category"] is None
    assert data["expense_category"] is None
    assert data["is_deductible"] is False

    recurring = db.query(RecurringTransaction).filter(
        RecurringTransaction.id == data["source_recurring_id"]
    ).one()
    assert recurring.recurring_type == RecurringTransactionType.MANUAL
    assert recurring.transaction_type == "liability_repayment"
    assert recurring.category == "liability_repayment"


def test_create_transaction_missing_category(client: TestClient, auth_headers: dict):
    """Test that creating a transaction without required category fails"""
    transaction_data = {
        "type": "income",
        "amount": 1000.00,
        "transaction_date": "2026-01-15",
        "description": "Test"
    }
    
    response = client.post(
        "/api/v1/transactions",
        json=transaction_data,
        headers=auth_headers
    )
    
    assert response.status_code == 422


def test_create_transaction_invalid_amount(client: TestClient, auth_headers: dict):
    """Test that creating a transaction with negative amount fails"""
    transaction_data = {
        "type": "expense",
        "amount": -100.00,
        "transaction_date": "2026-01-15",
        "expense_category": "office_supplies"
    }
    
    response = client.post(
        "/api/v1/transactions",
        json=transaction_data,
        headers=auth_headers
    )
    
    assert response.status_code == 422  # Validation error


def test_get_transactions(client: TestClient, auth_headers: dict, test_user: User, db: Session):
    """Test getting list of transactions"""
    # Create test transactions
    transactions = [
        Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=Decimal("3000.00"),
            transaction_date=date(2026, 1, 15),
            description="Salary",
            income_category=IncomeCategory.EMPLOYMENT
        ),
        Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("150.00"),
            transaction_date=date(2026, 1, 20),
            description="Office supplies",
            expense_category=ExpenseCategory.OFFICE_SUPPLIES,
            is_deductible=True
        )
    ]
    
    for txn in transactions:
        db.add(txn)
    db.commit()
    
    response = client.get("/api/v1/transactions", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["transactions"]) == 2
    assert data["page"] == 1
    assert data["total_pages"] == 1


def test_get_transactions_accepts_legacy_lowercase_line_item_enums(
    client: TestClient,
    auth_headers: dict,
    test_user: User,
    db: Session,
):
    """List endpoint should tolerate rows written with lowercase enum values."""
    transaction = Transaction(
        user_id=test_user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("150.00"),
        transaction_date=date(2026, 1, 20),
        description="Office supplies",
        expense_category=ExpenseCategory.OFFICE_SUPPLIES,
        is_deductible=True,
    )
    db.add(transaction)
    db.flush()

    line_item = TransactionLineItem(
        transaction_id=transaction.id,
        description="Pens",
        amount=Decimal("150.00"),
        quantity=1,
        posting_type=LineItemPostingType.EXPENSE,
        allocation_source=LineItemAllocationSource.MANUAL,
        category=ExpenseCategory.OFFICE_SUPPLIES.value,
        is_deductible=True,
    )
    db.add(line_item)
    db.commit()

    db.execute(
        text(
            """
            UPDATE transaction_line_items
            SET posting_type = :posting_type,
                allocation_source = :allocation_source
            WHERE id = :line_item_id
            """
        ),
        {
            "posting_type": "expense",
            "allocation_source": "manual",
            "line_item_id": line_item.id,
        },
    )
    db.commit()

    response = client.get(
        "/api/v1/transactions?page=1&page_size=20",
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["transactions"][0]["line_items"][0]["posting_type"] == "expense"


def test_get_transactions_with_filters(client: TestClient, auth_headers: dict, test_user: User, db: Session):
    """Test getting transactions with filters"""
    # Create test transactions
    transactions = [
        Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=Decimal("3000.00"),
            transaction_date=date(2026, 1, 15),
            income_category=IncomeCategory.EMPLOYMENT
        ),
        Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("150.00"),
            transaction_date=date(2026, 1, 20),
            expense_category=ExpenseCategory.OFFICE_SUPPLIES,
            is_deductible=True
        ),
        Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("50.00"),
            transaction_date=date(2026, 1, 25),
            expense_category=ExpenseCategory.GROCERIES,
            is_deductible=False
        )
    ]
    
    for txn in transactions:
        db.add(txn)
    db.commit()
    
    # Filter by type
    response = client.get("/api/v1/transactions?type=expense", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    
    # Filter by deductibility
    response = client.get("/api/v1/transactions?is_deductible=true", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    
    # Filter by date range
    response = client.get(
        "/api/v1/transactions?date_from=2026-01-20&date_to=2026-01-25",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2


def test_get_transaction_by_id(client: TestClient, auth_headers: dict, test_user: User, db: Session):
    """Test getting a specific transaction by ID"""
    transaction = Transaction(
        user_id=test_user.id,
        type=TransactionType.INCOME,
        amount=Decimal("3000.00"),
        transaction_date=date(2026, 1, 15),
        description="Salary",
        income_category=IncomeCategory.EMPLOYMENT
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    
    response = client.get(f"/api/v1/transactions/{transaction.id}", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == transaction.id
    assert data["description"] == "Salary"


def test_get_nonexistent_transaction(client: TestClient, auth_headers: dict):
    """Test getting a transaction that doesn't exist"""
    response = client.get("/api/v1/transactions/99999", headers=auth_headers)
    assert response.status_code == 404


def test_update_transaction(client: TestClient, auth_headers: dict, test_user: User, db: Session):
    """Test updating a transaction"""
    transaction = Transaction(
        user_id=test_user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("100.00"),
        transaction_date=date(2026, 1, 15),
        description="Original description",
        expense_category=ExpenseCategory.OFFICE_SUPPLIES,
        is_deductible=False
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    
    update_data = {
        "amount": 150.50,
        "description": "Updated description",
        "is_deductible": True,
        "deduction_reason": "Business expense"
    }
    
    response = client.put(
        f"/api/v1/transactions/{transaction.id}",
        json=update_data,
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["amount"]) == Decimal("150.50")
    assert data["description"] == "Updated description"
    assert data["is_deductible"] is True
    assert data["deduction_reason"] == "Business expense"
    assert data["reviewed"] is True
    assert data["locked"] is True
    assert data["needs_review"] is False


def test_update_transaction_returns_400_for_line_item_reconciliation_mismatch(
    client: TestClient,
    auth_headers: dict,
    test_user: User,
    db: Session,
):
    """Line-item totals that do not match the parent amount should be a 400, not a 500."""
    transaction = Transaction(
        user_id=test_user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("225.60"),
        transaction_date=date(2026, 1, 15),
        description="BRUNN",
        expense_category=ExpenseCategory.PROFESSIONAL_SERVICES,
        is_deductible=True,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    response = client.put(
        f"/api/v1/transactions/{transaction.id}",
        json={
            "line_items": [
                {
                    "description": "Original item",
                    "amount": 225.60,
                    "quantity": 1,
                    "category": "professional_services",
                    "is_deductible": True,
                },
                {
                    "description": "Added item",
                    "amount": 111.00,
                    "quantity": 1,
                    "category": "professional_services",
                    "is_deductible": False,
                },
            ],
        },
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "Line items do not reconcile with the parent amount" in response.json()["detail"]


def test_update_transaction_category_change_with_line_items_locks_and_cascades(
    client: TestClient,
    auth_headers: dict,
    test_user: User,
    db: Session,
):
    """Manual parent category corrections should survive legacy uppercase line-item categories."""
    transaction = Transaction(
        user_id=test_user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("68.32"),
        transaction_date=date(2026, 1, 15),
        description="Eni Service-Station",
        expense_category=ExpenseCategory.OTHER,
        is_deductible=False,
        needs_review=True,
        reviewed=False,
        locked=False,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    db.add(
        TransactionLineItem(
            transaction_id=transaction.id,
            description="Diesel fuel purchase",
            amount=Decimal("68.32"),
            quantity=1,
            posting_type=LineItemPostingType.EXPENSE,
            allocation_source=LineItemAllocationSource.MANUAL,
            category=ExpenseCategory.OTHER.value,
            is_deductible=False,
            deduction_reason="Initial automatic guess",
            sort_order=0,
        )
    )
    db.commit()

    response = client.put(
        f"/api/v1/transactions/{transaction.id}",
        json={
            "expense_category": "fuel",
            "line_items": [
                {
                    "description": "Diesel fuel purchase",
                    "amount": 68.32,
                    "quantity": 1,
                    "posting_type": "expense",
                    "allocation_source": "manual",
                    "category": "OTHER",
                    "is_deductible": True,
                    "deduction_reason": "Guest transport for lodging business",
                    "sort_order": 0,
                }
            ],
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["expense_category"] == "fuel"
    assert payload["reviewed"] is True
    assert payload["locked"] is True
    assert payload["needs_review"] is False
    assert payload["is_deductible"] is True

    db.refresh(transaction)
    updated_line_items = (
        db.query(TransactionLineItem)
        .filter(TransactionLineItem.transaction_id == transaction.id)
        .order_by(TransactionLineItem.sort_order.asc())
        .all()
    )
    assert len(updated_line_items) == 1
    assert updated_line_items[0].category == "fuel"
    assert updated_line_items[0].is_deductible is True


def test_update_transaction_first_category_assignment_creates_rule(
    client: TestClient,
    auth_headers: dict,
    test_user: User,
    db: Session,
):
    """Assigning a first category to a legacy uncategorized transaction should learn a rule."""
    transaction = Transaction(
        user_id=test_user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("64.03"),
        transaction_date=date(2026, 1, 15),
        description="INTERSPAR breakfast groceries",
        expense_category=None,
        income_category=None,
        is_deductible=False,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    response = client.put(
        f"/api/v1/transactions/{transaction.id}",
        json={"expense_category": "groceries"},
        headers=auth_headers,
    )

    assert response.status_code == 200

    learned_rule = (
        db.query(UserClassificationRule)
        .filter(
            UserClassificationRule.user_id == test_user.id,
            UserClassificationRule.txn_type == "expense",
            UserClassificationRule.category == "groceries",
        )
        .first()
    )
    assert learned_rule is not None
    assert learned_rule.original_description == "INTERSPAR breakfast groceries"


def test_update_transaction_deductibility_override_is_remembered(
    client: TestClient,
    auth_headers: dict,
    test_user: User,
    db: Session,
):
    """A manual deductible/non-deductible correction should create a reusable override rule."""
    transaction = Transaction(
        user_id=test_user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("89.00"),
        transaction_date=date(2026, 1, 15),
        description="OMV guest shuttle fuel",
        expense_category=ExpenseCategory.VEHICLE,
        is_deductible=False,
        deduction_reason="Use Pendlerpauschale",
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    response = client.put(
        f"/api/v1/transactions/{transaction.id}",
        json={
            "is_deductible": True,
            "deduction_reason": "Guest transport for lodging business",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200

    learned_rule = (
        db.query(UserDeductibilityRule)
        .filter(
            UserDeductibilityRule.user_id == test_user.id,
            UserDeductibilityRule.expense_category == "vehicle",
        )
        .first()
    )
    assert learned_rule is not None
    assert learned_rule.is_deductible is True
    assert learned_rule.original_description == "OMV guest shuttle fuel"

    checker = DeductibilityChecker(db=db)
    result = checker.check(
        "vehicle",
        test_user.user_type.value,
        description="OMV guest shuttle fuel",
        user_id=test_user.id,
    )
    assert result.is_deductible is True
    assert "Guest transport" in result.reason


def test_update_transaction_can_skip_rule_learning_for_document_sync(
    client: TestClient,
    auth_headers: dict,
    test_user: User,
    db: Session,
):
    """Document-originated sync updates should not double-learn user rules."""
    transaction = Transaction(
        user_id=test_user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("237.90"),
        transaction_date=date(2026, 1, 15),
        description="ÖAMTC: Purchase of VARTA battery and coolant",
        expense_category=ExpenseCategory.OTHER,
        is_deductible=False,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    response = client.put(
        f"/api/v1/transactions/{transaction.id}",
        json={
            "expense_category": "other",
            "reviewed": True,
            "locked": True,
            "suppress_rule_learning": True,
            "line_items": [
                {
                    "description": "VARTA ABA71 BLUE DYN EFB",
                    "amount": 222.00,
                    "quantity": 1,
                    "posting_type": "expense",
                    "allocation_source": "manual",
                    "category": "other",
                    "is_deductible": False,
                    "deduction_reason": "Battery purchase is not deductible.",
                    "sort_order": 0,
                },
                {
                    "description": "KÜHLERFROSTSCHUTZ MC30 1,5l.",
                    "amount": 15.90,
                    "quantity": 1,
                    "posting_type": "expense",
                    "allocation_source": "manual",
                    "category": "other",
                    "is_deductible": False,
                    "deduction_reason": "Battery purchase is not deductible.",
                    "sort_order": 1,
                },
            ],
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert (
        db.query(UserClassificationRule)
        .filter(UserClassificationRule.user_id == test_user.id)
        .count()
        == 0
    )
    assert (
        db.query(UserDeductibilityRule)
        .filter(UserDeductibilityRule.user_id == test_user.id)
        .count()
        == 0
    )


def test_update_transaction_to_liability_repayment_clears_expense_fields(
    client: TestClient,
    auth_headers: dict,
    test_user: User,
    db: Session,
):
    """Changing an expense into principal repayment must clear expense-only semantics."""
    transaction = Transaction(
        user_id=test_user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("1508.33"),
        transaction_date=date(2026, 1, 15),
        description="Monthly loan payment",
        expense_category=ExpenseCategory.LOAN_INTEREST,
        is_deductible=True,
        deduction_reason="Old incorrect expense classification",
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    response = client.put(
        f"/api/v1/transactions/{transaction.id}",
        json={
            "type": "liability_repayment",
            "description": "Monthly principal repayment",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "liability_repayment"
    assert data["expense_category"] is None
    assert data["income_category"] is None
    assert data["is_deductible"] is False
    assert data["deduction_reason"] is None


def test_delete_transaction(client: TestClient, auth_headers: dict, test_user: User, db: Session):
    """Test deleting a transaction"""
    transaction = Transaction(
        user_id=test_user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("100.00"),
        transaction_date=date(2026, 1, 15),
        expense_category=ExpenseCategory.OFFICE_SUPPLIES
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    
    response = client.delete(f"/api/v1/transactions/{transaction.id}", headers=auth_headers)
    
    assert response.status_code == 204
    
    # Verify transaction is deleted
    deleted_txn = db.query(Transaction).filter(Transaction.id == transaction.id).first()
    assert deleted_txn is None


def test_delete_transaction_resets_auto_created_bank_line(
    client: TestClient,
    auth_headers: dict,
    test_user: User,
    db: Session,
):
    transaction = Transaction(
        user_id=test_user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("100.00"),
        transaction_date=date(2026, 1, 15),
        description="Bank import created expense",
        expense_category=ExpenseCategory.OTHER,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    line = _make_bank_import_line(
        db,
        test_user,
        transaction_id=transaction.id,
        review_status=BankStatementLineStatus.AUTO_CREATED,
    )

    response = client.delete(f"/api/v1/transactions/{transaction.id}", headers=auth_headers)

    assert response.status_code == 204

    db.refresh(line)
    assert line.review_status == BankStatementLineStatus.PENDING_REVIEW
    assert line.suggested_action == BankStatementSuggestedAction.CREATE_NEW
    assert line.linked_transaction_id is None
    assert line.created_transaction_id is None
    assert line.reviewed_at is None
    assert line.reviewed_by is None


def test_batch_delete_transactions_resets_bank_statement_lines(
    client: TestClient,
    auth_headers: dict,
    test_user: User,
    db: Session,
):
    matched_transaction = Transaction(
        user_id=test_user.id,
        type=TransactionType.INCOME,
        amount=Decimal("2400.00"),
        transaction_date=date(2026, 1, 18),
        description="Matched rent",
        income_category=IncomeCategory.EMPLOYMENT,
    )
    candidate_transaction = Transaction(
        user_id=test_user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("55.10"),
        transaction_date=date(2026, 1, 19),
        description="Suggested candidate",
        expense_category=ExpenseCategory.OTHER,
    )
    db.add_all([matched_transaction, candidate_transaction])
    db.commit()
    db.refresh(matched_transaction)
    db.refresh(candidate_transaction)

    matched_line = _make_bank_import_line(
        db,
        test_user,
        transaction_id=matched_transaction.id,
        review_status=BankStatementLineStatus.MATCHED_EXISTING,
        suggested_action=BankStatementSuggestedAction.MATCH_EXISTING,
        amount=Decimal("2400.00"),
    )
    candidate_line = _make_bank_import_line(
        db,
        test_user,
        transaction_id=candidate_transaction.id,
        review_status=BankStatementLineStatus.PENDING_REVIEW,
        suggested_action=BankStatementSuggestedAction.MATCH_EXISTING,
        amount=Decimal("55.10"),
    )

    precheck = client.post(
        "/api/v1/transactions/batch-delete",
        json={"ids": [matched_transaction.id, candidate_transaction.id]},
        headers=auth_headers,
    )
    assert precheck.status_code == 200

    response = client.post(
        "/api/v1/transactions/batch-delete",
        json={"ids": [matched_transaction.id, candidate_transaction.id], "force": True},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert set(response.json()["deleted"]) == {matched_transaction.id, candidate_transaction.id}

    db.refresh(matched_line)
    db.refresh(candidate_line)

    assert matched_line.review_status == BankStatementLineStatus.PENDING_REVIEW
    assert matched_line.suggested_action == BankStatementSuggestedAction.CREATE_NEW
    assert matched_line.linked_transaction_id is None
    assert matched_line.created_transaction_id is None

    assert candidate_line.review_status == BankStatementLineStatus.PENDING_REVIEW
    assert candidate_line.suggested_action == BankStatementSuggestedAction.CREATE_NEW
    assert candidate_line.linked_transaction_id is None
    assert candidate_line.created_transaction_id is None


def test_unauthorized_access(client: TestClient):
    """Test that endpoints require authentication"""
    response = client.get("/api/v1/transactions")
    assert response.status_code == 401
    
    response = client.post("/api/v1/transactions", json={})
    assert response.status_code == 401


def test_user_can_only_access_own_transactions(client: TestClient, db: Session):
    """Test that users can only access their own transactions"""
    # Create two users
    user1 = User(
        email="user1@example.com",
        password_hash=get_password_hash("Password123"),
        name="User 1",
        user_type=UserType.EMPLOYEE
    )
    user2 = User(
        email="user2@example.com",
        password_hash=get_password_hash("Password123"),
        name="User 2",
        user_type=UserType.EMPLOYEE
    )
    db.add(user1)
    db.add(user2)
    db.commit()
    
    # Create transaction for user2
    transaction = Transaction(
        user_id=user2.id,
        type=TransactionType.INCOME,
        amount=Decimal("1000.00"),
        transaction_date=date(2026, 1, 15),
        income_category=IncomeCategory.EMPLOYMENT
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    
    # Try to access user2's transaction as user1
    token = create_access_token(data={"sub": user1.email})
    headers = {"Authorization": f"Bearer {token}"}
    
    response = client.get(f"/api/v1/transactions/{transaction.id}", headers=headers)
    assert response.status_code == 404  # Should not find transaction
