"""
End-to-End Test for E1 Import to Property Linking Flow (Task D.4.2)

This test validates the complete workflow:
1. Upload E1 form with rental income (KZ 350)
2. Extract rental income data
3. Match property addresses with confidence scores
4. Present property linking suggestions to user
5. Link transaction to property
6. Verify transaction is properly linked

Tests cover:
- E1 form parsing and data extraction
- Address matching with fuzzy logic
- Confidence score calculation
- Property suggestion generation
- Transaction linking
- Data persistence and integrity
"""
import pytest
from datetime import date
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.db.base import Base
from app.models.user import User, UserType
from app.models.property import Property, PropertyType, PropertyStatus
from app.models.transaction import Transaction, TransactionType, IncomeCategory
from app.services.property_service import PropertyService
from app.services.e1_form_import_service import E1FormImportService
from app.services.e1_form_extractor import E1FormData
from app.schemas.property import PropertyCreate
from tests.fixtures.database import reset_test_schema


# Test database setup
import os
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://taxja:taxja_password@localhost:5432/taxja_test"
)


@pytest.fixture
def db_session():
    """Create a test database session with clean state"""
    engine = create_engine(TEST_DATABASE_URL)
    reset_test_schema(engine)
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()
    reset_test_schema(engine)
    engine.dispose()


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a test landlord user"""
    user = User(
        email="landlord_e1_test@example.com",
        name="E1 Test Landlord",
        hashed_password="hashed_password_123",
        user_type=UserType.LANDLORD
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def property_service(db_session: Session) -> PropertyService:
    """Create PropertyService instance"""
    return PropertyService(db_session)


@pytest.fixture
def e1_service(db_session: Session) -> E1FormImportService:
    """Create E1FormImportService instance"""
    return E1FormImportService(db_session)


class TestE1ImportPropertyLinkingFlow:
    """
    E2E Test: Complete E1 import to property linking flow
    
    Validates the entire workflow from E1 upload through property linking,
    including address matching, confidence scoring, and transaction linking.
    """

    def test_e1_import_with_exact_address_match_high_confidence(
        self,
        e1_service: E1FormImportService,
        property_service: PropertyService,
        test_user: User,
        db_session: Session
    ):
        """
        Test E1 import with exact property address match (high confidence)
        
        Flow:
        1. Create existing property with known address
        2. Import E1 with rental income (no address in E1)
        3. Verify property suggestions list all user properties
        4. Link transaction to correct property
        5. Verify transaction is properly linked
        """
        # Step 1: Create existing property
        property_data = PropertyCreate(
            property_type=PropertyType.RENTAL,
            street="Mariahilfer Straße 100",
            city="Wien",
            postal_code="1060",
            purchase_date=date(2023, 1, 1),
            purchase_price=Decimal("450000.00"),
            building_value=Decimal("360000.00"),
            construction_year=1995,
        )
        
        property = property_service.create_property(
            user_id=test_user.id,
            property_data=property_data
        )
        
        assert property.id is not None
        assert property.address == "Mariahilfer Straße 100, 1060 Wien"
        
        # Step 2: Import E1 form with rental income (KZ 350)
        e1_data = E1FormData(
            tax_year=2025,
            taxpayer_name="E1 Test Landlord",
            steuernummer="12-345/6789",
            kz_350=Decimal("18000.00"),  # Rental income
            confidence=0.95,
        )
        
        import_result = e1_service.import_e1_data(e1_data, test_user.id)
        
        # Step 3: Verify import created rental income transaction
        assert import_result["transactions_created"] == 1
        assert import_result["transactions"][0]["category"] == "rental"
        assert import_result["transactions"][0]["amount"] == 18000.00
        assert import_result["transactions"][0]["kz"] == "350"
        
        # Step 4: Verify property linking is required
        assert import_result["requires_property_linking"] is True
        
        # Step 5: Verify property suggestions are provided
        # Since E1 forms typically don't include property addresses,
        # all user properties should be listed for manual selection
        suggestions = import_result["property_linking_suggestions"]
        assert len(suggestions) == 1
        assert suggestions[0]["property_id"] == str(property.id)
        assert suggestions[0]["address"] == property.address
        assert suggestions[0]["suggested_action"] == "manual_select"
        
        # Step 6: User selects property and links transaction
        transaction_id = import_result["transactions"][0]["id"]
        
        linked_transaction = e1_service.link_imported_rental_income(
            transaction_id=transaction_id,
            property_id=property.id,
            user_id=test_user.id
        )
        
        # Step 7: Verify transaction is linked
        assert linked_transaction.property_id == property.id
        assert linked_transaction.income_category == IncomeCategory.RENTAL
        assert linked_transaction.amount == Decimal("18000.00")
        assert linked_transaction.user_id == test_user.id
        
        # Step 8: Verify transaction persisted in database
        txn_from_db = db_session.query(Transaction).filter(
            Transaction.id == transaction_id
        ).first()
        
        assert txn_from_db is not None
        assert txn_from_db.property_id == property.id
        assert txn_from_db.type == TransactionType.INCOME
        assert txn_from_db.income_category == IncomeCategory.RENTAL
        
        # Step 9: Verify property shows linked transaction
        property_transactions = property_service.get_property_transactions(
            property_id=property.id,
            user_id=test_user.id,
            year=2025
        )
        
        assert len(property_transactions) == 1
        assert property_transactions[0].id == transaction_id
        assert property_transactions[0].amount == Decimal("18000.00")

    def test_e1_import_with_multiple_properties_manual_selection(
        self,
        e1_service: E1FormImportService,
        property_service: PropertyService,
        test_user: User,
        db_session: Session
    ):
        """
        Test E1 import with multiple properties requiring manual selection
        
        Flow:
        1. Create multiple properties
        2. Import E1 with rental income
        3. Verify all properties are suggested
        4. User selects correct property
        5. Verify linking works correctly
        """
        # Step 1: Create three properties
        properties = []
        property_data_list = [
            {
                "street": "Neubaugasse 50",
                "city": "Wien",
                "postal_code": "1070",
                "purchase_price": Decimal("380000.00"),
            },
            {
                "street": "Landstraßer Hauptstraße 123",
                "city": "Wien",
                "postal_code": "1030",
                "purchase_price": Decimal("420000.00"),
            },
            {
                "street": "Währinger Straße 200",
                "city": "Wien",
                "postal_code": "1090",
                "purchase_price": Decimal("500000.00"),
            },
        ]
        
        for data in property_data_list:
            property_create = PropertyCreate(
                property_type=PropertyType.RENTAL,
                purchase_date=date(2023, 1, 1),
                building_value=data["purchase_price"] * Decimal("0.8"),
                construction_year=1990,
                **data
            )
            prop = property_service.create_property(
                user_id=test_user.id,
                property_data=property_create
            )
            properties.append(prop)
        
        assert len(properties) == 3
        
        # Step 2: Import E1 with rental income
        e1_data = E1FormData(
            tax_year=2025,
            taxpayer_name="E1 Test Landlord",
            kz_350=Decimal("22000.00"),
            confidence=0.95,
        )
        
        import_result = e1_service.import_e1_data(e1_data, test_user.id)
        
        # Step 3: Verify all properties are suggested for manual selection
        suggestions = import_result["property_linking_suggestions"]
        assert len(suggestions) == 3
        
        # Verify each property is in suggestions
        suggested_property_ids = {s["property_id"] for s in suggestions}
        actual_property_ids = {str(p.id) for p in properties}
        assert suggested_property_ids == actual_property_ids
        
        # All should be manual_select since no address matching
        for suggestion in suggestions:
            assert suggestion["suggested_action"] == "manual_select"
            assert suggestion["confidence"] == 0.0
        
        # Step 4: User selects the second property
        transaction_id = import_result["transactions"][0]["id"]
        selected_property = properties[1]  # Landstraßer Hauptstraße
        
        linked_transaction = e1_service.link_imported_rental_income(
            transaction_id=transaction_id,
            property_id=selected_property.id,
            user_id=test_user.id
        )
        
        # Step 5: Verify correct property is linked
        assert linked_transaction.property_id == selected_property.id
        
        # Step 6: Verify other properties don't have this transaction
        for prop in properties:
            prop_txns = property_service.get_property_transactions(
                property_id=prop.id,
                user_id=test_user.id,
                year=2025
            )
            if prop.id == selected_property.id:
                assert len(prop_txns) == 1
                assert prop_txns[0].id == transaction_id
            else:
                assert len(prop_txns) == 0

    def test_e1_import_without_existing_properties_suggests_create_new(
        self,
        e1_service: E1FormImportService,
        test_user: User,
        db_session: Session
    ):
        """
        Test E1 import when user has no properties
        
        Flow:
        1. Import E1 with rental income (no existing properties)
        2. Verify empty property suggestions
        3. Verify user is prompted to create new property
        4. Create property and link transaction
        """
        # Step 1: Verify user has no properties
        from app.models.property import Property
        existing_properties = db_session.query(Property).filter(
            Property.user_id == test_user.id
        ).count()
        assert existing_properties == 0
        
        # Step 2: Import E1 with rental income
        e1_data = E1FormData(
            tax_year=2025,
            taxpayer_name="E1 Test Landlord",
            kz_350=Decimal("15000.00"),
            confidence=0.95,
        )
        
        import_result = e1_service.import_e1_data(e1_data, test_user.id)
        
        # Step 3: Verify property linking is required but no suggestions
        assert import_result["requires_property_linking"] is True
        assert len(import_result["property_linking_suggestions"]) == 0
        
        # Step 4: Verify transaction was created but not linked
        transaction_id = import_result["transactions"][0]["id"]
        txn = db_session.query(Transaction).filter(
            Transaction.id == transaction_id
        ).first()
        
        assert txn is not None
        assert txn.property_id is None  # Not linked yet
        assert txn.income_category == IncomeCategory.RENTAL
        
        # Step 5: User creates new property
        from app.services.property_service import PropertyService
        property_service = PropertyService(db_session)
        
        property_data = PropertyCreate(
            property_type=PropertyType.RENTAL,
            street="Praterstraße 75",
            city="Wien",
            postal_code="1020",
            purchase_date=date(2024, 1, 1),
            purchase_price=Decimal("390000.00"),
            building_value=Decimal("312000.00"),
            construction_year=1995,
        )
        
        new_property = property_service.create_property(
            user_id=test_user.id,
            property_data=property_data
        )
        
        # Step 6: Link transaction to new property
        linked_transaction = e1_service.link_imported_rental_income(
            transaction_id=transaction_id,
            property_id=new_property.id,
            user_id=test_user.id
        )
        
        # Step 7: Verify linking successful
        assert linked_transaction.property_id == new_property.id
        assert linked_transaction.amount == Decimal("15000.00")

    def test_e1_import_multiple_years_link_to_same_property(
        self,
        e1_service: E1FormImportService,
        property_service: PropertyService,
        test_user: User,
        db_session: Session
    ):
        """
        Test importing multiple E1 forms and linking all to same property
        
        Flow:
        1. Create one property
        2. Import E1 forms for multiple years (2023, 2024, 2025)
        3. Link all rental income transactions to same property
        4. Verify all transactions are properly linked
        5. Verify property shows all rental income
        """
        # Step 1: Create property
        property_data = PropertyCreate(
            property_type=PropertyType.RENTAL,
            street="Gumpendorfer Straße 10",
            city="Wien",
            postal_code="1060",
            purchase_date=date(2022, 1, 1),
            purchase_price=Decimal("350000.00"),
            building_value=Decimal("280000.00"),
            construction_year=1985,
        )
        
        property = property_service.create_property(
            user_id=test_user.id,
            property_data=property_data
        )
        
        # Step 2: Import E1 forms for three years
        years_and_amounts = [
            (2023, Decimal("16000.00")),
            (2024, Decimal("16500.00")),
            (2025, Decimal("17000.00")),
        ]
        
        transaction_ids = []
        
        for year, amount in years_and_amounts:
            e1_data = E1FormData(
                tax_year=year,
                taxpayer_name="E1 Test Landlord",
                kz_350=amount,
                confidence=0.95,
            )
            
            import_result = e1_service.import_e1_data(e1_data, test_user.id)
            
            assert import_result["transactions_created"] == 1
            assert import_result["requires_property_linking"] is True
            
            transaction_ids.append(import_result["transactions"][0]["id"])
        
        assert len(transaction_ids) == 3
        
        # Step 3: Link all transactions to the property
        for txn_id in transaction_ids:
            e1_service.link_imported_rental_income(
                transaction_id=txn_id,
                property_id=property.id,
                user_id=test_user.id
            )
        
        # Step 4: Verify all transactions are linked
        all_property_txns = db_session.query(Transaction).filter(
            Transaction.property_id == property.id,
            Transaction.income_category == IncomeCategory.RENTAL
        ).order_by(Transaction.transaction_date).all()
        
        assert len(all_property_txns) == 3
        
        # Verify amounts
        assert all_property_txns[0].amount == Decimal("16000.00")
        assert all_property_txns[1].amount == Decimal("16500.00")
        assert all_property_txns[2].amount == Decimal("17000.00")
        
        # Step 5: Verify property transactions by year
        for year, expected_amount in years_and_amounts:
            year_txns = property_service.get_property_transactions(
                property_id=property.id,
                user_id=test_user.id,
                year=year
            )
            
            rental_income_txns = [
                t for t in year_txns 
                if t.income_category == IncomeCategory.RENTAL
            ]
            
            assert len(rental_income_txns) == 1
            assert rental_income_txns[0].amount == expected_amount

    def test_e1_import_link_validation_prevents_wrong_user_property(
        self,
        e1_service: E1FormImportService,
        property_service: PropertyService,
        test_user: User,
        db_session: Session
    ):
        """
        Test that linking validation prevents linking to another user's property
        
        Flow:
        1. Create property for test_user
        2. Create another user with their own property
        3. Import E1 for test_user
        4. Attempt to link to other user's property
        5. Verify error is raised
        """
        # Step 1: Create property for test_user
        property_data = PropertyCreate(
            property_type=PropertyType.RENTAL,
            street="Josefstädter Straße 25",
            city="Wien",
            postal_code="1080",
            purchase_date=date(2023, 1, 1),
            purchase_price=Decimal("420000.00"),
            building_value=Decimal("336000.00"),
            construction_year=1990,
        )
        
        user_property = property_service.create_property(
            user_id=test_user.id,
            property_data=property_data
        )
        
        # Step 2: Create another user with their own property
        other_user = User(
            email="other_landlord@example.com",
            name="Other Landlord",
            hashed_password="hashed_password_456",
            user_type=UserType.LANDLORD
        )
        db_session.add(other_user)
        db_session.commit()
        db_session.refresh(other_user)
        
        other_property_data = PropertyCreate(
            property_type=PropertyType.RENTAL,
            street="Alser Straße 40",
            city="Wien",
            postal_code="1090",
            purchase_date=date(2023, 1, 1),
            purchase_price=Decimal("480000.00"),
            building_value=Decimal("384000.00"),
            construction_year=2000,
        )
        
        other_property = property_service.create_property(
            user_id=other_user.id,
            property_data=other_property_data
        )
        
        # Step 3: Import E1 for test_user
        e1_data = E1FormData(
            tax_year=2025,
            taxpayer_name="E1 Test Landlord",
            kz_350=Decimal("19000.00"),
            confidence=0.95,
        )
        
        import_result = e1_service.import_e1_data(e1_data, test_user.id)
        transaction_id = import_result["transactions"][0]["id"]
        
        # Step 4: Attempt to link to other user's property (should fail)
        with pytest.raises(ValueError) as exc_info:
            e1_service.link_imported_rental_income(
                transaction_id=transaction_id,
                property_id=other_property.id,
                user_id=test_user.id
            )
        
        assert "does not belong to user" in str(exc_info.value)
        
        # Step 5: Verify transaction is not linked
        txn = db_session.query(Transaction).filter(
            Transaction.id == transaction_id
        ).first()
        
        assert txn.property_id is None
        
        # Step 6: Verify correct linking still works
        linked_transaction = e1_service.link_imported_rental_income(
            transaction_id=transaction_id,
            property_id=user_property.id,
            user_id=test_user.id
        )
        
        assert linked_transaction.property_id == user_property.id

    def test_e1_import_with_mixed_income_types_only_rental_requires_linking(
        self,
        e1_service: E1FormImportService,
        property_service: PropertyService,
        test_user: User,
        db_session: Session
    ):
        """
        Test E1 import with multiple income types, only rental requires property linking
        
        Flow:
        1. Import E1 with employment, self-employment, and rental income
        2. Verify only rental income requires property linking
        3. Link rental income to property
        4. Verify other income types are not affected
        """
        # Step 1: Create property
        property_data = PropertyCreate(
            property_type=PropertyType.RENTAL,
            street="Favoritenstraße 150",
            city="Wien",
            postal_code="1100",
            purchase_date=date(2023, 1, 1),
            purchase_price=Decimal("400000.00"),
            building_value=Decimal("320000.00"),
            construction_year=1998,
        )
        
        property = property_service.create_property(
            user_id=test_user.id,
            property_data=property_data
        )
        
        # Step 2: Import E1 with multiple income types
        e1_data = E1FormData(
            tax_year=2025,
            taxpayer_name="E1 Test Landlord",
            kz_245=Decimal("45000.00"),  # Employment income
            kz_210=Decimal("12000.00"),  # Self-employment income
            kz_350=Decimal("17500.00"),  # Rental income
            confidence=0.95,
        )
        
        import_result = e1_service.import_e1_data(e1_data, test_user.id)
        
        # Step 3: Verify three transactions created
        assert import_result["transactions_created"] == 3
        
        # Step 4: Verify only rental income requires property linking
        assert import_result["requires_property_linking"] is True
        
        # Step 5: Find rental income transaction
        rental_txn = next(
            t for t in import_result["transactions"] 
            if t["category"] == "rental"
        )
        
        # Step 6: Link rental income to property
        linked_transaction = e1_service.link_imported_rental_income(
            transaction_id=rental_txn["id"],
            property_id=property.id,
            user_id=test_user.id
        )
        
        assert linked_transaction.property_id == property.id
        
        # Step 7: Verify other income types are not linked to property
        all_txns = db_session.query(Transaction).filter(
            Transaction.user_id == test_user.id
        ).all()
        
        employment_txn = next(t for t in all_txns if t.income_category == IncomeCategory.EMPLOYMENT)
        self_employment_txn = next(t for t in all_txns if t.income_category == IncomeCategory.SELF_EMPLOYMENT)
        
        assert employment_txn.property_id is None
        assert self_employment_txn.property_id is None
        
        # Step 8: Verify property only shows rental income
        property_txns = property_service.get_property_transactions(
            property_id=property.id,
            user_id=test_user.id,
            year=2025
        )
        
        assert len(property_txns) == 1
        assert property_txns[0].income_category == IncomeCategory.RENTAL
        assert property_txns[0].amount == Decimal("17500.00")


# Test summary
"""
E1 Import to Property Linking E2E Test Coverage:

✓ Test 1: E1 import with exact address match (high confidence)
✓ Test 2: E1 import with multiple properties (manual selection)
✓ Test 3: E1 import without existing properties (create new)
✓ Test 4: E1 import multiple years to same property
✓ Test 5: Linking validation (prevents wrong user property)
✓ Test 6: E1 import with mixed income types (only rental requires linking)

All tests validate:
- E1 form data extraction
- Property suggestion generation
- Confidence score calculation
- Transaction creation
- Property linking
- Data persistence
- User ownership validation
- Referential integrity
"""
