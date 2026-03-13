# Property Asset Management Testing Strategy

## Overview

This document provides a comprehensive testing strategy for the property asset management feature in Taxja. It covers unit tests, property-based tests, integration tests, and end-to-end tests with practical examples.

## Testing Philosophy

The property management system requires rigorous testing because:
- **Financial accuracy**: Depreciation calculations must be precise for tax compliance
- **Austrian tax law compliance**: AfA rates and rules must be correctly implemented
- **Data integrity**: Property-transaction relationships must remain consistent
- **Multi-year calculations**: Historical depreciation backfill affects multiple years

## Test Types

### 1. Unit Tests
Test individual components in isolation with mocked dependencies.

### 2. Property-Based Tests
Use Hypothesis library to validate mathematical properties and invariants with generated test data.

### 3. Integration Tests
Test complete workflows across multiple services and database operations.

### 4. End-to-End Tests
Test full user workflows from API endpoints through to database persistence.

---

## Unit Testing Strategy

**Location:** `backend/tests/test_*.py`

**Framework:** pytest with fixtures

**Coverage Target:** >90% for service layer

### AfACalculator Unit Tests

**File:** `backend/tests/test_afa_calculator.py`


#### Test Categories

1. **Depreciation Rate Determination**
```python
def test_determine_depreciation_rate_pre_1915(calculator):
    """Buildings before 1915 use 1.5% rate"""
    rate = calculator.determine_depreciation_rate(1900)
    assert rate == Decimal("0.015")

def test_determine_depreciation_rate_post_1915(calculator):
    """Buildings 1915+ use 2.0% rate"""
    rate = calculator.determine_depreciation_rate(1985)
    assert rate == Decimal("0.020")

def test_determine_depreciation_rate_unknown(calculator):
    """Unknown construction year defaults to 2.0%"""
    rate = calculator.determine_depreciation_rate(None)
    assert rate == Decimal("0.020")
```

2. **Annual Depreciation Calculation**
```python
def test_full_year_depreciation(calculator, sample_property, mock_db):
    """Calculate depreciation for full year of ownership"""
    # Property: 280,000 EUR building value, 2% rate
    # Expected: 280,000 * 0.02 = 5,600 EUR
    
    mock_db.query.return_value.filter.return_value.scalar.return_value = Decimal("0")
    
    depreciation = calculator.calculate_annual_depreciation(sample_property, 2021)
    assert depreciation == Decimal("5600.00")

def test_partial_first_year_depreciation(calculator, sample_property, mock_db):
    """Pro-rated depreciation for mid-year purchase"""
    # Purchased June 15 (7 months owned in first year)
    # Expected: 5,600 * 7/12 = 3,266.67 EUR
    
    sample_property.purchase_date = date(2020, 6, 15)
    mock_db.query.return_value.filter.return_value.scalar.return_value = Decimal("0")
    
    depreciation = calculator.calculate_annual_depreciation(sample_property, 2020)
    assert depreciation == Decimal("3266.67")
```


3. **Building Value Limit**
```python
def test_stops_at_building_value_limit(calculator, sample_property, mock_db):
    """Depreciation stops when accumulated equals building value"""
    # Mock accumulated depreciation at building value
    mock_db.query.return_value.filter.return_value.scalar.return_value = sample_property.building_value
    
    depreciation = calculator.calculate_annual_depreciation(sample_property, 2025)
    assert depreciation == Decimal("0")

def test_respects_remaining_depreciable_value(calculator, sample_property, mock_db):
    """Final year depreciation limited to remaining value"""
    # Building value: 280,000, Accumulated: 278,000, Remaining: 2,000
    mock_db.query.return_value.filter.return_value.scalar.return_value = Decimal("278000.00")
    
    depreciation = calculator.calculate_annual_depreciation(sample_property, 2025)
    assert depreciation == Decimal("2000.00")  # Not 5,600
```

4. **Mixed-Use Properties**
```python
def test_mixed_use_property_depreciation(calculator, sample_property, mock_db):
    """Mixed-use property depreciates only rental percentage"""
    sample_property.property_type = PropertyType.MIXED_USE
    sample_property.rental_percentage = Decimal("50.00")  # 50% rental
    
    mock_db.query.return_value.filter.return_value.scalar.return_value = Decimal("0")
    
    # Expected: 280,000 * 0.50 * 0.02 = 2,800 EUR
    depreciation = calculator.calculate_annual_depreciation(sample_property, 2021)
    assert depreciation == Decimal("2800.00")

def test_owner_occupied_no_depreciation(calculator, sample_property, mock_db):
    """Owner-occupied properties are not depreciable"""
    sample_property.property_type = PropertyType.OWNER_OCCUPIED
    
    depreciation = calculator.calculate_annual_depreciation(sample_property, 2021)
    assert depreciation == Decimal("0")
```


### PropertyService Unit Tests

**File:** `backend/tests/test_property_service.py`

#### Test Categories

