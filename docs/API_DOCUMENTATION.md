# Taxja API Documentation

## Overview

The Taxja API is a RESTful API built with FastAPI that provides comprehensive tax management functionality for Austrian taxpayers. All endpoints are versioned under `/api/v1/`.

## Base URL

```
Development: http://localhost:8000
Production: https://api.taxja.at
```

## Authentication

Most endpoints require JWT authentication. Include the token in the Authorization header:

```
Authorization: Bearer <your_jwt_token>
```

### Authentication Endpoints

#### POST /api/v1/auth/register
Register a new user account.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "full_name": "Max Mustermann",
  "user_type": "employee"
}
```

**Response (201 Created):**
```json
{
  "id": 1,
  "email": "user@example.com",
  "full_name": "Max Mustermann",
  "user_type": "employee",
  "created_at": "2026-03-04T10:00:00Z"
}
```

#### POST /api/v1/auth/login
Login with email and password.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "requires_2fa": true
}
```

**If 2FA is enabled, follow up with:**

#### POST /api/v1/auth/verify-2fa
Verify 2FA token and complete login.

**Request Body:**
```json
{
  "email": "user@example.com",
  "token": "123456"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "full_name": "Max Mustermann"
  }
}
```

#### POST /api/v1/auth/refresh
Refresh access token.

**Request Body:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

## Transaction Management

### Endpoints

#### GET /api/v1/transactions
List all transactions with filtering and pagination.

**Query Parameters:**
- `tax_year` (optional): Filter by tax year (default: current year)
- `type` (optional): Filter by type (`income` or `expense`)
- `category` (optional): Filter by category
- `start_date` (optional): Filter by start date (ISO 8601)
- `end_date` (optional): Filter by end date (ISO 8601)
- `skip` (optional): Pagination offset (default: 0)
- `limit` (optional): Pagination limit (default: 100)

**Response (200 OK):**
```json
{
  "items": [
    {
      "id": 1,
      "type": "income",
      "amount": "3500.00",
      "date": "2026-02-15",
      "description": "Monthly salary",
      "category": "employment_income",
      "is_deductible": false,
      "vat_rate": null,
      "vat_amount": null,
      "document_id": 5,
      "classification_confidence": 0.95,
      "created_at": "2026-02-15T10:00:00Z"
    }
  ],
  "total": 150,
  "skip": 0,
  "limit": 100
}
```

#### POST /api/v1/transactions
Create a new transaction.

**Request Body:**
```json
{
  "type": "expense",
  "amount": "125.50",
  "date": "2026-03-01",
  "description": "Office supplies from Staples",
  "category": "office_supplies",
  "is_deductible": true,
  "vat_rate": "0.20",
  "vat_amount": "20.92",
  "document_id": 10
}
```

**Response (201 Created):**
```json
{
  "id": 2,
  "type": "expense",
  "amount": "125.50",
  "date": "2026-03-01",
  "description": "Office supplies from Staples",
  "category": "office_supplies",
  "is_deductible": true,
  "vat_rate": "0.20",
  "vat_amount": "20.92",
  "document_id": 10,
  "classification_confidence": 0.88,
  "created_at": "2026-03-04T10:00:00Z"
}
```

#### GET /api/v1/transactions/{id}
Get a specific transaction by ID.

**Response (200 OK):**
```json
{
  "id": 1,
  "type": "income",
  "amount": "3500.00",
  "date": "2026-02-15",
  "description": "Monthly salary",
  "category": "employment_income",
  "is_deductible": false,
  "document": {
    "id": 5,
    "document_type": "payslip",
    "file_path": "documents/user_1/2026/payslip_feb.pdf"
  }
}
```

#### PUT /api/v1/transactions/{id}
Update an existing transaction.

**Request Body:** (same as POST)

**Response (200 OK):** (updated transaction object)

#### DELETE /api/v1/transactions/{id}
Delete a transaction.

**Response (204 No Content)**

#### POST /api/v1/transactions/import
Import transactions from CSV or MT940 file.

**Request (multipart/form-data):**
- `file`: CSV or MT940 file
- `format`: "csv" or "mt940"

**Response (200 OK):**
```json
{
  "imported": 45,
  "duplicates": 3,
  "errors": 0,
  "transactions": [
    {
      "id": 100,
      "amount": "50.00",
      "description": "BILLA Supermarket",
      "category": "groceries",
      "is_duplicate": false
    }
  ]
}
```

## Document Management & OCR

#### POST /api/v1/documents/upload
Upload a document for OCR processing.

**Request (multipart/form-data):**
- `file`: Image file (JPEG, PNG) or PDF
- `document_type` (optional): Hint for document type

