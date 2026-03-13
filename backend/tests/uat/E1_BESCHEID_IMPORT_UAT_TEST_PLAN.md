# E1/Bescheid Import with Property Matching - UAT Test Plan

## Overview

This document outlines the User Acceptance Testing plan for E1 Form and Bescheid import functionality with property matching and linking. The goal is to validate that landlords can successfully import their tax documents, have rental income automatically detected, and link transactions to properties with minimal manual effort.

## Test Objectives

1. Validate E1 form import with rental income detection (KZ 350)
2. Verify Bescheid import with property address extraction
3. Test property matching and linking suggestions
4. Validate confidence scoring and auto-link behavior
5. Test manual property selection workflow
6. Verify transaction-property linking accuracy
7. Collect feedback on import workflow usability

## Test Environment

### Setup
- **Environment**: Staging server (staging.taxja.at)
- **Test Data**: Real E1 forms and Bescheid documents (anonymized)
- **Access**: UAT test accounts with pre-registered properties
- **Duration**: 1 week testing period

### Pre-Test Setup
1. Create test accounts with existing properties
2. Prepare sample E1 and Bescheid documents
3. Set up property matching test scenarios
4. Configure feedback collection

## Test Data Preparation

### Sample Properties (Pre-registered)

```python
# Property 1: Exact match scenario
{
    "street": "Hauptstraße 123",
    "city": "Wien",
    "postal_code": "1010",
    "purchase_date": "2020-06-15",
    "purchase_price": 350000.00,
    "building_value": 280000.00
}

# Property 2: Fuzzy match scenario
{
    "street": "Mariahilfer Str. 45",  # Note: abbreviated
    "city": "Wien",
    "postal_code": "1060",
    "purchase_date": "2019-03-01",
    "purchase_price": 420000.00,
    "building_value": 336000.00
}

# Property 3: No match scenario (for new property creation)
# User will import E1 with rental income from a property not yet registered
```

### Sample E1 Forms

#### E1 Form 1: Single Rental Property (Exact Match)
```
Tax Year: 2025
Taxpayer: Max Mustermann
Steuernummer: 12-345/6789

KZ 245 (Employment Income): €45,000
KZ 350 (Rental Income): €14,400
KZ 260 (Werbungskosten): €1,500

Rental Income Details:
- Property: Hauptstraße 123, 1010 Wien
- Monthly Rent: €1,200
- Annual Total: €14,400
```

#### E1 Form 2: Multiple Rental Properties
```
Tax Year: 2025
Taxpayer: Maria Beispiel
Steuernummer: 98-765/4321

KZ 245 (Employment Income): €52,000
KZ 350 (Rental Income): €28,800

Rental Income Details:
- Property 1: Hauptstraße 123, 1010 Wien - €14,400
- Property 2: Mariahilfer Straße 45, 1060 Wien - €14,400
```

#### E1 Form 3: New Property (No Match)
```
Tax Year: 2025
Taxpayer: Johann Neu
Steuernummer: 11-222/3333

KZ 245 (Employment Income): €48,000
KZ 350 (Rental Income): €18,000

Rental Income Details:
- Property: Linzer Straße 78, 5020 Salzburg
```

### Sample Bescheid Documents

#### Bescheid 1: With Property Address (High Confidence Match)
```
EINKOMMENSTEUERBESCHEID 2025
Finanzamt Wien 1/23

Steuerpflichtige/r: Max Mustermann
Steuernummer: 12-345/6789

EINKÜNFTE:
Nichtselbständige Arbeit: €45,000.00
Vermietung und Verpachtung: €14,400.00
  - Hauptstraße 123, 1010 Wien: €14,400.00

FESTGESETZTE EINKOMMENSTEUER: €8,250.00
ABGABENGUTSCHRIFT: €1,200.00
```

