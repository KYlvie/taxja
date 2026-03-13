# Landlord User Acceptance Testing (UAT) Plan

## Overview

This document outlines the User Acceptance Testing plan for the Property Asset Management feature. The goal is to validate that landlords can successfully use the system to manage their rental properties, track depreciation, link transactions, and generate reports.

## Test Objectives

1. Validate property registration workflow
2. Verify transaction linking functionality
3. Test report generation accuracy
4. Collect user feedback on usability and features
5. Identify any bugs or UX issues before production release

## Test Participants

### Target Users
- **Primary**: Landlords with 1-5 rental properties
- **Secondary**: Landlords with 6+ properties (portfolio management)
- **Tertiary**: Mixed-use property owners (rental + personal use)

### Recruitment Criteria
- Austrian taxpayers with rental income
- Currently managing rental properties
- Varying technical proficiency levels
- Mix of new and experienced landlords

### Sample Size
- Minimum 5 landlords
- Recommended 10-15 landlords for comprehensive feedback

## Test Environment

### Setup
- **Environment**: Staging server (staging.taxja.at)
- **Data**: Test accounts with sample data
- **Access**: Temporary credentials provided to participants
- **Duration**: 2-3 weeks testing period

### Pre-Test Setup
1. Create test user accounts for each participant
2. Provide test credentials and access instructions
3. Share user guide and tutorial materials
4. Set up feedback collection mechanisms

## Test Scenarios

### Scenario 1: Property Registration

**Objective**: Test the complete property registration workflow

**Steps**:
1. Navigate to Properties section
2. Click "Add Property" button
3. Fill in property details:
   - Address: Hauptstraße 123, 1010 Wien
   - Purchase date: 2020-06-15
   - Purchase price: €350,000
   - Building value: €280,000 (or let system calculate)
   - Construction year: 1985
4. Review auto-calculated depreciation rate (should be 2%)
5. Submit property registration
6. Verify property appears in property list

**Expected Results**:
- Property successfully created
- Depreciation rate correctly determined (2% for post-1915)
- Building value auto-calculated if not provided (80% of purchase price)
- Property visible in property list with correct details

**Success Criteria**:
- ✅ Property registration completes without errors
- ✅ All fields validate correctly
- ✅ Auto-calculations are accurate
- ✅ User understands the form fields

**Feedback Questions**:
- Was the property registration form easy to understand?
- Were the field labels clear (especially German tax terms)?
- Did you understand what "building value" (Gebäudewert) means?
- Was the auto-calculation of depreciation rate helpful?

---

### Scenario 2: Historical Depreciation Backfill

**Objective**: Test backfilling depreciation for properties purchased in previous years

**Steps**:
1. Register a property with purchase date in 2020
2. Navigate to property detail page
3. Notice "Historical Depreciation Backfill" prompt
4. Click "Preview Backfill" button
5. Review year-by-year depreciation breakdown (2020-2026)
6. Verify total amount to be backfilled
7. Click "Confirm Backfill" button
8. Verify depreciation transactions created for each year

**Expected Results**:
- Preview shows correct depreciation for each year
- First year (2020) is pro-rated based on purchase month
- Subsequent years show full annual depreciation
- Total accumulated depreciation is accurate
- Transactions dated December 31 of each year

**Success Criteria**:
- ✅ Backfill preview displays correctly
- ✅ Amounts are accurate per Austrian tax law
- ✅ User understands what backfill does
- ✅ Transactions created successfully

**Feedback Questions**:
- Did you understand why historical backfill is necessary?
- Was the year-by-year breakdown helpful?
- Were the depreciation amounts what you expected?
- Did the confirmation process feel safe?

---

### Scenario 3: Transaction Linking

**Objective**: Test linking rental income and expenses to properties

**Steps**:
1. Navigate to Transactions page
2. Create a new income transaction:
   - Type: Income
   - Category: Rental Income
   - Amount: €1,200
   - Date: 2026-01-01
   - Description: "January rent - Hauptstraße 123"
3. Link transaction to property (should prompt automatically)
4. Select property from dropdown
5. Verify transaction now shows property link
6. Create expense transactions:
   - Maintenance & Repairs: €500
   - Property Insurance: €150
