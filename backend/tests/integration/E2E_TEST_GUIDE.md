# End-to-End Test Guide

## Overview

This document describes the comprehensive end-to-end (E2E) tests for the Taxja tax management system. These tests validate complete user journeys from start to finish, ensuring all system components work together correctly.

## Test Coverage

### 1. Complete Tax Filing Workflow (`TestCompleteTaxFilingWorkflow`)

**Scenario**: Self-employed user's complete tax year journey

**Steps**:
1. Register new self-employed user account
2. Login and obtain authentication token
3. Update profile with business information (tax number, VAT number, address)
4. Add income transactions throughout the year (consulting revenue)
5. Add deductible business expenses (equipment, supplies, insurance, marketing)
6. Verify all transactions were created correctly
7. Calculate taxes for the year (income tax, VAT, SVS)
8. Generate PDF tax report in German
9. Download and verify PDF report
10. Generate FinanzOnline XML export
11. Download and verify XML contains required elements
12. Export transactions to CSV
13. View dashboard summary with all calculations

**Validates**:
- User registration and authentication (Requirements 11.1, 11.2, 17.3, 17.4)
- Transaction management (Requirements 1.1, 1.2, 1.5, 1.6)
- Tax calculation (Requirements 3.1-3.9, 4.1-4.13, 28.1-28.9)
- Report generation (Requirements 7.1-7.8, 8.1-8.3)
- Dashboard functionality (Requirements 34.1-34.7)

**Expected Results**:
- Total income: €36,200
- Total expenses: €2,800
- VAT status: Small business exemption (below €55,000 threshold)
- SVS contributions calculated
- Income tax calculated on taxable income
- All reports generated successfully

---

### 2. OCR to Transaction to Report Flow (`TestOCRToTransactionToReportFlow`)

**Scenario**: User uploads receipts and invoices, processes via OCR, creates transactions, generates reports

**Steps**:
1. Create test receipt image
2. Upload document for OCR processing
3. Verify OCR extraction completed
4. Get OCR review data with confidence scores
5. Correct OCR data (simulate user review)
6. Create transaction from corrected OCR data
7. Upload business invoice document
8. Create deductible expense from invoice
9. Verify documents are archived and linked to transactions
10. Generate report including OCR-sourced transactions
11. Verify report includes document references
12. Check audit readiness (transactions have supporting documents)

**Batch Processing Test**:
- Upload 5 receipts simultaneously
- Verify batch OCR processing
- Review low-confidence results

**Validates**:
- Document upload (Requirements 19.1, 24.1, 24.2)
- OCR processing (Requirements 19.2, 19.3, 19.4, 19.7)
- OCR review and correction (Requirements 23.1-23.5)
- Document archival (Requirements 24.3-24.7, 19.8, 19.9)
- Transaction-document linking
- Audit trail completeness (Requirements 32.1-32.6)

---

### 3. Employee Refund Calculation Flow (`TestEmployeeRefundCalculationFlow`)

**Scenario**: Employee uploads Lohnzettel, calculates tax refund (Arbeitnehmerveranlagung)

**Steps**:
1. Register employee user
2. Login and authenticate
3. Update profile with commuting information (45km, public transport available)
4. Update family information (2 children)
5. Upload Lohnzettel (payslip) document
6. Provide Lohnzettel data (gross income, withheld tax, withheld SVS)
7. Create employment income transaction
8. Add deductible work-related expenses
9. Calculate employee refund
10. Verify deductions applied (commuting, home office, family, work expenses)
11. Verify refund amount is positive
12. Generate refund report (Arbeitnehmerveranlagung)
13. Download PDF report
14. Generate FinanzOnline XML for submission
15. View refund estimate on dashboard

**Validates**:
- Employee-specific workflows (Requirements 37.1-37.7)
- Lohnzettel OCR extraction (Requirements 20.2-20.5, 37.1, 37.2)
- Refund calculation (Requirements 37.3, 37.4, 37.5)
- Commuting allowance (Requirements 29.2, Pendlerpauschale)
- Home office deduction (Requirements 29.3)
- Family deductions (Requirements 29.1, Kinderabsetzbetrag)
- Dashboard refund display (Requirements 37.6, 37.7)