#### Bescheid 2: Multiple Properties with Addresses
```
EINKOMMENSTEUERBESCHEID 2025
Finanzamt Wien 1/23

Steuerpflichtige/r: Maria Beispiel
Steuernummer: 98-765/4321

EINKÜNFTE:
Nichtselbständige Arbeit: €52,000.00
Vermietung und Verpachtung: €28,800.00
  - Hauptstraße 123, 1010 Wien: €14,400.00
  - Mariahilfer Str. 45, 1060 Wien: €14,400.00

FESTGESETZTE EINKOMMENSTEUER: €12,500.00
```

#### Bescheid 3: Rental Income Without Address Details
```
EINKOMMENSTEUERBESCHEID 2025
Finanzamt Salzburg

Steuerpflichtige/r: Johann Neu
Steuernummer: 11-222/3333

EINKÜNFTE:
Nichtselbständige Arbeit: €48,000.00
Vermietung und Verpachtung: €18,000.00

FESTGESETZTE EINKOMMENSTEUER: €10,800.00
```

## Test Scenarios

### Scenario 1: E1 Import with Exact Property Match

**Objective**: Test E1 import when property address exactly matches existing property

**Pre-conditions**:
- User has property registered: "Hauptstraße 123, 1010 Wien"
- Property is active status

**Steps**:
1. Log in to staging environment
2. Navigate to Documents → Upload Document
3. Upload E1 Form 1 (PDF or image)
4. Wait for OCR processing
5. Review extracted data preview:
   - Verify KZ 350 (Rental Income) = €14,400
   - Verify taxpayer name and Steuernummer
6. Click "Import Data" button
7. Observe property linking suggestion modal:
   - Should show matched property: "Hauptstraße 123, 1010 Wien"
   - Confidence score should be >0.9 (high confidence)
   - Suggested action: "Auto-link" (recommended)
8. Review match details:
   - Street match: ✓
   - Postal code match: ✓
   - City match: ✓
9. Click "Confirm Auto-Link" button
10. Verify transaction created and linked:
    - Navigate to Transactions page
    - Find rental income transaction (€14,400)
    - Verify property link shows "Hauptstraße 123, 1010 Wien"
11. Navigate to Property Detail page
12. Verify transaction appears in property's transaction list

**Expected Results**:
- ✅ E1 form imported successfully
- ✅ Rental income transaction created (€14,400)
- ✅ Property match detected with high confidence (>0.9)
- ✅ Auto-link suggestion presented
- ✅ Transaction linked to correct property
- ✅ Property detail page shows linked transaction

**Success Criteria**:
- Import completes without errors
- Property matching is accurate
- Confidence score reflects match quality
- User understands auto-link recommendation
- Linking workflow is intuitive

**Feedback Questions**:
- Was the E1 import process clear and easy to follow?
- Did you understand the property matching suggestion?
- Was the confidence score helpful in making your decision?
- Did the auto-link recommendation feel trustworthy?
- Was it clear which property the transaction was linked to?

---

### Scenario 2: E1 Import with Fuzzy Property Match

**Objective**: Test E1 import when property address is similar but not exact

**Pre-conditions**:
- User has property registered: "Mariahilfer Str. 45, 1060 Wien"
- E1 form contains: "Mariahilfer Straße 45, 1060 Wien" (full spelling)

**Steps**:
1. Upload E1 Form 2 (contains multiple properties)
2. Review extracted data
3. Click "Import Data"
4. Observe property linking suggestions for Property 2:
   - Should show matched property: "Mariahilfer Str. 45, 1060 Wien"
   - Confidence score should be 0.7-0.9 (medium confidence)
   - Suggested action: "Suggest" (not auto-link)
5. Review match details:
   - Street match: ✓ (fuzzy match due to "Str." vs "Straße")
   - Postal code match: ✓
   - City match: ✓
6. User options:
   - Option A: "Link to suggested property"
   - Option B: "Select different property"
   - Option C: "Create new property"
