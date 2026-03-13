# Database Migrations

This directory contains Alembic migration scripts for the Austrian Tax Management System (Taxja).

## Migration 001: Initial Migration

**File**: `001_initial_migration.py`  
**Created**: 2026-03-04  
**Requirements**: 9.1, 9.2

### Tables Created

This migration creates all core database tables for the system:

#### 1. **users** table
- Stores user accounts with encrypted sensitive fields
- Fields: id, email, password_hash, name, tax_number (encrypted), vat_number (encrypted), address (encrypted)
- User types: EMPLOYEE, SELF_EMPLOYED, LANDLORD, MIXED
- Includes family_info and commuting_info as JSON fields
- Two-factor authentication support
- Relationships: transactions, documents, tax_reports, loss_carryforwards

#### 2. **tax_configurations** table
- Stores yearly tax rates and rules
- Fields: tax_year (unique), tax_brackets (JSON), exemption_amount, vat_rates (JSON), svs_rates (JSON), deduction_config (JSON)
- Allows admin to update tax rates for each year
- Seeded with 2026 USP official tax rates

#### 3. **documents** table
- Stores uploaded documents and OCR results
- Fields: document_type, file_path, file_name, ocr_result (JSON), raw_text, confidence_score
- Document types: PAYSLIP, RECEIPT, INVOICE, RENTAL_CONTRACT, BANK_STATEMENT, PROPERTY_TAX, LOHNZETTEL, SVS_NOTICE, OTHER
- Links to user and optionally to transaction

#### 4. **transactions** table
- Stores income and expense transactions
- Fields: type (INCOME/EXPENSE), amount, transaction_date, description
- Income categories: EMPLOYMENT, RENTAL, SELF_EMPLOYMENT, CAPITAL_GAINS
- Expense categories: OFFICE_SUPPLIES, EQUIPMENT, TRAVEL, MARKETING, PROFESSIONAL_SERVICES, INSURANCE, MAINTENANCE, PROPERTY_TAX, LOAN_INTEREST, DEPRECIATION, GROCERIES, UTILITIES, COMMUTING, HOME_OFFICE, OTHER
- Includes VAT information and deductibility flags
- Links to user and optionally to document

#### 5. **loss_carryforwards** table
- Tracks losses across tax years (Verlustvortrag)
- Fields: loss_year, loss_amount, used_amount, remaining_amount
- Unique constraint on (user_id, loss_year)
- Automatically applies previous year losses to current year calculations

#### 6. **tax_reports** table
- Stores generated tax reports
- Fields: tax_year, income_summary (JSON), expense_summary (JSON), tax_calculation (JSON), deductions (JSON), net_income
- Includes paths to generated PDF and XML files
- Links to user

### Relationships

- **users** → **transactions** (one-to-many)
- **users** → **documents** (one-to-many)
- **users** → **tax_reports** (one-to-many)
- **users** → **loss_carryforwards** (one-to-many)
- **transactions** ↔ **documents** (many-to-one, bidirectional)

### Indexes

- `users.email` (unique)
- `users.id`
- `tax_configurations.tax_year` (unique)
- `documents.user_id`
- `documents.document_type`
- `transactions.user_id`
- `transactions.transaction_date`
- `transactions.type`
- `loss_carryforwards.user_id`
- `loss_carryforwards.loss_year`
- `tax_reports.user_id`
- `tax_reports.tax_year`

### Enums

- **UserType**: EMPLOYEE, SELF_EMPLOYED, LANDLORD, MIXED
- **TransactionType**: INCOME, EXPENSE
- **IncomeCategory**: EMPLOYMENT, RENTAL, SELF_EMPLOYMENT, CAPITAL_GAINS
- **ExpenseCategory**: OFFICE_SUPPLIES, EQUIPMENT, TRAVEL, MARKETING, PROFESSIONAL_SERVICES, INSURANCE, MAINTENANCE, PROPERTY_TAX, LOAN_INTEREST, DEPRECIATION, GROCERIES, UTILITIES, COMMUTING, HOME_OFFICE, OTHER
- **DocumentType**: PAYSLIP, RECEIPT, INVOICE, RENTAL_CONTRACT, BANK_STATEMENT, PROPERTY_TAX, LOHNZETTEL, SVS_NOTICE, OTHER

## Running Migrations

### Prerequisites

1. Ensure PostgreSQL is running
2. Create database: `createdb taxja`
3. Install dependencies: `pip install -r requirements.txt`

### Apply Migration

```bash
# Upgrade to latest version
alembic upgrade head

# Upgrade one version
alembic upgrade +1

# Show current version
alembic current

# Show migration history
alembic history
```

### Rollback Migration

```bash
# Downgrade one version
alembic downgrade -1

# Downgrade to base (empty database)
alembic downgrade base
```

### Verify Schema

After running the migration, verify the schema:

```bash
# Connect to database
psql -d taxja

# List tables
\dt

# Describe users table
\d users

# Describe transactions table
\d transactions
```

## Testing on Clean Database

To test the migration on a clean database:

```bash
# Create test database
createdb taxja_test

# Set test database URL
export DATABASE_URL="postgresql://taxja:taxja_password@localhost:5432/taxja_test"

# Run migration
alembic upgrade head

# Verify tables were created
psql -d taxja_test -c "\dt"

# Clean up
dropdb taxja_test
```

## Notes

- All sensitive fields (tax_number, vat_number, address, two_factor_secret) are stored as encrypted strings using AES-256-GCM encryption
- JSON fields are used for flexible data structures (family_info, commuting_info, OCR results, tax calculations)
- The migration handles circular foreign key references between transactions and documents
- Unique constraints ensure data integrity (email, tax_year, user_id+loss_year)
- Indexes are created on frequently queried columns for performance

## Next Steps

After applying this migration:

1. Seed the database with 2026 tax configuration using `get_2026_tax_config()`
2. Create test users for development
3. Run property-based tests to verify data integrity
4. Test encryption/decryption of sensitive fields
