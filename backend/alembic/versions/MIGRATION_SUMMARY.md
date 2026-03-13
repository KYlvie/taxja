# Migration 001: Summary

## Overview

Initial database migration for the Austrian Tax Management System (Taxja). This migration creates all core tables required for the system to function.

## What Was Created

### Database Tables (6 total)

1. **users** - User accounts with encrypted sensitive fields
2. **tax_configurations** - Yearly tax rates and rules (seeded with 2026 USP data)
3. **documents** - Uploaded documents and OCR results
4. **transactions** - Income and expense transactions
5. **loss_carryforwards** - Multi-year loss tracking (Verlustvortrag)
6. **tax_reports** - Generated tax reports

### Relationships

- Users have many transactions, documents, tax reports, and loss carryforwards
- Transactions belong to users and optionally link to documents
- Documents belong to users and optionally link to transactions
- Bidirectional relationship between transactions and documents

### Indexes

Created 15+ indexes on frequently queried columns:
- User email (unique)
- Transaction dates and user IDs
- Document types and user IDs
- Tax configuration years (unique)
- Loss carryforward years and user IDs
- Tax report years and user IDs

### Enums

Defined 5 enum types:
- UserType (4 values)
- TransactionType (2 values)
- IncomeCategory (4 values)
- ExpenseCategory (15 values)
- DocumentType (9 values)

## Files Created

1. **001_initial_migration.py** - Main migration file
2. **README.md** - Migration documentation
3. **MIGRATION_SUMMARY.md** - This file
4. **../verify_migration.py** - Migration structure verification script
5. **../seed_tax_config.py** - Script to seed 2026 tax configuration
6. **../MIGRATION_TEST_GUIDE.md** - Comprehensive testing guide

## Requirements Satisfied

- ✓ Requirement 9.1: Validate all transaction records' dates in valid tax year range
- ✓ Requirement 9.2: Validate all amount fields are positive with two decimal precision
- ✓ All models from tasks 2.1-2.7 are migrated

## How to Use

### Apply Migration

```bash
# Ensure PostgreSQL is running and database exists
createdb taxja

# Apply migration
alembic upgrade head

# Seed 2026 tax configuration
python seed_tax_config.py
```

### Verify Migration

```bash
# Verify migration structure
python verify_migration.py

# Connect to database and check tables
psql -d taxja -c "\dt"

# Check specific table
psql -d taxja -c "\d users"
```

### Rollback Migration

```bash
# Downgrade to previous version (empty database)
alembic downgrade -1

# Or downgrade to base
alembic downgrade base
```

## Testing

See **MIGRATION_TEST_GUIDE.md** for comprehensive testing instructions including:
- Structure verification
- Clean database testing
- Sample data insertion
- Rollback testing
- Common issues and solutions

## Data Integrity Features

### Constraints

- **Primary keys** on all tables
- **Foreign keys** with proper cascading
- **Unique constraints** on email, tax_year, (user_id, loss_year)
- **NOT NULL** constraints on required fields

### Data Types

- **Numeric(12, 2)** for monetary amounts (ensures 2 decimal precision)
- **Date** for transaction dates
- **DateTime** for timestamps
- **JSON** for flexible structured data
- **Enum** for categorical data with fixed values

### Security

- Sensitive fields (tax_number, vat_number, address, two_factor_secret) stored as encrypted strings
- Password stored as hash
- Encryption handled at application layer (AES-256-GCM)

## Performance Considerations

### Indexes

Indexes created on:
- Foreign keys (user_id columns)
- Frequently filtered columns (transaction_date, document_type, tax_year)
- Unique constraints (email, tax_year)

### JSON Fields

JSON fields used for:
- Flexible data structures (family_info, commuting_info)
- OCR results (variable structure)
- Tax calculations (complex nested data)

Benefits:
- No need for additional tables for variable data
- Easy to query with PostgreSQL JSON operators
- Flexible schema evolution

## Next Steps

After applying this migration:

1. ✓ Run property-based tests (tasks 2.2, 2.4)
2. ✓ Test encryption/decryption (task 2.2)
3. ✓ Test transaction unique identifiers (task 2.4)
4. ✓ Proceed to checkpoint task 3
5. ✓ Begin authentication system (task 4)

## Maintenance

### Adding New Migrations

```bash
# Create new migration
alembic revision -m "Description of changes"

# Edit the generated file in alembic/versions/
# Add upgrade() and downgrade() logic

# Test migration
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

### Updating Tax Configuration

```bash
# For new tax year, create new migration:
alembic revision -m "Add 2027 tax configuration"

# In the migration file:
def upgrade():
    # Insert new tax configuration
    op.execute("""
        INSERT INTO tax_configurations (tax_year, ...)
        VALUES (2027, ...)
    """)
```

## Notes

- Migration uses Alembic's `op.create_table()` for clean DDL generation
- Enum types are created automatically by SQLAlchemy
- Foreign keys handle circular references between transactions and documents
- All timestamps use UTC (datetime.utcnow)
- JSON fields use PostgreSQL's native JSON type for efficient querying

## Support

For issues or questions:
1. Check **MIGRATION_TEST_GUIDE.md** for common issues
2. Review **README.md** for detailed table documentation
3. Check Alembic logs: `alembic history --verbose`
4. Verify database state: `psql -d taxja -c "\d"`

## Version History

- **001** (2026-03-04): Initial migration - all core tables
