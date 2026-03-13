# Demo Data for Taxja

This directory contains scripts to generate realistic demo data for testing and demonstration purposes.

## Demo User Profiles

### 1. Employee (Arbeitnehmer)
**Email:** `employee@demo.taxja.at`  
**Password:** `Demo2026!`  
**Profile:**
- Name: Maria Müller
- Monthly salary: €3,500
- 2 children
- Commutes 35 km with public transport
- Has work equipment expenses
- Eligible for commuting allowance and child tax credits

**Transactions:**
- Monthly salary payments
- Public transport monthly pass
- Laptop for home office
- Professional literature

### 2. Self-Employed (Selbständiger)
**Email:** `selfemployed@demo.taxja.at`  
**Password:** `Demo2026!`  
**Profile:**
- Name: Thomas Weber
- Freelance IT consultant
- VAT registered
- Multiple clients
- Various business expenses

**Transactions:**
- Client invoices (€1,500-€4,500 each)
- Office supplies
- Software subscriptions (Adobe Creative Cloud)
- Marketing expenses (Google Ads)
- Professional services (tax advisor)
- Business travel
- Equipment purchases (MacBook Pro)

### 3. Landlord (Vermieter)
**Email:** `landlord@demo.taxja.at`  
**Password:** `Demo2026!`  
**Profile:**
- Name: Anna Schmidt
- Single parent with 1 child
- Rents out residential property
- Monthly rental income: €1,200

**Transactions:**
- Monthly rental income
- Property maintenance
- Property management fees
- Property insurance
- Mortgage interest payments

### 4. Mixed Income
**Email:** `mixed@demo.taxja.at`  
**Password:** `Demo2026!`  
**Profile:**
- Name: Peter Gruber
- Employee with rental income
- 3 children
- Commutes 45 km without public transport
- Eligible for large commuting allowance

## Usage

### Seed Demo Data

```bash
cd backend
python scripts/seed_demo.py
```

### Clear and Re-seed

```bash
python scripts/seed_demo.py --clear
```

### Using Make

```bash
make seed-demo
```

## What Gets Created

For each demo user:

1. **User Account**
   - Email and password
   - Personal information
   - Tax number
   - Family and commuting information

2. **Transactions**
   - 2 months of realistic transactions (Jan-Feb 2026)
   - Income transactions with proper categorization
   - Expense transactions with VAT information
   - Deductibility flags set correctly

3. **Documents**
   - Sample payslips (for employees)
   - Sample receipts
   - Sample invoices
   - OCR data pre-populated

## Tax Scenarios Covered

### Employee Scenario
- Standard employment income
- Commuting allowance calculation
- Work equipment deductions
- Professional literature deductions
- Child tax credits
- Potential tax refund (Arbeitnehmerveranlagung)

### Self-Employed Scenario
- Multiple income sources
- VAT calculations (20% standard rate)
- Business expense deductions
- Equipment depreciation
- SVS social insurance contributions
- Quarterly VAT prepayments

### Landlord Scenario
- Residential rental income (10% VAT)
- Property-related expense deductions
- Mortgage interest deductions
- Property depreciation
- Property management costs

### Mixed Income Scenario
- Employment income + rental income
- Large commuting allowance (no public transport)
- Multiple child tax credits
- Complex tax calculation with multiple income sources

## Testing Use Cases

Use these demo accounts to test:

1. **Transaction Management**
   - View and filter transactions
   - Edit transaction categories
   - Import bank statements

2. **Tax Calculations**
   - Income tax calculation
   - VAT calculation
   - SVS contributions
   - Tax credits and deductions

3. **Reports**
   - PDF tax report generation
   - FinanzOnline XML export
   - CSV data export
   - Audit checklist

4. **OCR**
   - Document upload
   - OCR result review
   - Transaction creation from documents

5. **AI Assistant**
   - Ask tax questions
   - Get document analysis
   - Receive optimization suggestions

6. **What-If Simulator**
   - Test expense additions
   - Compare flat-rate vs actual accounting
   - Calculate potential savings

## Customization

To create custom demo scenarios, edit `backend/app/db/demo_data.py`:

```python
# Add custom transactions
transactions.append(Transaction(
    user_id=user.id,
    type=TransactionType.EXPENSE,
    amount=Decimal("500.00"),
    date=datetime(2026, 3, 1),
    description="Custom expense",
    category=ExpenseCategory.CUSTOM,
    is_deductible=True
))
```

## Notes

- Demo data is clearly marked with `@demo.taxja.at` email addresses
- All amounts are in EUR
- Dates are set to 2026 (current tax year)
- VAT rates follow Austrian 2026 regulations
- Tax calculations use official USP 2026 rates

## Cleanup

To remove all demo data:

```bash
python scripts/seed_demo.py --clear
```

Or manually delete users with `@demo.taxja.at` email addresses from the database.

## Production Warning

⚠️ **Never run demo data scripts in production!**

Demo data is for development and testing only. Always use separate databases for development and production environments.