**Response (201 Created):**
```json
{
  "id": 10,
  "document_type": "receipt",
  "file_path": "documents/user_1/2026/receipt_001.jpg",
  "ocr_status": "processing",
  "confidence_score": null,
  "created_at": "2026-03-04T10:00:00Z"
}
```

#### POST /api/v1/documents/batch-upload
Upload multiple documents for batch OCR processing.

**Request (multipart/form-data):**
- `files`: Multiple image files

**Response (200 OK):**
```json
{
  "total": 5,
  "processing": 5,
  "documents": [
    {
      "id": 11,
      "document_type": "receipt",
      "ocr_status": "processing"
    }
  ]
}
```

#### GET /api/v1/documents/{id}
Get document details and OCR results.

**Response (200 OK):**
```json
{
  "id": 10,
  "document_type": "receipt",
  "file_path": "documents/user_1/2026/receipt_001.jpg",
  "ocr_status": "completed",
  "confidence_score": 0.85,
  "extracted_data": {
    "date": "2026-03-01",
    "amount": "45.80",
    "merchant": "BILLA AG",
    "items": [
      {"name": "Milk", "amount": "1.50"},
      {"name": "Bread", "amount": "2.30"}
    ],
    "vat_amounts": {
      "20%": "7.63"
    }
  },
  "raw_text": "BILLA AG\n...",
  "needs_review": false
}
```

#### GET /api/v1/documents
List all documents with filtering.

**Query Parameters:**
- `document_type` (optional): Filter by type
- `start_date` (optional): Filter by date
- `end_date` (optional): Filter by date
- `skip`, `limit`: Pagination

**Response (200 OK):**
```json
{
  "items": [...],
  "total": 50
}
```

#### GET /api/v1/documents/{id}/download
Download original document file.

**Response (200 OK):** Binary file stream

#### POST /api/v1/documents/{id}/confirm
Confirm OCR results and create transaction.

**Request Body:**
```json
{
  "extracted_data": {
    "date": "2026-03-01",
    "amount": "45.80",
    "merchant": "BILLA AG"
  },
  "create_transaction": true
}
```

**Response (200 OK):**
```json
{
  "document_id": 10,
  "transaction_id": 150,
  "message": "Transaction created successfully"
}
```

## Tax Calculations

#### POST /api/v1/tax/calculate
Calculate taxes for a specific year.

**Request Body:**
```json
{
  "tax_year": 2026,
  "user_type": "self_employed",
  "include_deductions": true
}
```

**Response (200 OK):**
```json
{
  "tax_year": 2026,
  "gross_income": "65000.00",
  "taxable_income": "58500.00",
  "income_tax": "15420.00",
  "vat_liability": "2500.00",
  "svs_contributions": "8450.00",
  "total_tax": "26370.00",
  "net_income": "38630.00",
  "breakdown": {
    "income_tax_by_bracket": [
      {"bracket": "€13,539 - €21,992", "rate": "20%", "tax": "1690.60"},
      {"bracket": "€21,992 - €36,458", "rate": "30%", "tax": "4339.80"}
    ],
    "deductions_applied": {
      "commuting_allowance": "1200.00",
      "home_office": "300.00",
      "svs_contributions": "8450.00"
    }
  }
}
```

#### POST /api/v1/tax/simulate
Simulate tax changes with what-if scenarios.

**Request Body:**
```json
{
  "tax_year": 2026,
  "changes": {
    "add_expense": {
      "amount": "5000.00",
      "category": "equipment"
    }
  }
}
```

**Response (200 OK):**
```json
{
  "current_tax": "15420.00",
  "simulated_tax": "13920.00",
  "tax_difference": "-1500.00",
  "explanation": "Adding €5,000 in equipment expenses reduces your taxable income, saving €1,500 in taxes."
}
```

#### GET /api/v1/tax/flat-rate-compare
Compare actual accounting vs flat-rate taxation.

**Query Parameters:**
- `tax_year`: Year to compare

**Response (200 OK):**
```json
{
  "actual_accounting": {
    "gross_income": "65000.00",
    "deductible_expenses": "15000.00",
    "taxable_income": "50000.00",
    "tax": "12420.00"
  },
  "flat_rate": {
    "gross_income": "65000.00",
    "flat_rate_deduction": "3900.00",
    "taxable_income": "61100.00",
    "tax": "16920.00"
  },
  "recommendation": "actual_accounting",
  "savings": "4500.00",
  "explanation": "Actual accounting saves €4,500 compared to flat-rate taxation."
}
```

#### POST /api/v1/tax/calculate-refund
Calculate employee tax refund (Arbeitnehmerveranlagung).

