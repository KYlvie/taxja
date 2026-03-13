"""
Tests for Prometheus Metrics

Verifies that Prometheus metrics are correctly defined and integrated
into property management services.
"""

import pytest
from decimal import Decimal
from datetime import date
from unittest.mock import Mock, patch
from prometheus_client import REGISTRY

from app.core.metrics import (
    property_created_counter,
    depreciation_generated_counter,
    backfill_duration_histogram
)


class TestPrometheusMetrics:
    """Test Prometheus metrics definitions"""
    
    def test_property_created_counter_exists(self):
        """Test that property_created_counter is registered"""
        # Check that the metric is in the registry
        # Note: Prometheus counters may appear without _total suffix in registry
        metric_names = [metric.name for metric in REGISTRY.collect()]
        assert 'property_created_total' in metric_names or 'property_created' in metric_names
    
    def test_depreciation_generated_counter_exists(self):
        """Test that depreciation_generated_counter is registered"""
        metric_names = [metric.name for metric in REGISTRY.collect()]
        assert 'depreciation_generated_total' in metric_names or 'depreciation_generated' in metric_names
    
    def test_backfill_duration_histogram_exists(self):
        """Test that backfill_duration_histogram is registered"""
        metric_names = [metric.name for metric in REGISTRY.collect()]
        assert 'backfill_duration_seconds' in metric_names
    
    def test_property_created_counter_labels(self):
        """Test that property_created_counter has correct labels"""
        # Increment counter with label
        property_created_counter.labels(user_id="test_user_123").inc()
        
        # Verify metric was incremented
        for metric in REGISTRY.collect():
            if metric.name in ['property_created_total', 'property_created']:
                for sample in metric.samples:
                    if sample.labels.get('user_id') == 'test_user_123':
                        assert sample.value >= 1
                        return
        
        pytest.fail("Metric with label not found")
    
    def test_depreciation_generated_counter_labels(self):
        """Test that depreciation_generated_counter has correct labels"""
        # Increment counter with labels
        depreciation_generated_counter.labels(
            user_id="test_user_456",
            year="2026"
        ).inc()
        
        # Verify metric was incremented
        for metric in REGISTRY.collect():
            if metric.name in ['depreciation_generated_total', 'depreciation_generated']:
                for sample in metric.samples:
                    if (sample.labels.get('user_id') == 'test_user_456' and
                        sample.labels.get('year') == '2026'):
                        assert sample.value >= 1
                        return
        
        pytest.fail("Metric with labels not found")
    
    def test_backfill_duration_histogram_observe(self):
        """Test that backfill_duration_histogram records observations"""
        # Record observation
        property_id = "test_property_789"
        backfill_duration_histogram.labels(property_id=property_id).observe(5.5)
        
        # Verify metric was recorded
        for metric in REGISTRY.collect():
            if metric.name == 'backfill_duration_seconds':
                for sample in metric.samples:
                    if (sample.labels.get('property_id') == property_id and
                        sample.name == 'backfill_duration_seconds_count'):
                        assert sample.value >= 1
                        return
        
        pytest.fail("Histogram observation not found")
    
    def test_backfill_duration_histogram_buckets(self):
        """Test that backfill_duration_histogram has correct buckets"""
        expected_buckets = [0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, float('inf')]
        
        # Record observation to ensure metric is in registry
        backfill_duration_histogram.labels(property_id="test_buckets").observe(1.0)
        
        # Check buckets
        for metric in REGISTRY.collect():
            if metric.name == 'backfill_duration_seconds':
                bucket_values = []
                for sample in metric.samples:
                    if (sample.name == 'backfill_duration_seconds_bucket' and
                        sample.labels.get('property_id') == 'test_buckets'):
                        bucket_values.append(float(sample.labels['le']))
                
                # Remove duplicates and sort
                bucket_values = sorted(set(bucket_values))
                
                # Verify buckets match expected
                assert bucket_values == expected_buckets
                return
        
        pytest.fail("Histogram buckets not found")


class TestMetricsEndpoint:
    """Test /metrics endpoint"""
    
    def test_metrics_endpoint_exists(self):
        """Test that /metrics endpoint is accessible"""
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        response = client.get("/metrics")
        
        assert response.status_code == 200
        assert response.headers['content-type'].startswith('text/plain')
    
    def test_metrics_endpoint_returns_prometheus_format(self):
        """Test that /metrics endpoint returns Prometheus text format"""
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        response = client.get("/metrics")
        
        content = response.text
        
        # Check for Prometheus format indicators
        assert '# HELP' in content or '# TYPE' in content
        
        # Check for our custom metrics
        assert 'property_created_total' in content
        assert 'depreciation_generated_total' in content
        assert 'backfill_duration_seconds' in content


