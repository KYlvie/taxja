# Property Management Migration Test Guide

## Overview

This guide provides comprehensive testing procedures for the property management feature migrations (002-009). These migrations add rental property tracking, depreciation calculation (AfA), and property-transaction linking capabilities to the Taxja platform.

## Migration Sequence

The property management feature consists of the following migrations:

1. **002_add_property_table.py** - Core properties table with enums
2. **003_add_property_id_to_transactions.py** - Link transactions to properties
3. **004_add_property_loans_table.py** - Property loan tracking
4. **005_add_historical_import_tables.py** - Historical data import support
5. **006_add_property_performance_indexes.py** - Performance optimization indexes
6. **007_add_property_address_encryption.py** - Increase column sizes for encryption
7. **008_encrypt_existing_property_addresses.py** - Data migration for encryption
8. **009_add_audit_logs_table.py** - Audit logging for compliance

## Prerequisites

### Environment Setup

```bash
# Ensure you have a staging database
createdb taxja_staging

# Set environment variables for staging
export DATABASE_URL="postgresql://user:password@localhost:5432/taxja_staging"
export ENVIRONMENT="staging"

# Ensure Alembic is configured
cd backend
pip install -r requirements.txt
```

### Backup Production Data

**CRITICAL**: Always backup production data before testing migrations:

```bash
# Backup production database
pg_dump -h production-host -U username -d taxja_production -F c -f taxja_backup_$(date +%Y%m%d_%H%M%S).dump

# Verify backup
pg_restore --list taxja_backup_*.dump | head -20
```

## Testing Procedure

### Phase 1: Clean Database Testing

Test migrations on a fresh database to ensure they work from scratch.

#### Step 1.1: Create Clean Test Database

```bash
# Drop and recreate test database
dropdb taxja_test --if-exists
createdb taxja_test

# Set environment to test database
export DATABASE_URL="postgresql://user:password@localhost:5432/taxja_test"
```

#### Step 1.2: Apply Base Migration

```bash
cd backend

# Apply initial migration (001)
alembic upgrade 001

# Verify base tables exist
psql -d taxja_test -c "\dt"
```

Expected output: users, transactions, documents, tax_configurations, loss_carryforwards, tax_reports

#### Step 1.3: Apply Property Migrations Sequentially

```bash
# Apply migration 002 (properties table)
alembic upgrade 002

# Verify properties table
psql -d taxja_test -c "\d properties"

# Check enums were created
psql -d taxja_test -c "\dT+ propertytype"
psql -d taxja_test -c "\dT+ propertystatus"

# Apply migration 003 (property_id in transactions)
alembic upgrade 003

# Verify property_id column
psql -d taxja_test -c "\d transactions" | grep property_id

# Apply remaining migrations
alembic upgrade 004  # property_loans
alembic upgrade 005  # historical_import
alembic upgrade 006  # performance indexes
alembic upgrade 007  # address encryption columns
alembic upgrade 008  # encrypt existing data
alembic upgrade 009  # audit logs

# Verify final state
alembic current
```

#### Step 1.4: Verify Database Structure

```bash
# Run verification script
python backend/alembic/verify_property_migration.py
```

Expected output:
```
✓ Properties table exists
✓ Property enums exist (propertytype, propertystatus)
✓ All required columns present
✓ All indexes created
✓ All constraints defined
✓ Foreign keys properly configured
✓ Transactions.property_id column exists
✓ Property_loans table exists
✓ Audit_logs table exists
```

### Phase 2: Data Insertion Testing

Test that the schema accepts valid data and rejects invalid data.

#### Step 2.1: Insert Test User

```sql
-- Connect to test database
psql -d taxja_test

-- Insert test user
INSERT INTO users (email, password_hash, name, user_type, tax_number)
VALUES ('test@example.com', 'hashed_password', 'Test User', 'landlord', '123456789');

-- Get user ID
SELECT id FROM users WHERE email = 'test@example.com';
-- Note the user_id for next steps (assume id=1)
```

#### Step 2.2: Insert Valid Property

```sql
-- Insert rental property
INSERT INTO properties (
    user_id,
    property_type,
    rental_percentage,
    address,
    street,
    city,
    postal_code,
    purchase_date,
    purchase_price,
    building_value,
    construction_year,
    depreciation_rate,
    status
) VALUES (
    1,
    'rental',
    100.00,
    'Hauptstraße 123, 1010 Wien',
    'Hauptstraße 123',
    'Wien',
    '1010',
    '2020-06-15',
    350000.00,
    280000.00,
    1985,
    0.02,
    'active'
);

-- Verify insertion
SELECT id, address, purchase_price, building_value, land_value, depreciation_rate
FROM properties
WHERE user_id = 1;
```

