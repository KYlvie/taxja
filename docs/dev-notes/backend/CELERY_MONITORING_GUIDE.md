# Celery Task Monitoring Guide

## Overview

This guide covers monitoring and observability for Celery tasks in the Property Asset Management system, with a focus on the annual depreciation generation task.

## Monitoring Components

### 1. Celery Beat Schedule

The annual depreciation task is scheduled to run automatically:

- **Schedule**: December 31 at 23:00 (Vienna time)
- **Task**: `property.generate_annual_depreciation`
- **Priority**: High (9)
- **Expiration**: 2 hours
- **Timezone**: Europe/Vienna

### 2. Prometheus Metrics

Three key metrics are exposed at `/metrics` endpoint:

#### property_created_total
- **Type**: Counter
- **Labels**: `user_id`
- **Description**: Total number of properties created
- **Usage**: Track property registration rate

#### depreciation_generated_total
- **Type**: Counter
- **Labels**: `user_id`, `year`
- **Description**: Total depreciation transactions generated
- **Usage**: Monitor annual depreciation generation success

#### backfill_duration_seconds
- **Type**: Histogram
- **Labels**: `property_id`
- **Buckets**: 0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, +Inf
- **Description**: Duration of historical depreciation backfill operations
- **Usage**: Track backfill performance and identify slow operations

### 3. Structured Logging

All Celery tasks emit structured logs with the following events:

- `task_started`: Task execution begins
- `task_completed`: Task execution finishes
- `task_success`: Task succeeded
- `task_failure`: Task failed
- `annual_depreciation_success`: Annual depreciation completed successfully
- `annual_depreciation_failure`: Annual depreciation failed (CRITICAL)

Log fields include:
- `task_id`: Unique task identifier
- `task_name`: Task name
- `task_state`: Task state (SUCCESS, FAILURE, etc.)
- `event`: Event type for filtering
- Additional context (user_id, year, amounts, etc.)

## Monitoring Dashboards

### Grafana Dashboard Queries

#### Annual Depreciation Success Rate
```promql
rate(depreciation_generated_total[1h])
```

#### Properties Created Per Hour
```promql
rate(property_created_total[1h])
```

#### Backfill Duration P95
```promql
histogram_quantile(0.95, rate(backfill_duration_seconds_bucket[5m]))
```

#### Backfill Duration Average
```promql
rate(backfill_duration_seconds_sum[5m]) / rate(backfill_duration_seconds_count[5m])
```

#### Failed Tasks (Last 24h)
```promql
increase(celery_task_failed_total[24h])
```

## Alerting Rules

### Critical Alerts

#### Annual Depreciation Failure
```yaml
- alert: AnnualDepreciationFailed
  expr: increase(celery_task_failed_total{task_name="property.generate_annual_depreciation"}[1h]) > 0
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "Annual depreciation generation failed"
    description: "The annual depreciation task failed. This requires immediate attention as it affects year-end tax calculations."
```

#### Annual Depreciation Not Running
```yaml
- alert: AnnualDepreciationNotRunning
  expr: |
    (month() == 12 and day_of_month() == 31 and hour() >= 23) and
    (time() - celery_task_last_success_timestamp{task_name="property.generate_annual_depreciation"} > 7200)
  for: 10m
  labels:
    severity: critical
  annotations:
    summary: "Annual depreciation task did not run on schedule"
    description: "The annual depreciation task should have run on Dec 31 at 23:00 but did not execute."
```

### Warning Alerts

#### Slow Backfill Operations
```yaml
- alert: SlowBackfillOperations
  expr: histogram_quantile(0.95, rate(backfill_duration_seconds_bucket[5m])) > 60
  for: 15m
  labels:
    severity: warning
  annotations:
    summary: "Backfill operations are slow"
    description: "95th percentile backfill duration is above 60 seconds. Consider investigating database performance."
```

#### High Task Failure Rate
```yaml
- alert: HighCeleryTaskFailureRate
  expr: rate(celery_task_failed_total[5m]) / rate(celery_task_total[5m]) > 0.1
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "High Celery task failure rate"
    description: "More than 10% of Celery tasks are failing."
```

## Log Aggregation

### ELK Stack Queries

