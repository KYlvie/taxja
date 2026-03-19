"""
End-to-End Tests for Annual Depreciation Generation

Tests the complete workflow of triggering year-end depreciation generation,
verifying transactions are created correctly, no duplicates occur, and amounts
are accurate.

Task: D.4.3 Test annual depreciation generation
"""

import pytest
from decimal import Decimal
from datetime import date
from uuid import uuid4

from app.services.annual_depreciation_service import AnnualDepreciationService
from app.models.property import Property, PropertyType, PropertyStatus, BuildingUse
from app.models.recurring_transaction import (
    RecurringTransaction,
    RecurringTransactionType,
    RecurrenceFrequency,
)
from app.models.transaction import Transaction, TransactionType, ExpenseCategory
from app.models.user import User, UserType


@pytest.fixture
def landlord_user(db):
    """Create a landlord user"""
    user = User(
        email="landlord@example.com",
        name="Landlord User",
        password_hash="hashed_password",
        user_type=UserType.EMPLOYEE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _add_rental_contract(
    db,
    user_id: int,
    property_id,
    start_date: date,
    unit_percentage: Decimal = Decimal("100.00"),
    amount: Decimal = Decimal("1500.00"),
) -> RecurringTransaction:
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
def multiple_properties(db, landlord_user):
    """Create multiple properties with different scenarios"""
    properties = []
    
    # Property 1: Standard rental property (purchased 2020)
    prop1 = Property(
        user_id=landlord_user.id,
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
    db.add(prop1)
    properties.append(prop1)
    
    # Property 2: Mixed-use property (50% rental)
    prop2 = Property(
        user_id=landlord_user.id,
        property_type=PropertyType.MIXED_USE,
        rental_percentage=Decimal("50.00"),
        address="Mischstraße 456, 1020 Wien",
        street="Mischstraße 456",
        city="Wien",
        postal_code="1020",
        purchase_date=date(2021, 1, 1),
        purchase_price=Decimal("500000.00"),
        building_value=Decimal("400000.00"),
        land_value=Decimal("100000.00"),
        construction_year=2010,
        depreciation_rate=Decimal("0.02"),
        status=PropertyStatus.ACTIVE
    )
    db.add(prop2)
    properties.append(prop2)
    
    # Property 3: Pre-1915 building (1.5% rate)
    prop3 = Property(
        user_id=landlord_user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        address="Altbau 789, 1030 Wien",
        street="Altbau 789",
        city="Wien",
        postal_code="1030",
        purchase_date=date(2019, 3, 1),
        purchase_price=Decimal("450000.00"),
        building_value=Decimal("360000.00"),
        land_value=Decimal("90000.00"),
        construction_year=1900,
        depreciation_rate=Decimal("0.015"),
        status=PropertyStatus.ACTIVE
    )
    db.add(prop3)
    properties.append(prop3)
    
    # Property 4: Recently purchased (partial year 2025)
    prop4 = Property(
        user_id=landlord_user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        address="Neubau 101, 1040 Wien",
        street="Neubau 101",
        city="Wien",
        postal_code="1040",
        purchase_date=date(2025, 7, 1),  # Mid-year purchase
        purchase_price=Decimal("600000.00"),
        building_value=Decimal("480000.00"),
        land_value=Decimal("120000.00"),
        construction_year=2020,
        depreciation_rate=Decimal("0.02"),
        status=PropertyStatus.ACTIVE
    )
    db.add(prop4)
    properties.append(prop4)
    
    # Property 5: Sold property (should be skipped)
    prop5 = Property(
        user_id=landlord_user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        address="Verkauft 202, 1050 Wien",
        street="Verkauft 202",
        city="Wien",
        postal_code="1050",
        purchase_date=date(2018, 1, 1),
        purchase_price=Decimal("300000.00"),
        building_value=Decimal("240000.00"),
        land_value=Decimal("60000.00"),
        construction_year=1995,
        depreciation_rate=Decimal("0.02"),
        status=PropertyStatus.SOLD,
        sale_date=date(2024, 12, 31)
    )
    db.add(prop5)
    properties.append(prop5)
    
    db.commit()
    for prop in properties:
        db.refresh(prop)

    _add_rental_contract(db, landlord_user.id, prop1.id, date(2020, 6, 15))
    _add_rental_contract(
        db,
        landlord_user.id,
        prop2.id,
        date(2021, 1, 1),
        unit_percentage=Decimal("50.00"),
    )
    _add_rental_contract(db, landlord_user.id, prop3.id, date(2019, 3, 1))
    _add_rental_contract(db, landlord_user.id, prop4.id, date(2025, 7, 1))
    
    return properties


class TestAnnualDepreciationE2E:
    """End-to-end tests for annual depreciation generation"""
    
    def test_year_end_task_creates_transactions_for_all_active_properties(
        self, 
        db, 
        landlord_user, 
        multiple_properties
    ):
        """
        E2E Test: Trigger year-end task and verify transactions created
        
        Scenario: December 31, 2025 - system generates annual depreciation
        for all active properties
        """
        service = AnnualDepreciationService(db)
        year = 2025
        
        # Trigger year-end depreciation generation
        result = service.generate_annual_depreciation(
            year=year,
            user_id=landlord_user.id
        )
        
        # Verify summary
        assert result.year == year
        assert result.properties_processed == 4  # Only active properties are queried
        assert result.transactions_created == 4  # 4 active properties
        assert result.properties_skipped == 0
        
        # Verify transactions in database
        transactions = db.query(Transaction).filter(
            Transaction.user_id == landlord_user.id,
            Transaction.expense_category == ExpenseCategory.DEPRECIATION_AFA,
            Transaction.transaction_date == date(year, 12, 31)
        ).all()
        
        assert len(transactions) == 4
        
        # Verify all transactions are system-generated
        for txn in transactions:
            assert txn.is_system_generated is True
            assert txn.import_source == "annual_depreciation"
            assert txn.type == TransactionType.EXPENSE
            assert txn.is_deductible is True
            assert txn.transaction_date == date(year, 12, 31)
            assert "AfA" in txn.description
            assert str(year) in txn.description
    
    def test_verify_no_duplicates_on_repeated_execution(
        self, 
        db, 
        landlord_user, 
        multiple_properties
    ):
        """
        E2E Test: Verify no duplicates when task runs multiple times
        
        Scenario: Task accidentally runs twice - should not create duplicates
        """
        service = AnnualDepreciationService(db)
        year = 2025
        
        # First execution
        result1 = service.generate_annual_depreciation(
            year=year,
            user_id=landlord_user.id
        )
        
        assert result1.transactions_created == 4
        first_transaction_ids = [t.id for t in result1.transactions]
        
        # Second execution (should skip all)
        result2 = service.generate_annual_depreciation(
            year=year,
            user_id=landlord_user.id
        )
        
        assert result2.transactions_created == 0
        assert result2.properties_skipped == 4  # All active properties skipped
        
        # Verify all skipped due to "already_exists"
        for skip_detail in result2.skipped_details:
            assert skip_detail["reason"] == "already_exists"
        
        # Verify total transaction count in database hasn't changed
        transactions = db.query(Transaction).filter(
            Transaction.user_id == landlord_user.id,
            Transaction.expense_category == ExpenseCategory.DEPRECIATION_AFA,
            Transaction.transaction_date == date(year, 12, 31)
        ).all()
        
        assert len(transactions) == 4
        
        # Verify transaction IDs are the same (no new ones created)
        db_transaction_ids = [t.id for t in transactions]
        assert set(db_transaction_ids) == set(first_transaction_ids)
    
    def test_verify_amounts_correct_for_different_scenarios(
        self, 
        db, 
        landlord_user, 
        multiple_properties
    ):
        """
        E2E Test: Verify depreciation amounts are calculated correctly
        
        Tests:
        - Standard rental property: full year depreciation
        - Mixed-use property: only rental percentage
        - Pre-1915 building: 1.5% rate
        - Partial year: pro-rated depreciation
        """
        service = AnnualDepreciationService(db)
        year = 2025
        
        # Generate depreciation
        result = service.generate_annual_depreciation(
            year=year,
            user_id=landlord_user.id
        )
        
        # Get all transactions
        transactions = db.query(Transaction).filter(
            Transaction.user_id == landlord_user.id,
            Transaction.expense_category == ExpenseCategory.DEPRECIATION_AFA,
            Transaction.transaction_date == date(year, 12, 31)
        ).all()
        
        # Create mapping of property_id to transaction
        txn_by_property = {t.property_id: t for t in transactions}
        
        # Property 1: Standard residential rental (280000 * 0.015 = 4200)
        prop1 = multiple_properties[0]
        txn1 = txn_by_property[prop1.id]
        assert txn1.amount == Decimal("4200.00")
        assert prop1.address in txn1.description
        
        # Property 2: Mixed-use 50% via rental contracts (400000 * 0.50 * 0.015 = 3000)
        prop2 = multiple_properties[1]
        txn2 = txn_by_property[prop2.id]
        assert txn2.amount == Decimal("3000.00")
        assert prop2.address in txn2.description
        
        # Property 3: Residential old building still uses the current 1.5% residential rate
        prop3 = multiple_properties[2]
        txn3 = txn_by_property[prop3.id]
        assert txn3.amount == Decimal("5400.00")
        assert prop3.address in txn3.description
        
        # Property 4: Partial year - purchased July 1 (6 months)
        # 480000 * 0.015 * 6/12 = 3600
        prop4 = multiple_properties[3]
        txn4 = txn_by_property[prop4.id]
        assert txn4.amount == Decimal("3600.00")
        assert prop4.address in txn4.description
        
        # Property 5: Sold - should not have transaction
        prop5 = multiple_properties[4]
        assert prop5.id not in txn_by_property
        
        # Verify total amount
        total_expected = Decimal("4200.00") + Decimal("3000.00") + \
                        Decimal("5400.00") + Decimal("3600.00")
        assert result.total_amount == total_expected
    
    def test_multi_year_depreciation_accumulation(
        self, 
        db, 
        landlord_user, 
        multiple_properties
    ):
        """
        E2E Test: Generate depreciation for multiple years and verify accumulation
        
        Scenario: Generate depreciation for 2023, 2024, 2025 and verify
        accumulated amounts don't exceed building value
        """
        service = AnnualDepreciationService(db)
        
        # Generate for 3 consecutive years
        years = [2023, 2024, 2025]
        
        for year in years:
            result = service.generate_annual_depreciation(
                year=year,
                user_id=landlord_user.id
            )
            
            # Each year should create transactions
            assert result.transactions_created > 0
        
        # Verify accumulated depreciation for Property 1
        prop1 = multiple_properties[0]
        
        accumulated_txns = db.query(Transaction).filter(
            Transaction.property_id == prop1.id,
            Transaction.expense_category == ExpenseCategory.DEPRECIATION_AFA
        ).all()
        
        # Should have 3 transactions (one per year)
        assert len(accumulated_txns) == 3
        
        # Verify each transaction is for correct year
        years_found = set()
        for txn in accumulated_txns:
            years_found.add(txn.transaction_date.year)
            assert txn.amount == Decimal("4200.00")  # Same amount each year
        
        assert years_found == {2023, 2024, 2025}
        
        # Verify total accumulated doesn't exceed building value
        total_accumulated = sum(t.amount for t in accumulated_txns)
        assert total_accumulated <= prop1.building_value
        assert total_accumulated == Decimal("12600.00")  # 4200 * 3
    
    def test_admin_generates_for_all_users(
        self, 
        db, 
        landlord_user, 
        multiple_properties
    ):
        """
        E2E Test: Admin triggers depreciation for all users
        
        Scenario: System admin runs year-end task for entire platform
        """
        # Create another user with properties
        user2 = User(
            email="landlord2@example.com",
            name="Second Landlord",
            password_hash="hashed_password",
            user_type=UserType.EMPLOYEE,
        )
        db.add(user2)
        db.commit()
        
        prop_user2 = Property(
            user_id=user2.id,
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100.00"),
            address="User2 Street 1, 1060 Wien",
            street="User2 Street 1",
            city="Wien",
            postal_code="1060",
            purchase_date=date(2022, 1, 1),
            purchase_price=Decimal("400000.00"),
            building_value=Decimal("320000.00"),
            land_value=Decimal("80000.00"),
            construction_year=2015,
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db.add(prop_user2)
        db.commit()
        db.refresh(prop_user2)
        _add_rental_contract(db, user2.id, prop_user2.id, date(2022, 1, 1))
        
        service = AnnualDepreciationService(db)
        year = 2025
        
        # Admin generates for all users (user_id=None)
        result = service.generate_annual_depreciation(
            year=year,
            user_id=None  # All users
        )
        
        # Verify transactions created for both users
        assert result.transactions_created == 5  # 4 from user1 + 1 from user2
        
        # Verify user1's transactions
        user1_txns = db.query(Transaction).filter(
            Transaction.user_id == landlord_user.id,
            Transaction.expense_category == ExpenseCategory.DEPRECIATION_AFA,
            Transaction.transaction_date == date(year, 12, 31)
        ).all()
        assert len(user1_txns) == 4
        
        # Verify user2's transactions
        user2_txns = db.query(Transaction).filter(
            Transaction.user_id == user2.id,
            Transaction.expense_category == ExpenseCategory.DEPRECIATION_AFA,
            Transaction.transaction_date == date(year, 12, 31)
        ).all()
        assert len(user2_txns) == 1
        assert user2_txns[0].amount == Decimal("4800.00")  # 320000 * 1.5%
    
    def test_depreciation_stops_at_building_value_limit(
        self, 
        db, 
        landlord_user
    ):
        """
        E2E Test: Verify depreciation stops when building value is reached
        
        Scenario: Property has been depreciated for many years and is
        approaching full depreciation
        """
        # Create property with small building value for faster testing
        prop = Property(
            user_id=landlord_user.id,
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100.00"),
            address="Small Building 1, 1070 Wien",
            street="Small Building 1",
            city="Wien",
            postal_code="1070",
            purchase_date=date(2000, 1, 1),
            purchase_price=Decimal("100000.00"),
            building_value=Decimal("10000.00"),  # Small value
            land_value=Decimal("90000.00"),
            construction_year=2000,
            depreciation_rate=Decimal("0.025"),
            building_use=BuildingUse.COMMERCIAL,
            status=PropertyStatus.ACTIVE
        )
        db.add(prop)
        db.commit()
        db.refresh(prop)
        _add_rental_contract(db, landlord_user.id, prop.id, date(2000, 1, 1))
        
        service = AnnualDepreciationService(db)
        
        # Generate depreciation for many years to reach limit
        # Commercial building annual depreciation: 10000 * 0.025 = 250
        # Need 40 years to fully depreciate
        
        # Generate for 39 years (should work)
        for year in range(2001, 2040):
            result = service.generate_annual_depreciation(
                year=year,
                user_id=landlord_user.id
            )
            assert result.transactions_created == 1
        
        # Verify accumulated depreciation
        accumulated_txns = db.query(Transaction).filter(
            Transaction.property_id == prop.id,
            Transaction.expense_category == ExpenseCategory.DEPRECIATION_AFA
        ).all()
        
        total_accumulated = sum(t.amount for t in accumulated_txns)
        assert total_accumulated == Decimal("9750.00")  # 39 * 250
        
        # The current service computes accumulated depreciation mathematically
        # from purchase year, so by 2040 this asset is already considered fully
        # depreciated even if the first generated transaction in this test is 2001.
        result_40 = service.generate_annual_depreciation(
            year=2040,
            user_id=landlord_user.id
        )
        
        assert result_40.transactions_created == 0
        assert result_40.properties_skipped == 1
        assert result_40.skipped_details[0]["reason"] == "fully_depreciated"
    
    def test_transaction_attributes_are_correct(
        self, 
        db, 
        landlord_user, 
        multiple_properties
    ):
        """
        E2E Test: Verify all transaction attributes are set correctly
        
        Validates:
        - Transaction type
        - Category
        - Date
        - Description format
        - System-generated flag
        - Deductibility
        - Import source
        - Confidence score
        """
        service = AnnualDepreciationService(db)
        year = 2025
        
        result = service.generate_annual_depreciation(
            year=year,
            user_id=landlord_user.id
        )
        
        for transaction in result.transactions:
            # Verify type and category
            assert transaction.type == TransactionType.EXPENSE
            assert transaction.expense_category == ExpenseCategory.DEPRECIATION_AFA
            
            # Verify date
            assert transaction.transaction_date == date(year, 12, 31)
            
            # Verify description format
            assert "AfA" in transaction.description
            assert str(year) in transaction.description
            
            # Find corresponding property
            prop = db.query(Property).filter(
                Property.id == transaction.property_id
            ).first()
            assert prop is not None
            assert prop.address in transaction.description
            
            # Verify flags
            assert transaction.is_system_generated is True
            assert transaction.is_deductible is True
            
            # Verify metadata
            assert transaction.import_source == "annual_depreciation"
            assert transaction.classification_confidence == Decimal("1.0")
            
            # Verify ownership
            assert transaction.user_id == landlord_user.id
            assert transaction.user_id == prop.user_id
    
    def test_result_to_dict_serialization(
        self, 
        db, 
        landlord_user, 
        multiple_properties
    ):
        """
        E2E Test: Verify result can be serialized to dict for API response
        """
        service = AnnualDepreciationService(db)
        year = 2025
        
        result = service.generate_annual_depreciation(
            year=year,
            user_id=landlord_user.id
        )
        
        # Convert to dict
        result_dict = result.to_dict()
        
        # Verify structure
        assert isinstance(result_dict, dict)
        assert "year" in result_dict
        assert "properties_processed" in result_dict
        assert "transactions_created" in result_dict
        assert "properties_skipped" in result_dict
        assert "total_amount" in result_dict
        assert "transaction_ids" in result_dict
        assert "skipped_details" in result_dict
        
        # Verify values
        assert result_dict["year"] == year
        assert result_dict["properties_processed"] == 4
        assert result_dict["transactions_created"] == 4
        assert result_dict["properties_skipped"] == 0
        assert isinstance(result_dict["total_amount"], float)
        assert len(result_dict["transaction_ids"]) == 4
        assert isinstance(result_dict["skipped_details"], list)
        
        # Verify transaction IDs are valid
        for txn_id in result_dict["transaction_ids"]:
            assert txn_id is not None
            txn = db.query(Transaction).filter(Transaction.id == txn_id).first()
            assert txn is not None
