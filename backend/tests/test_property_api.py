"""Tests for Property API endpoints"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.user import User, UserType
from app.models.property import Property, PropertyType, PropertyStatus
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.core.security import create_access_token


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


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
def auth_headers(test_user: User):
    """Create authentication headers"""
    token = create_access_token(subject=test_user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_property(db: Session, test_user: User):
    """Create a test property"""
    property = Property(
        user_id=test_user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        address="Hauptstraße 123, 1010 Wien",
        street="Hauptstraße 123",
        city="Wien",
        postal_code="1010",
        purchase_date=date(2020, 6, 15),
        purchase_price=Decimal("350000.00"),
        building_value=Decimal("280000.00"),
        land_value=Decimal("70000.00"),
        construction_year=1985,
        depreciation_rate=Decimal("0.02"),
        status=PropertyStatus.ACTIVE
    )
    db.add(property)
    db.commit()
    db.refresh(property)
    return property


class TestCreateProperty:
    """Tests for POST /api/v1/properties"""
    
    def test_create_property_success(self, client, auth_headers, db):
        """Test successful property creation"""
        property_data = {
            "street": "Teststraße 456",
            "city": "Graz",
            "postal_code": "8010",
            "purchase_date": "2021-03-15",
            "purchase_price": 250000.00,
            "construction_year": 1990
        }
        
        response = client.post(
            "/api/v1/properties",
            json=property_data,
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["street"] == "Teststraße 456"
        assert data["city"] == "Graz"
        assert data["postal_code"] == "8010"
        assert data["purchase_price"] == "250000.00"
        # Check auto-calculated building_value (80%)
        assert data["building_value"] == "200000.00"
        # Check auto-determined depreciation_rate (2% for 1990)
        assert data["depreciation_rate"] == "0.0200"
        assert data["status"] == "active"
        assert "id" in data
    
    def test_create_property_with_building_value(self, client, auth_headers):
        """Test property creation with explicit building_value"""
        property_data = {
            "street": "Teststraße 789",
            "city": "Linz",
            "postal_code": "4020",
            "purchase_date": "2022-01-10",
            "purchase_price": 300000.00,
            "building_value": 240000.00,
            "construction_year": 1910
        }
        
        response = client.post(
            "/api/v1/properties",
            json=property_data,
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["building_value"] == "240000.00"
        # Check depreciation_rate for pre-1915 building (1.5%)
        assert data["depreciation_rate"] == "0.0150"
    
    def test_create_property_validation_errors(self, client, auth_headers):
        """Test property creation with validation errors"""
        # Missing required fields
        response = client.post(
            "/api/v1/properties",
            json={},
            headers=auth_headers
        )
        assert response.status_code == 422
        
        # Purchase date in future
        property_data = {
            "street": "Test",
            "city": "Wien",
            "postal_code": "1010",
            "purchase_date": (date.today() + timedelta(days=1)).isoformat(),
            "purchase_price": 100000.00
        }
        response = client.post(
            "/api/v1/properties",
            json=property_data,
            headers=auth_headers
        )
        assert response.status_code == 422
        
        # Invalid purchase price
        property_data["purchase_date"] = "2020-01-01"
        property_data["purchase_price"] = -1000
        response = client.post(
            "/api/v1/properties",
            json=property_data,
            headers=auth_headers
        )
        assert response.status_code == 422
    
    def test_create_property_unauthorized(self, client):
        """Test property creation without authentication"""
        property_data = {
            "street": "Test",
            "city": "Wien",
            "postal_code": "1010",
            "purchase_date": "2020-01-01",
            "purchase_price": 100000.00
        }
        
        response = client.post("/api/v1/properties", json=property_data)
        assert response.status_code == 401


class TestListProperties:
    """Tests for GET /api/v1/properties"""
    
    def test_list_properties(self, client, auth_headers, test_property):
        """Test listing properties"""
        response = client.get("/api/v1/properties", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["properties"]) == 1
        assert data["properties"][0]["address"] == "Hauptstraße 123, 1010 Wien"
    
    def test_list_properties_exclude_archived(self, client, auth_headers, db, test_user):
        """Test that archived properties are excluded by default"""
        # Create active property
        active_prop = Property(
            user_id=test_user.id,
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100.00"),
            address="Active Street 1, 1010 Wien",
            street="Active Street 1",
            city="Wien",
            postal_code="1010",
            purchase_date=date(2020, 1, 1),
            purchase_price=Decimal("200000.00"),
            building_value=Decimal("160000.00"),
            land_value=Decimal("40000.00"),
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db.add(active_prop)
        
        # Create archived property
        archived_prop = Property(
            user_id=test_user.id,
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100.00"),
            address="Archived Street 2, 1010 Wien",
            street="Archived Street 2",
            city="Wien",
            postal_code="1010",
            purchase_date=date(2019, 1, 1),
            purchase_price=Decimal("150000.00"),
            building_value=Decimal("120000.00"),
            land_value=Decimal("30000.00"),
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.SOLD,
            sale_date=date(2023, 12, 31)
        )
        db.add(archived_prop)
        db.commit()
        
        # List without include_archived
        response = client.get("/api/v1/properties", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["include_archived"] is False
        
        # List with include_archived
        response = client.get(
            "/api/v1/properties?include_archived=true",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["include_archived"] is True


class TestGetProperty:
    """Tests for GET /api/v1/properties/{property_id}"""
    
    def test_get_property_success(self, client, auth_headers, test_property):
        """Test getting property details"""
        response = client.get(
            f"/api/v1/properties/{test_property.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_property.id)
        assert data["address"] == "Hauptstraße 123, 1010 Wien"
        assert "metrics" in data
    
    def test_get_property_not_found(self, client, auth_headers):
        """Test getting non-existent property"""
        fake_id = uuid4()
        response = client.get(
            f"/api/v1/properties/{fake_id}",
            headers=auth_headers
        )
        assert response.status_code == 404
    
    def test_get_property_forbidden(self, client, db, test_property):
        """Test getting property owned by another user"""
        # Create another user
        other_user = User(
            email="other@example.com",
            hashed_password="hashed",
            name="Other User",
            user_type=UserType.EMPLOYEE,
            is_active=True
        )
        db.add(other_user)
        db.commit()
        
        # Create token for other user
        token = create_access_token(subject=other_user.email)
        headers = {"Authorization": f"Bearer {token}"}
        
        response = client.get(
            f"/api/v1/properties/{test_property.id}",
            headers=headers
        )
        assert response.status_code == 403


class TestUpdateProperty:
    """Tests for PUT /api/v1/properties/{property_id}"""
    
    def test_update_property_success(self, client, auth_headers, test_property):
        """Test updating property"""
        update_data = {
            "street": "Updated Street 999",
            "depreciation_rate": 0.025
        }
        
        response = client.put(
            f"/api/v1/properties/{test_property.id}",
            json=update_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["street"] == "Updated Street 999"
        assert data["depreciation_rate"] == "0.0250"
        # Check that address was recalculated
        assert "Updated Street 999" in data["address"]


class TestDeleteProperty:
    """Tests for DELETE /api/v1/properties/{property_id}"""
    
    def test_delete_property_success(self, client, auth_headers, test_property):
        """Test deleting property without transactions"""
        response = client.delete(
            f"/api/v1/properties/{test_property.id}",
            headers=auth_headers
        )
        assert response.status_code == 204
    
    def test_delete_property_with_transactions(self, client, auth_headers, db, test_property, test_user):
        """Test that property with transactions cannot be deleted"""
        # Create a transaction linked to property
        transaction = Transaction(
            user_id=test_user.id,
            property_id=test_property.id,
            type=TransactionType.INCOME,
            amount=Decimal("1000.00"),
            transaction_date=date.today(),
            description="Rental income",
            income_category=IncomeCategory.RENTAL
        )
        db.add(transaction)
        db.commit()
        
        response = client.delete(
            f"/api/v1/properties/{test_property.id}",
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "linked transaction" in response.json()["detail"].lower()


class TestArchiveProperty:
    """Tests for POST /api/v1/properties/{property_id}/archive"""
    
    def test_archive_property_success(self, client, auth_headers, test_property):
        """Test archiving property"""
        sale_date = "2024-12-31"
        response = client.post(
            f"/api/v1/properties/{test_property.id}/archive?sale_date={sale_date}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "sold"
        assert data["sale_date"] == sale_date
    
    def test_archive_property_invalid_date(self, client, auth_headers, test_property):
        """Test archiving with sale_date before purchase_date"""
        # Property purchased on 2020-06-15
        sale_date = "2020-01-01"
        response = client.post(
            f"/api/v1/properties/{test_property.id}/archive?sale_date={sale_date}",
            headers=auth_headers
        )
        assert response.status_code == 400


class TestPropertyTransactions:
    """Tests for property-transaction linking endpoints"""
    
    def test_get_property_transactions(self, client, auth_headers, db, test_property, test_user):
        """Test getting transactions for a property"""
        # Create transactions
        for i in range(3):
            transaction = Transaction(
                user_id=test_user.id,
                property_id=test_property.id,
                type=TransactionType.INCOME,
                amount=Decimal("1000.00"),
                transaction_date=date(2024, i+1, 1),
                description=f"Rental income {i+1}",
                income_category=IncomeCategory.RENTAL
            )
            db.add(transaction)
        db.commit()
        
        response = client.get(
            f"/api/v1/properties/{test_property.id}/transactions",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["transactions"]) == 3
    
    def test_link_transaction(self, client, auth_headers, db, test_property, test_user):
        """Test linking a transaction to a property"""
        # Create unlinked transaction
        transaction = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("500.00"),
            transaction_date=date.today(),
            description="Maintenance",
            expense_category=ExpenseCategory.MAINTENANCE
        )
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        
        response = client.post(
            f"/api/v1/properties/{test_property.id}/link-transaction?transaction_id={transaction.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Transaction linked successfully"
        assert data["transaction"]["property_id"] == str(test_property.id)
    
    def test_unlink_transaction(self, client, auth_headers, db, test_property, test_user):
        """Test unlinking a transaction from a property"""
        # Create linked transaction
        transaction = Transaction(
            user_id=test_user.id,
            property_id=test_property.id,
            type=TransactionType.INCOME,
            amount=Decimal("1000.00"),
            transaction_date=date.today(),
            description="Rental income",
            income_category=IncomeCategory.RENTAL
        )
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        
        response = client.delete(
            f"/api/v1/properties/{test_property.id}/unlink-transaction/{transaction.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Transaction unlinked successfully"
        assert data["property_id"] is None
