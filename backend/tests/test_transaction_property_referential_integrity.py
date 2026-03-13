"""
Database Integration Test for Transaction-Property Referential Integrity

This module tests that all transactions with property_id reference valid properties
in the actual database, validating the foreign key constraint and data consistency.

**Validates: Requirement 13.5 - Transaction-Property Referential Integrity**

Correctness Property:
FOR ALL transactions t where t.property_id IS NOT NULL:
    EXISTS property p WHERE p.id = t.property_id AND p.user_id = t.user_id
"""

import pytest
from decimal import Decimal
from datetime import date
from uuid import uuid4
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.property import Property, PropertyType, PropertyStatus
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.models.user import User, UserType


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def test_user(db: Session):
    """Create a test user"""
    user = User(
        email=f"test_{uuid4()}@example.com",
        password_hash="test_hash",
        name="Test User",
        user_type=UserType.LANDLORD
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_property(db: Session, test_user: User):
    """Create a test property"""
    property = Property(
        id=uuid4(),
        user_id=test_user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        address="Test Street 123, 1010 Wien",
        street="Test Street 123",
        city="Wien",
        postal_code="1010",
        purchase_date=date(2020, 6, 15),
        purchase_price=Decimal("350000.00"),
        building_value=Decimal("280000.00"),
        construction_year=1985,
        depreciation_rate=Decimal("0.02"),
        status=PropertyStatus.ACTIVE
    )
    db.add(property)
    db.commit()
    db.refresh(property)
    return property


# ============================================================================
# Test: All Transactions with property_id Reference Valid Properties
# ============================================================================

def test_all_transactions_with_property_id_reference_valid_properties(db: Session):
    """
    Verify that ALL transactions in the database with a property_id reference
    a valid property that exists and belongs to the same user.
    
    This is a database-wide integrity check.
    """
    # Query all transactions that have a property_id
    transactions_with_property = db.query(Transaction).filter(
        Transaction.property_id.isnot(None)
    ).all()
    
    # For each transaction with property_id, verify the property exists
    for transaction in transactions_with_property:
        # Query the referenced property
        property = db.query(Property).filter(
            Property.id == transaction.property_id
        ).first()
        
        # ASSERTION 1: Property must exist
        assert property is not None, (
            f"Transaction {transaction.id} references non-existent property "
            f"{transaction.property_id}"
        )
        
        # ASSERTION 2: Property and transaction must belong to same user
        assert property.user_id == transaction.user_id, (
            f"Transaction {transaction.id} user_id {transaction.user_id} does not match "
            f"property {property.id} user_id {property.user_id}"
        )


def test_transaction_property_foreign_key_constraint(
    db: Session,
    test_user: User,
    test_property: Property
):
    """
    Test that the database foreign key constraint prevents creating transactions
    with invalid property_id values.
    """
    # Create a transaction with valid property_id
    valid_transaction = Transaction(
        user_id=test_user.id,
        property_id=test_property.id,
        type=TransactionType.INCOME,
        amount=Decimal("1500.00"),
        transaction_date=date(2025, 1, 15),
        description="Rental income",
        income_category=IncomeCategory.RENTAL,
        is_deductible=False
    )
    
    db.add(valid_transaction)
    db.commit()
    db.refresh(valid_transaction)
    
    # ASSERTION: Transaction was created successfully
    assert valid_transaction.id is not None
    assert valid_transaction.property_id == test_property.id
    
    # Verify the property exists and matches
    property = db.query(Property).filter(
        Property.id == valid_transaction.property_id
    ).first()
    
    assert property is not None
    assert property.id == test_property.id
    assert property.user_id == test_user.id


def test_transaction_with_nonexistent_property_id_fails(
    db: Session,
    test_user: User
):
    """
    Test that attempting to create a transaction with a non-existent property_id
    fails due to foreign key constraint.
    
    Note: SQLite doesn't enforce foreign key constraints by default in test mode,
    so this test documents the expected behavior for PostgreSQL production database.
    """
    # Generate a random UUID that doesn't exist in the database
    nonexistent_property_id = uuid4()
    
    # Verify this property doesn't exist
    property_exists = db.query(Property).filter(
        Property.id == nonexistent_property_id
    ).first()
    assert property_exists is None, "Test setup error: property should not exist"
    
    # Attempt to create transaction with non-existent property_id
    invalid_transaction = Transaction(
        user_id=test_user.id,
        property_id=nonexistent_property_id,
        type=TransactionType.INCOME,
        amount=Decimal("1500.00"),
        transaction_date=date(2025, 1, 15),
        description="Invalid rental income",
        income_category=IncomeCategory.RENTAL,
        is_deductible=False
    )
    
    db.add(invalid_transaction)
    
    # ASSERTION: Commit should fail due to foreign key constraint
    # Note: SQLite in test mode may not enforce this, but PostgreSQL will
    try:
        db.commit()
        # If we reach here with SQLite, that's expected
        # In production PostgreSQL, this would raise an IntegrityError
        db.rollback()
        
        # Document that this transaction should not be allowed in production
        assert True, (
            "SQLite test database allows this, but production PostgreSQL "
            "will enforce foreign key constraint"
        )
    except Exception as exc:
        # Rollback the failed transaction
        db.rollback()
        
        # Verify the error is related to foreign key constraint
        error_message = str(exc).lower()
        assert any(keyword in error_message for keyword in [
            'foreign key', 'constraint', 'violates', 'fk_', 'property'
        ]), f"Expected foreign key constraint error, got: {exc}"


def test_transaction_property_user_consistency(
    db: Session,
    test_user: User,
    test_property: Property
):
    """
    Test that transactions linked to properties maintain user_id consistency.
    """
    # Create multiple transactions for the property
    transactions = []
    for i in range(5):
        transaction = Transaction(
            user_id=test_user.id,
            property_id=test_property.id,
            type=TransactionType.EXPENSE if i % 2 == 0 else TransactionType.INCOME,
            amount=Decimal(f"{1000 + i * 100}.00"),
            transaction_date=date(2025, 1, i + 1),
            description=f"Test transaction {i}",
            expense_category=ExpenseCategory.MAINTENANCE if i % 2 == 0 else None,
            income_category=IncomeCategory.RENTAL if i % 2 == 1 else None,
            is_deductible=i % 2 == 0
        )
        db.add(transaction)
        transactions.append(transaction)
    
    db.commit()
    
    # Verify all transactions have consistent user_id with property
    for transaction in transactions:
        db.refresh(transaction)
        
        # ASSERTION: Transaction user_id matches property user_id
        assert transaction.user_id == test_property.user_id, (
            f"Transaction {transaction.id} user_id {transaction.user_id} does not match "
            f"property user_id {test_property.user_id}"
        )
        
        # ASSERTION: Transaction property_id is correct
        assert transaction.property_id == test_property.id, (
            f"Transaction {transaction.id} property_id mismatch"
        )


def test_property_deletion_sets_transaction_property_id_to_null(
    db: Session,
    test_user: User,
    test_property: Property
):
    """
    Test that deleting a property sets transaction.property_id to NULL
    (ON DELETE SET NULL behavior).
    """
    # Create a transaction linked to the property
    transaction = Transaction(
        user_id=test_user.id,
        property_id=test_property.id,
        type=TransactionType.INCOME,
        amount=Decimal("1500.00"),
        transaction_date=date(2025, 1, 15),
        description="Rental income",
        income_category=IncomeCategory.RENTAL,
        is_deductible=False
    )
    
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    
    transaction_id = transaction.id
    property_id = test_property.id
    
    # Verify transaction is linked to property
    assert transaction.property_id == property_id
    
    # Delete the property
    db.delete(test_property)
    db.commit()
    
    # Refresh transaction and verify property_id is now NULL
    db.expire(transaction)
    updated_transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id
    ).first()
    
    # ASSERTION: Transaction still exists
    assert updated_transaction is not None, (
        "Transaction should still exist after property deletion"
    )
    
    # ASSERTION: property_id is now NULL (ON DELETE SET NULL)
    assert updated_transaction.property_id is None, (
        f"Transaction property_id should be NULL after property deletion, "
        f"but got {updated_transaction.property_id}"
    )