**Request Body:**
```json
{
  "tax_year": 2026,
  "gross_income": "42000.00",
  "withheld_tax": "8500.00",
  "deductions": {
    "commuting_allowance": "1200.00",
    "home_office": "300.00"
  }
}
```

**Response (200 OK):**
```json
{
  "actual_tax_liability": "7200.00",
  "withheld_tax": "8500.00",
  "refund_amount": "1300.00",
  "explanation": "You overpaid €1,300 in taxes. File Arbeitnehmerveranlagung to claim your refund."
}
```

## Reports & Export

#### POST /api/v1/reports/generate
Generate tax report.

**Request Body:**
```json
{
  "tax_year": 2026,
  "report_type": "pdf",
  "language": "de"
}
```

**Response (201 Created):**
```json
{
  "id": 5,
  "tax_year": 2026,
  "report_type": "pdf",
  "language": "de",
  "status": "completed",
  "file_path": "reports/user_1/tax_report_2026_de.pdf",
  "created_at": "2026-03-04T10:00:00Z"
}
```

#### GET /api/v1/reports/{id}/pdf
Download PDF report.

**Response (200 OK):** PDF file stream

#### GET /api/v1/reports/{id}/xml
Download FinanzOnline XML.

**Response (200 OK):** XML file stream

#### GET /api/v1/reports/audit-checklist
Get audit readiness checklist.

**Query Parameters:**
- `tax_year`: Year to check

**Response (200 OK):**
```json
{
  "tax_year": 2026,
  "overall_status": "ready",
  "checks": [
    {
      "item": "All transactions have supporting documents",
      "status": "passed",
      "details": "150/150 transactions documented"
    },
    {
      "item": "All deductions properly documented",
      "status": "warning",
      "details": "2 deductions missing receipts"
    }
  ],
  "missing_documents": [
    {
      "transaction_id": 45,
      "description": "Office supplies",
      "amount": "150.00"
    }
  ]
}
```

## Dashboard

#### GET /api/v1/dashboard
Get dashboard overview.

**Query Parameters:**
- `tax_year` (optional): Year to display (default: current)

**Response (200 OK):**
```json
{
  "tax_year": 2026,
  "ytd_income": "45000.00",
  "ytd_expenses": "12000.00",
  "estimated_tax": "8500.00",
  "paid_tax": "6000.00",
  "remaining_tax": "2500.00",
  "net_income": "36500.00",
  "vat_threshold_distance": "10000.00",
  "income_trend": [
    {"month": "2026-01", "income": "3500.00", "expenses": "1200.00"},
    {"month": "2026-02", "income": "3500.00", "expenses": "1500.00"}
  ]
}
```

#### GET /api/v1/dashboard/suggestions
Get tax savings suggestions.

**Response (200 OK):**
```json
{
  "suggestions": [
    {
      "type": "commuting_allowance",
      "potential_savings": "1200.00",
      "description": "You haven't claimed commuting allowance. Update your profile with commuting distance.",
      "action_url": "/profile/commuting"
    },
    {
      "type": "flat_rate_comparison",
      "potential_savings": "4500.00",
      "description": "Actual accounting could save €4,500 compared to flat-rate taxation.",
      "action_url": "/tax/flat-rate-compare"
    }
  ]
}
```

#### GET /api/v1/dashboard/calendar
Get tax calendar with upcoming deadlines.

**Response (200 OK):**
```json
{
  "deadlines": [
    {
      "date": "2026-06-30",
      "title": "Income tax filing deadline",
      "description": "File Einkommensteuererklärung by June 30",
      "priority": "high",
      "days_remaining": 118
    },
    {
      "date": "2026-03-15",
      "title": "Q1 VAT prepayment",
      "description": "Pay quarterly VAT prepayment",
      "priority": "medium",
      "days_remaining": 11
    }
  ]
}
```

## AI Tax Assistant

#### POST /api/v1/ai/chat
Send a message to the AI assistant.

**Request Body:**
```json
{
  "message": "Can I deduct my home office expenses?",
  "language": "de",
  "context": {
    "user_type": "self_employed",
    "tax_year": 2026
  }
}
```

**Response (200 OK):**
```json
{
  "message_id": "msg_123",
  "response": "Ja, als Selbständiger können Sie Ihr Homeoffice absetzen. In Österreich gibt es eine Pauschale von €300 pro Jahr für Homeoffice-Kosten...\n\n⚠️ Disclaimer: Diese Antwort dient nur als allgemeine Information und stellt keine Steuerberatung dar. Bitte konsultieren Sie bei komplexen Fällen einen Steuerberater.",
  "sources": [
    {
      "title": "BMF Homeoffice-Regelung 2026",
      "url": "https://www.bmf.gv.at/..."
    }
  ],
  "created_at": "2026-03-04T10:00:00Z"
}
```

