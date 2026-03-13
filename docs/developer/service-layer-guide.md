# Property Asset Management - Service Layer Guide

## Overview

This document provides comprehensive technical documentation for the service layer of the Property Asset Management feature in Taxja. The service layer implements business logic for property tracking, depreciation calculations (AfA), transaction linking, and Austrian tax law compliance.

## Architecture

### Service Layer Pattern

The property management system follows a layered architecture:

```
API Layer (FastAPI)
       ↓
Service Layer (Business Logic)
       ↓
Data Layer (SQLAlchemy ORM)
       ↓
Database (PostgreSQL)
```

### Core Services

1. **PropertyService** - CRUD operations and property management
2. **AfACalculator** - Depreciation calculations (Austrian tax law)
3. **HistoricalDepreciationService** - Historical depreciation backfill
4. **AddressMatcher** - Fuzzy address matching for imports
5. **AnnualDepreciationService** - Year-end depreciation generation

---

## 1. PropertyService

**Location:** `backend/app/services/property_service.py`

**Responsibility:** Core CRUD operations and business logic for property management.

### Class Definition

```python
class PropertyService:
    """Main service for property management operations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.afa_calculator = AfACalculator()
```

### Methods

#### create_property()

Creates a new property with validation and auto-calculations.

**Signature:**
```python
def create_property(
    self, 
    user_id: int, 
    property_data: PropertyCreate
) -> Property
```

**Auto-calculations:**
- `building_value` = 80% of `purchase_price` if not provided
- `depreciation_rate` based on `construction_year` (1.5% or 2.0%)
- `land_value` = `purchase_price` - `building_value`

**Validation:**
- `purchase_price` > 0 and <= 100,000,000
- `building_value` > 0 and <= `purchase_price`
- `purchase_date` not in future
- Address fields (street, city, postal_code) required

**Example:**
```python
property_service = PropertyService(db)
property = property_service.create_property(
    user_id=123,
    property_data=PropertyCreate(
        street="Hauptstraße 123",
        city="Wien",
        postal_code="1010",
        purchase_date=date(2020, 6, 15),
        purchase_price=Decimal("350000.00"),
        construction_year=1985
    )
)
# Auto-calculated: building_value=280000.00, depreciation_rate=0.02
```

#### get_property()

Retrieves a property with ownership validation.

**Signature:**
```python
def get_property(self, property_id: UUID, user_id: int) -> Property
```

**Raises:**
- `HTTPException(404)` if property not found or doesn't belong to user

#### list_properties()

Lists user's properties with optional archived filter.

**Signature:**
```python
def list_properties(
    self, 
    user_id: int, 
    include_archived: bool = False
) -> List[Property]
```

**Returns:** List of properties ordered by purchase_date DESC

#### update_property()

Updates property fields (restricted fields: purchase_date, purchase_price).

**Signature:**
```python
def update_property(
    self, 
    property_id: UUID, 
    user_id: int, 
    updates: PropertyUpdate
) -> Property
```

**Immutable Fields:**
- `purchase_date` - Cannot be changed after creation
- `purchase_price` - Cannot be changed after creation

**Reason:** These fields affect historical depreciation calculations


#### archive_property()

Marks property as sold and archived.

**Signature:**
```python
def archive_property(
    self, 
    property_id: UUID, 
    user_id: int, 
    sale_date: date
) -> Property
```

**Actions:**
- Sets `status` to 'sold'
- Sets `sale_date`
- Stops future depreciation generation

#### link_transaction()

Links a transaction to a property with validation.

**Signature:**
```python
def link_transaction(
    self, 
    transaction_id: int, 
    property_id: UUID, 
    user_id: int
) -> Transaction
```

**Validation:**
- Both property and transaction must belong to user
- Property must exist and be active

#### calculate_property_metrics()

Calculates financial metrics for a property.

**Signature:**
```python
def calculate_property_metrics(
    self, 
    property_id: UUID, 
    year: Optional[int] = None
) -> PropertyMetrics
```

