# Staging Deployment Guide - Property Asset Management

## Overview

This guide provides step-by-step instructions for deploying the Property Asset Management feature to the staging environment. The deployment includes database migrations, application updates, and comprehensive verification procedures.

## Feature Summary

The Property Asset Management feature enables:
- Property registration and tracking for landlords
- Automatic depreciation (AfA) calculation per Austrian tax law
- Property-transaction linking
- Historical depreciation backfill
- Property reports and analytics
- E1/Bescheid integration
- Multi-property portfolio management

## Prerequisites

### Required Tools
- Docker and Docker Compose
- Git
- Python 3.11+
- PostgreSQL client tools
- curl or similar HTTP client

### Access Requirements
- Staging environment access
- Database credentials
- Git repository access
- Sufficient disk space (>20% free)

## Deployment Methods

### Method 1: Automated Deployment (Recommended)

Use the automated deployment script for a streamlined process:

```bash
# Navigate to project root
cd taxja

# Make script executable (if needed)
chmod +x backend/scripts/staging_deployment.sh

# Run deployment script
./backend/scripts/staging_deployment.sh
```

The script will:
1. Run pre-flight checks
2. Create database backup
3. Check current state
4. Build Docker images
5. Stop application services
6. Apply database migrations
7. Verify migrations
8. Start services
9. Run health checks
10. Generate deployment log

**Follow the prompts** and confirm each phase before proceeding.

### Method 2: Manual Deployment

For more control or troubleshooting, follow the manual steps below.

## Manual Deployment Steps

### Phase 1: Pre-Deployment (15 minutes)

#### 1.1 Verify Environment

```bash
# Check Docker
docker --version
docker-compose --version

# Check disk space
df -h

# Check services are running
docker-compose ps
```

#### 1.2 Create Backup

```bash
# Create backup directory
mkdir -p backup/staging/$(date +%Y%m%d)

# Backup database
docker-compose exec postgres pg_dump -U taxja -d taxja > \
  backup/staging/$(date +%Y%m%d)/taxja_staging_pre_property_$(date +%Y%m%d_%H%M%S).sql

# Verify backup
ls -lh backup/staging/$(date +%Y%m%d)/
```

**CRITICAL**: Verify backup was created successfully before proceeding!

#### 1.3 Check Current State

```bash
# Check migration version
cd backend
alembic current

# Check database size
docker-compose exec postgres psql -U taxja -d taxja -c "
SELECT
    pg_size_pretty(pg_database_size('taxja')) as database_size,
    pg_size_pretty(pg_total_relation_size('transactions')) as transactions_size;
"

# Check table counts
docker-compose exec postgres psql -U taxja -d taxja -c "
SELECT 'users' as table, COUNT(*) FROM users
UNION ALL SELECT 'transactions', COUNT(*) FROM transactions;
"

cd ..
```

### Phase 2: Build and Deploy (20 minutes)

#### 2.1 Pull Latest Code

```bash
# Ensure on correct branch
git status
git pull origin main

# Verify commit
git log -1 --oneline
```

#### 2.2 Build Docker Images

```bash
# Build backend
docker-compose build backend

# Build frontend
docker-compose build frontend

# Verify images
docker images | grep taxja
```

#### 2.3 Stop Application Services

```bash
# Stop only application services (keep data services running)
docker-compose stop backend frontend celery-worker

# Verify stopped
docker-compose ps
```

### Phase 3: Database Migration (10 minutes)

#### 3.1 Apply Migrations

```bash
cd backend

# Apply all property migrations
alembic upgrade head

# Verify final state
alembic current
```

Expected output: Should show migration 009 or later as current.

#### 3.2 Verify Migration

```bash
# Check tables exist
docker-compose exec postgres psql -U taxja -d taxja -c "\dt" | grep -E "properties|audit_logs"

# Check indexes
docker-compose exec postgres psql -U taxja -d taxja -c "\di" | grep -E "idx_properties|idx_transactions"

# Verify constraints
docker-compose exec postgres psql -U taxja -d taxja -c "
SELECT conname, contype
FROM pg_constraint
WHERE conrelid = 'properties'::regclass;
"

cd ..
```

### Phase 4: Start Services (10 minutes)

#### 4.1 Start All Services

```bash
# Start services
docker-compose up -d

# Wait for services to be ready
sleep 30

# Check status
docker-compose ps
```

All services should show "Up" status.

#### 4.2 Verify Application Health

```bash
# Check backend health
curl http://localhost:8000/health

# Expected: {"status":"ok"} or similar

# Check API docs
curl http://localhost:8000/docs

# Expected: HTML response

# Check frontend
curl http://localhost:5173

# Expected: HTML response
```

### Phase 5: Verification (30 minutes)

#### 5.1 Run Automated Verification

```bash
# Run verification script
cd backend
python scripts/verify_staging_deployment.py

cd ..
```

Expected: All checks should pass.

#### 5.2 Manual API Testing

```bash
# Get auth token (replace with actual test user credentials)
TOKEN=$(curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass"}' \
  | jq -r '.access_token')

# Test property listing (should return empty array for new feature)
curl -X GET http://localhost:8000/api/v1/properties \
  -H "Authorization: Bearer $TOKEN"

# Test property creation
curl -X POST http://localhost:8000/api/v1/properties \
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

# Expected: Property created with ID
```

