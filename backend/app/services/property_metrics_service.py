"""
Property Management Metrics Service

Provides Prometheus metrics for monitoring property management operations.
Tracks property creation, depreciation generation, backfill operations, and errors.
"""
import logging
from typing import Optional
from prometheus_client import Counter, Histogram, Gauge, REGISTRY
from datetime import datetime


logger = logging.getLogger(__name__)


def _expected_labelnames(args, kwargs) -> tuple[str, ...]:
    if "labelnames" in kwargs:
        return tuple(kwargs["labelnames"])
    if args and isinstance(args[0], (list, tuple)):
        return tuple(args[0])
    return ()


def _collector_matches(existing, metric_cls, expected_labelnames: tuple[str, ...]) -> bool:
    return (
        existing is not None
        and isinstance(existing, metric_cls)
        and tuple(getattr(existing, "_labelnames", ())) == expected_labelnames
    )


def _unregister_conflicting_collector(existing) -> None:
    if existing is None:
        return
    try:
        REGISTRY.unregister(existing)
    except KeyError:
        pass


def _get_or_create_metric(metric_cls, name: str, documentation: str, *args, **kwargs):
    """Reuse an existing Prometheus collector when the module is imported repeatedly."""
    registry_map = getattr(REGISTRY, "_names_to_collectors", {})
    lookup_names = [name]
    if name.endswith("_total"):
        lookup_names.append(name[:-6])
    expected_labelnames = _expected_labelnames(args, kwargs)
    conflicting = None

    for lookup_name in lookup_names:
        existing = registry_map.get(lookup_name)
        if _collector_matches(existing, metric_cls, expected_labelnames):
            return existing
        if existing is not None:
            conflicting = existing

    try:
        _unregister_conflicting_collector(conflicting)
        return metric_cls(name, documentation, *args, **kwargs)
    except ValueError:
        registry_map = getattr(REGISTRY, "_names_to_collectors", {})
        for lookup_name in lookup_names:
            existing = registry_map.get(lookup_name)
            if _collector_matches(existing, metric_cls, expected_labelnames):
                return existing
            if existing is not None:
                conflicting = existing
        _unregister_conflicting_collector(conflicting)
        return metric_cls(name, documentation, *args, **kwargs)

# Property creation metrics
property_created_total = _get_or_create_metric(
    Counter,
    'property_created_total',
    'Total number of properties created',
    ['property_type', 'user_type']
)

property_creation_errors_total = _get_or_create_metric(
    Counter,
    'property_creation_errors_total',
    'Total number of property creation errors',
    ['error_type']
)

# Depreciation generation metrics
depreciation_generated_total = _get_or_create_metric(
    Counter,
    'depreciation_generated_total',
    'Total number of depreciation transactions generated',
    ['generation_type']
)

depreciation_generation_errors_total = _get_or_create_metric(
    Counter,
    'depreciation_generation_errors_total',
    'Total number of depreciation generation errors',
    ['error_type']
)

depreciation_amount_total = _get_or_create_metric(
    Counter,
    'depreciation_amount_total',
    'Total depreciation amount generated in EUR',
    ['generation_type']
)

# Backfill operation metrics
backfill_duration_seconds = _get_or_create_metric(
    Histogram,
    'backfill_duration_seconds',
    'Duration of historical depreciation backfill operations',
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0]
)

backfill_years_processed = _get_or_create_metric(
    Histogram,
    'backfill_years_processed',
    'Number of years processed in backfill operations',
    buckets=[1, 2, 3, 5, 10, 15, 20, 30]
)

backfill_errors_total = _get_or_create_metric(
    Counter,
    'backfill_errors_total',
    'Total number of backfill operation errors',
    ['error_type']
)

# Property operation metrics
property_updated_total = _get_or_create_metric(
    Counter,
    'property_updated_total',
    'Total number of property updates',
    ['update_type']
)

property_deleted_total = _get_or_create_metric(
    Counter,
    'property_deleted_total',
    'Total number of properties deleted'
)

