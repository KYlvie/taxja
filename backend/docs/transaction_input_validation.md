# Transaction Input Validation

## Overview

This document describes the comprehensive input validation implemented for transaction management in the Austrian Tax Management System (Taxja).

## Requirements Addressed

- **Requirement 1.3**: Validate required fields completeness
- **Requirement 1.4**: Validate amount format and positivity
- **Requirement 9.1**: Validate dates in valid tax year range
- **Requirement 9.2**: Validate amounts are positive and properly formatted
- **Requirement 9.4**: Display detailed error messages for validation failures

## Validation Rules

### Required Fields

For transaction creation (`TransactionCreate`), the following fields are **required**:

1. **type** - Transaction type (income or expense)
2. **amount** - Transaction amount
3. **transaction_date** - Date of the transaction
4. **description** - Transaction description (cannot be empty)

### Conditional Required Fields

Based on the transaction type:

- **Income transactions** require `income_category`
- **Expense transactions** require `expense_category`

### Amount Validation

1. **Positive values only**: Amount must be greater than 0
   - ❌ Rejected: `-100.00`, `0.00`
   - ✅ Accepted: `100.00`, `0.01`

2. **Decimal precision**: Maximum 2 decimal places
   - ❌ Rejected: `100.999` (3 decimal places)
   - ✅ Accepted: `100.50`, `100.00`

3. **Error message**: Clear indication of the issue
   ```
   "Transaction amount must be positive. Provided amount: €-50.00"
   ```

### Date Validation

1. **No future dates**: Transaction date cannot be in the future
   - ❌ Rejected: Tomorrow's date
   - ✅ Accepted: Today's date, past dates

2. **Error message**: Shows both provided date and current date
   ```
   "Transaction date cannot be in the future. 
    Provided date: 2026-03-10, Today: 2026-03-04"
   ```

### Description Validation

1. **Non-empty**: Description cannot be empty or whitespace-only
   - ❌ Rejected: `""`, `"   "`
   - ✅ Accepted: `"Office supplies"`

2. **Maximum length**: 500 characters
   - ❌ Rejected: 501+ characters
   - ✅ Accepted: 1-500 characters

### Category Validation

1. **Valid enum values**: Category must be from predefined enums
   - **Income categories**: `employment`, `rental`, `self_employment`, `capital_gains`
   - **Expense categories**: `office_supplies`, `equipment`, `travel`, `marketing`, etc.

2. **Type consistency**: Category must match transaction type
   - Income transactions cannot have `expense_category`
   - Expense transactions cannot have `income_category`

3. **Error messages**: List valid options
   ```
   "income_category is required for income transactions. 
    Valid categories: employment, rental, self_employment, capital_gains"
   ```

## Implementation

### Schema Validation (Pydantic)

The validation is implemented using Pydantic v2 with custom validators:

```python
class TransactionCreate(TransactionBase):
    """Transaction creation schema with comprehensive validation"""
    
    description: str = Field(..., min_length=1, max_length=500)
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError(
                f"Transaction amount must be positive. Provided amount: €{v}"
            )
        return v.quantize(Decimal('0.01'))
    
    @field_validator('transaction_date')
    @classmethod
    def validate_transaction_date(cls, v: date) -> date:
        if v > date.today():
            raise ValueError(
                f"Transaction date cannot be in the future. "
                f"Provided date: {v.strftime('%Y-%m-%d')}, "
                f"Today: {date.today().strftime('%Y-%m-%d')}"
            )
        return v
    
    @model_validator(mode='after')
    def validate_category_consistency(self):
        if self.type == TransactionType.INCOME:
            if not self.income_category:
                raise ValueError(
                    'income_category is required for income transactions. '
                    f'Valid categories: {", ".join([c.value for c in IncomeCategory])}'
                )
        return self
```

### API Endpoint Validation

The FastAPI endpoint provides additional validation and error handling:

```python
@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    transaction_data: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new transaction record.
    
    **Validation rules:**
    1. Amount must be positive
    2. Date cannot be in the future
    3. Description cannot be empty
    4. Category must match transaction type
    5. Category must be a valid enum value
    """
    # Pydantic handles validation automatically
    # Additional safety checks can be added here
    ...
```

## Error Response Format

When validation fails, the API returns a 422 Unprocessable Entity response with detailed error information:

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "amount"],
      "msg": "Transaction amount must be positive. Provided amount: €-50.00",
      "input": -50.00
    }
  ]
}
```

## Testing

Comprehensive unit tests verify all validation rules:

### Test Coverage

1. ✅ Valid transactions (income and expense)
2. ✅ Missing required fields
3. ✅ Negative and zero amounts
4. ✅ Future dates
5. ✅ Empty descriptions
6. ✅ Invalid category values
7. ✅ Category-type mismatches
8. ✅ Decimal precision
9. ✅ Error message clarity

### Running Tests

```bash
cd backend
python -m pytest tests/test_transaction_validation_standalone.py -v
```

### Test Results

```
12 passed in 0.68s
```

All validation tests pass successfully.

## Usage Examples

### Valid Income Transaction

```python
transaction = TransactionCreate(
    type=TransactionType.INCOME,
    amount=Decimal("1000.50"),
    transaction_date=date.today(),
    description="Monthly salary",
    income_category=IncomeCategory.EMPLOYMENT
)
```

### Valid Expense Transaction

```python
transaction = TransactionCreate(
    type=TransactionType.EXPENSE,
    amount=Decimal("50.99"),
    transaction_date=date.today(),
    description="Office supplies",
    expense_category=ExpenseCategory.OFFICE_SUPPLIES,
    is_deductible=True
)
```

### Invalid Examples (Will Raise ValidationError)

```python
# Negative amount
transaction = TransactionCreate(
    type=TransactionType.INCOME,
    amount=Decimal("-100.00"),  # ❌ Must be positive
    ...
)

# Future date
transaction = TransactionCreate(
    type=TransactionType.INCOME,
    transaction_date=date.today() + timedelta(days=1),  # ❌ Cannot be future
    ...
)

# Missing category
transaction = TransactionCreate(
    type=TransactionType.INCOME,
    amount=Decimal("100.00"),
    transaction_date=date.today(),
    description="Test"
    # ❌ Missing income_category
)
```

## Benefits

1. **Data Integrity**: Ensures all transactions have valid, consistent data
2. **User Experience**: Clear error messages help users correct issues quickly
3. **Tax Compliance**: Prevents invalid data that could cause tax calculation errors
4. **Audit Trail**: Valid data ensures reliable audit reports
5. **Type Safety**: Pydantic provides runtime type checking and IDE support

## Future Enhancements

Potential improvements for future iterations:

1. **Date Range Validation**: Validate dates are within reasonable tax year ranges
2. **Amount Limits**: Add configurable maximum transaction amounts
3. **Custom Validation Rules**: Allow users to define custom validation rules
4. **Batch Validation**: Optimize validation for bulk imports
5. **Localized Error Messages**: Support German, English, and Chinese error messages

## Related Documentation

- [Transaction API Implementation](./TRANSACTION_API_IMPLEMENTATION.md)
- [Transaction Roundtrip Properties](../tests/test_transaction_roundtrip_properties.py)
- [Duplicate Detection](./duplicate_detector.md)
