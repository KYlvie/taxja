"""
Tests for Annual Depreciation API Endpoints

Tests both user and admin endpoints for generating annual depreciation.
"""
import pytest
from datetime import date
from decimal import Decimal
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User, UserType
from app.models.property import Property, PropertyType, PropertyStatus
from app.models.transaction import Transaction, TransactionType, ExpenseCategory
from app.models.recurring_transaction import (
    RecurringTransaction,
    RecurringTransactionType,
    RecurrenceFrequency,
)
from app.core.security import create_access_token


@pytest.fixture
def test_user(db: Session) -> User:
    """Create a test user"""
    user = User(
        email="testuser@example.com",
        password_hash="hashed_password",
        name="Test User",
        user_type=UserType.EMPLOYEE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict:
    """Create authentication headers for test user"""
    token = create_access_token({"sub": test_user.email})
    return {"Authorization": f"Bearer {token}"}


def _add_rental_contract(
    db: Session,
    user_id: int,
    property_id,
    start_date: date,
    unit_percentage: Decimal = Decimal("100.00"),
    amount: Decimal = Decimal("1500.00"),
) -> RecurringTransaction:
    """Create a rental-income recurring contract so AfA is allowed for the year."""
    contract = RecurringTransaction(
        user_id=user_id,
        recurring_type=RecurringTransactionType.RENTAL_INCOME,
        property_id=property_id,
        description="Monthly rent",
        amount=amount,
        transaction_type="income",
        category="rental_income",
        frequency=RecurrenceFrequency.MONTHLY,
        start_date=start_date,
        day_of_month=1,
        is_active=True,
        unit_percentage=unit_percentage,
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract


@pytest.fixture
def test_property(db: Session, test_user: User) -> Property:
    """Create a test property"""
    property = Property(
        id=uuid4(),
        user_id=test_user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        street="Teststraße 123",
        city="Wien",
        postal_code="1010",
        address="Teststraße 123, 1010 Wien",
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
    _add_rental_contract(db, test_user.id, property.id, date(2020, 6, 15))
    return property


@pytest.fixture
def test_property_with_depreciation(db: Session, test_user: User) -> Property:
    """Create a test property that already has depreciation for current year"""
    property = Property(
        id=uuid4(),
        user_id=test_user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        street="Hauptstraße 456",
        city="Wien",
        postal_code="1020",
        address="Hauptstraße 456, 1020 Wien",
        purchase_date=date(2019, 1, 1),
        purchase_price=Decimal("400000.00"),
        building_value=Decimal("320000.00"),
        construction_year=1990,
        depreciation_rate=Decimal("0.02"),
        status=PropertyStatus.ACTIVE
    )
    db.add(property)
    db.commit()
    _add_rental_contract(db, test_user.id, property.id, date(2019, 1, 1))
    
    # Add depreciation transaction for current year
    current_year = date.today().year
    transaction = Transaction(
        user_id=test_user.id,
        property_id=property.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("6400.00"),
        transaction_date=date(current_year, 12, 31),
        description=f"AfA {property.address} ({current_year})",
        expense_category=ExpenseCategory.DEPRECIATION_AFA,
        is_deductible=True,
        is_system_generated=True,
        import_source="annual_depreciation",
        classification_confidence=Decimal("1.0")
    )
    db.add(transaction)
    db.commit()
    db.refresh(property)
    return property


class TestGenerateAnnualDepreciationUserEndpoint:
    """Test suite for user annual depreciation endpoint"""
    
    def test_generate_depreciation_success(
        self,
        client: TestClient,
        db: Session,
        test_property: Property,
        auth_headers: dict
    ):
        """Test successful depreciation generation for current year"""
        current_year = date.today().year
        
        response = client.post(
            "/api/v1/properties/generate-annual-depreciation",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["year"] == current_year
        assert data["properties_processed"] == 1
        assert data["transactions_created"] == 1
        assert data["properties_skipped"] == 0
        assert float(data["total_amount"]) == 4200.00  # 280000 * 1.5%
        assert len(data["transaction_ids"]) == 1
        
        # Verify transaction was created in database
        transaction = db.query(Transaction).filter(
            Transaction.property_id == test_property.id,
            Transaction.expense_category == ExpenseCategory.DEPRECIATION_AFA
        ).first()
        
        assert transaction is not None
        assert transaction.amount == Decimal("4200.00")
        assert transaction.is_system_generated is True
        assert transaction.transaction_date == date(current_year, 12, 31)
    
    def test_generate_depreciation_specific_year(
        self,
        client: TestClient,
        db: Session,
        test_property: Property,
        auth_headers: dict
    ):
        """Test depreciation generation for specific year"""
        response = client.post(
            "/api/v1/properties/generate-annual-depreciation?year=2024",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["year"] == 2024
        assert data["transactions_created"] == 1
        
        # Verify transaction date
        transaction = db.query(Transaction).filter(
            Transaction.property_id == test_property.id
        ).first()
        assert transaction.transaction_date == date(2024, 12, 31)
    
    def test_generate_depreciation_already_exists(
        self,
        client: TestClient,
        test_property_with_depreciation: Property,
        auth_headers: dict
    ):
        """Test that existing depreciation is skipped"""
        current_year = date.today().year
        
        response = client.post(
            "/api/v1/properties/generate-annual-depreciation",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["year"] == current_year
        assert data["properties_processed"] == 1
        assert data["transactions_created"] == 0
        assert data["properties_skipped"] == 1
        assert len(data["skipped_details"]) == 1
        assert data["skipped_details"][0]["reason"] == "already_exists"
    
    def test_generate_depreciation_invalid_year(
        self,
        client: TestClient,
        auth_headers: dict
    ):
        """Test validation of invalid year parameter"""
        response = client.post(
            "/api/v1/properties/generate-annual-depreciation?year=1999",
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert "Invalid year" in response.json()["detail"]
        
        response = client.post(
            "/api/v1/properties/generate-annual-depreciation?year=2050",
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert "Invalid year" in response.json()["detail"]
    
    def test_generate_depreciation_no_properties(
        self,
        client: TestClient,
        auth_headers: dict
    ):
        """Test depreciation generation when user has no properties"""
        response = client.post(
            "/api/v1/properties/generate-annual-depreciation",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["properties_processed"] == 0
        assert data["transactions_created"] == 0
        assert data["properties_skipped"] == 0
        assert float(data["total_amount"]) == 0.0
    
    def test_generate_depreciation_unauthenticated(self, client: TestClient):
        """Test that unauthenticated requests are rejected"""
        response = client.post(
            "/api/v1/properties/generate-annual-depreciation"
        )
        
        assert response.status_code == 401


class TestAnnualDepreciationMultipleProperties:
    """Test annual depreciation with multiple properties"""
    
    def test_generate_depreciation_multiple_properties(
        self,
        client: TestClient,
        db: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test depreciation generation for multiple properties"""
        # Create multiple properties
        properties = []
        for i in range(3):
            property = Property(
                id=uuid4(),
                user_id=test_user.id,
                property_type=PropertyType.RENTAL,
                rental_percentage=Decimal("100.00"),
                street=f"Teststraße {i}",
                city="Wien",
                postal_code="1010",
                address=f"Teststraße {i}, 1010 Wien",
                purchase_date=date(2020, 1, 1),
                purchase_price=Decimal("300000.00"),
                building_value=Decimal("240000.00"),
                construction_year=1990,
                depreciation_rate=Decimal("0.02"),
                status=PropertyStatus.ACTIVE
            )
            db.add(property)
            properties.append(property)
        
        db.commit()
        for property in properties:
            _add_rental_contract(db, test_user.id, property.id, date(2020, 1, 1))
        
        response = client.post(
            "/api/v1/properties/generate-annual-depreciation",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["properties_processed"] == 3
        assert data["transactions_created"] == 3
        assert data["properties_skipped"] == 0
        assert float(data["total_amount"]) == 10800.00  # 3 * (240000 * 1.5%)
        assert len(data["transaction_ids"]) == 3
    
    def test_generate_depreciation_mixed_status(
        self,
        client: TestClient,
        db: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test that only active properties generate depreciation"""
        # Create active property
        active_property = Property(
            id=uuid4(),
            user_id=test_user.id,
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100.00"),
            street="Active Street",
            city="Wien",
            postal_code="1010",
            address="Active Street, 1010 Wien",
            purchase_date=date(2020, 1, 1),
            purchase_price=Decimal("300000.00"),
            building_value=Decimal("240000.00"),
            construction_year=1990,
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db.add(active_property)
        db.commit()
        db.refresh(active_property)
        _add_rental_contract(db, test_user.id, active_property.id, date(2020, 1, 1))
        
        # Create sold property
        sold_property = Property(
            id=uuid4(),
            user_id=test_user.id,
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100.00"),
            street="Sold Street",
            city="Wien",
            postal_code="1020",
            address="Sold Street, 1020 Wien",
            purchase_date=date(2019, 1, 1),
            purchase_price=Decimal("300000.00"),
            building_value=Decimal("240000.00"),
            construction_year=1990,
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.SOLD,
            sale_date=date(2023, 6, 1)
        )
        db.add(sold_property)
        
        db.commit()
        
        response = client.post(
            "/api/v1/properties/generate-annual-depreciation",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Only active property should be processed
        assert data["properties_processed"] == 1
        assert data["transactions_created"] == 1
        assert float(data["total_amount"]) == 3600.00  # 240000 * 1.5%
