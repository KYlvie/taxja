# Property Management Migration Rollback Procedures

## Overview

This document provides detailed rollback procedures for the property management feature migrations. Use these procedures when you need to revert database changes due to issues discovered during or after deployment.

## Table of Contents

1. [Pre-Rollback Checklist](#pre-rollback-checklist)
2. [Emergency Rollback (Full)](#emergency-rollback-full)
3. [Partial Rollback Procedures](#partial-rollback-procedures)
4. [Data Preservation](#data-preservation)
5. [Post-Rollback Verification](#post-rollback-verification)
6. [Re-Application After Rollback](#re-application-after-rollback)
7. [Troubleshooting](#troubleshooting)

## Pre-Rollback Checklist

Before performing any rollback, complete these steps:

### 1. Assess the Situation

- [ ] Identify the specific issue requiring rollback
- [ ] Determine which migrations need to be rolled back
- [ ] Assess impact on users and data
- [ ] Notify stakeholders of planned rollback

### 2. Backup Current State

```bash
# Create timestamped backup
BACKUP_FILE="taxja_pre_rollback_$(date +%Y%m%d_%H%M%S).dump"
pg_dump -h <host> -U <user> -d <database> -F c -f $BACKUP_FILE

# Verify backup
pg_restore --list $BACKUP_FILE | head -20

# Store backup securely
cp $BACKUP_FILE /backup/critical/
```

### 3. Stop Application Services

```bash
# Stop application servers to prevent new writes
systemctl stop taxja-backend
# or
docker-compose stop backend

# Verify no connections to database
psql -d taxja_production -c "
SELECT pid, usename, application_name, state
FROM pg_stat_activity
WHERE datname = 'taxja_production'
AND application_name != 'psql';
"

# Terminate active connections if needed
psql -d taxja_production -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'taxja_production'
AND pid <> pg_backend_pid()
AND application_name != 'psql';
"
```

### 4. Document Current State

```bash
# Record current migration version
alembic current > rollback_start_version.txt

# Record table counts
psql -d taxja_production -c "
SELECT 'properties' as table_name, COUNT(*) as row_count FROM properties
UNION ALL
SELECT 'transactions', COUNT(*) FROM transactions WHERE property_id IS NOT NULL
UNION ALL
SELECT 'property_loans', COUNT(*) FROM property_loans;
" > rollback_start_counts.txt
```

## Emergency Rollback (Full)

Use this procedure when you need to completely remove the property management feature.

### Step 1: Backup and Stop Services

Follow the [Pre-Rollback Checklist](#pre-rollback-checklist) above.

### Step 2: Export Property Data (Optional)

If you want to preserve property data for later re-import:

```bash
# Export properties table
psql -d taxja_production -c "
COPY (
    SELECT * FROM properties
) TO STDOUT WITH CSV HEADER
" > properties_backup_$(date +%Y%m%d).csv

# Export property-linked transactions
psql -d taxja_production -c "
COPY (
    SELECT * FROM transactions WHERE property_id IS NOT NULL
) TO STDOUT WITH CSV HEADER
" > property_transactions_backup_$(date +%Y%m%d).csv

# Export property loans
psql -d taxja_production -c "
COPY (
    SELECT * FROM property_loans
) TO STDOUT WITH CSV HEADER
" > property_loans_backup_$(date +%Y%m%d).csv
```

### Step 3: Perform Rollback

```bash
# Set database connection
export DATABASE_URL="postgresql://user:password@host:port/taxja_production"

# Check current version
alembic current
# Expected: 009 or later

# Rollback to version 001 (before property feature)
alembic downgrade 001

# Verify rollback
alembic current
# Expected: 001
```

### Step 4: Verify Rollback

```bash
# Verify properties table removed
psql -d taxja_production -c "\dt" | grep properties
# Expected: No results

# Verify enums removed
psql -d taxja_production -c "\dT" | grep -E "propertytype|propertystatus"
# Expected: No results

# Verify transactions.property_id removed
psql -d taxja_production -c "\d transactions" | grep property_id
# Expected: No results

# Verify base tables still exist
psql -d taxja_production -c "\dt" | grep -E "users|transactions|documents"
# Expected: All base tables present
```

### Step 5: Deploy Previous Application Version

```bash
# Deploy application version without property features
git checkout <previous-version-tag>
docker-compose build backend
docker-compose up -d backend

# Or using systemd
systemctl start taxja-backend
```

### Step 6: Verify Application

```bash
# Test health endpoint
curl http://localhost:8000/health

# Test basic functionality
curl -X GET http://localhost:8000/api/v1/transactions \
  -H "Authorization: Bearer $TOKEN"

# Verify property endpoints return 404
curl -X GET http://localhost:8000/api/v1/properties \
  -H "Authorization: Bearer $TOKEN"
# Expected: 404 Not Found
```

## Partial Rollback Procedures

Use these procedures when you only need to rollback specific migrations.

### Rollback Scenario 1: Remove Encryption (Migrations 008, 007)

**Use case**: Encryption causing performance issues or data corruption

```bash
# Rollback to version 006 (before encryption)
alembic downgrade 006

# Verify address columns reverted to original size
psql -d taxja_production -c "\d properties" | grep -E "address|street|city"
# Expected:
#   address  | character varying(500)
#   street   | character varying(255)
#   city     | character varying(100)

# Verify data still accessible
psql -d taxja_production -c "SELECT id, address FROM properties LIMIT 5;"
```

**Important**: If data was encrypted, you must decrypt it before rolling back column sizes:

```python
# Run decryption script before rollback
python backend/scripts/decrypt_property_addresses.py --all

# Then perform rollback
alembic downgrade 006
```

### Rollback Scenario 2: Remove Performance Indexes (Migration 006)

**Use case**: Indexes causing write performance issues

```bash
# Rollback to version 005
alembic downgrade 005

# Verify indexes removed
psql -d taxja_production -c "
SELECT indexname FROM pg_indexes
WHERE tablename IN ('properties', 'transactions')
AND indexname LIKE 'idx_%';
"
# Expected: Performance indexes removed, base indexes remain
```

### Rollback Scenario 3: Remove Property Loans (Migration 004)

**Use case**: Property loans feature not needed

```bash
# Export property loans data first
psql -d taxja_production -c "
COPY property_loans TO '/tmp/property_loans_backup.csv' CSV HEADER;
"

# Rollback to version 003
alembic downgrade 003

# Verify property_loans table removed
psql -d taxja_production -c "\dt" | grep property_loans
# Expected: No results

# Verify properties and transactions tables intact
psql -d taxja_production -c "SELECT COUNT(*) FROM properties;"
psql -d taxja_production -c "SELECT COUNT(*) FROM transactions WHERE property_id IS NOT NULL;"
```

### Rollback Scenario 4: Remove Property-Transaction Linking (Migration 003)

**Use case**: Need to remove property_id from transactions

**WARNING**: This will break the link between transactions and properties. Export data first.

```bash
# Export property-transaction links
psql -d taxja_production -c "
COPY (
    SELECT t.id as transaction_id, t.property_id, p.address
    FROM transactions t
    JOIN properties p ON t.property_id = p.id
    WHERE t.property_id IS NOT NULL
) TO '/tmp/property_transaction_links.csv' CSV HEADER;
"

# Rollback to version 002
alembic downgrade 002

# Verify property_id column removed from transactions
psql -d taxja_production -c "\d transactions" | grep property_id
# Expected: No results

# Verify properties table still exists
psql -d taxja_production -c "SELECT COUNT(*) FROM properties;"
```

## Data Preservation

### Exporting All Property Data

Before any rollback, export all property-related data:

```bash
#!/bin/bash
# export_property_data.sh

EXPORT_DIR="property_data_export_$(date +%Y%m%d_%H%M%S)"
mkdir -p $EXPORT_DIR

# Export properties
psql -d taxja_production -c "
COPY properties TO STDOUT CSV HEADER
" > $EXPORT_DIR/properties.csv

# Export property-linked transactions
psql -d taxja_production -c "
COPY (
    SELECT t.*, p.address as property_address
    FROM transactions t
    LEFT JOIN properties p ON t.property_id = p.id
    WHERE t.property_id IS NOT NULL
) TO STDOUT CSV HEADER
" > $EXPORT_DIR/property_transactions.csv

# Export property loans
psql -d taxja_production -c "
COPY property_loans TO STDOUT CSV HEADER
" > $EXPORT_DIR/property_loans.csv

# Export property metrics summary
psql -d taxja_production -c "
COPY (
    SELECT
        p.id,
        p.address,
        p.purchase_price,
        p.building_value,
        COUNT(t.id) as transaction_count,
        SUM(CASE WHEN t.type = 'expense' THEN t.amount ELSE 0 END) as total_expenses,
        SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE 0 END) as total_income
    FROM properties p
    LEFT JOIN transactions t ON t.property_id = p.id
    GROUP BY p.id
) TO STDOUT CSV HEADER
" > $EXPORT_DIR/property_metrics.csv

# Create archive
tar -czf $EXPORT_DIR.tar.gz $EXPORT_DIR
echo "Property data exported to $EXPORT_DIR.tar.gz"
```

### Importing Property Data After Re-Application

After rolling back and re-applying migrations:

```bash
#!/bin/bash
# import_property_data.sh

EXPORT_DIR=$1

if [ -z "$EXPORT_DIR" ]; then
    echo "Usage: $0 <export_directory>"
    exit 1
fi

# Import properties
psql -d taxja_production -c "
COPY properties FROM STDIN CSV HEADER
" < $EXPORT_DIR/properties.csv

# Update property_id in transactions
# Note: This requires matching transaction IDs
psql -d taxja_production -c "
CREATE TEMP TABLE temp_property_transactions (
    id INTEGER,
    property_id UUID,
    -- other columns...
);

COPY temp_property_transactions FROM STDIN CSV HEADER;

UPDATE transactions t
SET property_id = tpt.property_id
FROM temp_property_transactions tpt
WHERE t.id = tpt.id;

DROP TABLE temp_property_transactions;
" < $EXPORT_DIR/property_transactions.csv

# Import property loans
psql -d taxja_production -c "
COPY property_loans FROM STDIN CSV HEADER
" < $EXPORT_DIR/property_loans.csv

echo "Property data imported successfully"
```

## Post-Rollback Verification

After completing rollback, verify the database state:

### 1. Check Migration Version

```bash
alembic current
# Verify it matches expected version
```

### 2. Verify Table Structure

```bash
# List all tables
psql -d taxja_production -c "\dt"

# Check specific tables based on rollback level
psql -d taxja_production -c "\d properties"  # Should exist or not based on rollback
psql -d taxja_production -c "\d transactions"  # Should always exist
```

### 3. Verify Data Integrity

```bash
# Check row counts
psql -d taxja_production -c "
SELECT 'users' as table_name, COUNT(*) FROM users
UNION ALL
SELECT 'transactions', COUNT(*) FROM transactions
UNION ALL
SELECT 'documents', COUNT(*) FROM documents;
"

# Compare with pre-rollback counts
diff rollback_start_counts.txt <(psql -d taxja_production -c "...")
```

### 4. Test Application Functionality

```bash
# Test authentication
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password"}'

# Test transaction listing
curl -X GET http://localhost:8000/api/v1/transactions \
  -H "Authorization: Bearer $TOKEN"

# Test document upload
curl -X POST http://localhost:8000/api/v1/documents \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test_receipt.pdf"
```

### 5. Monitor Logs

```bash
# Monitor application logs for errors
tail -f /var/log/taxja/app.log | grep -i error

# Monitor database logs
tail -f /var/log/postgresql/postgresql-*.log | grep -i error
```

## Re-Application After Rollback

If you need to re-apply migrations after fixing issues:

### Step 1: Verify Current State

```bash
# Check current migration version
alembic current

# Verify database is in expected state
python backend/alembic/verify_property_migration.py
```

### Step 2: Apply Migrations

```bash
# Apply all migrations
alembic upgrade head

# Or apply specific migration
alembic upgrade 009
```

### Step 3: Restore Data

```bash
# If you exported data, restore it
./import_property_data.sh property_data_export_20260308_120000
```

### Step 4: Verify Re-Application

```bash
# Run verification script
python backend/alembic/verify_property_migration.py

# Test application
curl -X GET http://localhost:8000/api/v1/properties \
  -H "Authorization: Bearer $TOKEN"
```

## Troubleshooting

### Issue 1: Rollback Fails with Foreign Key Constraint

**Error**: `ERROR: cannot drop table properties because other objects depend on it`

**Solution**:
```sql
-- Find dependent objects
SELECT
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
AND ccu.table_name = 'properties';

-- Drop dependent objects first, then retry rollback
-- Or use CASCADE (WARNING: drops all dependent data)
DROP TABLE properties CASCADE;
```

### Issue 2: Enum Type Cannot Be Dropped

**Error**: `ERROR: cannot drop type propertytype because other objects depend on it`

**Solution**:
```sql
-- Find objects using the enum
SELECT
    n.nspname AS schema,
    t.typname AS enum_type,
    c.relname AS table_name,
    a.attname AS column_name
FROM pg_type t
JOIN pg_enum e ON t.oid = e.enumtypid
JOIN pg_attribute a ON a.atttypid = t.oid
JOIN pg_class c ON a.attrelid = c.oid
JOIN pg_namespace n ON c.relnamespace = n.oid
WHERE t.typname = 'propertytype';

-- Drop columns using the enum first
ALTER TABLE properties DROP COLUMN property_type;

-- Then drop the enum
DROP TYPE propertytype;
```

### Issue 3: Data Loss During Rollback

**Error**: Rollback completed but data is missing

**Solution**:
```bash
# Restore from backup
pg_restore -h <host> -U <user> -d taxja_production -c taxja_pre_rollback_*.dump

# Or restore specific tables
pg_restore -h <host> -U <user> -d taxja_production -t properties taxja_pre_rollback_*.dump
```

### Issue 4: Application Still Expects Property Tables

**Error**: Application throws errors about missing properties table

**Solution**:
```bash
# Deploy previous application version
git checkout <version-before-property-feature>
docker-compose build backend
docker-compose up -d backend

# Or set feature flag to disable property features
export ENABLE_PROPERTY_MANAGEMENT=false
systemctl restart taxja-backend
```

### Issue 5: Cannot Reconnect After Rollback

**Error**: `FATAL: database "taxja_production" does not exist`

**Solution**:
```bash
# Check database exists
psql -l | grep taxja

# If database was accidentally dropped, restore from backup
createdb taxja_production
pg_restore -d taxja_production taxja_pre_rollback_*.dump
```

## Emergency Contacts

- **Database Administrator**: dba@taxja.com / +43 XXX XXXXXXX
- **DevOps Team**: devops@taxja.com / +43 XXX XXXXXXX
- **On-Call Engineer**: oncall@taxja.com / +43 XXX XXXXXXX
- **CTO**: cto@taxja.com / +43 XXX XXXXXXX

## Rollback Decision Matrix

| Severity | Issue Type | Recommended Action | Rollback Level |
|----------|-----------|-------------------|----------------|
| Critical | Data corruption | Full rollback | 001 |
| Critical | Application crash | Full rollback | 001 |
| High | Performance degradation | Partial rollback | 006 (remove indexes) |
| High | Encryption issues | Partial rollback | 006 (remove encryption) |
| Medium | Feature bugs | Fix forward | None (deploy fix) |
| Low | UI issues | Fix forward | None (deploy fix) |

## Document Version

- **Version**: 1.0
- **Last Updated**: 2026-03-08
- **Author**: Development Team
- **Status**: Ready for Use
- **Next Review**: 2026-06-08
