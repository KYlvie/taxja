# Property 18: Duplicate Transaction Detection

## Overview

**Validates: Requirements 9.3, 12.9**

This property test suite validates that the duplicate transaction detection system correctly identifies duplicate transactions based on three criteria:
1. Same transaction date
2. Same amount (exact match to 2 decimal places)
3. Similar description (≥80% similarity using SequenceMatcher)

## Property Statement

**Property 18**: The duplicate detection system SHALL correctly identify transactions as duplicates if and only if they have the same date, same amount, and similar descriptions (≥80% similarity), while respecting user isolation and handling edge cases consistently.

## Test Coverage

### 1. Exact Duplicate Detection (`test_exact_duplicate_always_detected`)
**Property**: Transactions with identical date, amount, and description are always detected as duplicates.

**Validates**: Requirement 9.3

**Test Strategy**:
- Generate random transaction data (amount, date, description)
- Create a transaction with this data
- Check for duplicate with exact same data
- Assert: Always returns True (is duplicate)

**Examples**: 100 random test cases

### 2. Similar Description Detection (`test_similar_description_detected_as_duplicate`)
**Property**: Transactions with >80% similar descriptions are detected as duplicates.

**Validates**: Requirement 9.3

**Test Strategy**:
- Generate base description (≥10 characters)
- Create transaction with original description
- Create similar description (change last 2 characters to ensure >80% similarity)
- Check for duplicate
- Assert: If similarity ≥80%, returns True

**Examples**: 100 random test cases

### 3. Different Date Rejection (`test_different_date_not_duplicate`)
**Property**: Transactions with different dates are NOT duplicates, even with same amount and description.

**Validates**: Requirement 9.3

**Test Strategy**:
- Generate two different dates (D1 ≠ D2)
- Create transaction with (D1, amount, description)
- Check for duplicate with (D2, amount, description)
- Assert: Returns False (not duplicate)

**Examples**: 100 random test cases

### 4. Different Amount Rejection (`test_different_amount_not_duplicate`)
**Property**: Transactions with different amounts are NOT duplicates, even with same date and description.

**Validates**: Requirement 9.3

**Test Strategy**:
- Generate two different amounts (A1 ≠ A2)
- Create transaction with (date, A1, description)
- Check for duplicate with (date, A2, description)
- Assert: Returns False (not duplicate)

**Examples**: 100 random test cases

### 5. Dissimilar Description Rejection (`test_dissimilar_description_not_duplicate`)
**Property**: Transactions with dissimilar descriptions (<80% similarity) are NOT duplicates.

**Validates**: Requirement 9.3

**Test Strategy**:
- Generate two descriptions with similarity <80%
- Create transaction with first description
- Check for duplicate with second description
- Assert: Returns False (not duplicate)

**Examples**: 100 random test cases

### 6. Deterministic Detection (`test_duplicate_detection_is_deterministic`)
**Property**: Duplicate detection is deterministic - same input always produces same output.

**Validates**: Requirement 9.3

**Test Strategy**:
- Create a transaction
- Check for duplicate 3 times with same data
- Assert: All 3 checks return identical results

**Examples**: 50 random test cases

### 7. Batch Detection Consistency (`test_batch_duplicate_detection_consistency`)
**Property**: Batch duplicate detection produces same results as individual checks.

**Validates**: Requirement 12.9 (bank import duplicate detection)

**Test Strategy**:
- Create some existing transactions
- Prepare batch of transactions to check
- Run batch check
- Run individual checks for each transaction
- Assert: Batch results match individual results

**Examples**: 50 random test cases

### 8. User Isolation (`test_user_isolation_in_duplicate_detection`)
**Property**: Duplicate detection respects user isolation - transactions from different users are never duplicates.

**Validates**: Requirement 9.3

**Test Strategy**:
- Create transaction for user U1
- Check for duplicate for user U2 with same data
- Assert: Returns False (different users)

**Examples**: 50 random test cases

### 9. None Descriptions Are Duplicates (`test_none_descriptions_are_duplicates`)
**Property**: Transactions with both None descriptions are considered duplicates (if date and amount match).

**Validates**: Requirement 9.3

**Test Strategy**:
- Create transaction with (date, amount, None)
- Check for duplicate with (date, amount, None)
- Assert: Returns True (is duplicate)

