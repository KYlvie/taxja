# Property Management Migration Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying the property management feature migrations to staging and production environments. Follow these procedures to ensure a safe, successful deployment.

## Migration Overview

The property management feature consists of 8 migrations:

| Migration | Description | Risk Level | Estimated Time |
|-----------|-------------|------------|----------------|
| 002 | Add properties table | Low | 1-2 seconds |
| 003 | Add property_id to transactions | Low | 2-5 seconds |
| 004 | Add property_loans table | Low | 1-2 seconds |
| 005 | Add historical_import tables | Low | 1-2 seconds |
| 006 | Add performance indexes | Medium | 5-30 seconds* |
| 007 | Increase column sizes for encryption | Low | 2-5 seconds |
| 008 | Encrypt existing property addresses | High | Varies** |
| 009 | Add audit_logs table | Low | 1-2 seconds |

\* Time depends on existing data volume in properties and transactions tables  
\** Time depends on number of existing properties (if any)

## Pre-Deployment Checklist

### 1. Code Review and Testing

- [ ] All migration files reviewed and approved
- [ ] Migrations tested on clean database
- [ ] Migrations tested with sample data
- [ ] Rollback procedures tested
- [ ] Application code compatible with new schema
- [ ] All unit tests passing
- [ ] All integration tests passing
- [ ] Property-based tests passing

### 2. Documentation

- [ ] Migration test guide reviewed
- [ ] Rollback procedures documented
- [ ] Deployment guide reviewed (this document)
- [ ] API documentation updated
- [ ] User documentation prepared

### 3. Environment Preparation

- [ ] Staging environment ready
- [ ] Production backup schedule confirmed
- [ ] Maintenance window scheduled
- [ ] Stakeholders notified
- [ ] Rollback plan approved
- [ ] Emergency contacts confirmed

### 4. Database Preparation

- [ ] Database backup tested and verified
- [ ] Disk space checked (at least 20% free)
- [ ] Database performance baseline recorded
- [ ] Connection pool settings reviewed
- [ ] Query timeout settings reviewed

## Staging Deployment

### Phase 1: Preparation

#### Step 1.1: Backup Staging Database

```bash
# Create backup directory
mkdir -p /backup/staging/$(date +%Y%m%d)

# Backup database
pg_dump -h staging-db-host -U taxja_user -d taxja_staging \
  -F c -f /backup/staging/$(date +%Y%m%d)/taxja_staging_pre_property_$(date +%Y%m%d_%H%M%S).dump

# Verify backup
BACKUP_FILE=$(ls -t /backup/staging/$(date +%Y%m%d)/*.dump | head -1)
pg_restore --list $BACKUP_FILE | head -20

# Check backup size
ls -lh $BACKUP_FILE
```

#### Step 1.2: Check Current State

```bash
# Set environment
export DATABASE_URL="postgresql://taxja_user:password@staging-db-host:5432/taxja_staging"

# Check current migration version
cd backend
alembic current

# Check database size
psql -h staging-db-host -d taxja_staging -c "
SELECT
    pg_size_pretty(pg_database_size('taxja_staging')) as database_size,
    pg_size_pretty(pg_total_relation_size('transactions')) as transactions_size,
    pg_size_pretty(pg_total_relation_size('users')) as users_size;
"

# Check table counts
psql -h staging-db-host -d taxja_staging -c "
SELECT 'users' as table_name, COUNT(*) as row_count FROM users
UNION ALL
SELECT 'transactions', COUNT(*) FROM transactions
UNION ALL
SELECT 'documents', COUNT(*) FROM documents;
"
```

#### Step 1.3: Record Performance Baseline

```bash
# Record query performance
psql -h staging-db-host -d taxja_staging -c "
SELECT
    schemaname,
    tablename,
    seq_scan,
    seq_tup_read,
    idx_scan,
    idx_tup_fetch
FROM pg_stat_user_tables
WHERE tablename IN ('users', 'transactions', 'documents')
ORDER BY seq_scan DESC;
" > staging_baseline_stats.txt
```

### Phase 2: Migration Execution

#### Step 2.1: Stop Application (Optional)

For staging, you may choose to keep the application running if it's not critical.

```bash
# Stop application servers (optional)
ssh staging-app-server "systemctl stop taxja-backend"

# Or using Docker
ssh staging-app-server "cd /opt/taxja && docker-compose stop backend"
```

#### Step 2.2: Apply Migrations