#### 5.3 Frontend Testing

Open browser and navigate to `http://localhost:5173`

Test the following:
1. Login with test user
2. Navigate to Properties page
3. Create new property
4. View property list
5. Click property to view details
6. Edit property
7. Link transaction to property
8. Preview historical depreciation
9. Backfill historical depreciation

#### 5.4 Monitor Logs

```bash
# Monitor backend logs for errors
docker-compose logs -f backend | grep -i "error\|property"

# Monitor for 5-10 minutes
# Press Ctrl+C to stop
```

### Phase 6: Performance Testing (15 minutes)

#### 6.1 Database Performance

```bash
# Check index usage
docker-compose exec postgres psql -U taxja -d taxja -c "
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
```

Index scan ratio should be > 0.8 for good performance.

#### 6.2 API Response Times

```bash
# Test property list performance
time curl -X GET http://localhost:8000/api/v1/properties \
  -H "Authorization: Bearer $TOKEN"

# Expected: < 1 second

# Test property detail performance
PROPERTY_ID="<property-id-from-previous-test>"
time curl -X GET http://localhost:8000/api/v1/properties/$PROPERTY_ID \
  -H "Authorization: Bearer $TOKEN"

# Expected: < 500ms
```

## Post-Deployment Checklist

Use the comprehensive checklist:

```bash
# Open checklist
cat backend/docs/STAGING_DEPLOYMENT_CHECKLIST.md
```

Complete all items in the checklist and obtain sign-offs.

## Rollback Procedure

If critical issues are discovered:

### Quick Rollback

```bash
# 1. Stop services
docker-compose stop backend frontend celery-worker

# 2. Rollback migrations
cd backend
alembic downgrade 001

# 3. Restore database
docker-compose exec -T postgres psql -U taxja -d taxja < \
  backup/staging/YYYYMMDD/taxja_staging_pre_property_*.sql

# 4. Restart with previous version
git checkout <previous-commit>
docker-compose build backend frontend
docker-compose up -d

# 5. Verify
alembic current
curl http://localhost:8000/health

cd ..
```

## Troubleshooting

### Issue: Migration Fails

**Symptom**: Alembic upgrade command fails

**Solution**:
```bash
# Check current migration state
alembic current

# Check migration history
alembic history

# Try upgrading one migration at a time
alembic upgrade +1

# Check database logs
docker-compose logs postgres
```

### Issue: Service Won't Start

**Symptom**: Docker container exits immediately

**Solution**:
```bash
# Check logs
docker-compose logs backend

# Check database connectivity
docker-compose exec backend python -c "
from sqlalchemy import create_engine
engine = create_engine('postgresql://taxja:taxja_password@postgres:5432/taxja')
with engine.connect() as conn:
    print('Connected!')
"

# Rebuild image
docker-compose build --no-cache backend
docker-compose up -d backend
```

### Issue: API Returns 500 Errors

**Symptom**: Property endpoints return internal server errors

**Solution**:
```bash
# Check backend logs
docker-compose logs backend | tail -50

# Check database connection
docker-compose exec postgres psql -U taxja -d taxja -c "SELECT 1;"

# Verify migrations applied
docker-compose exec postgres psql -U taxja -d taxja -c "\dt" | grep properties

# Restart backend
docker-compose restart backend
```

### Issue: Frontend Can't Connect to Backend

**Symptom**: Frontend shows connection errors

**Solution**:
```bash
# Check CORS configuration
docker-compose exec backend env | grep CORS

# Verify backend is accessible
curl http://localhost:8000/health

# Check frontend environment
docker-compose exec frontend env | grep VITE_API_URL

# Restart frontend
docker-compose restart frontend
```

## Success Criteria

Deployment is successful when:

- [x] All migrations applied successfully
- [x] Verification script passes all checks
- [x] Application health checks pass
- [x] No errors in logs (15 min monitoring)
- [x] Property endpoints respond correctly
- [x] Frontend UI works correctly
- [x] Response times within SLA (p95 < 500ms)
- [x] All manual test scenarios pass
- [x] Database performance acceptable
- [x] No data integrity issues

## Next Steps

After successful staging deployment:

1. **Monitor for 24-48 hours**
   - Check logs daily
   - Monitor error rates
   - Track performance metrics

2. **User Acceptance Testing**
   - Invite beta users to test
   - Collect feedback
   - Document issues

3. **Address Issues**
   - Fix any bugs found
   - Optimize performance if needed
   - Update documentation

4. **Prepare for Production**
   - Schedule production deployment
   - Create production deployment checklist
   - Notify stakeholders
   - Plan maintenance window

## Support

For issues or questions:
- Check troubleshooting section above
- Review deployment logs
- Contact DevOps team
- Escalate to development team if needed

## Documentation References

- [Staging Deployment Checklist](backend/docs/STAGING_DEPLOYMENT_CHECKLIST.md)
- [Property Migration Deployment Guide](backend/alembic/versions/PROPERTY_MIGRATION_DEPLOYMENT_GUIDE.md)
- [Property Migration Test Guide](backend/alembic/versions/PROPERTY_MIGRATION_TEST_GUIDE.md)
- [Property Rollback Procedures](backend/alembic/versions/PROPERTY_ROLLBACK_PROCEDURES.md)

---

**Document Version**: 1.0  
**Last Updated**: 2026-03-08  
**Status**: Ready for Use
