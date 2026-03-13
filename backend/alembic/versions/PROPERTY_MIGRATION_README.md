# Property Table Migration (002_add_property_table)

## Overview

This migration adds the `properties` table to support rental property asset management functionality in the Taxja platform. The table enables landlords to track rental properties, calculate depreciation (AfA), and link properties to income/expense transactions.

## Migration Details

- **Revision ID**: 002
- **Revises**: 001
- **Created**: 2026-03-07

## Database Changes

### New Enums

1. **propertytype**
   - `rental` - Property used for rental income
   - `owner_occupied` - Property used as primary residence
   - `mixed_use` - Property with both rental and personal use

2. **propertystatus**
   - `active` - Property is currently owned and active
   - `sold` - Property has been sold
   - `archived` - Property is archived (hidden from active list)

### New Table: properties

#### Columns

**Primary Key:**
- `id` (UUID) - Primary key, auto-generated

**Foreign Keys:**
- `user_id` (INTEGER) - References users.id, CASCADE on delete
- `kaufvertrag_document_id` (INTEGER) - References documents.id, SET NULL on delete
- `mietvertrag_document_id` (INTEGER) - References documents.id, SET NULL on delete

**Property Classification:**
- `property_type` (ENUM propertytype) - Type of property, default 'rental'
- `rental_percentage` (NUMERIC(5,2)) - Percentage used for rental (0-100), default 100.00

**Address:**
- `address` (VARCHAR(500)) - Full address string
- `street` (VARCHAR(255)) - Street address
- `city` (VARCHAR(100)) - City name
- `postal_code` (VARCHAR(10)) - Postal code

**Purchase Information:**
- `purchase_date` (DATE) - Date property was purchased
- `purchase_price` (NUMERIC(12,2)) - Total purchase price
- `building_value` (NUMERIC(12,2)) - Depreciable building value
- `land_value` (NUMERIC(12,2)) - Calculated land value (purchase_price - building_value)

**Purchase Costs:**
- `grunderwerbsteuer` (NUMERIC(12,2)) - Property transfer tax
- `notary_fees` (NUMERIC(12,2)) - Notary fees
- `registry_fees` (NUMERIC(12,2)) - Land registry fees (Eintragungsgebühr)

**Building Details:**
- `construction_year` (INTEGER) - Year building was constructed
- `depreciation_rate` (NUMERIC(5,4)) - Annual depreciation rate (0.001-0.10), default 0.02

**Status:**
- `status` (ENUM propertystatus) - Current status, default 'active'
- `sale_date` (DATE) - Date property was sold (if applicable)

**Timestamps:**
- `created_at` (TIMESTAMP) - Record creation timestamp
- `updated_at` (TIMESTAMP) - Record last update timestamp

#### Indexes

1. `ix_properties_user_id` - Index on user_id for fast user property lookups
2. `ix_properties_status` - Index on status for filtering by status
3. `ix_properties_user_status` - Composite index on (user_id, status) for efficient filtered queries

#### Constraints

1. **check_rental_percentage_range**: rental_percentage >= 0 AND rental_percentage <= 100
2. **check_purchase_price_range**: purchase_price > 0 AND purchase_price <= 100000000
3. **check_building_value_range**: building_value > 0 AND building_value <= purchase_price
4. **check_depreciation_rate_range**: depreciation_rate >= 0.001 AND depreciation_rate <= 0.10
5. **check_construction_year_range**: construction_year IS NULL OR (construction_year >= 1800 AND construction_year <= CURRENT_YEAR)
6. **check_sale_date_after_purchase**: sale_date IS NULL OR sale_date >= purchase_date
7. **check_sold_has_sale_date**: status != 'sold' OR sale_date IS NOT NULL

## Running the Migration

### Upgrade

To apply this migration:

```bash
cd backend
alembic upgrade head
```

Or to upgrade to this specific revision:

```bash
alembic upgrade 002
```

### Downgrade

To rollback this migration:

```bash
alembic downgrade 001
```

This will:
1. Drop all indexes
2. Drop the properties table
3. Drop the propertytype and propertystatus enums

## Verification

After running the migration, verify the table was created:

```sql
-- Check table exists
SELECT table_name 
FROM information_schema.tables 
WHERE table_name = 'properties';

-- Check columns
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'properties'
ORDER BY ordinal_position;

-- Check indexes
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'properties';

-- Check constraints
SELECT conname, contype, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'properties'::regclass;
```

## Austrian Tax Law Context

This table supports Austrian tax law requirements for rental property depreciation (AfA):

- **Buildings constructed before 1915**: 1.5% annual depreciation rate
- **Buildings constructed 1915 or later**: 2.0% annual depreciation rate
- **Only building value is depreciable** (land value is not depreciable)
- **Pro-rated depreciation** for partial year ownership
- **Mixed-use properties**: Only the rental percentage portion is depreciable

## Related Models

- **User Model**: One-to-many relationship (user.properties)
- **Transaction Model**: Will be extended with property_id foreign key in future migration
- **Document Model**: Optional references to Kaufvertrag and Mietvertrag documents

## Next Steps

After this migration:
1. Task 1.3: Extend Transaction model with property_id foreign key
2. Task 1.4: Create Property Pydantic schemas
3. Task 1.5: Implement AfA Calculator service
4. Task 1.6: Implement Property Management service
5. Task 1.7: Create Property API endpoints

## Notes

- The migration uses PostgreSQL-specific features (UUID, ENUM types)
- The `gen_random_uuid()` function requires PostgreSQL 13+
- All monetary values use NUMERIC(12,2) for precision
- Depreciation rate uses NUMERIC(5,4) to support rates like 0.015 (1.5%)
