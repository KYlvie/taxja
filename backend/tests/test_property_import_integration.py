"""
Integration tests for E1/Bescheid import with property linking.

Tests the end-to-end flow:
1. Import E1/Bescheid with rental income
2. Property linking suggestions generated
3. Link transaction to property
4. Backfill historical depreciation
5. Verify transactions created correctly
"""
import pytest
from datetime import date
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.db.base import Base
from app.models.user import User, UserType
from app.models.property import Property, PropertyType, PropertyStatus
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.services.e1_form_import_service import E1FormImportService
from app.services.bescheid_import_service import BescheidImportService
from app.services.property_service import PropertyService
from app.services.historical_depreciation_service import HistoricalDepreciationService
from app.services.e1_form_extractor import E1FormData
from app.services.bescheid_extractor import BescheidData
from app.schemas.property import PropertyCreate


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
        email="landlord@example.com",
        name="Test Landlord",
        hashed_password="hashed",
        user_type=UserType.LANDLORD
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def existing_property(db_session: Session, test_user: User) -> Property:
    """Create an existing property for matching tests"""
    property = Property(
        user_id=test_user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        street="Hauptstraße 123",
        city="Wien",
        postal_code="1010",
        address="Hauptstraße 123, 1010 Wien",
        purchase_date=date(2020, 6, 15),
        purchase_price=Decimal("350000.00"),
        building_value=Decimal("280000.00"),
        construction_year=1985,
        depreciation_rate=Decimal("0.02"),
        status=PropertyStatus.ACTIVE
    )
    db_session.add(property)
    db_session.commit()
    db_session.refresh(property)
    return property


@pytest.fixture
def e1_service(db_session: Session) -> E1FormImportService:
    """Create E1FormImportService instance"""
    return E1FormImportService(db_session)


@pytest.fixture
def bescheid_service(db_session: Session) -> BescheidImportService:
    """Create BescheidImportService instance"""
    return BescheidImportService(db_session)


@pytest.fixture
def property_service(db_session: Session) -> PropertyService:
    """Create PropertyService instance"""
    return PropertyService(db_session)


@pytest.fixture
def historical_service(db_session: Session) -> HistoricalDepreciationService:
    """Create HistoricalDepreciationService instance"""
    return HistoricalDepreciationService(db_session)


class TestE1ImportPropertyLinkingIntegration:
    """Integration tests for E1 import with property linking"""

    def test_e1_import_triggers_property_linking_suggestions(
        self, e1_service: E1FormImportService, test_user: User, existing_property: Property
    ):
        """Test that E1 import with KZ 350 triggers property linking suggestions"""
        # Import E1 with rental income
        e1_data = E1FormData(
            tax_year=2025,
            taxpayer_name="Test Landlord",
            steuernummer="12-345/6789",
            kz_350=Decimal("12000.00"),  # Rental income
            confidence=0.95,
        )
        
        result = e1_service.import_e1_data(e1_data, test_user.id)
        
        # Verify property linking flag is set
        assert result["requires_property_linking"] is True
        assert len(result["property_linking_suggestions"]) == 1
        
        # Verify suggestion includes existing property
        suggestion = result["property_linking_suggestions"][0]
        assert suggestion["property_id"] == str(existing_property.id)
        assert suggestion["address"] == existing_property.address
        assert suggestion["suggested_action"] == "manual_select"
        
        # Verify transaction was created
        assert result["transactions_created"] == 1
        assert result["transactions"][0]["category"] == "rental"

    def test_e1_import_link_to_existing_property_success(
        self,
        e1_service: E1FormImportService,
        test_user: User,
        existing_property: Property,
        db_session: Session
    ):
        """Test linking imported E1 rental income to existing property"""
        # Import E1
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
            property_id=existing_property.id,
            user_id=test_user.id
        )
        
        # Verify linking
        assert updated_txn.property_id == existing_property.id
        
        # Verify in database
        txn_from_db = db_session.query(Transaction).filter(
            Transaction.id == transaction_id
        ).first()
        assert txn_from_db.property_id == existing_property.id
        assert txn_from_db.income_category == IncomeCategory.RENTAL

    def test_e1_import_low_confidence_suggests_create_new(
        self, e1_service: E1FormImportService, test_user: User
    ):
        """Test that E1 import without matching property suggests creating new"""
        # Import E1 with rental income but no existing properties
        e1_data = E1FormData(
            tax_year=2025,
            kz_350=Decimal("12000.00"),
            confidence=0.95,
        )
        
        result = e1_service.import_e1_data(e1_data, test_user.id)
        
        # Should still require property linking
        assert result["requires_property_linking"] is True
        
        # But no properties to suggest
        assert len(result["property_linking_suggestions"]) == 0