**Returns:**
```python
PropertyMetrics(
    accumulated_depreciation=Decimal,  # Total depreciation to date
    remaining_depreciable_value=Decimal,  # building_value - accumulated
    rental_income=Decimal,  # Total rental income (year or YTD)
    expenses=Decimal,  # Total expenses (year or YTD)
    net_income=Decimal  # rental_income - expenses
)
```

---

## 2. AfACalculator

**Location:** `backend/app/services/afa_calculator.py`

**Responsibility:** Calculate depreciation (Absetzung für Abnutzung) according to Austrian tax law.

### Austrian Tax Law Context

**§ 8 EStG (Einkommensteuergesetz):**
- Buildings constructed before 1915: 1.5% annual depreciation
- Buildings constructed 1915 or later: 2.0% annual depreciation
- Only building value is depreciable (not land)
- Pro-rated for partial year ownership
- Stops when accumulated depreciation reaches building value

### Class Definition

```python
class AfACalculator:
    """
    Calculates depreciation for rental properties.
    Implements Austrian tax law (§ 8 EStG).
    """
    
    def __init__(self, db: Session):
        self.db = db
```


### Methods

#### determine_depreciation_rate()

Determines depreciation rate based on construction year.

**Signature:**
```python
def determine_depreciation_rate(
    self, 
    construction_year: Optional[int]
) -> Decimal
```

**Logic:**
- Pre-1915 buildings: `Decimal("0.015")` (1.5%)
- 1915+ buildings: `Decimal("0.020")` (2.0%)
- Unknown year: `Decimal("0.020")` (default)

**Example:**
```python
calculator = AfACalculator(db)
rate = calculator.determine_depreciation_rate(1900)  # Returns 0.015
rate = calculator.determine_depreciation_rate(1985)  # Returns 0.020
```

#### calculate_annual_depreciation()

Calculates annual depreciation for a property in a given year.

**Signature:**
```python
def calculate_annual_depreciation(
    self, 
    property: Property, 
    year: int
) -> Decimal
```

**Handles:**
1. Full year depreciation
2. Pro-rated first year (based on purchase month)
3. Pro-rated last year (if sold mid-year)
4. Building value limit (stops when fully depreciated)
5. Mixed-use properties (only rental percentage)

**Algorithm:**
```python
# 1. Check ownership period
if year < property.purchase_date.year:
    return Decimal("0")

# 2. Get accumulated depreciation
accumulated = get_accumulated_depreciation(property.id, year - 1)

# 3. Calculate depreciable value
depreciable_value = property.building_value
if property.property_type == PropertyType.MIXED_USE:
    depreciable_value *= (property.rental_percentage / 100)

# 4. Check if fully depreciated
if accumulated >= depreciable_value:
    return Decimal("0")

# 5. Calculate base annual amount
annual_amount = depreciable_value * property.depreciation_rate

# 6. Pro-rate for partial year
months_owned = calculate_months_owned(property, year)
if months_owned < 12:
    annual_amount = (annual_amount * months_owned) / 12

# 7. Ensure we don't exceed building value
remaining = depreciable_value - accumulated
final_amount = min(annual_amount, remaining)

return final_amount.quantize(Decimal("0.01"))
```


**Example:**
```python
# Full year depreciation
property = Property(
    building_value=Decimal("280000"),
    depreciation_rate=Decimal("0.02"),
    purchase_date=date(2020, 1, 1)
)
depreciation = calculator.calculate_annual_depreciation(property, 2021)
# Returns: 5600.00 (280000 * 0.02)

# Partial year (purchased mid-year)
property = Property(
    building_value=Decimal("280000"),
    depreciation_rate=Decimal("0.02"),
    purchase_date=date(2020, 7, 1)  # July 1
)
depreciation = calculator.calculate_annual_depreciation(property, 2020)
# Returns: 2800.00 (280000 * 0.02 * 6/12)
```

#### get_accumulated_depreciation()

Gets total accumulated depreciation for a property.

**Signature:**
```python
def get_accumulated_depreciation(
    self, 
    property_id: UUID, 
    up_to_year: Optional[int] = None
) -> Decimal
```

**Query:**
```sql
SELECT SUM(amount) 
FROM transactions
WHERE property_id = :property_id
  AND expense_category = 'depreciation_afa'
  AND EXTRACT(YEAR FROM transaction_date) <= :up_to_year
```