7. Select Option A: "Link to suggested property"
8. Verify transaction linked correctly

**Expected Results**:
- ✅ Fuzzy matching detects similar address
- ✅ Confidence score reflects uncertainty (0.7-0.9)
- ✅ Suggestion presented (not auto-link)
- ✅ User has clear options to choose from
- ✅ Manual confirmation required before linking

**Success Criteria**:
- Fuzzy matching works for common abbreviations
- Confidence scoring is accurate
- User understands why auto-link wasn't suggested
- Manual selection workflow is clear

**Feedback Questions**:
- Did you notice the address difference (Str. vs Straße)?
- Was the confidence score appropriate for this match?
- Did you feel comfortable linking to the suggested property?
- Would you have preferred auto-link in this case?

---

### Scenario 3: E1 Import with No Property Match (Create New)

**Objective**: Test E1 import when no matching property exists

**Pre-conditions**:
- User does NOT have property registered for "Linzer Straße 78, 5020 Salzburg"

**Steps**:
1. Upload E1 Form 3
2. Review extracted data
3. Click "Import Data"
4. Observe property linking suggestion:
   - No matching properties found
   - Suggested action: "Create new property"
   - Extracted address displayed: "Linzer Straße 78, 5020 Salzburg"
5. Click "Create New Property" button
6. Property registration form opens with pre-filled data:
   - Street: "Linzer Straße 78"
   - City: "Salzburg"
   - Postal Code: "5020"
7. Fill in remaining required fields:
   - Purchase date
   - Purchase price
   - Building value
8. Submit property registration
9. Verify transaction automatically linked to new property

**Expected Results**:
- ✅ No match detected correctly
- ✅ Create new property option presented
- ✅ Property form pre-filled with extracted address
- ✅ New property created successfully
- ✅ Transaction auto-linked to new property

**Success Criteria**:
- No false positive matches
- Create new property workflow is seamless
- Address pre-filling saves user time
- Transaction linking happens automatically

**Feedback Questions**:
- Was it clear that no matching property was found?
- Did the "Create new property" workflow feel natural?
- Was the address pre-filling helpful?
- Did you expect the transaction to be linked automatically?

---

### Scenario 4: Bescheid Import with High Confidence Match

**Objective**: Test Bescheid import with property address extraction and matching

**Pre-conditions**:
- User has property registered: "Hauptstraße 123, 1010 Wien"

**Steps**:
1. Navigate to Documents → Upload Document
2. Upload Bescheid 1 (PDF)
3. Wait for OCR processing
4. Review extracted data preview:
   - Tax year: 2025
   - Employment income: €45,000
   - Rental income: €14,400
   - Property address: "Hauptstraße 123, 1010 Wien"
5. Click "Import Data"
6. Observe property linking suggestion:
   - Matched property: "Hauptstraße 123, 1010 Wien"
   - Confidence: >0.9 (high)
   - Suggested action: "Auto-link"
   - Match details show all components matched
7. Click "Confirm Auto-Link"
8. Verify transactions created:
   - Employment income: €45,000
   - Rental income: €14,400 (linked to property)
9. Navigate to Property Detail page
10. Verify rental income transaction appears

**Expected Results**:
- ✅ Bescheid imported successfully
- ✅ Property address extracted from document
- ✅ High confidence match detected
- ✅ Auto-link suggested and executed
- ✅ All transactions created correctly

**Success Criteria**:
- Bescheid OCR extraction is accurate
- Property address parsing works
- Matching algorithm performs well
- User trusts auto-link recommendation

**Feedback Questions**:
- Was the Bescheid import process smooth?
- Did you notice the property address was extracted automatically?
- Was the auto-link suggestion appropriate?
- Do you trust the system to auto-link in the future?

---

### Scenario 5: Bescheid Import with Multiple Properties

**Objective**: Test Bescheid import when multiple rental properties are listed