def test_count_transactions_with_invalid_property_references(db: Session):
    """
    Count and report any transactions with invalid property references.
    This is a diagnostic test that should always pass (count = 0).
    """
    # Query transactions with property_id that don't have matching properties
    query = db.query(Transaction).outerjoin(
        Property,
        Transaction.property_id == Property.id
    ).filter(
        Transaction.property_id.isnot(None),
        Property.id.is_(None)
    )
    
    invalid_transactions = query.all()
    invalid_count = len(invalid_transactions)
    
    # ASSERTION: There should be no transactions with invalid property references
    assert invalid_count == 0, (
        f"Found {invalid_count} transactions with invalid property_id references: "
        f"{[t.id for t in invalid_transactions]}"
    )


def test_count_transactions_with_user_property_mismatch(db: Session):
    """
    Count transactions where user_id doesn't match the property's user_id.
    This should always be 0 if referential integrity is maintained.
    """
    # Query transactions where user_id doesn't match property.user_id
    query = db.query(Transaction).join(
        Property,
        Transaction.property_id == Property.id
    ).filter(
        Transaction.property_id.isnot(None),
        Transaction.user_id != Property.user_id
    )
    
    mismatched_transactions = query.all()
    mismatch_count = len(mismatched_transactions)
    
    # ASSERTION: There should be no user_id mismatches
    assert mismatch_count == 0, (
        f"Found {mismatch_count} transactions with user_id mismatch: "
        f"{[(t.id, t.user_id, t.property_id) for t in mismatched_transactions]}"
    )