7. Link expenses to property
8. View property detail page to see all linked transactions

**Expected Results**:
- Rental income prompts for property linking
- Property dropdown shows user's properties
- Linked transactions display property name
- Property detail page shows all linked transactions
- Transactions grouped by category (income, expenses, depreciation)

**Success Criteria**:
- ✅ Transaction linking workflow is intuitive
- ✅ Property selection is easy
- ✅ Linked transactions are clearly indicated
- ✅ Property detail page aggregates correctly

**Feedback Questions**:
- Was it clear which transactions should be linked to properties?
- Was the property selection process easy?
- Could you easily see which transactions are linked to which property?
- Did you find any transactions that should be linkable but weren't?

---

### Scenario 4: Property Metrics and Dashboard

**Objective**: Test property metrics calculation and display

**Steps**:
1. Navigate to property detail page
2. Review Property Metrics section:
   - Accumulated depreciation
   - Remaining depreciable value
   - Years remaining until fully depreciated
   - Rental income YTD
   - Expenses YTD
   - Net income YTD
3. Verify calculations are correct
4. Navigate to Dashboard
5. Review Property Portfolio widget:
   - Total properties count
   - Total building value
   - Total annual depreciation
   - Rental income vs expenses chart

**Expected Results**:
- All metrics calculate correctly
- Accumulated depreciation matches sum of depreciation transactions
- Net income = rental income - expenses
- Dashboard shows portfolio-level aggregations
- Charts display data clearly

**Success Criteria**:
- ✅ Metrics are accurate
- ✅ Calculations match manual verification
- ✅ Dashboard provides useful overview
- ✅ User understands the metrics

**Feedback Questions**:
- Are the property metrics useful for your needs?
- Do you understand what each metric represents?
- Is the dashboard overview helpful?
- What additional metrics would you like to see?

---

### Scenario 5: Report Generation

**Objective**: Test property income statement and depreciation schedule reports

**Steps**:
1. Navigate to property detail page
2. Click "Generate Report" button
3. Select "Property Income Statement"
4. Choose date range: 2026-01-01 to 2026-12-31
5. Generate report
6. Review report contents:
   - Rental income by month
   - Expenses by category
   - Net income calculation
7. Export report to PDF
8. Generate "Depreciation Schedule" report
9. Review depreciation by year
10. Export to CSV

**Expected Results**:
- Reports generate without errors
- Data is accurate and matches transactions
- PDF export is formatted correctly
- CSV export contains all data
- Reports are suitable for tax filing

**Success Criteria**:
- ✅ Reports generate successfully
- ✅ Data accuracy is verified
- ✅ Export formats are usable
- ✅ Reports meet user needs

**Feedback Questions**:
- Are the reports useful for your tax filing?
- Is the report format clear and professional?
- What additional information would you like in reports?
- Would you share these reports with your Steuerberater?

---

### Scenario 6: Multi-Property Management

**Objective**: Test managing multiple properties simultaneously

**Steps**:
1. Register 3 different properties
2. Link transactions to each property
3. View property list with all properties
4. Compare properties using comparison view
5. Filter transactions by property
6. Generate portfolio-level reports

**Expected Results**:
- All properties display correctly in list
- Each property maintains separate transaction links
- Comparison view shows performance differences
- Filtering works correctly
- Portfolio metrics aggregate all properties

**Success Criteria**:
- ✅ Multiple properties managed without confusion
- ✅ Transaction linking doesn't mix properties
- ✅ Comparison features are useful
- ✅ Portfolio view provides value

**Feedback Questions**:
- Is it easy to manage multiple properties?
- Can you quickly identify which property is which?
- Is the comparison feature useful?
- What would make multi-property management easier?

---

### Scenario 7: Property Archival and Deletion

**Objective**: Test archiving sold properties and deleting unused properties

**Steps**:
1. Mark a property as "Sold"
2. Enter sale date
3. Verify property moves to archived list
4. Verify depreciation stops after sale date
5. Attempt to delete property with linked transactions (should fail)
6. Create a new property without transactions
7. Delete the property (should succeed)

**Expected Results**:
- Sold properties can be archived
- Archived properties hidden from active list
- Depreciation stops at sale date
- Cannot delete properties with transactions
- Can delete properties without transactions

