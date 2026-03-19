"""
User Acceptance Tests for Historical Depreciation Backfill
"""

import pytest
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session

from app.models.user import User, UserType
from app.models.property import Property, PropertyType, PropertyStatus
from app.models.transaction import ExpenseCategory, Transaction, TransactionType
from app.models.recurring_transaction import (
    RecurrenceFrequency,
    RecurringTransaction,
    RecurringTransactionType,
)
from app.services.historical_depreciation_service import HistoricalDepreciationService
from app.services.afa_calculator import AfACalculator


@pytest.fixture
def test_user(db: Session) -> User:
    """Create a test user"""
    user = User(
        email="test@example.com",
        password_hash="hashed_password",
        name="Test User",
        user_type=UserType.LANDLORD,
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
        address="Teststraße 1, 1010 Wien",
        street="Teststraße 1",
        city="Wien",
        postal_code="1010",
        purchase_date=date(2023, 3, 15),
        purchase_price=Decimal("300000.00"),
        building_value=Decimal("240000.00"),
        land_value=Decimal("60000.00"),
        construction_year=1920,
        depreciation_rate=Decimal("0.015"),
    )
    db.add(prop)
    db.commit()
    db.refresh(prop)
    return prop


@pytest.fixture
def rental_contract_2023(db: Session, test_user, property_2023):
    """Active rental contract so historical AfA applies in each covered year."""
    contract = RecurringTransaction(
        user_id=test_user.id,
        recurring_type=RecurringTransactionType.RENTAL_INCOME,
        property_id=property_2023.id,
        description="Historical rental income",
        amount=Decimal("1500.00"),
        transaction_type="income",
        category="rental_income",
        frequency=RecurrenceFrequency.MONTHLY,
        start_date=date(2023, 3, 15),
        end_date=None,
        day_of_month=15,
        is_active=True,
        unit_percentage=Decimal("100.00"),
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract



def test_backfill_property_from_2023(db: Session, test_user, property_2023, rental_contract_2023):
    """Test backfilling depreciation for a property purchased in 2023"""
    service = HistoricalDepreciationService(db)

    # Preview backfill
    preview = service.calculate_historical_depreciation(property_2023.id)
    expected_years = list(range(2023, date.today().year + 1))

    assert [item.year for item in preview] == expected_years

    # Execute backfill
    result = service.backfill_depreciation(property_2023.id, test_user.id, confirm=True)

    assert result.property_id == property_2023.id
    assert result.years_backfilled == len(expected_years)
    assert len(result.transactions) == len(expected_years)

    # Verify transactions were created
    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.property_id == property_2023.id,
            Transaction.is_system_generated == True,
            Transaction.expense_category == ExpenseCategory.DEPRECIATION_AFA,
        )
        .order_by(Transaction.transaction_date)
        .all()
    )

    assert len(transactions) == len(expected_years)
    assert transactions[0].transaction_date == date(2023, 12, 31)
    assert transactions[-1].transaction_date == date(expected_years[-1], 12, 31)


def test_backfill_is_idempotent_after_initial_run(db: Session, test_user, property_2023, rental_contract_2023):
    """Test repeated backfill runs do not create duplicate depreciation transactions."""
    service = HistoricalDepreciationService(db)
    expected_year_count = len(range(2023, date.today().year + 1))

    # First backfill
    result1 = service.backfill_depreciation(property_2023.id, test_user.id, confirm=True)
    assert result1.years_backfilled == expected_year_count

    # Second backfill should be a no-op
    result2 = service.backfill_depreciation(property_2023.id, test_user.id, confirm=True)
    assert result2.years_backfilled == 0
    assert result2.transactions == []

    # Verify only the original transactions exist
    count = (
        db.query(Transaction)
        .filter(
            Transaction.property_id == property_2023.id,
            Transaction.is_system_generated == True,
        )
        .count()
    )
    assert count == expected_year_count


def test_backfill_respects_building_value_limit(db: Session, test_user):
    """Test that backfill stops when accumulated depreciation reaches building value"""
    prop = Property(
        user_id=test_user.id,
        property_type=PropertyType.RENTAL,
        status=PropertyStatus.ACTIVE,
        address="Teststraße 99, 1010 Wien",
        street="Teststraße 99",
        city="Wien",
        postal_code="1010",
        purchase_date=date(1970, 1, 1),
        purchase_price=Decimal("100000.00"),
        building_value=Decimal("80000.00"),
        land_value=Decimal("20000.00"),
        construction_year=1900,
        depreciation_rate=Decimal("0.015"),
    )
    db.add(prop)
    db.commit()
    db.refresh(prop)

    rental_contract = RecurringTransaction(
        user_id=test_user.id,
        recurring_type=RecurringTransactionType.RENTAL_INCOME,
        property_id=prop.id,
        description="Legacy rental income",
        amount=Decimal("900.00"),
        transaction_type="income",
        category="rental_income",
        frequency=RecurrenceFrequency.MONTHLY,
        start_date=date(1970, 1, 1),
        end_date=None,
        day_of_month=1,
        is_active=True,
        unit_percentage=Decimal("100.00"),
    )
    db.add(rental_contract)
    db.commit()

    service = HistoricalDepreciationService(db)
    calculator = AfACalculator(db)

    # Preview backfill
    preview = service.calculate_historical_depreciation(prop.id)
    total_depreciation = sum(p.amount for p in preview)

    # Verify total does not exceed building value
    assert total_depreciation <= prop.building_value

    # Execute backfill
    result = service.backfill_depreciation(prop.id, test_user.id, confirm=True)

    # Verify accumulated depreciation
    accumulated = calculator.get_accumulated_depreciation(prop.id)
    assert accumulated <= prop.building_value
