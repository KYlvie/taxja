# User Acceptance Testing (UAT) Execution Guide
## Property Asset Management Feature

This guide provides instructions for executing user acceptance testing for the Property Asset Management feature.

## Overview

User Acceptance Testing validates that the feature meets business requirements and works correctly from an end-user perspective. This guide covers both automated UAT tests and manual testing procedures.

## Prerequisites

### Environment Setup

1. **Staging Environment**: Ensure staging environment is deployed and accessible
2. **Test Data**: Clean database with test users
3. **Authentication**: Valid test user credentials
4. **Browser**: Modern browser (Chrome, Firefox, Safari)

### Test Users

Create the following test users:

```sql
-- Landlord with no properties (new user)
INSERT INTO users (email, name, user_type, is_active)
VALUES ('landlord.new@test.com', 'New Landlord', 'landlord', true);

-- Landlord with existing properties
INSERT INTO users (email, name, user_type, is_active)
VALUES ('landlord.existing@test.com', 'Existing Landlord', 'landlord', true);

-- Admin user for testing admin features
INSERT INTO users (email, name, user_type, is_active, is_admin)
VALUES ('admin@test.com', 'Admin User', 'landlord', true, true);
```

## Automated UAT Tests

### Running Automated Tests

```bash
# Navigate to backend directory
cd backend

# Run all UAT tests
pytest tests/uat/test_property_uat.py -v

# Run specific test class
pytest tests/uat/test_property_uat.py::TestPropertyRegistrationUAT -v

# Run with coverage
pytest tests/uat/test_property_uat.py --cov=app.services --cov=app.api

# Generate HTML coverage report
pytest tests/uat/test_property_uat.py --cov=app --cov-report=html
```

### Expected Results

All automated tests should pass:

- ✓ UAT-1.1: Property registration
- ✓ UAT-1.2: Property list view
- ✓ UAT-1.3: Property editing
- ✓ UAT-2.1: Depreciation calculation
- ✓ UAT-2.2: Pro-rated depreciation
- ✓ UAT-2.3: Historical backfill
- ✓ UAT-3.1: Transaction linking
- ✓ UAT-3.2: Property transactions view
- ✓ UAT-5.1: Income statement report
- ✓ UAT-6.1: Portfolio metrics
- ✓ UAT-7.1: Performance with 100 properties

## Manual UAT Test Cases

### Test Case 1: New Landlord Onboarding

**Objective**: Verify a new landlord can register their first property

**Steps**:
1. Log in as `landlord.new@test.com`
2. Navigate to Properties page
3. Click "Add Property" button
4. Fill in property details:
   - Street: "Hauptstraße 123"
   - City: "Wien"
   - Postal Code: "1010"
   - Purchase Date: "2020-06-15"
   - Purchase Price: "350,000 EUR"
   - Construction Year: "1985"
5. Observe auto-calculated fields:
   - Building Value: Should show "280,000 EUR" (80%)
   - Land Value: Should show "70,000 EUR"
   - Depreciation Rate: Should show "2.0%"
6. Click "Save Property"

**Expected Results**:
- Property created successfully
- Success notification displayed
- Property appears in property list
- All calculated fields are correct

**Pass/Fail**: ___________

---

### Test Case 2: Historical Depreciation Backfill

**Objective**: Verify historical depreciation backfill for property purchased in previous years

**Steps**:
1. Log in as `landlord.new@test.com`
2. Navigate to property created in Test Case 1
3. System should display notice: "This property needs historical depreciation backfill"
4. Click "Preview Backfill" button
5. Review preview showing years 2020-2025
6. Verify total amount: 28,800 EUR (4,800 * 6 years)
7. Click "Confirm Backfill"
8. Wait for processing
9. Navigate to Transactions tab

**Expected Results**:
- Preview shows 6 years of depreciation
- Total amount is correct
- Backfill completes successfully
- 6 depreciation transactions created (one per year)
- Each transaction dated December 31
- Transactions marked as "System Generated"

