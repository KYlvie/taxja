# Austrian Tax Law Reference: Property Asset Management

## Document Purpose

This document provides a reference guide to Austrian tax law as it relates to rental property management, depreciation (AfA), and property-related deductions. This is intended as a technical reference for developers implementing property tax calculations in the Taxja platform.

**IMPORTANT DISCLAIMER:** This document is for informational and development purposes only. It does not constitute tax advice. Users should consult with a qualified Steuerberater (tax advisor) for specific tax situations. Final tax filing must be done through FinanzOnline.

---

## Table of Contents

1. [AfA (Depreciation) Calculation Rules](#afa-depreciation-calculation-rules)
2. [Property Expense Categories](#property-expense-categories)
3. [Owner-Occupied vs Rental Properties](#owner-occupied-vs-rental-properties)
4. [Mixed-Use Properties](#mixed-use-properties)
5. [Property Purchase Costs](#property-purchase-costs)
6. [Legal References](#legal-references)

---

## AfA (Depreciation) Calculation Rules

### Legal Basis

**Absetzung für Abnutzung (AfA)** is regulated under Austrian Income Tax Law:
- **§ 7 EStG** - General depreciation rules
- **§ 8 EStG** - Depreciation rates for buildings
- **§ 16 EStG** - Income from rental and leasing (Vermietung und Verpachtung)

### Depreciation Rates for Buildings

Austrian tax law specifies different depreciation rates based on building construction year:

| Construction Year | Annual Depreciation Rate | Legal Basis |
|-------------------|-------------------------|-------------|
| Before 1915 | 1.5% | § 8 Abs 1 EStG |
| 1915 or later | 2.0% | § 8 Abs 1 EStG |

**Implementation Note:** If construction year is unknown, use the default rate of 2.0%.

### Depreciable Value

Only the **building value** (Gebäudewert) is depreciable. Land value (Grundwert) is NOT depreciable.

**Standard Allocation:**
- Building value: 80% of total purchase price
- Land value: 20% of total purchase price

**Alternative Methods:**
- Use official property valuation (Gutachten)
- Use assessed values from property tax assessment (Einheitswert)
- Use values stated in purchase contract (Kaufvertrag) if separately itemized

**Formula:**
```
Depreciable Building Value = Purchase Price - Land Value
Annual AfA = Building Value × Depreciation Rate
```

### Pro-Rata Depreciation (First and Last Year)

**First Year of Ownership:**
Depreciation is calculated pro-rata based on months of ownership in the year of purchase.

**Formula:**
```
First Year AfA = (Building Value × Depreciation Rate × Months Owned) / 12
```

**Month Counting Rule:**
- Purchase in January: 12 months
- Purchase in June: 7 months (June through December)
- Purchase in December: 1 month

**Last Year of Ownership (Sale):**
Similar pro-rata calculation applies in the year of sale.

### Depreciation Limit

**Maximum Accumulated Depreciation:**
Total accumulated depreciation cannot exceed the original building value.

**Formula:**
```
Total Accumulated AfA ≤ Building Value
```

Once fully depreciated, no further depreciation can be claimed.

### Depreciation Period

**Standard Depreciation Period:**
- 1.5% rate: 66.67 years to fully depreciate
- 2.0% rate: 50 years to fully depreciate

**Practical Note:** Most buildings will not be fully depreciated during ownership due to the long depreciation periods.

---

## Property Expense Categories

### Deductible Rental Property Expenses

Under **§ 28 EStG** (Income from rental and leasing), the following expenses are deductible:

#### 1. Loan Interest (Kreditzinsen)
- **Deductible:** Interest portion of mortgage payments
- **NOT Deductible:** Principal repayment
- **E1 Form Field:** KZ 351 (Werbungskosten)
- **Documentation:** Bank statements, loan agreement

#### 2. Maintenance and Repairs (Instandhaltung und Reparaturen)
- **Deductible:** Ordinary repairs to maintain property condition
- **Examples:** Painting, plumbing repairs, roof repairs, heating system maintenance
- **NOT Deductible:** Major improvements that increase property value (capitalized)
- **E1 Form Field:** KZ 351
- **Documentation:** Invoices from contractors

#### 3. Property Management Fees (Hausverwaltungskosten)
- **Deductible:** Fees paid to property management companies
- **Examples:** Monthly management fees, tenant placement fees
- **E1 Form Field:** KZ 351
- **Documentation:** Management company invoices

#### 4. Property Insurance (Versicherungen)
- **Deductible:** Building insurance, liability insurance, rental loss insurance
- **E1 Form Field:** KZ 351
- **Documentation:** Insurance premium statements

#### 5. Property Tax (Grundsteuer)
- **Deductible:** Annual municipal property tax
- **E1 Form Field:** KZ 351
- **Documentation:** Property tax assessment notice

#### 6. Utilities (Betriebskosten)
- **Deductible:** Utilities paid by landlord (if not reimbursed by tenant)
- **Examples:** Water, heating, electricity for common areas
- **NOT Deductible:** Utilities reimbursed by tenant
- **E1 Form Field:** KZ 351
- **Documentation:** Utility bills

#### 7. Depreciation (AfA - Absetzung für Abnutzung)
- **Deductible:** Annual building depreciation (see AfA section above)
- **E1 Form Field:** KZ 351
- **Calculation:** Automatic based on building value and depreciation rate

#### 8. Legal and Professional Fees (Rechts- und Beratungskosten)
- **Deductible:** Lawyer fees, tax advisor fees related to rental property
- **E1 Form Field:** KZ 351
- **Documentation:** Professional service invoices

#### 9. Advertising Costs (Werbekosten)
- **Deductible:** Costs to find tenants (online listings, newspaper ads)
- **E1 Form Field:** KZ 351
- **Documentation:** Advertising invoices

#### 10. Travel Expenses (Fahrtkosten)
- **Deductible:** Travel to property for management purposes
- **Rate:** Standard mileage rate or actual costs
- **E1 Form Field:** KZ 351
- **Documentation:** Mileage log or receipts

### Non-Deductible Expenses

The following are **NOT** deductible for rental properties:
- Principal portion of mortgage payments
- Major improvements (capitalized and depreciated separately)
- Personal expenses unrelated to rental activity
- Fines and penalties

---

## Owner-Occupied vs Rental Properties

### Rental Properties (Vermietung)

**Tax Treatment:**
- **Income:** Rental income is taxable under § 28 EStG
- **Expenses:** All ordinary and necessary expenses are deductible
- **Depreciation:** Building value is depreciable (AfA)
- **E1 Form Section:** Einkünfte aus Vermietung und Verpachtung
- **E1 Form Fields:**
  - KZ 350: Rental income (Einnahmen)
  - KZ 351: Rental expenses (Werbungskosten)

**Net Rental Income Calculation:**
```
Net Rental Income = Rental Income - Deductible Expenses - AfA
```

**Loss Carryforward:**
If expenses exceed income, the loss can be carried forward to future years under § 18 Abs 6 EStG.

### Owner-Occupied Properties (Eigennutzung)

**Tax Treatment:**
- **Income:** No rental income (personal use)
- **Expenses:** Generally NOT deductible
- **Depreciation:** NOT allowed (no AfA for personal residence)
- **E1 Form:** Not reported (no rental activity)

**Exceptions (Limited Deductibility):**

1. **Home Office (Arbeitszimmer) - § 20 Abs 1 Z 2 lit d EStG**
   - Deductible if home office is center of professional activity
   - Maximum deduction: €1,200 per year (for employees)
   - Self-employed: Full deduction if exclusively used for business
   - Requirements: Separate room, exclusively for work, necessary for profession

2. **Energy-Efficient Renovations (Sanierungskosten)**
   - Specific tax credits may apply for thermal renovations
   - Subject to specific programs and requirements
   - Consult current BMF guidelines

3. **Capital Gains Tax Consideration (ImmoESt)**
   - Purchase costs are relevant for capital gains calculation upon sale
   - Grunderwerbsteuer (property transfer tax) is part of cost basis
   - Reduces taxable gain when property is sold

**Purchase Costs for Owner-Occupied:**
While not immediately deductible, the following should be tracked for future capital gains calculations:
- Purchase price
- Grunderwerbsteuer (property transfer tax): 3.5% of purchase price
- Eintragungsgebühr (land registry fee): 1.1% of purchase price
- Notary fees
- Real estate agent commission (if applicable)

### Key Differences Summary

| Aspect | Rental Property | Owner-Occupied |
|--------|----------------|----------------|
| Rental Income | Taxable (KZ 350) | N/A |
| Operating Expenses | Deductible (KZ 351) | NOT deductible |
| Depreciation (AfA) | Deductible | NOT allowed |
| Loan Interest | Deductible | NOT deductible* |
| Property Tax | Deductible | NOT deductible |
| Insurance | Deductible | NOT deductible |
| Maintenance | Deductible | NOT deductible |
| Home Office | N/A | Limited deduction |
| Purchase Costs | Capitalized & depreciated | Tracked for capital gains |

*Exception: Interest may be partially deductible if home office qualifies

---

## Mixed-Use Properties (Gemischt)

### Definition

A mixed-use property is one where part is used for rental income and part for personal residence.

**Examples:**
- Two-family house: Owner lives in one unit, rents the other
- Commercial/residential building: Ground floor shop (rented), upper floor apartment (owner-occupied)
- Single-family house with separate rental apartment

### Tax Treatment

**Allocation Principle:**
Expenses must be allocated proportionally between rental and personal use.

**Rental Percentage Calculation:**
```
Rental Percentage = (Rental Area in m²) / (Total Property Area in m²) × 100%
```

**Alternative Methods:**
- Number of rooms (if similar size)
- Assessed value allocation
- Income-based allocation (for commercial properties)

### Depreciation for Mixed-Use

**Only the rental portion is depreciable:**
```
Depreciable Building Value = Total Building Value × Rental Percentage
Annual AfA = Depreciable Building Value × Depreciation Rate
```

**Example:**
- Total building value: €300,000
- Rental percentage: 50% (one unit rented, one owner-occupied)
- Depreciation rate: 2.0%
- Annual AfA: €300,000 × 50% × 2.0% = €3,000

### Expense Allocation for Mixed-Use

**Directly Attributable Expenses:**
- Expenses specific to rental unit: 100% deductible
- Expenses specific to owner-occupied unit: 0% deductible

**Shared Expenses (allocated by rental percentage):**
- Property tax (Grundsteuer)
- Building insurance
- Common area maintenance
- Roof repairs
- Heating system (if shared)
- Property management fees

**Example Allocation:**
- Rental percentage: 60%
- Total property tax: €1,000
- Deductible portion: €1,000 × 60% = €600

### E1 Form Reporting for Mixed-Use

**KZ 350 (Rental Income):**
- Report only rental income from rented portion

**KZ 351 (Rental Expenses):**
- Report only allocated expenses (rental percentage)
- Include allocated AfA

**Documentation Requirements:**
- Floor plan showing rental vs personal areas
- Calculation of rental percentage
- Allocation methodology for shared expenses

---

## Property Purchase Costs

### Grunderwerbsteuer (Property Transfer Tax)

**Rate:** 3.5% of purchase price (standard rate)

**Reduced Rates:**
- 0.5% for transfers within family (certain conditions)
- 2.0% for agricultural/forestry land

**Tax Basis:** Purchase price stated in contract

**Payment:** Due within one month of contract signing

**Tax Treatment:**
- **Rental Property:** Part of acquisition cost, capitalized and depreciated
- **Owner-Occupied:** Part of cost basis for future capital gains calculation
- **NOT immediately deductible** in year of purchase

### Eintragungsgebühr (Land Registry Fee)

**Rate:** 1.1% of purchase price

**Purpose:** Fee for registering ownership in land registry (Grundbuch)

**Tax Treatment:** Same as Grunderwerbsteuer (capitalized, not immediately deductible)

### Notary Fees (Notarkosten)

**Typical Range:** 1-2% of purchase price

**Services Included:**
- Contract preparation
- Due diligence
- Registration with land registry
- Escrow services

**Tax Treatment:** Part of acquisition costs (capitalized)

### Real Estate Agent Commission (Maklerprovision)

**Typical Rate:** 3% + 20% VAT = 3.6% of purchase price

**Legal Note:** Commission structure varies; may be split between buyer and seller

**Tax Treatment:** Part of acquisition costs (capitalized)

### Total Purchase Costs Summary

**Typical Total Costs (beyond purchase price):**
- Grunderwerbsteuer: 3.5%
- Eintragungsgebühr: 1.1%
- Notary fees: 1.5%
- Agent commission: 3.6%
- **Total: ~9.7% of purchase price**

**Example:**
- Purchase price: €300,000
- Additional costs: €29,100
- Total investment: €329,100

---

## Legal References

### Primary Legislation

**Einkommensteuergesetz (EStG) - Income Tax Act**
- § 7 EStG: Depreciation of assets
- § 8 EStG: Depreciation rates for buildings
- § 16 EStG: Determination of income
- § 18 EStG: Loss carryforward
- § 20 EStG: Business expenses (Betriebsausgaben)
- § 28 EStG: Income from rental and leasing (Vermietung und Verpachtung)

**Immobilienertragsteuergesetz (ImmoESt) - Real Estate Capital Gains Tax**
- Applies to property sales
- Rate: 30% on capital gains (for properties acquired after March 31, 2012)
- Cost basis includes purchase price + acquisition costs

**Grunderwerbsteuergesetz (GrEStG) - Property Transfer Tax Act**
- Regulates property transfer tax rates and exemptions

### Official Resources

**Bundesministerium für Finanzen (BMF) - Federal Ministry of Finance**
- Website: https://www.bmf.gv.at
- Tax guidelines and circulars (Einkommensteuerrichtlinien)

**FinanzOnline**
- Official tax filing portal: https://finanzonline.bmf.gv.at
- E1 form (Einkommensteuererklärung) for annual tax declaration

**Einkommensteuerrichtlinien (EStR)**
- Detailed administrative guidelines for income tax
- Section on rental income (Vermietung und Verpachtung)

### Professional Resources

**Wirtschaftskammer Österreich (WKO)**
- Austrian Economic Chamber
- Tax guides for businesses and landlords

**Österreichischer Steuerberaterverband**
- Austrian Tax Advisors Association
- Professional standards and guidance

---

## Implementation Notes for Developers

### Validation Rules

1. **Depreciation Rate:**
   - Must be between 0.1% and 10%
   - Default: 2.0% (or 1.5% if construction_year < 1915)

2. **Building Value:**
   - Must be ≤ purchase_price
   - Must be > 0
   - Default: 80% of purchase_price if not specified

3. **Rental Percentage (Mixed-Use):**
   - Must be between 0% and 100%
   - Default: 100% for rental properties
   - Required for mixed-use properties

4. **Purchase Price:**
   - Must be > 0
   - Must be ≤ €100,000,000 (sanity check)

### Calculation Precision

- All monetary amounts: Round to 2 decimal places
- Percentages: Store as decimal (e.g., 2.0% = 0.02)
- Use Decimal type for financial calculations (avoid float)

### E1 Form Field Mapping

| Property Data | E1 Form Field | Description |
|---------------|---------------|-------------|
| Rental Income | KZ 350 | Einnahmen aus Vermietung |
| All Expenses | KZ 351 | Werbungskosten |
| AfA | KZ 351 | Included in Werbungskosten |
| Net Income | Calculated | KZ 350 - KZ 351 |

### Audit Trail Requirements

For GDPR and tax audit purposes, maintain:
- Property registration date and user
- All depreciation calculations with timestamps
- Expense allocations for mixed-use properties
- Source documents (Kaufvertrag, invoices)
- Changes to property data (audit log)

---

## Disclaimer

This document is provided for informational purposes only and does not constitute legal or tax advice. Austrian tax law is complex and subject to change. Users should:

1. Consult with a qualified Steuerberater (tax advisor) for specific situations
2. Verify current tax rates and rules with official BMF sources
3. File official tax returns through FinanzOnline
4. Retain all supporting documentation for tax audits

The Taxja platform is a reference tool to assist with tax calculations. It does not replace professional tax advice or official tax filing obligations.

---

**Document Version:** 1.0  
**Last Updated:** 2026-03-08  
**Applicable Tax Year:** 2026  
**Legal Basis:** Austrian Income Tax Act (EStG) as of 2026

