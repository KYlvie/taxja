# Property Asset Management - Database Schema Documentation

## Overview

This document provides comprehensive database schema documentation for the Property Asset Management feature in the Taxja platform. The schema supports rental property tracking, depreciation calculations (AfA), transaction linking, and Austrian tax law compliance.

## Entity Relationship Diagram

```
┌─────────────────┐         ┌──────────────────┐
│      User       │         │    Property      │
├─────────────────┤         ├──────────────────┤
│ id (PK)         │1      * │ id (PK)          │
│ email           │─────────│ user_id (FK)     │
│ name            │         │ property_type    │
│ user_type       │         │ rental_pct       │
│ ...             │         │ address          │
└─────────────────┘         │ street           │
                            │ city             │
                            │ postal_code      │
                            │ purchase_date    │
                            │ purchase_price   │
                            │ building_value   │
                            │ land_value       │
                            │ construction_year│
                            │ depreciation_rate│
                            │ status           │
                            │ sale_date        │
                            │ created_at       │
                            │ updated_at       │
                            └────────┬─────────┘
                                     │
                                     │1
                                     │
                                     │*
                            ┌────────┴─────────┐
                            │   Transaction    │
                            ├──────────────────┤
                            │ id (PK)          │
                            │ user_id (FK)     │
                            │ property_id (FK) │
                            │ type             │
                            │ amount           │
                            │ transaction_date │
                            │ description      │
                            │ income_category  │
                            │ expense_category │
                            │ is_deductible    │
                            │ is_system_gen    │
                            │ ...              │
                            └──────────────────┘
```

## Tables

### properties

The `properties` table stores rental property information for landlords.

#### Schema Definition

```sql
CREATE TYPE property_type AS ENUM ('rental', 'owner_occupied', 'mixed_use');
CREATE TYPE property_status AS ENUM ('active', 'sold', 'archived');

CREATE TABLE properties (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Foreign Keys
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kaufvertrag_document_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
    mietvertrag_document_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
    
    -- Property Classification
    property_type property_type NOT NULL DEFAULT 'rental',
    rental_percentage NUMERIC(5,2) DEFAULT 100.00 
        CHECK (rental_percentage >= 0 AND rental_percentage <= 100),
    
    -- Address Information
    address TEXT NOT NULL,
    street TEXT NOT NULL,
    city TEXT NOT NULL,
    postal_code VARCHAR(10) NOT NULL,
    
    -- Purchase Information
    purchase_date DATE NOT NULL,
    purchase_price NUMERIC(12,2) NOT NULL 
        CHECK (purchase_price > 0 AND purchase_price <= 100000000),
    building_value NUMERIC(12,2) NOT NULL 
        CHECK (building_value > 0 AND building_value <= purchase_price),
    land_value NUMERIC(12,2) GENERATED ALWAYS AS (purchase_price - building_value) STORED,
    
    -- Purchase Costs (for owner-occupied tracking)
    grunderwerbsteuer NUMERIC(12,2),  -- Property transfer tax
    notary_fees NUMERIC(12,2),
    registry_fees NUMERIC(12,2),      -- Eintragungsgebühr
    
    -- Building Details
    construction_year INTEGER 
        CHECK (construction_year >= 1800 AND construction_year <= EXTRACT(YEAR FROM CURRENT_DATE)),
    depreciation_rate NUMERIC(5,4) NOT NULL DEFAULT 0.02 
        CHECK (depreciation_rate >= 0.001 AND depreciation_rate <= 0.10),
    
    -- Status
    status property_status NOT NULL DEFAULT 'active',
    sale_date DATE CHECK (sale_date IS NULL OR sale_date >= purchase_date),
    
    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT valid_sale_date CHECK (status != 'sold' OR sale_date IS NOT NULL)
);
```

#### Indexes

```sql
-- User-based queries
CREATE INDEX idx_properties_user_id ON properties(user_id);

-- Status filtering
CREATE INDEX idx_properties_status ON properties(status);

-- Combined user + status queries (most common)
CREATE INDEX idx_properties_user_status ON properties(user_id, status);
```