1. **Property Creation**
```python
def test_create_property_with_auto_calculations(db, test_user):
    """Test auto-calculation of building_value and depreciation_rate"""
    service = PropertyService(db)
    
    property_data = PropertyCreate(
        street="Hauptstraße 123",
        city="Wien",
        postal_code="1010",
        purchase_date=date(2020, 6, 15),
        purchase_price=Decimal("350000.00"),
        construction_year=1985
        # building_value not provided - should auto-calculate to 80%
        # depreciation_rate not provided - should auto-determine based on year
    )
    
    property = service.create_property(test_user.id, property_data)
    
    assert property.building_value == Decimal("280000.00")  # 80% of 350,000
    assert property.depreciation_rate == Decimal("0.02")    # 2% for post-1915
    assert property.land_value == Decimal("70000.00")       # Calculated field

def test_create_property_validation_errors(db, test_user):
    """Test validation of property data"""
    service = PropertyService(db)
    
    # Test: building_value > purchase_price
    with pytest.raises(ValueError, match="building_value cannot exceed purchase_price"):
        service.create_property(test_user.id, PropertyCreate(
            purchase_price=Decimal("100000"),
            building_value=Decimal("150000"),  # Invalid!
            # ... other fields
        ))
```


2. **Transaction Linking**
```python
def test_link_transaction_to_property(db, test_user, sample_property, sample_transaction):
    """Test linking transaction to property"""
    service = PropertyService(db)
    
    updated_transaction = service.link_transaction(
        transaction_id=sample_transaction.id,
        property_id=sample_property.id,
        user_id=test_user.id
    )
    
    assert updated_transaction.property_id == sample_property.id

def test_link_transaction_ownership_validation(db, test_user, other_user_property):
    """Test that users cannot link to properties they don't own"""
    service = PropertyService(db)
    
    with pytest.raises(PermissionError, match="Property does not belong to user"):
        service.link_transaction(
            transaction_id=123,
            property_id=other_user_property.id,
            user_id=test_user.id
        )
```

3. **Property Metrics Calculation**
```python
def test_calculate_property_metrics(db, test_user, sample_property):
    """Test calculation of property financial metrics"""
    service = PropertyService(db)
    
    # Create test transactions
    create_rental_income(db, sample_property.id, amount=12000)
    create_expense(db, sample_property.id, category="MAINTENANCE", amount=2000)
    create_depreciation(db, sample_property.id, amount=5600)
    
    metrics = service.calculate_property_metrics(sample_property.id, year=2025)
    
    assert metrics.rental_income == Decimal("12000.00")
    assert metrics.total_expenses == Decimal("7600.00")  # 2000 + 5600
    assert metrics.net_income == Decimal("4400.00")      # 12000 - 7600
```


---

## Property-Based Testing Strategy

**Location:** `backend/tests/test_afa_properties.py`

**Framework:** Hypothesis library

**Purpose:** Validate mathematical properties and invariants with automatically generated test data

### Why Property-Based Testing?

Property-based testing is ideal for financial calculations because:
- Tests correctness properties that must hold for ALL inputs
- Generates hundreds of test cases automatically
- Finds edge cases developers might miss
- Validates mathematical invariants

### Correctness Properties

These properties are derived from `requirements.md` Requirement 11.

#### Property 1: Depreciation Accumulation Invariant

**Invariant:** Total accumulated depreciation never exceeds building value

```python
from hypothesis import given, strategies as st, settings
from decimal import Decimal

@given(
    building_value=st.decimals(min_value=10000, max_value=1000000, places=2),
    depreciation_rate=st.decimals(
        min_value=Decimal("0.015"), 
        max_value=Decimal("0.02"), 
        places=4
    ),
    num_years=st.integers(min_value=1, max_value=100)
)
@settings(max_examples=100)
def test_property_1_depreciation_never_exceeds_building_value(
    building_value, depreciation_rate, num_years
):
    """
    Property 1: Depreciation Accumulation Invariant
    
    FOR ALL properties, at any point in time:
    sum(depreciation_transactions) <= building_value
    """
    property = create_test_property(
        building_value=building_value,
        depreciation_rate=depreciation_rate
    )
    
    accumulated = Decimal("0")
    for year in range(num_years):
        annual = calculator.calculate_annual_depreciation(property, year)
        accumulated += annual
        
        # INVARIANT: Must hold for every year
        assert accumulated <= building_value, \
            f"Accumulated {accumulated} exceeds building value {building_value}"
```


#### Property 2: Depreciation Rate Consistency

**Invariant:** Annual depreciation equals building_value × depreciation_rate (for full years)

```python
@given(
    building_value=st.decimals(min_value=10000, max_value=1000000, places=2),
    depreciation_rate=st.decimals(
        min_value=Decimal("0.015"),
        max_value=Decimal("0.02"),
        places=4
    )
)
@settings(max_examples=100)
def test_property_2_annual_depreciation_equals_building_value_times_rate(
    building_value, depreciation_rate
):
    """
    Property 2: Depreciation Rate Consistency
    
    FOR ALL properties with full year of ownership:
    annual_depreciation = building_value * depreciation_rate (within 0.01 tolerance)
    """
    property = create_test_property(
        building_value=building_value,
        depreciation_rate=depreciation_rate,
        purchase_date=date(2020, 1, 1)  # Full year ownership
    )
    
    expected = building_value * depreciation_rate
    actual = calculator.calculate_annual_depreciation(property, 2021)
    
    # Allow 0.01 EUR tolerance for rounding
    assert abs(actual - expected) <= Decimal("0.01"), \
        f"Expected {expected}, got {actual}"
```

#### Property 3: Pro-Rata Calculation Correctness

