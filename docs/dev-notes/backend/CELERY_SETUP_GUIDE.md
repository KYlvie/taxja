# Celery Setup and Configuration Guide

## Overview

This guide covers the complete setup and configuration of Celery for the Property Asset Management system, including the annual depreciation task that runs automatically on December 31st.

## Prerequisites

- Python 3.11+
- Redis 7+ (message broker and result backend)
- PostgreSQL 15+ (application database)
- Docker and Docker Compose (for containerized deployment)

## Quick Start

### Local Development

1. **Start Redis** (if not already running):
   ```bash
   docker-compose up -d redis
   ```

2. **Start Celery Worker**:
   ```bash
   cd backend
   celery -A app.celery_app worker --loglevel=info
   ```

3. **Start Celery Beat** (in a separate terminal):
   ```bash
   cd backend
   celery -A app.celery_app beat --loglevel=info
   ```

4. **Optional: Start Flower** (monitoring dashboard):
   ```bash
   celery -A app.celery_app flower --port=5555
   ```
   Access at: http://localhost:5555

### Docker Deployment

1. **Start all Celery services**:
   ```bash
   docker-compose -f docker-compose.celery.yml up -d
   ```

2. **View logs**:
   ```bash
   docker-compose -f docker-compose.celery.yml logs -f celery-worker
   docker-compose -f docker-compose.celery.yml logs -f celery-beat
   ```

3. **Stop services**:
   ```bash
   docker-compose -f docker-compose.celery.yml down
   ```

## Configuration

### Environment Variables

Add to your `.env` file:

```bash
# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Optional: Email notifications
ENABLE_EMAIL_NOTIFICATIONS=false
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=noreply@taxja.at
SMTP_PASSWORD=your_password

# Optional: Flower monitoring
FLOWER_USER=admin
FLOWER_PASSWORD=secure_password
```

### Celery Configuration

The main configuration is in `backend/app/celery_app.py`:

```python
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Vienna",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    result_expires=3600 * 24 * 7,  # 7 days
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
)
```

### Beat Schedule

The annual depreciation task is scheduled in `backend/app/celery_app.py`:

```python
celery_app.conf.beat_schedule = {
    'generate-annual-depreciation': {
        'task': 'property.generate_annual_depreciation',
        'schedule': {
            'minute': '0',
            'hour': '23',
            'day_of_month': '31',
            'month_of_year': '12',
        },
        'options': {
            'expires': 3600 * 2,  # 2 hours
            'priority': 9,  # High priority
        },
    },
}
```

## Available Tasks

### 1. Annual Depreciation Generation

**Task Name**: `property.generate_annual_depreciation`

**Description**: Generates depreciation transactions for all active properties at year-end.

**Schedule**: December 31 at 23:00 (Vienna time)

**Manual Trigger**:
```bash
# For current year, all users
celery -A app.celery_app call property.generate_annual_depreciation

# For specific year
celery -A app.celery_app call property.generate_annual_depreciation --args='[2025]'

# For specific user
celery -A app.celery_app call property.generate_annual_depreciation --kwargs='{"user_id": 123}'
```

**API Endpoint**:
```bash
# User-triggered (authenticated)
POST /api/v1/properties/generate-annual-depreciation
{
  "year": 2026
}

# Admin-triggered (admin only)
POST /api/v1/admin/generate-annual-depreciation
{
  "year": 2026,
  "user_id": null  # null = all users
}
```

### 2. Portfolio Metrics Calculation

**Task Name**: `property.calculate_portfolio_metrics`

**Description**: Pre-calculates portfolio metrics for dashboard display.

**Manual Trigger**:
```bash
celery -A app.celery_app call property.calculate_portfolio_metrics --kwargs='{"user_id": 123, "year": 2026}'
```

### 3. Bulk Archive Properties

**Task Name**: `property.bulk_archive_properties`

**Description**: Archives multiple properties in bulk.

**Manual Trigger**:
```bash
celery -A app.celery_app call property.bulk_archive_properties --kwargs='{"property_ids": ["uuid1", "uuid2"], "user_id": 123, "sale_date": "2026-12-31"}'
```

### 4. Test Task

**Task Name**: `property.test_task`

**Description**: Simple test task to verify Celery is working.

**Manual Trigger**:
```bash
celery -A app.celery_app call property.test_task --kwargs='{"message": "Hello Celery!"}'
```