**Pass/Fail**: ___________

---

### Test Case 3: Link Rental Income to Property

**Objective**: Verify linking rental income transactions to properties

**Steps**:
1. Log in as `landlord.existing@test.com`
2. Navigate to Transactions page
3. Create new income transaction:
   - Type: Income
   - Amount: "1,200 EUR"
   - Date: "2025-01-01"
   - Description: "Miete Januar 2025"
   - Category: "Rental Income"
4. Click "Link to Property"
5. Select property from dropdown
6. Click "Save"
7. Navigate to property details
8. View Transactions tab

**Expected Results**:
- Transaction successfully linked
- Transaction appears in property's transaction list
- Property metrics updated (rental income YTD)

**Pass/Fail**: ___________

---

### Test Case 4: Generate Property Income Statement

**Objective**: Verify property income statement report generation

**Steps**:
1. Log in as `landlord.existing@test.com`
2. Navigate to property with transactions
3. Click "Reports" tab
4. Select "Income Statement"
5. Select year: "2025"
6. Click "Generate Report"
7. Review report sections:
   - Rental Income
   - Expenses by Category
   - Net Income
8. Click "Export to PDF"

**Expected Results**:
- Report generates successfully
- All sections display correct data
- Income and expenses match transactions
- Net income calculated correctly
- PDF export works

**Pass/Fail**: ___________

---

### Test Case 5: Multi-Property Portfolio View

**Objective**: Verify portfolio dashboard with multiple properties

**Steps**:
1. Log in as `landlord.existing@test.com`
2. Ensure user has at least 3 properties
3. Navigate to Portfolio Dashboard
4. Review metrics:
   - Total Properties
   - Total Building Value
   - Total Annual Depreciation
   - Total Rental Income YTD
   - Total Expenses YTD
   - Net Income YTD
5. View property comparison chart
6. Sort properties by net income

**Expected Results**:
- All metrics display correctly
- Aggregated values are accurate
- Comparison chart renders
- Sorting works correctly

**Pass/Fail**: ___________

---

### Test Case 6: Property Archival

**Objective**: Verify archiving sold properties

**Steps**:
1. Log in as `landlord.existing@test.com`
2. Navigate to a property
3. Click "Archive Property"
4. Enter sale date: "2025-12-31"
5. Confirm archival
6. Navigate to Properties list
7. Verify property not in active list
8. Toggle "Show Archived"
9. Verify property appears in archived list

**Expected Results**:
- Property archived successfully
- Property removed from active list
- Property visible in archived list
- No new depreciation generated after sale date

**Pass/Fail**: ___________

---

### Test Case 7: Mixed-Use Property

**Objective**: Verify mixed-use property depreciation calculation

**Steps**:
1. Log in as `landlord.new@test.com`
2. Create new property:
   - Property Type: "Mixed-Use"
   - Rental Percentage: "50%"
   - Purchase Price: "400,000 EUR"
   - Building Value: "320,000 EUR"
   - Depreciation Rate: "2.0%"
3. Save property
4. Generate annual depreciation
5. Verify depreciation amount

**Expected Results**:
- Property created with mixed-use type
- Annual depreciation: 3,200 EUR (320,000 * 0.02 * 0.5)
- Only rental portion depreciated

**Pass/Fail**: ___________

---

### Test Case 8: Performance with Large Portfolio

**Objective**: Verify system performance with many properties

**Steps**:
1. Log in as admin user
2. Use admin script to create 100 test properties
3. Navigate to Properties list
4. Measure page load time
5. Filter properties by status
6. Search for specific property
7. Generate portfolio report

**Expected Results**:
- Property list loads in < 1 second
- Filtering works smoothly
- Search returns results quickly
- Portfolio report generates in < 5 seconds

**Pass/Fail**: ___________

---

### Test Case 9: E1 Import Integration (If Available)

**Objective**: Verify E1 import suggests property linking

