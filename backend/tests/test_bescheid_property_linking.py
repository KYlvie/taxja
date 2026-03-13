"""
Tests for Bescheid Import Service property linking functionality.

Tests the integration between BescheidImportService and AddressMatcher
for automatic property linking suggestions during Bescheid import.
"""
import pytest
from decimal import Decimal
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.db.base import Base
from app.models.user import User, UserType
from app.models.property import Property, PropertyStatus, PropertyType
from app.services.bescheid_import_service import BescheidImportService
from app.services.bescheid_extractor import BescheidData


# Test database setup
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def db_session():
    """Create a test database session"""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a test user"""
    user = User(
        email="test@example.com",
        name="Test User",
        password_hash="hashed",
        user_type=UserType.LANDLORD
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_property(db_session: Session, test_user: User) -> Property:
    """Create a test property"""
    property = Property(
        user_id=test_user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        street="Hauptstraße 123",
        city="Wien",
        postal_code="1010",
        address="Hauptstraße 123, 1010 Wien",
        purchase_date=date(2020, 1, 1),
        purchase_price=Decimal("350000.00"),
        building_value=Decimal("280000.00"),
        depreciation_rate=Decimal("0.02"),
        status=PropertyStatus.ACTIVE
    )
    db_session.add(property)
    db_session.commit()
    db_session.refresh(property)
    return property


@pytest.fixture
def bescheid_service(db_session: Session) -> BescheidImportService:
    """Create BescheidImportService instance"""
    return BescheidImportService(db_session)


class TestBescheidPropertyLinking:
    """Test property linking suggestions during Bescheid import"""

    def test_import_with_exact_address_match(
        self, db_session: Session, bescheid_service: BescheidImportService, 
        test_user: User, test_property: Property
    ):
        """Test import with exact address match suggests auto_link"""
        bescheid_data = BescheidData(
            tax_year=2025,
            taxpayer_name="Test User",
            einkommen=Decimal("50000.00"),
            vermietung_details=[
                {
                    "address": "Hauptstraße 123, 1010 Wien",
                    "amount": Decimal("12000.00")
                }
            ]
        )
        
        result = bescheid_service.import_bescheid_data(
            bescheid_data, test_user.id
        )
        
        # Check that transaction was created
        assert result["transactions_created"] == 1
        assert len(result["transactions"]) == 1
        
        # Check property linking suggestions
        assert result["requires_property_linking"] is True
        assert len(result["property_linking_suggestions"]) == 1
        
        suggestion = result["property_linking_suggestions"][0]
        assert suggestion["extracted_address"] == "Hauptstraße 123, 1010 Wien"
        assert suggestion["matched_property_id"] == str(test_property.id)
        assert suggestion["confidence_score"] >= 0.9
        assert suggestion["suggested_action"] == "auto_link"
        assert suggestion["match_details"]["street_match"] is True

    def test_import_with_partial_address_match(
        self, db_session: Session, bescheid_service: BescheidImportService,
        test_user: User, test_property: Property
    ):
        """Test import with partial address match suggests suggest action"""
        bescheid_data = BescheidData(
            tax_year=2025,
            taxpayer_name="Test User",
            einkommen=Decimal("50000.00"),
            vermietung_details=[
                {
                    "address": "Hauptstr. 123, Wien",  # Abbreviated street name
                    "amount": Decimal("12000.00")
                }
            ]
        )
        
        result = bescheid_service.import_bescheid_data(
            bescheid_data, test_user.id
        )
        
        # Check property linking suggestions
        assert result["requires_property_linking"] is True
        assert len(result["property_linking_suggestions"]) == 1
        
        suggestion = result["property_linking_suggestions"][0]
        assert suggestion["extracted_address"] == "Hauptstr. 123, Wien"
        assert suggestion["matched_property_id"] == str(test_property.id)
        # Confidence should be medium (0.7-0.9)
        assert 0.7 <= suggestion["confidence_score"] < 0.9
        assert suggestion["suggested_action"] == "suggest"

    def test_import_with_no_address_match(
        self, db_session: Session, bescheid_service: BescheidImportService,
        test_user: User, test_property: Property
    ):
        """Test import with no address match suggests create_new"""
        bescheid_data = BescheidData(
            tax_year=2025,
            taxpayer_name="Test User",
            einkommen=Decimal("50000.00"),
            vermietung_details=[
                {
                    "address": "Mariahilfer Straße 456, 1060 Wien",  # Different address
                    "amount": Decimal("12000.00")
                }
            ]
        )
        
        result = bescheid_service.import_bescheid_data(
            bescheid_data, test_user.id
        )
        
        # Check property linking suggestions
        assert result["requires_property_linking"] is True
        assert len(result["property_linking_suggestions"]) == 1
        
        suggestion = result["property_linking_suggestions"][0]
        assert suggestion["extracted_address"] == "Mariahilfer Straße 456, 1060 Wien"
        assert suggestion["matched_property_id"] is None
        assert suggestion["confidence_score"] == 0.0
        assert suggestion["suggested_action"] == "create_new"

    def test_import_with_multiple_properties(
        self, db_session: Session, bescheid_service: BescheidImportService,
        test_user: User, test_property: Property
    ):
        """Test import with multiple rental properties"""
        # Create second property
        property2 = Property(
            user_id=test_user.id,
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100.00"),
            street="Mariahilfer Straße 456",
            city="Wien",
            postal_code="1060",
            address="Mariahilfer Straße 456, 1060 Wien",
            purchase_date=date(2021, 1, 1),
            purchase_price=Decimal("400000.00"),
            building_value=Decimal("320000.00"),
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db_session.add(property2)
        db_session.commit()
        
        bescheid_data = BescheidData(
            tax_year=2025,
            taxpayer_name="Test User",
            einkommen=Decimal("50000.00"),
            vermietung_details=[
                {
                    "address": "Hauptstraße 123, 1010 Wien",
                    "amount": Decimal("12000.00")
                },
                {
                    "address": "Mariahilfer Straße 456, 1060 Wien",
                    "amount": Decimal("15000.00")
                }
            ]
        )
        
        result = bescheid_service.import_bescheid_data(
            bescheid_data, test_user.id
        )
        
        # Check that both transactions were created
        assert result["transactions_created"] == 2
        
        # Check property linking suggestions for both
        assert result["requires_property_linking"] is True
        assert len(result["property_linking_suggestions"]) == 2
        
        # First property should match test_property
        suggestion1 = result["property_linking_suggestions"][0]
        assert suggestion1["matched_property_id"] == str(test_property.id)
        assert suggestion1["suggested_action"] in ["auto_link", "suggest"]
        
        # Second property should match property2
        suggestion2 = result["property_linking_suggestions"][1]
        assert suggestion2["matched_property_id"] == str(property2.id)
        assert suggestion2["suggested_action"] in ["auto_link", "suggest"]

    def test_import_without_vermietung_details(
        self, db_session: Session, bescheid_service: BescheidImportService,
        test_user: User
    ):
        """Test import without rental income doesn't generate suggestions"""
        bescheid_data = BescheidData(
            tax_year=2025,
            taxpayer_name="Test User",
            einkommen=Decimal("50000.00"),
            einkuenfte_nichtselbstaendig=Decimal("50000.00")
        )
        
        result = bescheid_service.import_bescheid_data(
            bescheid_data, test_user.id
        )
        
        # Check that no property linking suggestions were generated
        assert result["requires_property_linking"] is False
        assert len(result["property_linking_suggestions"]) == 0

    def test_import_with_empty_address(
        self, db_session: Session, bescheid_service: BescheidImportService,
        test_user: User, test_property: Property
    ):
        """Test import with empty address doesn't generate suggestions"""
        bescheid_data = BescheidData(
            tax_year=2025,
            taxpayer_name="Test User",
            einkommen=Decimal("50000.00"),
            vermietung_details=[
                {
                    "address": "",  # Empty address
                    "amount": Decimal("12000.00")
                }
            ]
        )
        
        result = bescheid_service.import_bescheid_data(
            bescheid_data, test_user.id
        )
        
        # Transaction should be created but no linking suggestions
        assert result["transactions_created"] == 1
        assert result["requires_property_linking"] is False
        assert len(result["property_linking_suggestions"]) == 0

    def test_import_with_alternative_matches(
        self, db_session: Session, bescheid_service: BescheidImportService,
        test_user: User, test_property: Property
    ):
        """Test that alternative matches are included in suggestions"""
        # Create similar properties
        property2 = Property(
            user_id=test_user.id,
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100.00"),
            street="Hauptstraße 125",  # Similar address
            city="Wien",
            postal_code="1010",
            address="Hauptstraße 125, 1010 Wien",
            purchase_date=date(2021, 1, 1),
            purchase_price=Decimal("400000.00"),
            building_value=Decimal("320000.00"),
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db_session.add(property2)
        db_session.commit()
        
        bescheid_data = BescheidData(
            tax_year=2025,
            taxpayer_name="Test User",
            einkommen=Decimal("50000.00"),
            vermietung_details=[
                {
                    "address": "Hauptstraße 123, Wien",
                    "amount": Decimal("12000.00")
                }
            ]
        )
        
        result = bescheid_service.import_bescheid_data(
            bescheid_data, test_user.id
        )
        
        suggestion = result["property_linking_suggestions"][0]
        
        # Should have alternative matches
        assert "alternative_matches" in suggestion
        # May have 0-2 alternatives depending on matching scores
        assert len(suggestion["alternative_matches"]) <= 2

    def test_import_with_negative_rental_income(
        self, db_session: Session, bescheid_service: BescheidImportService,
        test_user: User, test_property: Property
    ):
        """Test import with negative rental income (loss) still generates suggestions"""
        bescheid_data = BescheidData(
            tax_year=2025,
            taxpayer_name="Test User",
            einkommen=Decimal("50000.00"),
            vermietung_details=[
                {
                    "address": "Hauptstraße 123, 1010 Wien",
                    "amount": Decimal("-5000.00")  # Rental loss
                }
            ]
        )
        
        result = bescheid_service.import_bescheid_data(
            bescheid_data, test_user.id
        )
        
        # Transaction should be created as expense
        assert result["transactions_created"] == 1
        assert result["transactions"][0]["type"] == "expense"
        
        # Property linking suggestions should still be generated
        assert result["requires_property_linking"] is True
        assert len(result["property_linking_suggestions"]) == 1
        
        suggestion = result["property_linking_suggestions"][0]
        assert suggestion["matched_property_id"] == str(test_property.id)
