# Migration Testing Guide

This guide explains how to test the database migrations for the Austrian Tax Management System.

## Prerequisites

Before testing migrations, ensure you have:

1. **PostgreSQL installed and running**
   ```bash
   # Check PostgreSQL status
   pg_isready
   
   # Or on Windows
   pg_ctl status
   ```

2. **Python dependencies installed**
   ```bash
   pip install -r requirements.txt
   ```

3. **Environment variables configured**
   ```bash
   # Copy .env.example to .env
   cp .env.example .env
   
   # Edit .env with your database credentials
   ```

## Test 1: Verify Migration File Structure

This test verifies that the migration file has the correct structure without requiring a database connection.

```bash
python verify_migration.py
```

**Expected output:**
```
✓ Found revision attribute
✓ Found down_revision attribute
✓ Found upgrade function
✓ Found downgrade function
✓ Index 'ix_users_email' is created
✓ Index 'ix_transactions_user_id' is created
...
✓ Migration file structure verification passed!
```

## Test 2: Apply Migration to Clean Database

### Step 1: Create Test Database

```bash
# Create a test database
createdb taxja_test

# Or using psql
psql -U postgres -c "CREATE DATABASE taxja_test;"
```

### Step 2: Configure Test Database

```bash
# Set environment variable for test database
export DATABASE_URL="postgresql://taxja:taxja_password@localhost:5432/taxja_test"

# Or on Windows PowerShell
$env:DATABASE_URL="postgresql://taxja:taxja_password@localhost:5432/taxja_test"
```

### Step 3: Run Migration

```bash
# Apply migration
alembic upgrade head
```

**Expected output:**
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 001, Initial migration: create all tables
```

### Step 4: Verify Tables Were Created

```bash
# Connect to test database
psql -d taxja_test

# List all tables
\dt

# Expected tables:
# - users
# - transactions
# - documents
# - tax_configurations
# - loss_carryforwards
# - tax_reports
```

### Step 5: Verify Table Schemas

```sql
-- Check users table
\d users

-- Expected columns:
-- id, email, password_hash, name, tax_number, vat_number, address,
-- user_type, family_info, commuting_info, home_office_eligible,
-- language, two_factor_enabled, two_factor_secret, disclaimer_accepted_at,
-- created_at, updated_at, last_login

-- Check transactions table
\d transactions

-- Expected columns:
-- id, user_id, type, amount, transaction_date, description,
-- income_category, expense_category, is_deductible, deduction_reason,
-- vat_rate, vat_amount, document_id, classification_confidence,
-- needs_review, import_source, created_at, updated_at

-- Check foreign keys
SELECT
    tc.table_name, 
    kcu.column_name, 
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name 
FROM 
    information_schema.table_constraints AS tc 
    JOIN information_schema.key_column_usage AS kcu
      ON tc.constraint_name = kcu.constraint_name
      AND tc.table_schema = kcu.table_schema
    JOIN information_schema.constraint_column_usage AS ccu
      ON ccu.constraint_name = tc.constraint_name
      AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY';

-- Expected foreign keys:
-- transactions.user_id -> users.id
-- transactions.document_id -> documents.id
-- documents.user_id -> users.id
-- documents.transaction_id -> transactions.id
-- loss_carryforwards.user_id -> users.id
-- tax_reports.user_id -> users.id
```

### Step 6: Verify Indexes

```sql
-- List all indexes
SELECT
    tablename,
    indexname,
    indexdef
FROM
    pg_indexes
WHERE
    schemaname = 'public'
ORDER BY
    tablename,
    indexname;

-- Expected indexes:
-- ix_users_email (unique)
-- ix_users_id
-- ix_tax_configurations_tax_year (unique)
-- ix_documents_user_id
-- ix_documents_document_type
-- ix_transactions_user_id
-- ix_transactions_transaction_date
-- ix_transactions_type
-- ix_loss_carryforwards_user_id
-- ix_loss_carryforwards_loss_year
-- ix_tax_reports_user_id
-- ix_tax_reports_tax_year
```

### Step 7: Verify Enums

```sql
-- List all enum types
SELECT
    t.typname,
    e.enumlabel
FROM
    pg_type t
    JOIN pg_enum e ON t.oid = e.enumtypid
WHERE
    t.typname IN ('usertype', 'transactiontype', 'incomecategory', 'expensecategory', 'documenttype')
ORDER BY
    t.typname,
    e.enumsortorder;