property_archived_total = _get_or_create_metric(
    Counter,
    'property_archived_total',
    'Total number of properties archived'
)

# Transaction linking metrics
transaction_linked_total = _get_or_create_metric(
    Counter,
    'transaction_linked_total',
    'Total number of transactions linked to properties',
    ['transaction_type']
)

transaction_unlinked_total = _get_or_create_metric(
    Counter,
    'transaction_unlinked_total',
    'Total number of transactions unlinked from properties'
)

# Property query performance metrics
property_query_duration_seconds = _get_or_create_metric(
    Histogram,
    'property_query_duration_seconds',
    'Duration of property query operations',
    ['query_type'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5]
)

# Cache metrics
property_cache_hits_total = _get_or_create_metric(
    Counter,
    'property_cache_hits_total',
    'Total number of property cache hits',
    ['cache_type']
)

property_cache_misses_total = _get_or_create_metric(
    Counter,
    'property_cache_misses_total',
    'Total number of property cache misses',
    ['cache_type']
)

# Active properties gauge
active_properties_gauge = _get_or_create_metric(
    Gauge,
    'active_properties_total',
    'Current number of active properties',
    ['property_type']
)

# Validation error metrics
property_validation_errors_total = _get_or_create_metric(
    Counter,
    'property_validation_errors_total',
    'Total number of property validation errors',
    ['validation_type']
)


