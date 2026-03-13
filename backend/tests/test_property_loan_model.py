"""Unit tests for PropertyLoan model"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from app.models.property_loan import PropertyLoan
from app.models.property import Property, PropertyType, PropertyStatus
from app.models.user import User, UserType


def test_create_property_loan(db_session, test_user, test_property):
    """Test creating a property loan"""
    loan = PropertyLoan(
        property_id=test_property.id,
        user_id=test_user.id,
        loan_amount=Decimal("200000.00"),
        interest_rate=Decimal("0.0325"),  # 3.25%
        start_date=date(2020, 1, 1),
        end_date=date(2050, 1, 1),
        monthly_payment=Decimal("1200.00"),
        lender_name="Test Bank AG",
        lender_account="AT123456789012345678",
        loan_type="fixed_rate"
    )
    
    db_session.add(loan)
    db_session.commit()
    
    assert loan.id is not None
    assert loan.property_id == test_property.id
    assert loan.user_id == test_user.id
    assert loan.loan_amount == Decimal("200000.00")
    assert loan.interest_rate == Decimal("0.0325")
    assert loan.lender_name == "Test Bank AG"


def test_property_loan_relationships(db_session, test_user, test_property):
    """Test PropertyLoan relationships with Property and User"""
    loan = PropertyLoan(
        property_id=test_property.id,
        user_id=test_user.id,
        loan_amount=Decimal("150000.00"),
        interest_rate=Decimal("0.0275"),
        start_date=date(2021, 6, 1),
        monthly_payment=Decimal("900.00"),
        lender_name="Austrian Bank"
    )
    
    db_session.add(loan)
    db_session.commit()
    db_session.refresh(loan)
    
    # Test property relationship
    assert loan.property is not None
    assert loan.property.id == test_property.id
    
    # Test user relationship
    assert loan.user is not None
    assert loan.user.id == test_user.id
    
    # Test reverse relationship from property
    db_session.refresh(test_property)
    assert len(test_property.loans) == 1
    assert test_property.loans[0].id == loan.id


def test_property_loan_constraints(db_session, test_user, test_property):
    """Test PropertyLoan database constraints"""
    
    # Test negative loan amount (should fail)
    with pytest.raises(IntegrityError):
        loan = PropertyLoan(
            property_id=test_property.id,
            user_id=test_user.id,
            loan_amount=Decimal("-100000.00"),
            interest_rate=Decimal("0.03"),
            start_date=date(2020, 1, 1),
            monthly_payment=Decimal("1000.00"),
            lender_name="Test Bank"
        )
        db_session.add(loan)
        db_session.commit()
    
    db_session.rollback()
    
    # Test interest rate out of range (should fail)
    with pytest.raises(IntegrityError):
        loan = PropertyLoan(
            property_id=test_property.id,
            user_id=test_user.id,
            loan_amount=Decimal("100000.00"),
            interest_rate=Decimal("0.25"),  # 25% - too high
            start_date=date(2020, 1, 1),
            monthly_payment=Decimal("1000.00"),
            lender_name="Test Bank"
        )
        db_session.add(loan)
        db_session.commit()
    
    db_session.rollback()
    
    # Test end_date before start_date (should fail)
    with pytest.raises(IntegrityError):
        loan = PropertyLoan(
            property_id=test_property.id,
            user_id=test_user.id,
            loan_amount=Decimal("100000.00"),
            interest_rate=Decimal("0.03"),
            start_date=date(2020, 1, 1),
            end_date=date(2019, 1, 1),  # Before start_date
            monthly_payment=Decimal("1000.00"),
            lender_name="Test Bank"
        )
        db_session.add(loan)
        db_session.commit()
    
    db_session.rollback()


def test_calculate_annual_interest(db_session, test_user, test_property):
    """Test annual interest calculation"""
    loan = PropertyLoan(
        property_id=test_property.id,
        user_id=test_user.id,
        loan_amount=Decimal("200000.00"),
        interest_rate=Decimal("0.03"),  # 3%
        start_date=date(2020, 1, 1),
        end_date=date(2050, 1, 1),
        monthly_payment=Decimal("1000.00"),
        lender_name="Test Bank"
    )
    
    db_session.add(loan)
    db_session.commit()
    
    # Full year interest
    annual_interest = loan.calculate_annual_interest(2021)
    expected = Decimal("200000.00") * Decimal("0.03")
    assert annual_interest == expected.quantize(Decimal("0.01"))
    
    # Partial year (first year) - started in January, so full year
    first_year_interest = loan.calculate_annual_interest(2020)
    assert first_year_interest == expected.quantize(Decimal("0.01"))


def test_calculate_annual_interest_partial_year(db_session, test_user, test_property):
    """Test annual interest calculation for partial years"""
    loan = PropertyLoan(
        property_id=test_property.id,
        user_id=test_user.id,
        loan_amount=Decimal("100000.00"),
        interest_rate=Decimal("0.04"),  # 4%
        start_date=date(2020, 7, 1),  # Started mid-year
        end_date=date(2025, 6, 30),  # Ends mid-year
        monthly_payment=Decimal("800.00"),
        lender_name="Test Bank"
    )
    
    db_session.add(loan)
    db_session.commit()
    
    # First year (July-December = 6 months)
    first_year_interest = loan.calculate_annual_interest(2020)
    expected_first = Decimal("100000.00") * Decimal("0.04") * Decimal("6") / Decimal("12")
    assert first_year_interest == expected_first.quantize(Decimal("0.01"))
    
    # Last year (January-June = 6 months)
    last_year_interest = loan.calculate_annual_interest(2025)
    expected_last = Decimal("100000.00") * Decimal("0.04") * Decimal("6") / Decimal("12")
    assert last_year_interest == expected_last.quantize(Decimal("0.01"))
    
    # Full year in between
    full_year_interest = loan.calculate_annual_interest(2022)
    expected_full = Decimal("100000.00") * Decimal("0.04")
    assert full_year_interest == expected_full.quantize(Decimal("0.01"))


def test_calculate_remaining_balance(db_session, test_user, test_property):
    """Test remaining balance calculation"""
    loan = PropertyLoan(
        property_id=test_property.id,
        user_id=test_user.id,
        loan_amount=Decimal("150000.00"),
        interest_rate=Decimal("0.035"),
        start_date=date(2020, 1, 1),
        end_date=date(2040, 1, 1),
        monthly_payment=Decimal("900.00"),
        lender_name="Test Bank"
    )
    
    db_session.add(loan)
    db_session.commit()
    
    # Before loan start
    balance_before = loan.calculate_remaining_balance(date(2019, 12, 31))
    assert balance_before == Decimal("0")
    
    # At loan start
    balance_start = loan.calculate_remaining_balance(date(2020, 1, 1))
    assert balance_start == loan.loan_amount
    
    # After loan end
    balance_after = loan.calculate_remaining_balance(date(2040, 1, 2))
    assert balance_after == Decimal("0")


def test_property_loan_cascade_delete(db_session, test_user, test_property):
    """Test that loans are deleted when property is deleted"""
    loan = PropertyLoan(
        property_id=test_property.id,
        user_id=test_user.id,
        loan_amount=Decimal("100000.00"),
        interest_rate=Decimal("0.03"),
        start_date=date(2020, 1, 1),
        monthly_payment=Decimal("800.00"),
        lender_name="Test Bank"
    )
    
    db_session.add(loan)
    db_session.commit()
    loan_id = loan.id
    
    # Delete property
    db_session.delete(test_property)
    db_session.commit()
    
    # Loan should be deleted due to cascade
    deleted_loan = db_session.query(PropertyLoan).filter_by(id=loan_id).first()
    assert deleted_loan is None


def test_property_loan_repr(db_session, test_user, test_property):
    """Test PropertyLoan __repr__ method"""
    loan = PropertyLoan(
        property_id=test_property.id,
        user_id=test_user.id,
        loan_amount=Decimal("100000.00"),
        interest_rate=Decimal("0.03"),
        start_date=date(2020, 1, 1),
        monthly_payment=Decimal("800.00"),
        lender_name="Test Bank AG"
    )
    
    db_session.add(loan)
    db_session.commit()
    
    repr_str = repr(loan)
    assert "PropertyLoan" in repr_str
    assert str(loan.id) in repr_str
    assert "Test Bank AG" in repr_str
    assert "100000.00" in repr_str


# Fixtures
@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    user = User(
        email="test@example.com",
        password_hash="hashed_password",
        name="Test User",
        user_type=UserType.LANDLORD
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def test_property(db_session, test_user):
    """Create a test property"""
    property = Property(
        user_id=test_user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        address="Teststraße 123, 1010 Wien",
        street="Teststraße 123",
        city="Wien",
        postal_code="1010",
        purchase_date=date(2020, 1, 1),
        purchase_price=Decimal("350000.00"),
        building_value=Decimal("280000.00"),
        land_value=Decimal("70000.00"),
        construction_year=1985,
        depreciation_rate=Decimal("0.02"),
        status=PropertyStatus.ACTIVE
    )
    db_session.add(property)
    db_session.commit()
    return property
