# Property Asset Management - Code Examples

## Overview

This document provides practical, copy-paste ready code examples for common property management operations in Taxja. These examples demonstrate real-world usage patterns for developers implementing or extending property features.

## Table of Contents

1. [Property Registration](#property-registration)
2. [Depreciation Calculations](#depreciation-calculations)
3. [Transaction Linking](#transaction-linking)
4. [Historical Data Import](#historical-data-import)
5. [Property Reports](#property-reports)
6. [Frontend Integration](#frontend-integration)
7. [Testing Examples](#testing-examples)

---

## Property Registration

### Basic Property Creation

```python
from app.services.property_service import PropertyService
from app.schemas.property import PropertyCreate
from decimal import Decimal
from datetime import date

# Initialize service
service = PropertyService(db)

# Create property with minimal data (auto-calculations)
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
```

### Property with Custom Building Value

```python
# Specify custom building/land split
property_data = PropertyCreate(
    street="Mariahilfer Straße 45",
    city="Wien",
    postal_code="1060",
    purchase_date=date(2019, 3, 1),
    purchase_price=Decimal("500000.00"),
    building_value=Decimal("350000.00"),  # Custom 70/30 split
    construction_year=1900,  # Pre-1915 building
    depreciation_rate=Decimal("0.015")  # Will auto-set to 1.5%
)

property = service.create_property(user_id=123, property_data=property_data)
# land_value: 150000.00 (500000 - 350000)
# depreciation_rate: 0.015 (1.5% for pre-1915 building)
```

### Mixed-Use Property (Rental + Owner-Occupied)

```python
from app.models.property import PropertyType

# Property with 60% rental, 40% personal use
property_data = PropertyCreate(
    property_type=PropertyType.MIXED_USE,
    rental_percentage=Decimal("60.00"),
    street="Neubaugasse 78",
    city="Wien",
    postal_code="1070",
    purchase_date=date(2021, 1, 15),
    purchase_price=Decimal("400000.00"),
    construction_year=2010
)

property = service.create_property(user_id=123, property_data=property_data)
# Only 60% of building_value will be depreciated
# Depreciation = 400000 * 0.80 * 0.60 * 0.02 = 3840.00 per year
```

### Property with Purchase Costs

```python
# Track purchase costs for tax purposes
property_data = PropertyCreate(
    street="Landstraßer Hauptstraße 100",
    city="Wien",
    postal_code="1030",
    purchase_date=date(2022, 9, 1),
    purchase_price=Decimal("600000.00"),
    grunderwerbsteuer=Decimal("21000.00"),  # 3.5% property transfer tax
    notary_fees=Decimal("4500.00"),
    registry_fees=Decimal("1200.00"),
    construction_year=1995
)

property = service.create_property(user_id=123, property_data=property_data)
# Total purchase costs: 26700.00
# These costs are tracked for capital gains calculations
```

---

## Depreciation Calculations

### Calculate Annual Depreciation

```python
from app.services.afa_calculator import AfACalculator

calculator = AfACalculator(db)

# Full year depreciation
property = db.query(Property).filter(Property.id == property_id).first()
depreciation_2025 = calculator.calculate_annual_depreciation(property, 2025)
print(f"2025 Depreciation: €{depreciation_2025}")

# Example output: 2025 Depreciation: €5600.00
```

### Pro-Rated First Year Depreciation

```python
# Property purchased mid-year (July 1, 2024)
property = Property(
    building_value=Decimal("280000"),
    depreciation_rate=Decimal("0.02"),
    purchase_date=date(2024, 7, 1)
)

# Calculate 2024 depreciation (6 months)
depreciation_2024 = calculator.calculate_annual_depreciation(property, 2024)
# Result: 2800.00 (280000 * 0.02 * 6/12)

# Calculate 2025 depreciation (full year)
depreciation_2025 = calculator.calculate_annual_depreciation(property, 2025)
# Result: 5600.00 (280000 * 0.02)
```

### Check Accumulated Depreciation

```python
# Get total depreciation to date
accumulated = calculator.get_accumulated_depreciation(property.id)
remaining = property.building_value - accumulated

print(f"Building Value: €{property.building_value}")
print(f"Accumulated Depreciation: €{accumulated}")
print(f"Remaining Depreciable Value: €{remaining}")

# Example output:
# Building Value: €280000.00
# Accumulated Depreciation: €28000.00
# Remaining Depreciable Value: €252000.00
```

### Determine Depreciation Rate by Construction Year

```python
# Pre-1915 building
rate_old = calculator.determine_depreciation_rate(1900)
# Returns: Decimal("0.015") - 1.5%

# Post-1915 building
rate_new = calculator.determine_depreciation_rate(1985)
# Returns: Decimal("0.020") - 2.0%

# Unknown construction year
rate_default = calculator.determine_depreciation_rate(None)
# Returns: Decimal("0.020") - 2.0% (default)
```

---

## Transaction Linking

### Link Rental Income to Property

```python
from app.services.property_service import PropertyService

service = PropertyService(db)

# Link existing transaction to property
transaction_id = 456
property_id = "550e8400-e29b-41d4-a716-446655440000"

transaction = service.link_transaction(
    transaction_id=transaction_id,
    property_id=property_id,
    user_id=123
)

print(f"Transaction {transaction_id} linked to property {property_id}")
```

### Link Property Expense

```python
# Link maintenance expense to property
expense_transaction_id = 789
property_id = "550e8400-e29b-41d4-a716-446655440000"

transaction = service.link_transaction(
    transaction_id=expense_transaction_id,
    property_id=property_id,
    user_id=123
)
```

### Get All Transactions for a Property

```python
# Get all transactions (all years)
transactions = service.get_property_transactions(
    property_id=property_id,
    user_id=123
)

# Get transactions for specific year
transactions_2025 = service.get_property_transactions(
    property_id=property_id,
    user_id=123,
    year=2025
)

# Calculate totals
rental_income = sum(
    t.amount for t in transactions_2025 
    if t.type == TransactionType.INCOME
)
expenses = sum(
    t.amount for t in transactions_2025 
    if t.type == TransactionType.EXPENSE
)
net_income = rental_income - expenses

print(f"2025 Rental Income: €{rental_income}")
print(f"2025 Expenses: €{expenses}")
print(f"2025 Net Income: €{net_income}")
```

### Unlink Transaction from Property

```python
# Remove property link from transaction
transaction = db.query(Transaction).filter(
    Transaction.id == transaction_id,
    Transaction.user_id == user_id
).first()

if transaction:
    transaction.property_id = None
    db.commit()
    print(f"Transaction {transaction_id} unlinked from property")
```

---

## Historical Data Import

### Backfill Historical Depreciation

```python
from app.services.historical_depreciation_service import HistoricalDepreciationService

service = HistoricalDepreciationService(db)

# Step 1: Preview historical depreciation
preview = service.calculate_historical_depreciation(property_id)

print("Historical Depreciation Preview:")
total = Decimal("0")
for year_data in preview:
    print(f"  {year_data.year}: €{year_data.amount}")
    total += year_data.amount
print(f"Total: €{total}")

# Example output:
# Historical Depreciation Preview:
#   2020: €2800.00
#   2021: €5600.00
#   2022: €5600.00
#   2023: €5600.00
#   2024: €5600.00
#   2025: €5600.00
# Total: €30800.00

# Step 2: Execute backfill
result = service.backfill_depreciation(property_id, user_id=123)

print(f"\nBackfill Complete:")
print(f"  Years backfilled: {result.years_backfilled}")
print(f"  Total amount: €{result.total_amount}")
print(f"  Transactions created: {len(result.transactions)}")
```

### Import E1 with Property Linking

```python
from app.services.e1_form_import_service import E1FormImportService

service = E1FormImportService(db)

# Import E1 data
e1_data = E1FormData(
    kz_350=Decimal("12000.00"),  # Rental income
    vermietung_details=[
        {
            "address": "Hauptstraße 123, 1010 Wien",
            "rental_income": Decimal("12000.00")
        }
    ]
)

result = service.import_e1_data(e1_data, user_id=123)

# Check property linking suggestions
if result["property_linking_required"]:
    for suggestion in result["property_suggestions"]:
        print(f"Extracted Address: {suggestion['extracted_address']}")
        
        for match in suggestion["matches"]:
            print(f"  Match: {match['address']}")
            print(f"  Confidence: {match['confidence']:.2%}")
            print(f"  Action: {match['suggested_action']}")
            
            # Auto-link high confidence matches
            if match["suggested_action"] == "auto_link":
                service.link_imported_rental_income(
                    transaction_id=result["transaction_id"],
                    property_id=match["property_id"],
                    user_id=123
                )
                print(f"  ✓ Auto-linked")
```

### Address Matching

```python
from app.services.address_matcher import AddressMatcher

matcher = AddressMatcher(db)

# Find matching properties
address_string = "Hauptstr. 123, 1010 Wien"
matches = matcher.match_address(address_string, user_id=123)

for match in matches:
    print(f"Property: {match.property.address}")
    print(f"Confidence: {match.confidence:.2%}")
    print(f"Components matched:")
    for component, matched in match.matched_components.items():
        print(f"  {component}: {'✓' if matched else '✗'}")
    print()

# Example output:
# Property: Hauptstraße 123, 1010 Wien
# Confidence: 95.00%
# Components matched:
#   street: ✓
#   postal_code: ✓
#   city: ✓
```

---

## Property Reports

### Calculate Property Metrics

```python
from app.services.property_service import PropertyService

service = PropertyService(db)

# Get metrics for current year
metrics = service.calculate_property_metrics(property_id)

print(f"Property Metrics:")
print(f"  Accumulated Depreciation: €{metrics.accumulated_depreciation}")
print(f"  Remaining Depreciable Value: €{metrics.remaining_depreciable_value}")
print(f"  Rental Income (YTD): €{metrics.rental_income}")
print(f"  Expenses (YTD): €{metrics.expenses}")
print(f"  Net Income (YTD): €{metrics.net_income}")

# Get metrics for specific year
metrics_2024 = service.calculate_property_metrics(property_id, year=2024)
```

### Generate Annual Depreciation for All Properties

```python
from app.services.annual_depreciation_service import AnnualDepreciationService

service = AnnualDepreciationService(db)

# Generate for current user
result = service.generate_annual_depreciation(year=2025, user_id=123)

print(f"Annual Depreciation Generation:")
print(f"  Properties processed: {result.properties_processed}")
print(f"  Transactions created: {result.transactions_created}")
print(f"  Properties skipped: {result.properties_skipped}")
print(f"  Total depreciation: €{result.total_amount}")

# Check skipped properties
if result.skipped_details:
    print(f"\nSkipped Properties:")
    for skip in result.skipped_details:
        print(f"  {skip['property_id']}: {skip['reason']}")
```

### Portfolio Summary

```python
from sqlalchemy import func
from app.models.property import Property, PropertyStatus
from app.models.transaction import Transaction, ExpenseCategory

# Calculate portfolio totals
portfolio_query = db.query(
    func.count(Property.id).label('property_count'),
    func.sum(Property.building_value).label('total_building_value'),
    func.sum(Property.purchase_price).label('total_purchase_price')
).filter(
    Property.user_id == user_id,
    Property.status == PropertyStatus.ACTIVE
).first()

# Calculate total depreciation
total_depreciation = db.query(
    func.sum(Transaction.amount)
).filter(
    Transaction.user_id == user_id,
    Transaction.expense_category == ExpenseCategory.DEPRECIATION_AFA
).scalar() or Decimal("0")

# Calculate rental income (current year)
current_year = date.today().year
rental_income = db.query(
    func.sum(Transaction.amount)
).filter(
    Transaction.user_id == user_id,
    Transaction.property_id.isnot(None),
    Transaction.type == TransactionType.INCOME,
    extract('year', Transaction.transaction_date) == current_year
).scalar() or Decimal("0")

print(f"Portfolio Summary:")
print(f"  Active Properties: {portfolio_query.property_count}")
print(f"  Total Building Value: €{portfolio_query.total_building_value}")
print(f"  Total Purchase Price: €{portfolio_query.total_purchase_price}")
print(f"  Accumulated Depreciation: €{total_depreciation}")
print(f"  Rental Income ({current_year}): €{rental_income}")
```

---

## Frontend Integration

### Fetch Properties (React + Zustand)

```typescript
// Using Zustand store
import { usePropertyStore } from '@/stores/propertyStore';

function PropertiesPage() {
  const { properties, loading, error, fetchProperties } = usePropertyStore();
  
  useEffect(() => {
    fetchProperties(false); // Don't include archived
  }, [fetchProperties]);
  
  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error}</div>;
  
  return (
    <div>
      {properties.map(property => (
        <PropertyCard key={property.id} property={property} />
      ))}
    </div>
  );
}
```

### Create Property Form (React Hook Form + Zod)

```typescript
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { propertyCreateSchema } from '@/schemas/property';
import { usePropertyStore } from '@/stores/propertyStore';

function PropertyForm() {
  const { createProperty } = usePropertyStore();
  
  const form = useForm({
    resolver: zodResolver(propertyCreateSchema),
    defaultValues: {
      street: '',
      city: '',
      postal_code: '',
      purchase_date: '',
      purchase_price: 0,
      construction_year: undefined,
    }
  });
  
  const onSubmit = async (data: PropertyCreate) => {
    try {
      await createProperty(data);
      toast.success('Property created successfully');
    } catch (error) {
      toast.error('Failed to create property');
    }
  };
  
  return (
    <form onSubmit={form.handleSubmit(onSubmit)}>
      <input {...form.register('street')} placeholder="Street" />
      <input {...form.register('city')} placeholder="City" />
      <input {...form.register('postal_code')} placeholder="Postal Code" />
      <input {...form.register('purchase_date')} type="date" />
      <input {...form.register('purchase_price')} type="number" />
      <input {...form.register('construction_year')} type="number" />
      <button type="submit">Create Property</button>
    </form>
  );
}
```

### Display Property Metrics

```typescript
import { useEffect, useState } from 'react';
import { propertyService } from '@/services/propertyService';

function PropertyMetrics({ propertyId }: { propertyId: string }) {
  const [metrics, setMetrics] = useState(null);
  
  useEffect(() => {
    async function loadMetrics() {
      const data = await propertyService.getPropertyMetrics(propertyId);
      setMetrics(data);
    }
    loadMetrics();
  }, [propertyId]);
  
  if (!metrics) return <div>Loading metrics...</div>;
  
  return (
    <div className="metrics-grid">
      <MetricCard 
        label="Accumulated Depreciation" 
        value={metrics.accumulated_depreciation}
        format="currency"
      />
      <MetricCard 
        label="Remaining Value" 
        value={metrics.remaining_depreciable_value}
        format="currency"
      />
      <MetricCard 
        label="Rental Income (YTD)" 
        value={metrics.rental_income}
        format="currency"
      />
      <MetricCard 
        label="Net Income (YTD)" 
        value={metrics.net_income}
        format="currency"
      />
    </div>
  );
}
```

---

## Testing Examples

### Unit Test: AfA Calculator

```python
import pytest
from decimal import Decimal
from datetime import date
from app.services.afa_calculator import AfACalculator

def test_determine_depreciation_rate_pre_1915(db):
    calculator = AfACalculator(db)
    rate = calculator.determine_depreciation_rate(1900)
    assert rate == Decimal("0.015")

def test_determine_depreciation_rate_post_1915(db):
    calculator = AfACalculator(db)
    rate = calculator.determine_depreciation_rate(1985)
    assert rate == Decimal("0.020")

def test_calculate_annual_depreciation_full_year(db, test_property):
    calculator = AfACalculator(db)
    
    # Property: 280000 building value, 2% rate, owned full year
    depreciation = calculator.calculate_annual_depreciation(test_property, 2025)
    
    expected = Decimal("280000") * Decimal("0.02")
    assert depreciation == expected.quantize(Decimal("0.01"))
    assert depreciation == Decimal("5600.00")

def test_calculate_annual_depreciation_partial_year(db):
    calculator = AfACalculator(db)
    
    # Property purchased July 1 (6 months)
    property = create_test_property(
        building_value=Decimal("280000"),
        depreciation_rate=Decimal("0.02"),
        purchase_date=date(2025, 7, 1)
    )
    
    depreciation = calculator.calculate_annual_depreciation(property, 2025)
    
    # Expected: 280000 * 0.02 * 6/12 = 2800.00
    assert depreciation == Decimal("2800.00")
```

### Property-Based Test: Depreciation Invariant

```python
from hypothesis import given, strategies as st
from decimal import Decimal

@given(
    building_value=st.decimals(
        min_value=10000, 
        max_value=1000000, 
        places=2
    ),
    depreciation_rate=st.decimals(
        min_value=Decimal("0.015"), 
        max_value=Decimal("0.02"), 
        places=4
    )
)
def test_depreciation_accumulation_invariant(db, building_value, depreciation_rate):
    """Property 1: Accumulated depreciation never exceeds building value"""
    
    property = create_test_property(
        building_value=building_value,
        depreciation_rate=depreciation_rate,
        purchase_date=date(2000, 1, 1)
    )
    
    calculator = AfACalculator(db)
    accumulated = Decimal("0")
    
    # Test 50 years of depreciation
    for year in range(2000, 2050):
        annual = calculator.calculate_annual_depreciation(property, year)
        accumulated += annual
        
        # INVARIANT: accumulated <= building_value
        assert accumulated <= building_value, \
            f"Accumulated {accumulated} exceeds building value {building_value}"
```

### Integration Test: E1 Import with Property Linking

```python
def test_e1_import_with_property_linking(db, test_user, test_property):
    """Test complete E1 import → property linking workflow"""
    
    # 1. Create property
    property = create_test_property(
        user_id=test_user.id,
        address="Hauptstraße 123, 1010 Wien"
    )
    db.add(property)
    db.commit()
    
    # 2. Import E1 with rental income
    e1_service = E1FormImportService(db)
    e1_data = E1FormData(
        kz_350=Decimal("12000.00"),
        vermietung_details=[{
            "address": "Hauptstr. 123, 1010 Wien",
            "rental_income": Decimal("12000.00")
        }]
    )
    
    result = e1_service.import_e1_data(e1_data, user_id=test_user.id)
    
    # 3. Verify property suggestions
    assert result["property_linking_required"] is True
    assert len(result["property_suggestions"]) == 1
    
    suggestion = result["property_suggestions"][0]
    assert len(suggestion["matches"]) > 0
    
    match = suggestion["matches"][0]
    assert match["confidence"] > 0.9
    assert match["suggested_action"] == "auto_link"
    
    # 4. Link transaction to property
    property_service = PropertyService(db)
    transaction = property_service.link_transaction(
        transaction_id=result["transaction_id"],
        property_id=property.id,
        user_id=test_user.id
    )
    
    # 5. Verify link
    assert transaction.property_id == property.id
    assert transaction.amount == Decimal("12000.00")
```

### Frontend Component Test (Vitest + React Testing Library)

```typescript
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import PropertyForm from '@/components/properties/PropertyForm';

describe('PropertyForm', () => {
  it('should create property with auto-calculated building value', async () => {
    const onSubmit = vi.fn();
    
    render(<PropertyForm onSubmit={onSubmit} />);
    
    // Fill form
    fireEvent.change(screen.getByLabelText('Street'), {
      target: { value: 'Hauptstraße 123' }
    });
    fireEvent.change(screen.getByLabelText('Purchase Price'), {
      target: { value: '350000' }
    });
    
    // Submit
    fireEvent.click(screen.getByText('Create Property'));
    
    // Verify auto-calculation
    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          street: 'Hauptstraße 123',
          purchase_price: 350000,
          building_value: 280000, // 80% auto-calculated
        })
      );
    });
  });
});
```

---

## API Usage Examples

### cURL Examples

#### Create Property

```bash
curl -X POST http://localhost:8000/api/v1/properties \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "street": "Hauptstraße 123",
    "city": "Wien",
    "postal_code": "1010",
    "purchase_date": "2020-06-15",
    "purchase_price": 350000.00,
    "construction_year": 1985
  }'
```

#### Get Property List

```bash
curl -X GET "http://localhost:8000/api/v1/properties?include_archived=false" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

#### Backfill Historical Depreciation

```bash
# Preview
curl -X GET "http://localhost:8000/api/v1/properties/{property_id}/historical-depreciation" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Execute
curl -X POST "http://localhost:8000/api/v1/properties/{property_id}/backfill-depreciation" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

#### Generate Annual Depreciation

```bash
curl -X POST "http://localhost:8000/api/v1/properties/generate-annual-depreciation?year=2025" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## Common Patterns

### Pattern: Service Initialization

```python
from app.db.session import get_db
from app.services.property_service import PropertyService

def my_function(db: Session = Depends(get_db)):
    service = PropertyService(db)
    # Use service...
```

### Pattern: Error Handling

```python
from fastapi import HTTPException

try:
    property = service.get_property(property_id, user_id)
except HTTPException as e:
    if e.status_code == 404:
        # Property not found or access denied
        return {"error": "Property not found"}
    raise
```

### Pattern: Decimal Precision

```python
from decimal import Decimal

# Always use Decimal for money
amount = Decimal("280000.00")
rate = Decimal("0.02")
result = (amount * rate).quantize(Decimal("0.01"))
```

### Pattern: Date Handling

```python
from datetime import date

# Parse date from string
purchase_date = date.fromisoformat("2020-06-15")

# Current date
today = date.today()

# Date arithmetic
years_owned = today.year - purchase_date.year
```

---

## Troubleshooting

### Debug: Check Property Depreciation

```python
# Get property
property = db.query(Property).filter(Property.id == property_id).first()

print(f"Property: {property.address}")
print(f"Building Value: €{property.building_value}")
print(f"Depreciation Rate: {property.depreciation_rate}")
print(f"Purchase Date: {property.purchase_date}")
print(f"Status: {property.status}")

# Check accumulated depreciation
calculator = AfACalculator(db)
accumulated = calculator.get_accumulated_depreciation(property.id)
print(f"Accumulated Depreciation: €{accumulated}")

# Calculate current year depreciation
current_year = date.today().year
annual = calculator.calculate_annual_depreciation(property, current_year)
print(f"{current_year} Depreciation: €{annual}")

# Check remaining value
remaining = property.building_value - accumulated
print(f"Remaining Depreciable Value: €{remaining}")
```

### Debug: Address Matching

```python
from app.services.address_matcher import AddressMatcher

matcher = AddressMatcher(db)

# Test address matching
test_address = "Hauptstr. 123, 1010 Wien"
matches = matcher.match_address(test_address, user_id=123)

print(f"Testing address: {test_address}")
print(f"Found {len(matches)} matches:")

for match in matches:
    print(f"\n  Property: {match.property.address}")
    print(f"  Confidence: {match.confidence:.2%}")
    print(f"  Components:")
    for component, matched in match.matched_components.items():
        print(f"    {component}: {'✓' if matched else '✗'}")
```

---

## References

- **Service Layer Guide:** `docs/developer/service-layer-guide.md`
- **Database Schema:** `docs/developer/database-schema.md`
- **API Documentation:** FastAPI `/docs` endpoint
- **Testing Strategy:** `docs/developer/property-testing-strategy.md`

---

**Document Version:** 1.0  
**Last Updated:** 2026-03-07  
**Maintained By:** Taxja Development Team