```bash
# Navigate to backend directory
cd backend

# Apply migrations one at a time with verification
echo "Applying migration 002: Add properties table"
alembic upgrade 002
psql -h staging-db-host -d taxja_staging -c "\d properties"

echo "Applying migration 003: Add property_id to transactions"
alembic upgrade 003
psql -h staging-db-host -d taxja_staging -c "\d transactions" | grep property_id

echo "Applying migration 004: Add property_loans table"
alembic upgrade 004
psql -h staging-db-host -d taxja_staging -c "\d property_loans"

echo "Applying migration 005: Add historical_import tables"
alembic upgrade 005

echo "Applying migration 006: Add performance indexes"
alembic upgrade 006
psql -h staging-db-host -d taxja_staging -c "\di" | grep -E "idx_properties|idx_transactions"

echo "Applying migration 007: Increase column sizes for encryption"
alembic upgrade 007
psql -h staging-db-host -d taxja_staging -c "\d properties" | grep -E "address|street|city"

echo "Applying migration 008: Encrypt existing property addresses"
alembic upgrade 008

echo "Applying migration 009: Add audit_logs table"
alembic upgrade 009
psql -h staging-db-host -d taxja_staging -c "\d audit_logs"

# Verify final state
alembic current
```

#### Step 2.3: Verify Migration

```bash
# Run verification script
python backend/alembic/verify_property_migration.py --database taxja_staging

# Check for errors
echo $?
# Expected: 0 (success)
```

### Phase 3: Application Deployment

#### Step 3.1: Deploy New Application Version

```bash
# Pull latest code
ssh staging-app-server "cd /opt/taxja && git pull origin main"

# Build new Docker image
ssh staging-app-server "cd /opt/taxja && docker-compose build backend"

# Start application
ssh staging-app-server "cd /opt/taxja && docker-compose up -d backend"

# Or using systemd
ssh staging-app-server "systemctl start taxja-backend"
```

#### Step 3.2: Verify Application

```bash
# Wait for application to start
sleep 10

# Test health endpoint
curl http://staging-app-server:8000/health

# Test property endpoints
TOKEN=$(curl -X POST http://staging-app-server:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass"}' \
  | jq -r '.access_token')

# Test property listing (should return empty array for new feature)
curl -X GET http://staging-app-server:8000/api/v1/properties \
  -H "Authorization: Bearer $TOKEN"

# Test property creation
curl -X POST http://staging-app-server:8000/api/v1/properties \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "property_type": "rental",
    "street": "Teststraße 1",
    "city": "Wien",
    "postal_code": "1010",
    "purchase_date": "2020-01-01",
    "purchase_price": 300000.00,
    "building_value": 240000.00,
    "construction_year": 1990
  }'
```

### Phase 4: Staging Validation

#### Step 4.1: Run Integration Tests

```bash
# Run backend integration tests
cd backend
pytest tests/integration/test_property_*.py -v

# Run end-to-end tests
cd ../frontend
npm run test:e2e -- --grep "property"
```

#### Step 4.2: Manual Testing

Test the following scenarios:

1. **Property Registration**
   - [ ] Create rental property
   - [ ] Create owner-occupied property
   - [ ] Create mixed-use property
   - [ ] Verify validation errors for invalid data

2. **Property Management**
   - [ ] List properties
   - [ ] View property details
   - [ ] Update property
   - [ ] Archive property

3. **Property-Transaction Linking**
   - [ ] Link transaction to property
   - [ ] Unlink transaction from property
   - [ ] View property transactions

4. **Historical Depreciation**
   - [ ] Preview historical depreciation
   - [ ] Backfill historical depreciation
   - [ ] Verify depreciation transactions created

5. **Performance**
   - [ ] Property list loads in < 1 second
   - [ ] Property detail loads in < 500ms
   - [ ] Transaction linking completes in < 500ms

#### Step 4.3: Monitor Performance

```bash
# Monitor application logs
ssh staging-app-server "tail -f /var/log/taxja/app.log | grep -i property"

# Monitor database performance
psql -h staging-db-host -d taxja_staging -c "
SELECT
    schemaname,
    tablename,
    seq_scan,
    idx_scan,
    idx_scan::float / NULLIF(seq_scan + idx_scan, 0) as idx_scan_ratio
FROM pg_stat_user_tables
WHERE tablename IN ('properties', 'transactions')
ORDER BY seq_scan DESC;
"

# Check slow queries
psql -h staging-db-host -d taxja_staging -c "
SELECT
    query,
    calls,
    total_time,
    mean_time,
    max_time
FROM pg_stat_statements
WHERE query LIKE '%properties%'
ORDER BY mean_time DESC
LIMIT 10;
"
```