-- Expected enums:
-- usertype: EMPLOYEE, SELF_EMPLOYED, LANDLORD, MIXED
-- transactiontype: INCOME, EXPENSE
-- incomecategory: EMPLOYMENT, RENTAL, SELF_EMPLOYMENT, CAPITAL_GAINS
-- expensecategory: OFFICE_SUPPLIES, EQUIPMENT, TRAVEL, MARKETING, etc.
-- documenttype: PAYSLIP, RECEIPT, INVOICE, RENTAL_CONTRACT, etc.
```

## Test 3: Seed Tax Configuration

After migration, seed the 2026 tax configuration:

```bash
python seed_tax_config.py
```

**Expected output:**
```
Connecting to database...
✓ Successfully seeded 2026 tax configuration
  - Tax year: 2026
  - Exemption amount: €13539.00
  - Tax brackets: 7 brackets
  - VAT standard rate: 20.0%
  - VAT residential rate: 10.0%
  - Small business threshold: €55000.0
```

### Verify Tax Configuration

```sql
-- Connect to database
psql -d taxja_test

-- Query tax configuration
SELECT
    tax_year,
    exemption_amount,
    jsonb_pretty(tax_brackets::jsonb) AS tax_brackets,
    jsonb_pretty(vat_rates::jsonb) AS vat_rates
FROM
    tax_configurations
WHERE
    tax_year = 2026;

-- Expected output:
-- tax_year: 2026
-- exemption_amount: 13539.00
-- tax_brackets: 7 brackets from 0% to 55%
-- vat_rates: standard 20%, residential 10%, thresholds
```

## Test 4: Test Migration Rollback

Test that the migration can be rolled back cleanly:

```bash
# Downgrade migration
alembic downgrade -1
```

**Expected output:**
```
INFO  [alembic.runtime.migration] Running downgrade 001 -> , Initial migration: create all tables
```

### Verify Tables Were Dropped

```bash
# Connect to test database
psql -d taxja_test

# List tables (should be empty)
\dt

# Expected: No relations found
```

### Re-apply Migration

```bash
# Upgrade again
alembic upgrade head
```

## Test 5: Test with Sample Data

Create sample data to verify relationships work correctly:

```sql
-- Connect to database
psql -d taxja_test

-- Insert test user
INSERT INTO users (
    email, password_hash, name, user_type,
    created_at, updated_at
) VALUES (
    'test@example.com',
    'hashed_password',
    'Test User',
    'EMPLOYEE',
    NOW(),
    NOW()
) RETURNING id;

-- Note the returned user_id (e.g., 1)

-- Insert test transaction
INSERT INTO transactions (
    user_id, type, amount, transaction_date,
    description, income_category,
    created_at, updated_at
) VALUES (
    1,  -- Replace with actual user_id
    'INCOME',
    3000.00,
    '2026-01-15',
    'Monthly salary',
    'EMPLOYMENT',
    NOW(),
    NOW()
);

-- Verify data was inserted
SELECT * FROM users;
SELECT * FROM transactions;

-- Verify foreign key relationship
SELECT
    u.name,
    t.type,
    t.amount,
    t.transaction_date
FROM
    users u
    JOIN transactions t ON u.id = t.user_id;
```

## Test 6: Clean Up

After testing, clean up the test database:

```bash
# Drop test database
dropdb taxja_test

# Or using psql
psql -U postgres -c "DROP DATABASE taxja_test;"
```

## Common Issues and Solutions

### Issue 1: "alembic: command not found"

**Solution:**
```bash
# Install alembic
pip install alembic

# Or use python -m
python -m alembic upgrade head
```

### Issue 2: "could not connect to server"

**Solution:**
```bash
# Check PostgreSQL is running
pg_isready

# Start PostgreSQL
# On Linux/Mac:
sudo service postgresql start

# On Windows:
net start postgresql-x64-15
```

### Issue 3: "database does not exist"

**Solution:**
```bash
# Create the database
createdb taxja_test

# Or specify user
createdb -U postgres taxja_test
```

### Issue 4: "permission denied"

**Solution:**
```bash
# Grant permissions
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE taxja_test TO taxja;"
```

### Issue 5: "relation already exists"

**Solution:**
```bash
# Drop and recreate database
dropdb taxja_test
createdb taxja_test
alembic upgrade head
```

## Success Criteria

The migration is considered successful if:

1. ✓ Migration file structure is valid
2. ✓ All 6 tables are created (users, transactions, documents, tax_configurations, loss_carryforwards, tax_reports)
3. ✓ All foreign key relationships are established
4. ✓ All indexes are created
5. ✓ All enum types are defined
6. ✓ 2026 tax configuration is seeded successfully
7. ✓ Sample data can be inserted and queried
8. ✓ Migration can be rolled back cleanly
9. ✓ Migration can be re-applied after rollback

## Next Steps

After successful migration testing:

1. Apply migration to development database
2. Run property-based tests (tasks 2.2, 2.4)
3. Test encryption/decryption of sensitive fields
4. Proceed to task 3 (Checkpoint - Database schema complete)