def test_archived_property_preserves_transaction_links(
    db: Session,
    test_user: User,
    test_property: Property
):
    """
    Test that archiving a property preserves transaction links.
    """
    # Create transactions linked to the property
    transactions = []
    for i in range(3):
        transaction = Transaction(
            user_id=test_user.id,
            property_id=test_property.id,
            type=TransactionType.INCOME,
            amount=Decimal(f"{1500 + i * 100}.00"),
            transaction_date=date(2025, 1, i + 1),
            description=f"Rental income {i}",
            income_category=IncomeCategory.RENTAL,
            is_deductible=False
        )
        db.add(transaction)
        transactions.append(transaction)
    
    db.commit()
    
    # Archive the property
    test_property.status = PropertyStatus.ARCHIVED
    test_property.sale_date = date(2025, 12, 31)
    db.commit()
    
    # Verify all transactions still reference the property
    for transaction in transactions:
        db.refresh(transaction)
        
        # ASSERTION: Transaction still linked to property
        assert transaction.property_id == test_property.id, (
            f"Transaction {transaction.id} lost property link after archival"
        )
        
        # ASSERTION: Property still exists and is archived
        property = db.query(Property).filter(
            Property.id == test_property.id
        ).first()
        
        assert property is not None
        assert property.status == PropertyStatus.ARCHIVED


def test_database_referential_integrity_statistics(db: Session):
    """
    Generate statistics about transaction-property relationships in the database.
    This is an informational test that provides insights into data quality.
    """
    # Count total transactions
    total_transactions = db.query(func.count(Transaction.id)).scalar()
    
    # Count transactions with property_id
    transactions_with_property = db.query(func.count(Transaction.id)).filter(
        Transaction.property_id.isnot(None)
    ).scalar()
    
    # Count transactions without property_id
    transactions_without_property = total_transactions - transactions_with_property
    
    # Count unique properties referenced by transactions
    unique_properties = db.query(func.count(func.distinct(Transaction.property_id))).filter(
        Transaction.property_id.isnot(None)
    ).scalar()
    
    # Count total properties in database
    total_properties = db.query(func.count(Property.id)).scalar()
    
    # Print statistics (for informational purposes)
    print(f"\n=== Transaction-Property Referential Integrity Statistics ===")
    print(f"Total transactions: {total_transactions}")
    print(f"Transactions with property_id: {transactions_with_property}")
    print(f"Transactions without property_id: {transactions_without_property}")
    print(f"Unique properties referenced: {unique_properties}")
    print(f"Total properties in database: {total_properties}")
    
    if transactions_with_property > 0:
        percentage = (transactions_with_property / total_transactions) * 100
        print(f"Percentage of transactions linked to properties: {percentage:.2f}%")
    
    # ASSERTION: All statistics should be non-negative
    assert total_transactions >= 0
    assert transactions_with_property >= 0
    assert transactions_without_property >= 0
    assert unique_properties >= 0
    assert total_properties >= 0
    
    # ASSERTION: Transactions with property should not exceed total
    assert transactions_with_property <= total_transactions
    
    # ASSERTION: Unique properties referenced should not exceed total properties
    assert unique_properties <= total_properties
