# User Acceptance Testing (UAT) Guide

## Overview

This guide outlines the user acceptance testing procedures for Taxja. UAT validates that the system meets Austrian tax requirements and provides a good user experience.

## Test Environment

**URL:** https://uat.taxja.at  
**Test Period:** March 4-18, 2026  
**Test Users:** See demo accounts in [Demo Data README](../backend/scripts/README_DEMO.md)

## Testing Objectives

1. Verify tax calculations against official USP 2026 calculator
2. Validate all user workflows
3. Test with real Austrian tax scenarios
4. Ensure multi-language support works correctly
5. Verify GDPR compliance
6. Test mobile responsiveness

## Test Scenarios

### Scenario 1: Employee Tax Refund (Arbeitnehmerveranlagung)

**User Profile:** Maria Müller (employee@demo.taxja.at)

**Test Steps:**

1. **Login**
   - Navigate to https://uat.taxja.at
   - Login with employee@demo.taxja.at / Demo2026!
   - ✅ Verify successful login and redirect to dashboard

2. **View Dashboard**
   - Check year-to-date income display
   - Check estimated tax display
   - ✅ Verify amounts match expected values

3. **Upload Lohnzettel**
   - Go to Documents → Upload
   - Upload sample payslip (Lohnzettel)
   - ✅ Verify OCR recognizes: gross income, net income, withheld tax

4. **Review OCR Results**
   - Check extracted data accuracy
   - Correct any errors
   - Confirm and create transaction
   - ✅ Verify transaction created correctly

5. **Calculate Tax Refund**
   - Go to Tax → Calculate Refund
   - Review calculation
   - ✅ Verify refund amount matches manual calculation

6. **Generate Tax Report**
   - Go to Reports → Generate
   - Select PDF format, German language
   - ✅ Verify PDF contains all required sections

**Expected Results:**
- Refund calculation: ~€1,300 (based on commuting allowance + home office)
- PDF report generated in German
- All deductions properly documented

**Validation Against USP Calculator:**
- Compare calculated tax with https://rechner.cpulohn.at/bmf.gv.at/
- Deviation must be < €0.01

---

### Scenario 2: Self-Employed VAT and SVS

**User Profile:** Thomas Weber (selfemployed@demo.taxja.at)

**Test Steps:**

1. **Login and Setup**
   - Login with selfemployed@demo.taxja.at / Demo2026!
   - Verify profile shows VAT number

2. **Import Bank Transactions**
   - Go to Transactions → Import
   - Upload sample CSV file
   - ✅ Verify transactions imported correctly
   - ✅ Verify automatic categorization

3. **Review VAT Calculation**
   - Go to Tax → VAT Overview
   - Check output VAT (20% on income)
   - Check input VAT (from expenses)
   - ✅ Verify net VAT payable is correct

4. **Review SVS Contributions**
   - Go to Tax → Social Insurance
   - Check pension insurance (18.5%)
   - Check health insurance (6.8%)
   - ✅ Verify total SVS contributions

5. **Test What-If Simulator**
   - Go to Tax → Simulator
   - Add hypothetical expense (€5,000 equipment)
   - ✅ Verify tax savings calculation

6. **Compare Flat-Rate vs Actual**
   - Go to Tax → Flat-Rate Comparison
   - ✅ Verify both methods calculated
   - ✅ Verify recommendation shown

7. **Generate FinanzOnline XML**
   - Go to Reports → Generate
   - Select XML format
   - Download file
   - ✅ Verify XML validates against FinanzOnline schema

**Expected Results:**
- VAT liability: ~€2,500
- SVS contributions: ~€8,450/year
- Actual accounting saves ~€4,500 vs flat-rate
- XML passes schema validation

---

### Scenario 3: Landlord with Property Expenses

**User Profile:** Anna Schmidt (landlord@demo.taxja.at)

**Test Steps:**

1. **Login**
   - Login with landlord@demo.taxja.at / Demo2026!

2. **Review Rental Income**
   - Go to Transactions
   - Filter by income type
   - ✅ Verify monthly rental income (€1,200)
   - ✅ Verify 10% VAT applied (residential)

