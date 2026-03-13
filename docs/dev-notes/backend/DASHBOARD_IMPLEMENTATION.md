# Dashboard and Tax Simulation Implementation

## Overview

This document describes the implementation of Task 17: Dashboard and tax simulation features for the Taxja Austrian Tax Management System.

## Implemented Components

### 1. Dashboard Data Aggregation Service
**File**: `app/services/dashboard_service.py`

Provides comprehensive dashboard data including:
- Year-to-date income and expenses
- Estimated tax liability breakdown (income tax, VAT, SVS)
- Paid vs. remaining tax calculations
- VAT threshold distance monitoring
- Monthly income/expense trends with trend direction analysis

**Key Features**:
- Real-time tax calculations
- VAT small business threshold tracking (€55,000)
- Tolerance rule monitoring (€60,500)
- Monthly aggregation with profit trends
- Payment status tracking

**Validates**: Requirements 34.1, 34.2, 34.3, 34.7

### 2. What-If Tax Simulator
**File**: `app/services/what_if_simulator.py`

Simulates tax impact of financial changes:
- **Add Expense**: Calculate tax savings from new deductible expenses
- **Remove Expense**: Calculate tax impact of removing expenses
- **Income Change**: Simulate income increases/decreases

**Key Features**:
- Non-destructive simulations (no database modifications)
- Detailed tax breakdown comparisons
- Natural language explanations
- Effective tax rate calculations
- Marginal rate analysis

**Validates**: Requirement 34.4

### 3. Flat-Rate Tax Comparator
**File**: `app/services/flat_rate_tax_comparator.py`

Compares actual accounting vs. flat-rate tax system (Pauschalierung):
- **Actual Accounting**: Einnahmen-Ausgaben-Rechnung
- **6% Flat-Rate**: 6% deemed expenses
- **12% Flat-Rate**: 12% deemed expenses

**Key Features**:
- Eligibility checking (profit ≤ €33,000)
- Basic exemption calculation (15%, max €4,950)
- Side-by-side comparison
- Automatic recommendation of best method
- Detailed savings analysis

**Validates**: Requirements 31.1, 31.2, 31.3, 31.4, 31.5, 31.6

### 4. Savings Suggestion Generator
**File**: `app/services/savings_suggestion_service.py`

Generates personalized tax savings suggestions:
- Commuting allowance (Pendlerpauschale)
- Home office deduction (€300/year)
- Flat-rate tax comparison
- Family deductions (Kinderabsetzbetrag)
- SVS contribution deductibility

**Key Features**:
- Ranked by potential savings
- Actionable recommendations
- Eligibility checking
- Multi-language support
- Priority scoring

**Validates**: Requirement 34.5

### 5. Tax Calendar Service
**File**: `app/services/tax_calendar_service.py`

Manages Austrian tax deadlines:
- **Annual Deadlines**: Income tax (June 30), VAT annual (June 30)
- **Quarterly Deadlines**: VAT prepayments, SVS contributions
- **Employee Tax**: Arbeitnehmerveranlagung (June 30)

**Key Features**:
- Upcoming deadline tracking
- Urgency levels (urgent, soon, upcoming)
- Multi-language labels (German, English, Chinese)
- Quarter-based calculations
- Days-until countdown

**Validates**: Requirements 8.7, 34.6

### 6. Dashboard API Endpoints
**File**: `app/api/v1/endpoints/dashboard.py`

RESTful API endpoints:
- `GET /api/v1/dashboard` - Comprehensive dashboard data
- `GET /api/v1/dashboard/suggestions` - Tax savings suggestions
- `GET /api/v1/dashboard/calendar` - Upcoming tax deadlines
- `POST /api/v1/tax/simulate` - What-if tax simulations
- `GET /api/v1/tax/flat-rate-compare` - Flat-rate comparison

**Validates**: Requirements 34.1-34.7, 8.7, 31.1-31.6

## Property-Based Tests

### Property 24: What-If Simulation Consistency
**File**: `tests/test_what_if_simulation_properties.py`

Tests:
1. **Add Expense Consistency**: Deductible expenses reduce tax
2. **Income Change Monotonicity**: Income increases → tax increases
3. **Simulation Idempotence**: Same simulation → same results
4. **Database Isolation**: Simulations don't modify database

**Validates**: Requirement 34.4

### Property 22: Flat-Rate Tax Comparison
**File**: `tests/test_flat_rate_comparison_properties.py`

Tests:
1. **Deemed Expenses**: 6%/12% of turnover correctly calculated
2. **Basic Exemption Cap**: Max €4,950 enforced
3. **Profit Threshold**: €33,000 limit enforced
4. **Comparison Consistency**: Best method has lowest tax
5. **Employee Eligibility**: Employees not eligible

**Validates**: Requirements 31.1, 31.2, 31.3, 31.4

## API Usage Examples

### Get Dashboard Data
```bash
GET /api/v1/dashboard?tax_year=2026
Authorization: Bearer <token>
```