## Testing

### 1. Run Verification Script

```bash
cd backend
python verify_celery_beat_config.py
```

This validates the Celery Beat configuration without requiring a full environment.

### 2. Run Integration Test

```bash
cd backend
python test_celery_annual_depreciation.py
```

This tests the complete annual depreciation workflow:
- Creates test properties
- Triggers the task
- Verifies transactions are created
- Checks idempotence

### 3. Run Unit Tests

```bash
cd backend
pytest tests/test_celery_beat_schedule.py -v
pytest tests/test_prometheus_metrics.py -v
```

## Monitoring

### 1. Flower Dashboard

Access the Flower monitoring dashboard at http://localhost:5555

Features:
- Real-time task monitoring
- Worker status and statistics
- Task history and results
- Task rate graphs
- Worker pool information

### 2. Prometheus Metrics

Metrics are exposed at http://localhost:8000/metrics

Key metrics:
- `property_created_total`: Properties created counter
- `depreciation_generated_total`: Depreciation transactions counter
- `backfill_duration_seconds`: Backfill operation duration histogram

### 3. Grafana Dashboard

Import the dashboard from `k8s/monitoring/grafana-dashboard-property-management.json`

Panels include:
- Annual depreciation success rate
- Properties created rate
- Backfill duration (P50, P95, average)
- Task success rate
- Task failures (24h)
- Worker status

### 4. Logs

View structured logs:

```bash
# Worker logs
docker-compose -f docker-compose.celery.yml logs -f celery-worker

# Beat logs
docker-compose -f docker-compose.celery.yml logs -f celery-beat

# Filter for specific events
docker-compose -f docker-compose.celery.yml logs celery-worker | grep "annual_depreciation"
```

## Troubleshooting

### Worker Not Starting

**Symptom**: Worker fails to start or crashes immediately.

**Solutions**:
1. Check Redis is running:
   ```bash
   redis-cli ping
   ```

2. Check database connection:
   ```bash
   psql -h localhost -U taxja -d taxja -c "SELECT 1"
   ```

3. Check environment variables:
   ```bash
   env | grep CELERY
   env | grep POSTGRES
   env | grep REDIS
   ```

4. Check logs for errors:
   ```bash
   celery -A app.celery_app worker --loglevel=debug
   ```

### Beat Not Scheduling Tasks

**Symptom**: Scheduled tasks are not running.

**Solutions**:
1. Verify Beat is running:
   ```bash
   ps aux | grep "celery.*beat"
   ```

2. Check Beat schedule:
   ```bash
   celery -A app.celery_app inspect scheduled
   ```

3. Verify schedule configuration:
   ```bash
   python verify_celery_beat_config.py
   ```

4. Check Beat logs:
   ```bash
   celery -A app.celery_app beat --loglevel=debug
   ```

### Tasks Failing

**Symptom**: Tasks are failing with errors.

**Solutions**:
1. Check task result:
   ```bash
   celery -A app.celery_app result <task_id>
   ```

2. Check worker logs:
   ```bash
   docker-compose -f docker-compose.celery.yml logs celery-worker | grep ERROR
   ```

3. Test task directly:
   ```bash
   cd backend
   python test_celery_annual_depreciation.py
   ```

4. Check database connectivity from worker:
   ```bash
   docker-compose -f docker-compose.celery.yml exec celery-worker python -c "from app.db.session import SessionLocal; db = SessionLocal(); print('DB OK')"
   ```

### Slow Performance

**Symptom**: Tasks are taking too long to complete.

**Solutions**:
1. Check database query performance:
   ```sql
   SELECT * FROM pg_stat_statements 
   ORDER BY total_exec_time DESC 
   LIMIT 10;
   ```

2. Increase worker concurrency:
   ```bash
   celery -A app.celery_app worker --concurrency=8
   ```

3. Check Redis latency:
   ```bash
   redis-cli --latency
   ```

4. Monitor worker stats:
   ```bash
   celery -A app.celery_app inspect stats
   ```

### Duplicate Tasks

**Symptom**: Tasks are running multiple times.

**Solutions**:
1. Ensure only one Beat instance is running:
   ```bash
   ps aux | grep "celery.*beat" | wc -l
   ```

2. Check for duplicate schedule entries:
   ```bash
   python verify_celery_beat_config.py
   ```