#### Field Descriptions

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `id` | UUID | NO | Primary key, auto-generated |
| `user_id` | INTEGER | NO | Foreign key to users table, CASCADE delete |
| `property_type` | ENUM | NO | Type: rental, owner_occupied, mixed_use (default: rental) |
| `rental_percentage` | NUMERIC(5,2) | YES | For mixed-use properties, percentage used for rental (0-100) |
| `address` | TEXT | NO | Full address string (encrypted in application layer) |
| `street` | TEXT | NO | Street address component (encrypted) |
| `city` | TEXT | NO | City component (encrypted) |
| `postal_code` | VARCHAR(10) | NO | Postal code |
| `purchase_date` | DATE | NO | Date property was purchased |
| `purchase_price` | NUMERIC(12,2) | NO | Total purchase price (0 < value <= 100M) |
| `building_value` | NUMERIC(12,2) | NO | Depreciable building value (must be <= purchase_price) |
| `land_value` | NUMERIC(12,2) | NO | Computed: purchase_price - building_value (STORED) |
| `grunderwerbsteuer` | NUMERIC(12,2) | YES | Property transfer tax paid |
| `notary_fees` | NUMERIC(12,2) | YES | Notary fees paid |
| `registry_fees` | NUMERIC(12,2) | YES | Land registry fees (Eintragungsgebühr) |
| `construction_year` | INTEGER | YES | Year building was constructed (1800-current year) |
| `depreciation_rate` | NUMERIC(5,4) | NO | Annual depreciation rate (0.001-0.10, default: 0.02) |
| `status` | ENUM | NO | Status: active, sold, archived (default: active) |
| `sale_date` | DATE | YES | Date property was sold (required if status='sold') |
| `kaufvertrag_document_id` | INTEGER | YES | Link to purchase contract document |
| `mietvertrag_document_id` | INTEGER | YES | Link to rental contract document |
| `created_at` | TIMESTAMP | NO | Record creation timestamp |
| `updated_at` | TIMESTAMP | NO | Last update timestamp |

#### Business Rules

1. **Building Value Calculation**: If not provided, defaults to 80% of purchase_price (Austrian tax convention)
2. **Depreciation Rate Determination**: 
   - Buildings constructed before 1915: 1.5% (0.015)
   - Buildings constructed 1915 or later: 2.0% (0.020)
3. **Land Value**: Automatically calculated as purchase_price - building_value (non-depreciable)
4. **Mixed-Use Properties**: rental_percentage determines what portion of building_value is depreciable
5. **Sale Date Validation**: If status is 'sold', sale_date must be provided and >= purchase_date

### transactions (Extension)

The existing `transactions` table is extended with property-related fields.

#### Schema Extension

```sql
-- Add property_id column to existing transactions table
ALTER TABLE transactions 
ADD COLUMN property_id UUID REFERENCES properties(id) ON DELETE SET NULL;

-- Add system-generated flag for depreciation transactions
ALTER TABLE transactions
ADD COLUMN is_system_generated BOOLEAN NOT NULL DEFAULT FALSE;
```

#### New Indexes

```sql
-- Property-based transaction queries
CREATE INDEX idx_transactions_property_id ON transactions(property_id);

-- Property + date range queries (common for reports)
CREATE INDEX idx_transactions_property_date ON transactions(property_id, transaction_date);

-- User + property queries
CREATE INDEX idx_transactions_user_property ON transactions(user_id, property_id);

-- Depreciation-specific queries
CREATE INDEX idx_transactions_depreciation ON transactions(expense_category, transaction_date) 
WHERE expense_category = 'depreciation_afa';
```

#### New Field Descriptions

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `property_id` | UUID | YES | Foreign key to properties table, SET NULL on delete |
| `is_system_generated` | BOOLEAN | NO | True for auto-generated depreciation transactions (default: false) |

#### Property-Related Transaction Types

**Income Categories:**
- `rental` - Rental income (Vermietung und Verpachtung)

**Expense Categories:**
- `depreciation_afa` - Depreciation (Absetzung für Abnutzung)
- `loan_interest` - Mortgage/loan interest
- `maintenance` - Maintenance and repairs
- `property_management_fees` - Property management fees
- `property_insurance` - Property insurance
- `property_tax` - Property tax (Grundsteuer)
- `utilities` - Utilities (if paid by landlord)

## Enums

### property_type

Defines the usage classification of a property.

```sql
CREATE TYPE property_type AS ENUM (
    'rental',           -- Fully rented property (Vermietung)
    'owner_occupied',   -- Owner-occupied property (Eigennutzung)
    'mixed_use'         -- Mixed rental and personal use (Gemischt)
);
```

