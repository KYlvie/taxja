# Staging Deployment Checklist - Property Asset Management

## Deployment Date: 2026-03-08
## Feature: Property Asset Management (Phases A-E)
## Status: Ready for Staging Deployment

---

## Pre-Deployment Checklist

### 1. Code Readiness
- [x] All Phase A-E tasks completed
- [x] All unit tests passing
- [x] All integration tests passing
- [x] Property-based tests passing
- [x] Code reviewed and approved
- [x] Documentation complete

### 2. Database Migrations
- [x] 8 property migrations created (002-009)
- [x] Migration test guide reviewed
- [x] Rollback procedures documented
- [x] Migrations tested on clean database
- [x] Migrations tested with sample data

### 3. Environment Preparation
- [ ] Staging environment accessible
- [ ] Staging database backup created
- [ ] Disk space verified (>20% free)
- [ ] Docker images built
- [ ] Environment variables configured

### 4. Stakeholder Communication
- [ ] Deployment scheduled
- [ ] Team notified
- [ ] Rollback plan approved

---

## Staging Deployment Steps

### Phase 1: Environment Setup (15 minutes)

#### Step 1.1: Verify Staging Environment
```bash
# Check Docker is running
docker --version
docker-compose --version

# Check available disk space
df -h

# Verify network connectivity
ping staging-db-host
```

**Status**: [ ] Complete

#### Step 1.2: Backup Staging Database
```bash
# Create backup directory
mkdir -p backup/staging/$(date +%Y%m%d)

# Backup current staging database
docker-compose exec postgres pg_dump -U taxja -d taxja > \
  backup/staging/$(date +%Y%m%d)/taxja_staging_pre_property_$(date +%Y%m%d_%H%M%S).sql

# Verify backup
ls -lh backup/staging/$(date +%Y%m%d)/
```

**Status**: [ ] Complete  
**Backup Location**: ___________________________  
**Backup Size**: ___________________________

#### Step 1.3: Check Current State
```bash
# Check current migration version
cd backend
alembic current

# Check database size
docker-compose exec postgres psql -U taxja -d taxja -c "
SELECT
    pg_size_pretty(pg_database_size('taxja')) as database_size,
    pg_size_pretty(pg_total_relation_size('transactions')) as transactions_size,
    pg_size_pretty(pg_total_relation_size('users')) as users_size;
"

# Check table counts
docker-compose exec postgres psql -U taxja -d taxja -c "
SELECT 'users' as table_name, COUNT(*) as row_count FROM users
UNION ALL
SELECT 'transactions', COUNT(*) FROM transactions
UNION ALL
SELECT 'documents', COUNT(*) FROM documents;
"
```

**Status**: [ ] Complete  
**Current Migration**: ___________________________  
**Database Size**: ___________________________  
**User Count**: ___________________________  
**Transaction Count**: ___________________________

---

### Phase 2: Build and Deploy (20 minutes)

#### Step 2.1: Pull Latest Code
```bash
# Ensure on correct branch
git status
git pull origin main

# Verify latest commit
git log -1 --oneline
```

**Status**: [ ] Complete  
**Commit Hash**: ___________________________

#### Step 2.2: Build Docker Images
```bash
# Build backend image
docker-compose build backend

# Build frontend image
docker-compose build frontend

# Verify images
docker images | grep taxja
```

**Status**: [ ] Complete  
**Backend Image**: ___________________________  
**Frontend Image**: ___________________________

#### Step 2.3: Stop Current Services
```bash
# Stop application services (keep data services running)
docker-compose stop backend frontend celery-worker

# Verify stopped
docker-compose ps
```

**Status**: [ ] Complete  
**Stopped At**: ___________________________

---

### Phase 3: Database Migration (10 minutes)

#### Step 3.1: Apply Migrations
```bash
# Set environment
export DATABASE_URL="postgresql://taxja:taxja_password@localhost:5432/taxja"

# Apply migrations one at a time
cd backend

echo "Applying migration 002: Add properties table"
alembic upgrade 002
docker-compose exec postgres psql -U taxja -d taxja -c "\d properties"

echo "Applying migration 003: Add property_id to transactions"
alembic upgrade 003
docker-compose exec postgres psql -U taxja -d taxja -c "\d transactions" | grep property_id

echo "Applying migration 004: Add property_loans table"
alembic upgrade 004

echo "Applying migration 005: Add historical_import tables"
alembic upgrade 005

echo "Applying migration 006: Add performance indexes"
alembic upgrade 006

echo "Applying migration 007: Increase column sizes for encryption"
alembic upgrade 007

echo "Applying migration 008: Encrypt existing property addresses"
alembic upgrade 008

echo "Applying migration 009: Add audit_logs table"
alembic upgrade 009

# Verify final state
alembic current
```