class TestBescheidImportPropertyLinkingIntegration:
    """Integration tests for Bescheid import with property linking"""

    def test_bescheid_import_with_exact_address_match(
        self,
        bescheid_service: BescheidImportService,
        test_user: User,
        existing_property: Property
    ):
        """Test Bescheid import with exact address triggers high confidence match"""
        bescheid_data = BescheidData(
            tax_year=2025,
            taxpayer_name="Test Landlord",
            einkommen=Decimal("50000.00"),
            vermietung_details=[
                {
                    "address": "Hauptstraße 123, 1010 Wien",
                    "amount": Decimal("12000.00")
                }
            ]
        )
        
        result = bescheid_service.import_bescheid_data(bescheid_data, test_user.id)
        
        # Verify property linking suggestions
        assert result["requires_property_linking"] is True
        assert len(result["property_linking_suggestions"]) == 1
        
        suggestion = result["property_linking_suggestions"][0]
        assert suggestion["matched_property_id"] == str(existing_property.id)
        assert suggestion["confidence_score"] >= 0.9
        assert suggestion["suggested_action"] == "auto_link"
        assert suggestion["match_details"]["street_match"] is True

    def test_bescheid_import_with_partial_address_match(
        self,
        bescheid_service: BescheidImportService,
        test_user: User,
        existing_property: Property
    ):
        """Test Bescheid import with partial address triggers medium confidence"""
        bescheid_data = BescheidData(
            tax_year=2025,
            taxpayer_name="Test Landlord",
            einkommen=Decimal("50000.00"),
            vermietung_details=[
                {
                    "address": "Hauptstr. 123, Wien",  # Abbreviated
                    "amount": Decimal("12000.00")
                }
            ]
        )
        
        result = bescheid_service.import_bescheid_data(bescheid_data, test_user.id)
        
        # Verify medium confidence suggestion
        assert result["requires_property_linking"] is True
        suggestion = result["property_linking_suggestions"][0]
        assert suggestion["matched_property_id"] == str(existing_property.id)
        assert 0.7 <= suggestion["confidence_score"] < 0.9
        assert suggestion["suggested_action"] == "suggest"

    def test_bescheid_import_no_match_suggests_create_new(
        self,
        bescheid_service: BescheidImportService,
        test_user: User,
        existing_property: Property
    ):
        """Test Bescheid import with no address match suggests creating new property"""
        bescheid_data = BescheidData(
            tax_year=2025,
            taxpayer_name="Test Landlord",
            einkommen=Decimal("50000.00"),
            vermietung_details=[
                {
                    "address": "Mariahilfer Straße 456, 1060 Wien",  # Different
                    "amount": Decimal("15000.00")
                }
            ]
        )
        
        result = bescheid_service.import_bescheid_data(bescheid_data, test_user.id)
        
        # Verify create_new suggestion
        assert result["requires_property_linking"] is True
        suggestion = result["property_linking_suggestions"][0]
        assert suggestion["matched_property_id"] is None
        assert suggestion["confidence_score"] == 0.0
        assert suggestion["suggested_action"] == "create_new"