class PropertyMetricsService:
    """
    Service for tracking property management metrics.
    
    Provides methods to record various property operations and their outcomes
    for monitoring and alerting purposes.
    """
    
    @staticmethod
    def record_property_created(property_type: str, user_type: str = "landlord"):
        """Record a property creation event."""
        try:
            property_created_total.labels(
                property_type=property_type,
                user_type=user_type
            ).inc()
            logger.info(
                "Property created metric recorded",
                extra={
                    "property_type": property_type,
                    "user_type": user_type
                }
            )
        except Exception as e:
            logger.error(f"Failed to record property creation metric: {e}")
    
    @staticmethod
    def record_property_creation_error(error_type: str):
        """Record a property creation error."""
        try:
            property_creation_errors_total.labels(error_type=error_type).inc()
            logger.warning(
                "Property creation error recorded",
                extra={"error_type": error_type}
            )
        except Exception as e:
            logger.error(f"Failed to record property creation error metric: {e}")
    
    @staticmethod
    def record_depreciation_generated(
        generation_type: str,
        count: int = 1,
        total_amount: Optional[float] = None
    ):
        """
        Record depreciation generation event.
        
        Args:
            generation_type: Type of generation ('annual', 'historical_backfill', 'manual')
            count: Number of depreciation transactions generated
            total_amount: Total depreciation amount in EUR
        """
        try:
            depreciation_generated_total.labels(
                generation_type=generation_type
            ).inc(count)
            
            if total_amount is not None:
                depreciation_amount_total.labels(
                    generation_type=generation_type
                ).inc(total_amount)
            
            logger.info(
                "Depreciation generation metric recorded",
                extra={
                    "generation_type": generation_type,
                    "count": count,
                    "total_amount": total_amount
                }
            )
        except Exception as e:
            logger.error(f"Failed to record depreciation generation metric: {e}")
    
    @staticmethod
    def record_depreciation_generation_error(error_type: str):
        """Record a depreciation generation error."""
        try:
            depreciation_generation_errors_total.labels(error_type=error_type).inc()
            logger.warning(
                "Depreciation generation error recorded",
                extra={"error_type": error_type}
            )
        except Exception as e:
            logger.error(f"Failed to record depreciation generation error metric: {e}")
    
    @staticmethod
    def record_backfill_operation(duration_seconds: float, years_processed: int):
        """
        Record a backfill operation.
        
        Args:
            duration_seconds: Duration of the backfill operation
            years_processed: Number of years processed
        """
        try:
            backfill_duration_seconds.observe(duration_seconds)
            backfill_years_processed.observe(years_processed)
            
            logger.info(
                "Backfill operation metric recorded",
                extra={
                    "duration_seconds": duration_seconds,
                    "years_processed": years_processed
                }
            )
        except Exception as e:
            logger.error(f"Failed to record backfill operation metric: {e}")
    
    @staticmethod
    def record_backfill_error(error_type: str):
        """Record a backfill operation error."""
        try:
            backfill_errors_total.labels(error_type=error_type).inc()
            logger.warning(
                "Backfill error recorded",
                extra={"error_type": error_type}
            )
        except Exception as e:
            logger.error(f"Failed to record backfill error metric: {e}")
    
    @staticmethod
    def record_property_updated(update_type: str):
        """Record a property update event."""
        try:
            property_updated_total.labels(update_type=update_type).inc()
            logger.info(
                "Property update metric recorded",
                extra={"update_type": update_type}
            )
        except Exception as e:
            logger.error(f"Failed to record property update metric: {e}")
    
    @staticmethod
    def record_property_deleted():
        """Record a property deletion event."""
        try:
            property_deleted_total.inc()
            logger.info("Property deletion metric recorded")
        except Exception as e:
            logger.error(f"Failed to record property deletion metric: {e}")
    
    @staticmethod
    def record_property_archived():
        """Record a property archival event."""
        try:
            property_archived_total.inc()
            logger.info("Property archival metric recorded")
        except Exception as e:
            logger.error(f"Failed to record property archival metric: {e}")
    
    @staticmethod
    def record_transaction_linked(transaction_type: str):
        """Record a transaction linking event."""
        try:
            transaction_linked_total.labels(transaction_type=transaction_type).inc()
            logger.info(
                "Transaction linking metric recorded",
                extra={"transaction_type": transaction_type}
            )
        except Exception as e:
            logger.error(f"Failed to record transaction linking metric: {e}")
    
    @staticmethod
    def record_transaction_unlinked():
        """Record a transaction unlinking event."""
        try:
            transaction_unlinked_total.inc()
            logger.info("Transaction unlinking metric recorded")
        except Exception as e:
            logger.error(f"Failed to record transaction unlinking metric: {e}")
    
    @staticmethod
    def record_property_query(query_type: str, duration_seconds: float):
        """
        Record a property query operation.
        
        Args:
            query_type: Type of query ('list', 'get', 'metrics', 'transactions')
            duration_seconds: Duration of the query
        """
        try:
            property_query_duration_seconds.labels(query_type=query_type).observe(duration_seconds)
            logger.debug(
                "Property query metric recorded",
                extra={
                    "query_type": query_type,
                    "duration_seconds": duration_seconds
                }
            )
        except Exception as e:
            logger.error(f"Failed to record property query metric: {e}")
    
    @staticmethod
    def record_cache_hit(cache_type: str):
        """Record a cache hit."""
        try:
            property_cache_hits_total.labels(cache_type=cache_type).inc()
        except Exception as e:
            logger.error(f"Failed to record cache hit metric: {e}")
    
    @staticmethod
    def record_cache_miss(cache_type: str):
        """Record a cache miss."""
        try:
            property_cache_misses_total.labels(cache_type=cache_type).inc()
        except Exception as e:
            logger.error(f"Failed to record cache miss metric: {e}")
    
    @staticmethod
    def update_active_properties_gauge(property_type: str, count: int):
        """
        Update the active properties gauge.
        
        Args:
            property_type: Type of property ('rental', 'owner_occupied', 'mixed_use')
            count: Current count of active properties
        """
        try:
            active_properties_gauge.labels(property_type=property_type).set(count)
        except Exception as e:
            logger.error(f"Failed to update active properties gauge: {e}")
    
    @staticmethod
    def record_validation_error(validation_type: str):
        """Record a validation error."""
        try:
            property_validation_errors_total.labels(validation_type=validation_type).inc()
            logger.warning(
                "Property validation error recorded",
                extra={"validation_type": validation_type}
            )
        except Exception as e:
            logger.error(f"Failed to record validation error metric: {e}")
