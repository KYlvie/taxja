"""
Tests for E1 Import Service property linking functionality.

Tests the extension of E1FormImportService to suggest property linking
when KZ 350 (rental income) is detected.
"""
import pytest
from datetime import date
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.user import User
from app.models.property import Property, PropertyType, PropertyStatus
from app.models.transaction import Transaction, TransactionType, IncomeCategory
from app.services.e1_form_import_service import E1FormImportService
from app.services.e1_form_extractor import E1FormData


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
def test_user(db):
    """Create a test user"""
    user = User(
        email="test@example.com",
        name="Test User",
        hashed_password="hashed",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_property(db, test_user: User):
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
        status=PropertyStatus.ACTIVE,
    )
    db.add(property)
    db.commit()
    db.refresh(property)
    return property


@pytest.fixture
def e1_service(db):
    """Create E1FormImportService instance"""
    return E1FormImportService(db)


class TestE1PropertyLinking:
    """Test E1 import service property linking functionality"""
    
    def test_import_with_rental_income_sets_linking_flag(
        self, e1_service: E1FormImportService, test_user: User
    ):
        """Test that importing E1 with KZ 350 sets requires_property_linking flag"""
        e1_data = E1FormData(
            tax_year=2025,
            taxpayer_name="Test User",
            steuernummer="12-345/6789",
            kz_350=Decimal("12000.00"),  # Rental income
            confidence=0.95,
        )
        
        result = e1_service.import_e1_data(e1_data, test_user.id)
        
        assert result["requires_property_linking"] is True
        assert "property_linking_suggestions" in result
        assert result["transactions_created"] == 1
        assert result["transactions"][0]["kz"] == "350"
    
    def test_import_without_rental_income_no_linking_flag(
        self, e1_service: E1FormImportService, test_user: User
    ):
        """Test that importing E1 without KZ 350 does not set linking flag"""
        e1_data = E1FormData(
            tax_year=2025,
            taxpayer_name="Test User",
            steuernummer="12-345/6789",
            kz_245=Decimal("45000.00"),  # Employment income only
            confidence=0.95,
        )
        
        result = e1_service.import_e1_data(e1_data, test_user.id)
        
        assert result["requires_property_linking"] is False
        assert result["property_linking_suggestions"] == []
    
    def test_property_suggestions_without_address_hint(
        self, e1_service: E1FormImportService, test_user: User, test_property: Property
    ):
        """Test property suggestions when no address hint is available (typical E1 case)"""
        e1_data = E1FormData(
            tax_year=2025,
            taxpayer_name="Test User",
            steuernummer="12-345/6789",
            kz_350=Decimal("12000.00"),
            confidence=0.95,
        )
        
        result = e1_service.import_e1_data(e1_data, test_user.id)
        
        suggestions = result["property_linking_suggestions"]
        assert len(suggestions) == 1
        assert suggestions[0]["property_id"] == str(test_property.id)
        assert suggestions[0]["address"] == test_property.address
        assert suggestions[0]["confidence"] == 0.0  # No matching performed
        assert suggestions[0]["suggested_action"] == "manual_select"
    
    def test_property_suggestions_with_multiple_properties(
        self, e1_service: E1FormImportService, test_user: User, db
    ):
        """Test property suggestions when user has multiple properties"""
        # Create multiple properties
        properties = []
        for i in range(3):
            prop = Property(
                user_id=test_user.id,
                property_type=PropertyType.RENTAL,
                rental_percentage=Decimal("100.00"),
                address=f"Teststraße {i+1}, 1010 Wien",
                street=f"Teststraße {i+1}",
                city="Wien",
                postal_code="1010",
                purchase_date=date(2020, 1, 1),
                purchase_price=Decimal("300000.00"),
                building_value=Decimal("240000.00"),
                land_value=Decimal("60000.00"),
                depreciation_rate=Decimal("0.02"),
                status=PropertyStatus.ACTIVE,
            )
            db.add(prop)
            properties.append(prop)
        
        db.commit()
        
        e1_data = E1FormData(
            tax_year=2025,
            taxpayer_name="Test User",
            kz_350=Decimal("12000.00"),
            confidence=0.95,
        )
        
        result = e1_service.import_e1_data(e1_data, test_user.id)
        
        suggestions = result["property_linking_suggestions"]
        assert len(suggestions) == 3
        
        # All properties should be suggested for manual selection
        property_ids = {s["property_id"] for s in suggestions}
        expected_ids = {str(p.id) for p in properties}
        assert property_ids == expected_ids
    
    def test_property_suggestions_excludes_archived_properties(
        self, e1_service: E1FormImportService, test_user: User, db
    ):
        """Test that archived properties are not included in suggestions"""
        # Create active property
        active_prop = Property(
            user_id=test_user.id,
            property_type=PropertyType.RENTAL,
            address="Active Street 1, 1010 Wien",
            street="Active Street 1",
            city="Wien",
            postal_code="1010",
            purchase_date=date(2020, 1, 1),
            purchase_price=Decimal("300000.00"),
            building_value=Decimal("240000.00"),
            land_value=Decimal("60000.00"),
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE,
        )
        
        # Create archived property
        archived_prop = Property(
            user_id=test_user.id,
            property_type=PropertyType.RENTAL,
            address="Archived Street 1, 1010 Wien",
            street="Archived Street 1",
            city="Wien",
            postal_code="1010",
            purchase_date=date(2018, 1, 1),
            purchase_price=Decimal("300000.00"),
            building_value=Decimal("240000.00"),
            land_value=Decimal("60000.00"),
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ARCHIVED,
            sale_date=date(2024, 12, 31),
        )
        
        db.add_all([active_prop, archived_prop])
        db.commit()
        
        e1_data = E1FormData(
            tax_year=2025,
            kz_350=Decimal("12000.00"),
            confidence=0.95,
        )
        
        result = e1_service.import_e1_data(e1_data, test_user.id)
        
        suggestions = result["property_linking_suggestions"]
        assert len(suggestions) == 1
        assert suggestions[0]["property_id"] == str(active_prop.id)
    
    def test_link_imported_rental_income_success(
        self, 
        e1_service: E1FormImportService, 
        test_user: User, 
        test_property: Property,
        db
    ):
        """Test successfully linking a rental income transaction to a property"""
        # Import E1 with rental income
        e1_data = E1FormData(
            tax_year=2025,
            kz_350=Decimal("12000.00"),
            confidence=0.95,
        )
        
        result = e1_service.import_e1_data(e1_data, test_user.id)
        transaction_id = result["transactions"][0]["id"]
        
        # Link transaction to property
        updated_txn = e1_service.link_imported_rental_income(
            transaction_id=transaction_id,
            property_id=test_property.id,
            user_id=test_user.id
        )
        
        assert updated_txn.property_id == test_property.id
        assert updated_txn.user_id == test_user.id
        
        # Verify in database
        txn_from_db = db.query(Transaction).filter(
            Transaction.id == transaction_id
        ).first()
        assert txn_from_db.property_id == test_property.id
    
    def test_link_imported_rental_income_invalid_transaction(
        self, e1_service: E1FormImportService, test_user: User, test_property: Property
    ):
        """Test linking with invalid transaction ID raises error"""
        with pytest.raises(ValueError, match="Transaction .* not found"):
            e1_service.link_imported_rental_income(
                transaction_id=99999,
                property_id=test_property.id,
                user_id=test_user.id
            )
    
    def test_link_imported_rental_income_invalid_property(
        self, 
        e1_service: E1FormImportService, 
        test_user: User,
        db
    ):
        """Test linking with invalid property ID raises error"""
        # Create a transaction
        e1_data = E1FormData(
            tax_year=2025,
            kz_350=Decimal("12000.00"),
            confidence=0.95,
        )
        
        result = e1_service.import_e1_data(e1_data, test_user.id)
        transaction_id = result["transactions"][0]["id"]
        
        # Try to link to non-existent property
        fake_property_id = uuid4()
        with pytest.raises(ValueError, match="Property .* not found"):
            e1_service.link_imported_rental_income(
                transaction_id=transaction_id,
                property_id=fake_property_id,
                user_id=test_user.id
            )
    
    def test_link_imported_rental_income_wrong_user(
        self, 
        e1_service: E1FormImportService, 
        test_user: User,
        test_property: Property,
        db
    ):
        """Test linking transaction from different user raises error"""
        # Create another user
        other_user = User(
            email="other@example.com",
            name="Other User",
            hashed_password="hashed",
        )
        db.add(other_user)
        db.commit()
        
        # Create transaction for test_user
        e1_data = E1FormData(
            tax_year=2025,
            kz_350=Decimal("12000.00"),
            confidence=0.95,
        )
        
        result = e1_service.import_e1_data(e1_data, test_user.id)
        transaction_id = result["transactions"][0]["id"]
        
        # Try to link as other_user
        with pytest.raises(ValueError, match="not found or does not belong to user"):
            e1_service.link_imported_rental_income(
                transaction_id=transaction_id,
                property_id=test_property.id,
                user_id=other_user.id
            )
    
    def test_rental_income_transaction_created_correctly(
        self, 
        e1_service: E1FormImportService, 
        test_user: User,
        db
    ):
        """Test that rental income transaction is created with correct attributes"""
        e1_data = E1FormData(
            tax_year=2025,
            kz_350=Decimal("12000.00"),
            confidence=0.95,
        )
        
        result = e1_service.import_e1_data(e1_data, test_user.id)
        transaction_id = result["transactions"][0]["id"]
        
        # Verify transaction in database
        txn = db.query(Transaction).filter(
            Transaction.id == transaction_id
        ).first()
        
        assert txn is not None
        assert txn.type == TransactionType.INCOME
        assert txn.amount == Decimal("12000.00")
        assert txn.income_category == IncomeCategory.RENTAL
        assert txn.import_source == "e1_import"
        assert txn.property_id is None  # Not linked yet
        assert "Vermietung und Verpachtung" in txn.description
    
    def test_negative_kz_350_creates_expense(
        self, 
        e1_service: E1FormImportService, 
        test_user: User,
        db
    ):
        """Test that negative KZ 350 creates expense transaction"""
        e1_data = E1FormData(
            tax_year=2025,
            kz_350=Decimal("-5000.00"),  # Negative = expense
            confidence=0.95,
        )
        
        result = e1_service.import_e1_data(e1_data, test_user.id)
        
        assert result["requires_property_linking"] is True
        transaction_id = result["transactions"][0]["id"]
        
        txn = db.query(Transaction).filter(
            Transaction.id == transaction_id
        ).first()
        
        assert txn.type == TransactionType.EXPENSE
        assert txn.amount == Decimal("5000.00")  # Absolute value
        assert txn.is_deductible is True


class TestPropertySuggestionActions:
    """Test suggested action determination based on confidence scores"""
    
    def test_determine_action_high_confidence(self, e1_service: E1FormImportService):
        """Test action for high confidence match (>0.9)"""
        action = e1_service._determine_action(0.95)
        assert action == "auto_link"
    
    def test_determine_action_medium_confidence(self, e1_service: E1FormImportService):
        """Test action for medium confidence match (0.7-0.9)"""
        action = e1_service._determine_action(0.8)
        assert action == "suggest"
        
        action = e1_service._determine_action(0.7)
        assert action == "suggest"
    
    def test_determine_action_low_confidence(self, e1_service: E1FormImportService):
        """Test action for low confidence match (<0.7)"""
        action = e1_service._determine_action(0.6)
        assert action == "manual_select"
        
        action = e1_service._determine_action(0.0)
        assert action == "manual_select"