**Steps**:
1. Log in as `landlord.existing@test.com`
2. Navigate to Documents > Import E1
3. Upload E1 form with rental income (KZ 350)
4. Wait for processing
5. Review property linking suggestions
6. Select suggested property or create new
7. Confirm linking

**Expected Results**:
- E1 import completes successfully
- Rental income extracted correctly
- Property suggestions displayed
- Linking works correctly

**Pass/Fail**: ___________

---

### Test Case 10: Mobile Responsiveness

**Objective**: Verify property management works on mobile devices

**Steps**:
1. Open application on mobile device or use browser dev tools
2. Log in as landlord
3. Navigate to Properties page
4. View property list
5. Open property details
6. Create new property
7. Link transaction to property

**Expected Results**:
- All pages render correctly on mobile
- Forms are usable on small screens
- Navigation works smoothly
- No horizontal scrolling required

**Pass/Fail**: ___________

---

## UAT Acceptance Criteria

### Critical Issues (Must Fix Before Production)

- [ ] Property registration fails
- [ ] Depreciation calculations incorrect
- [ ] Data loss or corruption
- [ ] Security vulnerabilities
- [ ] Performance < 1 second for property list

### Major Issues (Should Fix Before Production)

- [ ] UI/UX issues affecting usability
- [ ] Missing validation errors
- [ ] Incorrect error messages
- [ ] Report generation failures
- [ ] Mobile responsiveness issues

### Minor Issues (Can Fix Post-Production)

- [ ] Cosmetic UI issues
- [ ] Non-critical validation messages
- [ ] Optional feature enhancements
- [ ] Performance optimizations

## UAT Sign-Off

### Test Execution Summary

| Test Case | Status | Notes |
|-----------|--------|-------|
| TC-1: New Landlord Onboarding | ☐ Pass ☐ Fail | |
| TC-2: Historical Backfill | ☐ Pass ☐ Fail | |
| TC-3: Transaction Linking | ☐ Pass ☐ Fail | |
| TC-4: Income Statement | ☐ Pass ☐ Fail | |
| TC-5: Portfolio View | ☐ Pass ☐ Fail | |
| TC-6: Property Archival | ☐ Pass ☐ Fail | |
| TC-7: Mixed-Use Property | ☐ Pass ☐ Fail | |
| TC-8: Performance Test | ☐ Pass ☐ Fail | |
| TC-9: E1 Integration | ☐ Pass ☐ Fail | |
| TC-10: Mobile Responsive | ☐ Pass ☐ Fail | |

### Overall Assessment

**Total Tests**: 10  
**Passed**: _____  
**Failed**: _____  
**Pass Rate**: _____%

### Recommendation

☐ **Approved for Production**: All critical and major issues resolved  
☐ **Conditional Approval**: Minor issues documented, can be fixed post-production  
☐ **Not Approved**: Critical or major issues require resolution

### Sign-Off

**Product Owner**: _________________ Date: _________

**QA Lead**: _________________ Date: _________

**Technical Lead**: _________________ Date: _________

## Troubleshooting

### Common Issues

**Issue**: Property list not loading  
**Solution**: Check database connection, verify user authentication

**Issue**: Depreciation calculation incorrect  
**Solution**: Verify construction_year and depreciation_rate, check AfACalculator logic

**Issue**: Backfill fails  
**Solution**: Check for existing depreciation transactions, verify date ranges

**Issue**: Reports not generating  
**Solution**: Verify transactions exist for selected period, check report service logs

## Additional Resources

- [Property Asset Management Design Document](../../.kiro/specs/property-asset-management/design.md)
- [Property Asset Management Requirements](../../.kiro/specs/property-asset-management/requirements.md)
- [API Documentation](../../backend/docs/api/properties.md)
- [Staging Deployment Guide](../../STAGING_DEPLOYMENT_GUIDE.md)

## Contact

For UAT support or questions:
- Technical Issues: dev-team@taxja.com
- Business Questions: product@taxja.com
- UAT Coordination: qa@taxja.com