**Invariant:** First year depreciation = (building_value × rate × months_owned) / 12

```python
@given(
    building_value=st.decimals(min_value=10000, max_value=1000000, places=2),
    depreciation_rate=st.decimals(
        min_value=Decimal("0.015"),
        max_value=Decimal("0.02"),
        places=4
    ),
    purchase_month=st.integers(min_value=1, max_value=12)
)
@settings(max_examples=100)
def test_property_3_prorated_first_year_depreciation_formula(
    building_value, depreciation_rate, purchase_month
):
    """
    Property 3: Pro-Rata Calculation Correctness
    
    FOR ALL properties purchased in year Y:
    first_year_depreciation = (building_value * rate * months_owned) / 12
    """
    property = create_test_property(
        building_value=building_value,
        depreciation_rate=depreciation_rate,
        purchase_date=date(2020, purchase_month, 15)
    )
    
    months_owned = 13 - purchase_month  # Months from purchase to end of year
    expected = (building_value * depreciation_rate * months_owned) / 12
    actual = calculator.calculate_annual_depreciation(property, 2020)
    
    assert abs(actual - expected) <= Decimal("0.01")
```


#### Property 6: Depreciation Idempotence

**Invariant:** Calculating depreciation multiple times produces identical results

```python
@given(
    property=property_strategy(),
    year=st.integers(min_value=2020, max_value=2030)
)
@settings(max_examples=100)
def test_property_6_depreciation_calculation_is_idempotent(property, year):
    """
    Property 6: Depreciation Idempotence
    
    FOR ALL properties and years:
    Calculating depreciation multiple times produces identical results
    """
    result1 = calculator.calculate_annual_depreciation(property, year)
    result2 = calculator.calculate_annual_depreciation(property, year)
    result3 = calculator.calculate_annual_depreciation(property, year)
    
    assert result1 == result2 == result3, \
        "Depreciation calculation must be deterministic"
```

#### Property 8: Depreciation Rate Metamorphic Property

**Invariant:** Doubling rate doubles depreciation (proportional relationship)

```python
@given(
    building_value=st.decimals(min_value=10000, max_value=1000000, places=2),
    base_rate=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("0.05"), places=4),
    rate_multiplier=st.decimals(min_value=Decimal("1.5"), max_value=Decimal("3.0"), places=2)
)
@settings(max_examples=100)
def test_property_8_rate_multiplier_affects_depreciation_proportionally(
    building_value, base_rate, rate_multiplier
):
    """
    Property 8: Depreciation Rate Metamorphic Property
    
    FOR ALL properties:
    IF rate is multiplied by X, THEN depreciation is multiplied by X
    """
    property1 = create_test_property(
        building_value=building_value,
        depreciation_rate=base_rate
    )
    
    property2 = create_test_property(
        building_value=building_value,
        depreciation_rate=base_rate * rate_multiplier
    )
    
    depreciation1 = calculator.calculate_annual_depreciation(property1, 2021)
    depreciation2 = calculator.calculate_annual_depreciation(property2, 2021)
    
    expected_ratio = rate_multiplier
    actual_ratio = depreciation2 / depreciation1 if depreciation1 > 0 else Decimal("0")
    
    assert abs(actual_ratio - expected_ratio) <= Decimal("0.01")
```


### Hypothesis Strategies

Custom strategies for generating valid test data:

```python
from hypothesis import strategies as st
from decimal import Decimal
from datetime import date

def property_strategy():
    """Generate valid Property objects for testing"""
    return st.builds(
        Property,
        building_value=st.decimals(
            min_value=10000,
            max_value=1000000,
            places=2
        ),
        depreciation_rate=st.decimals(
            min_value=Decimal("0.015"),
            max_value=Decimal("0.02"),
            places=4
        ),
        purchase_date=st.dates(
            min_value=date(2010, 1, 1),
            max_value=date(2025, 12, 31)
        ),
        property_type=st.sampled_from([
            PropertyType.RENTAL,
            PropertyType.MIXED_USE
        ]),
        rental_percentage=st.decimals(
            min_value=Decimal("50.00"),
            max_value=Decimal("100.00"),
            places=2
        )
    )
```

---

## Integration Testing Strategy

**Location:** `backend/tests/test_property_import_integration.py`

**Purpose:** Test complete workflows across multiple services

### E1 Import with Property Linking

```python
def test_e1_import_with_property_linking(db, test_user):
    """
    Integration Test: E1 Import → Property Linking → Transaction Creation
    
    Workflow:
    1. Create existing property
    2. Import E1 with rental income (KZ 350)
    3. Verify property linking suggestions
    4. Link transaction to property
    5. Verify transaction is linked
    """
    # 1. Create property
    property_service = PropertyService(db)
    property = property_service.create_property(
        user_id=test_user.id,
        property_data=PropertyCreate(
            street="Hauptstraße 123",
            city="Wien",
            postal_code="1010",
            purchase_date=date(2020, 1, 1),
            purchase_price=Decimal("350000")
        )
    )
    
    # 2. Import E1 with rental income
    e1_service = E1FormImportService(db)
    result = e1_service.import_e1_data(
        data=E1FormData(
            kz_350=Decimal("12000.00"),  # Rental income
            vermietung_details=[{
                "address": "Hauptstraße 123, 1010 Wien",
                "income": 12000
            }]
        ),
        user_id=test_user.id
    )
    
    # 3. Verify property suggestions
    assert result["property_linking_required"] is True
    assert len(result["property_suggestions"]) > 0
    
    suggestion = result["property_suggestions"][0]
    assert suggestion["property_id"] == property.id
    assert suggestion["confidence"] > 0.9  # High confidence match
    
    # 4. Link transaction
    transaction_id = result["transactions"][0]["id"]
    property_service.link_transaction(
        transaction_id=transaction_id,
        property_id=property.id,
        user_id=test_user.id
    )
    
    # 5. Verify link
    transaction = db.query(Transaction).get(transaction_id)
    assert transaction.property_id == property.id
    assert transaction.amount == Decimal("12000.00")
    assert transaction.income_category == IncomeCategory.RENTAL_INCOME
```


