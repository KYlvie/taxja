# Employee Tax Refund Module (Arbeitnehmerveranlagung)

## Overview

The Employee Tax Refund module calculates potential tax refunds for Austrian employees by comparing withheld tax (Lohnsteuer) from their Lohnzettel with actual tax liability after applying all available deductions.

**Requirements**: 37.1, 37.2, 37.3, 37.4, 37.5, 37.6, 37.7

## Key Features

- **Lohnzettel OCR Extraction**: Automatically extract gross income, withheld tax, and employer information from Lohnzettel documents
- **Refund Calculation**: Calculate actual tax liability with all deductions and compare with withheld tax
- **Deduction Application**: Automatically apply commuting allowance, home office deduction, family deductions, and social insurance
- **Refund Estimation**: Estimate refund potential for dashboard widget without requiring Lohnzettel
- **Transaction Aggregation**: Calculate refund from monthly payslip transactions

## Architecture

### Components

1. **EmployeeRefundCalculator** (`app/services/employee_refund_calculator.py`)
   - Main service for refund calculation
   - Integrates with IncomeTaxCalculator and DeductionCalculator
   - Generates human-readable explanations

2. **API Endpoints** (`app/api/v1/endpoints/tax.py`)
   - `POST /api/v1/tax/calculate-refund` - Calculate refund from Lohnzettel
   - `POST /api/v1/tax/calculate-refund-from-transactions` - Calculate from transactions
   - `GET /api/v1/tax/refund-estimate` - Estimate refund potential

3. **Property Tests** (`tests/test_employee_refund_properties.py`)
   - Property 23: Employee tax refund calculation correctness
   - Validates universal properties using Hypothesis

## Usage

### Basic Refund Calculation

```python
from app.services.employee_refund_calculator import (
    EmployeeRefundCalculator,
    LohnzettelData,
)
from app.models.user import User, FamilyInfo
from decimal import Decimal

# Create calculator
calculator = EmployeeRefundCalculator()

# Create Lohnzettel data
lohnzettel = LohnzettelData(
    gross_income=Decimal("45000.00"),
    withheld_tax=Decimal("9500.00"),
    withheld_svs=Decimal("6750.00"),
    employer_name="Example GmbH",
    tax_year=2026,
)

# Create user
user = User()
user.commuting_distance = 45
user.public_transport_available = True
user.family_info = FamilyInfo(num_children=2, is_single_parent=False)

# Calculate refund
result = calculator.calculate_refund(lohnzettel, user)

print(f"Refund: €{result.refund_amount:,.2f}")
print(f"Is Refund: {result.is_refund}")
print(result.explanation)
```

### API Usage

#### Calculate Refund from Lohnzettel

```bash
curl -X POST "http://localhost:8000/api/v1/tax/calculate-refund" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "lohnzettel": {
      "gross_income": 45000.00,
      "withheld_tax": 9500.00,
      "withheld_svs": 6750.00,
      "employer_name": "Example GmbH",
      "tax_year": 2026
    },
    "additional_deductions": {
      "donations": 500.00,
      "church_tax": 200.00
    }
  }'
```

Response:
```json
{
  "gross_income": 45000.00,
  "withheld_tax": 9500.00,
  "actual_tax_liability": 8234.56,
  "refund_amount": 1265.44,
  "is_refund": true,
  "deductions_applied": {
    "commuting_allowance": 1626.00,
    "home_office": 300.00,
    "family_deductions": 1401.60,
    "social_insurance": 6750.00,
    "donations": 500.00,
    "church_tax": 200.00
  },
  "explanation": "Good news! You are entitled to a tax refund of €1,265.44...",
  "breakdown": {
    "gross_income": 45000.00,
    "total_deductions": 10777.60,
    "taxable_income": 34222.40,
    "tax_calculation": {
      "total_tax": 8234.56,
      "effective_rate": 0.183,
      "breakdown": [...]
    }
  }
}
```

#### Estimate Refund Potential

