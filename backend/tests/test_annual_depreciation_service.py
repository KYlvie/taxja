"""
Unit tests for Annual Depreciation Service

Tests the generation of annual depreciation transactions for active properties.
"""

import pytest
from decimal import Decimal
from datetime import date
from uuid import uuid4

from app.services.annual_depreciation_service import AnnualDepreciationService
from app.models.property import Property, PropertyType, PropertyStatus
from app.models.transaction import Transaction, TransactionType, ExpenseCategory
from app.models.user import User


@pytest.fixture
def user(db):
    """Create a test user"""
    user = User(
        email="test@example.com",
        name="Test User",
        hashed_password="hashed_password",
        user_type="landlord"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def active_property(db, user):
    """Create an active rental property"""
    property = Property(
        user_id=user.id,
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


@pytest.fixture
def sold_property(db, user):
    """Create a sold property"""
    property = Property(
        user_id=user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        address="Nebenstraße 456, 1020 Wien",
        street="Nebenstraße 456",
        city="Wien",
        postal_code="1020",
        purchase_date=date(2018, 3, 1),
        purchase_price=Decimal("250000.00"),
        building_value=Decimal("200000.00"),
        land_value=Decimal("50000.00"),
        construction_year=1990,
        depreciation_rate=Decimal("0.02"),
        status=PropertyStatus.SOLD,
        sale_date=date(2023, 12, 31)
    )
    db.add(property)
    db.commit()
    db.refresh(property)
    return property


@pytest.fixture
def annual_depreciation_service(db):
    """Create annual depreciation service instance"""
    return AnnualDepreciationService(db)


class TestAnnualDepreciationService:
    """Test suite for AnnualDepreciationService"""
    
    def test_generate_annual_depreciation_for_active_property(
        self, 
        db, 
        annual_depreciation_service, 
        active_property
    ):
        """Test generating depreciation for an active property"""
        year = 2025
        
        result = annual_depreciation_service.generate_annual_depreciation(
            year=year,
            user_id=active_property.user_id
        )
        
        # Verify result summary
        assert result.year == year
        assert result.properties_processed == 1
        assert result.transactions_created == 1
        assert result.properties_skipped == 0
        assert result.total_amount == Decimal("5600.00")  # 280000 * 0.02
        
        # Verify transaction was created
        assert len(result.transactions) == 1
        transaction = result.transactions[0]
        
        assert transaction.user_id == active_property.user_id
        assert transaction.property_id == active_property.id
        assert transaction.type == TransactionType.EXPENSE
        assert transaction.amount == Decimal("5600.00")
        assert transaction.transaction_date == date(year, 12, 31)
        assert transaction.expense_category == ExpenseCategory.DEPRECIATION_AFA
        assert transaction.is_deductible is True
        assert transaction.is_system_generated is True
        assert transaction.import_source == "annual_depreciation"
        assert "AfA" in transaction.description
        assert str(year) in transaction.description
    
    def test_generate_annual_depreciation_skips_sold_properties(
        self, 
        db, 
        annual_depreciation_service, 
        sold_property
    ):
        """Test that sold properties are not processed"""
        year = 2025
        
        result = annual_depreciation_service.generate_annual_depreciation(
            year=year,
            user_id=sold_property.user_id
        )
        
        # Verify no transactions created for sold property
        assert result.properties_processed == 0
        assert result.transactions_created == 0
        assert result.total_amount == Decimal("0")
    
    def test_generate_annual_depreciation_prevents_duplicates(
        self, 
        db, 
        annual_depreciation_service, 
        active_property
    ):
        """Test that duplicate depreciation transactions are prevented"""
        year = 2025
        
        # Generate depreciation first time
        result1 = annual_depreciation_service.generate_annual_depreciation(
            year=year,
            user_id=active_property.user_id
        )
        assert result1.transactions_created == 1
        
        # Try to generate again for same year
        result2 = annual_depreciation_service.generate_annual_depreciation(
            year=year,
            user_id=active_property.user_id
        )
        
        # Verify no new transactions created
        assert result2.transactions_created == 0
        assert result2.properties_skipped == 1
        assert result2.skipped_details[0]["reason"] == "already_exists"
    
    def test_generate_annual_depreciation_for_all_users(
        self, 
        db, 
        annual_depreciation_service, 
        active_property
    ):
        """Test generating depreciation for all users (admin function)"""
        # Create another user with a property
        user2 = User(
            email="user2@example.com",
            name="User Two",
            hashed_password="hashed_password",
            user_type="landlord"
        )
        db.add(user2)
        db.commit()
        
        property2 = Property(
            user_id=user2.id,
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100.00"),
            address="Teststraße 789, 1030 Wien",
            street="Teststraße 789",
            city="Wien",
            postal_code="1030",
            purchase_date=date(2021, 1, 1),
            purchase_price=Decimal("400000.00"),
            building_value=Decimal("320000.00"),
            land_value=Decimal("80000.00"),
            construction_year=2000,
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db.add(property2)
        db.commit()
        
        year = 2025
        
        # Generate for all users (user_id=None)
        result = annual_depreciation_service.generate_annual_depreciation(
            year=year,
            user_id=None
        )
        
        # Verify transactions created for both properties
        assert result.properties_processed == 2
        assert result.transactions_created == 2
        assert result.total_amount == Decimal("12000.00")  # 5600 + 6400
    
    def test_generate_annual_depreciation_for_specific_user(
        self, 
        db, 
        annual_depreciation_service, 
        active_property
    ):
        """Test generating depreciation for a specific user only"""
        # Create another user with a property
        user2 = User(
            email="user2@example.com",
            name="User Two",
            hashed_password="hashed_password",
            user_type="landlord"
        )
        db.add(user2)
        db.commit()
        
        property2 = Property(
            user_id=user2.id,
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100.00"),
            address="Teststraße 789, 1030 Wien",
            street="Teststraße 789",
            city="Wien",
            postal_code="1030",
            purchase_date=date(2021, 1, 1),
            purchase_price=Decimal("400000.00"),
            building_value=Decimal("320000.00"),
            land_value=Decimal("80000.00"),
            construction_year=2000,
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db.add(property2)
        db.commit()
        
        year = 2025
        
        # Generate only for user1
        result = annual_depreciation_service.generate_annual_depreciation(
            year=year,
            user_id=active_property.user_id
        )
        
        # Verify only user1's property was processed
        assert result.properties_processed == 1
        assert result.transactions_created == 1
        assert result.transactions[0].user_id == active_property.user_id
    
    def test_generate_annual_depreciation_skips_fully_depreciated(
        self, 
        db, 
        annual_depreciation_service, 
        active_property
    ):
        """Test that fully depreciated properties are skipped"""
        year = 2025
        
        # Create depreciation transactions that fully depreciate the property
        # Building value: 280000, so we need 280000 in depreciation
        for y in range(2020, 2070):  # 50 years * 5600 = 280000
            transaction = Transaction(
                user_id=active_property.user_id,
                property_id=active_property.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("5600.00"),
                transaction_date=date(y, 12, 31),
                description=f"AfA {active_property.address} ({y})",
                expense_category=ExpenseCategory.DEPRECIATION_AFA,
                is_deductible=True,
                is_system_generated=True,
                import_source="test",
                classification_confidence=Decimal("1.0")
            )
            db.add(transaction)
        db.commit()
        
        # Try to generate depreciation for 2070
        result = annual_depreciation_service.generate_annual_depreciation(
            year=2070,
            user_id=active_property.user_id
        )
        
        # Verify property was skipped
        assert result.transactions_created == 0
        assert result.properties_skipped == 1
        assert result.skipped_details[0]["reason"] == "fully_depreciated"
    
    def test_generate_annual_depreciation_mixed_use_property(
        self, 
        db, 
        annual_depreciation_service, 
        user
    ):
        """Test depreciation for mixed-use property (50% rental)"""
        property = Property(
            user_id=user.id,
            property_type=PropertyType.MIXED_USE,
            rental_percentage=Decimal("50.00"),
            address="Mischstraße 100, 1040 Wien",
            street="Mischstraße 100",
            city="Wien",
            postal_code="1040",
            purchase_date=date(2022, 1, 1),
            purchase_price=Decimal("500000.00"),
            building_value=Decimal("400000.00"),
            land_value=Decimal("100000.00"),
            construction_year=2010,
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db.add(property)
        db.commit()
        
        year = 2025
        
        result = annual_depreciation_service.generate_annual_depreciation(
            year=year,
            user_id=user.id
        )
        
        # Verify depreciation is only for rental percentage
        # 400000 * 0.50 * 0.02 = 4000
        assert result.transactions_created == 1
        assert result.total_amount == Decimal("4000.00")
    
    def test_generate_annual_depreciation_owner_occupied_skipped(
        self, 
        db, 
        annual_depreciation_service, 
        user
    ):
        """Test that owner-occupied properties are skipped"""
        property = Property(
            user_id=user.id,
            property_type=PropertyType.OWNER_OCCUPIED,
            rental_percentage=Decimal("0.00"),
            address="Eigenheim 1, 1050 Wien",
            street="Eigenheim 1",
            city="Wien",
            postal_code="1050",
            purchase_date=date(2023, 1, 1),
            purchase_price=Decimal("600000.00"),
            building_value=Decimal("480000.00"),
            land_value=Decimal("120000.00"),
            construction_year=2020,
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db.add(property)
        db.commit()
        
        year = 2025
        
        result = annual_depreciation_service.generate_annual_depreciation(
            year=year,
            user_id=user.id
        )
        
        # Verify no depreciation for owner-occupied
        assert result.transactions_created == 0
        assert result.properties_skipped == 1
        assert result.skipped_details[0]["reason"] == "fully_depreciated"
    
    def test_generate_annual_depreciation_result_to_dict(
        self, 
        db, 
        annual_depreciation_service, 
        active_property
    ):
        """Test that result can be converted to dictionary"""
        year = 2025
        
        result = annual_depreciation_service.generate_annual_depreciation(
            year=year,
            user_id=active_property.user_id
        )
        
        result_dict = result.to_dict()
        
        # Verify dictionary structure
        assert result_dict["year"] == year
        assert result_dict["properties_processed"] == 1
        assert result_dict["transactions_created"] == 1
        assert result_dict["properties_skipped"] == 0
        assert result_dict["total_amount"] == 5600.00
        assert len(result_dict["transaction_ids"]) == 1
        assert isinstance(result_dict["skipped_details"], list)
    
    def test_generate_annual_depreciation_no_properties(
        self, 
        db, 
        annual_depreciation_service, 
        user
    ):
        """Test generating depreciation when user has no properties"""
        year = 2025
        
        result = annual_depreciation_service.generate_annual_depreciation(
            year=year,
            user_id=user.id
        )
        
        # Verify empty result
        assert result.properties_processed == 0
        assert result.transactions_created == 0
        assert result.properties_skipped == 0
        assert result.total_amount == Decimal("0")