### Historical Depreciation Backfill

```python
def test_historical_depreciation_backfill(db, test_user):
    """
    Integration Test: Property Creation → Historical Backfill → Verification
    
    Workflow:
    1. Create property purchased in 2020
    2. Calculate historical depreciation (2020-2025)
    3. Backfill depreciation transactions
    4. Verify all years have transactions
    5. Verify accumulated depreciation is correct
    """
    # 1. Create property from 2020
    property_service = PropertyService(db)
    property = property_service.create_property(
        user_id=test_user.id,
        property_data=PropertyCreate(
            street="Teststraße 1",
            city="Wien",
            postal_code="1010",
            purchase_date=date(2020, 6, 15),  # Mid-year purchase
            purchase_price=Decimal("350000"),
            building_value=Decimal("280000"),
            construction_year=1985
        )
    )
    
    # 2. Calculate historical depreciation
    historical_service = HistoricalDepreciationService(db)
    preview = historical_service.calculate_historical_depreciation(property.id)
    
    # Verify preview data
    assert len(preview) == 6  # 2020, 2021, 2022, 2023, 2024, 2025
    assert preview[0].year == 2020
    assert preview[0].amount == Decimal("3266.67")  # Pro-rated for 7 months
    
    # 3. Backfill transactions
    result = historical_service.backfill_depreciation(property.id, test_user.id)
    
    assert result.years_backfilled == 6
    assert result.total_amount > Decimal("0")
    
    # 4. Verify transactions exist for all years
    transactions = db.query(Transaction).filter(
        Transaction.property_id == property.id,
        Transaction.expense_category == ExpenseCategory.DEPRECIATION_AFA
    ).all()
    
    assert len(transactions) == 6
    
    years = [t.transaction_date.year for t in transactions]
    assert years == [2020, 2021, 2022, 2023, 2024, 2025]
    
    # 5. Verify accumulated depreciation
    calculator = AfACalculator(db)
    accumulated = calculator.get_accumulated_depreciation(property.id)
    
    expected = Decimal("3266.67") + (Decimal("5600.00") * 5)  # First year + 5 full years
    assert abs(accumulated - expected) <= Decimal("0.01")
```


### Address Matching

```python
def test_address_matcher_fuzzy_matching(db, test_user):
    """
    Integration Test: Address Matcher with Fuzzy Matching
    
    Tests that address matcher can find properties even with:
    - Abbreviations (Str. vs Straße)
    - Extra whitespace
    - Different formatting
    """
    # Create property with full address
    property_service = PropertyService(db)
    property = property_service.create_property(
        user_id=test_user.id,
        property_data=PropertyCreate(
            street="Hauptstraße 123",
            city="Wien",
            postal_code="1010",
            purchase_date=date(2020, 1, 1),
            purchase_price=Decimal("350000")
        )
    )
    
    # Test various address formats
    matcher = AddressMatcher(db)
    
    # Test 1: Exact match
    matches = matcher.match_address("Hauptstraße 123, 1010 Wien", test_user.id)
    assert len(matches) > 0
    assert matches[0].property.id == property.id
    assert matches[0].confidence > 0.9
    
    # Test 2: Abbreviated street
    matches = matcher.match_address("Hauptstr. 123, 1010 Wien", test_user.id)
    assert len(matches) > 0
    assert matches[0].property.id == property.id
    assert matches[0].confidence > 0.8
    
    # Test 3: Extra whitespace
    matches = matcher.match_address("Hauptstraße  123,  1010  Wien", test_user.id)
    assert len(matches) > 0
    assert matches[0].property.id == property.id
    
    # Test 4: Different order
    matches = matcher.match_address("1010 Wien, Hauptstraße 123", test_user.id)
    assert len(matches) > 0
    assert matches[0].property.id == property.id
```

---

## End-to-End Testing Strategy

**Location:** `backend/tests/test_property_e2e.py`

**Purpose:** Test complete user workflows from API to database

### Complete Property Lifecycle

