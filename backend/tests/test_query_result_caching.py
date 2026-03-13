"""
Unit tests for query result caching (Task C.2.4).

Tests cache behavior for:
- Portfolio metrics caching
- Depreciation schedule caching
- Property list caching
- Cache invalidation strategies
"""

import pytest
from decimal import Decimal
from datetime import date
from uuid import uuid4
from unittest.mock import Mock, patch, MagicMock
import json

from app.services.property_service import PropertyService
from app.services.property_report_service import PropertyReportService
from app.services.dashboard_service import DashboardService
from app.models.property import Property, PropertyType, PropertyStatus
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.models.user import User
from app.schemas.property import PropertyCreate, PropertyUpdate


class TestPortfolioMetricsCaching:
    """Test portfolio metrics caching in PropertyService and DashboardService"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock()
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client"""
        redis_mock = Mock()
        redis_mock.ping.return_value = True
        redis_mock.get.return_value = None
        redis_mock.setex.return_value = True
        redis_mock.delete.return_value = 1
        redis_mock.keys.return_value = []
        return redis_mock
    
    @pytest.fixture
    def property_service(self, mock_db, mock_redis):
        """Create PropertyService with mocked Redis"""
        with patch('redis.from_url', return_value=mock_redis):
            service = PropertyService(mock_db)
            return service
    
    @pytest.fixture
    def dashboard_service(self, mock_db, mock_redis):
        """Create DashboardService with mocked Redis"""
        with patch('redis.from_url', return_value=mock_redis):
            service = DashboardService(mock_db)
            return service
    
    def test_portfolio_metrics_cache_miss(self, property_service):
        """Test that cache miss returns None"""
        property_service._redis_client.get.return_value = None
        
        result = property_service._get_cached_portfolio_metrics(1, 2026)
        
        assert result is None
        property_service._redis_client.get.assert_called_once_with("portfolio_metrics:1:2026")
    
    def test_portfolio_metrics_cache_hit(self, property_service):
        """Test that cache hit returns cached data"""
        cached_data = {
            "total_properties": 3,
            "total_building_value": "840000.00",
            "total_annual_depreciation": "16800.00",
            "total_rental_income": "54000.00",
            "total_expenses": "25500.00",
            "net_rental_income": "28500.00"
        }
        property_service._redis_client.get.return_value = json.dumps(cached_data)
        
        result = property_service._get_cached_portfolio_metrics(1, 2026)
        
        assert result is not None
        assert result["total_properties"] == 3
        assert result["total_building_value"] == Decimal("840000.00")
        assert result["total_annual_depreciation"] == Decimal("16800.00")
        assert result["total_rental_income"] == Decimal("54000.00")
    
    def test_portfolio_metrics_cache_set(self, property_service):
        """Test that portfolio metrics are cached correctly"""
        metrics = {
            "total_properties": 3,
            "total_building_value": Decimal("840000.00"),
            "total_annual_depreciation": Decimal("16800.00"),
            "total_rental_income": Decimal("54000.00"),
            "total_expenses": Decimal("25500.00"),
            "net_rental_income": Decimal("28500.00")
        }
        
        result = property_service._set_cached_portfolio_metrics(1, 2026, metrics)
        
        assert result is True
        property_service._redis_client.setex.assert_called_once()
        call_args = property_service._redis_client.setex.call_args
        assert call_args[0][0] == "portfolio_metrics:1:2026"
        assert call_args[0][1] == 3600  # 1 hour TTL
    
    def test_portfolio_cache_invalidation(self, property_service):
        """Test that portfolio cache is invalidated for all years"""
        property_service._redis_client.keys.return_value = [
            "portfolio_metrics:1:2024",
            "portfolio_metrics:1:2025",
            "portfolio_metrics:1:2026"
        ]
        
        result = property_service._invalidate_portfolio_cache(1)
        
        assert result is True
        property_service._redis_client.keys.assert_called_once_with("portfolio_metrics:1:*")
        property_service._redis_client.delete.assert_called_once()
    
    def test_dashboard_portfolio_metrics_uses_cache(self, dashboard_service, mock_db):
        """Test that DashboardService uses cached portfolio metrics"""
        cached_data = {
            "has_properties": True,
            "active_properties_count": 3,
            "total_rental_income": Decimal("54000.00"),
            "total_property_expenses": Decimal("25500.00"),
            "net_rental_income": Decimal("28500.00"),
            "total_building_value": Decimal("840000.00"),
            "total_annual_depreciation": Decimal("16800.00")
        }
        dashboard_service._redis_client.get.return_value = json.dumps({
            "has_properties": True,
            "active_properties_count": 3,
            "total_rental_income": "54000.00",
            "total_property_expenses": "25500.00",
            "net_rental_income": "28500.00",
            "total_building_value": "840000.00",
            "total_annual_depreciation": "16800.00"
        })
        
        result = dashboard_service.get_property_metrics(1, 2026)
        
        assert result["active_properties_count"] == 3
        assert result["total_rental_income"] == Decimal("54000.00")
        # Verify no database queries were made
        mock_db.query.assert_not_called()
    
    def test_portfolio_cache_invalidated_on_property_create(self, property_service, mock_db):
        """Test that creating property invalidates portfolio cache"""
        user = User(id=1, email="test@example.com")
        mock_db.query.return_value.filter.return_value.first.return_value = user
        
        property_data = PropertyCreate(
            street="Teststraße 1",
            city="Wien",
            postal_code="1010",
            purchase_date=date(2020, 1, 1),
            purchase_price=Decimal("350000"),
            building_value=Decimal("280000"),
            depreciation_rate=Decimal("0.02")
        )
        
        property_service.create_property(1, property_data)
        
        # Verify portfolio cache was invalidated
        property_service._redis_client.keys.assert_called()
        assert any("portfolio_metrics:1:*" in str(call) for call in property_service._redis_client.keys.call_args_list)


