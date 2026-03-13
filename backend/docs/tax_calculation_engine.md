# TaxCalculationEngine Documentation

## Overview

The `TaxCalculationEngine` is a unified tax calculation system that integrates all tax calculators for the Austrian tax system. It provides a comprehensive solution for calculating total tax liability including income tax, VAT, and social insurance contributions.

## Architecture

The engine integrates four specialized calculators:

1. **IncomeTaxCalculator** - Progressive income tax based on 2026 USP rates
2. **VATCalculator** - VAT calculation with small business exemption
3. **SVSCalculator** - Social insurance contributions (GSVG and Neue Selbständige)
4. **DeductionCalculator** - Tax deductions (commuting, home office, family)

## Key Features

### 1. Unified Tax Calculation

Calculate all tax components in a single call:
- Income tax (progressive, 7 brackets)
- VAT (if applicable)
- SVS contributions (if applicable)
- All deductions automatically applied

### 2. Net Income Calculation

Automatically calculates net income after all taxes and contributions:
```
Net Income = Gross Income - (Income Tax + VAT + SVS)
```

### 3. Comprehensive Tax Breakdown

Provides detailed breakdown of:
- Each tax bracket calculation
- SVS contribution components
- VAT output/input calculation
- All deductions applied

### 4. Quarterly Prepayment Calculation

Calculates quarterly prepayment amounts for:
- Income tax (Einkommensteuer-Vorauszahlungen)
- SVS contributions

### 5. Loss Carryforward Support

Integrates loss carryforward (Verlustvortrag) into tax calculation:
- Applies previous year losses
- Tracks remaining loss balance
- Reduces current year tax liability

## Usage Examples

### Basic Employee Calculation

```python
from decimal import Decimal
from app.services.tax_calculation_engine import TaxCalculationEngine
from app.services.svs_calculator import UserType

engine = TaxCalculationEngine(tax_config)

result = engine.calculate_total_tax(
    gross_income=Decimal('50000.00'),
    tax_year=2026,
    user_type=UserType.EMPLOYEE
)

print(f"Total Tax: €{result.total_tax}")
print(f"Net Income: €{result.net_income}")
```

### GSVG with Deductions

```python
from app.services.deduction_calculator import FamilyInfo

family_info = FamilyInfo(num_children=2, is_single_parent=True)

result = engine.calculate_total_tax(
    gross_income=Decimal('60000.00'),
    tax_year=2026,
    user_type=UserType.GSVG,
    commuting_distance_km=50,
    public_transport_available=False,
    home_office_eligible=True,
    family_info=family_info
)
```

### With VAT Calculation

```python
from app.services.vat_calculator import Transaction

transactions = [
    Transaction(amount=Decimal('80000.00'), is_income=True),
    Transaction(amount=Decimal('25000.00'), is_income=False)
]

result = engine.calculate_total_tax(
    gross_income=Decimal('80000.00'),
    tax_year=2026,
    user_type=UserType.GSVG,
    transactions=transactions,
    gross_turnover=Decimal('80000.00')
)
```

### Generate API-Ready Breakdown

```python
breakdown = engine.generate_tax_breakdown(
    gross_income=Decimal('50000.00'),
    tax_year=2026,
    user_type=UserType.GSVG
)

# Returns dictionary with all tax components
# Suitable for JSON API responses
```

### Calculate Quarterly Prepayment

```python
prepayment = engine.calculate_quarterly_prepayment(
    gross_income=Decimal('60000.00'),
    tax_year=2026,
    user_type=UserType.GSVG
)

print(f"Quarterly Income Tax: €{prepayment['income_tax']}")
print(f"Quarterly SVS: €{prepayment['svs']}")
print(f"Total per Quarter: €{prepayment['total']}")
```

## API Reference

### TaxCalculationEngine

#### `__init__(tax_config: Dict)`

Initialize the engine with tax configuration.

**Parameters:**
- `tax_config`: Dictionary containing tax brackets and exemption amount

#### `calculate_total_tax(...) -> TaxBreakdown`

Calculate comprehensive tax liability.

**Parameters:**
- `gross_income`: Annual gross income (Decimal)
- `tax_year`: Tax year (int)
- `user_type`: User type (UserType enum)
- `transactions`: List of transactions for VAT (optional)
- `gross_turnover`: Annual gross turnover for VAT (optional)
- `property_type`: Property type for rental income (optional)
- `commuting_distance_km`: Commuting distance (optional)
- `public_transport_available`: Public transport availability (optional)
- `home_office_eligible`: Home office eligibility (bool)
- `family_info`: Family information (optional)
- `loss_carryforward_applied`: Loss carryforward amount (Decimal)
- `remaining_loss_balance`: Remaining loss balance (Decimal)

