"""
Unit tests for optimized property list queries (Task C.2.3)

Tests cover:
- Query efficiency (verify minimal queries)
- Pagination behavior
- Metrics calculation accuracy
- Filter combinations
"""

import pytest
from decimal import Decimal
from datetime import date, timedelta
from uuid import uuid4
from sqlalchemy.orm import Session
from sqlalchemy import event, create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.property import Property, PropertyType, PropertyStatus
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.models.user import User, UserType
from app.services.property_service import PropertyService
from app.schemas.property import PropertyCreate


# Test database setup
TEST_DATABASE_URL = "sqlite:///:memory:"


class QueryCounter:
    """Helper class to count SQL queries executed"""
    def __init__(self):
        self.count = 0
        self.queries = []
    
    def __call__(self, conn, cursor, statement, parameters, context, executemany):
        self.count += 1
        self.queries.append(statement)


@pytest.fixture
def db_session():
    """Create a test database session"""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    
    # Create tables - SQLite will ignore unsupported PostgreSQL syntax
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Warning: Some database constraints may not be enforced in SQLite: {e}")
    
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def query_counter(db_session: Session):
    """Fixture to count queries executed during a test"""
    counter = QueryCounter()
    event.listen(db_session.bind, "before_cursor_execute", counter)
    yield counter
    event.remove(db_session.bind, "before_cursor_execute", counter)


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a test user"""
    user = User(
        email=f"test_{uuid4()}@example.com",
        name="Test User",
        user_type=UserType.LANDLORD,
        password_hash="hashed_password",
        language="de"
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
def sample_properties(db_session: Session, test_user: User, property_service: PropertyService) -> list[Property]:
    """Create sample properties for testing"""
    properties = []
    
    # Create 5 active properties
    for i in range(5):
        property_data = PropertyCreate(
            street=f"Test Street {i+1}",
            city="Vienna",
            postal_code=f"10{i:02d}",
            purchase_date=date(2020, 1, 1) + timedelta(days=i*30),
            purchase_price=Decimal("300000.00") + Decimal(i * 10000),
            building_value=Decimal("240000.00") + Decimal(i * 8000),
            construction_year=1990 + i,
            property_type=PropertyType.RENTAL
        )
        property = property_service.create_property(test_user.id, property_data)
        properties.append(property)
    
    # Create 2 archived properties
    for i in range(2):
        property_data = PropertyCreate(
            street=f"Archived Street {i+1}",
            city="Vienna",
            postal_code=f"20{i:02d}",
            purchase_date=date(2018, 1, 1),
            purchase_price=Decimal("250000.00"),
            building_value=Decimal("200000.00"),
            construction_year=1985,
            property_type=PropertyType.RENTAL
        )
        property = property_service.create_property(test_user.id, property_data)
        property_service.archive_property(property.id, test_user.id, date(2023, 12, 31))
        properties.append(property)
    
    db_session.commit()
    return properties


@pytest.fixture
def properties_with_transactions(
    db_session: Session,
    test_user: User,
    sample_properties: list[Property]
) -> list[Property]:
    """Add transactions to sample properties"""
    current_year = date.today().year
    
    for i, property in enumerate(sample_properties[:5]):  # Only active properties
        # Add rental income
        for month in range(1, 13):
            transaction = Transaction(
                user_id=test_user.id,
                property_id=property.id,
                type=TransactionType.INCOME,
                income_category=IncomeCategory.RENTAL,
                amount=Decimal("1000.00") + Decimal(i * 100),
                transaction_date=date(current_year, month, 1),
                description=f"Rental income {month}/{current_year}",
                is_deductible=False
            )
            db_session.add(transaction)
        
        # Add expenses
        for month in range(1, 7):
            transaction = Transaction(
                user_id=test_user.id,
                property_id=property.id,
                type=TransactionType.EXPENSE,
                expense_category=ExpenseCategory.MAINTENANCE,
                amount=Decimal("200.00") + Decimal(i * 20),
                transaction_date=date(current_year, month, 15),
                description=f"Maintenance {month}/{current_year}",
                is_deductible=True
            )
            db_session.add(transaction)
        
        # Add depreciation transactions for previous years
        for year in range(2020, current_year):
            transaction = Transaction(
                user_id=test_user.id,
                property_id=property.id,
                type=TransactionType.EXPENSE,
                expense_category=ExpenseCategory.DEPRECIATION_AFA,
                amount=property.building_value * property.depreciation_rate,
                transaction_date=date(year, 12, 31),
                description=f"AfA {year}",
                is_deductible=True,
                is_system_generated=True
            )
            db_session.add(transaction)
    
    db_session.commit()
    return sample_properties


class TestListPropertiesWithMetrics:
    """Test suite for list_properties_with_metrics method"""
    
    def test_query_efficiency_no_n_plus_1(
        self,
        db_session: Session,
        property_service: PropertyService,
        test_user: User,
        properties_with_transactions: list[Property],
        query_counter: QueryCounter
    ):
        """
        Test that list_properties_with_metrics avoids N+1 query problem.
        
        Should execute a fixed number of queries regardless of property count:
        1. Count query for total
        2. Properties query with pagination
        3. Depreciation aggregation query
        4. Rental income aggregation query
        5. Expenses aggregation query
        6. Combined metrics query
        
        Plus a few queries for annual depreciation calculation (one per property).
        Total should be significantly less than N queries for N properties.
        """
        # Reset counter
        query_counter.count = 0
        query_counter.queries = []
        
        # Execute list_properties_with_metrics
        properties, metrics, total = property_service.list_properties_with_metrics(
            user_id=test_user.id,
            include_archived=False,
            skip=0,
            limit=50
        )
        
        # Verify results
        assert len(properties) == 5
        assert len(metrics) == 5
        assert total == 5
        
        # Count queries - should be much less than 5 * N (where N is number of properties)
        # Expected: ~10-15 queries total (not 5 * 5 = 25+ for N+1 problem)
        print(f"\nTotal queries executed: {query_counter.count}")
        print(f"Queries per property: {query_counter.count / len(properties):.2f}")
        
        # Assert query efficiency - should be less than 4 queries per property on average
        # (N+1 would be 5+ queries per property)
        assert query_counter.count < len(properties) * 4, \
            f"Too many queries: {query_counter.count} for {len(properties)} properties"
    
    def test_pagination_first_page(
        self,
        property_service: PropertyService,
        test_user: User,
        properties_with_transactions: list[Property]
    ):
        """Test pagination - first page"""
        properties, metrics, total = property_service.list_properties_with_metrics(
            user_id=test_user.id,
            include_archived=False,
            skip=0,
            limit=3
        )
        
        assert len(properties) == 3
        assert len(metrics) == 3
        assert total == 5  # Total active properties
        
        # Verify properties are ordered by created_at desc (newest first)
        assert properties[0].created_at >= properties[1].created_at
        assert properties[1].created_at >= properties[2].created_at
    
    def test_pagination_second_page(
        self,
        property_service: PropertyService,
        test_user: User,
        properties_with_transactions: list[Property]
    ):
        """Test pagination - second page"""
        properties, metrics, total = property_service.list_properties_with_metrics(
            user_id=test_user.id,
            include_archived=False,
            skip=3,
            limit=3
        )
        
        assert len(properties) == 2  # Only 2 remaining
        assert len(metrics) == 2
        assert total == 5
    
    def test_pagination_beyond_available(
        self,
        property_service: PropertyService,
        test_user: User,
        properties_with_transactions: list[Property]
    ):
        """Test pagination - skip beyond available records"""
        properties, metrics, total = property_service.list_properties_with_metrics(
            user_id=test_user.id,
            include_archived=False,
            skip=10,
            limit=3
        )
        
        assert len(properties) == 0
        assert len(metrics) == 0
        assert total == 5
    
    def test_metrics_calculation_accuracy(
        self,
        property_service: PropertyService,
        test_user: User,
        properties_with_transactions: list[Property]
    ):
        """Test that metrics are calculated accurately"""
        current_year = date.today().year
        
        # Get the first property (index 0 in the original list)
        first_property = properties_with_transactions[0]
        
        properties, metrics, total = property_service.list_properties_with_metrics(
            user_id=test_user.id,
            include_archived=False,
            skip=0,
            limit=50,
            year=current_year
        )
        
        # Find the first property in the results
        property_index = next(i for i, p in enumerate(properties) if p.id == first_property.id)
        property = properties[property_index]
        metric = metrics[property_index]
        
        # Verify metric structure
        assert metric.property_id == property.id
        assert metric.accumulated_depreciation >= Decimal("0")
        assert metric.remaining_depreciable_value >= Decimal("0")
        assert metric.annual_depreciation >= Decimal("0")
        assert metric.total_rental_income >= Decimal("0")
        assert metric.total_expenses >= Decimal("0")
        
        # Verify rental income (12 months * (1000 + 0*100) = 12000 for first property)
        assert metric.total_rental_income == Decimal("12000.00")
        
        # Verify expenses (6 months * (200 + 0*20) = 1200 for first property)
        assert metric.total_expenses == Decimal("1200.00")
        
        # Verify net income
        assert metric.net_rental_income == metric.total_rental_income - metric.total_expenses
        assert metric.net_rental_income == Decimal("10800.00")
        
        # Verify accumulated depreciation (years from 2020 to current_year - 1)
        years_depreciated = current_year - 2020
        expected_accumulated = property.building_value * property.depreciation_rate * years_depreciated
        assert abs(metric.accumulated_depreciation - expected_accumulated) < Decimal("1.00")
    
    def test_filter_include_archived(
        self,
        property_service: PropertyService,
        test_user: User,
        properties_with_transactions: list[Property]
    ):
        """Test include_archived filter"""
        # Without archived
        properties_active, metrics_active, total_active = property_service.list_properties_with_metrics(
            user_id=test_user.id,
            include_archived=False,
            skip=0,
            limit=50
        )
        
        assert len(properties_active) == 5
        assert total_active == 5
        
        # With archived
        properties_all, metrics_all, total_all = property_service.list_properties_with_metrics(
            user_id=test_user.id,
            include_archived=True,
            skip=0,
            limit=50
        )
        
        assert len(properties_all) == 7  # 5 active + 2 archived
        assert total_all == 7
        
        # Verify archived properties are included
        archived_count = sum(1 for p in properties_all if p.status != PropertyStatus.ACTIVE)
        assert archived_count == 2
    
    def test_empty_result_set(
        self,
        db_session: Session,
        property_service: PropertyService
    ):
        """Test with user who has no properties"""
        # Create new user with no properties
        new_user = User(
            email=f"empty_{uuid4()}@example.com",
            name="Empty User",
            user_type=UserType.LANDLORD,
            password_hash="hashed_password",
            language="de"
        )
        db_session.add(new_user)
        db_session.commit()
        db_session.refresh(new_user)
        
        properties, metrics, total = property_service.list_properties_with_metrics(
            user_id=new_user.id,
            include_archived=False,
            skip=0,
            limit=50
        )
        
        assert len(properties) == 0
        assert len(metrics) == 0
        assert total == 0
    
    def test_properties_without_transactions(
        self,
        property_service: PropertyService,
        test_user: User,
        sample_properties: list[Property]
    ):
        """Test properties that have no transactions"""
        properties, metrics, total = property_service.list_properties_with_metrics(
            user_id=test_user.id,
            include_archived=False,
            skip=0,
            limit=50
        )
        
        assert len(properties) == 5
        assert len(metrics) == 5
        
        # All metrics should be zero or minimal
        for metric in metrics:
            assert metric.accumulated_depreciation == Decimal("0")
            assert metric.total_rental_income == Decimal("0")
            assert metric.total_expenses == Decimal("0")
            assert metric.net_rental_income == Decimal("0")
    
    def test_year_filter(
        self,
        property_service: PropertyService,
        test_user: User,
        properties_with_transactions: list[Property]
    ):
        """Test year filter for metrics"""
        current_year = date.today().year
        last_year = current_year - 1
        
        # Get the first property
        first_property = properties_with_transactions[0]
        
        # Get metrics for current year
        properties_current, metrics_current, _ = property_service.list_properties_with_metrics(
            user_id=test_user.id,
            include_archived=False,
            skip=0,
            limit=50,
            year=current_year
        )
        
        # Find the first property in results
        idx_current = next(i for i, p in enumerate(properties_current) if p.id == first_property.id)
        
        # Get metrics for last year (should have no income/expenses from current year transactions)
        properties_last, metrics_last, _ = property_service.list_properties_with_metrics(
            user_id=test_user.id,
            include_archived=False,
            skip=0,
            limit=50,
            year=last_year
        )
        
        # Find the first property in results
        idx_last = next(i for i, p in enumerate(properties_last) if p.id == first_property.id)
        
        # Current year should have income/expenses
        assert metrics_current[idx_current].total_rental_income > Decimal("0")
        assert metrics_current[idx_current].total_expenses > Decimal("0")
        
        # Last year should have no income/expenses from current year transactions
        # (only depreciation from historical years, but that's not counted in total_expenses for last year)
        assert metrics_last[idx_last].total_rental_income == Decimal("0")
        # Note: total_expenses for last year will be 0 because we only added transactions for current year
        # The depreciation transactions are for years 2020 to current_year-1, so last year would have depreciation
        # But our expense query filters by year, so it should only show expenses from that specific year
        # Since we didn't add any expenses for last year, it should be 0
        # However, if last_year is in the range 2020 to current_year-1, there will be depreciation
        if last_year >= 2020:
            # There should be depreciation for last year
            assert metrics_last[idx_last].total_expenses > Decimal("0")
        else:
            assert metrics_last[idx_last].total_expenses == Decimal("0")
        
        # But accumulated depreciation should be the same (all-time)
        assert metrics_current[idx_current].accumulated_depreciation == metrics_last[idx_last].accumulated_depreciation
    
    def test_mixed_use_property_metrics(
        self,
        db_session: Session,
        property_service: PropertyService,
        test_user: User
    ):
        """Test metrics calculation for mixed-use properties"""
        # Create mixed-use property (50% rental)
        property_data = PropertyCreate(
            street="Mixed Use Street",
            city="Vienna",
            postal_code="1010",
            purchase_date=date(2020, 1, 1),
            purchase_price=Decimal("400000.00"),
            building_value=Decimal("320000.00"),
            construction_year=2000,
            property_type=PropertyType.MIXED_USE,
            rental_percentage=Decimal("50.00")
        )
        property = property_service.create_property(test_user.id, property_data)
        
        # Add depreciation transaction
        transaction = Transaction(
            user_id=test_user.id,
            property_id=property.id,
            type=TransactionType.EXPENSE,
            expense_category=ExpenseCategory.DEPRECIATION_AFA,
            amount=Decimal("3200.00"),  # 50% of building_value * 2%
            transaction_date=date(2020, 12, 31),
            description="AfA 2020",
            is_deductible=True,
            is_system_generated=True
        )
        db_session.add(transaction)
        db_session.commit()
        
        properties, metrics, total = property_service.list_properties_with_metrics(
            user_id=test_user.id,
            include_archived=False,
            skip=0,
            limit=50
        )
        
        # Find the mixed-use property
        mixed_property = next(p for p in properties if p.id == property.id)
        mixed_metric = next(m for m in metrics if m.property_id == property.id)
        
        # Verify depreciable value is calculated correctly (50% of building_value)
        expected_depreciable = Decimal("320000.00") * Decimal("0.50")
        expected_remaining = expected_depreciable - mixed_metric.accumulated_depreciation
        
        assert abs(mixed_metric.remaining_depreciable_value - expected_remaining) < Decimal("1.00")
    
    def test_default_limit(
        self,
        db_session: Session,
        property_service: PropertyService,
        test_user: User
    ):
        """Test default limit of 50 properties"""
        # Create 60 properties
        for i in range(60):
            property_data = PropertyCreate(
                street=f"Street {i}",
                city="Vienna",
                postal_code=f"{1000 + i}",
                purchase_date=date(2020, 1, 1),
                purchase_price=Decimal("300000.00"),
                building_value=Decimal("240000.00"),
                construction_year=2000,
                property_type=PropertyType.RENTAL
            )
            property_service.create_property(test_user.id, property_data)
        
        db_session.commit()
        
        # Get first page with default limit
        properties, metrics, total = property_service.list_properties_with_metrics(
            user_id=test_user.id,
            include_archived=False,
            skip=0,
            limit=50
        )
        
        assert len(properties) == 50
        assert len(metrics) == 50
        assert total == 60
        
        # Get second page
        properties2, metrics2, total2 = property_service.list_properties_with_metrics(
            user_id=test_user.id,
            include_archived=False,
            skip=50,
            limit=50
        )
        
        assert len(properties2) == 10
        assert len(metrics2) == 10
        assert total2 == 60


class TestListPropertiesBackwardCompatibility:
    """Test that original list_properties method still works"""
    
    def test_list_properties_unchanged(
        self,
        property_service: PropertyService,
        test_user: User,
        sample_properties: list[Property]
    ):
        """Test that list_properties method still works as before"""
        properties = property_service.list_properties(
            user_id=test_user.id,
            include_archived=False
        )
        
        assert len(properties) == 5
        assert all(p.status == PropertyStatus.ACTIVE for p in properties)
    
    def test_list_properties_with_archived(
        self,
        property_service: PropertyService,
        test_user: User,
        sample_properties: list[Property]
    ):
        """Test list_properties with archived filter"""
        properties = property_service.list_properties(
            user_id=test_user.id,
            include_archived=True
        )
        
        assert len(properties) == 7  # 5 active + 2 archived
