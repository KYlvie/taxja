"""
Performance tests for property queries (Task C.2.2)

Tests verify that property queries complete under 100ms target.
Uses realistic data volumes and measures actual execution time.
"""

import pytest
import time
from decimal import Decimal
from datetime import date, timedelta
from uuid import uuid4
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.property import Property, PropertyType, PropertyStatus
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.models.user import User, UserType
from app.services.property_service import PropertyService
from app.schemas.property import PropertyCreate


# Test database setup - use PostgreSQL-like settings
TEST_DATABASE_URL = "sqlite:///:memory:"

# Performance thresholds (in seconds)
TARGET_QUERY_TIME = 0.100  # 100ms target
WARNING_QUERY_TIME = 0.150  # 150ms warning threshold
MAX_QUERY_TIME = 0.200  # 200ms maximum acceptable


@pytest.fixture
def db_session():
    """Create a test database session"""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False  # Disable SQL logging for performance tests
    )
    
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
def test_user(db_session: Session) -> User:
    """Create a test user"""
    user = User(
        email=f"perf_test_{uuid4()}@example.com",
        name="Performance Test User",
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


def create_realistic_property_portfolio(
    db_session: Session,
    property_service: PropertyService,
    user: User,
    num_properties: int = 20
) -> list[Property]:
    """
    Create a realistic property portfolio with transactions.
    
    Simulates a landlord with multiple properties, each having:
    - Monthly rental income
    - Various expenses (maintenance, insurance, etc.)
    - Historical depreciation transactions
    """
    properties = []
    current_year = date.today().year
    
    for i in range(num_properties):
        # Create property
        purchase_year = 2015 + (i % 8)  # Properties purchased between 2015-2022
        property_data = PropertyCreate(
            street=f"Property Street {i+1}",
            city="Vienna" if i % 3 == 0 else "Graz" if i % 3 == 1 else "Salzburg",
            postal_code=f"{1000 + i:04d}",
            purchase_date=date(purchase_year, (i % 12) + 1, 1),
            purchase_price=Decimal("250000.00") + Decimal(i * 15000),
            building_value=Decimal("200000.00") + Decimal(i * 12000),
            construction_year=1980 + (i % 40),
            property_type=PropertyType.RENTAL if i % 10 != 0 else PropertyType.MIXED_USE,
            rental_percentage=Decimal("100.00") if i % 10 != 0 else Decimal("60.00")
        )
        property = property_service.create_property(user.id, property_data)
        properties.append(property)
        
        # Add rental income transactions (monthly for current year)
        monthly_rent = Decimal("800.00") + Decimal(i * 50)
        for month in range(1, 13):
            transaction = Transaction(
                user_id=user.id,
                property_id=property.id,
                type=TransactionType.INCOME,
                income_category=IncomeCategory.RENTAL,
                amount=monthly_rent,
                transaction_date=date(current_year, month, 1),
                description=f"Rental income {month}/{current_year}",
                is_deductible=False
            )
            db_session.add(transaction)
        
        # Add various expenses (current year)
        expense_types = [
            (ExpenseCategory.MAINTENANCE, Decimal("150.00"), 4),  # Quarterly
            (ExpenseCategory.PROPERTY_INSURANCE, Decimal("300.00"), 1),  # Annual
            (ExpenseCategory.PROPERTY_TAX, Decimal("500.00"), 1),  # Annual
            (ExpenseCategory.UTILITIES, Decimal("80.00"), 12),  # Monthly
        ]
        
        for expense_cat, base_amount, frequency in expense_types:
            for j in range(frequency):
                month = (j * (12 // frequency)) + 1 if frequency > 1 else 6
                transaction = Transaction(
                    user_id=user.id,
                    property_id=property.id,
                    type=TransactionType.EXPENSE,
                    expense_category=expense_cat,
                    amount=base_amount + Decimal(i * 10),
                    transaction_date=date(current_year, month, 15),
                    description=f"{expense_cat.value} {month}/{current_year}",
                    is_deductible=True
                )
                db_session.add(transaction)
        
        # Add historical depreciation transactions
        for year in range(purchase_year, current_year):
            annual_depreciation = property.building_value * property.depreciation_rate
            if property.property_type == PropertyType.MIXED_USE:
                annual_depreciation *= (property.rental_percentage / Decimal("100"))
            
            transaction = Transaction(
                user_id=user.id,
                property_id=property.id,
                type=TransactionType.EXPENSE,
                expense_category=ExpenseCategory.DEPRECIATION_AFA,
                amount=annual_depreciation,
                transaction_date=date(year, 12, 31),
                description=f"AfA {year}",
                is_deductible=True,
                is_system_generated=True
            )
            db_session.add(transaction)
    
    db_session.commit()
    return properties


class TestPropertyQueryPerformance:
    """Performance tests for property queries"""
    
    def test_list_properties_performance_small_portfolio(
        self,
        db_session: Session,
        property_service: PropertyService,
        test_user: User
    ):
        """
        Test list_properties_with_metrics performance with small portfolio (5 properties).
        
        Target: < 100ms
        """
        # Create 5 properties with realistic data
        properties = create_realistic_property_portfolio(
            db_session, property_service, test_user, num_properties=5
        )
        
        # Warm up query (first query may be slower due to SQLAlchemy initialization)
        property_service.list_properties_with_metrics(
            user_id=test_user.id,
            include_archived=False,
            skip=0,
            limit=50
        )
        
        # Measure actual query time
        start_time = time.perf_counter()
        
        result_properties, result_metrics, total = property_service.list_properties_with_metrics(
            user_id=test_user.id,
            include_archived=False,
            skip=0,
            limit=50
        )
        
        end_time = time.perf_counter()
        query_time = end_time - start_time
        
        # Verify results
        assert len(result_properties) == 5
        assert len(result_metrics) == 5
        assert total == 5
        
        # Performance assertions
        print(f"\nSmall portfolio query time: {query_time*1000:.2f}ms")
        
        if query_time > MAX_QUERY_TIME:
            pytest.fail(
                f"Query too slow: {query_time*1000:.2f}ms (max: {MAX_QUERY_TIME*1000:.0f}ms)"
            )
        elif query_time > WARNING_QUERY_TIME:
            pytest.warns(
                UserWarning,
                match=f"Query slower than warning threshold: {query_time*1000:.2f}ms"
            )
        
        # Target assertion (may fail in CI/slow environments, but good to track)
        assert query_time < TARGET_QUERY_TIME, \
            f"Query time {query_time*1000:.2f}ms exceeds target {TARGET_QUERY_TIME*1000:.0f}ms"
    
    def test_list_properties_performance_medium_portfolio(
        self,
        db_session: Session,
        property_service: PropertyService,
        test_user: User
    ):
        """
        Test list_properties_with_metrics performance with medium portfolio (20 properties).
        
        Target: < 100ms
        """
        # Create 20 properties with realistic data
        properties = create_realistic_property_portfolio(
            db_session, property_service, test_user, num_properties=20
        )
        
        # Warm up
        property_service.list_properties_with_metrics(
            user_id=test_user.id,
            include_archived=False,
            skip=0,
            limit=50
        )
        
        # Measure query time
        start_time = time.perf_counter()
        
        result_properties, result_metrics, total = property_service.list_properties_with_metrics(
            user_id=test_user.id,
            include_archived=False,
            skip=0,
            limit=50
        )
        
        end_time = time.perf_counter()
        query_time = end_time - start_time
        
        # Verify results
        assert len(result_properties) == 20
        assert len(result_metrics) == 20
        assert total == 20
        
        # Performance assertions
        print(f"\nMedium portfolio query time: {query_time*1000:.2f}ms")
        
        if query_time > MAX_QUERY_TIME:
            pytest.fail(
                f"Query too slow: {query_time*1000:.2f}ms (max: {MAX_QUERY_TIME*1000:.0f}ms)"
            )
        elif query_time > WARNING_QUERY_TIME:
            print(f"⚠️  Warning: Query time {query_time*1000:.2f}ms exceeds warning threshold")
        
        assert query_time < TARGET_QUERY_TIME, \
            f"Query time {query_time*1000:.2f}ms exceeds target {TARGET_QUERY_TIME*1000:.0f}ms"
    
    def test_list_properties_performance_large_portfolio(
        self,
        db_session: Session,
        property_service: PropertyService,
        test_user: User
    ):
        """
        Test list_properties_with_metrics performance with large portfolio (50 properties).
        
        Target: < 100ms (with pagination)
        """
        # Create 50 properties with realistic data
        properties = create_realistic_property_portfolio(
            db_session, property_service, test_user, num_properties=50
        )
        
        # Warm up
        property_service.list_properties_with_metrics(
            user_id=test_user.id,
            include_archived=False,
            skip=0,
            limit=50
        )
        
        # Measure query time for first page
        start_time = time.perf_counter()
        
        result_properties, result_metrics, total = property_service.list_properties_with_metrics(
            user_id=test_user.id,
            include_archived=False,
            skip=0,
            limit=50
        )
        
        end_time = time.perf_counter()
        query_time = end_time - start_time
        
        # Verify results
        assert len(result_properties) == 50
        assert len(result_metrics) == 50
        assert total == 50
        
        # Performance assertions
        print(f"\nLarge portfolio query time: {query_time*1000:.2f}ms")
        
        if query_time > MAX_QUERY_TIME:
            pytest.fail(
                f"Query too slow: {query_time*1000:.2f}ms (max: {MAX_QUERY_TIME*1000:.0f}ms)"
            )
        elif query_time > WARNING_QUERY_TIME:
            print(f"⚠️  Warning: Query time {query_time*1000:.2f}ms exceeds warning threshold")
        
        # For large portfolios, we allow slightly more time but still aim for target
        assert query_time < TARGET_QUERY_TIME * 1.5, \
            f"Query time {query_time*1000:.2f}ms significantly exceeds target"
    
    def test_get_property_performance(
        self,
        db_session: Session,
        property_service: PropertyService,
        test_user: User
    ):
        """
        Test get_property performance (single property fetch).
        
        Target: < 50ms
        """
        # Create one property with transactions
        properties = create_realistic_property_portfolio(
            db_session, property_service, test_user, num_properties=1
        )
        property_id = properties[0].id
        
        # Warm up
        property_service.get_property(property_id, test_user.id)
        
        # Measure query time
        start_time = time.perf_counter()
        
        property = property_service.get_property(property_id, test_user.id)
        
        end_time = time.perf_counter()
        query_time = end_time - start_time
        
        # Verify result
        assert property.id == property_id
        
        # Performance assertions (single property should be very fast)
        print(f"\nSingle property fetch time: {query_time*1000:.2f}ms")
        
        single_property_target = TARGET_QUERY_TIME / 2  # 50ms for single property
        
        assert query_time < single_property_target, \
            f"Single property fetch too slow: {query_time*1000:.2f}ms (target: {single_property_target*1000:.0f}ms)"
    
    def test_calculate_property_metrics_performance(
        self,
        db_session: Session,
        property_service: PropertyService,
        test_user: User
    ):
        """
        Test calculate_property_metrics performance.
        
        Target: < 100ms
        """
        # Create one property with many transactions
        properties = create_realistic_property_portfolio(
            db_session, property_service, test_user, num_properties=1
        )
        property_id = properties[0].id
        
        # Warm up
        property_service.calculate_property_metrics(property_id)
        
        # Measure query time
        start_time = time.perf_counter()
        
        metrics = property_service.calculate_property_metrics(property_id)
        
        end_time = time.perf_counter()
        query_time = end_time - start_time
        
        # Verify result
        assert metrics.property_id == property_id
        assert metrics.total_rental_income > Decimal("0")
        
        # Performance assertions
        print(f"\nProperty metrics calculation time: {query_time*1000:.2f}ms")
        
        assert query_time < TARGET_QUERY_TIME, \
            f"Metrics calculation too slow: {query_time*1000:.2f}ms (target: {TARGET_QUERY_TIME*1000:.0f}ms)"
    
    def test_pagination_performance_consistency(
        self,
        db_session: Session,
        property_service: PropertyService,
        test_user: User
    ):
        """
        Test that pagination doesn't significantly impact query performance.
        
        First page and subsequent pages should have similar performance.
        """
        # Create 60 properties
        properties = create_realistic_property_portfolio(
            db_session, property_service, test_user, num_properties=60
        )
        
        # Warm up
        property_service.list_properties_with_metrics(
            user_id=test_user.id, skip=0, limit=20
        )
        
        # Measure first page
        start_time = time.perf_counter()
        page1_props, page1_metrics, total = property_service.list_properties_with_metrics(
            user_id=test_user.id, skip=0, limit=20
        )
        page1_time = time.perf_counter() - start_time
        
        # Measure second page
        start_time = time.perf_counter()
        page2_props, page2_metrics, total = property_service.list_properties_with_metrics(
            user_id=test_user.id, skip=20, limit=20
        )
        page2_time = time.perf_counter() - start_time
        
        # Measure third page
        start_time = time.perf_counter()
        page3_props, page3_metrics, total = property_service.list_properties_with_metrics(
            user_id=test_user.id, skip=40, limit=20
        )
        page3_time = time.perf_counter() - start_time
        
        print(f"\nPagination performance:")
        print(f"  Page 1 (0-20): {page1_time*1000:.2f}ms")
        print(f"  Page 2 (20-40): {page2_time*1000:.2f}ms")
        print(f"  Page 3 (40-60): {page3_time*1000:.2f}ms")
        
        # All pages should be under target
        assert page1_time < TARGET_QUERY_TIME
        assert page2_time < TARGET_QUERY_TIME
        assert page3_time < TARGET_QUERY_TIME
        
        # Pages should have similar performance (within 50% variance)
        avg_time = (page1_time + page2_time + page3_time) / 3
        assert abs(page1_time - avg_time) < avg_time * 0.5
        assert abs(page2_time - avg_time) < avg_time * 0.5
        assert abs(page3_time - avg_time) < avg_time * 0.5
    
    def test_query_performance_with_filters(
        self,
        db_session: Session,
        property_service: PropertyService,
        test_user: User
    ):
        """
        Test query performance with various filters applied.
        
        Filters should not significantly degrade performance.
        """
        # Create mixed portfolio (active and archived)
        properties = create_realistic_property_portfolio(
            db_session, property_service, test_user, num_properties=30
        )
        
        # Archive some properties
        for i in range(0, 10, 3):
            property_service.archive_property(
                properties[i].id,
                test_user.id,
                date(2025, 12, 31)
            )
        
        # Warm up
        property_service.list_properties_with_metrics(
            user_id=test_user.id, include_archived=False
        )
        
        # Test with include_archived=False
        start_time = time.perf_counter()
        active_props, active_metrics, active_total = property_service.list_properties_with_metrics(
            user_id=test_user.id,
            include_archived=False,
            skip=0,
            limit=50
        )
        active_time = time.perf_counter() - start_time
        
        # Test with include_archived=True
        start_time = time.perf_counter()
        all_props, all_metrics, all_total = property_service.list_properties_with_metrics(
            user_id=test_user.id,
            include_archived=True,
            skip=0,
            limit=50
        )
        all_time = time.perf_counter() - start_time
        
        print(f"\nFilter performance:")
        print(f"  Active only: {active_time*1000:.2f}ms ({active_total} properties)")
        print(f"  All properties: {all_time*1000:.2f}ms ({all_total} properties)")
        
        # Both queries should be under target
        assert active_time < TARGET_QUERY_TIME
        assert all_time < TARGET_QUERY_TIME
        
        # Verify correct filtering
        assert active_total < all_total  # Some properties are archived


class TestPropertyQueryPerformanceRegression:
    """Regression tests to ensure performance doesn't degrade"""
    
    def test_no_n_plus_1_queries(
        self,
        db_session: Session,
        property_service: PropertyService,
        test_user: User
    ):
        """
        Verify that adding more properties doesn't cause linear query growth (N+1 problem).
        
        Query time should scale sub-linearly with property count.
        """
        # Test with 5 properties
        props_5 = create_realistic_property_portfolio(
            db_session, property_service, test_user, num_properties=5
        )
        
        start_time = time.perf_counter()
        property_service.list_properties_with_metrics(user_id=test_user.id, skip=0, limit=50)
        time_5 = time.perf_counter() - start_time
        
        # Add 15 more properties (total 20)
        props_20 = create_realistic_property_portfolio(
            db_session, property_service, test_user, num_properties=15
        )
        
        start_time = time.perf_counter()
        property_service.list_properties_with_metrics(user_id=test_user.id, skip=0, limit=50)
        time_20 = time.perf_counter() - start_time
        
        print(f"\nScalability test:")
        print(f"  5 properties: {time_5*1000:.2f}ms")
        print(f"  20 properties: {time_20*1000:.2f}ms")
        print(f"  Ratio: {time_20/time_5:.2f}x")
        
        # Time should not scale linearly (4x properties should not take 4x time)
        # Allow up to 2.5x time increase for 4x properties
        assert time_20 < time_5 * 2.5, \
            f"Query time scaling poorly: {time_20/time_5:.2f}x for 4x properties"
