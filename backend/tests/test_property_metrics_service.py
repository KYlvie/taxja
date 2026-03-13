"""
Tests for Property Metrics Service

Tests the Prometheus metrics tracking for property management operations.
"""
import pytest
from prometheus_client import REGISTRY
from app.services.property_metrics_service import PropertyMetricsService


def get_metric_value(metric_name: str, labels: dict = None):
    """Helper to get current value of a metric."""
    for metric in REGISTRY.collect():
        if metric.name == metric_name:
            for sample in metric.samples:
                if labels is None or all(
                    sample.labels.get(k) == v for k, v in labels.items()
                ):
                    return sample.value
    return None


def test_record_property_created():
    """Test recording property creation metric."""
    initial_value = get_metric_value(
        'property_created_total',
        {'property_type': 'rental', 'user_type': 'landlord'}
    ) or 0
    
    PropertyMetricsService.record_property_created('rental', 'landlord')
    
    new_value = get_metric_value(
        'property_created_total',
        {'property_type': 'rental', 'user_type': 'landlord'}
    )
    
    assert new_value == initial_value + 1


def test_record_property_creation_error():
    """Test recording property creation error."""
    initial_value = get_metric_value(
        'property_creation_errors_total',
        {'error_type': 'validation'}
    ) or 0
    
    PropertyMetricsService.record_property_creation_error('validation')
    
    new_value = get_metric_value(
        'property_creation_errors_total',
        {'error_type': 'validation'}
    )
    
    assert new_value == initial_value + 1


def test_record_depreciation_generated():
    """Test recording depreciation generation metric."""
    initial_count = get_metric_value(
        'depreciation_generated_total',
        {'generation_type': 'annual'}
    ) or 0
    
    initial_amount = get_metric_value(
        'depreciation_amount_total',
        {'generation_type': 'annual'}
    ) or 0
    
    PropertyMetricsService.record_depreciation_generated(
        generation_type='annual',
        count=5,
        total_amount=28000.00
    )
    
    new_count = get_metric_value(
        'depreciation_generated_total',
        {'generation_type': 'annual'}
    )
    
    new_amount = get_metric_value(
        'depreciation_amount_total',
        {'generation_type': 'annual'}
    )
    
    assert new_count == initial_count + 5
    assert new_amount == initial_amount + 28000.00


def test_record_backfill_operation():
    """Test recording backfill operation metrics."""
    PropertyMetricsService.record_backfill_operation(
        duration_seconds=2.5,
        years_processed=5
    )
    
    # Check that histogram was updated (we can't easily verify exact values)
    duration_metric = get_metric_value('backfill_duration_seconds_count')
    years_metric = get_metric_value('backfill_years_processed_count')
    
    assert duration_metric is not None
    assert years_metric is not None


def test_record_backfill_error():
    """Test recording backfill error."""
    initial_value = get_metric_value(
        'backfill_errors_total',
        {'error_type': 'database'}
    ) or 0
    
    PropertyMetricsService.record_backfill_error('database')
    
    new_value = get_metric_value(
        'backfill_errors_total',
        {'error_type': 'database'}
    )
    
    assert new_value == initial_value + 1


def test_record_property_updated():
    """Test recording property update metric."""
    initial_value = get_metric_value(
        'property_updated_total',
        {'update_type': 'details'}
    ) or 0
    
    PropertyMetricsService.record_property_updated('details')
    
    new_value = get_metric_value(
        'property_updated_total',
        {'update_type': 'details'}
    )
    
    assert new_value == initial_value + 1


def test_record_property_deleted():
    """Test recording property deletion metric."""
    initial_value = get_metric_value('property_deleted_total') or 0
    
    PropertyMetricsService.record_property_deleted()
    
    new_value = get_metric_value('property_deleted_total')
    
    assert new_value == initial_value + 1


def test_record_property_archived():
    """Test recording property archival metric."""
    initial_value = get_metric_value('property_archived_total') or 0
    
    PropertyMetricsService.record_property_archived()
    
    new_value = get_metric_value('property_archived_total')
    
    assert new_value == initial_value + 1


