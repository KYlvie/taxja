# Multi-Year Data Isolation

## Overview

Multi-year data isolation ensures that transactions are properly filtered by tax year, respecting year boundaries for accurate tax calculations and reporting.

## Requirements

This implementation satisfies the following requirements:

- **Requirement 10.1**: THE Tax_System SHALL 允许用户在不同 Tax_Year 之间切换
- **Requirement 10.2**: THE Tax_System SHALL 为每个 Tax_Year 独立存储交易记录和税务计算结果

## Implementation

### API Endpoint

The `GET /api/v1/transactions` endpoint now supports a `tax_year` query parameter:

```http
GET /api/v1/transactions?tax_year=2026
```

### Query Parameter

- **tax_year** (optional): Integer value representing the tax year (e.g., 2026)
  - Valid range: 1900 to 2100
  - When specified, only transactions within that calendar year are returned
  - Year boundaries: January 1 to December 31 of the specified year

### Year Boundary Logic

When `tax_year` is specified, the system applies the following filters:

```python
year_start = date(tax_year, 1, 1)
year_end = date(tax_year, 12, 31)

query = query.filter(
    Transaction.transaction_date >= year_start,
    Transaction.transaction_date <= year_end
)
```

This ensures:
- Transactions on January 1 are included in that year
- Transactions on December 31 are included in that year
- No cross-year contamination occurs

## Usage Examples

### Filter by Tax Year

```python
# Get all transactions for 2026
response = client.get(
    "/api/v1/transactions",
    params={"tax_year": 2026}
)
```

### Combine with Other Filters

```python
# Get income transactions for 2025
response = client.get(
    "/api/v1/transactions",
    params={
        "tax_year": 2025,
        "type": "income"
    }
)
```

### Calculate Year Totals

```python
# Get all 2026 transactions
transactions = client.get(
    "/api/v1/transactions",
    params={"tax_year": 2026}
).json()["transactions"]

# Calculate totals
total_income = sum(
    Decimal(txn["amount"]) 
    for txn in transactions 
    if txn["type"] == "income"
)

total_expenses = sum(
    Decimal(txn["amount"]) 
    for txn in transactions 
    if txn["type"] == "expense"
)

net_income = total_income - total_expenses
```

## Benefits

1. **Accurate Tax Calculations**: Each tax year's data is isolated, ensuring calculations use only relevant transactions
2. **Historical Analysis**: Users can easily view and compare data across different tax years
3. **Compliance**: Proper year boundaries ensure compliance with Austrian tax law requirements
4. **Performance**: Filtering by year reduces the dataset size for faster queries

## Testing

Comprehensive tests have been created to verify:

1. **Year Filtering**: Transactions are correctly filtered by tax year
2. **Boundary Respect**: Year boundaries (Jan 1 and Dec 31) are properly respected
3. **No Cross-Contamination**: Filtering one year doesn't include transactions from other years
4. **Empty Results**: Querying years with no transactions returns empty results
5. **User Isolation**: Year filtering respects user isolation
6. **Integration with Other Filters**: Tax year works correctly with other query parameters
7. **Pagination and Sorting**: Tax year filtering works with pagination and sorting

## Future Enhancements

Potential future improvements:

1. **Automatic Year Selection**: Default to current tax year if not specified
2. **Year Switching UI**: Frontend component for easy year switching
3. **Year Comparison**: Side-by-side comparison of multiple years
4. **Year-End Rollover**: Automatic handling of year-end transitions
5. **Multi-Year Reports**: Generate reports spanning multiple years

## Related Documentation

- [Transaction API Documentation](../TRANSACTION_API_IMPLEMENTATION.md)
- [Requirements Document](../../.kiro/specs/austrian-tax-management-system/requirements.md)
- [Design Document](../../.kiro/specs/austrian-tax-management-system/design.md)