Expected: Property inserted successfully, land_value calculated as 70000.00

#### Step 2.3: Test Constraint Validation

```sql
-- Test 1: Building value exceeds purchase price (should FAIL)
INSERT INTO properties (
    user_id, property_type, address, street, city, postal_code,
    purchase_date, purchase_price, building_value
) VALUES (
    1, 'rental', 'Test St', 'Test St', 'Wien', '1010',
    '2020-01-01', 100000.00, 150000.00
);
-- Expected: ERROR: check constraint "check_building_value_range" violated

-- Test 2: Invalid depreciation rate (should FAIL)
INSERT INTO properties (
    user_id, property_type, address, street, city, postal_code,
    purchase_date, purchase_price, building_value, depreciation_rate
) VALUES (
    1, 'rental', 'Test St', 'Test St', 'Wien', '1010',
    '2020-01-01', 100000.00, 80000.00, 0.15
);
-- Expected: ERROR: check constraint "check_depreciation_rate_range" violated

-- Test 3: Sale date before purchase date (should FAIL)
INSERT INTO properties (
    user_id, property_type, address, street, city, postal_code,
    purchase_date, purchase_price, building_value, sale_date
) VALUES (
    1, 'rental', 'Test St', 'Test St', 'Wien', '1010',
    '2020-01-01', 100000.00, 80000.00, '2019-12-31'
);
-- Expected: ERROR: check constraint "check_sale_date_after_purchase" violated

-- Test 4: Sold status without sale_date (should FAIL)
INSERT INTO properties (
    user_id, property_type, address, street, city, postal_code,
    purchase_date, purchase_price, building_value, status
) VALUES (
    1, 'rental', 'Test St', 'Test St', 'Wien', '1010',
    '2020-01-01', 100000.00, 80000.00, 'sold'
);
-- Expected: ERROR: check constraint "check_sold_has_sale_date" violated
```

#### Step 2.4: Test Property-Transaction Linking

```sql
-- Insert transaction
INSERT INTO transactions (
    user_id,
    type,
    amount,
    transaction_date,
    description,
    expense_category,
    is_deductible
) VALUES (
    1,
    'expense',
    5000.00,
    '2024-12-31',
    'AfA Hauptstraße 123 (2024)',
    'depreciation_afa',
    true
);

-- Get property_id and transaction_id
SELECT id FROM properties WHERE user_id = 1 LIMIT 1;  -- Assume property_id
SELECT id FROM transactions WHERE user_id = 1 LIMIT 1;  -- Assume transaction_id

-- Link transaction to property
UPDATE transactions
SET property_id = (SELECT id FROM properties WHERE user_id = 1 LIMIT 1)
WHERE id = (SELECT id FROM transactions WHERE user_id = 1 LIMIT 1);

-- Verify link
SELECT t.id, t.description, t.amount, p.address
FROM transactions t
JOIN properties p ON t.property_id = p.id
WHERE t.user_id = 1;
```

Expected: Transaction successfully linked to property

#### Step 2.5: Test Index Performance

```sql
-- Test index on user_id
EXPLAIN ANALYZE
SELECT * FROM properties WHERE user_id = 1;
-- Expected: Index Scan using ix_properties_user_id

-- Test composite index on user_id and status
EXPLAIN ANALYZE
SELECT * FROM properties WHERE user_id = 1 AND status = 'active';
-- Expected: Index Scan using idx_properties_user_status

-- Test property_id index on transactions
EXPLAIN ANALYZE
SELECT * FROM transactions WHERE property_id = (SELECT id FROM properties LIMIT 1);
-- Expected: Index Scan using ix_transactions_property_id
```

### Phase 3: Rollback Testing

Test that migrations can be safely rolled back without data loss.

#### Step 3.1: Backup Current State

```bash
# Backup test database with data
pg_dump -d taxja_test -F c -f taxja_test_with_data.dump
```

#### Step 3.2: Test Individual Rollbacks

