# Austrian Tax Guide

## Overview

This guide provides an overview of Austrian tax regulations relevant to the Taxja platform. It serves as a reference for developers and users to understand the tax calculations and compliance requirements.

**IMPORTANT DISCLAIMER:** This guide is for informational purposes only and does not constitute tax advice. Users should consult with a qualified Steuerberater (tax advisor) for specific tax situations. Final tax filing must be done through FinanzOnline.

---

## Table of Contents

1. [Income Tax (Einkommensteuer)](#income-tax)
2. [Value Added Tax (Umsatzsteuer/VAT)](#value-added-tax)
3. [Social Insurance (Sozialversicherung/SVS)](#social-insurance)
4. [Property and Rental Income](#property-and-rental-income)
5. [Deductible Expenses](#deductible-expenses)
6. [Tax Filing Requirements](#tax-filing-requirements)

---

## Income Tax (Einkommensteuer)

Austrian income tax is progressive with the following brackets for 2026:

| Annual Income (EUR) | Tax Rate |
|---------------------|----------|
| 0 - 12,816 | 0% |
| 12,817 - 20,818 | 20% |
| 20,819 - 34,513 | 30% |
| 34,514 - 66,612 | 40% |
| 66,613 - 99,266 | 48% |
| 99,267 - 1,000,000 | 50% |
| Above 1,000,000 | 55% |

**Legal Basis:** § 33 EStG (Einkommensteuergesetz)

---

## Value Added Tax (Umsatzsteuer/VAT)

### Standard Rates

- **Standard Rate:** 20%
- **Reduced Rate:** 10% (food, books, cultural events)
- **Special Rate:** 13% (certain services)

### Small Business Exemption (Kleinunternehmerregelung)

Businesses with annual turnover below €35,000 can opt out of VAT registration under § 6 Abs 1 Z 27 UStG.

**Legal Basis:** Umsatzsteuergesetz (UStG)

---

## Social Insurance (Sozialversicherung/SVS)

### Self-Employed Contributions

Self-employed individuals must pay social insurance contributions to SVS (Sozialversicherung der Selbständigen).

**Contribution Rates (2026):**
- Pension insurance: ~18.5%
- Health insurance: ~7.65%
- Accident insurance: ~1.3%

**Minimum Contribution Base:** €5,710.32 per year

**Legal Basis:** GSVG (Gewerbliches Sozialversicherungsgesetz)

---

## Property and Rental Income

### Rental Property Tax Treatment

Rental income is taxable under **§ 28 EStG** (Einkünfte aus Vermietung und Verpachtung).

**Key Concepts:**
- Rental income is reported on E1 form (KZ 350)
- Deductible expenses are reported on E1 form (KZ 351)
- Building depreciation (AfA) is deductible
- Net rental income = Rental income - Expenses - AfA

### Depreciation (AfA - Absetzung für Abnutzung)

**Depreciation Rates:**
- Buildings constructed before 1915: 1.5% per year
- Buildings constructed 1915 or later: 2.0% per year

**Legal Basis:** § 8 EStG

### Detailed Property Tax Reference

For comprehensive information on property asset management, depreciation calculations, expense categories, and owner-occupied vs rental property differences, see:

**[Austrian Tax Law Reference: Property Asset Management](./AUSTRIAN_TAX_LAW_PROPERTY_REFERENCE.md)**

This detailed guide covers:
- AfA calculation rules and formulas
- Property expense categories (deductible and non-deductible)
- Owner-occupied vs rental property tax treatment
- Mixed-use property allocation rules
- Property purchase costs (Grunderwerbsteuer, notary fees, etc.)
- Legal references and official resources

---

## Deductible Expenses

### General Principles

Under Austrian tax law, expenses are deductible if they are:
1. **Ordinary and necessary** for income generation
2. **Properly documented** with receipts/invoices
3. **Business-related** (not personal expenses)

### Common Deductible Expense Categories

**For Employees (Werbungskosten):**
- Commuting costs (Pendlerpauschale)
- Professional development and training
- Work equipment and supplies
- Home office expenses (limited)

**For Self-Employed (Betriebsausgaben):**
- Office rent and utilities
- Equipment and supplies
- Professional services (legal, accounting)
- Marketing and advertising
- Travel expenses
- Depreciation of assets

**For Landlords (Werbungskosten - Vermietung):**
- Loan interest
- Maintenance and repairs
- Property management fees
- Property insurance
- Property tax (Grundsteuer)
- Utilities (if not reimbursed by tenant)
- Depreciation (AfA)

See [Property Tax Reference](./AUSTRIAN_TAX_LAW_PROPERTY_REFERENCE.md) for detailed rental property expense categories.

---

## Tax Filing Requirements

### E1 Form (Einkommensteuererklärung)

The E1 form is the annual income tax declaration for individuals.

**Filing Deadline:**
- April 30 of the following year (for self-filing)
- June 30 if using a tax advisor (Steuerberater)

**Filing Method:**
- Electronic filing through FinanzOnline (mandatory for most taxpayers)

### Required Documentation

Taxpayers must retain the following for 7 years:
- Receipts and invoices
- Bank statements
- Employment records (Lohnzettel)
- Property purchase contracts (Kaufvertrag)
- Rental agreements (Mietvertrag)
- Tax assessments (Bescheid)

### FinanzOnline

**Official Portal:** https://finanzonline.bmf.gv.at

FinanzOnline is the official Austrian tax portal for:
- Filing tax returns (E1, U30, etc.)
- Viewing tax assessments (Bescheid)
- Making tax payments
- Communicating with tax authorities

---

## Official Resources

### Government Agencies

**Bundesministerium für Finanzen (BMF)**
- Federal Ministry of Finance
- Website: https://www.bmf.gv.at
- Tax guidelines and regulations

**Finanzamt**
- Local tax offices
- Handle tax assessments and audits

### Professional Organizations

**Wirtschaftskammer Österreich (WKO)**
- Austrian Economic Chamber
- Business and tax guidance

**Österreichischer Steuerberaterverband**
- Austrian Tax Advisors Association
- Find qualified tax advisors

---

## Taxja Platform Scope

The Taxja platform assists with:
- Transaction tracking and classification
- Tax calculation estimates
- Document management (OCR)
- Property asset management
- Report generation

**What Taxja Does NOT Do:**
- Official tax filing (use FinanzOnline)
- Replace professional tax advice
- Guarantee tax compliance
- Handle complex tax situations requiring Steuerberater

---

## Disclaimer

This guide is provided for informational purposes only and does not constitute legal or tax advice. Austrian tax law is complex and subject to change. Users should:

1. Consult with a qualified Steuerberater for specific situations
2. Verify current tax rates and rules with official BMF sources
3. File official tax returns through FinanzOnline
4. Retain all supporting documentation

The Taxja platform is a reference tool to assist with tax management. It does not replace professional tax advice or official tax filing obligations.

---

**Document Version:** 1.0  
**Last Updated:** 2026-03-08  
**Applicable Tax Year:** 2026

