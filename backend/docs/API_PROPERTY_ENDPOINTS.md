# Property Management API Documentation

## Overview

This document provides comprehensive documentation for all property management API endpoints in the Taxja platform. These endpoints enable landlords to manage rental properties, calculate depreciation (AfA), link transactions, and generate reports.

**Base URL:** `/api/v1/properties`

**Authentication:** All endpoints require JWT authentication via Bearer token in the `Authorization` header.

**Content-Type:** `application/json` (except for file exports which return PDF/CSV)

---

## Table of Contents

1. [Authentication](#authentication)
2. [Error Codes](#error-codes)
3. [Property Management Endpoints](#property-management-endpoints)
4. [Transaction Linking Endpoints](#transaction-linking-endpoints)
5. [Historical Depreciation Endpoints](#historical-depreciation-endpoints)
6. [Annual Depreciation Endpoints](#annual-depreciation-endpoints)
7. [Report Generation Endpoints](#report-generation-endpoints)
8. [Portfolio Management Endpoints](#portfolio-management-endpoints)
9. [Bulk Operations Endpoints](#bulk-operations-endpoints)
10. [Data Models](#data-models)

---

## Authentication

All API endpoints require authentication using JWT Bearer tokens.

**Header Format:**
```
Authorization: Bearer <your_jwt_token>
```

**Obtaining a Token:**
```bash
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "your_password"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

---

## Error Codes


### Standard HTTP Status Codes

| Status Code | Description | Common Causes |
|-------------|-------------|---------------|
| 200 OK | Request successful | GET, PUT requests completed successfully |
| 201 Created | Resource created | POST request created new property |
| 204 No Content | Deletion successful | DELETE request completed |
| 400 Bad Request | Invalid request data | Validation errors, invalid parameters |
| 401 Unauthorized | Authentication required | Missing or invalid JWT token |
| 403 Forbidden | Access denied | User doesn't own the resource |
| 404 Not Found | Resource not found | Property or transaction doesn't exist |
| 409 Conflict | Resource conflict | Duplicate depreciation transaction |
| 500 Internal Server Error | Server error | Database error, unexpected exception |
| 501 Not Implemented | Feature not available | Endpoint under development |

### Property-Specific Error Responses

**Validation Error (400):**
```json
{
  "detail": [
    {
      "loc": ["body", "purchase_price"],
      "msg": "purchase_price must be greater than 0",
      "type": "value_error"
    }
  ]
}
```

**Not Found Error (404):**
```json
{
  "detail": "Property 550e8400-e29b-41d4-a716-446655440000 not found"
}
```

**Permission Error (403):**
```json
{
  "detail": "Property does not belong to user"
}
```

**Conflict Error (409):**
```json
{
  "detail": "Depreciation already exists for property and year 2026"
}
```

---

## Property Management Endpoints

### 1. Create Property

Create a new rental property with automatic calculations for building value and depreciation rate.

**Endpoint:** `POST /api/v1/properties`

**Authentication:** Required

**Request Body:**
```json
{
  "property_type": "rental",
  "rental_percentage": 100.0,
  "street": "Hauptstraße 123",
  "city": "Wien",
  "postal_code": "1010",
  "purchase_date": "2020-06-15",
  "purchase_price": 350000.00,
  "building_value": 280000.00,
  "construction_year": 1985,
  "depreciation_rate": 0.02,
  "grunderwerbsteuer": 10500.00,
  "notary_fees": 2500.00,
  "registry_fees": 1200.00
}
```

**Required Fields:**
- `street` (string): Street address
- `city` (string): City name
- `postal_code` (string): Postal code
- `purchase_date` (date): Property purchase date (YYYY-MM-DD format, cannot be in future)
- `purchase_price` (decimal): Total purchase price (must be > 0 and <= €100,000,000)

**Optional Fields:**
- `property_type` (enum): "rental" (default), "owner_occupied", or "mixed_use"
- `rental_percentage` (decimal): Percentage used for rental (0-100, default: 100 for rental properties)
- `building_value` (decimal): Depreciable building value (default: 80% of purchase_price)
- `construction_year` (integer): Year of construction (affects depreciation rate, 1800-current year)
- `depreciation_rate` (decimal): Annual depreciation rate (0.001-0.10, default: auto-calculated)
- `grunderwerbsteuer` (decimal): Property transfer tax paid
- `notary_fees` (decimal): Notary fees paid
- `registry_fees` (decimal): Land registry fees (Eintragungsgebühr)

**Auto-Calculations:**
- `building_value` = 80% of `purchase_price` if not provided
- `depreciation_rate` = 1.5% for buildings constructed before 1915, 2.0% for 1915 or later
- `land_value` = `purchase_price` - `building_value`
- `address` = "{street}, {postal_code} {city}"

**Response (201 Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": 123,
  "property_type": "rental",
  "rental_percentage": 100.0,
  "address": "Hauptstraße 123, 1010 Wien",
  "street": "Hauptstraße 123",
  "city": "Wien",
  "postal_code": "1010",
  "purchase_date": "2020-06-15",
  "purchase_price": 350000.00,
  "building_value": 280000.00,
  "land_value": 70000.00,
  "construction_year": 1985,
  "depreciation_rate": 0.02,
  "status": "active",
  "sale_date": null,
  "grunderwerbsteuer": 10500.00,
  "notary_fees": 2500.00,
  "registry_fees": 1200.00,
  "created_at": "2026-03-07T10:30:00Z",
  "updated_at": "2026-03-07T10:30:00Z"
}
```

**Validation Rules:**
- `purchase_price` must be > 0 and <= €100,000,000
- `building_value` must be > 0 and <= `purchase_price`
- `purchase_date` cannot be in the future
- `construction_year` must be between 1800 and current year
- `depreciation_rate` must be between 0.1% and 10%
- `rental_percentage` must be between 0 and 100

**Example cURL:**
```bash
curl -X POST "https://api.taxja.com/api/v1/properties" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "street": "Hauptstraße 123",
    "city": "Wien",
    "postal_code": "1010",
    "purchase_date": "2020-06-15",
    "purchase_price": 350000.00,
    "construction_year": 1985
  }'
```

---

### 2. List Properties

Retrieve all properties owned by the authenticated user.

**Endpoint:** `GET /api/v1/properties`

**Authentication:** Required

**Query Parameters:**
- `include_archived` (boolean, optional): Include archived/sold properties (default: false)

**Response (200 OK):**
```json
{
  "total": 2,
  "include_archived": false,
  "properties": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "address": "Hauptstraße 123, 1010 Wien",
      "purchase_date": "2020-06-15",
      "purchase_price": 350000.00,
      "building_value": 280000.00,
      "depreciation_rate": 0.02,
      "status": "active",
      "property_type": "rental"
    },
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "address": "Mariahilfer Straße 45, 1060 Wien",
      "purchase_date": "2018-03-20",
      "purchase_price": 420000.00,
      "building_value": 336000.00,
      "depreciation_rate": 0.02,
      "status": "active",
      "property_type": "rental"
    }
  ]
}
```

**Example cURL:**
```bash
curl -X GET "https://api.taxja.com/api/v1/properties?include_archived=false" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

### 3. Get Property Details

Retrieve detailed information about a specific property, including optional financial metrics.

**Endpoint:** `GET /api/v1/properties/{property_id}`

**Authentication:** Required

**Path Parameters:**
- `property_id` (UUID, required): UUID of the property

**Query Parameters:**
- `include_metrics` (boolean, optional): Include financial metrics (default: true)
- `year` (integer, optional): Year for metrics calculation (default: current year)

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": 123,
  "property_type": "rental",
  "rental_percentage": 100.0,
  "address": "Hauptstraße 123, 1010 Wien",
  "street": "Hauptstraße 123",
  "city": "Wien",
  "postal_code": "1010",
  "purchase_date": "2020-06-15",
  "purchase_price": 350000.00,
  "building_value": 280000.00,
  "land_value": 70000.00,
  "construction_year": 1985,
  "depreciation_rate": 0.02,
  "status": "active",
  "sale_date": null,
  "metrics": {
    "accumulated_depreciation": 33600.00,
    "remaining_depreciable_value": 246400.00,
    "annual_depreciation": 5600.00,
    "total_rental_income": 18000.00,
    "total_expenses": 8200.00,
    "net_rental_income": 9800.00,
    "years_remaining": 44
  }
}
```

**Metrics Explanation:**
- `accumulated_depreciation`: Total depreciation claimed to date
- `remaining_depreciable_value`: Building value minus accumulated depreciation
- `annual_depreciation`: Depreciation amount for the specified year
- `total_rental_income`: Total rental income for the specified year
- `total_expenses`: Total expenses (including depreciation) for the specified year
- `net_rental_income`: Rental income minus expenses
- `years_remaining`: Estimated years until fully depreciated

**Example cURL:**
```bash
curl -X GET "https://api.taxja.com/api/v1/properties/550e8400-e29b-41d4-a716-446655440000?include_metrics=true&year=2026" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

### 4. Update Property

Update an existing property. Note that `purchase_date` and `purchase_price` are immutable and cannot be changed.

**Endpoint:** `PUT /api/v1/properties/{property_id}`

**Authentication:** Required

**Path Parameters:**
- `property_id` (UUID, required): UUID of the property to update

**Request Body (all fields optional):**
```json
{
  "property_type": "mixed_use",
  "rental_percentage": 50.0,
  "street": "Hauptstraße 123A",
  "city": "Wien",
  "postal_code": "1010",
  "building_value": 285000.00,
  "construction_year": 1980,
  "depreciation_rate": 0.025,
  "status": "active",
  "sale_date": null,
  "grunderwerbsteuer": 10500.00,
  "notary_fees": 2500.00,
  "registry_fees": 1200.00
}
```

**Updatable Fields:**
- `property_type`, `rental_percentage`
- `street`, `city`, `postal_code`
- `building_value`, `construction_year`, `depreciation_rate`
- `grunderwerbsteuer`, `notary_fees`, `registry_fees`
- `status`, `sale_date`

**Immutable Fields (cannot be updated):**
- `purchase_date`
- `purchase_price`

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": 123,
  "property_type": "mixed_use",
  "rental_percentage": 50.0,
  "address": "Hauptstraße 123A, 1010 Wien",
  "purchase_date": "2020-06-15",
  "purchase_price": 350000.00,
  "building_value": 285000.00,
  "construction_year": 1980,
  "depreciation_rate": 0.025,
  "status": "active",
  "updated_at": "2026-03-07T11:45:00Z"
}
```

**Example cURL:**
```bash
curl -X PUT "https://api.taxja.com/api/v1/properties/550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "depreciation_rate": 0.025,
    "construction_year": 1980
  }'
```

---

### 5. Delete Property

Permanently delete a property. Only allowed if the property has no linked transactions.

**Endpoint:** `DELETE /api/v1/properties/{property_id}`

**Authentication:** Required

**Path Parameters:**
- `property_id` (UUID, required): UUID of the property to delete

**Restrictions:**
- Property can only be deleted if it has NO linked transactions
- If transactions exist, you must either:
  1. Unlink all transactions first, or
  2. Archive the property instead (use `POST /properties/{property_id}/archive`)

**Response (204 No Content):**
No response body on success.

**Error Response (400 Bad Request):**
```json
{
  "detail": "Cannot delete property with linked transactions. Unlink transactions or archive the property instead."
}
```

**Example cURL:**
```bash
curl -X DELETE "https://api.taxja.com/api/v1/properties/550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

### 6. Archive Property

Archive a property by marking it as sold. This preserves all historical data while removing it from active property lists.

**Endpoint:** `POST /api/v1/properties/{property_id}/archive`

**Authentication:** Required

**Path Parameters:**
- `property_id` (UUID, required): UUID of the property to archive

**Query Parameters:**
- `sale_date` (date, required): Date the property was sold (YYYY-MM-DD format)

**Effects:**
- Property status changed to 'sold'
- Property will not appear in default property lists (unless `include_archived=true`)
- All historical transactions and depreciation records are preserved
- Depreciation will stop being calculated after the sale date

**Validation:**
- `sale_date` must be >= `purchase_date`

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "address": "Hauptstraße 123, 1010 Wien",
  "purchase_date": "2020-06-15",
  "purchase_price": 350000.00,
  "status": "sold",
  "sale_date": "2025-12-31",
  "updated_at": "2026-03-07T12:00:00Z"
}
```

**Example cURL:**
```bash
curl -X POST "https://api.taxja.com/api/v1/properties/550e8400-e29b-41d4-a716-446655440000/archive?sale_date=2025-12-31" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## Transaction Linking Endpoints

### 7. Get Property Transactions

Retrieve all transactions linked to a specific property.

**Endpoint:** `GET /api/v1/properties/{property_id}/transactions`

**Authentication:** Required

**Path Parameters:**
- `property_id` (UUID, required): UUID of the property

**Query Parameters:**
- `year` (integer, optional): Filter transactions by year (default: all years)

**Response (200 OK):**
```json
{
  "property_id": "550e8400-e29b-41d4-a716-446655440000",
  "year": 2026,
  "total": 15,
  "transactions": [
    {
      "id": 1001,
      "type": "income",
      "amount": 1500.00,
      "transaction_date": "2026-03-01",
      "description": "Miete März 2026",
      "income_category": "rental_income",
      "property_id": "550e8400-e29b-41d4-a716-446655440000"
    },
    {
      "id": 1002,
      "type": "expense",
      "amount": 350.00,
      "transaction_date": "2026-02-15",
      "description": "Hausverwaltung",
      "expense_category": "property_management_fees",
      "property_id": "550e8400-e29b-41d4-a716-446655440000"
    },
    {
      "id": 1003,
      "type": "expense",
      "amount": 5600.00,
      "transaction_date": "2025-12-31",
      "description": "AfA Hauptstraße 123, 1010 Wien (2025)",
      "expense_category": "depreciation_afa",
      "is_system_generated": true,
      "property_id": "550e8400-e29b-41d4-a716-446655440000"
    }
  ]
}
```

**Example cURL:**
```bash
curl -X GET "https://api.taxja.com/api/v1/properties/550e8400-e29b-41d4-a716-446655440000/transactions?year=2026" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

### 8. Link Transaction to Property

Link an existing transaction to a property.

**Endpoint:** `POST /api/v1/properties/{property_id}/link-transaction`

**Authentication:** Required

**Path Parameters:**
- `property_id` (UUID, required): UUID of the property

**Query Parameters:**
- `transaction_id` (integer, required): ID of the transaction to link

**Use Cases:**
- Link rental income to a property
- Link property expenses (maintenance, insurance, etc.) to a property
- Link depreciation transactions to a property

**Validation:**
- Both property and transaction must belong to the current user
- Transaction must exist
- Property must exist

**Response (200 OK):**
```json
{
  "message": "Transaction linked successfully",
  "transaction_id": 1001,
  "property_id": "550e8400-e29b-41d4-a716-446655440000",
  "transaction": {
    "id": 1001,
    "type": "income",
    "amount": 1500.00,
    "transaction_date": "2026-03-01",
    "description": "Miete März 2026",
    "income_category": "rental_income",
    "property_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

**Example cURL:**
```bash
curl -X POST "https://api.taxja.com/api/v1/properties/550e8400-e29b-41d4-a716-446655440000/link-transaction?transaction_id=1001" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

### 9. Unlink Transaction from Property

Remove the link between a transaction and a property.

**Endpoint:** `DELETE /api/v1/properties/{property_id}/unlink-transaction/{transaction_id}`

**Authentication:** Required

**Path Parameters:**
- `property_id` (UUID, required): UUID of the property (for validation)
- `transaction_id` (integer, required): ID of the transaction to unlink

**Effects:**
- Transaction's `property_id` is set to NULL
- Transaction remains in the system but is no longer associated with the property

**Response (200 OK):**
```json
{
  "message": "Transaction unlinked successfully",
  "transaction_id": 1001,
  "property_id": null,
  "transaction": {
    "id": 1001,
    "type": "income",
    "amount": 1500.00,
    "transaction_date": "2026-03-01",
    "description": "Miete März 2026",
    "income_category": "rental_income",
    "property_id": null
  }
}
```

**Example cURL:**
```bash
curl -X DELETE "https://api.taxja.com/api/v1/properties/550e8400-e29b-41d4-a716-446655440000/unlink-transaction/1001" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## Historical Depreciation Endpoints

### 10. Preview Historical Depreciation

Preview what historical depreciation transactions will be created for a property purchased in a previous year.

**Endpoint:** `GET /api/v1/properties/{property_id}/historical-depreciation`

**Authentication:** Required

**Path Parameters:**
- `property_id` (UUID, required): UUID of the property

**Use Case:**
When a property was purchased in a previous year (e.g., 2020) but registered in the system later (e.g., 2026), this endpoint shows what depreciation transactions will be created for the missing years (2020-2025).

**Note:**
- This is a preview only - no transactions are created
- Years that already have depreciation transactions are excluded
- Use `POST /backfill-depreciation` to confirm and create transactions

**Response (200 OK):**
```json
{
  "property_id": "550e8400-e29b-41d4-a716-446655440000",
  "years_count": 6,
  "total_amount": 33600.00,
  "years": [
    {
      "year": 2020,
      "amount": 2800.00,
      "transaction_date": "2020-12-31"
    },
    {
      "year": 2021,
      "amount": 5600.00,
      "transaction_date": "2021-12-31"
    },
    {
      "year": 2022,
      "amount": 5600.00,
      "transaction_date": "2022-12-31"
    },
    {
      "year": 2023,
      "amount": 5600.00,
      "transaction_date": "2023-12-31"
    },
    {
      "year": 2024,
      "amount": 5600.00,
      "transaction_date": "2024-12-31"
    },
    {
      "year": 2025,
      "amount": 5600.00,
      "transaction_date": "2025-12-31"
    }
  ]
}
```

**Example cURL:**
```bash
curl -X GET "https://api.taxja.com/api/v1/properties/550e8400-e29b-41d4-a716-446655440000/historical-depreciation" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

### 11. Backfill Historical Depreciation

Create historical depreciation transactions for a property purchased in a previous year.

**Endpoint:** `POST /api/v1/properties/{property_id}/backfill-depreciation`

**Authentication:** Required

**Path Parameters:**
- `property_id` (UUID, required): UUID of the property

**Effects:**
- Creates depreciation expense transactions for all missing years
- Transactions are dated December 31 of each year
- Transactions are marked as system-generated (`is_system_generated=True`)
- Transactions are linked to the property

**Validation:**
- Property must belong to current user
- Duplicate transactions are prevented (years already backfilled are skipped)
- Total accumulated depreciation cannot exceed building value

**Example:**
Property purchased in 2020, registered in 2026:
- Creates transactions for 2020, 2021, 2022, 2023, 2024, 2025
- Each transaction dated December 31 of respective year
- Total accumulated depreciation updated

**Response (200 OK):**
```json
{
  "property_id": "550e8400-e29b-41d4-a716-446655440000",
  "years_backfilled": 6,
  "total_amount": 33600.00,
  "transaction_ids": [5001, 5002, 5003, 5004, 5005, 5006]
}
```

**Error Response (400 Bad Request):**
```json
{
  "detail": "No historical depreciation to backfill. All years already have depreciation transactions."
}
```

**Example cURL:**
```bash
curl -X POST "https://api.taxja.com/api/v1/properties/550e8400-e29b-41d4-a716-446655440000/backfill-depreciation" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## Annual Depreciation Endpoints

### 12. Generate Annual Depreciation

Generate annual depreciation transactions for all active properties owned by the current user.

**Endpoint:** `POST /api/v1/properties/generate-annual-depreciation`

**Authentication:** Required

**Query Parameters:**
- `year` (integer, optional): Tax year to generate depreciation for (default: current year)

**Use Case:**
At year-end, users can trigger this endpoint to generate depreciation transactions for all their rental properties. This ensures all depreciation expenses are recorded for tax filing purposes.

**Effects:**
- Creates depreciation expense transactions for all active properties owned by current user
- Transactions are dated December 31 of the specified year
- Transactions are marked as system-generated (`is_system_generated=True`)
- Transactions are linked to their respective properties

**Skipping Logic:**
Properties are skipped if:
- Depreciation already exists for the specified year
- Property is fully depreciated (accumulated depreciation = building value)
- Calculated depreciation amount is zero

**Response (200 OK):**
```json
{
  "year": 2025,
  "properties_processed": 3,
  "transactions_created": 2,
  "properties_skipped": 1,
  "total_amount": 11200.00,
  "transaction_ids": [1234, 1235],
  "skipped_details": [
    {
      "property_id": "550e8400-e29b-41d4-a716-446655440000",
      "address": "Hauptstraße 123, 1010 Wien",
      "reason": "already_exists"
    }
  ]
}
```

**Validation:**
- Year must be between 2000 and current year + 1

**Error Response (400 Bad Request):**
```json
{
  "detail": "Invalid year. Year must be between 2000 and 2027. Provided: 2030"
}
```

**Example cURL:**
```bash
curl -X POST "https://api.taxja.com/api/v1/properties/generate-annual-depreciation?year=2025" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## Report Generation Endpoints

### 13. Get Income Statement Report

Generate an income statement report for a property showing rental income, expenses by category, and net income.

**Endpoint:** `GET /api/v1/properties/{property_id}/reports/income-statement`

**Authentication:** Required

**Path Parameters:**
- `property_id` (UUID, required): UUID of the property

**Query Parameters:**
- `start_date` (date, optional): Start date for report (default: beginning of current year)
- `end_date` (date, optional): End date for report (default: today)

**Response (200 OK):**
```json
{
  "property": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "address": "Hauptstraße 123, 1010 Wien",
    "purchase_date": "2020-06-15",
    "building_value": 280000.00
  },
  "period": {
    "start_date": "2026-01-01",
    "end_date": "2026-12-31"
  },
  "income": {
    "rental_income": 18000.00,
    "total": 18000.00
  },
  "expenses": {
    "depreciation_afa": 5600.00,
    "property_management_fees": 1200.00,
    "property_insurance": 800.00,
    "maintenance_repairs": 1500.00,
    "utilities": 900.00,
    "total": 10000.00
  },
  "net_income": 8000.00
}
```

**Example cURL:**
```bash
curl -X GET "https://api.taxja.com/api/v1/properties/550e8400-e29b-41d4-a716-446655440000/reports/income-statement?start_date=2026-01-01&end_date=2026-12-31" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

### 14. Get Depreciation Schedule Report

Generate a depreciation schedule report showing annual depreciation, accumulated depreciation, and remaining value by year.

**Endpoint:** `GET /api/v1/properties/{property_id}/reports/depreciation-schedule`

**Authentication:** Required

**Path Parameters:**
- `property_id` (UUID, required): UUID of the property

**Query Parameters:**
- `include_future` (boolean, optional): Include future depreciation projections (default: true)
- `future_years` (integer, optional): Number of future years to project, 1-50 (default: 10)

**Response (200 OK):**
```json
{
  "property": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "address": "Hauptstraße 123, 1010 Wien",
    "purchase_date": "2020-06-15",
    "building_value": 280000.00,
    "depreciation_rate": 0.02,
    "status": "active",
    "sale_date": null
  },
  "schedule": [
    {
      "year": 2020,
      "annual_depreciation": 2800.00,
      "accumulated_depreciation": 2800.00,
      "remaining_value": 277200.00,
      "is_projected": false
    },
    {
      "year": 2021,
      "annual_depreciation": 5600.00,
      "accumulated_depreciation": 8400.00,
      "remaining_value": 271600.00,
      "is_projected": false
    },
    {
      "year": 2027,
      "annual_depreciation": 5600.00,
      "accumulated_depreciation": 42000.00,
      "remaining_value": 238000.00,
      "is_projected": true
    }
  ],
  "summary": {
    "total_years": 56,
    "years_elapsed": 6,
    "years_projected": 10,
    "total_depreciation": 280000.00,
    "accumulated_depreciation": 33600.00,
    "remaining_value": 246400.00,
    "years_remaining": 44.0,
    "fully_depreciated_year": 2070
  }
}
```

**Example cURL:**
```bash
curl -X GET "https://api.taxja.com/api/v1/properties/550e8400-e29b-41d4-a716-446655440000/reports/depreciation-schedule?include_future=true&future_years=10" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

### 15. Export Income Statement (PDF)

Export income statement report as a PDF file.

**Endpoint:** `GET /api/v1/properties/{property_id}/reports/income-statement/export/pdf`

**Authentication:** Required

**Path Parameters:**
- `property_id` (UUID, required): UUID of the property

**Query Parameters:**
- `start_date` (date, optional): Start date for report
- `end_date` (date, optional): End date for report
- `language` (string, optional): Language code (de, en) (default: de)

**Response:**
- Content-Type: `application/pdf`
- Content-Disposition: `attachment; filename=income_statement_{property_id}_{date}.pdf`

**Example cURL:**
```bash
curl -X GET "https://api.taxja.com/api/v1/properties/550e8400-e29b-41d4-a716-446655440000/reports/income-statement/export/pdf?language=de" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  --output income_statement.pdf
```

---

### 16. Export Income Statement (CSV)

Export income statement report as a CSV file.

**Endpoint:** `GET /api/v1/properties/{property_id}/reports/income-statement/export/csv`

**Authentication:** Required

**Path Parameters:**
- `property_id` (UUID, required): UUID of the property

**Query Parameters:**
- `start_date` (date, optional): Start date for report
- `end_date` (date, optional): End date for report
- `language` (string, optional): Language code (de, en) (default: de)

**Response:**
- Content-Type: `text/csv`
- Content-Disposition: `attachment; filename=income_statement_{property_id}_{date}.csv`

**Example cURL:**
```bash
curl -X GET "https://api.taxja.com/api/v1/properties/550e8400-e29b-41d4-a716-446655440000/reports/income-statement/export/csv?language=de" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  --output income_statement.csv
```

---

### 17. Export Depreciation Schedule (PDF)

Export depreciation schedule report as a PDF file.

**Endpoint:** `GET /api/v1/properties/{property_id}/reports/depreciation-schedule/export/pdf`

**Authentication:** Required

**Path Parameters:**
- `property_id` (UUID, required): UUID of the property

**Query Parameters:**
- `include_future` (boolean, optional): Include future projections (default: true)
- `future_years` (integer, optional): Number of future years to project (default: 10)
- `language` (string, optional): Language code (de, en) (default: de)

**Response:**
- Content-Type: `application/pdf`
- Content-Disposition: `attachment; filename=depreciation_schedule_{property_id}_{date}.pdf`

**Example cURL:**
```bash
curl -X GET "https://api.taxja.com/api/v1/properties/550e8400-e29b-41d4-a716-446655440000/reports/depreciation-schedule/export/pdf?language=de" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  --output depreciation_schedule.pdf
```

---

### 18. Export Depreciation Schedule (CSV)

Export depreciation schedule report as a CSV file.

**Endpoint:** `GET /api/v1/properties/{property_id}/reports/depreciation-schedule/export/csv`

**Authentication:** Required

**Path Parameters:**
- `property_id` (UUID, required): UUID of the property

**Query Parameters:**
- `include_future` (boolean, optional): Include future projections (default: true)
- `future_years` (integer, optional): Number of future years to project (default: 10)
- `language` (string, optional): Language code (de, en) (default: de)

**Response:**
- Content-Type: `text/csv`
- Content-Disposition: `attachment; filename=depreciation_schedule_{property_id}_{date}.csv`

**Example cURL:**
```bash
curl -X GET "https://api.taxja.com/api/v1/properties/550e8400-e29b-41d4-a716-446655440000/reports/depreciation-schedule/export/csv?language=de" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  --output depreciation_schedule.csv
```

---

## Portfolio Management Endpoints

### 19. Compare Portfolio Properties

Compare performance across all user properties with sortable metrics.

**Endpoint:** `GET /api/v1/properties/portfolio/compare`

**Authentication:** Required

**Query Parameters:**
- `year` (integer, optional): Tax year (default: current year)
- `sort_by` (string, optional): Sort field - `net_income`, `rental_yield`, `expense_ratio`, `rental_income` (default: net_income)
- `sort_order` (string, optional): Sort order - `asc`, `desc` (default: desc)

**Response (200 OK):**
```json
[
  {
    "property_id": "550e8400-e29b-41d4-a716-446655440000",
    "address": "Hauptstraße 123, 1010 Wien",
    "rental_income": 18000.00,
    "expenses": 10000.00,
    "net_income": 8000.00,
    "rental_yield": 5.14,
    "expense_ratio": 55.56,
    "depreciation": 5600.00
  },
  {
    "property_id": "660e8400-e29b-41d4-a716-446655440001",
    "address": "Mariahilfer Straße 45, 1060 Wien",
    "rental_income": 24000.00,
    "expenses": 14000.00,
    "net_income": 10000.00,
    "rental_yield": 5.71,
    "expense_ratio": 58.33,
    "depreciation": 6720.00
  }
]
```

**Metrics Explanation:**
- `rental_yield`: (Net income / Building value) × 100
- `expense_ratio`: (Expenses / Rental income) × 100

**Example cURL:**
```bash
curl -X GET "https://api.taxja.com/api/v1/properties/portfolio/compare?year=2026&sort_by=net_income&sort_order=desc" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

### 20. Get Portfolio Summary

Get portfolio-level summary statistics including best/worst performers.

**Endpoint:** `GET /api/v1/properties/portfolio/summary`

**Authentication:** Required

**Query Parameters:**
- `year` (integer, optional): Tax year (default: current year)

**Response (200 OK):**
```json
{
  "year": 2026,
  "total_properties": 3,
  "active_properties": 3,
  "total_rental_income": 54000.00,
  "total_expenses": 32000.00,
  "total_net_income": 22000.00,
  "average_rental_yield": 5.45,
  "average_expense_ratio": 59.26,
  "total_building_value": 896000.00,
  "total_annual_depreciation": 17920.00,
  "best_performer": {
    "property_id": "660e8400-e29b-41d4-a716-446655440001",
    "address": "Mariahilfer Straße 45, 1060 Wien",
    "net_income": 10000.00,
    "rental_yield": 5.71
  },
  "worst_performer": {
    "property_id": "770e8400-e29b-41d4-a716-446655440002",
    "address": "Landstraße 78, 1030 Wien",
    "net_income": 2000.00,
    "rental_yield": 3.57
  }
}
```

**Example cURL:**
```bash
curl -X GET "https://api.taxja.com/api/v1/properties/portfolio/summary?year=2026" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## Bulk Operations Endpoints

### 21. Bulk Generate Annual Depreciation

Generate annual depreciation for multiple properties at once.

**Endpoint:** `POST /api/v1/properties/bulk/generate-depreciation`

**Authentication:** Required

**Request Body:**
```json
{
  "property_ids": [
    "550e8400-e29b-41d4-a716-446655440000",
    "660e8400-e29b-41d4-a716-446655440001",
    "770e8400-e29b-41d4-a716-446655440002"
  ],
  "year": 2026
}
```

**Response (200 OK):**
```json
{
  "year": 2026,
  "total_requested": 3,
  "successful": 2,
  "failed": 0,
  "skipped": 1,
  "total_amount": 11200.00,
  "transaction_ids": [1234, 1235],
  "results": [
    {
      "property_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "success",
      "transaction_id": 1234,
      "amount": 5600.00
    },
    {
      "property_id": "660e8400-e29b-41d4-a716-446655440001",
      "status": "success",
      "transaction_id": 1235,
      "amount": 5600.00
    },
    {
      "property_id": "770e8400-e29b-41d4-a716-446655440002",
      "status": "skipped",
      "reason": "already_exists"
    }
  ]
}
```

**Example cURL:**
```bash
curl -X POST "https://api.taxja.com/api/v1/properties/bulk/generate-depreciation" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "property_ids": ["550e8400-e29b-41d4-a716-446655440000", "660e8400-e29b-41d4-a716-446655440001"],
    "year": 2026
  }'
```

---

### 22. Bulk Archive Properties

Archive multiple properties at once.

**Endpoint:** `POST /api/v1/properties/bulk/archive`

**Authentication:** Required

**Request Body:**
```json
{
  "property_ids": [
    "550e8400-e29b-41d4-a716-446655440000",
    "660e8400-e29b-41d4-a716-446655440001"
  ]
}
```

**Response (200 OK):**
```json
{
  "total_requested": 2,
  "successful": 2,
  "failed": 0,
  "results": [
    {
      "property_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "success",
      "address": "Hauptstraße 123, 1010 Wien"
    },
    {
      "property_id": "660e8400-e29b-41d4-a716-446655440001",
      "status": "success",
      "address": "Mariahilfer Straße 45, 1060 Wien"
    }
  ]
}
```

**Example cURL:**
```bash
curl -X POST "https://api.taxja.com/api/v1/properties/bulk/archive" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "property_ids": ["550e8400-e29b-41d4-a716-446655440000"]
  }'
```

---

### 23. Bulk Link Transactions

Link multiple transactions to a property at once.

**Endpoint:** `POST /api/v1/properties/{property_id}/bulk/link-transactions`

**Authentication:** Required

**Path Parameters:**
- `property_id` (string, required): UUID of the property

**Request Body:**
```json
{
  "transaction_ids": [1001, 1002, 1003, 1004, 1005]
}
```

**Response (200 OK):**
```json
{
  "property_id": "550e8400-e29b-41d4-a716-446655440000",
  "total_requested": 5,
  "successful": 5,
  "failed": 0,
  "results": [
    {
      "transaction_id": 1001,
      "status": "success"
    },
    {
      "transaction_id": 1002,
      "status": "success"
    },
    {
      "transaction_id": 1003,
      "status": "success"
    },
    {
      "transaction_id": 1004,
      "status": "success"
    },
    {
      "transaction_id": 1005,
      "status": "success"
    }
  ]
}
```

**Example cURL:**
```bash
curl -X POST "https://api.taxja.com/api/v1/properties/550e8400-e29b-41d4-a716-446655440000/bulk/link-transactions" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_ids": [1001, 1002, 1003]
  }'
```

---

## Data Models

### Property Model

```json
{
  "id": "UUID",
  "user_id": "integer",
  "property_type": "rental | owner_occupied | mixed_use",
  "rental_percentage": "decimal (0-100)",
  "address": "string (computed: {street}, {postal_code} {city})",
  "street": "string",
  "city": "string",
  "postal_code": "string",
  "purchase_date": "date (YYYY-MM-DD)",
  "purchase_price": "decimal",
  "building_value": "decimal",
  "land_value": "decimal (computed: purchase_price - building_value)",
  "construction_year": "integer | null",
  "depreciation_rate": "decimal (0.001-0.10)",
  "status": "active | sold | archived",
  "sale_date": "date | null",
  "grunderwerbsteuer": "decimal | null",
  "notary_fees": "decimal | null",
  "registry_fees": "decimal | null",
  "created_at": "timestamp",
  "updated_at": "timestamp"
}
```

### Property Metrics Model

```json
{
  "accumulated_depreciation": "decimal",
  "remaining_depreciable_value": "decimal",
  "annual_depreciation": "decimal",
  "total_rental_income": "decimal",
  "total_expenses": "decimal",
  "net_rental_income": "decimal",
  "years_remaining": "integer"
}
```

### Transaction Model (Property-Related Fields)

```json
{
  "id": "integer",
  "user_id": "integer",
  "property_id": "UUID | null",
  "type": "income | expense",
  "amount": "decimal",
  "transaction_date": "date",
  "description": "string",
  "income_category": "string | null",
  "expense_category": "string | null",
  "is_deductible": "boolean",
  "is_system_generated": "boolean"
}
```

### Property Expense Categories

The following expense categories are recognized for property-related transactions:

- `depreciation_afa`: Depreciation (Absetzung für Abnutzung)
- `loan_interest`: Mortgage/loan interest payments
- `property_management_fees`: Property management fees (Hausverwaltung)
- `property_insurance`: Property insurance premiums
- `property_tax`: Property tax (Grundsteuer)
- `maintenance_repairs`: Maintenance and repair costs
- `utilities`: Utilities (if paid by landlord)

### Property Types

- **rental**: Property used exclusively for rental purposes (100% deductible)
- **owner_occupied**: Property used as primary residence (not depreciable, limited deductions)
- **mixed_use**: Property with both rental and personal use (proportional deductions based on rental_percentage)

### Property Status

- **active**: Property is currently owned and generating rental income
- **sold**: Property has been sold (archived)
- **archived**: Property is no longer active but data is preserved

---

## Austrian Tax Law Context

### Depreciation (AfA - Absetzung für Abnutzung)

**Legal Basis:** § 8 EStG (Einkommensteuergesetz)

**Depreciation Rates:**
- Buildings constructed **before 1915**: 1.5% annual depreciation
- Buildings constructed **1915 or later**: 2.0% annual depreciation

**Key Rules:**
1. Only the **building value** is depreciable (land value is not depreciable)
2. Depreciation is calculated on a **straight-line basis** (linear depreciation)
3. For properties purchased mid-year, depreciation is **pro-rated** based on months owned
4. Depreciation stops when **accumulated depreciation equals building value**
5. For **mixed-use properties**, only the rental percentage is depreciable

**Building Value Calculation:**
- If not explicitly stated in the purchase contract (Kaufvertrag), building value is typically estimated as **80% of purchase price**
- Land value = Purchase price - Building value

### Rental Income (Vermietung und Verpachtung)

**Legal Basis:** § 28 EStG

**Deductible Expenses:**
- Depreciation (AfA)
- Loan interest (Kreditzinsen)
- Property management fees (Hausverwaltung)
- Property insurance (Gebäudeversicherung)
- Property tax (Grundsteuer)
- Maintenance and repairs (Instandhaltung und Reparaturen)
- Utilities (if paid by landlord)

**Tax Form Fields:**
- **KZ 350**: Rental income (Einkünfte aus Vermietung und Verpachtung)
- **KZ 351**: Rental expenses (Werbungskosten)

### Owner-Occupied Properties

**Key Points:**
- Purchase costs are generally **NOT tax-deductible** for owner-occupied properties
- No depreciation (AfA) allowed for personal use
- Exceptions:
  - Home office (Arbeitszimmer) for self-employed individuals (limited deduction)
  - Energy-efficient renovation costs may qualify for specific tax credits
- Purchase costs are relevant for **capital gains tax (ImmoESt)** calculation upon future sale

### Property Transfer Tax (Grunderwerbsteuer)

- Typically **3.5%** of purchase price in Austria
- Paid by the buyer
- Not immediately deductible for owner-occupied properties
- For rental properties, included in the depreciable building value

---

## Rate Limits

**Standard Rate Limits:**
- 100 requests per minute per user
- 1000 requests per hour per user

**Bulk Operation Limits:**
- Maximum 50 properties per bulk operation
- Maximum 100 transactions per bulk link operation

**File Export Limits:**
- PDF exports: Maximum 100 pages
- CSV exports: Maximum 10,000 rows

---

## Best Practices

### 1. Property Registration

- Always provide `construction_year` for accurate depreciation rate calculation
- Use `building_value` from the purchase contract (Kaufvertrag) if available
- For mixed-use properties, accurately specify `rental_percentage`

### 2. Transaction Linking

- Link rental income transactions immediately upon creation
- Link property expenses to enable accurate net income calculations
- Use bulk linking for importing historical transactions

### 3. Historical Depreciation

- Always preview historical depreciation before backfilling
- Backfill immediately after registering a property purchased in a previous year
- Verify accumulated depreciation totals after backfilling

### 4. Annual Depreciation

- Generate annual depreciation at year-end (December 31)
- Use the bulk generation endpoint for multiple properties
- Verify no duplicates exist before generating

### 5. Reports

- Generate income statements for tax filing preparation
- Use depreciation schedules for long-term planning
- Export reports in German (de) for official tax submissions

### 6. Error Handling

- Always check for 404 errors (property not found)
- Handle 400 errors (validation failures) with user-friendly messages
- Implement retry logic for 500 errors (server errors)

---

## Security Considerations

### Authentication

- All endpoints require valid JWT Bearer token
- Tokens expire after 24 hours (configurable)
- Refresh tokens before expiration to maintain session

### Data Privacy (GDPR Compliance)

- Property addresses are encrypted at rest using AES-256
- User data is isolated (users can only access their own properties)
- Audit logs track all property operations
- Data retention: 10 years for tax compliance, then automatic deletion

### Ownership Validation

- All endpoints validate that the property belongs to the authenticated user
- Attempting to access another user's property returns 404 (not 403) to prevent information disclosure

---

## Support and Resources

### Documentation

- **API Reference**: `/api/v1/docs` (Swagger UI)
- **OpenAPI Spec**: `/api/v1/openapi.json`
- **Austrian Tax Law Guide**: `/docs/austrian-tax-law.md`

### Contact

- **Technical Support**: support@taxja.com
- **Tax Questions**: Consult a certified Steuerberater (tax advisor)
- **Bug Reports**: GitHub Issues

### Important Disclaimer

**Taxja is a reference system only and does not provide official tax advice.**

- All tax calculations are estimates based on Austrian tax law
- Final tax filing must be done through **FinanzOnline** (official Austrian tax portal)
- Complex cases require consultation with a certified **Steuerberater**
- Users are responsible for verifying all data before tax submission

---

## Changelog

### Version 1.0 (2026-03-07)

- Initial release of Property Management API
- Support for rental, owner-occupied, and mixed-use properties
- Depreciation calculation per Austrian tax law (§ 8 EStG)
- Historical depreciation backfill
- Annual depreciation generation
- Income statement and depreciation schedule reports
- Portfolio comparison and summary
- Bulk operations for depreciation and archiving

---

**Document Version:** 1.0  
**Last Updated:** 2026-03-07  
**API Version:** v1