#### Find Annual Depreciation Executions
```json
{
  "query": {
    "bool": {
      "must": [
        { "match": { "event": "annual_depreciation_success" } },
        { "range": { "@timestamp": { "gte": "now-7d" } } }
      ]
    }
  }
}
```

#### Find Failed Tasks
```json
{
  "query": {
    "bool": {
      "must": [
        { "match": { "event": "task_failure" } },
        { "range": { "@timestamp": { "gte": "now-24h" } } }
      ]
    }
  },
  "sort": [
    { "@timestamp": { "order": "desc" } }
  ]
}
```

#### Find Slow Backfills
```json
{
  "query": {
    "bool": {
      "must": [
        { "match": { "task_name": "property.backfill_depreciation" } },
        { "range": { "duration": { "gte": 30 } } }
      ]
    }
  }
}
```

## Manual Monitoring

### Check Celery Beat Status

```bash
# Check if Celery Beat is running
celery -A app.celery_app inspect active

# Check scheduled tasks
celery -A app.celery_app inspect scheduled

# Check registered tasks
celery -A app.celery_app inspect registered
```

### Check Task Results

```bash
# View task result in Redis
redis-cli GET celery-task-meta-<task_id>

# List all task results
redis-cli KEYS celery-task-meta-*
```

### Trigger Manual Depreciation

```bash
# Trigger for current year (all users)
celery -A app.celery_app call property.generate_annual_depreciation

# Trigger for specific year
celery -A app.celery_app call property.generate_annual_depreciation --args='[2025]'

# Trigger for specific user
celery -A app.celery_app call property.generate_annual_depreciation --kwargs='{"user_id": 123}'
```

## Performance Benchmarks

### Expected Performance

- **Property Creation**: < 100ms per property
- **Backfill Operation**: < 10s for 10 years of history
- **Annual Depreciation**: < 5 minutes for 1000 properties
- **Task Failure Rate**: < 1%

### Scaling Considerations

- **Workers**: 1 worker per 100 active properties
- **Concurrency**: 4-8 concurrent tasks per worker
- **Memory**: ~200MB per worker
- **Database Connections**: 2 per worker (1 for task, 1 for result backend)

## Troubleshooting

### Task Not Running

1. Check Celery Beat is running:
   ```bash
   ps aux | grep celery
   ```

2. Check beat schedule:
   ```bash
   celery -A app.celery_app inspect scheduled
   ```

3. Check logs:
   ```bash
   tail -f /var/log/celery/beat.log
   tail -f /var/log/celery/worker.log
   ```

### Task Failing

1. Check task result:
   ```bash
   celery -A app.celery_app result <task_id>
   ```

2. Check error logs:
   ```bash
   grep "task_failure" /var/log/celery/worker.log
   ```

3. Check database connectivity:
   ```bash
   psql -h localhost -U taxja -d taxja -c "SELECT 1"
   ```

### Slow Performance

1. Check database query performance:
   ```sql
   SELECT * FROM pg_stat_statements 
   ORDER BY total_exec_time DESC 
   LIMIT 10;
   ```

2. Check Redis latency:
   ```bash
   redis-cli --latency
   ```

3. Check worker load:
   ```bash
   celery -A app.celery_app inspect stats
   ```

## Maintenance

### Daily Checks

- [ ] Verify Celery workers are running
- [ ] Check task failure rate in Grafana
- [ ] Review error logs for anomalies

### Weekly Checks

- [ ] Review backfill performance metrics
- [ ] Check Redis memory usage
- [ ] Verify database connection pool health

### Monthly Checks

- [ ] Review and optimize slow queries
- [ ] Clean up old task results (> 7 days)
- [ ] Update alert thresholds based on trends

### Year-End Checks (December)

- [ ] Verify annual depreciation schedule is active
- [ ] Test manual trigger of depreciation task
- [ ] Ensure monitoring alerts are configured
- [ ] Verify email notification system is working
- [ ] Check database has sufficient space for new transactions
- [ ] Review and update task timeout settings if needed

## Contact

For critical issues with annual depreciation generation:
- **Escalation**: Alert on-call engineer immediately
- **Rollback**: Use manual API endpoint to regenerate if needed
- **Communication**: Notify affected users via email

---

**Last Updated**: 2026-03-08
**Version**: 1.0