### Phase 5: Staging Sign-Off

Before proceeding to production, obtain sign-off from:

- [ ] Development Team Lead
- [ ] QA Team Lead
- [ ] Product Manager
- [ ] Database Administrator
- [ ] DevOps Team Lead

## Production Deployment

### Phase 1: Pre-Deployment

#### Step 1.1: Schedule Maintenance Window

```
Recommended maintenance window:
- Duration: 30 minutes
- Time: Low-traffic period (e.g., Sunday 2:00 AM - 2:30 AM CET)
- Notification: 48 hours advance notice to users
```

#### Step 1.2: Notify Stakeholders

Send notification email:

```
Subject: Scheduled Maintenance - Property Management Feature Deployment

Dear Taxja Users,

We will be performing scheduled maintenance to deploy the new Property 
Management feature on [DATE] from [START_TIME] to [END_TIME] CET.

During this time:
- The application will be unavailable
- No data will be lost
- All existing features will continue to work after maintenance

The new Property Management feature will enable landlords to:
- Track rental properties
- Calculate depreciation (AfA) automatically
- Link transactions to properties
- Generate property reports

We apologize for any inconvenience.

Best regards,
Taxja Team
```

#### Step 1.3: Prepare Rollback Plan

Review and confirm rollback procedures:

- [ ] Rollback procedure document reviewed
- [ ] Rollback tested on staging
- [ ] Rollback team identified and briefed
- [ ] Emergency contacts confirmed

### Phase 2: Production Backup

#### Step 2.1: Create Full Backup

```bash
# Create backup directory
mkdir -p /backup/production/$(date +%Y%m%d)

# Create full database backup
pg_dump -h production-db-host -U taxja_user -d taxja_production \
  -F c -f /backup/production/$(date +%Y%m%d)/taxja_production_pre_property_$(date +%Y%m%d_%H%M%S).dump

# Verify backup
BACKUP_FILE=$(ls -t /backup/production/$(date +%Y%m%d)/*.dump | head -1)
pg_restore --list $BACKUP_FILE | head -20

# Check backup size
ls -lh $BACKUP_FILE

# Copy backup to secure location
cp $BACKUP_FILE /backup/critical/
aws s3 cp $BACKUP_FILE s3://taxja-backups/production/$(date +%Y%m%d)/
```

#### Step 2.2: Verify Backup

```bash
# Test restore to temporary database (optional but recommended)
createdb taxja_backup_test
pg_restore -d taxja_backup_test $BACKUP_FILE

# Verify data
psql -d taxja_backup_test -c "SELECT COUNT(*) FROM users;"
psql -d taxja_backup_test -c "SELECT COUNT(*) FROM transactions;"

# Drop test database
dropdb taxja_backup_test
```

### Phase 3: Production Migration

#### Step 3.1: Enable Maintenance Mode

```bash
# Enable maintenance mode in application
ssh production-app-server "touch /opt/taxja/MAINTENANCE_MODE"

# Or update load balancer to show maintenance page
aws elb modify-target-group --target-group-arn <arn> --health-check-path /maintenance
```

#### Step 3.2: Stop Application Servers

```bash
# Stop all application servers
for server in app-server-1 app-server-2 app-server-3; do
    ssh $server "systemctl stop taxja-backend"
done

# Verify no active connections
psql -h production-db-host -d taxja_production -c "
SELECT COUNT(*) as active_connections
FROM pg_stat_activity
WHERE datname = 'taxja_production'
AND application_name != 'psql'
AND state = 'active';
"
# Expected: 0
```

#### Step 3.3: Record Pre-Migration State

```bash
# Record current state
psql -h production-db-host -d taxja_production -c "
SELECT
    'users' as table_name,
    COUNT(*) as row_count,
    pg_size_pretty(pg_total_relation_size('users')) as size
FROM users
UNION ALL
SELECT 'transactions', COUNT(*), pg_size_pretty(pg_total_relation_size('transactions'))
FROM transactions
UNION ALL
SELECT 'documents', COUNT(*), pg_size_pretty(pg_total_relation_size('documents'))
FROM documents;
" > production_pre_migration_state.txt

# Record current migration version
cd backend
alembic current > production_pre_migration_version.txt
```

