# Task B.3.2: Update Tax Report Generation - COMPLETE ✅

## Overview
Successfully updated the tax report generation to include property-related information with detailed breakdowns for rental income, property expenses, and depreciation.

## Changes Made

### 1. PDF Generator Enhancements (`backend/app/services/pdf_generator.py`)

#### Added Translation Keys
**German (de):**
- `rental_income_by_property`: "Mieteinnahmen nach Immobilie"
- `property_expenses`: "Immobilienausgaben"
- `property_depreciation`: "Immobilienabschreibung (AfA)"
- `loan_interest`: "Darlehenszinsen"
- `property_management_fees`: "Hausverwaltungsgebühren"
- `property_insurance`: "Gebäudeversicherung"
- `property_tax`: "Grundsteuer"
- `maintenance`: "Instandhaltung"
- `utilities`: "Nebenkosten"

**English (en):**
- `rental_income_by_property`: "Rental Income by Property"
- `property_expenses`: "Property Expenses"
- `property_depreciation`: "Property Depreciation (AfA)"
- `loan_interest`: "Loan Interest"
- `property_management_fees`: "Property Management Fees"
- `property_insurance`: "Property Insurance"
- `property_tax`: "Property Tax"
- `maintenance`: "Maintenance"
- `utilities`: "Utilities"

**Chinese (zh):**
- `rental_income_by_property`: "按物业分类的租金收入"
- `property_expenses`: "物业支出"
- `property_depreciation`: "物业折旧 (AfA)"
- `loan_interest`: "贷款利息"
- `property_management_fees`: "物业管理费"
- `property_insurance`: "物业保险"
- `property_tax`: "物业税"
- `maintenance`: "维护费用"
- `utilities`: "水电费"

#### Enhanced Income Summary Section
- Added property-by-property breakdown for rental income
- Displays individual property addresses with corresponding rental amounts
- Format: Indented list under main rental income line

**Example Output:**
```
Einkommen aus Vermietung                    € 18.000,00
  Mieteinnahmen nach Immobilie:
    • Hauptstraße 123, 1010 Wien            € 12.000,00
    • Mariahilfer Straße 45, 1060 Wien      €  6.000,00
```

#### Enhanced Expense Summary Section
- Added detailed property expense breakdown by category
- Displays each expense category with amount
- Includes property depreciation (AfA) as separate line item
- Categories automatically translated based on language

**Example Output:**
```
Abzugsfähige Ausgaben                       € 25.000,00
Nicht abzugsfähige Ausgaben                 €  2.000,00

Immobilienausgaben:
  • Darlehenszinsen                         €  5.000,00
  • Hausverwaltungsgebühren                 €  1.200,00
  • Gebäudeversicherung                     €    800,00
  • Grundsteuer                             €  1.500,00
  • Instandhaltung                          €  3.000,00
  • Nebenkosten                             €  2.500,00

Immobilienabschreibung (AfA)                €  5.600,00

Gesamtausgaben                              € 27.000,00
```

### 2. Data Structure Requirements

The `tax_data` parameter for `generate_tax_report()` now supports:

```python
{
    'income_summary': {
        'rental': 18000.00,
        'rental_by_property': {  # NEW: Property breakdown
            'Property Address 1': 12000.00,
            'Property Address 2': 6000.00
        },
        # ... other income types
    },
    'expense_summary': {
        'property_expenses': {  # NEW: Property expense breakdown
            'loan_interest': 5000.00,
            'property_management_fees': 1200.00,
            'property_insurance': 800.00,
            'property_tax': 1500.00,
            'maintenance': 3000.00,
            'utilities': 2500.00
        },
        'property_depreciation': 5600.00,  # NEW: Depreciation total
        # ... other expense fields
    },
    # ... other tax data
}
```

## Testing

### Test Coverage
Created comprehensive test: `backend/test_pdf_property_report.py`

**Test Results:**
```
✓ German PDF generated: 5734 bytes
✓ English PDF generated: 5587 bytes
✓ Chinese PDF generated: 5142 bytes

✓ All PDF generation tests passed!
✓ Property income breakdown included
✓ Property expense categories included
✓ Property depreciation included
```

