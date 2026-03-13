"""
Unit tests for PropertyService

Tests CRUD operations, validation, ownership checks, and business logic.
"""
import pytest
from decimal import Decimal
from datetime import date, timedelta
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.user import User, UserType
from app.models.property import Property, PropertyType, PropertyStatus
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.schemas.property import PropertyCreate, PropertyUpdate
from app.services.property_service import PropertyService


# Test database setup
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def db_session():
    """Create a test database session
    
    Note: Uses SQLite for testing. Some PostgreSQL-specific constraints
    (like EXTRACT in CHECK constraints) are not enforced in SQLite,
    but the application logic is still tested.
    """
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    
    # Create tables - SQLite will ignore unsupported PostgreSQL syntax
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        # If table creation fails due to PostgreSQL-specific syntax,
        # skip those constraints - they're enforced at application level anyway
        print(f"Warning: Some database constraints may not be enforced in SQLite: {e}")
    
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    user = User(
        email="test@example.com",
        password_hash="hashed_password",
        name="Test User",
        user_type=UserType.LANDLORD,
        language="de"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def property_service(db_session):
    """Create a PropertyService instance"""
    return PropertyService(db_session)


@pytest.fixture
def sample_property_data():
    """Sample property creation data"""
    return PropertyCreate(
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        street="Hauptstraße 123",
        city="Wien",
        postal_code="1010",
        purchase_date=date(2020, 6, 15),
        purchase_price=Decimal("350000.00"),
        building_value=Decimal("280000.00"),
        construction_year=1985,
        depreciation_rate=Decimal("0.02")
    )


# Test: Property Creation
class TestPropertyCreation:
    """Tests for property creation"""
    
    def test_create_property_success(self, property_service, test_user, sample_property_data):
        """Test successful property creation"""
        property = property_service.create_property(test_user.id, sample_property_data)
        
        assert property.id is not None
        assert property.user_id == test_user.id
        assert property.street == "Hauptstraße 123"
        assert property.city == "Wien"
        assert property.postal_code == "1010"
        assert property.address == "Hauptstraße 123, 1010 Wien"
        assert property.purchase_price == Decimal("350000.00")
        assert property.building_value == Decimal("280000.00")
        assert property.land_value == Decimal("70000.00")
        assert property.depreciation_rate == Decimal("0.02")
        assert property.status == PropertyStatus.ACTIVE

    
    def test_create_property_auto_building_value(self, property_service, test_user):
        """Test building_value auto-calculation (80% of purchase_price)"""
        property_data = PropertyCreate(
            street="Teststraße 1",
            city="Graz",
            postal_code="8010",
            purchase_date=date(2021, 1, 1),
            purchase_price=Decimal("500000.00"),
            # building_value not provided - should be auto-calculated
            construction_year=2000
        )
        
        property = property_service.create_property(test_user.id, property_data)
        
        assert property.building_value == Decimal("400000.00")  # 80% of 500000
        assert property.land_value == Decimal("100000.00")
    
    def test_create_property_auto_depreciation_rate_post_1915(self, property_service, test_user):
        """Test auto-determination of depreciation rate for post-1915 building"""
        property_data = PropertyCreate(
            street="Teststraße 2",
            city="Linz",
            postal_code="4020",
            purchase_date=date(2022, 3, 1),
            purchase_price=Decimal("300000.00"),
            construction_year=1985  # Post-1915
            # depreciation_rate not provided
        )
        
        property = property_service.create_property(test_user.id, property_data)
        
        assert property.depreciation_rate == Decimal("0.02")  # 2.0%
    
    def test_create_property_auto_depreciation_rate_pre_1915(self, property_service, test_user):
        """Test auto-determination of depreciation rate for pre-1915 building"""
        property_data = PropertyCreate(
            street="Altstadt 5",
            city="Salzburg",
            postal_code="5020",
            purchase_date=date(2019, 8, 1),
            purchase_price=Decimal("450000.00"),
            construction_year=1890  # Pre-1915
        )
        
        property = property_service.create_property(test_user.id, property_data)
        
        assert property.depreciation_rate == Decimal("0.015")  # 1.5%

    
    def test_create_property_invalid_user(self, property_service, sample_property_data):
        """Test property creation with non-existent user"""
        with pytest.raises(ValueError, match="User with id 99999 not found"):
            property_service.create_property(99999, sample_property_data)


# Test: Property Retrieval
class TestPropertyRetrieval:
    """Tests for property retrieval"""
    
    def test_get_property_success(self, property_service, test_user, sample_property_data):
        """Test successful property retrieval"""
        created_property = property_service.create_property(test_user.id, sample_property_data)
        
        retrieved_property = property_service.get_property(created_property.id, test_user.id)
        
        assert retrieved_property.id == created_property.id
        assert retrieved_property.user_id == test_user.id
        assert retrieved_property.address == created_property.address
    
    def test_get_property_not_found(self, property_service, test_user):
        """Test retrieval of non-existent property"""
        fake_id = uuid4()
        
        with pytest.raises(ValueError, match=f"Property with id {fake_id} not found"):
            property_service.get_property(fake_id, test_user.id)
    
    def test_get_property_wrong_owner(self, property_service, test_user, sample_property_data, db_session):
        """Test retrieval of property by wrong user"""
        # Create property for test_user
        property = property_service.create_property(test_user.id, sample_property_data)
        
        # Create another user
        other_user = User(
            email="other@example.com",
            password_hash="hashed",
            name="Other User",
            user_type=UserType.LANDLORD,
            language="de"
        )
        db_session.add(other_user)
        db_session.commit()
        
        # Try to access property as other_user
        with pytest.raises(PermissionError, match="does not belong to user"):
            property_service.get_property(property.id, other_user.id)



# Test: Property Listing
class TestPropertyListing:
    """Tests for property listing"""
    
    def test_list_properties_empty(self, property_service, test_user):
        """Test listing when user has no properties"""
        properties = property_service.list_properties(test_user.id)
        
        assert len(properties) == 0
    
    def test_list_properties_multiple(self, property_service, test_user):
        """Test listing multiple properties"""
        # Create 3 properties
        for i in range(3):
            property_data = PropertyCreate(
                street=f"Street {i}",
                city="Wien",
                postal_code="1010",
                purchase_date=date(2020, 1, 1),
                purchase_price=Decimal("300000.00")
            )
            property_service.create_property(test_user.id, property_data)
        
        properties = property_service.list_properties(test_user.id)
        
        assert len(properties) == 3
    
    def test_list_properties_exclude_archived(self, property_service, test_user, sample_property_data):
        """Test that archived properties are excluded by default"""
        # Create active property
        active_property = property_service.create_property(test_user.id, sample_property_data)
        
        # Create and archive another property
        archived_data = PropertyCreate(
            street="Archived Street",
            city="Wien",
            postal_code="1020",
            purchase_date=date(2019, 1, 1),
            purchase_price=Decimal("250000.00")
        )
        archived_property = property_service.create_property(test_user.id, archived_data)
        property_service.archive_property(archived_property.id, test_user.id, date(2023, 12, 31))
        
        # List without archived
        properties = property_service.list_properties(test_user.id, include_archived=False)
        
        assert len(properties) == 1
        assert properties[0].id == active_property.id
    
    def test_list_properties_include_archived(self, property_service, test_user, sample_property_data):
        """Test including archived properties"""
        # Create active property
        property_service.create_property(test_user.id, sample_property_data)
        
        # Create and archive another property
        archived_data = PropertyCreate(
            street="Archived Street",
            city="Wien",
            postal_code="1020",
            purchase_date=date(2019, 1, 1),
            purchase_price=Decimal("250000.00")
        )
        archived_property = property_service.create_property(test_user.id, archived_data)
        property_service.archive_property(archived_property.id, test_user.id, date(2023, 12, 31))
        
        # List with archived
        properties = property_service.list_properties(test_user.id, include_archived=True)
        
        assert len(properties) == 2



# Test: Property Update
class TestPropertyUpdate:
    """Tests for property updates"""
    
    def test_update_property_address(self, property_service, test_user, sample_property_data):
        """Test updating property address"""
        property = property_service.create_property(test_user.id, sample_property_data)
        
        updates = PropertyUpdate(
            street="Neue Straße 456",
            city="Graz",
            postal_code="8010"
        )
        
        updated_property = property_service.update_property(property.id, test_user.id, updates)
        
        assert updated_property.street == "Neue Straße 456"
        assert updated_property.city == "Graz"
        assert updated_property.postal_code == "8010"
        assert updated_property.address == "Neue Straße 456, 8010 Graz"
    
    def test_update_property_building_value(self, property_service, test_user, sample_property_data):
        """Test updating building_value recalculates land_value"""
        property = property_service.create_property(test_user.id, sample_property_data)
        
        updates = PropertyUpdate(building_value=Decimal("300000.00"))
        
        updated_property = property_service.update_property(property.id, test_user.id, updates)
        
        assert updated_property.building_value == Decimal("300000.00")
        assert updated_property.land_value == Decimal("50000.00")  # 350000 - 300000
    
    def test_update_property_depreciation_rate(self, property_service, test_user, sample_property_data):
        """Test updating depreciation rate"""
        property = property_service.create_property(test_user.id, sample_property_data)
        
        updates = PropertyUpdate(depreciation_rate=Decimal("0.025"))
        
        updated_property = property_service.update_property(property.id, test_user.id, updates)
        
        assert updated_property.depreciation_rate == Decimal("0.025")
    
    def test_update_property_wrong_owner(self, property_service, test_user, sample_property_data, db_session):
        """Test updating property by wrong user"""
        property = property_service.create_property(test_user.id, sample_property_data)
        
        # Create another user
        other_user = User(
            email="other@example.com",
            password_hash="hashed",
            name="Other User",
            user_type=UserType.LANDLORD,
            language="de"
        )
        db_session.add(other_user)
        db_session.commit()
        
        updates = PropertyUpdate(street="Hacker Street")
        
        with pytest.raises(PermissionError):
            property_service.update_property(property.id, other_user.id, updates)



# Test: Property Archival
class TestPropertyArchival:
    """Tests for property archival"""
    
    def test_archive_property_success(self, property_service, test_user, sample_property_data):
        """Test successful property archival"""
        property = property_service.create_property(test_user.id, sample_property_data)
        
        sale_date = date(2023, 12, 31)
        archived_property = property_service.archive_property(property.id, test_user.id, sale_date)
        
        assert archived_property.status == PropertyStatus.SOLD
        assert archived_property.sale_date == sale_date
    
    def test_archive_property_invalid_sale_date(self, property_service, test_user, sample_property_data):
        """Test archival with sale_date before purchase_date"""
        property = property_service.create_property(test_user.id, sample_property_data)
        
        # Try to set sale_date before purchase_date
        invalid_sale_date = property.purchase_date - timedelta(days=1)
        
        with pytest.raises(ValueError, match="Sale date .* cannot be before purchase date"):
            property_service.archive_property(property.id, test_user.id, invalid_sale_date)


# Test: Property Deletion
class TestPropertyDeletion:
    """Tests for property deletion"""
    
    def test_delete_property_success(self, property_service, test_user, sample_property_data):
        """Test successful property deletion (no linked transactions)"""
        property = property_service.create_property(test_user.id, sample_property_data)
        
        result = property_service.delete_property(property.id, test_user.id)
        
        assert result is True
        
        # Verify property is deleted
        with pytest.raises(ValueError, match="Property with id .* not found"):
            property_service.get_property(property.id, test_user.id)
    
    def test_delete_property_with_transactions(self, property_service, test_user, sample_property_data, db_session):
        """Test deletion fails when property has linked transactions"""
        property = property_service.create_property(test_user.id, sample_property_data)
        
        # Create a linked transaction
        transaction = Transaction(
            user_id=test_user.id,
            property_id=property.id,
            type=TransactionType.INCOME,
            amount=Decimal("1000.00"),
            transaction_date=date(2023, 1, 1),
            income_category=IncomeCategory.RENTAL
        )
        db_session.add(transaction)
        db_session.commit()
        
        # Try to delete property
        with pytest.raises(ValueError, match="Cannot delete property .* linked transaction"):
            property_service.delete_property(property.id, test_user.id)



# Test: Transaction Linking
class TestTransactionLinking:
    """Tests for linking transactions to properties"""
    
    def test_link_transaction_success(self, property_service, test_user, sample_property_data, db_session):
        """Test successful transaction linking"""
        property = property_service.create_property(test_user.id, sample_property_data)
        
        # Create transaction
        transaction = Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=Decimal("1500.00"),
            transaction_date=date(2023, 1, 1),
            income_category=IncomeCategory.RENTAL
        )
        db_session.add(transaction)
        db_session.commit()
        db_session.refresh(transaction)
        
        # Link transaction to property
        linked_transaction = property_service.link_transaction_to_property(
            transaction.id, property.id, test_user.id
        )
        
        assert linked_transaction.property_id == property.id
    
    def test_link_transaction_wrong_user(self, property_service, test_user, sample_property_data, db_session):
        """Test linking transaction by wrong user"""
        property = property_service.create_property(test_user.id, sample_property_data)
        
        # Create another user
        other_user = User(
            email="other@example.com",
            password_hash="hashed",
            name="Other User",
            user_type=UserType.LANDLORD,
            language="de"
        )
        db_session.add(other_user)
        db_session.commit()
        
        # Create transaction for other_user
        transaction = Transaction(
            user_id=other_user.id,
            type=TransactionType.INCOME,
            amount=Decimal("1000.00"),
            transaction_date=date(2023, 1, 1),
            income_category=IncomeCategory.RENTAL
        )
        db_session.add(transaction)
        db_session.commit()
        db_session.refresh(transaction)
        
        # Try to link other_user's transaction to test_user's property
        with pytest.raises(PermissionError):
            property_service.link_transaction_to_property(
                transaction.id, property.id, test_user.id
            )
    
    def test_unlink_transaction_success(self, property_service, test_user, sample_property_data, db_session):
        """Test successful transaction unlinking"""
        property = property_service.create_property(test_user.id, sample_property_data)
        
        # Create and link transaction
        transaction = Transaction(
            user_id=test_user.id,
            property_id=property.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("500.00"),
            transaction_date=date(2023, 1, 1),
            expense_category=ExpenseCategory.MAINTENANCE
        )
        db_session.add(transaction)
        db_session.commit()
        db_session.refresh(transaction)
        
        # Unlink transaction
        unlinked_transaction = property_service.unlink_transaction_from_property(
            transaction.id, test_user.id
        )
        
        assert unlinked_transaction.property_id is None