**Expected Deductions**:
- Commuting allowance: €113/month (45km with public transport)
- Pendlereuro: €270/year (45km × €6)
- Home office: €300/year
- Family deductions: €1,401.60/year (2 children × €58.40/month × 12)
- Work expenses: €1,050

---

### 4. Mixed Income Complete Workflow (`TestMixedIncomeCompleteWorkflow`)

**Scenario**: Employee with additional rental income

**Steps**:
1. Register employee user
2. Login and authenticate
3. Add employment income (€50,000)
4. Add monthly rental income (€1,200/month × 12 = €14,400)
5. Add rental property expenses (maintenance, management, insurance, mortgage interest)
6. Calculate combined taxes
7. Verify income summary shows both sources
8. Verify rental expenses are deducted
9. Verify VAT status for rental income
10. Generate comprehensive report
11. View dashboard with mixed income breakdown

**Validates**:
- Multiple income sources (Requirements 3.8, 10.1)
- Rental income handling (Requirements 5.1-5.12)
- Combined tax calculation (Requirements 3.5, 3.8)
- Property expense deductions (Requirements 5.1, 5.2)
- VAT for residential rental (Requirements 4.4, 4.5)

**Expected Results**:
- Employment income: €50,000
- Rental income: €14,400
- Total income: €64,400
- Rental expenses: €6,200 (deductible)
- Combined income tax calculated correctly

---

### 5. Loss Carryforward Workflow (`TestLossCarryforwardWorkflow`)

**Scenario**: Self-employed user with loss in 2025, profit in 2026

**Steps**:
1. Register self-employed user
2. Add 2025 transactions (€15,000 income, €25,000 expenses = €10,000 loss)
3. Calculate 2025 taxes (verify loss recorded)
4. Add 2026 transactions (€50,000 income, €15,000 expenses = €35,000 profit)
5. Calculate 2026 taxes with loss carryforward
6. Verify loss carryforward was applied
7. Verify taxable income reduced by loss
8. Check remaining loss balance

**Validates**:
- Loss carryforward tracking (Requirements 36.1, 36.2, 36.3)
- Multi-year loss propagation (Requirements 36.5, 16.5)
- Tax calculation with loss offset
- Loss balance management

**Expected Results**:
- 2025 loss: €10,000
- 2026 profit before loss: €35,000
- Loss applied: €10,000
- 2026 taxable income: €25,000
- Tax savings: ~€3,000 (30% of €10,000)

---

### 6. Data Export/Import Workflow (`TestDataExportImportWorkflow`)

**Scenario**: GDPR-compliant data export

**Steps**:
1. Create transactions and documents
2. Request GDPR data export
3. Verify export contains all user data
4. Verify completeness of exported data

**Validates**:
- GDPR compliance (Requirements 17.6, 17.7)
- Data export completeness
- User data portability

---

### 7. Audit Readiness Workflow (`TestAuditReadinessWorkflow`)

**Scenario**: Prepare for tax audit

**Steps**:
1. Create transactions without documents
2. Generate initial audit checklist (shows missing documents)
3. Upload supporting documents
4. Link documents to transactions
5. Generate updated audit checklist (fewer missing documents)
6. Generate audit report with compliance status

**Validates**:
- Audit checklist generation (Requirements 32.1-32.6)
- Document coverage tracking
- Compliance status reporting
- Missing document warnings

---

### 8. What-If Simulation Workflow (`TestWhatIfSimulationWorkflow`)

**Scenario**: Tax optimization through simulation

**Steps**:
1. Create baseline scenario (€60,000 income, €10,000 expenses)
2. Calculate baseline taxes
3. Simulate adding €5,000 equipment purchase
4. Compare tax savings
5. Get optimization suggestions

**Validates**:
- What-if simulation (Requirements 34.4)
- Tax optimization suggestions (Requirements 34.5)
- Savings calculation accuracy

---

### 9. Multi-Language Report Generation (`TestMultiLanguageReportGeneration`)

**Scenario**: Generate reports in all supported languages

**Steps**:
1. Create sample transaction
2. Generate PDF reports in German, English, and Chinese
3. Verify all reports generated successfully

**Validates**:
- Multi-language support (Requirements 33.1-33.6)
- Report generation in all languages
- Language-specific content

---

### 10. Security and Access Control (`TestSecurityAndAccessControl`)

**Scenario**: Verify user data isolation and authentication