**Usage:**
- `rental`: 100% rental use, full depreciation applies
- `owner_occupied`: Personal residence, no depreciation (purchase costs tracked for capital gains)
- `mixed_use`: Partial rental (e.g., 50%), depreciation applies to rental_percentage only

### property_status

Defines the current status of a property.

```sql
CREATE TYPE property_status AS ENUM (
    'active',    -- Currently owned and active
    'sold',      -- Property has been sold
    'archived'   -- Archived (hidden from active list)
);
```

**Status Transitions:**
- `active` → `sold`: When property is sold (requires sale_date)
- `active` → `archived`: Manual archival (preserves all data)
- `sold` → `archived`: Sold properties can be archived

## Migrations

### Migration 002: Add Property Table

**File:** `backend/alembic/versions/002_add_property_table.py`

**Operations:**
1. Create `property_type` enum
2. Create `property_status` enum
3. Create `properties` table with all fields and constraints
4. Create indexes on user_id, status, and composite user_id+status

**Downgrade:**
- Drops properties table
- Drops enum types
- Drops indexes

### Migration 003: Add Property ID to Transactions

**File:** `backend/alembic/versions/003_add_property_id_to_transactions.py`

**Operations:**
1. Add `property_id` column to transactions table (nullable UUID)
2. Add foreign key constraint to properties(id) with ON DELETE SET NULL
3. Add `is_system_generated` column (boolean, default false)
4. Create indexes on property_id and property_id+transaction_date

**Downgrade:**
- Drops indexes
- Drops property_id and is_system_generated columns

### Migration 004: Add Property Loans Table (Phase 3)

**File:** `backend/alembic/versions/004_add_property_loans_table.py`

**Operations:**
1. Create `property_loans` table for tracking property financing
2. Link loans to properties via property_id foreign key
3. Track loan amount, interest rate, payment schedule

**Status:** Completed (Phase 3)

## Data Integrity Rules

### Referential Integrity

1. **User → Property**: CASCADE delete
   - When a user is deleted, all their properties are deleted
   
2. **Property → Transaction**: SET NULL on delete
   - When a property is deleted, linked transactions remain but property_id is set to NULL
   - Preserves transaction history for tax purposes
   
3. **Document → Property**: SET NULL on delete
   - When a document is deleted, property reference is cleared but property remains

### Check Constraints

1. **purchase_price**: Must be > 0 and <= 100,000,000
2. **building_value**: Must be > 0 and <= purchase_price
3. **rental_percentage**: Must be >= 0 and <= 100
4. **depreciation_rate**: Must be >= 0.001 and <= 0.10
5. **construction_year**: Must be >= 1800 and <= current year
6. **sale_date**: Must be >= purchase_date (if provided)
7. **valid_sale_date**: If status='sold', sale_date must not be NULL

### Computed Fields

1. **land_value**: GENERATED ALWAYS AS (purchase_price - building_value) STORED
   - Automatically calculated and stored
   - Cannot be manually set
   - Updated automatically when purchase_price or building_value changes

## Query Patterns

### Common Queries

#### Get User's Active Properties

```sql
SELECT * FROM properties
WHERE user_id = :user_id
  AND status = 'active'
ORDER BY purchase_date DESC;
```

**Index Used:** `idx_properties_user_status`

#### Get Property with Accumulated Depreciation

```sql
SELECT 
    p.*,
    COALESCE(SUM(t.amount), 0) as accumulated_depreciation,
    p.building_value - COALESCE(SUM(t.amount), 0) as remaining_value
FROM properties p
LEFT JOIN transactions t ON t.property_id = p.id 
    AND t.expense_category = 'depreciation_afa'
WHERE p.id = :property_id
GROUP BY p.id;
```

**Indexes Used:** 
- `properties` primary key
- `idx_transactions_property_id`
- `idx_transactions_depreciation`

#### Get Property Transactions for Year

```sql
SELECT * FROM transactions
WHERE property_id = :property_id
  AND EXTRACT(YEAR FROM transaction_date) = :year
ORDER BY transaction_date DESC;
```

**Index Used:** `idx_transactions_property_date`

#### Calculate Portfolio Metrics

```sql
SELECT 
    COUNT(*) as total_properties,
    SUM(building_value) as total_building_value,
    SUM(building_value * depreciation_rate) as total_annual_depreciation
FROM properties
WHERE user_id = :user_id
  AND status = 'active';
```

**Index Used:** `idx_properties_user_status`

## Performance Considerations

### Index Strategy