#### Step 3.4: Apply Migrations

```bash
# Set environment
export DATABASE_URL="postgresql://taxja_user:password@production-db-host:5432/taxja_production"

# Apply migrations with timing
cd backend

echo "Starting migration at $(date)"
START_TIME=$(date +%s)

# Apply all migrations at once
alembic upgrade head

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
echo "Migration completed in $DURATION seconds"

# Verify final state
alembic current
```

#### Step 3.5: Verify Migration

```bash
# Run verification script
python backend/alembic/verify_property_migration.py --database taxja_production

# Check for errors
if [ $? -eq 0 ]; then
    echo "✓ Migration verification passed"
else
    echo "✗ Migration verification failed - initiating rollback"
    alembic downgrade 001
    exit 1
fi

# Verify data integrity
psql -h production-db-host -d taxja_production -c "
SELECT
    'users' as table_name,
    COUNT(*) as row_count
FROM users
UNION ALL
SELECT 'transactions', COUNT(*) FROM transactions
UNION ALL
SELECT 'documents', COUNT(*) FROM documents;
"

# Compare with pre-migration state
diff production_pre_migration_state.txt <(psql -h production-db-host -d taxja_production -c "...")
```

### Phase 4: Application Deployment

#### Step 4.1: Deploy New Application Version

```bash
# Deploy to all application servers
for server in app-server-1 app-server-2 app-server-3; do
    echo "Deploying to $server"
    ssh $server "cd /opt/taxja && git pull origin main"
    ssh $server "cd /opt/taxja && docker-compose build backend"
    ssh $server "cd /opt/taxja && docker-compose up -d backend"
done

# Wait for applications to start
sleep 30
```

#### Step 4.2: Verify Application Health

```bash
# Check health endpoints
for server in app-server-1 app-server-2 app-server-3; do
    echo "Checking $server"
    curl -f http://$server:8000/health || echo "✗ $server health check failed"
done

# Test property endpoints
TOKEN=$(curl -X POST http://production-app-server:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@taxja.com","password":"<admin-password>"}' \
  | jq -r '.access_token')

curl -X GET http://production-app-server:8000/api/v1/properties \
  -H "Authorization: Bearer $TOKEN"
```

#### Step 4.3: Disable Maintenance Mode

```bash
# Disable maintenance mode
ssh production-app-server "rm /opt/taxja/MAINTENANCE_MODE"

# Or update load balancer
aws elb modify-target-group --target-group-arn <arn> --health-check-path /health
```

### Phase 5: Post-Deployment Monitoring

#### Step 5.1: Monitor Application Logs

```bash
# Monitor for errors
for server in app-server-1 app-server-2 app-server-3; do
    ssh $server "tail -f /var/log/taxja/app.log | grep -i 'error\|property'" &
done

# Monitor for 15 minutes
sleep 900
```

#### Step 5.2: Monitor Database Performance

```bash
# Monitor query performance
watch -n 10 "psql -h production-db-host -d taxja_production -c \"
SELECT
    schemaname,
    tablename,
    seq_scan,
    idx_scan,
    n_tup_ins,
    n_tup_upd,
    n_tup_del
FROM pg_stat_user_tables
WHERE tablename IN ('properties', 'transactions')
ORDER BY seq_scan DESC;
\""

# Monitor slow queries
psql -h production-db-host -d taxja_production -c "
SELECT
    query,
    calls,
    mean_time,
    max_time
FROM pg_stat_statements
WHERE query LIKE '%properties%'
AND mean_time > 100
ORDER BY mean_time DESC
LIMIT 10;
"
```

#### Step 5.3: Monitor Application Metrics

```bash
# Monitor response times
curl http://production-app-server:8000/metrics | grep -E "http_request_duration|property"

# Monitor error rates
curl http://production-app-server:8000/metrics | grep -E "http_requests_total|error"

# Check Prometheus/Grafana dashboards
# - Response time percentiles (p50, p95, p99)
# - Error rate
# - Database connection pool usage
# - Memory usage
```

### Phase 6: Post-Deployment Validation

#### Step 6.1: Smoke Tests

```bash
# Run automated smoke tests
cd backend
pytest tests/smoke/test_property_smoke.py -v

# Test critical user flows
# 1. User login
# 2. Transaction listing
# 3. Document upload
# 4. Property creation (new feature)
```

#### Step 6.2: User Acceptance