```bash
# Rollback migration 009 (audit logs)
alembic downgrade 008

# Verify audit_logs table dropped
psql -d taxja_test -c "\dt" | grep audit_logs
# Expected: No results

# Verify data still intact
psql -d taxja_test -c "SELECT COUNT(*) FROM properties;"
# Expected: Count matches inserted properties

# Rollback migration 008 (encryption data migration)
alembic downgrade 007

# Rollback migration 007 (encryption column sizes)
alembic downgrade 006

# Verify address columns reverted to original size
psql -d taxja_test -c "\d properties" | grep address
# Expected: address character varying(500)

# Rollback migration 006 (performance indexes)
alembic downgrade 005

# Verify indexes dropped
psql -d taxja_test -c "\di" | grep idx_properties_status
# Expected: No results

# Rollback migration 005 (historical import)
alembic downgrade 004

# Rollback migration 004 (property loans)
alembic downgrade 003

# Verify property_loans table dropped
psql -d taxja_test -c "\dt" | grep property_loans
# Expected: No results

# Rollback migration 003 (property_id in transactions)
alembic downgrade 002

# Verify property_id column removed
psql -d taxja_test -c "\d transactions" | grep property_id
# Expected: No results

# Rollback migration 002 (properties table)
alembic downgrade 001

# Verify properties table dropped
psql -d taxja_test -c "\dt" | grep properties
# Expected: No results

# Verify enums dropped
psql -d taxja_test -c "\dT" | grep propertytype
# Expected: No results
```

#### Step 3.3: Test Re-application After Rollback

```bash
# Re-apply all property migrations
alembic upgrade head

# Verify all tables recreated
psql -d taxja_test -c "\dt"

# Restore data from backup
pg_restore -d taxja_test --data-only taxja_test_with_data.dump

# Verify data restored
psql -d taxja_test -c "SELECT COUNT(*) FROM properties;"
```

### Phase 4: Staging Environment Testing

Test migrations on staging environment with production-like data.

#### Step 4.1: Prepare Staging Database

```bash
# Restore production backup to staging
pg_restore -h staging-host -U username -d taxja_staging -c taxja_backup_*.dump

# Verify data restored
psql -h staging-host -d taxja_staging -c "SELECT COUNT(*) FROM users;"
psql -h staging-host -d taxja_staging -c "SELECT COUNT(*) FROM transactions;"
```

#### Step 4.2: Check Current Migration State

```bash
# Set environment to staging
export DATABASE_URL="postgresql://user:password@staging-host:5432/taxja_staging"

# Check current migration version
alembic current

# Check migration history
alembic history --verbose
```

#### Step 4.3: Apply Property Migrations to Staging

```bash
# Apply migrations one at a time with verification
alembic upgrade 002
psql -h staging-host -d taxja_staging -c "SELECT COUNT(*) FROM properties;"

alembic upgrade 003
psql -h staging-host -d taxja_staging -c "\d transactions" | grep property_id

alembic upgrade 004
alembic upgrade 005
alembic upgrade 006
alembic upgrade 007
alembic upgrade 008
alembic upgrade 009

# Verify final state
alembic current
# Expected: 009 (head)
```

#### Step 4.4: Performance Testing on Staging

```sql
-- Connect to staging database
psql -h staging-host -d taxja_staging

-- Test query performance with real data volume
EXPLAIN ANALYZE
SELECT p.*, COUNT(t.id) as transaction_count
FROM properties p
LEFT JOIN transactions t ON t.property_id = p.id
WHERE p.user_id IN (SELECT id FROM users WHERE user_type = 'landlord')
GROUP BY p.id
ORDER BY p.created_at DESC
LIMIT 50;

-- Check index usage
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
WHERE tablename IN ('properties', 'transactions')
ORDER BY idx_scan DESC;

-- Check table sizes
SELECT
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE tablename IN ('properties', 'transactions', 'property_loans')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

#### Step 4.5: Application Integration Testing

```bash
# Start backend application on staging
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Test property endpoints
curl -X GET http://staging-host:8000/api/v1/properties \
  -H "Authorization: Bearer $STAGING_TOKEN"

# Test property creation
curl -X POST http://staging-host:8000/api/v1/properties \
  -H "Authorization: Bearer $STAGING_TOKEN" \
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

# Test property-transaction linking
curl -X POST http://staging-host:8000/api/v1/properties/{property_id}/link-transaction \
  -H "Authorization: Bearer $STAGING_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"transaction_id": 123}'
```

### Phase 5: Rollback Procedure Documentation

#### Emergency Rollback Procedure

If issues are discovered after deployment to production:

```bash
# STEP 1: Immediately stop application servers
# This prevents new data from being written during rollback

# STEP 2: Backup current state
pg_dump -h production-host -U username -d taxja_production \
  -F c -f taxja_emergency_backup_$(date +%Y%m%d_%H%M%S).dump

# STEP 3: Rollback migrations
export DATABASE_URL="postgresql://user:password@production-host:5432/taxja_production"

# Rollback to migration 001 (before property feature)
alembic downgrade 001

# STEP 4: Verify rollback
psql -h production-host -d taxja_production -c "\dt" | grep properties
# Expected: No results