1. **Composite Indexes**: user_id + status is the most common query pattern
2. **Partial Indexes**: Depreciation transactions use a partial index (WHERE clause)
3. **Foreign Key Indexes**: All foreign keys have indexes for join performance

### Query Optimization

1. **Avoid N+1 Queries**: Use JOINs with aggregations to fetch properties with metrics in single query
2. **Caching**: Property metrics (accumulated depreciation) cached for 1 hour
3. **Batch Operations**: Annual depreciation generation processes all properties in batches

### Data Volume Estimates

- **Properties per user**: 1-10 (typical landlord)
- **Transactions per property per year**: 12-50 (monthly rent + expenses)
- **Depreciation transactions per property**: 1 per year
- **Total properties in system**: 10,000-100,000 (estimated)

## Security & Privacy

### Data Encryption

**Sensitive fields encrypted at application layer:**
- `address` (full address string)
- `street` (street component)
- `city` (city component)

**Encryption Method:** AES-256 via application-level encryption service

**Note:** postal_code is NOT encrypted to allow for regional analytics

### Access Control

**All property operations validate ownership:**
```python
def _validate_ownership(property_id: UUID, user_id: int):
    property = db.query(Property).filter(
        Property.id == property_id,
        Property.user_id == user_id
    ).first()
    if not property:
        raise HTTPException(status_code=404, detail="Property not found")
```

### GDPR Compliance

**Right to Erasure:**
- User deletion cascades to properties
- Properties cascade to property_loans (if implemented)
- Transactions preserve history but property_id is set to NULL

**Data Retention:**
- Active properties: Retained indefinitely
- Sold/archived properties: Retained for 7 years (Austrian tax law)
- Transactions: Retained for 7 years minimum

## Austrian Tax Law Compliance

### Depreciation Rules (§ 8 EStG)

1. **Depreciation Rates:**
   - Pre-1915 buildings: 1.5% annual (66.67 years)
   - 1915+ buildings: 2.0% annual (50 years)

2. **Depreciable Value:**
   - Only building value (not land)
   - For mixed-use: Only rental percentage portion

3. **Depreciation Period:**
   - Starts: Month of purchase (pro-rated first year)
   - Ends: When accumulated depreciation = building_value OR property sold

### Rental Income (§ 28 EStG)

**Deductible Expenses:**
- Depreciation (AfA)
- Loan interest
- Maintenance and repairs
- Property management fees
- Property insurance
- Property tax (Grundsteuer)
- Utilities (if paid by landlord)

**Non-Deductible:**
- Land value (not depreciable)
- Principal loan payments
- Personal use portion (for mixed-use properties)

### Owner-Occupied Properties

**Purchase Costs (generally NOT deductible):**
- Grunderwerbsteuer (property transfer tax)
- Notary fees
- Registry fees (Eintragungsgebühr)

**Exception:** Tracked for capital gains tax calculation (ImmoESt) upon future sale

## Migration Testing

### Test Procedures

**Migration 002 (Properties Table):**
```bash
cd backend
python test_migration_002.py
```

**Validates:**
- Table creation
- All 23 columns with correct types
- Enum types (propertytype, propertystatus)
- 3 indexes
- 3 foreign keys
- 7 check constraints
- Downgrade cleanup

**Migration 003 (Property ID in Transactions):**
```bash
cd backend
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

**Validates:**
- Column addition
- Foreign key constraint
- Index creation
- Downgrade removes all objects

## Future Enhancements

### Phase 3 Additions

1. **property_loans table**: Track property financing
2. **tenants table**: Track tenant information
3. **property_documents table**: Link multiple documents per property
4. **property_valuations table**: Track property value over time

### Potential Optimizations

1. **Materialized Views**: Pre-compute property metrics for dashboard
2. **Partitioning**: Partition transactions by year for large datasets
3. **Read Replicas**: Separate read/write databases for reporting

## References

- **Austrian Tax Law**: § 8 EStG (Depreciation), § 28 EStG (Rental Income)
- **SQLAlchemy Models**: `backend/app/models/property.py`
- **Pydantic Schemas**: `backend/app/schemas/property.py`
- **API Documentation**: `backend/app/api/v1/endpoints/properties.py`
- **Service Layer**: `backend/app/services/property_service.py`, `backend/app/services/afa_calculator.py`

---

**Document Version:** 1.0  
**Last Updated:** 2026-03-07  
**Maintained By:** Taxja Development Team