- [ ] Notify beta users that property feature is available
- [ ] Monitor user feedback channels
- [ ] Track feature adoption metrics
- [ ] Monitor support tickets for property-related issues

### Phase 7: Post-Deployment Communication

#### Step 7.1: Send Completion Notification

```
Subject: Maintenance Complete - Property Management Feature Now Available

Dear Taxja Users,

The scheduled maintenance has been completed successfully. The application 
is now fully operational.

New Feature: Property Management
Landlords can now:
✓ Register rental properties
✓ Track property expenses
✓ Calculate depreciation (AfA) automatically
✓ Link transactions to properties
✓ Generate property reports

To get started, visit the Properties section in your dashboard.

Thank you for your patience.

Best regards,
Taxja Team
```

#### Step 7.2: Update Documentation

- [ ] Update user guide with property management instructions
- [ ] Update API documentation
- [ ] Update changelog
- [ ] Update release notes

## Rollback Procedure

If critical issues are discovered during or after deployment:

### Immediate Rollback

```bash
# 1. Stop application servers
for server in app-server-1 app-server-2 app-server-3; do
    ssh $server "systemctl stop taxja-backend"
done

# 2. Rollback database migrations
cd backend
alembic downgrade 001

# 3. Deploy previous application version
for server in app-server-1 app-server-2 app-server-3; do
    ssh $server "cd /opt/taxja && git checkout <previous-version-tag>"
    ssh $server "cd /opt/taxja && docker-compose up -d backend"
done

# 4. Verify rollback
alembic current
curl http://production-app-server:8000/health

# 5. Notify stakeholders
```

See [PROPERTY_ROLLBACK_PROCEDURES.md](./PROPERTY_ROLLBACK_PROCEDURES.md) for detailed rollback instructions.

## Success Criteria

Deployment is considered successful when:

- [ ] All migrations applied successfully
- [ ] Verification script passes
- [ ] Application health checks pass
- [ ] No errors in application logs (15 min monitoring)
- [ ] Database performance within acceptable limits
- [ ] Smoke tests pass
- [ ] Property endpoints respond correctly
- [ ] No increase in error rate
- [ ] Response times within SLA (p95 < 500ms)

## Troubleshooting

### Issue: Migration Takes Too Long

**Symptom**: Migration 006 (indexes) takes longer than expected

**Action**:
```bash
# Check index creation progress
psql -h production-db-host -d taxja_production -c "
SELECT
    now()::time,
    query,
    state,
    wait_event_type,
    wait_event
FROM pg_stat_activity
WHERE query LIKE '%CREATE INDEX%';
"

# If taking too long (> 5 minutes), consider:
# 1. Let it complete (indexes are important for performance)
# 2. Or cancel and create indexes CONCURRENTLY later
```

### Issue: Application Won't Start

**Symptom**: Health check fails after deployment

**Action**:
```bash
# Check application logs
ssh production-app-server "tail -100 /var/log/taxja/app.log"

# Check database connectivity
ssh production-app-server "psql -h production-db-host -d taxja_production -c 'SELECT 1;'"

# Verify environment variables
ssh production-app-server "docker exec taxja-backend env | grep DATABASE"

# If issue persists, initiate rollback
```

### Issue: High Error Rate After Deployment

**Symptom**: Error rate increases significantly

**Action**:
```bash
# Check error logs
ssh production-app-server "tail -100 /var/log/taxja/app.log | grep ERROR"

# Check database errors
psql -h production-db-host -d taxja_production -c "
SELECT * FROM pg_stat_database_conflicts WHERE datname = 'taxja_production';
"

# If errors are property-related and critical, initiate rollback
# If errors are minor, monitor and fix forward
```

## Contact Information

### Deployment Team

- **Deployment Lead**: devops-lead@taxja.com / +43 XXX XXXXXXX
- **Database Administrator**: dba@taxja.com / +43 XXX XXXXXXX
- **Backend Lead**: backend-lead@taxja.com / +43 XXX XXXXXXX
- **On-Call Engineer**: oncall@taxja.com / +43 XXX XXXXXXX

### Escalation Path

1. On-Call Engineer (immediate issues)
2. Deployment Lead (coordination)
3. CTO (critical decisions)

## Document Version

- **Version**: 1.0
- **Last Updated**: 2026-03-08
- **Author**: DevOps Team
- **Status**: Ready for Production Use
- **Next Review**: After first production deployment
