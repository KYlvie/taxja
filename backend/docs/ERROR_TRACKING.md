# Error Tracking System

## Overview

The error tracking system provides comprehensive monitoring and alerting for property asset management operations. It tracks validation errors, depreciation generation failures, backfill errors, and critical system errors with structured logging and automatic alerting.

## Features

- **Validation Error Tracking**: Track field validation errors with context
- **Depreciation Failure Tracking**: Monitor depreciation calculation failures
- **Backfill Error Tracking**: Track historical depreciation backfill failures
- **Critical Error Alerting**: Immediate alerts for critical system errors
- **Error Statistics**: Comprehensive error analytics and reporting
- **Automatic Thresholds**: Alert when error rates exceed thresholds
- **Time-based Filtering**: Query errors by time window
- **Category Filtering**: Filter errors by category and severity

## Architecture

### Error Categories

```python
class ErrorCategory(str, Enum):
    VALIDATION = "validation"
    DEPRECIATION_GENERATION = "depreciation_generation"
    BACKFILL = "backfill"
    PROPERTY_CREATION = "property_creation"
    PROPERTY_UPDATE = "property_update"
    PROPERTY_DELETION = "property_deletion"
    TRANSACTION_LINKING = "transaction_linking"
    DATABASE = "database"
    PERMISSION = "permission"
    CALCULATION = "calculation"
    SYSTEM = "system"
```

### Error Severity Levels

```python
class ErrorSeverity(str, Enum):
    LOW = "low"           # Validation errors, user input errors
    MEDIUM = "medium"     # Recoverable errors, warnings
    HIGH = "high"         # Depreciation failures, backfill errors
    CRITICAL = "critical" # System failures, data corruption
```

## Usage

### Tracking Validation Errors

```python
from app.services.error_tracker import ErrorTracker

ErrorTracker.track_validation_error(
    error_type="value_error",
    field="purchase_price",
    value="-1000",
    message="purchase_price must be greater than 0",
    user_id=123,
    property_id=property_id,
    context={"operation": "create_property"}
)
```

### Tracking Depreciation Failures

```python
ErrorTracker.track_depreciation_failure(
    property_id=property_id,
    year=2026,
    error=exception,
    user_id=user_id,
    property_address="Hauptstraße 123, 1010 Wien",
    context={
        "building_value": str(property.building_value),
        "depreciation_rate": str(property.depreciation_rate)
    }
)
```

### Tracking Backfill Failures

```python
ErrorTracker.track_backfill_failure(
    property_id=property_id,
    error=exception,
    user_id=user_id,
    years_attempted=[2020, 2021, 2022, 2023, 2024, 2025],
    context={"confirm": True}
)
```

### Tracking Critical Errors

```python
ErrorTracker.track_critical_error(
    category=ErrorCategory.DATABASE,
    error=exception,
    message="Critical database error in property service",
    user_id=user_id,
    property_id=property_id,
    context={"operation": "update_property"}
)
```

## Automatic Error Tracking with Decorators

### Property Operation Errors

```python
from app.services.property_error_integration import track_property_errors

@track_property_errors(ErrorCategory.PROPERTY_CREATION)
def create_property(self, user_id, property_data):
    # Automatically tracks ValueError, PermissionError, and other exceptions
    ...
```

### Depreciation Calculation Errors

```python
from app.services.property_error_integration import track_depreciation_errors

@track_depreciation_errors
def calculate_annual_depreciation(self, property, year):
    # Automatically tracks depreciation failures
    ...
```

### Backfill Operation Errors

```python
from app.services.property_error_integration import track_backfill_errors

@track_backfill_errors
def backfill_depreciation(self, property_id, user_id):
    # Automatically tracks backfill failures
    ...
```

## API Endpoints

### Get Error Statistics

```http
GET /api/v1/monitoring/errors/statistics?category=depreciation_generation&hours=24
```

**Response:**
```json
{
  "total_errors": 15,
  "since": "2026-03-07T10:00:00",
  "by_category": {
    "depreciation_generation": 8,
    "validation": 5,
    "backfill": 2
  },
  "by_severity": {
    "high": 10,
    "low": 5
  },
  "by_error_type": {
    "ValueError": 5,
    "RuntimeError": 3,
    "PermissionError": 2
  },
  "recent_errors": [...]
}
```

### Get Recent Errors

```http
GET /api/v1/monitoring/errors/recent?category=validation&limit=20
```

**Response:**
```json
[
  {
    "timestamp": "2026-03-08T14:30:00",
    "category": "validation",
    "severity": "low",
    "error_type": "value_error",
    "field": "purchase_price",
    "value": "-1000",
    "message": "purchase_price must be greater than 0",
    "user_id": 123,
    "property_id": "550e8400-e29b-41d4-a716-446655440000",
    "context": {}
  }
]
```