**Examples**: 50 random test cases

### 10. One None Description Not Duplicate (`test_one_none_description_not_duplicate`)
**Property**: Transaction with one None and one non-None description are NOT duplicates.

**Validates**: Requirement 9.3

**Test Strategy**:
- Create transaction with (date, amount, description)
- Check for duplicate with (date, amount, None)
- Assert: Returns False (not duplicate)

**Examples**: 50 random test cases

### 11. Exclude ID Prevents Self-Duplicate (`test_exclude_id_prevents_self_duplicate`)
**Property**: Excluding a transaction ID prevents it from being detected as its own duplicate (for update scenarios).

**Validates**: Requirement 9.3 (update scenario)

**Test Strategy**:
- Create transaction T
- Check for duplicate with same data but exclude_id=T.id
- Assert: Returns False (transaction excluded)

**Examples**: 50 random test cases

### 12. Multiple Duplicates Detection (`test_multiple_duplicates_detection`)
**Property**: When multiple duplicates exist, at least one is detected.

**Validates**: Requirement 9.3

**Test Strategy**:
- Create N identical transactions (N ≥ 2)
- Check for duplicate with same data
- Assert: Returns True and matches one of the existing transactions

**Examples**: 30 random test cases

### 13. Decimal Precision (`test_decimal_precision_in_duplicate_detection`)
**Property**: Duplicate detection respects decimal precision (2 places) - amounts that round to same value are duplicates.

**Validates**: Requirement 9.3

**Test Strategy**:
- Create transaction with amount A (quantized to 2 places)
- Check with amount A + 0.001 (rounds to same value)
- Assert: If amounts are same after quantization, returns True

**Examples**: 50 random test cases

### 14. Case-Insensitive Matching (`test_case_insensitive_description_matching`)
**Property**: Description matching is case-insensitive.

**Validates**: Requirement 9.3

**Test Strategy**:
- Create transaction with lowercase description
- Check with uppercase description
- Assert: Returns True (case-insensitive match)

**Examples**: 50 random test cases

## Similarity Algorithm

The duplicate detector uses Python's `difflib.SequenceMatcher` to calculate description similarity:

- **Threshold**: 80% similarity (0.80)
- **Normalization**: Descriptions are lowercased and whitespace-trimmed
- **Edge cases**:
  - Both `None` → 100% similar (identical)
  - One `None` → 0% similar (completely different)
  - Both empty → 100% similar (identical)
  - One empty → 0% similar (completely different)

## Running the Tests

```bash
# Run all property tests
pytest tests/test_duplicate_detection_properties.py -v

# Run with more examples (slower but more thorough)
pytest tests/test_duplicate_detection_properties.py -v --hypothesis-profile=thorough

# Run specific test
pytest tests/test_duplicate_detection_properties.py::TestProperty18DuplicateDetection::test_exact_duplicate_always_detected -v
```

## Test Statistics

- **Total property tests**: 14
- **Total test examples**: ~1,000 (varies by test)
- **Test execution time**: ~3-10 seconds
- **Coverage**: Validates Requirements 9.3 and 12.9

## Key Insights from Property Testing

1. **Determinism**: Duplicate detection is fully deterministic - same input always produces same output
2. **User Isolation**: Transactions from different users are never considered duplicates
3. **Precision Handling**: Decimal amounts are correctly quantized to 2 places before comparison
4. **Case Insensitivity**: Description matching is case-insensitive (using ASCII letters)
5. **Edge Cases**: None and empty descriptions are handled consistently
6. **Batch Consistency**: Batch operations produce identical results to individual checks
7. **Update Safety**: The exclude_id parameter correctly prevents self-duplication during updates

## Related Documentation

- [Duplicate Detector Implementation](./duplicate_detector.md)
- [Unit Tests](../tests/test_duplicate_detector.py)
- [Transaction API](./transaction_api.md)
- [Requirements Document](../../.kiro/specs/austrian-tax-management-system/requirements.md)

## Compliance

✅ **Requirement 9.3**: The Validation_Engine SHALL check for duplicate transaction records
✅ **Requirement 12.9**: The Tax_System SHALL detect and prevent duplicate imports of the same transaction records
