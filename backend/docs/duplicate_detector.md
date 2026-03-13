# Duplicate Transaction Detector

## Overview

The `DuplicateDetector` service identifies duplicate transactions based on three criteria:
1. Same transaction date
2. Same amount (exact match)
3. Similar description (>80% similarity using SequenceMatcher)

This helps prevent accidental duplicate entries during manual input or bank import operations.

## Requirements

Validates:
- **Requirement 9.3**: Data validation - Check for duplicate transaction records
- **Requirement 12.9**: Bank import - Detect and filter duplicates during import

## Usage

### Basic Duplicate Check

```python
from app.services.duplicate_detector import DuplicateDetector
from app.db.base import get_db

# Initialize detector
db = next(get_db())
detector = DuplicateDetector(db)

# Check if a transaction is a duplicate
is_duplicate, matching_txn = detector.check_duplicate(
    user_id=1,
    transaction_date=date(2026, 1, 15),
    amount=Decimal('100.00'),
    description="BILLA Supermarket"
)

if is_duplicate:
    print(f"Duplicate found: Transaction ID {matching_txn.id}")
```

### Batch Duplicate Check (for imports)

```python
# Check multiple transactions at once
transactions = [
    {
        'transaction_date': date(2026, 1, 15),
        'amount': Decimal('100.00'),
        'description': 'BILLA Purchase'
    },
    {
        'transaction_date': date(2026, 1, 16),
        'amount': Decimal('50.00'),
        'description': 'SPAR Purchase'
    }
]

results = detector.check_duplicates_batch(
    user_id=1,
    transactions=transactions
)

for result in results:
    if result['is_duplicate']:
        print(f"Duplicate: {result['description']} "
              f"(matches ID {result['duplicate_of_id']}, "
              f"confidence: {result['duplicate_confidence']})")
```

### Find Existing Duplicates

```python
# Find duplicate pairs in existing transactions
duplicates = detector.find_duplicates_in_existing(
    user_id=1,
    limit=10  # Optional: limit results
)

for txn1, txn2, similarity in duplicates:
    print(f"Duplicate pair: {txn1.id} and {txn2.id} "
          f"(similarity: {similarity:.2%})")
```

### Update Scenario (Exclude Current Transaction)

```python
# When updating a transaction, exclude it from duplicate check
is_duplicate, matching_txn = detector.check_duplicate(
    user_id=1,
    transaction_date=date(2026, 1, 15),
    amount=Decimal('100.00'),
    description="Updated description",
    exclude_id=123  # Exclude the transaction being updated
)
```

## Similarity Algorithm

The detector uses Python's `difflib.SequenceMatcher` to calculate description similarity:

- **Threshold**: 80% similarity (configurable via `SIMILARITY_THRESHOLD`)
- **Normalization**: Descriptions are lowercased and whitespace-trimmed
- **Edge cases**:
  - Both `None` → 100% similar (identical)
  - One `None` → 0% similar (completely different)
  - Both empty → 100% similar (identical)
  - One empty → 0% similar (completely different)

### Examples

| Description 1 | Description 2 | Similarity | Duplicate? |
|--------------|---------------|------------|------------|
| "BILLA Supermarket" | "BILLA Supermarket" | 100% | ✅ Yes |
| "SPAR Vienna" | "SPAR Wien" | ~85% | ✅ Yes |
| "BILLA Purchase" | "Office supplies" | ~20% | ❌ No |
| "Test" | "test" | 100% | ✅ Yes (case-insensitive) |
| None | None | 100% | ✅ Yes |
| "Text" | None | 0% | ❌ No |

## Integration with Transaction API

The duplicate detector should be integrated into:

1. **Transaction Creation** (`POST /api/v1/transactions`)
   - Check for duplicates before creating
   - Optionally warn user or prevent creation

2. **Bank Import** (`POST /api/v1/transactions/import`)
   - Use `check_duplicates_batch()` to mark duplicates
   - Allow user to review and decide

3. **Duplicate Management** (future endpoint)
   - `GET /api/v1/transactions/duplicates` - List potential duplicates
   - `POST /api/v1/transactions/merge` - Merge duplicate transactions

## Performance Considerations

- **Database queries**: Uses indexed fields (user_id, transaction_date, amount)
- **Batch processing**: More efficient than individual checks
- **Similarity calculation**: O(n*m) where n and m are description lengths
- **Large datasets**: Consider pagination for `find_duplicates_in_existing()`

## Testing

Comprehensive test coverage in `tests/test_duplicate_detector.py`:

- ✅ Exact duplicate detection
- ✅ Similar description detection (>80%)
- ✅ Different date/amount rejection
- ✅ Dissimilar description rejection
- ✅ None/empty description handling
- ✅ Exclude ID parameter (for updates)
- ✅ Multi-user isolation
- ✅ Batch duplicate checking
- ✅ Finding existing duplicates
- ✅ Similarity calculation edge cases
- ✅ Threshold boundary testing

Run tests:
```bash
pytest tests/test_duplicate_detector.py -v
```

## Future Enhancements

1. **Configurable threshold**: Allow users to adjust similarity threshold
2. **Fuzzy amount matching**: Detect near-duplicates with slightly different amounts
3. **Date range tolerance**: Consider transactions within ±1 day
4. **Machine learning**: Learn from user corrections to improve detection
5. **Bulk operations**: Merge or delete multiple duplicates at once
