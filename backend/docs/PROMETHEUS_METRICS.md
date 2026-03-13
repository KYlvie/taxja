# Prometheus Metrics Documentation

## Overview

The Taxja backend exposes Prometheus metrics for monitoring property management operations. These metrics help track system performance, usage patterns, and operational health.

## Metrics Endpoint

**URL:** `GET /metrics`

**Description:** Exposes metrics in Prometheus text format for scraping by Prometheus server.

**Authentication:** None (should be restricted at infrastructure level)

**Example:**
```bash
curl http://localhost:8000/metrics
```

## Available Metrics

### 1. property_created_total

**Type:** Counter

**Description:** Total number of properties created in the system.

**Labels:**
- `user_id` (string): ID of the user who created the property

**Usage:**
```python
from app.core.metrics import property_created_counter

# Increment counter when property is created
property_created_counter.labels(user_id=str(user_id)).inc()
```

**Example Queries:**
```promql
# Total properties created
sum(property_created_total)

# Properties created per user
sum by (user_id) (property_created_total)

# Rate of property creation (per minute)
rate(property_created_total[5m])
```

### 2. depreciation_generated_total

**Type:** Counter

**Description:** Total number of depreciation transactions generated (both annual and historical backfill).

**Labels:**
- `user_id` (string): ID of the user who owns the property
- `year` (string): Tax year for which depreciation was generated

**Usage:**
```python
from app.core.metrics import depreciation_generated_counter

# Increment counter when depreciation transaction is created
depreciation_generated_counter.labels(
    user_id=str(user_id),
    year=str(year)
).inc()
```

**Example Queries:**
```promql
# Total depreciation transactions generated
sum(depreciation_generated_total)

# Depreciation transactions per year
sum by (year) (depreciation_generated_total)

# Depreciation transactions per user
sum by (user_id) (depreciation_generated_total)

# Rate of depreciation generation (per minute)
rate(depreciation_generated_total[5m])
```

### 3. backfill_duration_seconds

**Type:** Histogram

**Description:** Duration of historical depreciation backfill operations in seconds.

**Labels:**
- `property_id` (string): UUID of the property being backfilled

**Buckets:** 0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, +Inf

**Usage:**
```python
from app.core.metrics import backfill_duration_histogram
import time

# Record duration of backfill operation
start_time = time.time()
try:
    # ... perform backfill ...
    pass
finally:
    duration = time.time() - start_time
    backfill_duration_histogram.labels(property_id=str(property_id)).observe(duration)
```

**Example Queries:**
```promql
# Average backfill duration
rate(backfill_duration_seconds_sum[5m]) / rate(backfill_duration_seconds_count[5m])

# 95th percentile backfill duration
histogram_quantile(0.95, rate(backfill_duration_seconds_bucket[5m]))

# 99th percentile backfill duration
histogram_quantile(0.99, rate(backfill_duration_seconds_bucket[5m]))

# Total backfill operations
sum(backfill_duration_seconds_count)
```

## Integration with Services

### PropertyService

**Location:** `backend/app/services/property_service.py`

**Metrics:**
- Increments `property_created_total` when `create_property()` is called

### AnnualDepreciationService

**Location:** `backend/app/services/annual_depreciation_service.py`

**Metrics:**
- Increments `depreciation_generated_total` for each depreciation transaction created in `generate_annual_depreciation()`

### HistoricalDepreciationService

**Location:** `backend/app/services/historical_depreciation_service.py`

**Metrics:**
- Records `backfill_duration_seconds` for each `backfill_depreciation()` operation (when `confirm=True`)

## Prometheus Configuration

### Scrape Configuration

Add the following to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'taxja-backend'
    scrape_interval: 15s
    static_configs:
      - targets: ['backend:8000']
    metrics_path: '/metrics'
```

### Kubernetes Service Monitor

For Kubernetes deployments with Prometheus Operator:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: taxja-backend
  namespace: taxja
spec:
  selector:
    matchLabels:
      app: taxja-backend
  endpoints:
    - port: http
      path: /metrics
      interval: 15s
```

## Alerting Rules

### Example Alert Rules

```yaml
groups:
  - name: taxja_property_management
    interval: 30s
    rules:
      # Alert if backfill operations are taking too long
      - alert: SlowBackfillOperations
        expr: histogram_quantile(0.95, rate(backfill_duration_seconds_bucket[5m])) > 30
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Backfill operations are slow"
          description: "95th percentile backfill duration is {{ $value }}s (threshold: 30s)"
      
      # Alert if no properties are being created (potential system issue)
      - alert: NoPropertyCreation
        expr: rate(property_created_total[1h]) == 0
        for: 24h
        labels:
          severity: info
        annotations:
          summary: "No properties created in 24 hours"
          description: "No new properties have been created in the last 24 hours"
      
      # Alert if depreciation generation fails (no transactions created during year-end)
      - alert: DepreciationGenerationFailure
        expr: rate(depreciation_generated_total[1h]) == 0
        for: 2h
        labels:
          severity: critical
        annotations:
          summary: "Depreciation generation may have failed"
          description: "No depreciation transactions generated in the last 2 hours during year-end period"
```

## Grafana Dashboard

### Example Dashboard Panels

#### Property Creation Rate
```promql
rate(property_created_total[5m])
```

#### Depreciation Generation by Year
```promql
sum by (year) (depreciation_generated_total)
```

#### Backfill Duration Heatmap
```promql
rate(backfill_duration_seconds_bucket[5m])
```

#### Average Backfill Duration
```promql
rate(backfill_duration_seconds_sum[5m]) / rate(backfill_duration_seconds_count[5m])
```

## Security Considerations

1. **Access Control:** The `/metrics` endpoint should be restricted at the infrastructure level (firewall, network policies) to only allow access from Prometheus servers.

2. **Sensitive Data:** Metrics include user IDs and property IDs. Ensure Prometheus storage is secured and access is restricted.

3. **Rate Limiting:** Consider rate limiting the `/metrics` endpoint if exposed to untrusted networks.

4. **HTTPS:** Always use HTTPS for metrics scraping in production environments.

## Troubleshooting

### Metrics Not Appearing

1. Check that prometheus-client is installed:
   ```bash
   pip list | grep prometheus-client
   ```

2. Verify the `/metrics` endpoint is accessible:
   ```bash
   curl http://localhost:8000/metrics
   ```

3. Check Prometheus scrape configuration and targets.

### Incorrect Metric Values

1. Verify that metrics are being incremented/observed in the correct locations in the code.

2. Check for exceptions that might prevent metrics from being recorded.

3. Review Prometheus query syntax and time ranges.

### Performance Impact

Prometheus metrics have minimal performance overhead. However, if you notice issues:

1. Reduce scrape frequency in Prometheus configuration.

2. Review histogram bucket configuration (fewer buckets = less overhead).

3. Consider sampling for high-frequency operations.

## References

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Prometheus Python Client](https://github.com/prometheus/client_python)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/naming/)
- [Grafana Documentation](https://grafana.com/docs/)