3. **Add Property Expenses**
   - Create new expense: Maintenance (€450)
   - Create new expense: Property management (€120)
   - ✅ Verify expenses marked as deductible

4. **Upload Maintenance Receipt**
   - Go to Documents → Upload
   - Upload receipt photo
   - ✅ Verify OCR extracts amount and date
   - Link to existing transaction

5. **Calculate Property Depreciation**
   - Go to Tax → Deductions
   - Enter property purchase price and date
   - ✅ Verify depreciation calculated (1.5% standard)

6. **Review Tax Calculation**
   - Go to Tax → Calculate
   - ✅ Verify rental income taxed correctly
   - ✅ Verify all expenses deducted
   - ✅ Verify mortgage interest deducted

7. **Check Audit Readiness**
   - Go to Reports → Audit Checklist
   - ✅ Verify all transactions have documents
   - ✅ Verify no missing receipts

**Expected Results:**
- Net rental income: ~€14,400/year
- Deductible expenses: ~€3,000/year
- All transactions properly documented

---

### Scenario 4: Mixed Income (Employee + Landlord)

**User Profile:** Peter Gruber (mixed@demo.taxja.at)

**Test Steps:**

1. **Login**
   - Login with mixed@demo.taxja.at / Demo2026!

2. **Review Multiple Income Sources**
   - Go to Dashboard
   - ✅ Verify employment income shown
   - ✅ Verify rental income shown
   - ✅ Verify combined tax calculation

3. **Test Large Commuting Allowance**
   - Go to Profile → Commuting
   - Verify distance: 45 km
   - Verify no public transport
   - ✅ Verify large Pendlerpauschale applied

4. **Test Family Deductions**
   - Go to Tax → Deductions
   - ✅ Verify 3 children registered
   - ✅ Verify Kinderabsetzbetrag calculated (€58.40 × 3 × 12)

5. **Generate Comprehensive Report**
   - Go to Reports → Generate
   - Select PDF, all sections
   - ✅ Verify both income sources included
   - ✅ Verify all deductions listed

**Expected Results:**
- Combined income properly taxed
- Large commuting allowance: ~€3,000/year
- Child tax credits: ~€2,100/year
- Complex tax calculation accurate

---

## Cross-Functional Tests

### Test 5: Multi-Language Support

**Test Steps:**

1. **Switch to German**
   - Click language selector
   - Select "Deutsch"
   - ✅ Verify all UI text in German
   - ✅ Verify tax terms use German (Einkommensteuer, USt, etc.)

2. **Switch to English**
   - Select "English"
   - ✅ Verify all UI text in English
   - ✅ Verify tax terms translated with German in parentheses

3. **Switch to Chinese**
   - Select "中文"
   - ✅ Verify all UI text in Chinese
   - ✅ Verify tax terms translated

4. **Generate Reports in Each Language**
   - Generate PDF in German
   - Generate PDF in English
   - Generate PDF in Chinese
   - ✅ Verify all reports properly formatted

---

### Test 6: AI Tax Assistant

**Test Steps:**

1. **Open AI Chat**
   - Click chat icon (bottom right)
   - ✅ Verify chat window opens

2. **Ask General Question (German)**
   - Type: "Kann ich mein Homeoffice absetzen?"
   - ✅ Verify response in German
   - ✅ Verify disclaimer included

3. **Ask Calculation Question (English)**
   - Switch to English
   - Type: "How much is the commuting allowance for 35 km?"
   - ✅ Verify response in English
   - ✅ Verify correct calculation explained

4. **Upload Document for Analysis**
   - Upload receipt in chat
   - Ask: "Which items are deductible?"
   - ✅ Verify AI analyzes items
   - ✅ Verify deductibility explained

5. **Ask for Optimization**
   - Type: "How can I save on taxes?"
   - ✅ Verify personalized suggestions
   - ✅ Verify based on user's actual data

---

### Test 7: Mobile Responsiveness

**Test Steps:**

1. **Access on Mobile Device**
   - Open https://uat.taxja.at on smartphone
   - ✅ Verify responsive layout

