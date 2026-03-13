"""
User Acceptance Tests for Historical Depreciation Backfill
"""

import pytest
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.property import Property, PropertyType, PropertyStatus
from app.models.transaction import Transaction, TransactionType, TransactionCategory
from app.services.historical_depreciation_service import HistoricalDepreciationService
from app.services.afa_calculator import AfACalculator


@pytest.fixture
def test_user(db: Session) -> User:
    """Create a test user"""
    user = User(
        email="test@example.com",
        hashed_password="hashed_password",
        full_name="Test User",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def property_2023(db: Session, test_user):
    """Property purchased in 2023"""
    prop = Property(
        user_id=test_user.id,
        property_type=PropertyType.RENTAL,
        status=PropertyStatus.ACTIVE,
        street="Teststraße 1",
        city="Wien",
        postal_code="1010",
        purchase_date=date(2023, 3, 15),
        purchase_price=Decimal("300000.00"),
        building_value=Decimal("240000.00"),
        land_value=Decimal("60000.00"),
        construction_year=1920,
        depreciation_rate=Decimal("1.5"),
    )
    db.add(prop)
    db.commit()
    db.refresh(prop)
    return prop



def test_backfill_property_from_2023(db: Session, property_2023):
    """Test backfilling depreciation for a property purchased in 2023"""
    service = HistoricalDepreciationService(db)
    calculator = AfACalculator()

    # Preview backfill
    preview = service.calculate_historical_depreciation(property_2023.id)
    
    assert len(preview) == 3
    assert preview[0]["year"] == 2023
    assert preview[1]["year"] == 2024
    assert preview[2]["year"] == 2025

    # Execute backfill
    result = service.backfill_depreciation(property_2023.id)
    
    assert result.property_id == property_2023.id
    assert result.years_backfilled == 3
    assert len(result.transactions_created) == 3

    # Verify transactions were created
    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.property_id == property_2023.id,
            Transaction.is_system_generated == True,
            Transaction.category == TransactionCategory.DEPRECIATION,
        )
        .order_by(Transaction.date)
        .all()
    )

    assert len(transactions) == 3
    assert transactions[0].date == date(2023, 12, 31)
    assert transactions[1].date == date(2024, 12, 31)
    assert transactions[2].date == date(2025, 12, 31)


def test_backfill_prevents_duplicates(db: Session, property_2023):
    """Test that backfill prevents creating duplicate depreciation transactions"""
    service = HistoricalDepreciationService(db)

    # First backfill
    result1 = service.backfill_depreciation(property_2023.id)
    assert result1.years_backfilled == 3

    # Attempt second backfill - should fail
    with pytest.raises(Exception, match="already exists"):
        service.backfill_depreciation(property_2023.id)

    # Verify only 3 transactions exist
    count = (
        db.query(Transaction)
        .filter(
            Transaction.property_id == property_2023.id,
            Transaction.is_system_generated == True,
        )
        .count()
    )
    assert count == 3


def test_backfill_respects_building_value_limit(db: Session, test_user):
    """Test that backfill stops when accumulated depreciation reaches building value"""
    prop = Property(
        user_id=test_user.id,
        property_type=PropertyType.RENTAL,
        status=PropertyStatus.ACTIVE,
        street="Teststraße 99",
        city="Wien",
        postal_code="1010",
        purchase_date=date(1970, 1, 1),
        purchase_price=Decimal("100000.00"),
        building_value=Decimal("80000.00"),
        land_value=Decimal("20000.00"),
        construction_year=1900,
        depreciation_rate=Decimal("1.5"),
    )
    db.add(prop)
    db.commit()

    service = HistoricalDepreciationService(db)
    calculator = AfACalculator()

    # Preview backfill
    preview = service.calculate_historical_depreciation(prop.id)
    total_depreciation = sum(p["amount"] for p in preview)

    # Verify total does not exceed building value
    assert total_depreciation <= prop.building_value

    # Execute backfill
    result = service.backfill_depreciation(prop.id)

    # Verify accumulated depreciation
    accumulated = calculator.get_accumulated_depreciation(
        property_id=prop.id,
        db=db,
    )
    assert accumulated <= prop.building_value