# Test: Get Property Transactions
class TestGetPropertyTransactions:
    """Tests for retrieving property transactions"""
    
    def test_get_property_transactions_empty(self, property_service, test_user, sample_property_data):
        """Test getting transactions when none exist"""
        property = property_service.create_property(test_user.id, sample_property_data)
        
        transactions = property_service.get_property_transactions(property.id, test_user.id)
        
        assert len(transactions) == 0
    
    def test_get_property_transactions_multiple(self, property_service, test_user, sample_property_data, db_session):
        """Test getting multiple transactions"""
        property = property_service.create_property(test_user.id, sample_property_data)
        
        # Create 3 transactions
        for i in range(3):
            transaction = Transaction(
                user_id=test_user.id,
                property_id=property.id,
                type=TransactionType.INCOME,
                amount=Decimal(f"{1000 + i * 100}.00"),
                transaction_date=date(2023, i + 1, 1),
                income_category=IncomeCategory.RENTAL
            )
            db_session.add(transaction)
        db_session.commit()
        
        transactions = property_service.get_property_transactions(property.id, test_user.id)
        
        assert len(transactions) == 3
    
    def test_get_property_transactions_year_filter(self, property_service, test_user, sample_property_data, db_session):
        """Test filtering transactions by year"""
        property = property_service.create_property(test_user.id, sample_property_data)
        
        # Create transactions in different years
        for year in [2021, 2022, 2023]:
            transaction = Transaction(
                user_id=test_user.id,
                property_id=property.id,
                type=TransactionType.INCOME,
                amount=Decimal("1000.00"),
                transaction_date=date(year, 1, 1),
                income_category=IncomeCategory.RENTAL
            )
            db_session.add(transaction)
        db_session.commit()
        
        # Get transactions for 2022 only
        transactions = property_service.get_property_transactions(property.id, test_user.id, year=2022)
        
        assert len(transactions) == 1
        assert transactions[0].transaction_date.year == 2022