**Status**: [ ] Complete  
**Final Migration**: ___________________________  
**Migration Duration**: ___________________________  
**Any Errors**: ___________________________

#### Step 3.2: Verify Migration
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
```

**Status**: [ ] Complete  
**Tables Created**: ___________________________  
**Indexes Created**: ___________________________

---

### Phase 4: Application Deployment (10 minutes)

#### Step 4.1: Start Services
```bash
# Start all services
docker-compose up -d

# Wait for services to be ready
sleep 30

# Check service status
docker-compose ps
```

**Status**: [ ] Complete  
**All Services Running**: [ ] Yes [ ] No

#### Step 4.2: Verify Application Health
```bash
# Check backend health
curl http://localhost:8000/health

# Check API docs
curl http://localhost:8000/docs

# Check frontend
curl http://localhost:5173
```

**Status**: [ ] Complete  
**Backend Health**: ___________________________  
**Frontend Accessible**: [ ] Yes [ ] No

#### Step 4.3: Test Property Endpoints
```bash
# Get auth token (use test user credentials)
TOKEN=$(curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass"}' \
  | jq -r '.access_token')

# Test property listing (should return empty array)
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
```

**Status**: [ ] Complete  
**Property List Works**: [ ] Yes [ ] No  
**Property Creation Works**: [ ] Yes [ ] No  
**Property ID Created**: ___________________________

---

### Phase 5: Integration Testing (30 minutes)

#### Step 5.1: Manual Testing Scenarios

**Test 1: Property Registration**
- [ ] Create rental property
- [ ] Create owner-occupied property
- [ ] Create mixed-use property
- [ ] Verify validation errors for invalid data

**Test 2: Property Management**
- [ ] List properties
- [ ] View property details
- [ ] Update property
- [ ] Archive property

**Test 3: Property-Transaction Linking**
- [ ] Link transaction to property
- [ ] Unlink transaction from property
- [ ] View property transactions

**Test 4: Historical Depreciation**
- [ ] Preview historical depreciation
- [ ] Backfill historical depreciation
- [ ] Verify depreciation transactions created

**Test 5: Performance**
- [ ] Property list loads in < 1 second
- [ ] Property detail loads in < 500ms
- [ ] Transaction linking completes in < 500ms

#### Step 5.2: Automated Test Execution
```bash
# Run backend integration tests
cd backend
pytest tests/integration/test_property_*.py -v

# Run property-based tests
pytest tests/test_*_properties.py -v

# Run E2E tests (if available)
pytest tests/e2e/test_property_e2e.py -v
```

**Status**: [ ] Complete  
**Tests Passed**: _____ / _____  
**Tests Failed**: _____ / _____  
**Failure Details**: ___________________________

---

### Phase 6: Performance Monitoring (15 minutes)

#### Step 6.1: Monitor Application Logs
```bash
# Monitor backend logs
docker-compose logs -f backend | grep -i "property\|error"

# Monitor for 5 minutes, check for errors
```

**Status**: [ ] Complete  
**Errors Found**: [ ] Yes [ ] No  
**Error Details**: ___________________________

#### Step 6.2: Monitor Database Performance
```bash
# Check query performance
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

# Check table sizes
docker-compose exec postgres psql -U taxja -d taxja -c "
SELECT
    tablename,
    pg_size_pretty(pg_total_relation_size(tablename::regclass)) AS size
FROM pg_tables
WHERE tablename IN ('properties', 'transactions', 'property_loans', 'audit_logs')
ORDER BY pg_total_relation_size(tablename::regclass) DESC;
"
```

**Status**: [ ] Complete  
**Index Usage Ratio**: ___________________________  
**Query Performance**: ___________________________

#### Step 6.3: Load Testing (Optional)
```bash
# Create multiple properties to test performance
for i in {1..50}; do
  curl -X POST http://localhost:8000/api/v1/properties \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
      \"property_type\": \"rental\",
      \"street\": \"Teststraße $i\",
      \"city\": \"Wien\",
      \"postal_code\": \"1010\",
      \"purchase_date\": \"2020-01-01\",
      \"purchase_price\": 300000.00,
      \"building_value\": 240000.00,
      \"construction_year\": 1990
    }"
done

