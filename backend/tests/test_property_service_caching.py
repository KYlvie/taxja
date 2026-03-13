"""
Unit tests for PropertyService caching functionality.

Tests cache behavior for property metrics including:
- Cache hit/miss scenarios
- Cache invalidation on property updates
- Cache invalidation on transaction linking/unlinking
- Redis connection failure handling
"""

import pytest
from decimal import Decimal
from datetime import date
from uuid import uuid4
from unittest.mock import Mock, patch, MagicMock
import json

from app.services.property_service import PropertyService
from app.models.property import Property, PropertyType, PropertyStatus
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.models.user import User
from app.schemas.property import PropertyMetrics, PropertyUpdate


class TestPropertyServiceCaching:
    """Test caching functionality in PropertyService"""
    
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
    
    @pytest.fixture
    def sample_metrics(self, sample_property):
        """Sample property metrics"""
        return PropertyMetrics(
            property_id=sample_property.id,
            accumulated_depreciation=Decimal("33600.00"),
            remaining_depreciable_value=Decimal("246400.00"),
            annual_depreciation=Decimal("5600.00"),
            total_rental_income=Decimal("18000.00"),
            total_expenses=Decimal("8500.00"),
            net_rental_income=Decimal("9500.00"),
            years_remaining=Decimal("44.0")
        )
    
    def test_cache_miss_calculates_metrics(self, property_service, mock_db, sample_property):
        """Test that cache miss triggers metric calculation"""
        # Setup
        property_service._redis_client.get.return_value = None
        mock_db.query.return_value.filter.return_value.first.return_value = sample_property
        mock_db.query.return_value.filter.return_value.scalar.return_value = Decimal("0")
        
        # Mock AfACalculator
        property_service.afa_calculator.get_accumulated_depreciation = Mock(return_value=Decimal("33600"))
        property_service.afa_calculator.calculate_annual_depreciation = Mock(return_value=Decimal("5600"))
        
        # Execute
        metrics = property_service.calculate_property_metrics(
            sample_property.id,
            sample_property.user_id
        )
        
        # Verify calculation was performed
        assert metrics.accumulated_depreciation == Decimal("33600")
        assert metrics.annual_depreciation == Decimal("5600")
        
        # Verify cache was set
        property_service._redis_client.setex.assert_called_once()
        call_args = property_service._redis_client.setex.call_args
        assert call_args[0][0] == f"property_metrics:{sample_property.id}"
        assert call_args[0][1] == 3600  # 1 hour TTL
    
    def test_cache_hit_returns_cached_metrics(self, property_service, sample_property, sample_metrics):
        """Test that cache hit returns cached data without calculation"""
        # Setup cached data
        cached_data = {
            "property_id": str(sample_property.id),
            "accumulated_depreciation": "33600.00",
            "remaining_depreciable_value": "246400.00",
            "annual_depreciation": "5600.00",
            "total_rental_income": "18000.00",
            "total_expenses": "8500.00",
            "net_rental_income": "9500.00",
            "years_remaining": "44.0"
        }
        property_service._redis_client.get.return_value = json.dumps(cached_data)
        
        # Execute
        metrics = property_service.calculate_property_metrics(
            sample_property.id,
            1  # user_id
        )
        
        # Verify cached data was returned
        assert metrics.property_id == sample_property.id
        assert metrics.accumulated_depreciation == Decimal("33600.00")
        assert metrics.annual_depreciation == Decimal("5600.00")
        
        # Verify no database queries were made
        property_service.db.query.assert_not_called()
    
    def test_cache_invalidation_on_property_update(self, property_service, mock_db, sample_property):
        """Test that updating property invalidates cache"""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = sample_property
        
        # Execute update
        updates = PropertyUpdate(building_value=Decimal("290000"))
        property_service.update_property(
            sample_property.id,
            sample_property.user_id,
            updates
        )
        
        # Verify cache was invalidated
        property_service._redis_client.delete.assert_called_once_with(
            f"property_metrics:{sample_property.id}"
        )
    
    def test_cache_invalidation_on_transaction_link(self, property_service, mock_db, sample_property):
        """Test that linking transaction invalidates cache"""
        # Setup
        transaction = Transaction(
            id=1,
            user_id=sample_property.user_id,
            type=TransactionType.INCOME,
            amount=Decimal("1000"),
            transaction_date=date.today(),
            income_category=IncomeCategory.RENTAL
        )
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            transaction,  # First call for transaction
            sample_property  # Second call for property
        ]
        
        # Execute
        property_service.link_transaction_to_property(
            transaction.id,
            sample_property.id,
            sample_property.user_id
        )
        
        # Verify cache was invalidated
        property_service._redis_client.delete.assert_called_once_with(
            f"property_metrics:{sample_property.id}"
        )
    
    def test_cache_invalidation_on_transaction_unlink(self, property_service, mock_db, sample_property):
        """Test that unlinking transaction invalidates cache"""
        # Setup
        transaction = Transaction(
            id=1,
            user_id=sample_property.user_id,
            property_id=sample_property.id,
            type=TransactionType.INCOME,
            amount=Decimal("1000"),
            transaction_date=date.today(),
            income_category=IncomeCategory.RENTAL
        )
        mock_db.query.return_value.filter.return_value.first.return_value = transaction
        
        # Execute
        property_service.unlink_transaction_from_property(
            transaction.id,
            sample_property.user_id
        )
        
        # Verify cache was invalidated
        property_service._redis_client.delete.assert_called_once_with(
            f"property_metrics:{sample_property.id}"
        )
    
    def test_redis_connection_failure_graceful_fallback(self, mock_db):
        """Test that Redis connection failure doesn't break functionality"""
        # Setup - Redis connection fails
        with patch('redis.from_url', side_effect=Exception("Redis connection failed")):
            service = PropertyService(mock_db)
            
            # Verify service still works without Redis
            assert service._redis_client is None
            
            # Cache operations should return False/None gracefully
            assert service._get_cached_metrics(uuid4()) is None
            assert service._set_cached_metrics(uuid4(), Mock()) is False
            assert service._invalidate_metrics_cache(uuid4()) is False
    
    def test_cache_get_error_returns_none(self, property_service, sample_property):
        """Test that cache get errors are handled gracefully"""
        # Setup - Redis get raises exception
        property_service._redis_client.get.side_effect = Exception("Redis error")
        
        # Execute
        result = property_service._get_cached_metrics(sample_property.id)
        
        # Verify None is returned
        assert result is None
    
    def test_cache_set_error_returns_false(self, property_service, sample_property, sample_metrics):
        """Test that cache set errors are handled gracefully"""
        # Setup - Redis setex raises exception
        property_service._redis_client.setex.side_effect = Exception("Redis error")
        
        # Execute
        result = property_service._set_cached_metrics(sample_property.id, sample_metrics)
        
        # Verify False is returned
        assert result is False
    
    def test_cache_invalidation_error_returns_false(self, property_service, sample_property):
        """Test that cache invalidation errors are handled gracefully"""
        # Setup - Redis delete raises exception
        property_service._redis_client.delete.side_effect = Exception("Redis error")
        
        # Execute
        result = property_service._invalidate_metrics_cache(sample_property.id)
        
        # Verify False is returned
        assert result is False
    
    def test_cache_only_for_current_year(self, property_service, mock_db, sample_property):
        """Test that caching only applies to current year metrics"""
        # Setup
        property_service._redis_client.get.return_value = None
        mock_db.query.return_value.filter.return_value.first.return_value = sample_property
        mock_db.query.return_value.filter.return_value.scalar.return_value = Decimal("0")
        
        property_service.afa_calculator.get_accumulated_depreciation = Mock(return_value=Decimal("33600"))
        property_service.afa_calculator.calculate_annual_depreciation = Mock(return_value=Decimal("5600"))
        
        # Execute for previous year
        metrics = property_service.calculate_property_metrics(
            sample_property.id,
            sample_property.user_id,
            year=2023
        )
        
        # Verify cache was NOT set for previous year
        property_service._redis_client.setex.assert_not_called()
        
        # Execute for current year
        metrics = property_service.calculate_property_metrics(
            sample_property.id,
            sample_property.user_id,
            year=date.today().year
        )
        
        # Verify cache WAS set for current year
        property_service._redis_client.setex.assert_called_once()
    
    def test_cache_key_format(self, property_service, sample_property):
        """Test that cache key follows correct format"""
        property_id = sample_property.id
        expected_key = f"property_metrics:{property_id}"
        
        # Test get
        property_service._get_cached_metrics(property_id)
        property_service._redis_client.get.assert_called_with(expected_key)
        
        # Test invalidate
        property_service._invalidate_metrics_cache(property_id)
        property_service._redis_client.delete.assert_called_with(expected_key)
    
    def test_decimal_serialization_in_cache(self, property_service, sample_property, sample_metrics):
        """Test that Decimal values are properly serialized to cache"""
        # Execute
        property_service._set_cached_metrics(sample_property.id, sample_metrics)
        
        # Get the cached data that was set
        call_args = property_service._redis_client.setex.call_args
        cached_json = call_args[0][2]
        cached_data = json.loads(cached_json)
        
        # Verify all Decimal values are strings
        assert isinstance(cached_data["accumulated_depreciation"], str)
        assert isinstance(cached_data["annual_depreciation"], str)
        assert cached_data["accumulated_depreciation"] == "33600.00"
        assert cached_data["annual_depreciation"] == "5600.00"
    
    def test_decimal_deserialization_from_cache(self, property_service, sample_property):
        """Test that cached string values are properly deserialized to Decimal"""
        # Setup cached data with string values
        cached_data = {
            "property_id": str(sample_property.id),
            "accumulated_depreciation": "33600.00",
            "remaining_depreciable_value": "246400.00",
            "annual_depreciation": "5600.00",
            "total_rental_income": "18000.00",
            "total_expenses": "8500.00",
            "net_rental_income": "9500.00",
            "years_remaining": "44.0"
        }
        property_service._redis_client.get.return_value = json.dumps(cached_data)
        
        # Execute
        metrics = property_service._get_cached_metrics(sample_property.id)
        
        # Verify all values are Decimal
        assert isinstance(metrics.accumulated_depreciation, Decimal)
        assert isinstance(metrics.annual_depreciation, Decimal)
        assert metrics.accumulated_depreciation == Decimal("33600.00")
        assert metrics.annual_depreciation == Decimal("5600.00")
