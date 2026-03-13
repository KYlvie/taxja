"""
Shared model fixtures for E2E and integration tests.

This module provides factory functions and fixtures for creating test data
with proper handling of relationships and dependencies.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
import pytest
from sqlalchemy.orm import Session

from app.models.user import User, UserType
from app.models.property import Property, PropertyType, PropertyStatus
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.models.document import Document, DocumentType


def create_test_user(
    db_session: Session,
    email: str = "test@example.com",
    name: str = "Test User",
    user_type: UserType = UserType.LANDLORD,
    **kwargs
) -> User:
    """
    Factory function to create a test user.
    
    Args:
        db_session: Database session
        email: User email (must be unique)
        name: User name
        user_type: Type of user
        **kwargs: Additional user fields
    
    Returns:
        Created and committed User instance
    """
    user = User(
        email=email,
        name=name,
        password_hash="hashed_password_test",
        user_type=user_type,
        **kwargs
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def create_test_property(
    db_session: Session,
    user: User,
    street: str = "Teststraße 123",
    city: str = "Wien",
    postal_code: str = "1010",
    purchase_date: date = date(2024, 1, 1),
    purchase_price: Decimal = Decimal("400000.00"),
    building_value: Optional[Decimal] = None,
    property_type: PropertyType = PropertyType.RENTAL,
    **kwargs
) -> Property:
    """
    Factory function to create a test property.
    
    Args:
        db_session: Database session
        user: Owner user
        street: Street address
        city: City
        postal_code: Postal code
        purchase_date: Purchase date
        purchase_price: Purchase price
        building_value: Building value (defaults to 80% of purchase_price)
        property_type: Type of property
        **kwargs: Additional property fields
    
    Returns:
        Created and committed Property instance
    """
    if building_value is None:
        building_value = purchase_price * Decimal("0.8")
    
    # Calculate land value
    land_value = purchase_price - building_value
    
    # Set default depreciation rate based on construction year
    if "construction_year" in kwargs:
        construction_year = kwargs["construction_year"]
        if construction_year and construction_year < 1915:
            kwargs.setdefault("depreciation_rate", Decimal("0.015"))
        else:
            kwargs.setdefault("depreciation_rate", Decimal("0.02"))
    else:
        kwargs.setdefault("depreciation_rate", Decimal("0.02"))
    
    property = Property(
        user_id=user.id,
        property_type=property_type,
        street=street,
        city=city,
        postal_code=postal_code,
        address=f"{street}, {postal_code} {city}",
        purchase_date=purchase_date,
        purchase_price=purchase_price,
        building_value=building_value,
        land_value=land_value,
        status=PropertyStatus.ACTIVE,
        **kwargs
    )
    db_session.add(property)
    db_session.commit()
    db_session.refresh(property)
    return property


def create_test_transaction(
    db_session: Session,
    user: User,
    transaction_type: TransactionType,
    amount: Decimal,
    transaction_date: date = date(2024, 1, 1),
    description: str = "Test transaction",
    property: Optional[Property] = None,
    income_category: Optional[IncomeCategory] = None,
    expense_category: Optional[ExpenseCategory] = None,
    **kwargs
) -> Transaction:
    """
    Factory function to create a test transaction.
    
    Args:
        db_session: Database session
        user: Transaction owner
        transaction_type: Income or expense
        amount: Transaction amount
        transaction_date: Transaction date
        description: Description
        property: Optional linked property
        income_category: Income category (for income transactions)
        expense_category: Expense category (for expense transactions)
        **kwargs: Additional transaction fields
    
    Returns:
        Created and committed Transaction instance
    """
    transaction = Transaction(
        user_id=user.id,
        property_id=property.id if property else None,
        type=transaction_type,
        amount=amount,
        transaction_date=transaction_date,
        description=description,
        income_category=income_category,
        expense_category=expense_category,
        **kwargs
    )
    db_session.add(transaction)
    db_session.commit()
    db_session.refresh(transaction)
    return transaction


def create_test_document(
    db_session: Session,
    user: User,
    document_type: DocumentType = DocumentType.RECEIPT,
    file_name: str = "test_document.pdf",
    file_path: str = "/test/path/document.pdf",
    **kwargs
) -> Document:
    """
    Factory function to create a test document.
    
    Args:
        db_session: Database session
        user: Document owner
        document_type: Type of document
        file_name: File name
        file_path: Storage path
        **kwargs: Additional document fields
    
    Returns:
        Created and committed Document instance
    """
    document = Document(
        user_id=user.id,
        document_type=document_type,
        file_name=file_name,
        file_path=file_path,
        uploaded_at=datetime.utcnow(),
        **kwargs
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document


# Pytest fixtures using the factory functions

@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a test landlord user."""
    return create_test_user(
        db_session,
        email="landlord@example.com",
        name="Test Landlord",
        user_type=UserType.LANDLORD
    )


@pytest.fixture
def test_employee_user(db_session: Session) -> User:
    """Create a test employee user."""
    return create_test_user(
        db_session,
        email="employee@example.com",
        name="Test Employee",
        user_type=UserType.EMPLOYEE
    )


@pytest.fixture
def test_property(db_session: Session, test_user: User) -> Property:
    """Create a test property."""
    return create_test_property(
        db_session,
        user=test_user,
        street="Mariahilfer Straße 100",
        city="Wien",
        postal_code="1060",
        purchase_date=date(2024, 1, 1),
        purchase_price=Decimal("450000.00"),
        construction_year=1995
    )


@pytest.fixture
def test_rental_income(
    db_session: Session,
    test_user: User,
    test_property: Property
) -> Transaction:
    """Create a test rental income transaction."""
    return create_test_transaction(
        db_session,
        user=test_user,
        transaction_type=TransactionType.INCOME,
        amount=Decimal("15000.00"),
        transaction_date=date(2024, 12, 31),
        description="Rental income",
        property=test_property,
        income_category=IncomeCategory.RENTAL
    )


@pytest.fixture
def test_depreciation_transaction(
    db_session: Session,
    test_user: User,
    test_property: Property
) -> Transaction:
    """Create a test depreciation transaction."""
    return create_test_transaction(
        db_session,
        user=test_user,
        transaction_type=TransactionType.EXPENSE,
        amount=Decimal("7200.00"),
        transaction_date=date(2024, 12, 31),
        description=f"AfA {test_property.address} (2024)",
        property=test_property,
        expense_category=ExpenseCategory.DEPRECIATION_AFA,
        is_deductible=True,
        is_system_generated=True
    )