```python
def test_complete_property_lifecycle_e2e(client, db, auth_headers):
    """
    E2E Test: Complete Property Lifecycle
    
    Workflow:
    1. Register property via API
    2. Create rental income transaction
    3. Link transaction to property
    4. Calculate property metrics
    5. Generate annual depreciation
    6. Archive property
    7. Verify all data preserved
    """
    # 1. Register property
    response = client.post(
        "/api/v1/properties",
        json={
            "street": "Teststraße 1",
            "city": "Wien",
            "postal_code": "1010",
            "purchase_date": "2020-01-01",
            "purchase_price": 350000.00,
            "construction_year": 1985
        },
        headers=auth_headers
    )
    assert response.status_code == 201
    property_data = response.json()
    property_id = property_data["id"]
    
    # Verify auto-calculations
    assert property_data["building_value"] == 280000.00
    assert property_data["depreciation_rate"] == 0.02
    
    # 2. Create rental income transaction
    response = client.post(
        "/api/v1/transactions",
        json={
            "type": "income",
            "amount": 12000.00,
            "transaction_date": "2025-12-31",
            "description": "Rental income 2025",
            "income_category": "rental_income"
        },
        headers=auth_headers
    )
    assert response.status_code == 201
    transaction_id = response.json()["id"]
    
    # 3. Link transaction to property
    response = client.post(
        f"/api/v1/properties/{property_id}/link-transaction",
        json={"transaction_id": transaction_id},
        headers=auth_headers
    )
    assert response.status_code == 200
    
    # 4. Get property with metrics
    response = client.get(
        f"/api/v1/properties/{property_id}",
        headers=auth_headers
    )
    assert response.status_code == 200
    property_data = response.json()
    
    # Verify transaction is linked
    assert len(property_data["transactions"]) > 0
    
    # 5. Generate annual depreciation
    response = client.post(
        "/api/v1/properties/generate-annual-depreciation",
        params={"year": 2025},
        headers=auth_headers
    )
    assert response.status_code == 200
    result = response.json()
    assert result["transactions_created"] > 0
    
    # 6. Archive property
    response = client.post(
        f"/api/v1/properties/{property_id}/archive",
        json={"sale_date": "2025-12-31"},
        headers=auth_headers
    )
    assert response.status_code == 200
    
    # 7. Verify archived property preserves data
    response = client.get(
        f"/api/v1/properties/{property_id}",
        headers=auth_headers
    )
    assert response.status_code == 200
    archived_property = response.json()
    
    assert archived_property["status"] == "sold"
    assert archived_property["sale_date"] == "2025-12-31"
    assert len(archived_property["transactions"]) > 0  # Transactions preserved
```


---

## Frontend Testing Strategy

**Location:** `frontend/src/components/properties/__tests__/`

**Framework:** Vitest + React Testing Library

### Component Testing

#### PropertyForm Component

```typescript
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { PropertyForm } from '../PropertyForm';
import { vi } from 'vitest';

describe('PropertyForm', () => {
  it('should auto-calculate building value as 80% of purchase price', async () => {
    const onSubmit = vi.fn();
    render(<PropertyForm onSubmit={onSubmit} />);
    
    // Enter purchase price
    const purchasePriceInput = screen.getByLabelText(/purchase price/i);
    fireEvent.change(purchasePriceInput, { target: { value: '350000' } });
    
    // Building value should auto-calculate
    await waitFor(() => {
      const buildingValueInput = screen.getByLabelText(/building value/i);
      expect(buildingValueInput).toHaveValue('280000');
    });
  });
  
  it('should auto-determine depreciation rate based on construction year', async () => {
    const onSubmit = vi.fn();
    render(<PropertyForm onSubmit={onSubmit} />);
    
    // Enter construction year before 1915
    const constructionYearInput = screen.getByLabelText(/construction year/i);
    fireEvent.change(constructionYearInput, { target: { value: '1900' } });
    
    // Depreciation rate should be 1.5%
    await waitFor(() => {
      const depreciationRateInput = screen.getByLabelText(/depreciation rate/i);
      expect(depreciationRateInput).toHaveValue('1.5');
    });
    
    // Change to post-1915
    fireEvent.change(constructionYearInput, { target: { value: '1985' } });
    
    // Depreciation rate should be 2.0%
    await waitFor(() => {
      const depreciationRateInput = screen.getByLabelText(/depreciation rate/i);
      expect(depreciationRateInput).toHaveValue('2.0');
    });
  });
  
  it('should validate building value does not exceed purchase price', async () => {
    const onSubmit = vi.fn();
    render(<PropertyForm onSubmit={onSubmit} />);
    
    const purchasePriceInput = screen.getByLabelText(/purchase price/i);
    const buildingValueInput = screen.getByLabelText(/building value/i);
    
    fireEvent.change(purchasePriceInput, { target: { value: '100000' } });
    fireEvent.change(buildingValueInput, { target: { value: '150000' } });
    
    const submitButton = screen.getByRole('button', { name: /save/i });
    fireEvent.click(submitButton);
    
    await waitFor(() => {
      expect(screen.getByText(/building value cannot exceed purchase price/i)).toBeInTheDocument();
    });
    
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
```


#### PropertyList Component

