"""
Tests for dashboard property metrics functionality.

Tests the integration of property portfolio metrics into the dashboard
for landlord and mixed user types.
"""

import pytest
from decimal import Decimal
from datetime import date, datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.user import User, UserType
from app.models.property import Property, PropertyStatus, PropertyType
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.models.chat_message import ChatMessage  # noqa: F401 - needed for User relationship
from app.models.document import Document  # noqa: F401 - needed for Property relationship
from app.services.dashboard_service import DashboardService


# Test database setup
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def db():
    """Create a test database session"""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def landlord_user(db: Session) -> User:
    """Create a landlord user for testing."""
    user = User(
        email="landlord@example.com",
        password_hash="hashed_password",
        name="Test Landlord",
        user_type=UserType.LANDLORD,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def mixed_user(db: Session) -> User:
    """Create a mixed user for testing."""
    user = User(
        email="mixed@example.com",
        password_hash="hashed_password",
        name="Test Mixed User",
        user_type=UserType.MIXED,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def employee_user(db: Session) -> User:
    """Create an employee user for testing."""
    user = User(
        email="employee@example.com",
        password_hash="hashed_password",
        name="Test Employee",
        user_type=UserType.EMPLOYEE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def sample_property(db: Session, landlord_user: User) -> Property:
    """Create a sample property for testing."""
    property = Property(
        user_id=landlord_user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        street="Hauptstraße 123",
        city="Wien",
        postal_code="1010",
        address="Hauptstraße 123, 1010 Wien",
        purchase_date=date(2020, 1, 1),
        purchase_price=Decimal("350000.00"),
        building_value=Decimal("280000.00"),
        construction_year=1985,
        depreciation_rate=Decimal("0.02"),
        status=PropertyStatus.ACTIVE,
    )
    db.add(property)
    db.commit()
    db.refresh(property)
    return property


def test_get_property_metrics_no_properties(db: Session, landlord_user: User):
    """Test property metrics when user has no properties."""
    service = DashboardService(db)
    metrics = service.get_property_metrics(landlord_user.id, 2026)
    
    assert metrics["has_properties"] is False
    assert metrics["active_properties_count"] == 0
    assert metrics["total_rental_income"] == 0.0
    assert metrics["total_property_expenses"] == 0.0
    assert metrics["net_rental_income"] == 0.0
    assert metrics["total_building_value"] == 0.0
    assert metrics["total_annual_depreciation"] == 0.0


def test_get_property_metrics_with_property(db: Session, landlord_user: User, sample_property: Property):
    """Test property metrics with one property."""
    service = DashboardService(db)
    metrics = service.get_property_metrics(landlord_user.id, 2026)
    
    assert metrics["has_properties"] is True
    assert metrics["active_properties_count"] == 1
    assert metrics["total_building_value"] == 280000.00
    # Annual depreciation = 280000 * 0.02 = 5600
    assert metrics["total_annual_depreciation"] == 5600.00
    # No transactions yet
    assert metrics["total_rental_income"] == 0.0
    assert metrics["total_property_expenses"] == 0.0
    assert metrics["net_rental_income"] == 0.0


def test_get_property_metrics_with_transactions(
    db: Session, landlord_user: User, sample_property: Property
):
    """Test property metrics with rental income and expenses."""
    # Add rental income transaction
    rental_income = Transaction(
        user_id=landlord_user.id,
        property_id=sample_property.id,
        type=TransactionType.INCOME,
        income_category=IncomeCategory.RENTAL,
        amount=Decimal("12000.00"),
        transaction_date=date(2026, 6, 1),
        description="Rental income June 2026",
        is_deductible=False,
    )
    db.add(rental_income)
    
    # Add property expense transaction
    expense = Transaction(
        user_id=landlord_user.id,
        property_id=sample_property.id,
        type=TransactionType.EXPENSE,
        expense_category=ExpenseCategory.MAINTENANCE,
        amount=Decimal("2500.00"),
        transaction_date=date(2026, 7, 15),
        description="Property maintenance",
        is_deductible=True,
    )
    db.add(expense)
    db.commit()
    
    service = DashboardService(db)
    metrics = service.get_property_metrics(landlord_user.id, 2026)
    
    assert metrics["has_properties"] is True
    assert metrics["active_properties_count"] == 1
    assert metrics["total_rental_income"] == 12000.00
    assert metrics["total_property_expenses"] == 2500.00
    assert metrics["net_rental_income"] == 9500.00


def test_get_property_metrics_multiple_properties(db: Session, landlord_user: User):
    """Test property metrics with multiple properties."""
    # Create first property
    property1 = Property(
        user_id=landlord_user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        street="Hauptstraße 123",
        city="Wien",
        postal_code="1010",
        address="Hauptstraße 123, 1010 Wien",
        purchase_date=date(2020, 1, 1),
        purchase_price=Decimal("350000.00"),
        building_value=Decimal("280000.00"),
        construction_year=1985,
        depreciation_rate=Decimal("0.02"),
        status=PropertyStatus.ACTIVE,
    )
    db.add(property1)
    
    # Create second property
    property2 = Property(
        user_id=landlord_user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        street="Mariahilfer Straße 45",
        city="Wien",
        postal_code="1060",
        address="Mariahilfer Straße 45, 1060 Wien",
        purchase_date=date(2018, 6, 15),
        purchase_price=Decimal("420000.00"),
        building_value=Decimal("336000.00"),
        construction_year=1920,
        depreciation_rate=Decimal("0.015"),
        status=PropertyStatus.ACTIVE,
    )
    db.add(property2)
    db.commit()
    
    service = DashboardService(db)
    metrics = service.get_property_metrics(landlord_user.id, 2026)
    
    assert metrics["has_properties"] is True
    assert metrics["active_properties_count"] == 2
    # Total building value = 280000 + 336000 = 616000
    assert metrics["total_building_value"] == 616000.00
    # Total depreciation = (280000 * 0.02) + (336000 * 0.015) = 5600 + 5040 = 10640
    assert metrics["total_annual_depreciation"] == 10640.00


def test_get_property_metrics_excludes_archived(db: Session, landlord_user: User):
    """Test that archived properties are excluded from metrics."""
    # Create active property
    active_property = Property(
        user_id=landlord_user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        street="Hauptstraße 123",
        city="Wien",
        postal_code="1010",
        address="Hauptstraße 123, 1010 Wien",
        purchase_date=date(2020, 1, 1),
        purchase_price=Decimal("350000.00"),
        building_value=Decimal("280000.00"),
        construction_year=1985,
        depreciation_rate=Decimal("0.02"),
        status=PropertyStatus.ACTIVE,
    )
    db.add(active_property)
    
    # Create archived property
    archived_property = Property(
        user_id=landlord_user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        street="Mariahilfer Straße 45",
        city="Wien",
        postal_code="1060",
        address="Mariahilfer Straße 45, 1060 Wien",
        purchase_date=date(2018, 6, 15),
        purchase_price=Decimal("420000.00"),
        building_value=Decimal("336000.00"),
        construction_year=1920,
        depreciation_rate=Decimal("0.015"),
        status=PropertyStatus.ARCHIVED,
        sale_date=date(2025, 12, 31),
    )
    db.add(archived_property)
    db.commit()
    
    service = DashboardService(db)
    metrics = service.get_property_metrics(landlord_user.id, 2026)
    
    # Should only count active property
    assert metrics["has_properties"] is True
    assert metrics["active_properties_count"] == 1
    assert metrics["total_building_value"] == 280000.00
    assert metrics["total_annual_depreciation"] == 5600.00


def test_get_property_metrics_mixed_user(db: Session, mixed_user: User):
    """Test property metrics work for mixed user type."""
    property = Property(
        user_id=mixed_user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        street="Hauptstraße 123",
        city="Wien",
        postal_code="1010",
        address="Hauptstraße 123, 1010 Wien",
        purchase_date=date(2020, 1, 1),
        purchase_price=Decimal("350000.00"),
        building_value=Decimal("280000.00"),
        construction_year=1985,
        depreciation_rate=Decimal("0.02"),
        status=PropertyStatus.ACTIVE,
    )
    db.add(property)
    db.commit()
    
    service = DashboardService(db)
    metrics = service.get_property_metrics(mixed_user.id, 2026)
    
    assert metrics["has_properties"] is True
    assert metrics["active_properties_count"] == 1


def test_get_property_metrics_filters_by_year(
    db: Session, landlord_user: User, sample_property: Property
):
    """Test that property metrics filter transactions by year."""
    # Add transaction in 2025
    transaction_2025 = Transaction(
        user_id=landlord_user.id,
        property_id=sample_property.id,
        type=TransactionType.INCOME,
        income_category=IncomeCategory.RENTAL,
        amount=Decimal("10000.00"),
        transaction_date=date(2025, 6, 1),
        description="Rental income 2025",
        is_deductible=False,
    )
    db.add(transaction_2025)
    
    # Add transaction in 2026
    transaction_2026 = Transaction(
        user_id=landlord_user.id,
        property_id=sample_property.id,
        type=TransactionType.INCOME,
        income_category=IncomeCategory.RENTAL,
        amount=Decimal("12000.00"),
        transaction_date=date(2026, 6, 1),
        description="Rental income 2026",
        is_deductible=False,
    )
    db.add(transaction_2026)
    db.commit()
    
    service = DashboardService(db)
    
    # Check 2025 metrics
    metrics_2025 = service.get_property_metrics(landlord_user.id, 2025)
    assert metrics_2025["total_rental_income"] == 10000.00
    
    # Check 2026 metrics
    metrics_2026 = service.get_property_metrics(landlord_user.id, 2026)
    assert metrics_2026["total_rental_income"] == 12000.00