class TestDepreciationScheduleCaching:
    """Test depreciation schedule caching in PropertyReportService"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock()
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client"""
        redis_mock = Mock()
        redis_mock.ping.return_value = True
        redis_mock.get.return_value = None
        redis_mock.setex.return_value = True
        redis_mock.delete.return_value = 1
        return redis_mock
    
    @pytest.fixture
    def report_service(self, mock_db, mock_redis):
        """Create PropertyReportService with mocked Redis"""
        with patch('redis.from_url', return_value=mock_redis):
            service = PropertyReportService(mock_db)
            return service
    
    @pytest.fixture
    def sample_property(self):
        """Sample property for testing"""
        return Property(
            id=uuid4(),
            user_id=1,
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100"),
            address="Hauptstraße 123, 1010 Wien",
            street="Hauptstraße 123",
            city="Wien",
            postal_code="1010",
            purchase_date=date(2020, 1, 1),
            purchase_price=Decimal("350000"),
            building_value=Decimal("280000"),
            land_value=Decimal("70000"),
            construction_year=1985,
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
    
    def test_depreciation_schedule_cache_miss(self, report_service):
        """Test that cache miss returns None"""
        property_id = str(uuid4())
        report_service._redis_client.get.return_value = None
        
        result = report_service._get_cached_depreciation_schedule(property_id)
        
        assert result is None
        report_service._redis_client.get.assert_called_once_with(f"depreciation_schedule:{property_id}")
    
    def test_depreciation_schedule_cache_hit(self, report_service):
        """Test that cache hit returns cached schedule"""
        property_id = str(uuid4())
        cached_schedule = {
            "property": {
                "id": property_id,
                "address": "Hauptstraße 123, 1010 Wien",
                "purchase_date": "2020-01-01",
                "building_value": 280000.0,
                "depreciation_rate": 0.02
            },
            "schedule": [
                {"year": 2020, "annual_depreciation": 5600.0, "accumulated_depreciation": 5600.0, "remaining_value": 274400.0}
            ],
            "summary": {
                "total_years": 1,
                "total_depreciation": 5600.0,
                "remaining_value": 274400.0
            }
        }
        report_service._redis_client.get.return_value = json.dumps(cached_schedule)
        
        result = report_service._get_cached_depreciation_schedule(property_id)
        
        assert result is not None
        assert result["property"]["id"] == property_id
        assert len(result["schedule"]) == 1
    
    def test_depreciation_schedule_cache_set(self, report_service):
        """Test that depreciation schedule is cached with 24 hour TTL"""
        property_id = str(uuid4())
        schedule = {
            "property": {"id": property_id},
            "schedule": [],
            "summary": {}
        }
        
        result = report_service._set_cached_depreciation_schedule(property_id, schedule)
        
        assert result is True
        report_service._redis_client.setex.assert_called_once()
        call_args = report_service._redis_client.setex.call_args
        assert call_args[0][0] == f"depreciation_schedule:{property_id}"
        assert call_args[0][1] == 86400  # 24 hours TTL
    
    def test_generate_depreciation_schedule_uses_cache(self, report_service, sample_property):
        """Test that generate_depreciation_schedule uses cache"""
        property_id = str(sample_property.id)
        cached_schedule = {
            "property": {
                "id": property_id,
                "address": sample_property.address,
                "purchase_date": sample_property.purchase_date.isoformat(),
                "building_value": float(sample_property.building_value),
                "depreciation_rate": float(sample_property.depreciation_rate)
            },
            "schedule": [],
            "summary": {}
        }
        report_service._redis_client.get.return_value = json.dumps(cached_schedule)
        
        result = report_service.generate_depreciation_schedule(property_id)
        
        assert result["property"]["id"] == property_id
        # Verify no database queries were made
        report_service.db.query.assert_not_called()
    
    def test_depreciation_schedule_cache_invalidated_on_property_update(self, mock_db, mock_redis):
        """Test that updating property invalidates depreciation schedule cache"""
        with patch('redis.from_url', return_value=mock_redis):
            property_service = PropertyService(mock_db)
            
            property_id = uuid4()
            sample_property = Property(
                id=property_id,
                user_id=1,
                property_type=PropertyType.RENTAL,
                rental_percentage=Decimal("100"),
                address="Hauptstraße 123, 1010 Wien",
                street="Hauptstraße 123",
                city="Wien",
                postal_code="1010",
                purchase_date=date(2020, 1, 1),
                purchase_price=Decimal("350000"),
                building_value=Decimal("280000"),
                land_value=Decimal("70000"),
                construction_year=1985,
                depreciation_rate=Decimal("0.02"),
                status=PropertyStatus.ACTIVE
            )
            mock_db.query.return_value.filter.return_value.first.return_value = sample_property
            
            updates = PropertyUpdate(building_value=Decimal("290000"))
            property_service.update_property(property_id, 1, updates)
            
            # Verify depreciation schedule cache was invalidated
            mock_redis.delete.assert_called()
            delete_calls = [str(call) for call in mock_redis.delete.call_args_list]
            assert any(f"depreciation_schedule:{property_id}" in call for call in delete_calls)


class TestPropertyListCaching:
    """Test property list caching in PropertyService"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock()
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client"""
        redis_mock = Mock()
        redis_mock.ping.return_value = True
        redis_mock.get.return_value = None
        redis_mock.setex.return_value = True
        redis_mock.delete.return_value = 1
        redis_mock.keys.return_value = []
        return redis_mock
    
    @pytest.fixture
    def property_service(self, mock_db, mock_redis):
        """Create PropertyService with mocked Redis"""
        with patch('redis.from_url', return_value=mock_redis):
            service = PropertyService(mock_db)
            return service
    
    def test_property_list_cache_miss(self, property_service):
        """Test that cache miss returns None"""
        result = property_service._get_cached_property_list(1, False, 0, 50, 2026)
        
        assert result is None
        property_service._redis_client.get.assert_called_once_with("property_list:1:False:0:50:2026")
    
    def test_property_list_cache_hit(self, property_service):
        """Test that cache hit returns cached data"""
        cached_data = [[], [], 0]  # properties, metrics, total_count
        property_service._redis_client.get.return_value = json.dumps(cached_data)
        
        result = property_service._get_cached_property_list(1, False, 0, 50, 2026)
        
        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 3
    
    def test_property_list_cache_set(self, property_service):
        """Test that property list is cached with 5 minute TTL"""
        data = ([], [], 0)
        
        result = property_service._set_cached_property_list(1, False, 0, 50, 2026, data)
        
        assert result is True
        property_service._redis_client.setex.assert_called_once()
        call_args = property_service._redis_client.setex.call_args
        assert call_args[0][0] == "property_list:1:False:0:50:2026"
        assert call_args[0][1] == 300  # 5 minutes TTL
    
    def test_property_list_cache_invalidation(self, property_service):
        """Test that property list cache is invalidated for all variations"""
        property_service._redis_client.keys.return_value = [
            "property_list:1:False:0:50:2026",
            "property_list:1:True:0:50:2026",
            "property_list:1:False:0:100:2026"
        ]
        
        result = property_service._invalidate_property_list_cache(1)
        
        assert result is True
        property_service._redis_client.keys.assert_called_once_with("property_list:1:*")
        property_service._redis_client.delete.assert_called_once()
    
    def test_property_list_cache_invalidated_on_create(self, property_service, mock_db):
        """Test that creating property invalidates list cache"""
        user = User(id=1, email="test@example.com")
        mock_db.query.return_value.filter.return_value.first.return_value = user
        
        property_data = PropertyCreate(
            street="Teststraße 1",
            city="Wien",
            postal_code="1010",
            purchase_date=date(2020, 1, 1),
            purchase_price=Decimal("350000"),
            building_value=Decimal("280000"),
            depreciation_rate=Decimal("0.02")
        )
        
        property_service.create_property(1, property_data)
        
        # Verify list cache was invalidated
        property_service._redis_client.keys.assert_called()
        assert any("property_list:1:*" in str(call) for call in property_service._redis_client.keys.call_args_list)


class TestCacheInvalidationStrategy:
    """Test comprehensive cache invalidation strategy"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock()
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client"""
        redis_mock = Mock()
        redis_mock.ping.return_value = True
        redis_mock.get.return_value = None
        redis_mock.setex.return_value = True
        redis_mock.delete.return_value = 1
        redis_mock.keys.return_value = []
        return redis_mock
    
    @pytest.fixture
    def property_service(self, mock_db, mock_redis):
        """Create PropertyService with mocked Redis"""
        with patch('redis.from_url', return_value=mock_redis):
            service = PropertyService(mock_db)
            return service
    
    @pytest.fixture
    def sample_property(self):
        """Sample property for testing"""
        return Property(
            id=uuid4(),
            user_id=1,
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100"),
            address="Hauptstraße 123, 1010 Wien",
            street="Hauptstraße 123",
            city="Wien",
            postal_code="1010",
            purchase_date=date(2020, 1, 1),
            purchase_price=Decimal("350000"),
            building_value=Decimal("280000"),
            land_value=Decimal("70000"),
            construction_year=1985,
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
    
    def test_update_property_invalidates_all_caches(self, property_service, mock_db, sample_property):
        """Test that updating property invalidates all three cache types"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_property
        
        updates = PropertyUpdate(building_value=Decimal("290000"))
        property_service.update_property(sample_property.id, 1, updates)
        
        # Verify all cache types were invalidated
        delete_calls = [str(call) for call in property_service._redis_client.delete.call_args_list]
        keys_calls = [str(call) for call in property_service._redis_client.keys.call_args_list]
        
        # Check for property metrics cache invalidation
        assert any(f"property_metrics:{sample_property.id}" in call for call in delete_calls)
        
        # Check for depreciation schedule cache invalidation
        assert any(f"depreciation_schedule:{sample_property.id}" in call for call in delete_calls)
        
        # Check for portfolio and list cache invalidation
        assert any("portfolio_metrics:1:*" in call for call in keys_calls)
        assert any("property_list:1:*" in call for call in keys_calls)
    
    def test_archive_property_invalidates_portfolio_and_list(self, property_service, mock_db, sample_property):
        """Test that archiving property invalidates portfolio and list caches"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_property
        
        property_service.archive_property(sample_property.id, 1, date(2025, 12, 31))
        
        # Verify portfolio and list caches were invalidated
        keys_calls = [str(call) for call in property_service._redis_client.keys.call_args_list]
        assert any("portfolio_metrics:1:*" in call for call in keys_calls)
        assert any("property_list:1:*" in call for call in keys_calls)
    
    def test_delete_property_invalidates_portfolio_and_list(self, property_service, mock_db, sample_property):
        """Test that deleting property invalidates portfolio and list caches"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_property
        mock_db.query.return_value.filter.return_value.scalar.return_value = 0  # No transactions
        
        property_service.delete_property(sample_property.id, 1)
        
        # Verify portfolio and list caches were invalidated
        keys_calls = [str(call) for call in property_service._redis_client.keys.call_args_list]
        assert any("portfolio_metrics:1:*" in call for call in keys_calls)
        assert any("property_list:1:*" in call for call in keys_calls)
    
    def test_link_transaction_invalidates_metrics_and_portfolio(self, property_service, mock_db, sample_property):
        """Test that linking transaction invalidates metrics and portfolio caches"""
        transaction = Transaction(
            id=1,
            user_id=1,
            type=TransactionType.INCOME,
            amount=Decimal("1000"),
            transaction_date=date.today(),
            income_category=IncomeCategory.RENTAL
        )
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            transaction,
            sample_property
        ]
        
        property_service.link_transaction_to_property(1, sample_property.id, 1)
        
        # Verify metrics and portfolio caches were invalidated
        delete_calls = [str(call) for call in property_service._redis_client.delete.call_args_list]
        keys_calls = [str(call) for call in property_service._redis_client.keys.call_args_list]
        
        assert any(f"property_metrics:{sample_property.id}" in call for call in delete_calls)
        assert any("portfolio_metrics:1:*" in call for call in keys_calls)


class TestCacheErrorHandling:
    """Test graceful error handling for cache operations"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock()
    
    def test_redis_connection_failure_graceful(self, mock_db):
        """Test that Redis connection failure doesn't break functionality"""
        with patch('redis.from_url', side_effect=Exception("Redis connection failed")):
            service = PropertyService(mock_db)
            
            assert service._redis_client is None
            
            # Cache operations should return False/None gracefully
            assert service._get_cached_portfolio_metrics(1, 2026) is None
            assert service._set_cached_portfolio_metrics(1, 2026, {}) is False
            assert service._invalidate_portfolio_cache(1) is False
    
    def test_cache_get_error_returns_none(self, mock_db):
        """Test that cache get errors are handled gracefully"""
        mock_redis = Mock()
        mock_redis.ping.return_value = True
        mock_redis.get.side_effect = Exception("Redis error")
        
        with patch('redis.from_url', return_value=mock_redis):
            service = PropertyService(mock_db)
            
            result = service._get_cached_portfolio_metrics(1, 2026)
            assert result is None
    
    def test_cache_set_error_returns_false(self, mock_db):
        """Test that cache set errors are handled gracefully"""
        mock_redis = Mock()
        mock_redis.ping.return_value = True
        mock_redis.setex.side_effect = Exception("Redis error")
        
        with patch('redis.from_url', return_value=mock_redis):
            service = PropertyService(mock_db)
            
            result = service._set_cached_portfolio_metrics(1, 2026, {
                "total_properties": 0,
                "total_building_value": Decimal("0"),
                "total_annual_depreciation": Decimal("0"),
                "total_rental_income": Decimal("0"),
                "total_expenses": Decimal("0"),
                "net_rental_income": Decimal("0")
            })
            assert result is False