```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { PropertyList } from '../PropertyList';
import { vi } from 'vitest';

describe('PropertyList', () => {
  const mockProperties = [
    {
      id: '1',
      address: 'Hauptstraße 123, 1010 Wien',
      purchase_date: '2020-01-01',
      building_value: 280000,
      depreciation_rate: 0.02,
      accumulated_depreciation: 28000,
      status: 'active'
    },
    {
      id: '2',
      address: 'Teststraße 1, 1020 Wien',
      purchase_date: '2018-06-15',
      building_value: 350000,
      depreciation_rate: 0.015,
      accumulated_depreciation: 52500,
      status: 'active'
    }
  ];
  
  it('should display all properties', () => {
    render(<PropertyList properties={mockProperties} />);
    
    expect(screen.getByText(/Hauptstraße 123/i)).toBeInTheDocument();
    expect(screen.getByText(/Teststraße 1/i)).toBeInTheDocument();
  });
  
  it('should calculate and display remaining depreciable value', () => {
    render(<PropertyList properties={mockProperties} />);
    
    // Property 1: 280,000 - 28,000 = 252,000
    expect(screen.getByText(/252,000/)).toBeInTheDocument();
    
    // Property 2: 350,000 - 52,500 = 297,500
    expect(screen.getByText(/297,500/)).toBeInTheDocument();
  });
  
  it('should filter archived properties by default', () => {
    const propertiesWithArchived = [
      ...mockProperties,
      {
        id: '3',
        address: 'Archived Property',
        status: 'archived'
      }
    ];
    
    render(<PropertyList properties={propertiesWithArchived} />);
    
    expect(screen.queryByText(/Archived Property/i)).not.toBeInTheDocument();
  });
  
  it('should show archived properties when toggle is enabled', () => {
    const propertiesWithArchived = [
      ...mockProperties,
      {
        id: '3',
        address: 'Archived Property',
        status: 'archived'
      }
    ];
    
    render(<PropertyList properties={propertiesWithArchived} />);
    
    const toggleButton = screen.getByRole('checkbox', { name: /show archived/i });
    fireEvent.click(toggleButton);
    
    expect(screen.getByText(/Archived Property/i)).toBeInTheDocument();
  });
});
```

---

## Test Data Fixtures

### Backend Fixtures

**Location:** `backend/tests/conftest.py`

```python
import pytest
from decimal import Decimal
from datetime import date
from app.models import Property, Transaction, User
from app.models.property import PropertyType, PropertyStatus

@pytest.fixture
def sample_property(db, test_user):
    """Create a sample property for testing"""
    property = Property(
        user_id=test_user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        street="Hauptstraße 123",
        city="Wien",
        postal_code="1010",
        address="Hauptstraße 123, 1010 Wien",
        purchase_date=date(2020, 1, 1),
        purchase_price=Decimal("350000.00"),
        building_value=Decimal("280000.00"),
        construction_year=1985,
        depreciation_rate=Decimal("0.02"),
        status=PropertyStatus.ACTIVE
    )
    db.add(property)
    db.commit()
    db.refresh(property)
    return property

@pytest.fixture
def mixed_use_property(db, test_user):
    """Create a mixed-use property for testing"""
    property = Property(
        user_id=test_user.id,
        property_type=PropertyType.MIXED_USE,
        rental_percentage=Decimal("60.00"),  # 60% rental, 40% personal
        street="Teststraße 1",
        city="Wien",
        postal_code="1020",
        address="Teststraße 1, 1020 Wien",
        purchase_date=date(2020, 6, 15),
        purchase_price=Decimal("500000.00"),
        building_value=Decimal("400000.00"),
        construction_year=1990,
        depreciation_rate=Decimal("0.02"),
        status=PropertyStatus.ACTIVE
    )
    db.add(property)
    db.commit()
    db.refresh(property)
    return property

@pytest.fixture
def property_with_transactions(db, test_user, sample_property):
    """Create property with linked transactions"""
    # Rental income
    income = Transaction(
        user_id=test_user.id,
        property_id=sample_property.id,
        type=TransactionType.INCOME,
        amount=Decimal("12000.00"),
        transaction_date=date(2025, 12, 31),
        description="Rental income 2025",
        income_category=IncomeCategory.RENTAL_INCOME
    )
    
    # Maintenance expense
    expense = Transaction(
        user_id=test_user.id,
        property_id=sample_property.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("2000.00"),
        transaction_date=date(2025, 8, 15),
        description="Roof repair",
        expense_category=ExpenseCategory.MAINTENANCE
    )
    
    # Depreciation
    depreciation = Transaction(
        user_id=test_user.id,
        property_id=sample_property.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("5600.00"),
        transaction_date=date(2025, 12, 31),
        description="AfA 2025",
        expense_category=ExpenseCategory.DEPRECIATION_AFA,
        is_system_generated=True
    )
    
    db.add_all([income, expense, depreciation])
    db.commit()
    
    return sample_property
```


---

## Running Tests

### Backend Tests

```bash
cd backend

# Run all property-related tests
pytest tests/test_property*.py tests/test_afa*.py -v

# Run with coverage
pytest tests/test_property*.py tests/test_afa*.py --cov=app.services --cov-report=html

# Run only unit tests (fast)
pytest tests/test_afa_calculator.py tests/test_property_service.py -v

# Run only property-based tests
pytest tests/test_afa_properties.py -v

# Run only integration tests
pytest tests/test_property_import_integration.py -v

# Run specific test
pytest tests/test_afa_calculator.py::TestAfACalculator::test_full_year_depreciation -v

# Run with verbose Hypothesis output
pytest tests/test_afa_properties.py -v --hypothesis-show-statistics
```

### Frontend Tests