```bash
curl -X GET "http://localhost:8000/api/v1/tax/refund-estimate?tax_year=2026&estimated_gross_income=45000" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Response:
```json
{
  "estimated_refund": 1200.00,
  "is_refund": true,
  "confidence": "low",
  "suggestions": [
    "Upload your Lohnzettel for accurate refund calculation"
  ],
  "message": "Upload your Lohnzettel for accurate refund calculation"
}
```

## Deductions Applied

The refund calculator automatically applies the following deductions:

### 1. Commuting Allowance (Pendlerpauschale)

- **Small Pendlerpauschale** (public transport available):
  - 20-40km: €58/month
  - 40-60km: €113/month
  - 60km+: €168/month

- **Large Pendlerpauschale** (no public transport):
  - 20-40km: €31/month
  - 40-60km: €123/month
  - 60km+: €214/month

- **Pendlereuro**: €6/km/year

### 2. Home Office Deduction

- Flat rate: €300/year

### 3. Family Deductions

- **Kinderabsetzbetrag**: €58.40/month per child
- **Single Parent Deduction**: €494/year

### 4. Social Insurance (Sonderausgaben)

- Withheld social insurance contributions are deductible

### 5. Additional Deductions (Optional)

- Charitable donations
- Church tax
- Other deductible expenses

## Calculation Logic

1. **Start with gross income** from Lohnzettel
2. **Apply all deductions** to calculate taxable income
3. **Calculate actual tax liability** using 2026 USP progressive tax rates
4. **Compare with withheld tax**:
   - If withheld > actual: **Refund** = withheld - actual
   - If withheld < actual: **Payment** = actual - withheld

## Property Tests

The module includes comprehensive property-based tests using Hypothesis:

### Property 23: Employee Tax Refund Calculation Correctness

1. **Refund Amount Equals Difference**: `refund_amount = |withheld_tax - actual_tax_liability|`
2. **Refund Flag Consistency**: `is_refund = True` when `withheld_tax > actual_tax_liability`
3. **Tax Never Exceeds Income**: `actual_tax_liability <= gross_income`
4. **Deductions Reduce Tax**: Tax with deductions ≤ tax without deductions
5. **Deterministic Calculation**: Same inputs always produce same results
6. **Progressive Tax Property**: Higher income never decreases absolute tax
7. **Breakdown Consistency**: Breakdown values match result values
8. **Explanation Always Provided**: Non-empty, meaningful explanation
9. **Additional Deductions Increase Refund**: More deductions = larger refund

## Dashboard Integration

The refund estimate endpoint is designed for dashboard widgets:

```python
# In dashboard service
refund_estimate = calculator.estimate_refund_potential(
    user, tax_year=2026, estimated_gross_income=Decimal("45000.00")
)

# Display on dashboard
if refund_estimate["is_refund"] and refund_estimate["estimated_refund"] > 0:
    show_widget(
        title="Potential Tax Refund",
        amount=refund_estimate["estimated_refund"],
        message="Upload your Lohnzettel to claim your refund!",
        action_url="/tax/refund"
    )
```

## Testing

Run property tests:
```bash
cd backend
pytest tests/test_employee_refund_properties.py -v
```

Run demo:
```bash
cd backend
python examples/refund_calculator_demo.py
```

## Important Notes

### Disclaimer

⚠️ **This is an estimate only. Final refund amounts may vary based on FinanzOnline calculation.**

The system provides:
- Automated calculation based on 2026 USP tax rates
- Application of common deductions
- Human-readable explanations

The system does NOT provide:
- Official tax advice
- Guaranteed refund amounts
- Filing services (use FinanzOnline)

### Deadline

Arbeitnehmerveranlagung must be filed by **June 30** of the following year.

### When to File

Employees should file if:
- They have deductible expenses (commuting, home office, etc.)
- They have multiple employers in one year
- They worked part of the year
- They have family deductions
- Their employer withheld too much tax

## Future Enhancements

- [ ] Support for multiple employers in one year
- [ ] Integration with FinanzOnline XML export
- [ ] Historical refund tracking
- [ ] Refund optimization suggestions
- [ ] Multi-year comparison
- [ ] AI-powered refund maximization tips

## References

- Requirements: 37.1, 37.2, 37.3, 37.4, 37.5, 37.6, 37.7
- USP 2026 Tax Tables
- Austrian Tax Law (Einkommensteuergesetz)
- FinanzOnline Documentation
