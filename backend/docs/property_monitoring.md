# Property Management Monitoring Guide

## Overview

This document describes the monitoring and observability infrastructure for the Property Asset Management feature in Taxja. The monitoring system tracks key metrics, errors, and performance indicators to ensure system health and enable proactive issue detection.

## Architecture

The monitoring system consists of three main components:

1. **Prometheus Metrics** - Time-series metrics for operational monitoring
2. **Structured Logging** - Contextual logs for debugging and analysis
3. **Error Tracking** - Categorized error tracking with severity levels

## Prometheus Metrics

### Metrics Endpoint

All metrics are exposed at the `/metrics` endpoint in Prometheus format:

```
GET http://localhost:8000/metrics
```

This endpoint is typically scraped by a Prometheus server at regular intervals (e.g., every 15 seconds).

### Available Metrics

#### Property Creation Metrics

**property_created_total** (Counter)
- Description: Total number of properties created
- Labels:
  - `property_type`: rental, owner_occupied, mixed_use
  - `user_type`: landlord, homeowner
- Example: `property_created_total{property_type="rental",user_type="landlord"} 42`

**property_creation_errors_total** (Counter)
- Description: Total number of property creation errors
- Labels:
  - `error_type`: validation, database, permission, etc.
- Example: `property_creation_errors_total{error_type="validation"} 5`

#### Depreciation Metrics

**depreciation_generated_total** (Counter)
- Description: Total number of depreciation transactions generated
- Labels:
  - `generation_type`: annual, historical_backfill, manual
- Example: `depreciation_generated_total{generation_type="annual"} 150`

**depreciation_amount_total** (Counter)
- Description: Total depreciation amount generated in EUR
- Labels:
  - `generation_type`: annual, historical_backfill, manual
- Example: `depreciation_amount_total{generation_type="annual"} 840000.00`

**depreciation_generation_errors_total** (Counter)
- Description: Total number of depreciation generation errors
- Labels:
  - `error_type`: calculation, database, conflict, etc.
- Example: `depreciation_generation_errors_total{error_type="calculation"} 2`

#### Backfill Metrics

**backfill_duration_seconds** (Histogram)
- Description: Duration of historical depreciation backfill operations
- Buckets: [0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0]
- Example: `backfill_duration_seconds_bucket{le="5.0"} 45`

**backfill_years_processed** (Histogram)
- Description: Number of years processed in backfill operations
- Buckets: [1, 2, 3, 5, 10, 15, 20, 30]
- Example: `backfill_years_processed_bucket{le="5"} 38`

**backfill_errors_total** (Counter)
- Description: Total number of backfill operation errors
- Labels:
  - `error_type`: database, calculation, validation, etc.
- Example: `backfill_errors_total{error_type="database"} 1`

#### Property Operation Metrics

**property_updated_total** (Counter)
- Description: Total number of property updates
- Labels:
  - `update_type`: details, archive, status
- Example: `property_updated_total{update_type="details"} 28`

**property_deleted_total** (Counter)
- Description: Total number of properties deleted
- Example: `property_deleted_total 3`

**property_archived_total** (Counter)
- Description: Total number of properties archived
- Example: `property_archived_total 7`

#### Transaction Linking Metrics

**transaction_linked_total** (Counter)
- Description: Total number of transactions linked to properties
- Labels:
  - `transaction_type`: income, expense
- Example: `transaction_linked_total{transaction_type="income"} 156`

**transaction_unlinked_total** (Counter)
- Description: Total number of transactions unlinked from properties
- Example: `transaction_unlinked_total 12`

#### Performance Metrics

**property_query_duration_seconds** (Histogram)
- Description: Duration of property query operations
- Labels:
  - `query_type`: list, get, metrics, transactions
- Buckets: [0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5]
- Example: `property_query_duration_seconds_bucket{query_type="list",le="0.1"} 95`

#### Cache Metrics

**property_cache_hits_total** (Counter)
- Description: Total number of property cache hits
- Labels:
  - `cache_type`: metrics, portfolio, depreciation_schedule
- Example: `property_cache_hits_total{cache_type="metrics"} 234`

**property_cache_misses_total** (Counter)
- Description: Total number of property cache misses
- Labels:
  - `cache_type`: metrics, portfolio, depreciation_schedule
- Example: `property_cache_misses_total{cache_type="metrics"} 45`

#### System State Metrics

**active_properties_total** (Gauge)
- Description: Current number of active properties
- Labels:
  - `property_type`: rental, owner_occupied, mixed_use
- Example: `active_properties_total{property_type="rental"} 127`

**property_validation_errors_total** (Counter)
- Description: Total number of property validation errors
- Labels:
  - `validation_type`: purchase_price, building_value, depreciation_rate, etc.
- Example: `property_validation_errors_total{validation_type="purchase_price"} 8`

## Using the Metrics Service

### Recording Metrics in Code

```python
from app.services.property_metrics_service import PropertyMetricsService

# Record property creation
PropertyMetricsService.record_property_created(
    property_type='rental',
    user_type='landlord'
)

# Record depreciation generation
PropertyMetricsService.record_depreciation_generated(
    generation_type='annual',
    count=5,
    total_amount=28000.00
)

# Record backfill operation
PropertyMetricsService.record_backfill_operation(
    duration_seconds=2.5,
    years_processed=5
)

# Record query performance
PropertyMetricsService.record_property_query(
    query_type='list',
    duration_seconds=0.05
)

# Record cache hit/miss
PropertyMetricsService.record_cache_hit('metrics')
PropertyMetricsService.record_cache_miss('portfolio')

# Update active properties gauge
PropertyMetricsService.update_active_properties_gauge('rental', 127)
```

## Error Tracking

### Error Categories

The system tracks errors in the following categories:

- **VALIDATION**: Input validation errors
- **DATABASE**: Database operation errors
- **CALCULATION**: Depreciation calculation errors
- **PERMISSION**: Authorization/permission errors
- **NOT_FOUND**: Resource not found errors
- **CONFLICT**: Conflict errors (e.g., duplicate depreciation)
- **EXTERNAL_SERVICE**: External service integration errors
- **UNKNOWN**: Uncategorized errors

### Error Severity Levels

- **LOW**: Minor issues that don't affect functionality
- **MEDIUM**: Issues that may affect user experience
- **HIGH**: Serious issues requiring attention
- **CRITICAL**: System-critical issues requiring immediate action

### Using the Error Tracker

```python
from app.services.property_error_tracker import (
    PropertyErrorTracker,
    ErrorSeverity,
    ErrorCategory
)

# Track a validation error
PropertyErrorTracker.track_validation_error(
    field_name="purchase_price",
    error_message="Must be greater than 0",
    user_id=123
)

# Track a depreciation generation failure
PropertyErrorTracker.track_depreciation_generation_failure(
    property_id="550e8400-e29b-41d4-a716-446655440000",
    year=2026,
    error_message="Building value exceeded"
)

# Track a backfill failure
PropertyErrorTracker.track_backfill_failure(
    property_id="550e8400-e29b-41d4-a716-446655440000",
    user_id=123,
    years_attempted=5,
    error_message="Transaction creation failed"
)

# Track a database error
PropertyErrorTracker.track_database_error(
    operation="property_creation",
    error_message="Connection timeout",
    context={"user_id": 123}
)
```

## Structured Logging

All property operations include structured logging with context:

```python
logger.info(
    "Property created",
    extra={
        "property_id": str(property.id),
        "user_id": property.user_id,
        "property_type": property.property_type,
        "building_value": float(property.building_value),
        "depreciation_rate": float(property.depreciation_rate)
    }
)
```

### Log Levels

- **DEBUG**: Detailed diagnostic information
- **INFO**: General informational messages
- **WARNING**: Warning messages for potential issues
- **ERROR**: Error messages for failures
- **CRITICAL**: Critical system failures

## Alerting Rules

### Recommended Prometheus Alerts

```yaml
groups:
  - name: property_management
    rules:
      # High error rate alert
      - alert: HighPropertyCreationErrorRate
        expr: rate(property_creation_errors_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High property creation error rate"
          description: "Property creation error rate is {{ $value }} errors/sec"
      
      # Depreciation generation failures
      - alert: DepreciationGenerationFailures
        expr: rate(depreciation_generation_errors_total[5m]) > 0
        for: 5m
        labels:
          severity: high
        annotations:
          summary: "Depreciation generation failures detected"
          description: "{{ $value }} depreciation generation errors in the last 5 minutes"
      
      # Slow property queries
      - alert: SlowPropertyQueries
        expr: histogram_quantile(0.95, rate(property_query_duration_seconds_bucket[5m])) > 1.0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Slow property queries detected"
          description: "95th percentile query duration is {{ $value }}s"
      
      # Low cache hit rate
      - alert: LowPropertyCacheHitRate
        expr: |
          rate(property_cache_hits_total[5m]) / 
          (rate(property_cache_hits_total[5m]) + rate(property_cache_misses_total[5m])) < 0.7
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Low property cache hit rate"
          description: "Cache hit rate is {{ $value | humanizePercentage }}"
      
      # Backfill operation failures
      - alert: BackfillOperationFailures
        expr: rate(backfill_errors_total[5m]) > 0
        for: 5m
        labels:
          severity: high
        annotations:
          summary: "Backfill operation failures detected"
          description: "{{ $value }} backfill errors in the last 5 minutes"
```

## Grafana Dashboards

### Recommended Dashboard Panels

1. **Property Operations Overview**
   - Total properties created (counter)
   - Properties by type (pie chart)
   - Property creation rate (graph)

2. **Depreciation Metrics**
   - Depreciation transactions generated (counter)
   - Total depreciation amount (counter)
   - Depreciation generation rate (graph)

3. **Performance Metrics**
   - Query duration percentiles (graph)
   - Cache hit rate (gauge)
   - Active properties (gauge)

4. **Error Tracking**
   - Error rate by category (graph)
   - Error count by type (table)
   - Recent errors (logs panel)

5. **Backfill Operations**
   - Backfill duration histogram (heatmap)
   - Years processed distribution (histogram)
   - Backfill success rate (gauge)

## Monitoring Best Practices

1. **Set up alerts** for critical metrics (error rates, performance degradation)
2. **Monitor trends** over time to identify patterns
3. **Correlate metrics** with logs for debugging
4. **Review dashboards** regularly during deployments
5. **Adjust thresholds** based on actual system behavior
6. **Document incidents** and update alerts accordingly

## Troubleshooting

### High Error Rate

1. Check error logs for specific error messages
2. Review recent code changes or deployments
3. Check database connection and performance
4. Verify external service availability

### Slow Queries

1. Check database indexes
2. Review query execution plans
3. Verify cache is working correctly
4. Check for N+1 query problems

### Low Cache Hit Rate

1. Verify Redis is running and accessible
2. Check cache TTL settings
3. Review cache invalidation logic
4. Monitor cache memory usage

### Backfill Failures

1. Check database transaction logs
2. Verify property data integrity
3. Review depreciation calculation logic
4. Check for duplicate transaction conflicts

## Testing

Run the monitoring tests to verify metrics are being recorded correctly:

```bash
cd backend
pytest tests/test_property_metrics_service.py -v
pytest tests/test_property_error_tracker.py -v
```

## References

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Python Prometheus Client](https://github.com/prometheus/client_python)
- [Structured Logging Best Practices](https://www.structlog.org/)