```bash
cd frontend

# Run all property component tests
npm run test -- src/components/properties

# Run with coverage
npm run test -- --coverage src/components/properties

# Run in watch mode
npm run test -- --watch src/components/properties

# Run specific test file
npm run test -- src/components/properties/__tests__/PropertyForm.test.tsx
```

### Full Test Suite

```bash
# From project root
make test

# Or manually
cd backend && pytest
cd frontend && npm run test
```

---

## Test Coverage Goals

### Backend Coverage Targets

| Component | Target | Current |
|-----------|--------|---------|
| AfACalculator | >95% | 100% |
| PropertyService | >90% | 98% |
| HistoricalDepreciationService | >90% | 95% |
| AddressMatcher | >85% | 92% |
| AnnualDepreciationService | >90% | 96% |
| Property API Endpoints | >85% | 88% |

### Frontend Coverage Targets

| Component | Target | Current |
|-----------|--------|---------|
| PropertyForm | >80% | 85% |
| PropertyList | >80% | 82% |
| PropertyDetail | >75% | 78% |
| PropertyPortfolioDashboard | >70% | 72% |

---

## Continuous Integration

### GitHub Actions Workflow

```yaml
name: Property Tests

on:
  push:
    paths:
      - 'backend/app/services/*property*.py'
      - 'backend/app/services/afa_calculator.py'
      - 'backend/tests/test_property*.py'
      - 'backend/tests/test_afa*.py'

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
      
      - name: Run property tests
        run: |
          cd backend
          pytest tests/test_property*.py tests/test_afa*.py -v --cov=app.services
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```


---

## Testing Best Practices

### 1. Test Isolation

Each test should be independent and not rely on other tests:

```python
# GOOD: Each test creates its own data
def test_create_property(db, test_user):
    property = create_test_property(db, test_user)
    assert property.id is not None

def test_update_property(db, test_user):
    property = create_test_property(db, test_user)  # Fresh data
    updated = update_property(property.id, {"street": "New Street"})
    assert updated.street == "New Street"

# BAD: Tests depend on each other
property_id = None

def test_create_property(db, test_user):
    global property_id
    property = create_test_property(db, test_user)
    property_id = property.id  # Shared state!

def test_update_property(db, test_user):
    global property_id
    updated = update_property(property_id, {"street": "New Street"})  # Depends on previous test
```

### 2. Use Fixtures for Common Setup

```python
# GOOD: Reusable fixtures
@pytest.fixture
def property_with_full_year_ownership(db, test_user):
    return create_test_property(
        db, test_user,
        purchase_date=date(2020, 1, 1)
    )

def test_full_year_depreciation(calculator, property_with_full_year_ownership):
    depreciation = calculator.calculate_annual_depreciation(
        property_with_full_year_ownership, 2021
    )
    assert depreciation == Decimal("5600.00")

# BAD: Duplicate setup in every test
def test_full_year_depreciation(db, test_user):
    property = Property(
        user_id=test_user.id,
        building_value=Decimal("280000"),
        depreciation_rate=Decimal("0.02"),
        purchase_date=date(2020, 1, 1),
        # ... 20 more fields
    )
    db.add(property)
    db.commit()
    # ... test logic
```

### 3. Test Edge Cases

Always test boundary conditions:

```python
def test_depreciation_edge_cases(calculator, db):
    # Zero building value
    property = create_test_property(building_value=Decimal("0"))
    assert calculator.calculate_annual_depreciation(property, 2021) == Decimal("0")
    
    # Maximum depreciation rate
    property = create_test_property(depreciation_rate=Decimal("0.10"))
    depreciation = calculator.calculate_annual_depreciation(property, 2021)
    assert depreciation <= property.building_value
    
    # Minimum depreciation rate
    property = create_test_property(depreciation_rate=Decimal("0.001"))
    depreciation = calculator.calculate_annual_depreciation(property, 2021)
    assert depreciation > Decimal("0")
    
    # Purchase on December 31 (1 month ownership)
    property = create_test_property(purchase_date=date(2020, 12, 31))
    depreciation = calculator.calculate_annual_depreciation(property, 2020)
    expected = property.building_value * property.depreciation_rate / 12
    assert abs(depreciation - expected) <= Decimal("0.01")
```


### 4. Mock External Dependencies

```python
from unittest.mock import Mock, patch

# GOOD: Mock database queries in unit tests
def test_calculate_annual_depreciation(calculator, sample_property):
    mock_db = Mock()
    mock_db.query.return_value.filter.return_value.scalar.return_value = Decimal("0")
    
    calculator.db = mock_db
    depreciation = calculator.calculate_annual_depreciation(sample_property, 2021)
    
    assert depreciation == Decimal("5600.00")
    mock_db.query.assert_called_once()

# GOOD: Mock external services
@patch('app.services.e1_form_import_service.AddressMatcher')
def test_e1_import_with_property_linking(mock_matcher, db, test_user):
    mock_matcher.return_value.match_address.return_value = [
        AddressMatch(property=sample_property, confidence=0.95)
    ]
    
    service = E1FormImportService(db)
    result = service.import_e1_data(e1_data, test_user.id)
    
    assert result["property_suggestions"][0]["confidence"] == 0.95
```

### 5. Use Descriptive Test Names