**Returns:** Total depreciation amount or `Decimal("0")` if none

---

## 3. HistoricalDepreciationService

**Location:** `backend/app/services/historical_depreciation_service.py`

**Responsibility:** Backfill historical depreciation for properties purchased in previous years.

### Use Case

When a new user registers a property bought in 2020, they need depreciation transactions for 2020, 2021, 2022, 2023, 2024, 2025 to have accurate accumulated depreciation.

### Class Definition

```python
class HistoricalDepreciationService:
    """
    Backfills depreciation transactions for properties 
    purchased in previous years.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.afa_calculator = AfACalculator(db)
```

### Methods

#### calculate_historical_depreciation()

Calculates depreciation for all years from purchase to current year.

**Signature:**
```python
def calculate_historical_depreciation(
    self, 
    property_id: UUID
) -> List[HistoricalDepreciationYear]
```

**Returns:** List of (year, amount, transaction_date) tuples for preview

**Does NOT create transactions** - preview only


#### backfill_depreciation()

Creates historical depreciation transactions.

**Signature:**
```python
def backfill_depreciation(
    self, 
    property_id: UUID, 
    user_id: int
) -> BackfillResult
```

**Actions:**
1. Validates ownership
2. Calculates historical depreciation
3. Creates transactions dated December 31 of each year
4. Marks as `is_system_generated=True`
5. Validates no duplicates
6. Commits all transactions atomically

**Transaction Properties:**
```python
Transaction(
    user_id=user_id,
    property_id=property_id,
    type=TransactionType.EXPENSE,
    amount=year_data.amount,
    transaction_date=date(year, 12, 31),  # Year-end
    description=f"AfA {property.address} ({year})",
    expense_category=ExpenseCategory.DEPRECIATION_AFA,
    is_deductible=True,
    is_system_generated=True,  # Flag for system-generated
    import_source="historical_backfill"
)
```

**Returns:**
```python
BackfillResult(
    property_id=UUID,
    years_backfilled=int,
    total_amount=Decimal,
    transactions=List[Transaction]
)
```

**Error Handling:**
- Rollback on any error
- Prevents duplicate transactions
- Validates ownership

**Example:**
```python
service = HistoricalDepreciationService(db)

# Preview
preview = service.calculate_historical_depreciation(property_id)
# Returns: [
#   HistoricalDepreciationYear(year=2020, amount=2800.00, ...),
#   HistoricalDepreciationYear(year=2021, amount=5600.00, ...),
#   ...
# ]

# Execute
result = service.backfill_depreciation(property_id, user_id)
# Creates 6 transactions, returns summary
```

---

## 4. AddressMatcher

**Location:** `backend/app/services/address_matcher.py`

**Responsibility:** Fuzzy matching of property addresses for E1/Bescheid import integration.

### Use Case

When importing E1/Bescheid with rental income, automatically suggest linking to existing properties based on address matching.

### Class Definition

```python
class AddressMatcher:
    """
    Matches property addresses using fuzzy string matching.
    Used for E1/Bescheid import property linking.
    """
    
    def __init__(self, db: Session):
        self.db = db
```


### Methods

#### match_address()

Finds properties matching the given address string.

**Signature:**
```python
def match_address(
    self, 
    address_string: str, 
    user_id: int
) -> List[AddressMatch]
```