2. **Test Camera Upload**
   - Go to Documents → Upload
   - Click camera icon
   - Take photo of receipt
   - ✅ Verify photo uploads
   - ✅ Verify OCR processes

3. **Test Mobile Navigation**
   - Open hamburger menu
   - Navigate to different pages
   - ✅ Verify all pages accessible
   - ✅ Verify touch-friendly buttons

4. **Test PWA Installation**
   - Click "Add to Home Screen"
   - ✅ Verify app installs
   - ✅ Verify offline mode works

---

### Test 8: Security and GDPR

**Test Steps:**

1. **Test 2FA**
   - Go to Settings → Security
   - Enable 2FA
   - ✅ Verify QR code displayed
   - Scan with authenticator app
   - Logout and login again
   - ✅ Verify 2FA token required

2. **Test Data Export**
   - Go to Settings → Privacy
   - Click "Export My Data"
   - ✅ Verify ZIP file downloads
   - ✅ Verify contains all user data

3. **Test Session Timeout**
   - Leave browser idle for 30 minutes
   - Try to perform action
   - ✅ Verify automatic logout
   - ✅ Verify redirect to login

4. **Test Disclaimer**
   - Create new account
   - ✅ Verify disclaimer modal on first login
   - ✅ Verify must accept to proceed

---

## Tax Calculation Validation

### Validation Against Official USP Calculator

For each test scenario, validate tax calculations:

1. **Access USP Calculator**
   - Go to https://rechner.cpulohn.at/bmf.gv.at/

2. **Enter Same Parameters**
   - Income amount
   - Deductions
   - Family situation

3. **Compare Results**
   - Taxja calculation
   - USP calculator result
   - ✅ Deviation must be < €0.01

### Test Cases for Validation

| Income | Deductions | Expected Tax | Taxja Result | USP Result | Pass/Fail |
|--------|------------|--------------|--------------|------------|-----------|
| €30,000 | €2,000 | €3,692.20 | | | |
| €50,000 | €5,000 | €10,692.20 | | | |
| €75,000 | €10,000 | €19,632.00 | | | |
| €100,000 | €15,000 | €29,532.00 | | | |

---

## Performance Tests

### Test 9: System Performance

**Test Steps:**

1. **Page Load Times**
   - Measure dashboard load time
   - ✅ Target: < 2 seconds

2. **OCR Processing**
   - Upload document
   - Measure processing time
   - ✅ Target: < 5 seconds per document

3. **Tax Calculation**
   - Calculate tax for 100 transactions
   - Measure calculation time
   - ✅ Target: < 1 second

4. **Report Generation**
   - Generate PDF report
   - Measure generation time
   - ✅ Target: < 3 seconds

---

## Bug Reporting

### Bug Report Template

```
**Title:** [Brief description]

**Severity:** Critical / High / Medium / Low

**Steps to Reproduce:**
1. 
2. 
3. 

**Expected Result:**

**Actual Result:**

**Screenshots:**

**Environment:**
- Browser:
- OS:
- User Account:

**Additional Notes:**
```

### Severity Levels

- **Critical:** System crash, data loss, security vulnerability
- **High:** Major feature broken, incorrect tax calculation
- **Medium:** Minor feature issue, UI problem
- **Low:** Cosmetic issue, typo

---

## Sign-Off Criteria

UAT is considered successful when:

- ✅ All critical and high-severity bugs resolved
- ✅ Tax calculations validated against USP calculator (< €0.01 deviation)
- ✅ All user workflows completed successfully
- ✅ Multi-language support verified
- ✅ Mobile responsiveness confirmed
- ✅ Security and GDPR compliance verified
- ✅ Performance targets met
- ✅ At least 3 real users tested the system

## UAT Sign-Off

**Test Lead:** _____________________  
**Date:** _____________________

**Product Owner:** _____________________  
**Date:** _____________________

**Stakeholders:**
- [ ] Development Team
- [ ] QA Team
- [ ] Business Analyst
- [ ] Tax Expert Consultant

---

**Version:** 1.0  
**Last Updated:** March 2026  
**© 2026 Taxja GmbH**