**Success Criteria**:
- ✅ Archival workflow is clear
- ✅ Deletion restrictions prevent data loss
- ✅ Historical data is preserved
- ✅ User understands the difference

**Feedback Questions**:
- Was it clear how to archive a sold property?
- Do you understand why properties with transactions can't be deleted?
- Is the archived properties list useful?
- Would you prefer a different archival workflow?

---

## Feedback Collection

### Methods

#### 1. In-App Feedback Form
- Embedded feedback widget in property management pages
- Quick rating (1-5 stars) for each feature
- Optional comment field
- Submit anonymously or with contact info

#### 2. Post-Test Survey
- Comprehensive questionnaire sent after testing period
- Covers all test scenarios
- Usability ratings (System Usability Scale)
- Feature prioritization questions
- Open-ended feedback

#### 3. User Interviews
- 30-minute video calls with willing participants
- Screen sharing to observe workflow
- Deep dive into pain points
- Feature requests and suggestions

#### 4. Analytics Tracking
- Track feature usage patterns
- Identify drop-off points
- Measure time to complete tasks
- Error rate monitoring

### Feedback Categories

#### Usability
- Ease of use (1-5 scale)
- Clarity of labels and instructions
- Navigation intuitiveness
- Visual design and layout

#### Functionality
- Feature completeness
- Accuracy of calculations
- Reliability and stability
- Performance and speed

#### Value
- Usefulness for tax filing
- Time savings vs manual tracking
- Confidence in data accuracy
- Likelihood to recommend

#### Improvements
- Missing features
- Confusing workflows
- Bug reports
- Enhancement suggestions

## Success Metrics

### Quantitative Metrics
- **Task Completion Rate**: >90% of users complete all scenarios
- **Error Rate**: <5% of actions result in errors
- **Time to Complete**: Property registration <3 minutes
- **User Satisfaction**: Average rating >4.0/5.0
- **Feature Adoption**: >80% of users use transaction linking

### Qualitative Metrics
- Users understand Austrian tax terminology
- Users feel confident in calculation accuracy
- Users would use the feature for real tax filing
- Users would recommend to other landlords

## Test Schedule

### Week 1: Preparation
- Recruit test participants
- Set up staging environment
- Create test accounts
- Prepare user guides

### Week 2-3: Active Testing
- Participants complete test scenarios
- Daily monitoring of feedback
- Quick bug fixes for critical issues
- Mid-test check-in with participants

### Week 4: Analysis
- Compile feedback from all sources
- Analyze usage analytics
- Conduct user interviews
- Prioritize improvements

### Week 5: Iteration
- Implement high-priority fixes
- Re-test critical workflows
- Final validation before production

## Bug Reporting

### Severity Levels
- **Critical**: System crash, data loss, security issue
- **High**: Feature unusable, incorrect calculations
- **Medium**: Usability issue, minor bugs
- **Low**: Cosmetic issues, enhancement requests

### Reporting Template
```
**Title**: Brief description
**Severity**: Critical/High/Medium/Low
**Steps to Reproduce**:
1. Step 1
2. Step 2
3. Step 3
**Expected Result**: What should happen
**Actual Result**: What actually happened
**Screenshots**: Attach if applicable
**Browser/Device**: Chrome 120 / Windows 11
**User Account**: test-user-01@taxja.at
```

## Exit Criteria

Testing is complete when:
- ✅ All test scenarios executed by at least 5 users
- ✅ Task completion rate >90%
- ✅ All critical and high severity bugs fixed
- ✅ User satisfaction rating >4.0/5.0
- ✅ Feedback compiled and analyzed
- ✅ Improvement backlog prioritized
- ✅ Product owner approves for production release

## Post-UAT Actions

1. **Bug Fixes**: Address all critical and high severity issues
2. **UX Improvements**: Implement quick wins from feedback
3. **Documentation Updates**: Revise user guide based on confusion points
4. **Training Materials**: Create video tutorials for complex workflows
5. **Production Deployment**: Schedule release after all fixes
6. **User Communication**: Notify beta testers of production launch
7. **Ongoing Support**: Monitor production usage and gather feedback

---

**Document Version**: 1.0  
**Last Updated**: 2026-03-08  
**Status**: Ready for Execution
