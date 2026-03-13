# Migration 002 Testing Guide

## Overview
This guide provides instructions for testing migration 002 (add_property_table) with both upgrade and downgrade operations.

## Prerequisites

1. **Database Running**: Ensure PostgreSQL is running
   ```bash
   # Using Docker Compose
   docker-compose up -d postgres
   
   # Or check if running locally
   pg_isready -h localhost -p 5432
   ```

2. **Python Environment**: Ensure dependencies are installed
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. **Database Connection**: Verify `.env` file has correct database credentials

## Testing Methods

### Method 1: Automated Test Script (Recommended)

Run the comprehensive test script that validates both upgrade and downgrade:

```bash
cd backend
python test_migration_002.py
```

**What it tests:**
- ✓ Table creation (properties)
- ✓ All 23 columns exist with correct types
- ✓ Enum types (propertytype, propertystatus)
- ✓ Indexes (user_id, status, user_status composite)
- ✓ Foreign keys (user_id, document references)
- ✓ Check constraints (price ranges, date validations)
- ✓ Downgrade removes everything cleanly
- ✓ Re-upgrade restores everything

### Method 2: Manual Testing

#### Step 1: Apply Migration (Upgrade)

```bash
cd backend

# Check current migration version
python -c "from alembic.config import Config; from alembic import command; cfg = Config('alembic.ini'); command.current(cfg)"

# Apply migration 002
python -c "from alembic.config import Config; from alembic import command; cfg = Config('alembic.ini'); command.upgrade(cfg, 'head')"
```

#### Step 2: Verify Upgrade

```bash
# Run verification script
python test_migration_002.py
```

Expected output:
```
======================================================================
TESTING MIGRATION 002 UPGRADE
======================================================================

1. Checking if 'properties' table exists...
   ✓ Table 'properties' exists

2. Checking columns...
   ✓ All 23 expected columns exist

3. Checking enum types...
   ✓ Enum 'propertytype' exists
   ✓ Enum 'propertystatus' exists

4. Checking indexes...
   ✓ All 3 expected indexes exist

5. Checking foreign keys...
   ✓ All 3 expected foreign keys exist

======================================================================
✓ MIGRATION 002 UPGRADE TEST PASSED
======================================================================
```

#### Step 3: Test Downgrade

```bash
# Downgrade one revision
python -c "from alembic.config import Config; from alembic import command; cfg = Config('alembic.ini'); command.downgrade(cfg, '-1')"

# Verify downgrade
python test_migration_002.py
```

Expected output:
```
======================================================================
TESTING MIGRATION 002 DOWNGRADE
======================================================================

1. Checking if 'properties' table was removed...
   ✓ Table 'properties' successfully removed

2. Checking if enum types were removed...
   ✓ Enum 'propertytype' successfully removed
   ✓ Enum 'propertystatus' successfully removed

======================================================================
✓ MIGRATION 002 DOWNGRADE TEST PASSED
======================================================================
```

#### Step 4: Re-apply Migration

```bash
# Upgrade back to head
python -c "from alembic.config import Config; from alembic import command; cfg = Config('alembic.ini'); command.upgrade(cfg, 'head')"
```

### Method 3: Using Docker

If running the full stack with Docker:

```bash
# Access backend container
docker exec -it taxja-backend bash

# Inside container, run tests
cd /app
python test_migration_002.py
```

## What Gets Created

### Tables
- **properties**: Main property asset table with 23 columns

### Enums
- **propertytype**: rental, owner_occupied, mixed_use
- **propertystatus**: active, sold, archived

### Indexes
- **ix_properties_user_id**: Fast lookup by user
- **ix_properties_status**: Fast filtering by status
- **ix_properties_user_status**: Composite index for user+status queries

### Foreign Keys
- **user_id** → users.id (CASCADE delete)
- **kaufvertrag_document_id** → documents.id (SET NULL)
- **mietvertrag_document_id** → documents.id (SET NULL)

### Check Constraints
- rental_percentage: 0-100 range
- purchase_price: 0-100,000,000 range
- building_value: 0 to purchase_price
- depreciation_rate: 0.001-0.10 range
- construction_year: 1800 to current year
- sale_date: must be >= purchase_date
- sold status: must have sale_date

## Troubleshooting

### Error: "Table 'properties' does NOT exist"
**Solution**: Migration hasn't been applied yet. Run:
```bash
python -c "from alembic.config import Config; from alembic import command; cfg = Config('alembic.ini'); command.upgrade(cfg, 'head')"
```

### Error: "ModuleNotFoundError: No module named 'alembic'"
**Solution**: Install dependencies:
```bash
pip install -r requirements.txt
```

### Error: "could not connect to server"
**Solution**: Start PostgreSQL:
```bash
docker-compose up -d postgres
```

### Error: "relation 'users' does not exist"
**Solution**: Apply previous migrations first:
```bash
python -c "from alembic.config import Config; from alembic import command; cfg = Config('alembic.ini'); command.upgrade(cfg, 'head')"
```

## Success Criteria

Migration 002 is considered fully tested when:

- ✅ Upgrade creates all tables, columns, indexes, and constraints
- ✅ All check constraints work correctly
- ✅ Foreign keys enforce referential integrity
- ✅ Enum types are created and usable
- ✅ Downgrade removes everything cleanly
- ✅ Re-upgrade works without errors
- ✅ No orphaned database objects remain after downgrade

## Next Steps

After successful testing:

1. Mark Task 1.2 as complete in tasks.md
2. Proceed to Task 1.3: Extend Transaction Model with Property Link
3. Update the Property model in `backend/app/models/__init__.py` to include the import

## Related Files

- Migration: `backend/alembic/versions/002_add_property_table.py`
- Test Script: `backend/test_migration_002.py`
- Model: `backend/app/models/property.py`
- Tasks: `.kiro/specs/property-asset-management/tasks.md`
