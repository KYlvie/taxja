"""
Tests for Property Portfolio Service

Tests portfolio comparison and bulk operations.
"""

import pytest
from decimal import Decimal
from datetime import date
from uuid import uuid4

from app.services.property_portfolio_service import PropertyPortfolioService
from app.models.property import Property, PropertyType, PropertyStatus
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.models.user import User


@pytest.fixture
def user(db):
    """Create test user"""
    user = User(
        email="test@example.com",
        hashed_password="hashed",
        full_name="Test User"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def properties(db, user):
    """Create test properties"""
    property1 = Property(
        user_id=user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100"),
        address="Test Street 1, 1010 Vienna",
        street="Test Street 1",
        city="Vienna",
        postal_code="1010",
        purchase_date=date(2020, 1, 1),
        purchase_price=Decimal("300000"),
        building_value=Decimal("240000"),
        land_value=Decimal("60000"),
        construction_year=1990,
        depreciation_rate=Decimal("0.015"),
        status=PropertyStatus.ACTIVE
    )
    
    property2 = Property(
        user_id=user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100"),
        address="Test Street 2, 1020 Vienna",
        street="Test Street 2",
        city="Vienna",
        postal_code="1020",
        purchase_date=date(2021, 1, 1),
        purchase_price=Decimal("400000"),
        building_value=Decimal("320000"),
        land_value=Decimal("80000"),
        construction_year=2000,
        depreciation_rate=Decimal("0.015"),
        status=PropertyStatus.ACTIVE
    )
    
    db.add_all([property1, property2])
    db.commit()
    db.refresh(property1)
    db.refresh(property2)
    
    return [property1, property2]


@pytest.fixture
def transactions(db, user, properties):
    """Create test transactions"""
    current_year = date.today().year
    
    # Property 1: High income, low expenses (good performer)
    t1 = Transaction(
        user_id=user.id,
        property_id=properties[0].id,
        type=TransactionType.INCOME,
        amount=Decimal("24000"),  # 2000/month
        transaction_date=date(current_year, 1, 1),
        description="Rental income property 1",
        income_category=IncomeCategory.RENTAL
    )
    
    t2 = Transaction(
        user_id=user.id,
        property_id=properties[0].id,
        type=TransactionType.EXPENSE,
        amount=Decimal("2000"),  # Low expenses
        transaction_date=date(current_year, 1, 1),
        description="Maintenance property 1",
        expense_category=ExpenseCategory.MAINTENANCE
    )
    
    # Property 2: Lower income, higher expenses (worse performer)
    t3 = Transaction(
        user_id=user.id,
        property_id=properties[1].id,
        type=TransactionType.INCOME,
        amount=Decimal("18000"),  # 1500/month
        transaction_date=date(current_year, 1, 1),
        description="Rental income property 2",
        income_category=IncomeCategory.RENTAL
    )
    
    t4 = Transaction(
        user_id=user.id,
        property_id=properties[1].id,
        type=TransactionType.EXPENSE,
        amount=Decimal("5000"),  # Higher expenses
        transaction_date=date(current_year, 1, 1),
        description="Repairs property 2",
        expense_category=ExpenseCategory.REPAIRS
    )
    
    db.add_all([t1, t2, t3, t4])
    db.commit()
    
    return [t1, t2, t3, t4]


def test_compare_portfolio_properties(db, user, properties, transactions):
    """Test portfolio comparison"""
    service = PropertyPortfolioService(db)
    
    comparisons = service.compare_portfolio_properties(
        user_id=user.id,
        sort_by="net_income",
        sort_order="desc"
    )
    
    assert len(comparisons) == 2
    
    # First property should be better performer (higher net income)
    assert comparisons[0]["property_id"] == str(properties[0].id)
    assert comparisons[0]["rental_income"] == 24000.0
    assert comparisons[0]["expenses"] == 2000.0
    assert comparisons[0]["net_income"] == 22000.0
    
    # Second property should be worse performer
    assert comparisons[1]["property_id"] == str(properties[1].id)
    assert comparisons[1]["rental_income"] == 18000.0
    assert comparisons[1]["expenses"] == 5000.0
    assert comparisons[1]["net_income"] == 13000.0
    
    # Check rental yield calculation
    # Property 1: 22000 / 300000 * 100 = 7.33%
    assert abs(comparisons[0]["rental_yield"] - 7.33) < 0.01
    
    # Check expense ratio calculation
    # Property 1: 2000 / 24000 * 100 = 8.33%
    assert abs(comparisons[0]["expense_ratio"] - 8.33) < 0.01


def test_compare_portfolio_sort_by_rental_yield(db, user, properties, transactions):
    """Test sorting by rental yield"""
    service = PropertyPortfolioService(db)
    
    comparisons = service.compare_portfolio_properties(
        user_id=user.id,
        sort_by="rental_yield",
        sort_order="desc"
    )
    
    # Property 1 should have higher rental yield
    assert comparisons[0]["property_id"] == str(properties[0].id)
    assert comparisons[0]["rental_yield"] > comparisons[1]["rental_yield"]


def test_get_portfolio_summary(db, user, properties, transactions):
    """Test portfolio summary"""
    service = PropertyPortfolioService(db)
    
    summary = service.get_portfolio_summary(user_id=user.id)
    
    assert summary["property_count"] == 2
    assert summary["total_rental_income"] == 42000.0  # 24000 + 18000
    assert summary["total_expenses"] == 7000.0  # 2000 + 5000
    assert summary["total_net_income"] == 35000.0  # 42000 - 7000
    
    # Check best/worst performers
    assert summary["best_performer"]["property_id"] == str(properties[0].id)
    assert summary["best_performer"]["net_income"] == 22000.0
    
    assert summary["worst_performer"]["property_id"] == str(properties[1].id)
    assert summary["worst_performer"]["net_income"] == 13000.0


def test_bulk_archive_properties(db, user, properties):
    """Test bulk archive"""
    service = PropertyPortfolioService(db)
    
    results = service.bulk_archive_properties(
        user_id=user.id,
        property_ids=[properties[0].id, properties[1].id]
    )
    
    assert results["requested_properties"] == 2
    assert results["successful"] == 2
    assert results["failed"] == 0
    
    # Verify properties are archived
    db.refresh(properties[0])
    db.refresh(properties[1])
    
    assert properties[0].status == PropertyStatus.ARCHIVED
    assert properties[1].status == PropertyStatus.ARCHIVED


def test_bulk_link_transactions(db, user, properties):
    """Test bulk transaction linking"""
    service = PropertyPortfolioService(db)
    
    # Create unlinked transactions
    t1 = Transaction(
        user_id=user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("1000"),
        transaction_date=date.today(),
        description="Unlinked expense 1",
        expense_category=ExpenseCategory.MAINTENANCE
    )
    
    t2 = Transaction(
        user_id=user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("2000"),
        transaction_date=date.today(),
        description="Unlinked expense 2",
        expense_category=ExpenseCategory.REPAIRS
    )
    
    db.add_all([t1, t2])
    db.commit()
    db.refresh(t1)
    db.refresh(t2)
    
    # Bulk link to property
    results = service.bulk_link_transactions(
        user_id=user.id,
        property_id=properties[0].id,
        transaction_ids=[t1.id, t2.id]
    )
    
    assert results["requested_transactions"] == 2
    assert results["successful"] == 2
    assert results["failed"] == 0
    
    # Verify transactions are linked
    db.refresh(t1)
    db.refresh(t2)
    
    assert t1.property_id == properties[0].id
    assert t2.property_id == properties[0].id


def test_compare_portfolio_empty(db, user):
    """Test portfolio comparison with no properties"""
    service = PropertyPortfolioService(db)
    
    comparisons = service.compare_portfolio_properties(user_id=user.id)
    
    assert len(comparisons) == 0


def test_bulk_operations_with_invalid_property(db, user, properties):
    """Test bulk operations with invalid property ID"""
    service = PropertyPortfolioService(db)
    
    invalid_uuid = uuid4()
    
    results = service.bulk_archive_properties(
        user_id=user.id,
        property_ids=[properties[0].id, invalid_uuid]
    )
    
    assert results["requested_properties"] == 2
    assert results["successful"] == 1
    assert results["failed"] == 1
    assert len(results["errors"]) == 1