### Get Error Health Status

```http
GET /api/v1/monitoring/errors/health
```

**Response:**
```json
{
  "status": "warning",
  "alerts": [
    {
      "type": "high_depreciation_failure_rate",
      "severity": "high",
      "message": "High depreciation failure rate - 5 failures in last hour",
      "count": 5,
      "threshold": 3
    }
  ],
  "error_rates": {
    "validation_errors_per_hour": 2.5,
    "depreciation_failures_per_hour": 5.0,
    "critical_errors_per_hour": 0.0
  }
}
```

### Clear Old Errors

```http
POST /api/v1/monitoring/errors/clear-old?days=30
```

**Response:**
```json
{
  "cleared_count": 1523,
  "older_than_days": 30
}
```

## Alert Thresholds

### Validation Errors
- **Threshold**: 10 errors per hour
- **Action**: Log warning with alert type
- **Severity**: Medium

### Depreciation Failures
- **Threshold**: 3 failures per hour
- **Action**: Log error with alert type
- **Severity**: High

### Critical Errors
- **Threshold**: 1 error (immediate)
- **Action**: Log critical with immediate alert
- **Severity**: Critical

## Integration with External Services

The error tracking system is designed to integrate with external monitoring and alerting services:

### Sentry Integration (Recommended)

```python
import sentry_sdk

# In _send_critical_alert method
sentry_sdk.capture_exception(error_data["error"])
```

### Email Alerts

```python
# In _send_critical_alert method
send_email_alert(
    to="admin@taxja.com",
    subject=f"CRITICAL: {error_data['message']}",
    body=format_error_email(error_data)
)
```

### Slack/Teams Webhooks

```python
# In _send_critical_alert method
send_slack_alert(
    webhook_url=settings.SLACK_WEBHOOK_URL,
    message=format_slack_message(error_data)
)
```

### PagerDuty

```python
# In _send_critical_alert method
create_pagerduty_incident(
    service_key=settings.PAGERDUTY_SERVICE_KEY,
    description=error_data["message"],
    details=error_data
)
```

## Structured Logging

All errors are logged with structured data for easy parsing and analysis:

```python
logger.error(
    f"Depreciation generation failed for property {property_id}",
    extra={
        "error_category": ErrorCategory.DEPRECIATION_GENERATION,
        "property_id": str(property_id),
        "year": year,
        "error_type": type(error).__name__,
        "user_id": user_id,
        "property_address": property_address
    },
    exc_info=True
)
```

## Monitoring Dashboard

The error tracking system provides data for monitoring dashboards:

- **Error Rate Graphs**: Track error rates over time
- **Category Distribution**: Pie chart of errors by category
- **Severity Distribution**: Bar chart of errors by severity
- **Top Error Types**: List of most common error types
- **Recent Errors Timeline**: Timeline of recent errors
- **Alert Status**: Current alert status and active alerts

## Best Practices

1. **Always provide context**: Include relevant context information when tracking errors
2. **Use appropriate severity**: Choose the correct severity level for each error
3. **Include user and property IDs**: Always include user_id and property_id when available
4. **Clear old errors regularly**: Run cleanup job to prevent memory issues
5. **Monitor alert thresholds**: Adjust thresholds based on system behavior
6. **Integrate with external services**: Use Sentry or similar for production monitoring
7. **Review error statistics daily**: Check error health status regularly

## Testing

Run error tracking tests:

```bash
cd backend
pytest tests/test_error_tracking.py -v
```

## Performance Considerations

- **In-memory storage**: Current implementation uses in-memory storage (suitable for development)
- **Production**: Use external service like Sentry, Datadog, or New Relic
- **Cleanup**: Run cleanup job daily to prevent memory growth
- **Sampling**: Consider sampling high-volume errors in production

## Future Enhancements

- [ ] Integration with Sentry for production error tracking
- [ ] Email notifications for critical errors
- [ ] Slack/Teams webhook integration
- [ ] PagerDuty integration for on-call alerts
- [ ] Error trend analysis and anomaly detection
- [ ] Automatic error categorization using ML
- [ ] Error resolution tracking and workflows
- [ ] User-facing error reporting dashboard

## Related Documentation

- [Prometheus Metrics](./PROMETHEUS_METRICS.md)
- [Structured Logging](../TASK_C.3.2_STRUCTURED_LOGGING_COMPLETE.md)
- [Property Asset Management Design](../../.kiro/specs/property-asset-management/design.md)
