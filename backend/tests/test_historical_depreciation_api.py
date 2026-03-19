"""
Tests for Historical Depreciation API Endpoints

Tests the GET /historical-depreciation and POST /backfill-depreciation endpoints.
"""

import pytest
from datetime import date
from decimal import Decimal
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.property import Property, PropertyType, PropertyStatus
from app.models.recurring_transaction import (
    RecurrenceFrequency,
    RecurringTransaction,
    RecurringTransactionType,
)
from app.models.transaction import Transaction, TransactionType, ExpenseCategory
from app.models.user import User, UserType
from app.core.security import create_access_token


@pytest.fixture
def test_user(db: Session):
    """Create a test user"""
    user = User(
        email="test@example.com",
        hashed_password="hashed_password",
        name="Test User",
        user_type=UserType.LANDLORD,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def other_user(db: Session):
    """Create another test user"""
    user = User(
        email="other@example.com",
        hashed_password="hashed_password",
        name="Other User",
        user_type=UserType.LANDLORD,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User):
    """Create authentication headers"""
    token = create_access_token(data={"sub": test_user.email})
    return {"Authorization": f"Bearer {token}"}


def _add_rental_contract(
    db: Session,
    user_id: int,
    property_id,
    start_date: date,
    unit_percentage: Decimal = Decimal("100.00"),
    amount: Decimal = Decimal("1500.00"),
) -> RecurringTransaction:
    """Create an active rental contract so rental-state sync keeps the property rentable."""
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


class TestHistoricalDepreciationPreview:
    """Tests for GET /api/v1/properties/{property_id}/historical-depreciation"""
    
    def test_preview_historical_depreciation_success(
        self,
        client: TestClient,
        db: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test successful preview of historical depreciation"""
        # Create property purchased 3 years ago
        property = Property(
            user_id=test_user.id,
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100.00"),
            street="Teststraße 1",
            city="Wien",
            postal_code="1010",
            address="Teststraße 1, 1010 Wien",
            purchase_date=date(2023, 1, 15),
            purchase_price=Decimal("300000.00"),
            building_value=Decimal("240000.00"),
            construction_year=2000,
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db.add(property)
        db.commit()
        db.refresh(property)
        _add_rental_contract(db, test_user.id, property.id, property.purchase_date)
        
        # Preview historical depreciation
        response = client.get(
            f"/api/v1/properties/{property.id}/historical-depreciation",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "property_id" in data
        assert "years" in data
        assert "total_amount" in data
        assert "years_count" in data
        
        # Should have 3 years (2023, 2024, 2025) plus current year 2026
        assert data["years_count"] >= 3
        
        # Verify years data
        years = data["years"]
        assert len(years) >= 3
        
        # First year should be 2023
        first_year = years[0]
        assert first_year["year"] == 2023
        assert Decimal(first_year["amount"]) > 0
        assert first_year["transaction_date"] == "2023-12-31"
        
        # Total amount should be sum of all years
        expected_total = sum(Decimal(year["amount"]) for year in years)
        assert abs(Decimal(data["total_amount"]) - expected_total) < Decimal("0.01")
    
    def test_preview_with_existing_depreciation(
        self,
        client: TestClient,
        db: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test preview excludes years that already have depreciation"""
        # Create property purchased 3 years ago
        property = Property(
            user_id=test_user.id,
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100.00"),
            street="Teststraße 2",
            city="Wien",
            postal_code="1010",
            address="Teststraße 2, 1010 Wien",
            purchase_date=date(2023, 1, 15),
            purchase_price=Decimal("300000.00"),
            building_value=Decimal("240000.00"),
            construction_year=2000,
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db.add(property)
        db.commit()
        db.refresh(property)
        _add_rental_contract(db, test_user.id, property.id, property.purchase_date)
        
        # Create depreciation transaction for 2023
        transaction = Transaction(
            user_id=test_user.id,
            property_id=property.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("4000.00"),
            transaction_date=date(2023, 12, 31),
            description="AfA 2023",
            expense_category=ExpenseCategory.DEPRECIATION_AFA,
            is_deductible=True,
            is_system_generated=True
        )
        db.add(transaction)
        db.commit()
        
        # Preview should exclude 2023
        response = client.get(
            f"/api/v1/properties/{property.id}/historical-depreciation",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should not include 2023
        years = [year["year"] for year in data["years"]]
        assert 2023 not in years
        
        # Should include 2024, 2025, 2026
        assert 2024 in years or 2025 in years
    
    def test_preview_property_not_found(
        self,
        client: TestClient,
        auth_headers: dict
    ):
        """Test preview with non-existent property"""
        fake_id = uuid4()
        response = client.get(
            f"/api/v1/properties/{fake_id}/historical-depreciation",
            headers=auth_headers
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_preview_unauthorized(
        self,
        client: TestClient,
        db: Session,
        test_user: User,
        other_user: User,
        auth_headers: dict
    ):
        """Test preview fails for property owned by another user"""
        # Create property owned by other_user
        property = Property(
            user_id=other_user.id,
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100.00"),
            street="Teststraße 3",
            city="Wien",
            postal_code="1010",
            address="Teststraße 3, 1010 Wien",
            purchase_date=date(2023, 1, 15),
            purchase_price=Decimal("300000.00"),
            building_value=Decimal("240000.00"),
            construction_year=2000,
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db.add(property)
        db.commit()
        db.refresh(property)
        _add_rental_contract(db, other_user.id, property.id, property.purchase_date)
        
        # Try to preview with test_user's auth
        response = client.get(
            f"/api/v1/properties/{property.id}/historical-depreciation",
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    def test_preview_no_authentication(
        self,
        client: TestClient,
        db: Session,
        test_user: User
    ):
        """Test preview requires authentication"""
        property = Property(
            user_id=test_user.id,
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100.00"),
            street="Teststraße 4",
            city="Wien",
            postal_code="1010",
            address="Teststraße 4, 1010 Wien",
            purchase_date=date(2023, 1, 15),
            purchase_price=Decimal("300000.00"),
            building_value=Decimal("240000.00"),
            construction_year=2000,
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db.add(property)
        db.commit()
        db.refresh(property)
        _add_rental_contract(db, test_user.id, property.id, property.purchase_date)
        
        # No auth headers
        response = client.get(
            f"/api/v1/properties/{property.id}/historical-depreciation"
        )
        
        assert response.status_code == 401


class TestBackfillDepreciation:
    """Tests for POST /api/v1/properties/{property_id}/backfill-depreciation"""
    
    def test_backfill_success(
        self,
        client: TestClient,
        db: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test successful backfill of historical depreciation"""
        # Create property purchased 2 years ago
        property = Property(
            user_id=test_user.id,
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100.00"),
            street="Teststraße 10",
            city="Wien",
            postal_code="1010",
            address="Teststraße 10, 1010 Wien",
            purchase_date=date(2024, 1, 15),
            purchase_price=Decimal("300000.00"),
            building_value=Decimal("240000.00"),
            construction_year=2000,
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db.add(property)
        db.commit()
        db.refresh(property)
        _add_rental_contract(db, test_user.id, property.id, property.purchase_date)
        
        # Backfill depreciation
        response = client.post(
            f"/api/v1/properties/{property.id}/backfill-depreciation",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "property_id" in data
        assert "years_backfilled" in data
        assert "total_amount" in data
        assert "transaction_ids" in data
        
        # Should have backfilled at least 2 years (2024, 2025)
        assert data["years_backfilled"] >= 2
        assert Decimal(data["total_amount"]) > 0
        assert len(data["transaction_ids"]) >= 2
        
        # Verify transactions were created in database
        transactions = db.query(Transaction).filter(
            Transaction.property_id == property.id,
            Transaction.expense_category == ExpenseCategory.DEPRECIATION_AFA
        ).all()
        
        assert len(transactions) >= 2
        
        # Verify transactions are system-generated
        for transaction in transactions:
            assert transaction.is_system_generated is True
            assert transaction.expense_category == ExpenseCategory.DEPRECIATION_AFA
            assert transaction.type == TransactionType.EXPENSE
            assert transaction.amount > 0
    
    def test_backfill_idempotence(
        self,
        client: TestClient,
        db: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test backfill is idempotent (calling twice doesn't duplicate)"""
        # Create property
        property = Property(
            user_id=test_user.id,
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100.00"),
            street="Teststraße 11",
            city="Wien",
            postal_code="1010",
            address="Teststraße 11, 1010 Wien",
            purchase_date=date(2024, 1, 15),
            purchase_price=Decimal("300000.00"),
            building_value=Decimal("240000.00"),
            construction_year=2000,
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db.add(property)
        db.commit()
        db.refresh(property)
        _add_rental_contract(db, test_user.id, property.id, property.purchase_date)
        
        # First backfill
        response1 = client.post(
            f"/api/v1/properties/{property.id}/backfill-depreciation",
            headers=auth_headers
        )
        assert response1.status_code == 200
        data1 = response1.json()
        years_backfilled_1 = data1["years_backfilled"]
        
        # Second backfill should return 400 (already backfilled)
        response2 = client.post(
            f"/api/v1/properties/{property.id}/backfill-depreciation",
            headers=auth_headers
        )
        assert response2.status_code == 400
        assert "already have depreciation" in response2.json()["detail"].lower()
        
        # Verify no duplicate transactions
        transactions = db.query(Transaction).filter(
            Transaction.property_id == property.id,
            Transaction.expense_category == ExpenseCategory.DEPRECIATION_AFA
        ).all()
        
        # Should still have same number of transactions
        assert len(transactions) == years_backfilled_1
    
    def test_backfill_property_not_found(
        self,
        client: TestClient,
        auth_headers: dict
    ):
        """Test backfill with non-existent property"""
        fake_id = uuid4()
        response = client.post(
            f"/api/v1/properties/{fake_id}/backfill-depreciation",
            headers=auth_headers
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_backfill_unauthorized(
        self,
        client: TestClient,
        db: Session,
        test_user: User,
        other_user: User,
        auth_headers: dict
    ):
        """Test backfill fails for property owned by another user"""
        # Create property owned by other_user
        property = Property(
            user_id=other_user.id,
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100.00"),
            street="Teststraße 12",
            city="Wien",
            postal_code="1010",
            address="Teststraße 12, 1010 Wien",
            purchase_date=date(2024, 1, 15),
            purchase_price=Decimal("300000.00"),
            building_value=Decimal("240000.00"),
            construction_year=2000,
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db.add(property)
        db.commit()
        db.refresh(property)
        _add_rental_contract(db, test_user.id, property.id, property.purchase_date)
        _add_rental_contract(db, test_user.id, property.id, property.purchase_date)
        
        # Try to backfill with test_user's auth
        response = client.post(
            f"/api/v1/properties/{property.id}/backfill-depreciation",
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    def test_backfill_no_authentication(
        self,
        client: TestClient,
        db: Session,
        test_user: User
    ):
        """Test backfill requires authentication"""
        property = Property(
            user_id=test_user.id,
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100.00"),
            street="Teststraße 13",
            city="Wien",
            postal_code="1010",
            address="Teststraße 13, 1010 Wien",
            purchase_date=date(2024, 1, 15),
            purchase_price=Decimal("300000.00"),
            building_value=Decimal("240000.00"),
            construction_year=2000,
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db.add(property)
        db.commit()
        db.refresh(property)
        _add_rental_contract(db, test_user.id, property.id, property.purchase_date)
        
        # No auth headers
        response = client.post(
            f"/api/v1/properties/{property.id}/backfill-depreciation"
        )
        
        assert response.status_code == 401
    
    def test_backfill_respects_building_value_limit(
        self,
        client: TestClient,
        db: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test backfill stops when accumulated depreciation reaches building value"""
        # Create property with low building value and high depreciation rate
        # This will fully depreciate quickly
        property = Property(
            user_id=test_user.id,
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100.00"),
            street="Teststraße 14",
            city="Wien",
            postal_code="1010",
            address="Teststraße 14, 1010 Wien",
            purchase_date=date(1970, 1, 1),  # Very old property
            purchase_price=Decimal("10000.00"),
            building_value=Decimal("8000.00"),
            construction_year=1960,
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db.add(property)
        db.commit()
        db.refresh(property)
        _add_rental_contract(db, test_user.id, property.id, property.purchase_date)
        
        # Backfill
        response = client.post(
            f"/api/v1/properties/{property.id}/backfill-depreciation",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Total amount should not exceed building value
        assert Decimal(data["total_amount"]) <= property.building_value
        
        # Verify in database
        transactions = db.query(Transaction).filter(
            Transaction.property_id == property.id,
            Transaction.expense_category == ExpenseCategory.DEPRECIATION_AFA
        ).all()
        
        total_depreciation = sum(t.amount for t in transactions)
        assert total_depreciation <= property.building_value


class TestHistoricalDepreciationIntegration:
    """Integration tests for preview + backfill workflow"""
    
    def test_preview_then_backfill_workflow(
        self,
        client: TestClient,
        db: Session,
        test_user: User,
        auth_headers: dict
    ):
        """Test complete workflow: preview then backfill"""
        # Create property
        property = Property(
            user_id=test_user.id,
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100.00"),
            street="Teststraße 20",
            city="Wien",
            postal_code="1010",
            address="Teststraße 20, 1010 Wien",
            purchase_date=date(2024, 6, 15),
            purchase_price=Decimal("300000.00"),
            building_value=Decimal("240000.00"),
            construction_year=2000,
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db.add(property)
        db.commit()
        db.refresh(property)
        _add_rental_contract(db, test_user.id, property.id, property.purchase_date)
        
        # Step 1: Preview
        preview_response = client.get(
            f"/api/v1/properties/{property.id}/historical-depreciation",
            headers=auth_headers
        )
        assert preview_response.status_code == 200
        preview_data = preview_response.json()
        
        expected_years = preview_data["years_count"]
        expected_total = preview_data["total_amount"]
        
        # Step 2: Backfill
        backfill_response = client.post(
            f"/api/v1/properties/{property.id}/backfill-depreciation",
            headers=auth_headers
        )
        assert backfill_response.status_code == 200
        backfill_data = backfill_response.json()
        
        # Verify preview matches backfill
        assert backfill_data["years_backfilled"] == expected_years
        assert abs(Decimal(backfill_data["total_amount"]) - Decimal(expected_total)) < Decimal("0.01")
        
        # Step 3: Preview again should show nothing to backfill
        preview_response_2 = client.get(
            f"/api/v1/properties/{property.id}/historical-depreciation",
            headers=auth_headers
        )
        assert preview_response_2.status_code == 200
        preview_data_2 = preview_response_2.json()
        
        # Should have no years to backfill
        assert preview_data_2["years_count"] == 0
        assert Decimal(preview_data_2["total_amount"]) == Decimal("0")