def test_record_transaction_linked():
    """Test recording transaction linking metric."""
    initial_value = get_metric_value(
        'transaction_linked_total',
        {'transaction_type': 'income'}
    ) or 0
    
    PropertyMetricsService.record_transaction_linked('income')
    
    new_value = get_metric_value(
        'transaction_linked_total',
        {'transaction_type': 'income'}
    )
    
    assert new_value == initial_value + 1


def test_record_transaction_unlinked():
    """Test recording transaction unlinking metric."""
    initial_value = get_metric_value('transaction_unlinked_total') or 0
    
    PropertyMetricsService.record_transaction_unlinked()
    
    new_value = get_metric_value('transaction_unlinked_total')
    
    assert new_value == initial_value + 1


def test_record_property_query():
    """Test recording property query metric."""
    PropertyMetricsService.record_property_query('list', 0.05)
    
    # Check that histogram was updated
    metric_value = get_metric_value('property_query_duration_seconds_count')
    assert metric_value is not None


def test_record_cache_hit():
    """Test recording cache hit metric."""
    initial_value = get_metric_value(
        'property_cache_hits_total',
        {'cache_type': 'metrics'}
    ) or 0
    
    PropertyMetricsService.record_cache_hit('metrics')
    
    new_value = get_metric_value(
        'property_cache_hits_total',
        {'cache_type': 'metrics'}
    )
    
    assert new_value == initial_value + 1


def test_record_cache_miss():
    """Test recording cache miss metric."""
    initial_value = get_metric_value(
        'property_cache_misses_total',
        {'cache_type': 'metrics'}
    ) or 0
    
    PropertyMetricsService.record_cache_miss('metrics')
    
    new_value = get_metric_value(
        'property_cache_misses_total',
        {'cache_type': 'metrics'}
    )
    
    assert new_value == initial_value + 1


def test_update_active_properties_gauge():
    """Test updating active properties gauge."""
    PropertyMetricsService.update_active_properties_gauge('rental', 42)
    
    value = get_metric_value(
        'active_properties_total',
        {'property_type': 'rental'}
    )
    
    assert value == 42


def test_record_validation_error():
    """Test recording validation error metric."""
    initial_value = get_metric_value(
        'property_validation_errors_total',
        {'validation_type': 'purchase_price'}
    ) or 0
    
    PropertyMetricsService.record_validation_error('purchase_price')
    
    new_value = get_metric_value(
        'property_validation_errors_total',
        {'validation_type': 'purchase_price'}
    )
    
    assert new_value == initial_value + 1


def test_multiple_property_types():
    """Test metrics for different property types."""
    PropertyMetricsService.record_property_created('rental', 'landlord')
    PropertyMetricsService.record_property_created('owner_occupied', 'homeowner')
    PropertyMetricsService.record_property_created('mixed_use', 'landlord')
    
    rental_count = get_metric_value(
        'property_created_total',
        {'property_type': 'rental', 'user_type': 'landlord'}
    )
    
    owner_count = get_metric_value(
        'property_created_total',
        {'property_type': 'owner_occupied', 'user_type': 'homeowner'}
    )
    
    mixed_count = get_metric_value(
        'property_created_total',
        {'property_type': 'mixed_use', 'user_type': 'landlord'}
    )
    
    assert rental_count >= 1
    assert owner_count >= 1
    assert mixed_count >= 1


def test_depreciation_generation_types():
    """Test metrics for different depreciation generation types."""
    PropertyMetricsService.record_depreciation_generated('annual', 1, 5600.00)
    PropertyMetricsService.record_depreciation_generated('historical_backfill', 5, 28000.00)
    PropertyMetricsService.record_depreciation_generated('manual', 1, 5600.00)
    
    annual_count = get_metric_value(
        'depreciation_generated_total',
        {'generation_type': 'annual'}
    )
    
    backfill_count = get_metric_value(
        'depreciation_generated_total',
        {'generation_type': 'historical_backfill'}
    )
    
    manual_count = get_metric_value(
        'depreciation_generated_total',
        {'generation_type': 'manual'}
    )
    
    assert annual_count >= 1
    assert backfill_count >= 5
    assert manual_count >= 1
