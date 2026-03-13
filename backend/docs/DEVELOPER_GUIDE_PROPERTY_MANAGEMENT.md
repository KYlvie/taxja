# Developer Guide: Property Asset Management

## Table of Contents

1. [Overview](#overview)
2. [Service Architecture](#service-architecture)
3. [Database Schema](#database-schema)
4. [Integration Points](#integration-points)
5. [Testing Strategy](#testing-strategy)
6. [Development Workflow](#development-workflow)
7. [Common Tasks](#common-tasks)
8. [Troubleshooting](#troubleshooting)

## Overview

The Property Asset Management feature enables landlords to track rental properties, calculate depreciation (AfA - Absetzung für Abnutzung), link properties to transactions, and import historical property data for accurate multi-year tax calculations.

### Key Features

- Property registration with purchase details
- Automatic depreciation calculation per Austrian tax law
- Historical depreciation backfill for properties purchased in previous years
- Property-transaction linking for rental income and expenses
- E1/Bescheid import integration with address matching
- Multi-property portfolio management
- Automated year-end depreciation generation

### Tech Stack

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy 2.0
- **Database:** PostgreSQL 15+ with UUID support
- **Task Queue:** Celery for scheduled depreciation generation
- **Testing:** pytest, Hypothesis (property-based testing)
- **Frontend:** React 18, TypeScript, Zustand

## Service Architecture

### Layered Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    API Layer (FastAPI)                           │
│  /api/v1/properties/*  │  /api/v1/transactions/*                │
└────────────┬────────────────────────────────────────────────────┘
             │
┌────────────┴────────────────────────────────────────────────────┐
│                      Service Layer                               │
│  PropertyService  │  AfACalculator  │  AddressMatcher           │
│  HistoricalDepreciationService  │  AnnualDepreciationService    │
└────────────┬────────────────────────────────────────────────────┘
             │
┌────────────┴────────────────────────────────────────────────────┐
│                    Data Layer (SQLAlchemy)                       │
│  Property Model  │  Transaction Model  │  User Model            │
└────────────┬────────────────────────────────────────────────────┘
             │
┌────────────┴────────────────────────────────────────────────────┐
│                   Database (PostgreSQL)                          │
└─────────────────────────────────────────────────────────────────┘
```

### Core Services


#### 1. PropertyService

**Location:** `backend/app/services/property_service.py`

**Responsibility:** Core CRUD operations and business logic for property management.

**Key Methods:**
- `create_property()` - Create new property with auto-calculations
- `get_property()` - Retrieve property with ownership validation
- `list_properties()` - List user's properties with optional filters
- `update_property()` - Update property (restricted fields)
- `archive_property()` - Mark property as sold/archived
- `delete_property()` - Delete property (only if no linked transactions)
- `link_transaction()` - Associate transaction with property
- `calculate_property_metrics()` - Calculate financial metrics

**Auto-Calculations:**
- `building_value` defaults to 80% of `purchase_price` if not provided
- `depreciation_rate` determined by `construction_year` (1.5% pre-1915, 2.0% post-1915)
- `land_value` calculated as `purchase_price - building_value`

#### 2. AfACalculator

**Location:** `backend/app/services/afa_calculator.py`

**Responsibility:** Calculate depreciation (Absetzung für Abnutzung) per Austrian tax law.

**Key Methods:**
- `determine_depreciation_rate()` - Determine rate based on construction year
- `calculate_annual_depreciation()` - Calculate depreciation for a specific year
- `calculate_prorated_depreciation()` - Pro-rate for partial year ownership
- `get_accumulated_depreciation()` - Sum all depreciation to date

**Austrian Tax Law Rules:**
- Buildings constructed before 1915: 1.5% annual depreciation (§ 8 EStG)
- Buildings constructed 1915 or later: 2.0% annual depreciation
- Only building value is depreciable (land is not)
- Pro-rated for partial year ownership (based on months)
- Stops when accumulated depreciation reaches building value
- Mixed-use properties: only rental percentage is depreciable

#### 3. HistoricalDepreciationService

**Location:** `backend/app/services/historical_depreciation_service.py`

**Responsibility:** Backfill historical depreciation for properties purchased in previous years.

**Key Methods:**
- `calculate_historical_depreciation()` - Preview depreciation for all years (no DB changes)
- `backfill_depreciation()` - Create depreciation transactions for historical years

**Use Case:** New user registers a property bought in 2020. Service creates depreciation transactions for 2020, 2021, 2022, 2023, 2024, 2025 to ensure accurate accumulated depreciation.

**Transaction Details:**
- Dated December 31 of each year
- Category: `DEPRECIATION_AFA`
- Marked as `is_system_generated: true`
- Validates no duplicates exist

#### 4. AddressMatcher

**Location:** `backend/app/services/address_matcher.py`

**Responsibility:** Fuzzy matching of property addresses for E1/Bescheid import integration.

**Key Methods:**
- `match_address()` - Find properties matching an address string
- `_normalize_address()` - Normalize address for comparison
- `_calculate_similarity()` - Calculate Levenshtein distance

**Confidence Levels:**
- > 0.9: High confidence (auto-suggest)
- 0.7-0.9: Medium confidence (show as option)
- < 0.7: Low confidence (don't suggest)

**Use Case:** When importing E1 form with rental income from "Hauptstraße 123, 1010 Wien", match to existing property with similar address.

#### 5. AnnualDepreciationService

**Location:** `backend/app/services/annual_depreciation_service.py`

**Responsibility:** Generate annual depreciation transactions at year-end.

**Key Methods:**
- `generate_annual_depreciation()` - Generate depreciation for all active properties

**Execution:**
- Typically run via Celery scheduled task on December 31, 23:00
- Can be triggered manually by users or admins
- Processes all active properties
- Skips properties already depreciated for the year
- Skips fully depreciated properties

## Database Schema

### Property Table

**Table Name:** `properties`

**Key Columns:**
```sql
id                  UUID PRIMARY KEY
user_id             INTEGER NOT NULL (FK to users)
property_type       ENUM ('rental', 'owner_occupied', 'mixed_use')
rental_percentage   NUMERIC(5,2) DEFAULT 100.00
address             TEXT NOT NULL (encrypted)
street              TEXT NOT NULL (encrypted)
city                TEXT NOT NULL (encrypted)
postal_code         VARCHAR(10) NOT NULL
purchase_date       DATE NOT NULL
purchase_price      NUMERIC(12,2) NOT NULL
building_value      NUMERIC(12,2) NOT NULL
land_value          NUMERIC(12,2) GENERATED (purchase_price - building_value)
construction_year   INTEGER
depreciation_rate   NUMERIC(5,4) NOT NULL DEFAULT 0.02
status              ENUM ('active', 'sold', 'archived')
sale_date           DATE
created_at          TIMESTAMP NOT NULL
updated_at          TIMESTAMP NOT NULL
```

**Indexes:**
```sql
idx_properties_user_id          ON (user_id)
idx_properties_status           ON (status)
idx_properties_user_status      ON (user_id, status)
```

**Constraints:**
- `purchase_price > 0 AND purchase_price <= 100000000`
- `building_value > 0 AND building_value <= purchase_price`
- `depreciation_rate >= 0.001 AND depreciation_rate <= 0.10`
- `rental_percentage >= 0 AND rental_percentage <= 100`
- `status != 'sold' OR sale_date IS NOT NULL`

### Transaction Table Extension

**New Columns:**
```sql
property_id          UUID (FK to properties, nullable)
is_system_generated  BOOLEAN NOT NULL DEFAULT FALSE
```

**New Indexes:**
```sql
idx_transactions_property_id        ON (property_id)
idx_transactions_property_date      ON (property_id, transaction_date)
idx_transactions_depreciation       ON (expense_category, transaction_date) 
                                    WHERE expense_category = 'depreciation_afa'
```

### Entity Relationships

```
User (1) ──────── (*) Property
                       │
                       │ (1)
                       │
                       │ (*)
                       └──────── Transaction
```

- One user can have many properties
- One property can have many linked transactions
- Transactions can optionally link to a property
- Cascade delete: Deleting user deletes properties and transactions

## Integration Points

### 1. E1 Form Import Integration

**File:** `backend/app/services/e1_form_import_service.py`

**Integration:**
- Extract rental income from KZ 350 (Vermietung und Verpachtung)
- Extract property addresses from `vermietung_details`
- Use `AddressMatcher` to find matching properties
- Return `property_suggestions` with confidence scores

**Response Structure:**
```python
{
    "property_linking_required": True,
    "property_suggestions": [
        {
            "extracted_address": "Hauptstraße 123, 1010 Wien",
            "matches": [
                {
                    "property_id": "uuid",
                    "address": "Hauptstraße 123, 1010 Wien",
                    "confidence": 0.95,
                    "suggested_action": "auto_link"  # or "suggest" or "create_new"
                }
            ]
        }
    ]
}
```

### 2. Bescheid Import Integration

**File:** `backend/app/services/bescheid_import_service.py`

**Integration:**
- Similar to E1 import
- Bescheid is prioritized as authoritative source
- Auto-match properties with high confidence
- Validate rental income matches linked properties

### 3. Tax Calculation Engine Integration

**File:** `backend/app/services/tax_calculation_engine.py`

**Integration:**
- Include property depreciation in deductions
- Include rental income in total income
- Include property expenses in deductions
- Handle mixed-use property allocation

**New Methods:**
```python
_calculate_property_depreciation(user_id, year) -> Decimal
_calculate_rental_income(user_id, year) -> Decimal
_calculate_property_expenses(user_id, year) -> Decimal
```

### 4. Dashboard Integration

**File:** `backend/app/services/dashboard_service.py`

**Integration:**
- Add property portfolio metrics for landlord users
- Calculate portfolio-level aggregations
- Display property count, total building value, annual depreciation

**New Method:**
```python
_get_property_portfolio_metrics(user_id) -> Dict[str, Any]
```

## Testing Strategy

### Unit Tests

**Location:** `backend/tests/services/test_property_service.py`, `test_afa_calculator.py`

**Coverage:**
- Test all service methods with various inputs
- Test edge cases (partial year, fully depreciated, etc.)
- Test validation errors
- Test ownership validation

**Example:**
```python
def test_calculate_annual_depreciation_full_year():
    property = Property(
        building_value=Decimal("280000"),
        depreciation_rate=Decimal("0.02"),
        purchase_date=date(2020, 1, 1)
    )
    calculator = AfACalculator()
    depreciation = calculator.calculate_annual_depreciation(property, 2021)
    assert depreciation == Decimal("5600.00")
```

### Property-Based Tests (Hypothesis)

**Location:** `backend/tests/properties/test_afa_properties.py`

**Purpose:** Validate correctness properties that must hold for all inputs.

**Key Properties:**
1. **Depreciation Accumulation Invariant:** `sum(depreciation) <= building_value`
2. **Depreciation Rate Consistency:** `annual_depreciation = building_value * rate`
3. **Pro-Rata Correctness:** Partial year calculation is proportional
4. **Idempotence:** Calculating twice produces same result
5. **Metamorphic:** Doubling rate doubles depreciation

**Example:**
```python
from hypothesis import given, strategies as st

@given(
    building_value=st.decimals(min_value=10000, max_value=1000000, places=2),
    depreciation_rate=st.decimals(min_value=Decimal("0.015"), max_value=Decimal("0.02"), places=4)
)
def test_depreciation_idempotence(building_value, depreciation_rate):
    """Property: Calculating depreciation twice produces same result"""
    property = Property(
        building_value=building_value,
        depreciation_rate=depreciation_rate,
        purchase_date=date(2020, 1, 1)
    )
    
    calculator = AfACalculator()
    result1 = calculator.calculate_annual_depreciation(property, 2021)
    result2 = calculator.calculate_annual_depreciation(property, 2021)
    
    assert result1 == result2
```

### Integration Tests

**Location:** `backend/tests/integration/test_property_integration.py`

**Coverage:**
- E1 import with property linking
- Bescheid import with property matching
- Tax calculation with properties
- Historical depreciation backfill

**Example:**
```python
def test_e1_import_with_property_linking(db_session, test_user):
    # Create existing property
    property = Property(...)
    db_session.add(property)
    db_session.commit()
    
    # Import E1 with rental income
    service = E1FormImportService(db_session)
    result = service.import_from_ocr_text(e1_text, test_user.id)
    
    # Verify property linking suggestions
    assert result["property_linking_required"] is True
    assert result["property_suggestions"][0]["matches"][0]["confidence"] > 0.9
```

### End-to-End Tests

**Location:** `backend/tests/e2e/test_property_e2e.py`

**Coverage:**
- Complete property lifecycle (create → backfill → link → archive)
- E1 import to property linking flow
- Annual depreciation generation
- Multi-property portfolio

**Run E2E Tests:**
```bash
cd backend
pytest tests/e2e/test_property_e2e.py -v
```

## Development Workflow

### Setting Up Development Environment

```bash
# 1. Start infrastructure services
make dev
# or
docker-compose up -d postgres redis minio

# 2. Install backend dependencies
cd backend
pip install -r requirements.txt

# 3. Run database migrations
alembic upgrade head

# 4. Seed test data (optional)
python -m app.db.seed

# 5. Start backend server
uvicorn app.main:app --reload

# 6. In another terminal, start frontend
cd frontend
npm install
npm run dev
```

### Creating a New Migration

```bash
cd backend

# Auto-generate migration from model changes
alembic revision --autogenerate -m "add_property_table"

# Review generated migration file in alembic/versions/

# Apply migration
alembic upgrade head

# Rollback if needed
alembic downgrade -1
```

### Running Tests

```bash
cd backend

# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/services/test_property_service.py -v

# Run property-based tests only
pytest tests/properties/ -v

# Run with specific marker
pytest -m "property_based" -v
```

### Code Quality Checks

```bash
cd backend

# Format code
black .

# Lint code
ruff check .

# Type checking
mypy .

# Run all quality checks
make lint
```

## Common Tasks

### Task 1: Add a New Property Field

1. **Update Model** (`backend/app/models/property.py`):
```python
class Property(Base):
    # ... existing fields ...
    new_field = Column(String(255), nullable=True)
```

2. **Create Migration**:
```bash
alembic revision --autogenerate -m "add_new_field_to_property"
alembic upgrade head
```

3. **Update Pydantic Schemas** (`backend/app/schemas/property.py`):
```python
class PropertyCreate(BaseModel):
    # ... existing fields ...
    new_field: Optional[str] = None

class PropertyResponse(BaseModel):
    # ... existing fields ...
    new_field: Optional[str] = None
```

4. **Update Service Logic** if needed
5. **Add Tests**
6. **Update Frontend** types and forms

### Task 2: Add a New Depreciation Rule

1. **Update AfACalculator** (`backend/app/services/afa_calculator.py`):
```python
def determine_depreciation_rate(self, construction_year: Optional[int]) -> Decimal:
    if construction_year and construction_year < 1915:
        return Decimal("0.015")
    elif construction_year and construction_year >= 2000:
        return Decimal("0.025")  # New rule for modern buildings
    return Decimal("0.020")
```

2. **Add Unit Tests**:
```python
def test_determine_depreciation_rate_modern_building():
    calculator = AfACalculator()
    rate = calculator.determine_depreciation_rate(2010)
    assert rate == Decimal("0.025")
```

3. **Add Property-Based Tests** to validate new rule
4. **Update Documentation**

### Task 3: Add a New Property Expense Category

1. **Update Enum** (`backend/app/models/transaction.py`):
```python
class ExpenseCategory(str, Enum):
    # ... existing categories ...
    NEW_CATEGORY = "new_category"
```

2. **Update Tax Calculation** (`backend/app/services/tax_calculation_engine.py`):
```python
property_expense_categories = [
    ExpenseCategory.LOAN_INTEREST,
    # ... existing categories ...
    ExpenseCategory.NEW_CATEGORY,
]
```

3. **Update Frontend** translations and UI
4. **Add Tests**

### Task 4: Debug Depreciation Calculation Issue

1. **Enable Debug Logging**:
```python
import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def calculate_annual_depreciation(self, property: Property, year: int) -> Decimal:
    logger.debug(f"Calculating depreciation for property {property.id}, year {year}")
    logger.debug(f"Building value: {property.building_value}, Rate: {property.depreciation_rate}")
    # ... calculation logic ...
    logger.debug(f"Result: {final_amount}")
    return final_amount
```

2. **Check Database State**:
```sql
-- View property details
SELECT * FROM properties WHERE id = 'uuid';

-- View depreciation transactions
SELECT * FROM transactions 
WHERE property_id = 'uuid' 
  AND expense_category = 'depreciation_afa'
ORDER BY transaction_date;

-- Calculate accumulated depreciation
SELECT SUM(amount) as accumulated
FROM transactions
WHERE property_id = 'uuid'
  AND expense_category = 'depreciation_afa';
```

3. **Run Property-Based Tests** to validate correctness
4. **Check for Edge Cases** (partial year, fully depreciated, etc.)

## Troubleshooting

### Issue: Depreciation Not Generated

**Symptoms:** Annual depreciation task runs but no transactions created.

**Diagnosis:**
1. Check Celery logs: `docker-compose logs celery`
2. Verify property status is `active`
3. Check if depreciation already exists for the year
4. Verify property is not fully depreciated

**Solution:**
```python
# Manually trigger depreciation generation
from app.services.annual_depreciation_service import AnnualDepreciationService
from app.db.session import SessionLocal

db = SessionLocal()
service = AnnualDepreciationService(db)
result = service.generate_annual_depreciation(2025, user_id=123)
print(result)
```

### Issue: Address Matching Not Working

**Symptoms:** E1 import doesn't suggest property linking despite matching address.

**Diagnosis:**
1. Check address normalization logic
2. Verify Levenshtein library is installed: `pip install python-Levenshtein`
3. Test similarity calculation manually

**Solution:**
```python
from app.services.address_matcher import AddressMatcher

matcher = AddressMatcher(db)
matches = matcher.match_address("Hauptstraße 123, 1010 Wien", user_id=123)
for match in matches:
    print(f"Property: {match.property.address}, Confidence: {match.confidence}")
```

### Issue: Historical Backfill Creates Duplicates

**Symptoms:** Multiple depreciation transactions for the same year.

**Diagnosis:**
1. Check `_depreciation_exists()` logic
2. Verify unique constraint on (property_id, year, category)

**Solution:**
```sql
-- Find duplicates
SELECT property_id, EXTRACT(YEAR FROM transaction_date) as year, COUNT(*)
FROM transactions
WHERE expense_category = 'depreciation_afa'
GROUP BY property_id, year
HAVING COUNT(*) > 1;

-- Delete duplicates (keep earliest)
DELETE FROM transactions t1
WHERE expense_category = 'depreciation_afa'
  AND EXISTS (
    SELECT 1 FROM transactions t2
    WHERE t2.property_id = t1.property_id
      AND EXTRACT(YEAR FROM t2.transaction_date) = EXTRACT(YEAR FROM t1.transaction_date)
      AND t2.expense_category = 'depreciation_afa'
      AND t2.id < t1.id
  );
```

### Issue: Property Metrics Calculation Slow

**Symptoms:** `/api/v1/properties` endpoint takes > 1 second.

**Diagnosis:**
1. Check query execution plan: `EXPLAIN ANALYZE SELECT ...`
2. Verify indexes exist
3. Check for N+1 query problem

**Solution:**
```python
# Use optimized query with joins
def list_properties_with_metrics(self, user_id: int):
    query = self.db.query(
        Property,
        func.coalesce(func.sum(Transaction.amount), 0).label('accumulated_depreciation')
    ).outerjoin(
        Transaction,
        and_(
            Transaction.property_id == Property.id,
            Transaction.expense_category == ExpenseCategory.DEPRECIATION_AFA
        )
    ).filter(
        Property.user_id == user_id
    ).group_by(Property.id)
    
    return query.all()
```

### Issue: Celery Task Not Scheduled

**Symptoms:** Annual depreciation doesn't run automatically on December 31.

**Diagnosis:**
1. Check Celery Beat is running: `docker-compose ps celery-beat`
2. Verify beat schedule configuration
3. Check Celery Beat logs

**Solution:**
```python
# Verify beat schedule
from app.core.celery_app import app
print(app.conf.beat_schedule)

# Manually trigger task
from app.tasks.property_tasks import generate_annual_depreciation_task
result = generate_annual_depreciation_task.delay(2025)
print(result.get())
```

## Austrian Tax Law References

### Comprehensive Tax Law Documentation

For detailed Austrian tax law information related to property asset management, see:

**[Austrian Tax Law Reference: Property Asset Management](../../docs/AUSTRIAN_TAX_LAW_PROPERTY_REFERENCE.md)**

This comprehensive guide covers:
- **AfA Calculation Rules:** Depreciation rates, pro-rata calculations, building vs land value
- **Property Expense Categories:** Deductible and non-deductible expenses with E1 form field mappings
- **Owner-Occupied vs Rental Properties:** Tax treatment differences and exceptions
- **Mixed-Use Properties:** Allocation rules and rental percentage calculations
- **Property Purchase Costs:** Grunderwerbsteuer, notary fees, registry fees
- **Legal References:** § 7 EStG, § 8 EStG, § 28 EStG, and official BMF resources

### Quick Reference

**Depreciation Rates (§ 8 EStG):**
- Pre-1915 buildings: 1.5% annual
- 1915+ buildings: 2.0% annual

**E1 Form Fields:**
- KZ 350: Rental income (Einnahmen aus Vermietung)
- KZ 351: Rental expenses including AfA (Werbungskosten)

**Deductible Expense Categories:**
- Loan interest (Kreditzinsen)
- Maintenance and repairs (Instandhaltung)
- Property management fees (Hausverwaltung)
- Property insurance (Versicherungen)
- Property tax (Grundsteuer)
- Utilities (Betriebskosten)
- Depreciation (AfA)

**Non-Deductible for Owner-Occupied:**
- Purchase costs (capitalized for capital gains)
- Operating expenses
- Depreciation (not allowed)
- Exception: Home office (Arbeitszimmer) with limitations

### Implementation Guidelines

When implementing property tax calculations:

1. **Always use Decimal type** for monetary calculations (avoid float)
2. **Round to 2 decimal places** for all currency amounts
3. **Validate depreciation rate** is between 0.1% and 10%
4. **Check building value** does not exceed purchase price
5. **Pro-rate first/last year** based on months of ownership
6. **Respect building value limit** for accumulated depreciation
7. **Handle mixed-use** by applying rental percentage to building value

### Legal Compliance

**Disclaimer Requirements:**
- Platform is a reference tool, not official tax advice
- Users must file through FinanzOnline
- Complex cases require Steuerberater consultation
- Maintain audit trail for GDPR compliance

**Documentation Retention:**
- Property purchase contracts (Kaufvertrag): 7 years
- Rental agreements (Mietvertrag): 7 years
- Expense receipts and invoices: 7 years
- Tax assessments (Bescheid): Permanent

## Additional Resources

- **API Documentation:** `backend/docs/API_PROPERTY_ENDPOINTS.md`
- **Requirements Document:** `.kiro/specs/property-asset-management/requirements.md`
- **Design Document:** `.kiro/specs/property-asset-management/design.md`
- **Tasks Document:** `.kiro/specs/property-asset-management/tasks.md`
- **Austrian Tax Guide:** `docs/AUSTRIAN_TAX_GUIDE.md`
- **Property Tax Law Reference:** `docs/AUSTRIAN_TAX_LAW_PROPERTY_REFERENCE.md`

## Contact & Support

For questions or issues:
- Review existing tests for examples
- Check design document for architectural decisions
- Consult Austrian tax law references for compliance questions
- Run property-based tests to validate correctness

---

**Document Version:** 1.0  
**Last Updated:** 2026-03-08  
**Status:** Complete