class TestEndToEndPropertyImportFlow:
    """End-to-end integration tests for complete property import workflow"""

    def test_complete_flow_import_link_backfill(
        self,
        bescheid_service: BescheidImportService,
        property_service: PropertyService,
        historical_service: HistoricalDepreciationService,
        test_user: User,
        db_session: Session
    ):
        """
        Test complete flow: import → link → backfill → verify
        
        Scenario: User imports Bescheid with rental income for a property
        purchased in 2020, links it to newly created property, and backfills
        historical depreciation.
        """
        # Step 1: Import Bescheid with rental income
        bescheid_data = BescheidData(
            tax_year=2025,
            taxpayer_name="Test Landlord",
            einkommen=Decimal("50000.00"),
            vermietung_details=[
                {
                    "address": "Teststraße 1, 1010 Wien",
                    "amount": Decimal("18000.00")
                }
            ]
        )
        
        import_result = bescheid_service.import_bescheid_data(
            bescheid_data, test_user.id
        )
        
        # Verify import created transaction
        assert import_result["transactions_created"] == 1
        assert import_result["requires_property_linking"] is True
        transaction_id = import_result["transactions"][0]["id"]
        
        # Step 2: Create new property (user chose "create_new")
        property_create = PropertyCreate(
            property_type=PropertyType.RENTAL,
            street="Teststraße 1",
            city="Wien",
            postal_code="1010",
            purchase_date=date(2020, 1, 1),
            purchase_price=Decimal("400000.00"),
            building_value=Decimal("320000.00"),
            construction_year=1990,
        )
        
        property = property_service.create_property(
            user_id=test_user.id,
            property_data=property_create
        )
        
        assert property.id is not None
        assert property.depreciation_rate == Decimal("0.02")
        
        # Step 3: Link transaction to property
        property_service.link_transaction_to_property(
            transaction_id=transaction_id,
            property_id=property.id,
            user_id=test_user.id
        )
        
        # Verify linking
        linked_txn = db_session.query(Transaction).filter(
            Transaction.id == transaction_id
        ).first()
        assert linked_txn.property_id == property.id
        
        # Step 4: Backfill historical depreciation
        backfill_result = historical_service.backfill_depreciation(
            property_id=property.id,
            user_id=test_user.id
        )
        
        # Verify backfill created depreciation for 2020-2025 (6 years)
        assert backfill_result.years_backfilled == 6
        assert backfill_result.total_amount == Decimal("33600.00")  # 5600 * 6
        
        # Step 5: Verify all transactions in database
        all_transactions = db_session.query(Transaction).filter(
            Transaction.user_id == test_user.id,
            Transaction.property_id == property.id
        ).order_by(Transaction.transaction_date).all()
        
        # Should have 7 transactions: 6 depreciation + 1 rental income
        assert len(all_transactions) == 7
        
        # Verify depreciation transactions
        depreciation_txns = [
            t for t in all_transactions
            if t.expense_category == ExpenseCategory.DEPRECIATION_AFA
        ]
        assert len(depreciation_txns) == 6
        
        # Verify first year (2020) has full year depreciation
        first_year_dep = next(
            t for t in depreciation_txns
            if t.transaction_date.year == 2020
        )
        assert first_year_dep.amount == Decimal("5600.00")
        assert first_year_dep.is_system_generated is True
        
        # Verify rental income transaction
        rental_txn = next(
            t for t in all_transactions
            if t.income_category == IncomeCategory.RENTAL
        )
        assert rental_txn.amount == Decimal("18000.00")
        assert rental_txn.property_id == property.id

    def test_import_multiple_properties_from_bescheid(
        self,
        bescheid_service: BescheidImportService,
        property_service: PropertyService,
        test_user: User,
        db_session: Session
    ):
        """Test importing Bescheid with multiple rental properties"""
        # Create two existing properties
        property1_create = PropertyCreate(
            property_type=PropertyType.RENTAL,
            street="Hauptstraße 123",
            city="Wien",
            postal_code="1010",
            purchase_date=date(2020, 1, 1),
            purchase_price=Decimal("350000.00"),
            building_value=Decimal("280000.00"),
        )
        property1 = property_service.create_property(
            user_id=test_user.id,
            property_data=property1_create
        )
        
        property2_create = PropertyCreate(
            property_type=PropertyType.RENTAL,
            street="Mariahilfer Straße 456",
            city="Wien",
            postal_code="1060",
            purchase_date=date(2021, 1, 1),
            purchase_price=Decimal("400000.00"),
            building_value=Decimal("320000.00"),
        )
        property2 = property_service.create_property(
            user_id=test_user.id,
            property_data=property2_create
        )
        
        # Import Bescheid with both properties
        bescheid_data = BescheidData(
            tax_year=2025,
            taxpayer_name="Test Landlord",
            einkommen=Decimal("80000.00"),
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
        
        result = bescheid_service.import_bescheid_data(bescheid_data, test_user.id)
        
        # Verify both transactions created
        assert result["transactions_created"] == 2
        assert result["requires_property_linking"] is True
        assert len(result["property_linking_suggestions"]) == 2
        
        # Verify both properties matched
        suggestion1 = result["property_linking_suggestions"][0]
        suggestion2 = result["property_linking_suggestions"][1]
        
        matched_ids = {
            suggestion1["matched_property_id"],
            suggestion2["matched_property_id"]
        }
        expected_ids = {str(property1.id), str(property2.id)}
        assert matched_ids == expected_ids

    def test_import_link_to_existing_then_backfill(
        self,
        e1_service: E1FormImportService,
        property_service: PropertyService,
        historical_service: HistoricalDepreciationService,
        test_user: User,
        db_session: Session
    ):
        """Test importing E1, linking to existing property, then backfilling"""
        # Create property purchased in previous year
        property_create = PropertyCreate(
            property_type=PropertyType.RENTAL,
            street="Teststraße 99",
            city="Wien",
            postal_code="1010",
            purchase_date=date(2023, 6, 15),
            purchase_price=Decimal("300000.00"),
            building_value=Decimal("240000.00"),
            construction_year=2000,
        )
        property = property_service.create_property(
            user_id=test_user.id,
            property_data=property_create
        )
        
        # Import E1 with rental income
        e1_data = E1FormData(
            tax_year=2025,
            kz_350=Decimal("10000.00"),
            confidence=0.95,
        )
        
        import_result = e1_service.import_e1_data(e1_data, test_user.id)
        transaction_id = import_result["transactions"][0]["id"]
        
        # Link to property
        e1_service.link_imported_rental_income(
            transaction_id=transaction_id,
            property_id=property.id,
            user_id=test_user.id
        )
        
        # Backfill depreciation
        backfill_result = historical_service.backfill_depreciation(
            property_id=property.id,
            user_id=test_user.id
        )
        
        # Should backfill for 2023 (partial), 2024, 2025 (3 years)
        assert backfill_result.years_backfilled == 3
        
        # Verify partial year 2023 (6.5 months: mid-June to Dec 31)
        dep_2023 = next(
            t for t in backfill_result.transactions
            if t.transaction_date.year == 2023
        )
        # (240000 * 0.02 * 6.5) / 12 = 2600
        assert dep_2023.amount == Decimal("2600.00")
        
        # Verify full years 2024 and 2025
        dep_2024 = next(
            t for t in backfill_result.transactions
            if t.transaction_date.year == 2024
        )
        assert dep_2024.amount == Decimal("4800.00")

    def test_create_new_property_from_import_suggestion(
        self,
        bescheid_service: BescheidImportService,
        property_service: PropertyService,
        test_user: User,
        db_session: Session
    ):
        """Test creating new property from import suggestion data"""
        # Import Bescheid with new property address
        bescheid_data = BescheidData(
            tax_year=2025,
            taxpayer_name="Test Landlord",
            einkommen=Decimal("50000.00"),
            vermietung_details=[
                {
                    "address": "Neubaugasse 77, 1070 Wien",
                    "amount": Decimal("14000.00")
                }
            ]
        )
        
        import_result = bescheid_service.import_bescheid_data(
            bescheid_data, test_user.id
        )
        
        # Verify suggestion to create new
        suggestion = import_result["property_linking_suggestions"][0]
        assert suggestion["suggested_action"] == "create_new"
        extracted_address = suggestion["extracted_address"]
        
        # User creates new property using extracted address
        property_create = PropertyCreate(
            property_type=PropertyType.RENTAL,
            street="Neubaugasse 77",
            city="Wien",
            postal_code="1070",
            purchase_date=date(2024, 1, 1),
            purchase_price=Decimal("380000.00"),
            building_value=Decimal("304000.00"),
        )
        property = property_service.create_property(
            user_id=test_user.id,
            property_data=property_create
        )
        
        # Link transaction to new property
        transaction_id = import_result["transactions"][0]["id"]
        property_service.link_transaction_to_property(
            transaction_id=transaction_id,
            property_id=property.id,
            user_id=test_user.id
        )
        
        # Verify linking
        txn = db_session.query(Transaction).filter(
            Transaction.id == transaction_id
        ).first()
        assert txn.property_id == property.id
        assert txn.amount == Decimal("14000.00")


class TestPropertyImportEdgeCases:
    """Test edge cases in property import integration"""

    def test_import_negative_rental_income_creates_expense(
        self,
        bescheid_service: BescheidImportService,
        existing_property: Property,
        test_user: User,
        db_session: Session
    ):
        """Test importing negative rental income (loss) still triggers linking"""
        bescheid_data = BescheidData(
            tax_year=2025,
            taxpayer_name="Test Landlord",
            einkommen=Decimal("50000.00"),
            vermietung_details=[
                {
                    "address": "Hauptstraße 123, 1010 Wien",
                    "amount": Decimal("-5000.00")  # Rental loss
                }
            ]
        )
        
        result = bescheid_service.import_bescheid_data(bescheid_data, test_user.id)
        
        # Should create expense transaction
        assert result["transactions_created"] == 1
        txn = result["transactions"][0]
        assert txn["type"] == "expense"
        assert txn["amount"] == 5000.00
        
        # Should still suggest property linking
        assert result["requires_property_linking"] is True
        suggestion = result["property_linking_suggestions"][0]
        assert suggestion["matched_property_id"] == str(existing_property.id)

    def test_import_without_address_lists_all_properties(
        self,
        e1_service: E1FormImportService,
        test_user: User,
        db_session: Session
    ):
        """Test E1 import without address lists all user properties"""
        # Create multiple properties
        from app.models.property import Property
        
        for i in range(3):
            prop = Property(
                user_id=test_user.id,
                property_type=PropertyType.RENTAL,
                street=f"Street {i+1}",
                city="Wien",
                postal_code="1010",
                address=f"Street {i+1}, 1010 Wien",
                purchase_date=date(2020, 1, 1),
                purchase_price=Decimal("300000.00"),
                building_value=Decimal("240000.00"),
                depreciation_rate=Decimal("0.02"),
                status=PropertyStatus.ACTIVE
            )
            db_session.add(prop)
        
        db_session.commit()
        
        # Import E1
        e1_data = E1FormData(
            tax_year=2025,
            kz_350=Decimal("12000.00"),
            confidence=0.95,
        )
        
        result = e1_service.import_e1_data(e1_data, test_user.id)
        
        # Should list all 3 properties for manual selection
        assert len(result["property_linking_suggestions"]) == 3
        for suggestion in result["property_linking_suggestions"]:
            assert suggestion["suggested_action"] == "manual_select"
            assert suggestion["confidence"] == 0.0

    def test_archived_property_not_suggested(
        self,
        bescheid_service: BescheidImportService,
        test_user: User,
        db_session: Session
    ):
        """Test that archived properties are not included in suggestions"""
        from app.models.property import Property
        
        # Create archived property
        archived = Property(
            user_id=test_user.id,
            property_type=PropertyType.RENTAL,
            street="Hauptstraße 123",
            city="Wien",
            postal_code="1010",
            address="Hauptstraße 123, 1010 Wien",
            purchase_date=date(2018, 1, 1),
            purchase_price=Decimal("300000.00"),
            building_value=Decimal("240000.00"),
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ARCHIVED,
            sale_date=date(2024, 12, 31)
        )
        db_session.add(archived)
        db_session.commit()
        
        # Import Bescheid with matching address
        bescheid_data = BescheidData(
            tax_year=2025,
            taxpayer_name="Test Landlord",
            einkommen=Decimal("50000.00"),
            vermietung_details=[
                {
                    "address": "Hauptstraße 123, 1010 Wien",
                    "amount": Decimal("12000.00")
                }
            ]
        )
        
        result = bescheid_service.import_bescheid_data(bescheid_data, test_user.id)
        
        # Should suggest creating new (archived not matched)
        suggestion = result["property_linking_suggestions"][0]
        assert suggestion["matched_property_id"] is None
        assert suggestion["suggested_action"] == "create_new"