#### GET /api/v1/ai/history
Get chat history.

**Query Parameters:**
- `limit` (optional): Number of messages (default: 50)

**Response (200 OK):**
```json
{
  "messages": [
    {
      "id": "msg_123",
      "role": "user",
      "content": "Can I deduct my home office expenses?",
      "created_at": "2026-03-04T10:00:00Z"
    },
    {
      "id": "msg_124",
      "role": "assistant",
      "content": "Ja, als Selbständiger...",
      "created_at": "2026-03-04T10:00:05Z"
    }
  ]
}
```

#### DELETE /api/v1/ai/history
Clear chat history.

**Response (204 No Content)**

## Admin Endpoints

#### POST /api/v1/admin/tax-config
Create or update tax configuration for a year.

**Request Body:**
```json
{
  "tax_year": 2027,
  "tax_brackets": [
    {"lower_limit": 0, "upper_limit": 13539, "rate": 0.0},
    {"lower_limit": 13539, "upper_limit": 21992, "rate": 0.20}
  ],
  "exemption_amount": "13539.00",
  "vat_rates": {
    "standard": "0.20",
    "residential": "0.10"
  }
}
```

**Response (201 Created):**
```json
{
  "id": 2,
  "tax_year": 2027,
  "created_at": "2026-03-04T10:00:00Z"
}
```

#### POST /api/v1/admin/ai/refresh-knowledge-base
Refresh AI knowledge base with updated tax laws.

**Response (200 OK):**
```json
{
  "status": "completed",
  "documents_indexed": 150,
  "embeddings_created": 1500
}
```

## Error Responses

All endpoints may return the following error responses:

### 400 Bad Request
```json
{
  "detail": "Validation error",
  "errors": [
    {
      "field": "amount",
      "message": "Amount must be positive"
    }
  ]
}
```

### 401 Unauthorized
```json
{
  "detail": "Not authenticated"
}
```

### 403 Forbidden
```json
{
  "detail": "Not enough permissions"
}
```

### 404 Not Found
```json
{
  "detail": "Transaction not found"
}
```

### 422 Unprocessable Entity
```json
{
  "detail": [
    {
      "loc": ["body", "amount"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### 500 Internal Server Error
```json
{
  "detail": "Internal server error",
  "error_id": "err_abc123"
}
```

## Rate Limiting

API endpoints are rate-limited to prevent abuse:

- **Authentication endpoints**: 5 requests per minute
- **OCR endpoints**: 10 requests per minute
- **AI chat endpoints**: 20 requests per minute
- **Other endpoints**: 100 requests per minute

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1709553600
```

## Pagination

List endpoints support pagination with `skip` and `limit` parameters:

```
GET /api/v1/transactions?skip=0&limit=50
```

Response includes pagination metadata:
```json
{
  "items": [...],
  "total": 150,
  "skip": 0,
  "limit": 50
}
```

## Interactive API Documentation

FastAPI automatically generates interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## SDK Examples

### Python
```python
import requests

# Login
response = requests.post(
    "http://localhost:8000/api/v1/auth/login",
    json={"email": "user@example.com", "password": "password"}
)
token = response.json()["access_token"]

# Create transaction
headers = {"Authorization": f"Bearer {token}"}
response = requests.post(
    "http://localhost:8000/api/v1/transactions",
    headers=headers,
    json={
        "type": "expense",
        "amount": "125.50",
        "date": "2026-03-01",
        "description": "Office supplies"
    }
)
```

### JavaScript/TypeScript
```typescript
// Login
const loginResponse = await fetch('http://localhost:8000/api/v1/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    email: 'user@example.com',
    password: 'password'
  })
});
const { access_token } = await loginResponse.json();

// Create transaction
const response = await fetch('http://localhost:8000/api/v1/transactions', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${access_token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    type: 'expense',
    amount: '125.50',
    date: '2026-03-01',
    description: 'Office supplies'
  })
});
```

## Webhooks (Future)

Webhook support is planned for future releases to notify external systems of events:

- Transaction created/updated
- OCR processing completed
- Tax calculation completed
- Report generated

## Versioning

The API uses URL versioning (`/api/v1/`). Breaking changes will be introduced in new versions (`/api/v2/`) while maintaining backward compatibility for at least 12 months.

## Support

For API support, contact:
- Email: api-support@taxja.at
- Documentation: https://docs.taxja.at
- GitHub Issues: https://github.com/taxja/taxja/issues