**Returns:**
- `TaxBreakdown` object with all tax components

#### `calculate_net_income(...) -> Decimal`

Convenience method to calculate only net income.

**Parameters:** Same as `calculate_total_tax`

**Returns:**
- Net income as Decimal

#### `generate_tax_breakdown(...) -> Dict`

Generate API-ready tax breakdown dictionary.

**Parameters:** Same as `calculate_total_tax`

**Returns:**
- Dictionary with structured tax breakdown

#### `calculate_quarterly_prepayment(...) -> Dict[str, Decimal]`

Calculate quarterly prepayment amounts.

**Parameters:**
- `gross_income`: Estimated annual income
- `tax_year`: Tax year
- `user_type`: User type
- `**kwargs`: Additional parameters

**Returns:**
- Dictionary with `income_tax`, `svs`, and `total` keys

## Data Structures

### TaxBreakdown

```python
@dataclass
class TaxBreakdown:
    income_tax: IncomeTaxResult
    vat: VATResult
    svs: SVSResult
    deductions: DeductionResult
    total_tax: Decimal
    net_income: Decimal
    gross_income: Decimal
    effective_tax_rate: Decimal
```

## Tax Calculation Flow

1. **Calculate Deductions**
   - Commuting allowance (Pendlerpauschale)
   - Home office deduction (€300/year)
   - Family deductions (Kinderabsetzbetrag)

2. **Calculate SVS Contributions**
   - Based on user type (GSVG or Neue Selbständige)
   - Apply minimum/maximum contribution bases
   - Mark as deductible (Sonderausgaben)

3. **Calculate Taxable Income**
   - Gross income - deductions - SVS contributions

4. **Calculate Income Tax**
   - Apply exemption amount (€13,539)
   - Apply loss carryforward (if any)
   - Calculate progressive tax across 7 brackets

5. **Calculate VAT** (if applicable)
   - Check small business exemption (€55,000)
   - Check tolerance rule (€60,500)
   - Calculate output VAT and input VAT

6. **Calculate Totals**
   - Total tax = Income tax + SVS + VAT
   - Net income = Gross income - Total tax
   - Effective tax rate = Total tax / Gross income

## Requirements Satisfied

This implementation satisfies the following requirements:

- **Requirement 3.5**: Calculate total tax (income tax + VAT + SVS)
- **Requirement 28.9**: Display net income (income - tax - social insurance)
- **Requirement 34.6**: Display net income on dashboard

## Testing

Comprehensive test suite with 21 test cases covering:
- Basic tax calculation for all user types
- Deductions (commuting, home office, family)
- VAT calculation (exempt, liable, tolerance rule)
- Loss carryforward
- Tax breakdown generation
- Quarterly prepayment calculation
- Edge cases (zero income, negative income, very high income)

Run tests:
```bash
pytest tests/test_tax_calculation_engine.py -v
```

## Examples

See `backend/examples/tax_calculation_example.py` for complete working examples:
1. Employee with commuting allowance
2. GSVG self-employed with family
3. GSVG with VAT liability
4. Neue Selbständige (freelancer)
5. Quarterly prepayment calculation

Run examples:
```bash
python examples/tax_calculation_example.py
```

## Integration Notes

### API Integration

The `generate_tax_breakdown()` method returns a dictionary suitable for JSON API responses:

```python
@app.post("/api/v1/tax/calculate")
async def calculate_tax(request: TaxCalculationRequest):
    engine = TaxCalculationEngine(tax_config)
    breakdown = engine.generate_tax_breakdown(
        gross_income=request.gross_income,
        tax_year=request.tax_year,
        user_type=request.user_type,
        # ... other parameters
    )
    return breakdown
```

### Dashboard Integration

For dashboard display:

```python
# Get net income for display
net_income = engine.calculate_net_income(
    gross_income=user_income,
    tax_year=current_year,
    user_type=user.user_type
)

# Get quarterly prepayment reminder
prepayment = engine.calculate_quarterly_prepayment(
    gross_income=user_income,
    tax_year=current_year,
    user_type=user.user_type
)
```

## Performance Considerations

- All calculations use `Decimal` for precision
- No database queries during calculation
- Suitable for real-time API responses
- Can be cached for repeated calculations with same parameters

## Future Enhancements

Potential future improvements:
1. Support for multiple income sources
2. Capital gains tax (Kapitalerträge) calculation
3. Flat-rate tax (Pauschalierung) comparison
4. Multi-year tax optimization
5. Tax-saving recommendations

## References

- Austrian tax law 2026
- USP 2026 tax rate tables
- SVS contribution rates 2026
- FinanzOnline requirements