**Confidence Levels:**
- `> 0.9`: High confidence (auto-suggest)
- `0.7-0.9`: Medium confidence (show as option)
- `< 0.7`: Low confidence (don't suggest)

**Algorithm:**
1. Normalize input address (lowercase, standardize abbreviations)
2. Query user's active properties
3. For each property:
   - Calculate overall similarity (Levenshtein distance)
   - Calculate component-wise similarity (street, city, postal)
   - Apply postal code exact match bonus (+0.2)
   - Compute final confidence score
4. Filter matches with confidence >= 0.7
5. Sort by confidence descending

**Normalization:**
```python
def _normalize_address(self, address: str) -> str:
    normalized = address.lower()
    
    # Standardize Austrian address terms
    replacements = {
        "str.": "strasse",
        "straße": "strasse",
        "gasse": "gasse",
        "platz": "platz",
        "weg": "weg",
        "allee": "allee",
    }
    
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    
    return " ".join(normalized.split())  # Remove extra whitespace
```

**Example:**
```python
matcher = AddressMatcher(db)
matches = matcher.match_address("Hauptstr. 123, 1010 Wien", user_id=123)

# Returns:
# [
#   AddressMatch(
#     property=Property(address="Hauptstraße 123, 1010 Wien"),
#     confidence=0.95,
#     matched_components={
#       "street": True,
#       "postal_code": True,
#       "city": True
#     }
#   )
# ]
```

---

## 5. AnnualDepreciationService

**Location:** `backend/app/services/annual_depreciation_service.py`

**Responsibility:** Generate annual depreciation transactions at year-end for all active properties.

### Use Case

Typically run at year-end (December 31) via Celery scheduled task. Can also be triggered manually by users or admins.

### Class Definition

```python
class AnnualDepreciationService:
    """
    Generates annual depreciation transactions for all active properties.
    Run at year-end via Celery or manually triggered.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.afa_calculator = AfACalculator(db)
```


### Methods

#### generate_annual_depreciation()

Generates depreciation transactions for all active properties.

**Signature:**
```python
def generate_annual_depreciation(
    self, 
    year: int, 
    user_id: Optional[int] = None
) -> AnnualDepreciationResult
```

**Parameters:**
- `year`: Tax year to generate depreciation for
- `user_id`: If provided, only generate for this user's properties

**Algorithm:**
1. Query active properties (optionally filtered by user)
2. For each property:
   - Check if depreciation already exists for year
   - Calculate annual depreciation
   - Skip if amount is zero (fully depreciated)
   - Create transaction dated December 31
3. Commit all transactions
4. Return summary

**Transaction Properties:**
```python
Transaction(
    user_id=property.user_id,
    property_id=property.id,
    type=TransactionType.EXPENSE,
    amount=amount,
    transaction_date=date(year, 12, 31),
    description=f"AfA {property.address} ({year})",
    expense_category=ExpenseCategory.DEPRECIATION_AFA,
    is_deductible=True,
    is_system_generated=True,
    import_source="annual_depreciation"
)
```

**Returns:**
```python
AnnualDepreciationResult(
    year=int,
    properties_processed=int,
    transactions_created=int,
    properties_skipped=int,
    total_amount=Decimal,
    transactions=List[Transaction],
    skipped_details=List[Dict]
)
```

**Skip Reasons:**
- `already_exists`: Depreciation transaction already exists for year
- `fully_depreciated`: Property is fully depreciated
- `error: <message>`: Error occurred during processing

**Example:**
```python
service = AnnualDepreciationService(db)

# Generate for specific user
result = service.generate_annual_depreciation(year=2025, user_id=123)

# Generate for all users (admin)
result = service.generate_annual_depreciation(year=2025)

# Result:
# AnnualDepreciationResult(
#   year=2025,
#   properties_processed=10,
#   transactions_created=8,
#   properties_skipped=2,
#   total_amount=Decimal("44800.00"),
#   ...
# )
```

---

## Integration Points

### 1. E1 Form Import Integration

**Service:** `E1FormImportService`  
**Location:** `backend/app/services/e1_form_import_service.py`

**Integration:**
When KZ 350 (rental income) is detected, trigger property linking suggestions.


**Code:**
```python
class E1FormImportService:
    def __init__(self, db: Session):
        self.db = db
        self.address_matcher = AddressMatcher(db)  # NEW
    
    def import_e1_data(self, data: E1FormData, user_id: int) -> Dict:
        # ... existing import logic ...
        
        # NEW: Property linking for rental income
        property_suggestions = []
        if data.kz_350 and data.kz_350 > 0:
            if data.vermietung_details:
                for detail in data.vermietung_details:
                    address = detail.get("address", "")
                    matches = self.address_matcher.match_address(address, user_id)
                    
                    property_suggestions.append({
                        "extracted_address": address,
                        "matches": [
                            {
                                "property_id": str(m.property.id),
                                "address": m.property.address,
                                "confidence": float(m.confidence),
                                "suggested_action": self._get_suggested_action(m.confidence)
                            }
                            for m in matches
                        ]
                    })
        
        return {
            # ... existing fields ...
            "property_linking_required": len(property_suggestions) > 0,
            "property_suggestions": property_suggestions
        }
    
    def _get_suggested_action(self, confidence: float) -> str:
        if confidence > 0.9:
            return "auto_link"  # High confidence
        elif confidence >= 0.7:
            return "suggest"  # Medium confidence
        else:
            return "create_new"  # Low confidence
```

### 2. Tax Calculation Engine Integration

**Service:** `TaxCalculationEngine`  
**Location:** `backend/app/services/tax_calculation_engine.py`

**Integration:**
Include property depreciation, rental income, and expenses in tax calculations.

**Code:**
```python
class TaxCalculationEngine:
    def calculate_tax(self, user_id: int, year: int) -> TaxCalculation:
        # ... existing code ...
        
        # NEW: Include property depreciation
        property_depreciation = self._calculate_property_depreciation(user_id, year)
        total_deductions += property_depreciation
        
        # NEW: Include rental income
        rental_income = self._calculate_rental_income(user_id, year)
        total_income += rental_income
        
        # NEW: Include property expenses
        property_expenses = self._calculate_property_expenses(user_id, year)
        total_deductions += property_expenses
        
        # ... rest of calculation ...
    
    def _calculate_property_depreciation(self, user_id: int, year: int) -> Decimal:
        """Sum all depreciation transactions for year"""
        total = self.db.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user_id,
            Transaction.expense_category == ExpenseCategory.DEPRECIATION_AFA,
            extract('year', Transaction.transaction_date) == year
        ).scalar()
        return total or Decimal("0")
```

---

## Testing Strategy

### Unit Tests

**Location:** `backend/tests/`

#### Test AfACalculator

```python
class TestAfACalculator:
    def test_determine_depreciation_rate_pre_1915(self):
        calculator = AfACalculator(db)
        rate = calculator.determine_depreciation_rate(1900)
        assert rate == Decimal("0.015")
    
    def test_calculate_annual_depreciation_full_year(self):
        property = create_test_property(
            building_value=Decimal("280000"),
            depreciation_rate=Decimal("0.02"),
            purchase_date=date(2020, 1, 1)
        )
        depreciation = calculator.calculate_annual_depreciation(property, 2021)
        assert depreciation == Decimal("5600.00")
```


### Property-Based Tests

**Location:** `backend/tests/test_afa_properties.py`

Uses Hypothesis library for property-based testing.

```python
from hypothesis import given, strategies as st
from decimal import Decimal

@given(
    building_value=st.decimals(min_value=10000, max_value=1000000, places=2),
    depreciation_rate=st.decimals(
        min_value=Decimal("0.015"), 
        max_value=Decimal("0.02"), 
        places=4
    )
)
def test_depreciation_accumulation_invariant(building_value, depreciation_rate):
    """Property 1: Accumulated depreciation never exceeds building value"""
    property = create_test_property(
        building_value=building_value,
        depreciation_rate=depreciation_rate
    )
    
    accumulated = Decimal("0")
    for year in range(50):  # Test 50 years
        annual = calculator.calculate_annual_depreciation(property, year)
        accumulated += annual
        
        # Invariant: accumulated <= building_value
        assert accumulated <= building_value
```

### Integration Tests

**Location:** `backend/tests/test_property_import_integration.py`

Tests complete workflows:

```python
def test_e1_import_with_property_linking(db, test_user):
    """Test E1 import → property linking → transaction creation"""
    # 1. Create property
    property = create_test_property(user_id=test_user.id)
    
    # 2. Import E1 with rental income
    e1_service = E1FormImportService(db)
    result = e1_service.import_e1_data(
        data=E1FormData(kz_350=12000, vermietung_details=[...]),
        user_id=test_user.id
    )
    
    # 3. Verify property suggestions
    assert result["property_linking_required"] is True
    assert len(result["property_suggestions"]) > 0
    
    # 4. Link transaction to property
    property_service = PropertyService(db)
    property_service.link_transaction(
        transaction_id=result["transaction_id"],
        property_id=property.id,
        user_id=test_user.id
    )
    
    # 5. Verify link
    transaction = db.query(Transaction).get(result["transaction_id"])
    assert transaction.property_id == property.id
```

---

## Performance Optimization

### Caching Strategy

**Cache property metrics** (accumulated depreciation, remaining value):

```python
from app.core.cache import cache_result

class PropertyService:
    @cache_result(ttl=3600)  # Cache for 1 hour
    def get_property_metrics(self, property_id: UUID) -> PropertyMetrics:
        """Calculate property metrics with caching"""
        # ... calculation logic ...
    
    def update_property(self, property_id: UUID, updates: PropertyUpdate):
        # ... update logic ...
        
        # Invalidate cache
        cache.delete(f"property_metrics:{property_id}")
```

**Cache invalidation triggers:**
- Property update
- Transaction creation/update/delete
- Depreciation backfill

### Query Optimization

**Avoid N+1 queries** when listing properties with metrics:

```python
def list_properties_with_metrics(self, user_id: int) -> List[PropertyWithMetrics]:
    """Optimized query using joins and aggregations"""
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
    
    results = query.all()
    
    return [
        PropertyWithMetrics(
            property=prop,
            accumulated_depreciation=acc_dep,
            remaining_value=prop.building_value - acc_dep
        )
        for prop, acc_dep in results
    ]
```

**Single query instead of N+1 queries!**


### Batch Processing

**Annual depreciation generation** processes properties in batches:

```python
def generate_annual_depreciation_batch(
    self, 
    year: int, 
    batch_size: int = 100
) -> AnnualDepreciationResult:
    """Process properties in batches to avoid memory issues"""
    offset = 0
    all_transactions = []
    
    while True:
        properties = self.db.query(Property).filter(
            Property.status == PropertyStatus.ACTIVE
        ).limit(batch_size).offset(offset).all()
        
        if not properties:
            break
        
        for property in properties:
            # Process property...
            pass
        
        offset += batch_size
        self.db.commit()  # Commit each batch
    
    return result
```

---

## Error Handling

### Service-Level Exceptions

All services use consistent error handling:

```python
from fastapi import HTTPException

class PropertyService:
    def get_property(self, property_id: UUID, user_id: int) -> Property:
        property = self.db.query(Property).filter(
            Property.id == property_id,
            Property.user_id == user_id
        ).first()
        
        if not property:
            raise HTTPException(
                status_code=404,
                detail="Property not found or access denied"
            )
        
        return property
```

### Transaction Rollback

All write operations use transaction rollback on error:

```python
def backfill_depreciation(self, property_id: UUID, user_id: int):
    try:
        # Create multiple transactions
        for year_data in historical_years:
            transaction = Transaction(...)
            self.db.add(transaction)
        
        self.db.commit()
        return result
        
    except Exception as e:
        self.db.rollback()
        logger.error(f"Backfill failed for property {property_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to backfill depreciation: {str(e)}"
        )
```

---

## Security Considerations

### Data Encryption

**Property addresses are encrypted at application layer:**

```python
from app.core.encryption import encrypt_field, decrypt_field

class Property(Base):
    _address = Column("address", String(1000), nullable=False)
    
    @hybrid_property
    def address(self):
        return decrypt_field(self._address)
    
    @address.setter
    def address(self, value):
        self._address = encrypt_field(value)
```

**Encryption method:** AES-256

### Ownership Validation

**All service methods validate ownership:**

```python
def _validate_ownership(self, property_id: UUID, user_id: int) -> Property:
    """Validate that property belongs to user"""
    property = self.db.query(Property).filter(
        Property.id == property_id,
        Property.user_id == user_id
    ).first()
    
    if not property:
        raise HTTPException(
            status_code=404,
            detail="Property not found or access denied"
        )
    
    return property
```

### Audit Logging

**All property operations are logged:**

```python
def _log_property_operation(
    self, 
    operation: str, 
    property_id: UUID, 
    user_id: int, 
    details: Dict[str, Any]
):
    """Log property operations for audit trail"""
    audit_log = AuditLog(
        user_id=user_id,
        operation=operation,
        entity_type="property",
        entity_id=str(property_id),
        details=details,
        timestamp=datetime.utcnow()
    )
    self.db.add(audit_log)
```

---

## Common Patterns

### Service Initialization

All services follow this pattern:

```python
class MyService:
    def __init__(self, db: Session):
        self.db = db
        # Initialize dependencies
        self.afa_calculator = AfACalculator(db)
```

### Dependency Injection

Services are injected via FastAPI dependencies:

```python
from fastapi import Depends
from app.db.session import get_db

@router.post("/properties")
def create_property(
    property_data: PropertyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = PropertyService(db)
    return service.create_property(current_user.id, property_data)
```

### Decimal Precision

All financial calculations use `Decimal` for precision:

```python
from decimal import Decimal

# GOOD
amount = Decimal("280000.00")
rate = Decimal("0.02")
depreciation = (amount * rate).quantize(Decimal("0.01"))

# BAD - floating point errors
amount = 280000.00
rate = 0.02
depreciation = round(amount * rate, 2)  # Can have precision issues
```

---

## Code Examples

### Complete Property Registration Flow

```python
from app.services.property_service import PropertyService
from app.schemas.property import PropertyCreate
from decimal import Decimal
from datetime import date

# Initialize service
service = PropertyService(db)

# Create property
property_data = PropertyCreate(
    street="Hauptstraße 123",
    city="Wien",
    postal_code="1010",
    purchase_date=date(2020, 6, 15),
    purchase_price=Decimal("350000.00"),
    construction_year=1985
)

property = service.create_property(user_id=123, property_data=property_data)

# Auto-calculated fields:
# - building_value: 280000.00 (80% of purchase_price)
# - depreciation_rate: 0.02 (2% for post-1915 building)
# - land_value: 70000.00 (purchase_price - building_value)

print(f"Property created: {property.id}")
print(f"Building value: {property.building_value}")
print(f"Depreciation rate: {property.depreciation_rate}")
```

### Historical Depreciation Backfill

```python
from app.services.historical_depreciation_service import HistoricalDepreciationService

service = HistoricalDepreciationService(db)

# Preview historical depreciation
preview = service.calculate_historical_depreciation(property.id)
for year_data in preview:
    print(f"{year_data.year}: {year_data.amount}")

# Execute backfill
result = service.backfill_depreciation(property.id, user_id=123)
print(f"Backfilled {result.years_backfilled} years")
print(f"Total amount: {result.total_amount}")
```

### Annual Depreciation Generation

```python
from app.services.annual_depreciation_service import AnnualDepreciationService

service = AnnualDepreciationService(db)

# Generate for current user
result = service.generate_annual_depreciation(year=2025, user_id=123)

print(f"Properties processed: {result.properties_processed}")
print(f"Transactions created: {result.transactions_created}")
print(f"Total depreciation: {result.total_amount}")

# Check skipped properties
for skip in result.skipped_details:
    print(f"Skipped {skip['property_id']}: {skip['reason']}")
```

---

## Troubleshooting

### Common Issues

#### Issue: Depreciation not calculating correctly

**Symptoms:** Annual depreciation is zero or incorrect amount

**Possible causes:**
1. Property already fully depreciated
2. Property sold before calculation year
3. Incorrect construction_year or depreciation_rate

**Debug:**
```python
# Check accumulated depreciation
accumulated = calculator.get_accumulated_depreciation(property.id)
print(f"Accumulated: {accumulated}")
print(f"Building value: {property.building_value}")
print(f"Remaining: {property.building_value - accumulated}")

# Check depreciation for specific year
depreciation = calculator.calculate_annual_depreciation(property, 2025)
print(f"2025 depreciation: {depreciation}")
```

#### Issue: Address matching not finding properties

**Symptoms:** E1 import doesn't suggest property links

**Possible causes:**
1. Address format mismatch
2. Property is archived/sold
3. Confidence score too low

**Debug:**
```python
matcher = AddressMatcher(db)
matches = matcher.match_address("Hauptstr. 123, 1010 Wien", user_id=123)

for match in matches:
    print(f"Property: {match.property.address}")
    print(f"Confidence: {match.confidence}")
    print(f"Components: {match.matched_components}")
```

#### Issue: Historical backfill creates duplicates

**Symptoms:** Multiple depreciation transactions for same year

**Possible causes:**
1. Backfill run multiple times
2. Manual transactions created before backfill

**Prevention:**
```python
# Service checks for existing transactions
def _depreciation_exists(self, property_id: UUID, year: int) -> bool:
    exists = self.db.query(Transaction).filter(
        Transaction.property_id == property_id,
        Transaction.expense_category == ExpenseCategory.DEPRECIATION_AFA,
        extract('year', Transaction.transaction_date) == year
    ).first()
    return exists is not None
```

---

## Best Practices

### 1. Always Use Services

**DON'T** access models directly in API endpoints:
```python
# BAD
@router.post("/properties")
def create_property(data: PropertyCreate, db: Session = Depends(get_db)):
    property = Property(**data.dict())
    db.add(property)
    db.commit()
    return property
```

**DO** use service layer:
```python
# GOOD
@router.post("/properties")
def create_property(data: PropertyCreate, db: Session = Depends(get_db)):
    service = PropertyService(db)
    return service.create_property(user_id, data)
```

### 2. Validate Ownership

**Always validate** that resources belong to the requesting user:
```python
def update_property(self, property_id: UUID, user_id: int, updates: PropertyUpdate):
    # Validate ownership first
    property = self._validate_ownership(property_id, user_id)
    
    # Then proceed with update
    for field, value in updates.dict(exclude_unset=True).items():
        setattr(property, field, value)
    
    self.db.commit()
    return property
```

### 3. Use Transactions

**Wrap multi-step operations** in transactions:
```python
def backfill_depreciation(self, property_id: UUID, user_id: int):
    try:
        # Multiple database operations
        for year_data in historical_years:
            transaction = Transaction(...)
            self.db.add(transaction)
        
        self.db.commit()  # Commit all or nothing
        
    except Exception as e:
        self.db.rollback()  # Rollback on error
        raise
```

### 4. Use Decimal for Money

**Always use Decimal** for financial calculations:
```python
from decimal import Decimal

# GOOD
amount = Decimal("280000.00")
rate = Decimal("0.02")

# BAD
amount = 280000.00  # Float has precision issues
```

### 5. Log Important Operations

**Log all significant operations** for debugging and audit:
```python
import logging

logger = logging.getLogger(__name__)

def backfill_depreciation(self, property_id: UUID, user_id: int):
    logger.info(f"Starting backfill for property {property_id}, user {user_id}")
    
    try:
        result = # ... backfill logic ...
        logger.info(f"Backfill completed: {result.years_backfilled} years")
        return result
        
    except Exception as e:
        logger.error(f"Backfill failed: {e}", exc_info=True)
        raise
```

---

## References

### Related Documentation

- **Database Schema:** `docs/developer/database-schema.md`
- **API Documentation:** `backend/app/api/v1/endpoints/properties.py`
- **Design Document:** `.kiro/specs/property-asset-management/design.md`
- **Requirements:** `.kiro/specs/property-asset-management/requirements.md`

### Source Code

- **PropertyService:** `backend/app/services/property_service.py`
- **AfACalculator:** `backend/app/services/afa_calculator.py`
- **HistoricalDepreciationService:** `backend/app/services/historical_depreciation_service.py`
- **AddressMatcher:** `backend/app/services/address_matcher.py`
- **AnnualDepreciationService:** `backend/app/services/annual_depreciation_service.py`

### Austrian Tax Law

- **§ 8 EStG:** Depreciation (Absetzung für Abnutzung)
- **§ 28 EStG:** Rental Income (Einkünfte aus Vermietung und Verpachtung)
- **BMF Guidelines:** Property valuation and depreciation

### Testing

- **Unit Tests:** `backend/tests/test_property_service.py`, `backend/tests/test_afa_calculator.py`
- **Property-Based Tests:** `backend/tests/test_afa_properties.py`
- **Integration Tests:** `backend/tests/test_property_import_integration.py`

---

**Document Version:** 1.0  
**Last Updated:** 2026-03-07  
**Maintained By:** Taxja Development Team