### Test Scenarios
1. ✅ PDF generation with property rental income breakdown
2. ✅ PDF generation with property expense categories
3. ✅ PDF generation with property depreciation
4. ✅ Multi-language support (German, English, Chinese)
5. ✅ Proper formatting and indentation
6. ✅ Currency formatting for all amounts

## Integration Points

### Tax Calculation Engine
The tax calculation engine should populate the new fields:
- `income_summary.rental_by_property`: Query transactions grouped by property_id
- `expense_summary.property_expenses`: Query property expense transactions by category
- `expense_summary.property_depreciation`: Sum of DEPRECIATION_AFA transactions

### Example Integration Code
```python
# In TaxCalculationEngine or similar service
def _get_rental_income_by_property(self, user_id: int, year: int) -> Dict[str, Decimal]:
    """Get rental income grouped by property"""
    from app.models.property import Property
    from app.models.transaction import Transaction, IncomeCategory
    
    properties = self.db.query(Property).filter(
        Property.user_id == user_id,
        Property.status == PropertyStatus.ACTIVE
    ).all()
    
    rental_by_property = {}
    for prop in properties:
        total = self.db.query(func.sum(Transaction.amount)).filter(
            Transaction.property_id == prop.id,
            Transaction.income_category == IncomeCategory.RENTAL_INCOME,
            extract('year', Transaction.transaction_date) == year
        ).scalar() or Decimal("0")
        
        if total > 0:
            rental_by_property[prop.address] = float(total)
    
    return rental_by_property

def _get_property_expenses_by_category(self, user_id: int, year: int) -> Dict[str, Decimal]:
    """Get property expenses grouped by category"""
    from app.models.transaction import Transaction, ExpenseCategory
    
    property_categories = [
        ExpenseCategory.LOAN_INTEREST,
        ExpenseCategory.PROPERTY_MANAGEMENT_FEES,
        ExpenseCategory.PROPERTY_INSURANCE,
        ExpenseCategory.PROPERTY_TAX,
        ExpenseCategory.MAINTENANCE,
        ExpenseCategory.UTILITIES
    ]
    
    expenses = {}
    for category in property_categories:
        total = self.db.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user_id,
            Transaction.expense_category == category,
            Transaction.property_id.isnot(None),  # Only property-linked expenses
            extract('year', Transaction.transaction_date) == year
        ).scalar() or Decimal("0")
        
        if total > 0:
            expenses[category.value] = float(total)
    
    return expenses
```

## Benefits

### For Users
1. **Transparency**: Clear breakdown of rental income by property
2. **Detailed Tracking**: See exactly where property expenses are going
3. **Tax Compliance**: Proper categorization of property-related deductions
4. **Multi-Property Support**: Easy to see performance of each property

### For Tax Filing
1. **E1 Form Preparation**: Data ready for KZ 350 (rental income) and KZ 351 (rental expenses)
2. **Audit Trail**: Detailed documentation of all property-related amounts
3. **Depreciation Tracking**: Clear visibility of AfA deductions

## Next Steps

### Immediate
- ✅ Task B.3.2 complete
- ⏭️ Move to Task B.3.3: Add property section to E1 form preview

### Future Enhancements
- Add property-specific net income calculation in report
- Include depreciation schedule table showing year-by-year breakdown
- Add property comparison charts (if multiple properties)
- Export property-specific reports (per-property income statements)

## Files Modified
- `backend/app/services/pdf_generator.py` - Enhanced with property breakdowns

## Files Created
- `backend/test_pdf_property_report.py` - Test suite for property report generation
- `backend/TASK_B.3.2_TAX_REPORT_PROPERTY_INTEGRATION_COMPLETE.md` - This document

## Acceptance Criteria Status
- ✅ Include property depreciation in deductions
- ✅ Show rental income breakdown by property
- ✅ Display property expense categories
- ✅ Multi-language support (de, en, zh)
- ✅ Proper formatting and layout
- ✅ All tests passing

## Task Complete! 🎉
Tax report generation now includes comprehensive property-related information with detailed breakdowns for landlord users.