**Steps**:
1. Create two users
2. User 1 creates transaction
3. User 2 attempts to access User 1's transaction (should fail)
4. User 2 lists transactions (should be empty)
5. User 1 can access their own transaction
6. Test authentication requirements on protected endpoints

**Validates**:
- User data isolation (Requirements 17.1, 17.2)
- Authentication requirements (Requirements 17.3, 17.4)
- Authorization enforcement
- Security boundaries

---

### 11. Complete System Integration (`TestSystemIntegration`)

**Comprehensive test verifying all major components**:

1. User Management (registration, authentication)
2. Transaction Management (CRUD operations)
3. Tax Calculation (income tax, VAT, SVS)
4. Report Generation (PDF, XML, CSV)
5. Dashboard (data aggregation, analytics)
6. Data Export (GDPR compliance)
7. Audit Features (checklist, compliance)

**Validates**: All core system components working together

---

## Running the Tests

### Run all E2E tests:
```bash
cd backend
pytest tests/integration/test_e2e_user_journeys.py -v
```

### Run specific test class:
```bash
pytest tests/integration/test_e2e_user_journeys.py::TestCompleteTaxFilingWorkflow -v
```

### Run specific test:
```bash
pytest tests/integration/test_e2e_user_journeys.py::TestCompleteTaxFilingWorkflow::test_self_employed_complete_tax_year -v
```

### Run with detailed output:
```bash
pytest tests/integration/test_e2e_user_journeys.py -v -s
```

### Run with coverage:
```bash
pytest tests/integration/test_e2e_user_journeys.py --cov=app --cov-report=html
```

---

## Test Data

All tests use:
- **Tax Year**: 2026
- **Tax Configuration**: 2026 USP rates with 7 tax brackets
- **Test Database**: SQLite in-memory database (isolated per test)
- **Authentication**: JWT tokens with test users

---

## Expected Test Duration

- Individual test: 2-5 seconds
- Full E2E suite: ~60-90 seconds
- With coverage reporting: ~90-120 seconds

---

## Requirements Coverage

These E2E tests validate the following requirement categories:

- **User Management**: 11.1, 11.2, 11.7, 17.3, 17.4, 17.5
- **Transactions**: 1.1-1.7, 2.1-2.6, 9.1-9.4
- **Tax Calculation**: 3.1-3.12, 4.1-4.13, 28.1-28.9
- **Deductions**: 5.1-5.12, 6.1-6.6, 29.1-29.7
- **Reports**: 7.1-7.8, 8.1-8.3, 14.1-14.5, 15.1-15.6
- **OCR**: 19.1-19.9, 20.1-20.5, 21.1-21.6, 22.1-22.6, 23.1-23.5
- **Documents**: 24.1-24.7, 25.1-25.8, 26.1-26.8
- **Multi-year**: 10.1-10.6, 36.1-36.5
- **Employee Refund**: 37.1-37.7
- **Dashboard**: 34.1-34.7
- **Audit**: 32.1-32.6
- **Security**: 17.1-17.11
- **Multi-language**: 33.1-33.6

---

## CI/CD Integration

These E2E tests are run:
- On every pull request
- Before deployment to staging
- Before deployment to production
- As part of nightly test suite
- With full coverage reporting

---

## Maintenance

When adding new features:
1. Add corresponding E2E test scenario
2. Update this documentation
3. Ensure test covers happy path and edge cases
4. Verify test runs in CI/CD pipeline
5. Update requirements coverage list

---

## Troubleshooting

### Test Failures

**Database errors**: Ensure test database is properly isolated
**Authentication errors**: Check JWT token generation and expiration
**OCR errors**: Verify Tesseract is installed and configured
**Timeout errors**: Increase timeout for slow operations

### Common Issues

1. **Import errors**: Run `pip install -r requirements.txt`
2. **Database migration errors**: Run `alembic upgrade head`
3. **Missing test data**: Check fixtures in `conftest.py`
4. **Flaky tests**: Ensure proper test isolation and cleanup

---

## Related Documentation

- [Integration Test README](./README.md)
- [Requirements Document](../../../.kiro/specs/austrian-tax-management-system/requirements.md)
- [Design Document](../../../.kiro/specs/austrian-tax-management-system/design.md)
- [API Documentation](../../docs/api.md)
