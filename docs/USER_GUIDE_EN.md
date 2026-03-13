# Taxja User Guide (English)

## Welcome to Taxja

Taxja is your automated tax management platform for Austrian taxpayers. This guide will help you make the most of the system.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Managing Transactions](#managing-transactions)
3. [Property Management (for Landlords)](#property-management-for-landlords)
4. [Document Upload & OCR](#document-upload--ocr)
5. [Tax Calculations](#tax-calculations)
6. [Generating Reports](#generating-reports)
7. [AI Tax Assistant](#ai-tax-assistant)
8. [Frequently Asked Questions (FAQ)](#faq)

## Getting Started

### Registration

1. Visit https://taxja.at
2. Click "Register"
3. Enter your email and a secure password
4. Select your user type:
   - **Employee**: Salaried workers with payslips
   - **Landlord**: Individuals with rental income
   - **Self-Employed**: Freelancers, sole proprietors
   - **Mixed**: Multiple income sources

### Setting Up Your Profile

After registration, complete your profile:

1. **Personal Information**
   - Name, address
   - Tax number (Steuernummer)
   - VAT number (UID) if self-employed

2. **Family Information**
   - Number of children (for child tax credit)
   - Single parent status (for additional deductions)

3. **Commuting Information**
   - Distance to work (for commuting allowance)
   - Public transport availability

### Two-Factor Authentication (2FA)

For additional security, enable 2FA:

1. Go to Settings → Security
2. Click "Enable 2FA"
3. Scan the QR code with an authenticator app (e.g., Google Authenticator)
4. Enter the 6-digit code

## Managing Transactions

### Creating a Transaction Manually

1. Click "Transactions" → "New Transaction"
2. Select type:
   - **Income**: Salary, rental income, fees
   - **Expense**: Business expenses, deductible costs
3. Enter:
   - Amount (€)
   - Date
   - Description
   - Category (automatically suggested)
4. Click "Save"

### Importing Transactions

#### CSV Import from Bank Account

1. Export your bank statements as CSV
2. Click "Transactions" → "Import"
3. Select your bank from the list
4. Upload the CSV file
5. Review the preview
6. Confirm the import

**Supported Banks:**
- Raiffeisen
- Erste Bank
- Sparkasse
- Bank Austria
- BAWAG P.S.K.

### Automatic Categorization

Taxja automatically categorizes transactions:

- **Rule-based**: Known merchants (BILLA, SPAR, etc.)
- **AI-powered**: Learns from your corrections

**To correct categories:**
1. Click on the transaction
2. Select the correct category
3. Taxja learns from your correction

### Checking Deductibility

Taxja automatically shows if an expense is tax-deductible:

- ✅ **Deductible**: Considered in tax calculation
- ❌ **Not Deductible**: Personal expense

**Examples of deductible expenses:**

**Self-Employed:**
- Office supplies
- Work equipment
- Professional literature
- Training courses
- Business travel

**Landlords:**
- Maintenance
- Property management
- Insurance
- Property tax
- Loan interest

## Property Management (for Landlords)

If you're a landlord with rental properties, Taxja helps you track your properties, calculate depreciation (AfA - Absetzung für Abnutzung), and manage property-related income and expenses.

### Registering a Property

#### Step 1: Navigate to Properties

1. Click "Properties" in the main menu
2. Click "Add New Property"

#### Step 2: Enter Property Details

**Address Information:**
- Street address (e.g., "Hauptstraße 123")
- Postal code (e.g., "1010")
- City (e.g., "Wien")

**Purchase Information:**
- Purchase date (when you bought the property)
- Purchase price (total amount paid, including land)
- Building value (depreciable portion, excluding land)

**Tip:** If you don't know the exact building value, Taxja automatically calculates it as 80% of the purchase price (standard Austrian tax convention).

**Building Details:**
- Construction year (determines depreciation rate)
- Property type:
  - **Rental**: Property used exclusively for rental
  - **Owner-Occupied**: Your primary residence (no depreciation)
  - **Mixed-Use**: Partially rented, partially personal use

**For Mixed-Use Properties:**
- Rental percentage (e.g., 50% if you rent out half the property)

#### Step 3: Automatic Calculations

Taxja automatically calculates:

- **Land value**: Purchase price minus building value
- **Depreciation rate**: 
  - 1.5% per year for buildings constructed before 1915
  - 2.0% per year for buildings constructed 1915 or later
- **Annual depreciation**: Building value × depreciation rate

#### Step 4: Save Property

Click "Save Property" to complete registration.

### Understanding Depreciation (AfA)

**What is AfA?**

AfA (Absetzung für Abnutzung) is the annual depreciation of your rental property's building value. It's a tax-deductible expense that reflects the gradual wear and tear of the building.

**Key Points:**
- Only the building is depreciable (not the land)
- Depreciation is calculated annually
- It reduces your taxable rental income
- Depreciation stops when the building is fully depreciated

**Example:**

You bought a rental property for €350,000:
- Purchase price: €350,000
- Building value (80%): €280,000
- Land value (20%): €70,000
- Construction year: 1985 (→ 2% depreciation rate)
- Annual depreciation: €280,000 × 2% = €5,600

This €5,600 is automatically deducted from your rental income each year!

### Linking Transactions to Properties

Once you've registered a property, you can link rental income and expenses to it.

#### Linking Rental Income

1. Go to "Transactions"
2. Find your rental income transaction
3. Click "Edit"
4. Select the property from the dropdown
5. Click "Save"

**Tip:** When importing E1 forms or Bescheid documents, Taxja automatically suggests linking rental income to your registered properties.

#### Linking Property Expenses

Link these expense categories to your property:

- **Maintenance & Repairs**: Plumbing, painting, repairs
- **Property Management Fees**: If you use a property manager
- **Property Insurance**: Building insurance
- **Property Tax**: Grundsteuer
- **Loan Interest**: Mortgage interest (deductible!)
- **Utilities**: If you pay utilities for tenants
- **Depreciation (AfA)**: Automatically generated by Taxja

**To link an expense:**

1. Go to "Transactions"
2. Find the expense transaction
3. Click "Edit"
4. Select the property from the dropdown
5. Click "Save"

### Backfilling Historical Depreciation

If you purchased a property in a previous year and are registering it now, you need to backfill historical depreciation to ensure accurate tax calculations.

#### When to Backfill

You should backfill if:
- You bought the property before the current tax year
- You haven't claimed depreciation in previous years
- You want accurate accumulated depreciation totals

#### Step 1: Preview Historical Depreciation

1. Go to "Properties"
2. Select your property
3. Click "Historical Depreciation"
4. Click "Preview Backfill"

Taxja shows you:
- Year-by-year depreciation amounts
- Total amount to be backfilled
- Transaction dates (December 31 of each year)

**Example:**

Property purchased June 15, 2020, registered in 2026:

| Year | Depreciation | Notes |
|------|--------------|-------|
| 2020 | €2,800 | Pro-rated (7 months) |
| 2021 | €5,600 | Full year |
| 2022 | €5,600 | Full year |
| 2023 | €5,600 | Full year |
| 2024 | €5,600 | Full year |
| 2025 | €5,600 | Full year |
| **Total** | **€30,800** | |

#### Step 2: Confirm Backfill

1. Review the preview
2. Click "Confirm Backfill"
3. Taxja creates depreciation transactions for all years

**Important Notes:**
- Backfilled transactions are marked as "system-generated"
- They are dated December 31 of each year
- Taxja prevents duplicate backfills
- Depreciation stops when building value is fully depreciated

#### Step 3: Verify Transactions

1. Go to "Transactions"
2. Filter by property
3. Verify all depreciation transactions were created

### Viewing Property Details

#### Property Overview

1. Go to "Properties"
2. Click on a property to view details

You'll see:

**Property Information:**
- Address
- Purchase date and price
- Building value and land value
- Construction year
- Depreciation rate
- Property status (Active, Sold, Archived)

**Financial Metrics:**
- Accumulated depreciation (total to date)
- Remaining depreciable value
- Years remaining until fully depreciated
- Annual rental income (current year)
- Annual expenses (current year)
- Net rental income (income minus expenses)

**Linked Transactions:**
- All income and expenses linked to this property
- Grouped by category
- Filterable by year

### Generating Property Reports

Taxja can generate detailed reports for each property.

#### Income Statement Report

Shows rental income and expenses for a specific period.

1. Go to "Properties"
2. Select your property
3. Click "Reports" → "Income Statement"
4. Select date range (e.g., "2025")
5. Click "Generate"

**Report includes:**
- Rental income by month
- Expenses by category:
  - Maintenance & Repairs
  - Property Management
  - Insurance
  - Property Tax
  - Loan Interest
  - Utilities
  - Depreciation (AfA)
- Net rental income (profit/loss)

#### Depreciation Schedule Report

Shows depreciation over time.

1. Go to "Properties"
2. Select your property
3. Click "Reports" → "Depreciation Schedule"
4. Click "Generate"

**Report includes:**
- Annual depreciation by year
- Accumulated depreciation to date
- Remaining depreciable value
- Projected future depreciation
- Year when fully depreciated

#### Exporting Reports

Both reports can be exported as:
- **PDF**: For printing or sharing with tax advisor
- **CSV**: For Excel analysis

### Managing Multiple Properties

If you own multiple rental properties, Taxja provides portfolio-level insights.

#### Portfolio Dashboard

1. Go to "Properties" → "Portfolio Overview"

You'll see:
- Total number of properties
- Total building value across all properties
- Total annual depreciation
- Total rental income (all properties)
- Total expenses (all properties)
- Net rental income (portfolio-wide)

#### Comparing Properties

1. Go to "Properties" → "Compare"
2. Select properties to compare
3. View side-by-side comparison:
   - Rental income
   - Expenses
   - Net income
   - Rental yield (income / building value)

This helps you identify your best and worst performing properties!

### Archiving or Deleting Properties

#### Archiving a Sold Property

When you sell a property:

1. Go to "Properties"
2. Select the property
3. Click "Archive"
4. Enter the sale date
5. Click "Confirm"

**What happens:**
- Property status changes to "Sold"
- Depreciation stops after the sale date
- Property is hidden from active list
- All historical data is preserved
- You can still view archived properties

#### Deleting a Property

You can only delete a property if it has no linked transactions.

1. Go to "Properties"
2. Select the property
3. Click "Delete"
4. Confirm deletion

**Warning:** This permanently deletes the property. If you have linked transactions, you must unlink them first or archive the property instead.

### Tips for Property Management

**1. Register properties as soon as possible**
- Don't wait until tax filing time
- Backfilling is possible but easier to track in real-time

**2. Link all property-related transactions**
- Helps you track profitability per property
- Ensures accurate tax calculations
- Makes report generation easier

**3. Keep purchase contracts (Kaufvertrag)**
- Upload to Taxja for reference
- OCR can extract property details automatically
- Useful for tax audits

**4. Track mixed-use properties carefully**
- Set the correct rental percentage
- Only the rental portion is depreciable
- Expenses must be allocated proportionally

**5. Review depreciation annually**
- Check that annual depreciation was generated
- Verify amounts are correct
- Ensure no duplicates

**6. Use property reports for tax filing**
- Generate income statement for E1 form
- Include depreciation in expense totals
- Export as PDF for tax advisor

### Common Questions

**Q: Can I deduct the purchase price of my rental property?**
A: No, you cannot deduct the full purchase price in one year. Instead, you depreciate the building value over many years (AfA). Land value is not depreciable.

**Q: What if I don't know the construction year?**
A: Taxja uses the default 2% depreciation rate. You can check the land registry (Grundbuch) or property deed for the construction year.

**Q: Can I depreciate my own home (owner-occupied)?**
A: No. Only rental properties are depreciable. Owner-occupied properties do not qualify for AfA.

**Q: What about mixed-use properties?**
A: If you rent out part of your property (e.g., one apartment in a two-family house), you can depreciate the rental portion. Set the rental percentage when registering the property.

**Q: How long does depreciation last?**
A: With a 2% rate, it takes 50 years to fully depreciate. With 1.5%, it takes about 67 years. Depreciation stops when accumulated depreciation equals building value.

**Q: Can I change the depreciation rate?**
A: The rate is determined by construction year per Austrian tax law. You can manually override it, but this should only be done with tax advisor guidance.

**Q: What happens if I sell a property mid-year?**
A: Depreciation is pro-rated for the months you owned the property. Enter the sale date when archiving, and Taxja calculates the partial-year depreciation.

**Q: Are property purchase costs deductible?**
A: Purchase costs (Grunderwerbsteuer, notary fees, registry fees) are capitalized into the purchase price, not immediately deductible. They increase your cost basis for future capital gains calculations.

## Document Upload & OCR

### Uploading Documents

1. Click "Documents" → "Upload"
2. Select files:
   - Take photo with smartphone
   - Choose files from computer
   - Drag & drop
3. Supported formats: JPG, PNG, PDF
4. Maximum size: 10 MB per file

### OCR Recognition

Taxja automatically recognizes:

**Payslips (Lohnzettel):**
- Gross salary
- Net salary
- Withheld tax
- Social insurance

**Receipts:**
- Date
- Amount
- Merchant
- Line items
- VAT amounts

**Invoices:**
- Invoice number
- Date
- Amount
- Supplier
- VAT amount

### Reviewing OCR Results

1. After upload, you'll see the recognized data
2. Fields with low confidence are highlighted
3. Correct values if needed
4. Click "Confirm"
5. Taxja automatically creates a transaction

**Tips for better recognition:**
- Good lighting
- Flat document (not crumpled)
- Entire document in frame
- Sufficient resolution

### Receipt Analysis for Self-Employed

For supermarket receipts, Taxja asks:

> "Is this a business purchase?"

Taxja analyzes line items:
- ✅ Office supplies, cleaning products → deductible
- ❌ Groceries, personal items → not deductible

You can adjust the selection.

## Tax Calculations

### Tax Overview

The dashboard shows:

- **Annual Income**: Sum of all income
- **Deductible Expenses**: Sum of all business expenses
- **Estimated Tax**: Expected tax liability
- **Already Paid**: Withheld tax, prepayments
- **Remaining**: Balance due

### Income Tax

Taxja calculates using **official USP 2026 rates**:

| Income | Tax Rate |
|--------|----------|
| €0 – €13,539 | 0% |
| €13,539 – €21,992 | 20% |
| €21,992 – €36,458 | 30% |
| €36,458 – €70,365 | 40% |
| €70,365 – €104,859 | 48% |
| €104,859 – €1,000,000 | 50% |
| over €1,000,000 | 55% |

### Value Added Tax (VAT)

**Small Business Exemption:**
- Turnover ≤ €55,000: VAT-exempt
- Turnover €55,000 – €60,500: Tolerance rule (still exempt, but automatically liable next year)
- Turnover > €60,500: VAT-liable

**VAT Rates:**
- Standard: 20%
- Residential rental: 10% (or exemption optional)

### Social Insurance (SVS)

For self-employed, Taxja automatically calculates:

- Pension insurance: 18.5%
- Health insurance: 6.8%
- Accident insurance: €12.95/month
- Supplementary pension: 1.53%

**Minimum contribution base:** €551.10/month
**Maximum contribution base:** €8,085/month

SVS contributions are deductible as special expenses!

### Tax Credits

**Commuting Allowance (Pendlerpauschale):**
- 20-40 km: €58-€306/month
- Plus commuter euro: €6/km/year

**Home Office Allowance:**
- €300/year (automatic)

**Child Tax Credit:**
- €58.40/month per child

**Single Parent Credit:**
- €494/year

### What-If Simulator

Test tax scenarios:

1. Go to "Taxes" → "Simulator"
2. Add hypothetical expenses
3. See immediate tax savings
4. Example: "How much do I save if I buy a new laptop?"

### Flat-Rate vs. Actual Accounting

For small businesses, Taxja shows both options:

**Flat-Rate (Pauschalierung):**
- 6% or 12% flat expense deduction
- Simpler, less effort
- No receipt requirement

**Actual Accounting:**
- Actual expenses deductible
- More effort, receipt requirement
- Often higher tax savings

Taxja recommends the cheaper option!

## Generating Reports

### Creating Tax Returns

1. Go to "Reports" → "Create New"
2. Select tax year
3. Select format:
   - **PDF**: Comprehensive report
   - **XML**: For FinanzOnline
   - **CSV**: For Excel/tax advisor
4. Select language (German, English, Chinese)
5. Click "Generate"

### PDF Report

The PDF report contains:

- Personal information
- Income overview
- Expense overview
- Tax calculation (detailed)
- Tax credits
- Summary

### FinanzOnline XML

1. Generate the XML report
2. Download the file
3. Log in to FinanzOnline
4. Upload the XML file

**Important:** Taxja validates the XML against the official FinanzOnline schema!

### Audit Checklist

Before submission, check:

1. Go to "Reports" → "Audit Checklist"
2. Taxja shows:
   - ✅ All transactions documented
   - ⚠️ 2 receipts missing
   - ✅ All deductions documented
3. Resolve warnings before submission

## AI Tax Assistant

### Starting a Chat

1. Click the chat icon (bottom right)
2. Ask your question in German, English, or Chinese
3. The AI assistant responds immediately

### Example Questions

**General Questions:**
- "Can I deduct my home office?"
- "How much is the commuting allowance?"
- "What is the small business exemption?"

**Document Analysis:**
- "Which items on this receipt are deductible?"
- "Is this invoice correct?"

**Optimization:**
- "How can I save on taxes?"
- "Should I choose flat-rate taxation?"

### Important Notice

Every AI response ends with:

> ⚠️ **Disclaimer:** This response is for general information only and does not constitute tax advice. For complex cases, please consult a tax advisor (Steuerberater).

## FAQ

### General

**Q: Is Taxja a replacement for a tax advisor?**
A: No. Taxja is a tax management tool. For complex cases, we recommend consulting a tax advisor.

**Q: Is my data secure?**
A: Yes. Taxja uses AES-256 encryption for stored data and TLS 1.3 for transmission. We are GDPR compliant.

**Q: Can I use Taxja on my smartphone?**
A: Yes! Taxja is available as a Progressive Web App (PWA) and works on all devices.

### Transactions

**Q: How do I import transactions from my bank?**
A: Export your bank statements as CSV and import them under "Transactions" → "Import".

**Q: What happens if I miscategorize a transaction?**
A: No problem! Just correct the category. Taxja learns from your corrections.

**Q: Are duplicates automatically detected?**
A: Yes. During import, Taxja checks for duplicates (same amount, date, similar description).

### OCR

**Q: Which documents can Taxja recognize?**
A: Payslips, receipts, invoices, rental contracts, SVS notices, bank statements.

**Q: What do I do if OCR recognition fails?**
A: You can enter the data manually. Tips for better recognition: good lighting, flat document, sufficient resolution.

**Q: Are original documents saved?**
A: Yes. All uploaded documents are encrypted and stored, accessible at any time.

### Taxes

**Q: How accurate are the tax calculations?**
A: Taxja uses the official USP 2026 rates. Calculations have been validated against the official USP calculator (deviation < €0.01).

**Q: Can I calculate taxes from previous years?**
A: Yes. Taxja supports multiple tax years and loss carryforwards.

**Q: What's the difference between wage tax and income tax?**
A: Wage tax is withheld by the employer. Income tax is the total tax on all income. With employee tax assessment (Arbeitnehmerveranlagung), you can reclaim overpaid wage tax.

### Reports

**Q: Can I send the report directly to FinanzOnline?**
A: No. You must download the XML file and manually upload it to FinanzOnline. (FinanzOnline has no public API.)

**Q: In which languages can I create reports?**
A: German, English, and Chinese.

**Q: Can I send the report to my tax advisor?**
A: Yes. Export as PDF or CSV and send the file via email.

### Privacy

**Q: Can I export my data?**
A: Yes. Under "Settings" → "Export Data", you can download all your data as a ZIP archive (GDPR right).

**Q: Can I delete my account?**
A: Yes. Under "Settings" → "Delete Account", all your data will be permanently deleted.

**Q: Who has access to my data?**
A: Only you. Taxja employees have no access to your tax data.

## Support

For questions or issues:

- **Email**: support@taxja.at
- **Phone**: +43 1 234 5678 (Mon-Fri, 9am-5pm CET)
- **Chat**: Available in the system
- **Documentation**: https://docs.taxja.at

## Legal Notice

Taxja is a tax management tool and does not provide tax advice as defined by Austrian tax advisory law (Steuerberatungsgesetz). Calculations serve as guidance. Final tax assessment is made by the tax office (Finanzamt). For complex tax cases, we recommend consulting a licensed tax advisor (Steuerberater).

---

**Version:** 1.0  
**Date:** March 2026  
**© 2026 Taxja GmbH**