# STEP 5: Restart application servers with previous version
# Deploy previous application version that doesn't use property features

# STEP 6: Verify application functionality
curl -X GET http://production-host:8000/health
curl -X GET http://production-host:8000/api/v1/transactions
```

#### Partial Rollback Procedure

If only specific migrations need to be rolled back:

```bash
# Example: Rollback only encryption migrations (008, 007)
alembic downgrade 006

# Verify specific tables still exist
psql -h production-host -d taxja_production -c "\dt" | grep properties
# Expected: properties table exists

# Verify address columns reverted
psql -h production-host -d taxja_production -c "\d properties" | grep address
# Expected: address character varying(500)

# Re-apply if needed
alembic upgrade head
```

## Common Issues and Solutions

### Issue 1: Enum Already Exists

**Error**: `DuplicateObject: type "propertytype" already exists`

**Solution**:
```bash
# Check if enum exists
psql -d taxja_staging -c "\dT propertytype"

# If exists, skip enum creation or drop and recreate
psql -d taxja_staging -c "DROP TYPE IF EXISTS propertytype CASCADE;"
alembic upgrade 002
```

### Issue 2: Foreign Key Constraint Violation

**Error**: `ForeignKeyViolation: insert or update on table "properties" violates foreign key constraint`

**Solution**:
```sql
-- Verify referenced user exists
SELECT id FROM users WHERE id = <user_id>;

-- If user doesn't exist, create test user first
INSERT INTO users (email, password_hash, name, user_type)
VALUES ('test@example.com', 'hash', 'Test', 'landlord');
```

### Issue 3: Column Size Too Small for Encrypted Data

**Error**: `DataException: value too long for type character varying(500)`

**Solution**:
```bash
# Ensure migration 007 is applied
alembic current
alembic upgrade 007

# Verify column sizes
psql -d taxja_staging -c "\d properties" | grep address
# Expected: address character varying(1000)
```

### Issue 4: Index Already Exists

**Error**: `DuplicateTable: relation "idx_properties_user_id" already exists`

**Solution**:
```sql
-- Drop existing index
DROP INDEX IF EXISTS idx_properties_user_id;

-- Re-run migration
alembic upgrade 002
```

### Issue 5: Migration Out of Sync

**Error**: `CommandError: Target database is not up to date`

**Solution**:
```bash
# Check current version
alembic current

# Check migration history
alembic history

# Stamp database to correct version
alembic stamp head

# Or downgrade and re-upgrade
alembic downgrade base
alembic upgrade head
```

## Verification Checklist

Before deploying to production, verify:

- [ ] All migrations apply successfully on clean database
- [ ] All migrations apply successfully on staging with production data
- [ ] All constraints work as expected (tested with invalid data)
- [ ] All indexes are created and used by queries
- [ ] Foreign key relationships work correctly
- [ ] Rollback procedure tested and documented
- [ ] Application integration tests pass on staging
- [ ] Performance tests show acceptable query times
- [ ] Backup and restore procedures tested
- [ ] Emergency rollback procedure documented and tested

## Production Deployment Steps

1. **Schedule maintenance window** (recommended: low-traffic period)
2. **Notify users** of planned maintenance
3. **Backup production database** (full backup)
4. **Stop application servers** (prevent writes during migration)
5. **Apply migrations** (`alembic upgrade head`)
6. **Verify migration** (`alembic current`, check tables)
7. **Run smoke tests** (basic API calls)
8. **Deploy new application version** (with property features)
9. **Start application servers**
10. **Monitor logs and metrics** (watch for errors)
11. **Run integration tests** (test property endpoints)
12. **Notify users** that maintenance is complete

## Monitoring After Deployment

```bash
# Monitor application logs
tail -f /var/log/taxja/app.log | grep -i "property\|error"

# Monitor database performance
psql -d taxja_production -c "
SELECT schemaname, tablename, seq_scan, seq_tup_read, idx_scan, idx_tup_fetch
FROM pg_stat_user_tables
WHERE tablename IN ('properties', 'transactions')
ORDER BY seq_scan DESC;
"

# Monitor slow queries
psql -d taxja_production -c "
SELECT query, calls, total_time, mean_time
FROM pg_stat_statements
WHERE query LIKE '%properties%'
ORDER BY mean_time DESC
LIMIT 10;
"
```

## Support Contacts

- **Database Admin**: dba@taxja.com
- **DevOps Team**: devops@taxja.com
- **On-Call Engineer**: +43 XXX XXXXXXX

## Document Version

- **Version**: 1.0
- **Last Updated**: 2026-03-08
- **Author**: Development Team
- **Status**: Ready for Use