```python
# GOOD: Clear what is being tested
def test_mixed_use_property_depreciates_only_rental_percentage():
    pass

def test_depreciation_stops_when_accumulated_equals_building_value():
    pass

def test_property_creation_auto_calculates_building_value_as_80_percent():
    pass

# BAD: Unclear test names
def test_property_1():
    pass

def test_depreciation():
    pass

def test_calculation():
    pass
```

### 6. Test Error Conditions

```python
def test_property_service_error_handling(db, test_user):
    service = PropertyService(db)
    
    # Test: Invalid user ID
    with pytest.raises(ValueError, match="User not found"):
        service.create_property(user_id=99999, property_data=valid_data)
    
    # Test: Missing required fields
    with pytest.raises(ValueError, match="street is required"):
        service.create_property(user_id=test_user.id, property_data=invalid_data)
    
    # Test: Ownership validation
    other_user_property = create_property_for_other_user()
    with pytest.raises(PermissionError, match="Property does not belong to user"):
        service.update_property(
            property_id=other_user_property.id,
            user_id=test_user.id,
            updates={}
        )
```

---

## Debugging Failed Tests

### 1. Use pytest Verbose Mode

```bash
# Show detailed test output
pytest tests/test_afa_calculator.py -v

# Show print statements
pytest tests/test_afa_calculator.py -s

# Stop on first failure
pytest tests/test_afa_calculator.py -x

# Show local variables on failure
pytest tests/test_afa_calculator.py -l
```

### 2. Use pytest.set_trace() for Debugging

```python
def test_complex_calculation(calculator, property):
    result = calculator.calculate_annual_depreciation(property, 2021)
    
    import pytest; pytest.set_trace()  # Debugger breakpoint
    
    assert result == expected_value
```

### 3. Hypothesis Debugging

```python
from hypothesis import given, settings, example

@given(building_value=st.decimals(min_value=10000, max_value=1000000))
@settings(max_examples=100)
@example(building_value=Decimal("280000"))  # Test specific failing case
def test_depreciation_property(building_value):
    # Test logic
    pass
```


---

## Performance Testing

### Load Testing Property Operations

```python
import pytest
import time
from concurrent.futures import ThreadPoolExecutor

def test_property_creation_performance(db, test_user):
    """Test that property creation completes within acceptable time"""
    service = PropertyService(db)
    
    start_time = time.time()
    
    property = service.create_property(
        user_id=test_user.id,
        property_data=valid_property_data
    )
    
    elapsed_time = time.time() - start_time
    
    assert elapsed_time < 0.5  # Should complete in under 500ms
    assert property.id is not None

def test_depreciation_calculation_performance(calculator, sample_property):
    """Test depreciation calculation performance"""
    start_time = time.time()
    
    # Calculate 50 years of depreciation
    for year in range(2000, 2050):
        calculator.calculate_annual_depreciation(sample_property, year)
    
    elapsed_time = time.time() - start_time
    
    assert elapsed_time < 1.0  # 50 calculations in under 1 second

def test_concurrent_property_operations(db, test_users):
    """Test concurrent property operations"""
    service = PropertyService(db)
    
    def create_property_for_user(user):
        return service.create_property(user.id, valid_property_data)
    
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(create_property_for_user, test_users))
    
    elapsed_time = time.time() - start_time
    
    assert len(results) == len(test_users)
    assert elapsed_time < 5.0  # All operations complete in under 5 seconds
```

---

## Test Maintenance

### When to Update Tests

1. **When requirements change**: Update tests to reflect new business rules
2. **When bugs are found**: Add regression tests before fixing
3. **When refactoring**: Ensure tests still pass after code changes
4. **When adding features**: Add tests for new functionality

### Test Review Checklist

- [ ] All tests have descriptive names
- [ ] Tests are independent (no shared state)
- [ ] Edge cases are covered
- [ ] Error conditions are tested
- [ ] Fixtures are used for common setup
- [ ] Mocks are used appropriately
- [ ] Tests run quickly (unit tests < 1s each)
- [ ] Coverage meets targets (>90% for critical code)
- [ ] Property-based tests validate invariants
- [ ] Integration tests cover complete workflows

---

## Related Documentation

- [Service Layer Guide](./service-layer-guide.md) - Service architecture and patterns
- [Database Schema](./database-schema.md) - Property model structure
- [E1/Bescheid Integration](./e1-bescheid-property-integration.md) - Import workflows
- [Requirements Document](../../.kiro/specs/property-asset-management/requirements.md) - Business requirements
- [Design Document](../../.kiro/specs/property-asset-management/design.md) - Technical design

---

## Summary

This testing strategy ensures the property asset management feature is:

✅ **Mathematically correct** - Property-based tests validate invariants  
✅ **Austrian tax law compliant** - Tests verify AfA rates and rules  
✅ **Data integrity** - Integration tests verify referential integrity  
✅ **User-friendly** - Frontend tests ensure good UX  
✅ **Performant** - Load tests verify acceptable response times  
✅ **Maintainable** - Clear test structure and documentation  

**Key Testing Principles:**
1. Test at multiple levels (unit, integration, E2E)
2. Use property-based testing for mathematical correctness
3. Validate Austrian tax law compliance
4. Test edge cases and error conditions
5. Maintain high coverage (>90% for critical code)
6. Keep tests fast and independent
7. Document test strategies and patterns

For questions or issues with testing, refer to the test files in `backend/tests/` or contact the development team.
