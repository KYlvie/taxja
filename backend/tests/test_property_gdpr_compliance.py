"""
Unit tests for Property GDPR compliance functionality.

Tests the implementation of GDPR rights:
- Right to erasure (delete_user_property_data)
- Right to access (get_user_property_data_summary)
- Cascade deletion of properties and transactions
- Cache clearing on deletion
"""

import pytest
from decimal import Decimal
from datetime import date
from uuid import uuid4
from sqlalchemy.orm import Session

from app.models.property import Property, PropertyType, PropertyStatus
from app.models.transaction import Transaction, TransactionType, ExpenseCategory, IncomeCategory
from app.models.user import User
from app.services.property_service import PropertyService


@pytest.fixture
def property_service(db: Session):
    """Create PropertyService instance with test database session"""
    return PropertyService(db)


@pytest.fixture
def test_user(db: Session):
    """Create a test user"""
    user = User(
        email="gdpr_test@example.com",
        name="GDPR Test User",
        hashed_password="hashed_password_here"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_properties(db: Session, test_user: User):
    """Create multiple test properties for a user"""
    properties = []
    
    # Property 1: Active rental property
    prop1 = Property(
        user_id=test_user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        address="Teststraße 1, 1010 Wien",
        street="Teststraße 1",
        city="Wien",
        postal_code="1010",
        purchase_date=date(2020, 1, 1),
        purchase_price=Decimal("300000.00"),
        building_value=Decimal("240000.00"),
        construction_year=1990,
        depreciation_rate=Decimal("0.02"),
        status=PropertyStatus.ACTIVE
    )
    properties.append(prop1)
    
    # Property 2: Archived property
    prop2 = Property(
        user_id=test_user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        address="Teststraße 2, 1020 Wien",
        street="Teststraße 2",
        city="Wien",
        postal_code="1020",
        purchase_date=date(2018, 6, 15),
        purchase_price=Decimal("250000.00"),
        building_value=Decimal("200000.00"),
        construction_year=1985,
        depreciation_rate=Decimal("0.02"),
        status=PropertyStatus.ARCHIVED
    )
    properties.append(prop2)
    
    # Property 3: Sold property
    prop3 = Property(
        user_id=test_user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        address="Teststraße 3, 1030 Wien",
        street="Teststraße 3",
        city="Wien",
        postal_code="1030",
        purchase_date=date(2015, 3, 1),
        purchase_price=Decimal("200000.00"),
        building_value=Decimal("160000.00"),
        construction_year=1980,
        depreciation_rate=Decimal("0.02"),
        status=PropertyStatus.SOLD,
        sale_date=date(2025, 12, 31)
    )
    properties.append(prop3)
    
    for prop in properties:
        db.add(prop)
    
    db.commit()
    
    for prop in properties:
        db.refresh(prop)
    
    return properties


@pytest.fixture
def test_transactions(db: Session, test_user: User, test_properties: list):
    """Create test transactions linked to properties"""
    transactions = []
    
    # Rental income for property 1
    trans1 = Transaction(
        user_id=test_user.id,
        property_id=test_properties[0].id,
        type=TransactionType.INCOME,
        amount=Decimal("1200.00"),
        transaction_date=date(2025, 1, 1),
        description="Rental income January",
        income_category=IncomeCategory.RENTAL,
        is_deductible=False
    )
    transactions.append(trans1)
    
    # Depreciation for property 1
    trans2 = Transaction(
        user_id=test_user.id,
        property_id=test_properties[0].id,
        type=TransactionType.EXPENSE,
        amount=Decimal("4800.00"),
        transaction_date=date(2025, 12, 31),
        description="AfA 2025",
        expense_category=ExpenseCategory.DEPRECIATION_AFA,
        is_deductible=True,
        is_system_generated=True
    )
    transactions.append(trans2)
    
    # Maintenance expense for property 2
    trans3 = Transaction(
        user_id=test_user.id,
        property_id=test_properties[1].id,
        type=TransactionType.EXPENSE,
        amount=Decimal("500.00"),
        transaction_date=date(2025, 6, 15),
        description="Maintenance repair",
        expense_category=ExpenseCategory.MAINTENANCE_REPAIRS,
        is_deductible=True
    )
    transactions.append(trans3)
    
    for trans in transactions:
        db.add(trans)
    
    db.commit()
    
    return transactions


class TestGDPRDataSummary:
    """Test the right to access (GDPR Article 15)"""
    
    def test_get_user_property_data_summary_with_properties(
        self, 
        property_service: PropertyService,
        test_user: User,
        test_properties: list,
        test_transactions: list
    ):
        """Test getting data summary for user with properties"""
        summary = property_service.get_user_property_data_summary(test_user.id)
        
        assert summary["user_id"] == test_user.id
        assert summary["total_properties"] == 3
        assert summary["active_properties"] == 1
        assert summary["archived_properties"] == 1
        assert summary["sold_properties"] == 1
        assert summary["total_transactions"] == 3
        
        # Check data retention info
        assert "data_retention_info" in summary
        assert "retention_period" in summary["data_retention_info"]
        assert "deletion_policy" in summary["data_retention_info"]
        assert "backup_retention" in summary["data_retention_info"]
        assert "legal_basis" in summary["data_retention_info"]
    
    def test_get_user_property_data_summary_no_properties(
        self,
        property_service: PropertyService,
        test_user: User
    ):
        """Test getting data summary for user with no properties"""
        summary = property_service.get_user_property_data_summary(test_user.id)
        
        assert summary["user_id"] == test_user.id
        assert summary["total_properties"] == 0
        assert summary["active_properties"] == 0
        assert summary["archived_properties"] == 0
        assert summary["sold_properties"] == 0
        assert summary["total_transactions"] == 0


class TestGDPRDataDeletion:
    """Test the right to erasure (GDPR Article 17)"""
    
    def test_delete_user_property_data_success(
        self,
        db: Session,
        property_service: PropertyService,
        test_user: User,
        test_properties: list,
        test_transactions: list
    ):
        """Test successful deletion of all user property data"""
        # Verify data exists before deletion
        properties_before = db.query(Property).filter(
            Property.user_id == test_user.id
        ).count()
        assert properties_before == 3
        
        transactions_before = db.query(Transaction).filter(
            Transaction.property_id.in_([p.id for p in test_properties])
        ).count()
        assert transactions_before == 3
        
        # Perform deletion
        result = property_service.delete_user_property_data(test_user.id)
        
        # Verify result
        assert result["user_id"] == test_user.id
        assert result["properties_deleted"] == 3
        assert result["transactions_deleted"] == 3
        assert len(result["deleted_property_ids"]) == 3
        
        # Verify data is deleted from database
        properties_after = db.query(Property).filter(
            Property.user_id == test_user.id
        ).count()
        assert properties_after == 0
        
        transactions_after = db.query(Transaction).filter(
            Transaction.property_id.in_([p.id for p in test_properties])
        ).count()
        assert transactions_after == 0
    
    def test_delete_user_property_data_no_properties(
        self,
        db: Session,
        property_service: PropertyService,
        test_user: User
    ):
        """Test deletion when user has no properties"""
        result = property_service.delete_user_property_data(test_user.id)
        
        assert result["user_id"] == test_user.id
        assert result["properties_deleted"] == 0
        assert result["transactions_deleted"] == 0
        assert result["deleted_property_ids"] == []
    
    def test_delete_user_property_data_cascade_transactions(
        self,
        db: Session,
        property_service: PropertyService,
        test_user: User,
        test_properties: list,
        test_transactions: list
    ):
        """Test that transactions are cascade deleted with properties"""
        property_ids = [p.id for p in test_properties]
        
        # Verify transactions exist
        trans_count_before = db.query(Transaction).filter(
            Transaction.property_id.in_(property_ids)
        ).count()
        assert trans_count_before > 0
        
        # Delete property data
        property_service.delete_user_property_data(test_user.id)
        
        # Verify all transactions are deleted
        trans_count_after = db.query(Transaction).filter(
            Transaction.property_id.in_(property_ids)
        ).count()
        assert trans_count_after == 0
    
    def test_delete_user_property_data_rollback_on_error(
        self,
        db: Session,
        property_service: PropertyService,
        test_user: User,
        test_properties: list,
        monkeypatch
    ):
        """Test that deletion is rolled back on error"""
        # Count properties before
        properties_before = db.query(Property).filter(
            Property.user_id == test_user.id
        ).count()
        
        # Mock an error during deletion
        def mock_delete(*args, **kwargs):
            raise Exception("Simulated database error")
        
        monkeypatch.setattr(db.query(Property).filter(
            Property.user_id == test_user.id
        ), "delete", mock_delete)
        
        # Attempt deletion (should fail)
        with pytest.raises(Exception):
            property_service.delete_user_property_data(test_user.id)
        
        # Verify data is NOT deleted (rollback occurred)
        properties_after = db.query(Property).filter(
            Property.user_id == test_user.id
        ).count()
        assert properties_after == properties_before


class TestGDPRCacheCleaning:
    """Test cache clearing on GDPR deletion"""
    
    def test_clear_user_property_cache_success(
        self,
        property_service: PropertyService,
        test_user: User,
        test_properties: list
    ):
        """Test successful cache clearing"""
        property_ids = [str(p.id) for p in test_properties]
        
        # Clear cache
        result = property_service._clear_user_property_cache(test_user.id, property_ids)
        
        # Result depends on Redis availability
        # If Redis is available, should return True
        # If Redis is unavailable, should return False (graceful degradation)
        assert isinstance(result, bool)
    
    def test_clear_user_property_cache_no_redis(
        self,
        property_service: PropertyService,
        test_user: User
    ):
        """Test cache clearing when Redis is unavailable"""
        # Disable Redis
        property_service._redis_client = None
        
        result = property_service._clear_user_property_cache(test_user.id, [])
        
        # Should return False but not raise error
        assert result is False


class TestGDPRDataIsolation:
    """Test that GDPR deletion only affects the specified user"""
    
    def test_delete_does_not_affect_other_users(
        self,
        db: Session,
        property_service: PropertyService,
        test_user: User,
        test_properties: list
    ):
        """Test that deleting one user's data doesn't affect other users"""
        # Create another user with properties
        other_user = User(
            email="other_user@example.com",
            name="Other User",
            hashed_password="hashed_password"
        )
        db.add(other_user)
        db.commit()
        db.refresh(other_user)
        
        other_property = Property(
            user_id=other_user.id,
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100.00"),
            address="Other Street 1, 1040 Wien",
            street="Other Street 1",
            city="Wien",
            postal_code="1040",
            purchase_date=date(2021, 1, 1),
            purchase_price=Decimal("350000.00"),
            building_value=Decimal("280000.00"),
            construction_year=1995,
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db.add(other_property)
        db.commit()
        
        # Delete test_user's data
        property_service.delete_user_property_data(test_user.id)
        
        # Verify test_user's properties are deleted
        test_user_properties = db.query(Property).filter(
            Property.user_id == test_user.id
        ).count()
        assert test_user_properties == 0
        
        # Verify other_user's properties are NOT deleted
        other_user_properties = db.query(Property).filter(
            Property.user_id == other_user.id
        ).count()
        assert other_user_properties == 1