class TestMetricsIntegration:
    """Test metrics integration with services"""
    
    def test_property_service_increments_counter(self, db, test_user):
        """Test that PropertyService increments property_created_counter"""
        from app.services.property_service import PropertyService
        from app.schemas.property import PropertyCreate
        
        # Get initial counter value
        initial_value = None
        for metric in REGISTRY.collect():
            if metric.name in ['property_created_total', 'property_created']:
                for sample in metric.samples:
                    if sample.labels.get('user_id') == str(test_user.id):
                        initial_value = sample.value
                        break
        
        if initial_value is None:
            initial_value = 0
        
        # Create property
        service = PropertyService(db)
        property_data = PropertyCreate(
            street="Test Street 123",
            city="Wien",
            postal_code="1010",
            purchase_date=date(2020, 6, 15),
            purchase_price=Decimal("350000.00"),
            building_value=Decimal("280000.00"),
            construction_year=1985,
            depreciation_rate=Decimal("0.02")
        )
        
        service.create_property(test_user.id, property_data)
        
        # Verify counter was incremented
        new_value = None
        for metric in REGISTRY.collect():
            if metric.name in ['property_created_total', 'property_created']:
                for sample in metric.samples:
                    if sample.labels.get('user_id') == str(test_user.id):
                        new_value = sample.value
                        break
        
        assert new_value is not None
        assert new_value > initial_value
    
    def test_annual_depreciation_service_increments_counter(self, db, test_property):
        """Test that AnnualDepreciationService increments depreciation_generated_counter"""
        from app.services.annual_depreciation_service import AnnualDepreciationService
        
        year = 2026
        user_id = str(test_property.user_id)
        
        # Get initial counter value
        initial_value = None
        for metric in REGISTRY.collect():
            if metric.name in ['depreciation_generated_total', 'depreciation_generated']:
                for sample in metric.samples:
                    if (sample.labels.get('user_id') == user_id and
                        sample.labels.get('year') == str(year)):
                        initial_value = sample.value
                        break
        
        if initial_value is None:
            initial_value = 0
        
        # Generate depreciation
        service = AnnualDepreciationService(db)
        result = service.generate_annual_depreciation(year, test_property.user_id)
        
        # Only check if transactions were created
        if result.transactions_created > 0:
            # Verify counter was incremented
            new_value = None
            for metric in REGISTRY.collect():
                if metric.name in ['depreciation_generated_total', 'depreciation_generated']:
                    for sample in metric.samples:
                        if (sample.labels.get('user_id') == user_id and
                            sample.labels.get('year') == str(year)):
                            new_value = sample.value
                            break
            
            assert new_value is not None
            assert new_value > initial_value
    
    def test_historical_depreciation_service_records_duration(self, db, test_property):
        """Test that HistoricalDepreciationService records backfill_duration_seconds"""
        from app.services.historical_depreciation_service import HistoricalDepreciationService
        
        property_id = str(test_property.id)
        
        # Get initial count
        initial_count = None
        for metric in REGISTRY.collect():
            if metric.name == 'backfill_duration_seconds':
                for sample in metric.samples:
                    if (sample.labels.get('property_id') == property_id and
                        sample.name == 'backfill_duration_seconds_count'):
                        initial_count = sample.value
                        break
        
        if initial_count is None:
            initial_count = 0
        
        # Perform backfill
        service = HistoricalDepreciationService(db)
        result = service.backfill_depreciation(
            test_property.id,
            test_property.user_id,
            confirm=True
        )
        
        # Only check if backfill was performed
        if result.years_backfilled > 0:
            # Verify histogram was updated
            new_count = None
            for metric in REGISTRY.collect():
                if metric.name == 'backfill_duration_seconds':
                    for sample in metric.samples:
                        if (sample.labels.get('property_id') == property_id and
                            sample.name == 'backfill_duration_seconds_count'):
                            new_count = sample.value
                            break
            
            assert new_count is not None
            assert new_count > initial_count


# Fixtures

@pytest.fixture
def test_user(db):
    """Create a test user"""
    from app.models.user import User
    
    user = User(
        email="test@example.com",
        hashed_password="hashed_password",
        full_name="Test User",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_property(db, test_user):
    """Create a test property"""
    from app.models.property import Property, PropertyType, PropertyStatus
    
    property = Property(
        user_id=test_user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        address="Test Street 123, 1010 Wien",
        street="Test Street 123",
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