# Test list performance with 50+ properties
time curl -X GET http://localhost:8000/api/v1/properties \
  -H "Authorization: Bearer $TOKEN"
```

**Status**: [ ] Complete  
**List Performance (50 properties)**: ___________________________  
**Acceptable (<1s)**: [ ] Yes [ ] No

---

### Phase 7: Frontend Testing (20 minutes)

#### Step 7.1: Manual UI Testing
- [ ] Navigate to Properties page
- [ ] Create new property via form
- [ ] View property list
- [ ] Click property card to view details
- [ ] Edit property information
- [ ] Link transaction to property
- [ ] Preview historical depreciation
- [ ] Backfill historical depreciation
- [ ] View property reports
- [ ] Archive property

#### Step 7.2: Browser Compatibility
- [ ] Chrome/Edge (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest)
- [ ] Mobile responsive

#### Step 7.3: i18n Testing
- [ ] German translations display correctly
- [ ] English translations display correctly
- [ ] Switch between languages works

**Status**: [ ] Complete  
**UI Issues Found**: ___________________________

---

### Phase 8: Documentation Review (10 minutes)

#### Step 8.1: Verify Documentation
- [ ] API documentation updated
- [ ] User guide available
- [ ] Developer guide available
- [ ] Migration guide reviewed
- [ ] Rollback procedures documented

#### Step 8.2: Update Changelog
```bash
# Add entry to CHANGELOG.md
echo "## [1.x.0] - $(date +%Y-%m-%d)

### Added
- Property Asset Management feature
  - Property registration and tracking
  - Automatic depreciation (AfA) calculation
  - Property-transaction linking
  - Historical depreciation backfill
  - Property reports and analytics
  - E1/Bescheid integration
  - Multi-property portfolio management

### Database
- Added 8 new migrations (002-009)
- Added properties, property_loans, audit_logs tables
- Added performance indexes
- Added address encryption

### API
- Added /api/v1/properties/* endpoints
- Added property-transaction linking endpoints
- Added historical depreciation endpoints
- Added annual depreciation endpoints
" >> CHANGELOG.md
```

**Status**: [ ] Complete

---

## Post-Deployment Validation

### Success Criteria
- [ ] All migrations applied successfully
- [ ] Verification script passes
- [ ] Application health checks pass
- [ ] No errors in application logs (15 min monitoring)
- [ ] Database performance within acceptable limits
- [ ] Property endpoints respond correctly
- [ ] No increase in error rate
- [ ] Response times within SLA (p95 < 500ms)
- [ ] Frontend UI works correctly
- [ ] All manual test scenarios pass

### Sign-Off
- [ ] Development Team Lead: ___________________________
- [ ] QA Team Lead: ___________________________
- [ ] Product Manager: ___________________________
- [ ] DevOps Lead: ___________________________

**Deployment Completed**: [ ] Yes [ ] No  
**Deployment Date/Time**: ___________________________  
**Deployed By**: ___________________________

---

## Rollback Procedure (If Needed)

### Emergency Rollback Steps
```bash
# 1. Stop application services
docker-compose stop backend frontend celery-worker

# 2. Rollback database migrations
cd backend
alembic downgrade 001

# 3. Restore from backup
docker-compose exec postgres psql -U taxja -d taxja < \
  backup/staging/YYYYMMDD/taxja_staging_pre_property_*.sql

# 4. Restart services with previous version
git checkout <previous-commit>
docker-compose build backend frontend
docker-compose up -d

# 5. Verify rollback
alembic current
curl http://localhost:8000/health
```

**Rollback Executed**: [ ] Yes [ ] No  
**Rollback Reason**: ___________________________  
**Rollback Completed At**: ___________________________

---

## Issues and Resolutions

### Issue 1
**Description**: ___________________________  
**Severity**: [ ] Critical [ ] High [ ] Medium [ ] Low  
**Resolution**: ___________________________  
**Resolved By**: ___________________________

### Issue 2
**Description**: ___________________________  
**Severity**: [ ] Critical [ ] High [ ] Medium [ ] Low  
**Resolution**: ___________________________  
**Resolved By**: ___________________________

---

## Next Steps

- [ ] Monitor staging for 24-48 hours
- [ ] Collect user feedback from beta testers
- [ ] Address any issues found
- [ ] Schedule production deployment
- [ ] Prepare production deployment checklist

---

## Notes

___________________________
___________________________
___________________________

---

**Document Version**: 1.0  
**Last Updated**: 2026-03-08  
**Status**: Ready for Use