Response:
```json
{
  "tax_year": 2026,
  "year_to_date": {
    "total_income": 50000.00,
    "total_expenses": 15000.00,
    "deductible_expenses": 12000.00,
    "profit": 35000.00
  },
  "tax_summary": {
    "estimated_total_tax": 8500.00,
    "income_tax": 6000.00,
    "vat": 1500.00,
    "svs_contributions": 1000.00,
    "paid_tax": 4250.00,
    "remaining_tax": 4250.00,
    "payment_status": "payment_due"
  },
  "vat_threshold": {
    "current_turnover": 45000.00,
    "small_business_threshold": 55000.00,
    "distance_to_threshold": 10000.00,
    "percentage_of_threshold": 81.82,
    "status": "exempt"
  },
  "trends": {
    "monthly": [...],
    "trend_direction": "increasing"
  }
}
```

### Get Savings Suggestions
```bash
GET /api/v1/dashboard/suggestions?tax_year=2026&language=de
Authorization: Bearer <token>
```

Response:
```json
{
  "tax_year": 2026,
  "suggestions": [
    {
      "rank": 1,
      "title": "Claim Commuting Allowance (Großes Pendlerpauschale)",
      "description": "You commute 45km to work...",
      "potential_savings": 450.00,
      "category": "deductions",
      "priority": 1,
      "action_required": "Add commuting distance to profile"
    }
  ],
  "total_potential_savings": 1200.00
}
```

### Simulate Tax Scenario
```bash
POST /api/v1/tax/simulate
Authorization: Bearer <token>
Content-Type: application/json

{
  "type": "add_expense",
  "tax_year": 2026,
  "expense": {
    "amount": 1000.00,
    "date": "2026-06-15",
    "description": "New equipment",
    "expense_category": "EQUIPMENT",
    "is_deductible": true
  }
}
```

Response:
```json
{
  "scenario": "add_expense",
  "current_tax": 8500.00,
  "simulated_tax": 8200.00,
  "tax_difference": -300.00,
  "savings": 300.00,
  "explanation": "Adding this €1000.00 expense would save you €300.00 in taxes..."
}
```

### Compare Flat-Rate Tax
```bash
GET /api/v1/tax/flat-rate-compare?tax_year=2026
Authorization: Bearer <token>
```

Response:
```json
{
  "eligible": true,
  "actual_accounting": {
    "method": "Einnahmen-Ausgaben-Rechnung",
    "total_tax": 8500.00,
    "net_income": 26500.00
  },
  "flat_rate_6_percent": {
    "method": "Pauschalierung (6% Flat-Rate)",
    "total_tax": 8200.00,
    "net_income": 26800.00
  },
  "flat_rate_12_percent": {
    "method": "Pauschalierung (12% Flat-Rate)",
    "total_tax": 7800.00,
    "net_income": 27200.00
  },
  "recommendation": {
    "best_method": "flat_rate_12",
    "savings_vs_actual": 700.00,
    "explanation": "12% flat-rate system is recommended..."
  }
}
```

## Testing

Run property-based tests:
```bash
cd backend
pytest tests/test_what_if_simulation_properties.py -v
pytest tests/test_flat_rate_comparison_properties.py -v
```

Run all dashboard tests:
```bash
pytest tests/test_*simulation* tests/test_*flat_rate* -v
```

## Integration Notes

### Dependencies
The dashboard services depend on:
- `TaxCalculationEngine` - Core tax calculations
- `IncomeTaxCalculator` - Income tax computation
- `VATCalculator` - VAT calculations
- `SVSCalculator` - Social insurance
- `DeductionCalculator` - Deduction calculations

### Database Models
Uses existing models:
- `User` - User profile and settings
- `Transaction` - Income/expense transactions
- `TaxConfiguration` - Tax rates and rules

### Multi-Language Support
All services support German, English, and Chinese through:
- Localized field names
- Language parameter in API calls
- i18next integration ready

## Austrian Tax Law Compliance

### 2026 USP Tax Rates
- Correctly implements 7-bracket progressive tax system
- Applies €13,539 exemption amount
- Uses official 2026 tax rates

### Flat-Rate System (Pauschalierung)
- €33,000 profit threshold enforced
- 15% basic exemption (max €4,950)
- 6% and 12% deemed expense options
- Self-employed only eligibility

### VAT Thresholds
- €55,000 small business exemption
- €60,500 tolerance rule
- Automatic threshold monitoring

### Tax Deadlines
- June 30: Income tax, VAT annual, Arbeitnehmerveranlagung
- Quarterly: VAT prepayments (15th of month after quarter)
- Quarterly: SVS contributions (15th of month after quarter)

## Future Enhancements

Potential improvements:
1. Historical trend analysis (multi-year)
2. AI-powered savings recommendations
3. Automated deadline reminders via email
4. Export simulation results to PDF
5. Comparison with previous years
6. Industry benchmark comparisons

## Disclaimer

All calculations are for reference only and do not constitute official tax advice. Users should:
- Verify calculations with official USP calculator
- Consult Steuerberater for complex situations
- Submit final returns through FinanzOnline
- Keep original documents for audit purposes

---

**Implementation Status**: ✅ Complete
**Requirements Validated**: 8.7, 31.1-31.6, 34.1-34.7
**Property Tests**: 2 test suites, 9 properties validated
**API Endpoints**: 5 endpoints implemented