**Pre-conditions**:
- User has two properties registered:
  - "Hauptstraße 123, 1010 Wien"
  - "Mariahilfer Str. 45, 1060 Wien"

**Steps**:
1. Upload Bescheid 2 (contains 2 properties)
2. Review extracted data:
   - Property 1: "Hauptstraße 123, 1010 Wien" - €14,400
   - Property 2: "Mariahilfer Str. 45, 1060 Wien" - €14,400
3. Click "Import Data"
4. Observe property linking suggestions (should show 2 separate suggestions):
   - Suggestion 1: Property 1 → High confidence match
   - Suggestion 2: Property 2 → Medium confidence match (fuzzy)
5. Review and confirm both suggestions
6. Verify two rental income transactions created:
   - Transaction 1: €14,400 → linked to Property 1
   - Transaction 2: €14,400 → linked to Property 2
7. Navigate to each property's detail page
8. Verify each property shows its respective transaction

**Expected Results**:
- ✅ Multiple properties detected in Bescheid
- ✅ Separate transactions created for each property
- ✅ Each transaction matched to correct property
- ✅ Confidence scores reflect match quality
- ✅ User can review and confirm each link separately

**Success Criteria**:
- Multi-property handling works correctly
- No cross-linking errors
- User can distinguish between properties
- Batch confirmation is efficient

**Feedback Questions**:
- Was it clear that multiple properties were detected?
- Could you easily distinguish between the two properties?
- Was the batch confirmation process efficient?
- Would you prefer to confirm all at once or individually?

---

### Scenario 6: Bescheid Import Without Property Addresses

**Objective**: Test Bescheid import when property addresses are not included

**Pre-conditions**:
- User has one or more properties registered
- Bescheid contains rental income but no property addresses

**Steps**:
1. Upload Bescheid 3 (no property addresses)
2. Review extracted data:
   - Rental income: €18,000
   - No property address extracted
3. Click "Import Data"
4. Observe property linking suggestion:
   - No address matching performed
   - All active properties listed for manual selection
   - Suggested action: "Manual select"
5. Select property from dropdown list
6. Click "Link to Selected Property"
7. Verify transaction created and linked

**Expected Results**:
- ✅ Import succeeds even without addresses
- ✅ Manual selection workflow presented
- ✅ All active properties available for selection
- ✅ User can choose correct property
- ✅ Transaction linked successfully

**Success Criteria**:
- Graceful handling of missing address data
- Manual selection is intuitive
- User can identify correct property
- No forced auto-linking without confidence

**Feedback Questions**:
- Was it clear why manual selection was required?
- Could you easily identify the correct property?
- Would additional property details help (e.g., purchase date, address)?
- Was the manual selection process straightforward?

---

### Scenario 7: E1 Import with Manual Property Override

**Objective**: Test user's ability to override auto-link suggestion

**Pre-conditions**:
- User has multiple properties registered
- E1 form suggests auto-link to Property A
- User wants to link to Property B instead

**Steps**:
1. Upload E1 form with rental income
2. Review property linking suggestion:
   - Auto-link suggested to Property A (high confidence)
3. Click "Select Different Property" option
4. Choose Property B from dropdown
5. Click "Link to Selected Property"
6. Verify transaction linked to Property B (not Property A)

**Expected Results**:
- ✅ User can override auto-link suggestion
- ✅ Manual selection option is available
- ✅ Transaction links to user-selected property
- ✅ No errors or warnings

**Success Criteria**:
- Override option is clearly visible
- User has full control over linking
- System respects user's choice
- No confusion about final link

**Feedback Questions**:
- Was it easy to override the auto-link suggestion?
- Did you feel in control of the linking decision?
- Was the manual selection option obvious?
- Would you want a confirmation before overriding?

---

### Scenario 8: Import Validation and Error Handling

**Objective**: Test error handling for invalid or problematic imports

**Test Cases**:

#### 8a: Duplicate Import Detection
1. Upload and import E1 form
2. Attempt to import the same E1 form again
3. Verify system detects duplicate
4. User prompted: "This document appears to be already imported. Continue anyway?"

#### 8b: Rental Income Without Property Link
1. Import E1 with rental income
2. Skip property linking (click "Link Later")
3. Verify transaction created without property_id
4. Navigate to Transactions page
5. Verify transaction shows "Unlinked" status
6. Click "Link to Property" action
7. Complete linking workflow

#### 8c: Invalid Property Address Format
1. Upload Bescheid with malformed address
2. Verify system handles gracefully
3. Manual selection workflow presented

#### 8d: Property Already Linked
1. Import E1 and link to Property A
2. Attempt to link same transaction to Property B
3. Verify system prevents duplicate linking or prompts for confirmation

**Expected Results**:
- ✅ Duplicate detection works
- ✅ Unlinked transactions can be linked later
- ✅ Invalid addresses handled gracefully
- ✅ Duplicate linking prevented or confirmed

---

## Feedback Collection

### In-App Feedback Form

After each import scenario, prompt user with quick feedback:

```
How was your E1/Bescheid import experience?

1. Import Process: ⭐⭐⭐⭐⭐
2. Property Matching Accuracy: ⭐⭐⭐⭐⭐
3. Linking Workflow Clarity: ⭐⭐⭐⭐⭐
4. Confidence in Results: ⭐⭐⭐⭐⭐

Comments (optional):
[Text area]

[Submit Feedback]
```

### Post-Test Survey

Comprehensive survey covering:
- Overall import experience
- Property matching accuracy
- Confidence score usefulness
- Auto-link trust level
- Manual selection ease
- Error handling satisfaction
- Feature requests

### User Interviews

30-minute interviews with participants:
- Screen share import workflow
- Observe decision-making process
- Identify pain points
- Gather improvement suggestions

## Success Metrics

### Quantitative Metrics
- **Import Success Rate**: >95% of imports complete without errors
- **Property Match Accuracy**: >90% of auto-link suggestions are correct
- **User Acceptance Rate**: >80% of users accept auto-link suggestions
- **Time to Complete**: Import + linking <5 minutes
- **Error Rate**: <5% of imports result in errors

### Qualitative Metrics
- Users trust auto-link suggestions
- Users understand confidence scores
- Users feel in control of linking decisions
- Users find workflow intuitive
- Users would use feature for real tax filing

## Test Schedule

### Week 1: Preparation
- Prepare test data (E1 forms, Bescheid documents)
- Set up test accounts with properties
- Configure staging environment
- Recruit test participants

### Week 2: Active Testing
- Participants complete test scenarios
- Monitor feedback and issues
- Quick fixes for critical bugs
- Daily check-ins

### Week 3: Analysis
- Compile feedback
- Analyze metrics
- Conduct user interviews
- Prioritize improvements

## Bug Reporting

### Severity Levels
- **Critical**: Import fails, data loss, incorrect linking
- **High**: Property matching fails, confidence scores wrong
- **Medium**: UI issues, unclear messaging
- **Low**: Cosmetic issues, minor improvements

### Reporting Template
```
**Title**: Brief description
**Scenario**: Which test scenario
**Severity**: Critical/High/Medium/Low
**Steps to Reproduce**:
1. Step 1
2. Step 2
**Expected**: What should happen
**Actual**: What actually happened
**Screenshots**: Attach if applicable
**Document Used**: E1 Form 1 / Bescheid 2 / etc.
```

## Exit Criteria

Testing complete when:
- ✅ All scenarios executed by at least 5 users
- ✅ Import success rate >95%
- ✅ Property match accuracy >90%
- ✅ User satisfaction >4.0/5.0
- ✅ All critical bugs fixed
- ✅ Feedback compiled and analyzed

---

**Document Version**: 1.0  
**Last Updated**: 2026-03-08  
**Status**: Ready for Execution