3. Clear Beat schedule file:
   ```bash
   rm -f celerybeat-schedule
   ```

## Production Deployment

### Kubernetes

Deploy using the provided manifests:

```bash
# Deploy Celery worker
kubectl apply -f k8s/celery-worker-deployment.yaml

# Deploy Celery beat
kubectl apply -f k8s/celery-beat-deployment.yaml

# Deploy monitoring
kubectl apply -f k8s/monitoring/prometheus-config.yaml
```

### Systemd Services

Create systemd service files for production servers:

**Worker Service** (`/etc/systemd/system/celery-worker.service`):
```ini
[Unit]
Description=Celery Worker for Taxja
After=network.target redis.service postgresql.service

[Service]
Type=forking
User=taxja
Group=taxja
WorkingDirectory=/opt/taxja/backend
Environment="PATH=/opt/taxja/venv/bin"
ExecStart=/opt/taxja/venv/bin/celery -A app.celery_app worker --loglevel=info --pidfile=/var/run/celery/worker.pid
ExecStop=/bin/kill -s TERM $MAINPID
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Beat Service** (`/etc/systemd/system/celery-beat.service`):
```ini
[Unit]
Description=Celery Beat for Taxja
After=network.target redis.service

[Service]
Type=simple
User=taxja
Group=taxja
WorkingDirectory=/opt/taxja/backend
Environment="PATH=/opt/taxja/venv/bin"
ExecStart=/opt/taxja/venv/bin/celery -A app.celery_app beat --loglevel=info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start services:
```bash
sudo systemctl enable celery-worker celery-beat
sudo systemctl start celery-worker celery-beat
sudo systemctl status celery-worker celery-beat
```

## Security Considerations

1. **Redis Security**:
   - Use password authentication: `redis-cli CONFIG SET requirepass "strong_password"`
   - Bind to localhost only: `bind 127.0.0.1`
   - Use TLS for production: `tls-port 6380`

2. **Flower Security**:
   - Enable basic auth: `FLOWER_BASIC_AUTH=admin:password`
   - Use HTTPS in production
   - Restrict access with firewall rules

3. **Task Security**:
   - Validate all task inputs
   - Use ownership checks for user-specific operations
   - Log all task executions for audit trail

## Performance Tuning

### Worker Configuration

```bash
# Increase concurrency for CPU-bound tasks
celery -A app.celery_app worker --concurrency=8

# Use gevent for I/O-bound tasks
celery -A app.celery_app worker --pool=gevent --concurrency=100

# Optimize prefetch multiplier
celery -A app.celery_app worker --prefetch-multiplier=4
```

### Redis Configuration

```ini
# /etc/redis/redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru
save ""  # Disable RDB snapshots for better performance
appendonly yes  # Enable AOF for durability
```

### Database Connection Pooling

```python
# app/db/session.py
engine = create_engine(
    DATABASE_URL,
    pool_size=20,  # Increase pool size
    max_overflow=40,
    pool_pre_ping=True,
    pool_recycle=3600
)
```

## Maintenance

### Daily Tasks

- [ ] Check worker status: `celery -A app.celery_app inspect active`
- [ ] Review error logs: `grep ERROR /var/log/celery/*.log`
- [ ] Monitor task failure rate in Grafana

### Weekly Tasks

- [ ] Clean up old task results: `celery -A app.celery_app purge`
- [ ] Review slow tasks in Flower
- [ ] Check Redis memory usage: `redis-cli INFO memory`

### Monthly Tasks

- [ ] Review and optimize database queries
- [ ] Update Celery and dependencies
- [ ] Review and adjust worker concurrency

### Year-End Tasks (December)

- [ ] Verify annual depreciation schedule is active
- [ ] Test manual trigger: `celery -A app.celery_app call property.generate_annual_depreciation`
- [ ] Ensure monitoring alerts are configured
- [ ] Verify email notifications are working
- [ ] Check database has sufficient space
- [ ] Review task timeout settings

## Support

For issues or questions:
- Check logs: `docker-compose -f docker-compose.celery.yml logs`
- Run tests: `python test_celery_annual_depreciation.py`
- Review monitoring: http://localhost:5555 (Flower)
- Check metrics: http://localhost:8000/metrics

---

**Last Updated**: 2026-03-08
**Version**: 1.0