# Test: Calculate Property Metrics
class TestCalculatePropertyMetrics:
    """Tests for property metrics calculation"""
    
    def test_calculate_metrics_no_transactions(self, property_service, test_user, sample_property_data):
        """Test metrics calculation with no transactions"""
        property = property_service.create_property(test_user.id, sample_property_data)
        
        metrics = property_service.calculate_property_metrics(property.id, test_user.id, year=2023)
        
        assert metrics.property_id == property.id
        assert metrics.accumulated_depreciation == Decimal("0")
        assert metrics.remaining_depreciable_value == property.building_value
        assert metrics.total_rental_income == Decimal("0")
        assert metrics.total_expenses == Decimal("0")
        assert metrics.net_rental_income == Decimal("0")
    
    def test_calculate_metrics_with_income_and_expenses(self, property_service, test_user, sample_property_data, db_session):
        """Test metrics calculation with income and expenses"""
        property = property_service.create_property(test_user.id, sample_property_data)
        
        # Create rental income
        income = Transaction(
            user_id=test_user.id,
            property_id=property.id,
            type=TransactionType.INCOME,
            amount=Decimal("12000.00"),
            transaction_date=date(2023, 1, 1),
            income_category=IncomeCategory.RENTAL
        )
        db_session.add(income)
        
        # Create expenses
        expense1 = Transaction(
            user_id=test_user.id,
            property_id=property.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("2000.00"),
            transaction_date=date(2023, 2, 1),
            expense_category=ExpenseCategory.MAINTENANCE
        )
        db_session.add(expense1)
        
        expense2 = Transaction(
            user_id=test_user.id,
            property_id=property.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("1500.00"),
            transaction_date=date(2023, 3, 1),
            expense_category=ExpenseCategory.PROPERTY_TAX
        )
        db_session.add(expense2)
        
        db_session.commit()
        
        metrics = property_service.calculate_property_metrics(property.id, test_user.id, year=2023)
        
        assert metrics.total_rental_income == Decimal("12000.00")
        assert metrics.total_expenses == Decimal("3500.00")
        assert metrics.net_rental_income == Decimal("8500.00")
    
    def test_calculate_metrics_with_depreciation(self, property_service, test_user, sample_property_data, db_session):
        """Test metrics calculation with depreciation transactions"""
        property = property_service.create_property(test_user.id, sample_property_data)
        
        # Create depreciation transactions for multiple years
        for year in [2020, 2021, 2022]:
            depreciation = Transaction(
                user_id=test_user.id,
                property_id=property.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("5600.00"),  # 280000 * 0.02
                transaction_date=date(year, 12, 31),
                expense_category=ExpenseCategory.DEPRECIATION,
                is_system_generated=True
            )
            db_session.add(depreciation)
        db_session.commit()
        
        metrics = property_service.calculate_property_metrics(property.id, test_user.id, year=2023)
        
        # Accumulated depreciation should be 3 years * 5600
        assert metrics.accumulated_depreciation == Decimal("16800.00")
        # Remaining value should be building_value - accumulated
        assert metrics.remaining_depreciable_value == Decimal("263200.00")  # 280000 - 16800
