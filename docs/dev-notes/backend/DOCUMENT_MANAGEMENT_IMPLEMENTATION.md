# Document Storage and Management Implementation

## Overview

Task 12 "Document storage and management" has been successfully completed. This implementation provides a comprehensive document management system with OCR integration, archival policies, and transaction suggestion capabilities.

## Implemented Components

### 1. MinIO Storage Service (Task 12.1) ✅

**File**: `backend/app/services/storage_service.py`

**Features**:
- S3-compatible API for MinIO integration
- AES-256 server-side encryption for all uploads
- Upload, download, and delete operations
- Presigned URL generation for secure file access
- Automatic bucket creation with encryption enabled

**Key Methods**:
- `upload_file()` - Upload with AES-256 encryption
- `download_file()` - Retrieve file from storage
- `delete_file()` - Remove file from storage
- `get_file_url()` - Generate presigned URLs

### 2. Document Upload API (Task 12.2) ✅

**File**: `backend/app/api/v1/endpoints/documents.py`

**Endpoints**:
- `POST /api/v1/documents/upload` - Single document upload
- `POST /api/v1/documents/batch-upload` - Batch upload (Task 12.3)
- `GET /api/v1/documents` - List with filtering (Task 12.4)
- `GET /api/v1/documents/{id}` - Get document details
- `GET /api/v1/documents/{id}/download` - Download file (Task 12.5)
- `DELETE /api/v1/documents/{id}` - Soft delete (archive)

**Features**:
- File format validation (JPEG, PNG, PDF)
- File size validation (max 10MB)
- Automatic OCR processing trigger
- Metadata storage in PostgreSQL
- Encrypted storage in MinIO

**Schemas**: `backend/app/schemas/document.py`
- `DocumentUploadResponse`
- `DocumentDetail`
- `DocumentList`
- `DocumentSearchParams`
- `BatchUploadResponse`

### 3. Batch Document Upload (Task 12.3) ✅

**Endpoint**: `POST /api/v1/documents/batch-upload`

**Features**:
- Process multiple files in parallel
- Individual status tracking for each file
- Continues processing even if some files fail
- Returns detailed success/failure report

### 4. Document Retrieval and Search (Task 12.4) ✅

**Endpoint**: `GET /api/v1/documents`

**Features**:
- Filter by document type
- Filter by date range
- Filter by transaction ID
- Full-text search on OCR text
- Pagination support

### 5. Document Download (Task 12.5) ✅

**Endpoint**: `GET /api/v1/documents/{id}/download`

**Features**:
- Stream file from MinIO storage
- Returns file with original filename
- Proper content-type headers

### 6. Document Archival and Retention (Task 12.6) ✅

**File**: `backend/app/services/document_archival_service.py`

**Features**:
- Soft delete (archival) instead of hard delete
- Automatic archival when transaction deleted
- 7-year retention policy (Austrian tax law)
- Restore archived documents
- Retention statistics

**Endpoints**:
- `POST /api/v1/documents/{id}/archive` - Archive document
- `POST /api/v1/documents/{id}/restore` - Restore archived document
- `GET /api/v1/documents/archived` - List archived documents
- `GET /api/v1/documents/retention-stats` - Get retention statistics

**Key Methods**:
- `archive_document()` - Mark document as archived
- `archive_documents_for_transaction()` - Archive all docs for a transaction
- `apply_retention_policy()` - Delete old archived documents (7+ years)
- `restore_document()` - Restore archived document
- `get_retention_statistics()` - Get archival stats

### 7. Property Tests for Document-Transaction Association (Task 12.7) ✅

**File**: `backend/tests/test_document_archival_properties.py`

**Property 26: Document archival association integrity**

**Tests**:
- `test_property_26a_document_archival_preserves_data` - Archival preserves all data
- `test_property_26b_transaction_deletion_archives_documents` - Transaction deletion triggers archival
- `test_property_26c_multiple_documents_archival` - Multiple documents archived correctly
- `test_property_26d_restore_reverses_archival` - Restore reverses archival
- `test_property_26e_retention_policy_respects_age` - Retention policy identifies old documents
- `test_property_26f_unarchived_documents_not_affected_by_retention` - Active docs not deleted

**Validates Requirements**: 19.8, 19.9, 24.1, 24.7

### 8. OCR Integration with Document Upload (Task 12.8) ✅

**File**: `backend/app/services/ocr_transaction_service.py`

**Features**:
- Automatic OCR processing on upload (via Celery)
- Transaction suggestion generation from OCR data
- Document type-specific extraction logic
- Automatic classification and deductibility checking

**Endpoints**:
- `GET /api/v1/documents/{id}/transaction-suggestion` - Get transaction suggestion
- `POST /api/v1/documents/{id}/create-transaction` - Create transaction from OCR

**Supported Document Types**:
- Receipts (supermarket, retail)
- Invoices (business purchases)
- Payslips (salary income)
- Lohnzettel (wage tax card)
- SVS notices (social insurance)

**Key Methods**:
- `create_transaction_suggestion()` - Generate suggestion from OCR
- `create_transaction_from_suggestion()` - Create actual transaction
- `_extract_from_receipt()` - Extract receipt data
- `_extract_from_invoice()` - Extract invoice data
- `_extract_from_payslip()` - Extract payslip data
- `_classify_from_ocr()` - Classify transaction type and category

## Database Model Updates

**File**: `backend/app/models/document.py`

**Added Fields**:
- `is_archived` - Boolean flag for archival status
- `archived_at` - Timestamp when archived
- `processed_at` - Timestamp when OCR completed

**Fixed Import**: Added `Enum as SQLEnum` and `Boolean` imports

## API Router Updates

**File**: `backend/app/api/v1/router.py`

**Added**: Documents router to API v1
```python
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
```

## Celery Task Updates

**File**: `backend/app/tasks/ocr_tasks.py`

**Enhanced**: `process_document_ocr` task now:
- Sets `processed_at` timestamp
- Automatically creates transaction suggestions
- Returns suggestion in task result

## Security Features

1. **Encryption at Rest**: AES-256 encryption for all stored documents
2. **Encryption in Transit**: TLS 1.3 for all API communications
3. **Access Control**: User-scoped document access (users can only access their own documents)
4. **Audit Trail**: Archival preserves documents even when transactions deleted

## GDPR Compliance

1. **Data Retention**: 7-year retention policy per Austrian tax law
2. **Right to Deletion**: Documents can be permanently deleted after retention period
3. **Data Portability**: Download endpoint allows users to retrieve their documents
4. **Audit Logging**: All document operations logged

## Testing

### Property-Based Tests
- 6 comprehensive property tests using Hypothesis
- Tests validate document archival integrity
- Tests ensure retention policy correctness

### Test Coverage
- Document upload and validation
- Batch upload processing
- Document retrieval and search
- Archival and restoration
- Transaction suggestion generation

## API Documentation

All endpoints are automatically documented via FastAPI's OpenAPI integration:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Usage Examples

### Upload Document
```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -H "Authorization: Bearer <token>" \
  -F "file=@receipt.jpg"
```

### Get Transaction Suggestion
```bash
curl -X GET "http://localhost:8000/api/v1/documents/123/transaction-suggestion" \
  -H "Authorization: Bearer <token>"
```

### Create Transaction from Document
```bash
curl -X POST "http://localhost:8000/api/v1/documents/123/create-transaction" \
  -H "Authorization: Bearer <token>"
```

### Search Documents
```bash
curl -X GET "http://localhost:8000/api/v1/documents?document_type=receipt&search_text=BILLA" \
  -H "Authorization: Bearer <token>"
```

### Archive Document
```bash
curl -X POST "http://localhost:8000/api/v1/documents/123/archive" \
  -H "Authorization: Bearer <token>"
```

## Requirements Validated

- ✅ **Requirement 17.1**: AES-256 encryption at rest
- ✅ **Requirement 17.2**: TLS 1.3 encryption in transit
- ✅ **Requirement 19.1**: Document upload (JPEG, PNG, PDF)
- ✅ **Requirement 19.5**: Batch processing
- ✅ **Requirement 19.6**: Parallel processing
- ✅ **Requirement 19.7**: OCR integration
- ✅ **Requirement 19.8**: Document-transaction association
- ✅ **Requirement 19.9**: Document archival
- ✅ **Requirement 20.5**: Payslip transaction creation
- ✅ **Requirement 21.6**: Receipt transaction creation
- ✅ **Requirement 22.6**: Invoice transaction creation
- ✅ **Requirement 24.1**: Document storage
- ✅ **Requirement 24.2**: File format validation
- ✅ **Requirement 24.3**: Document filtering
- ✅ **Requirement 24.4**: Date range filtering
- ✅ **Requirement 24.5**: Full-text search
- ✅ **Requirement 24.6**: Document download
- ✅ **Requirement 24.7**: Document archival
- ✅ **Requirement 25.1**: File size validation

## Next Steps

The document management system is now complete and ready for integration with:
1. Frontend document upload UI (Task 28)
2. OCR review interface (Task 13)
3. Transaction management workflow (Task 8)

## Notes

- All document operations are user-scoped for security
- OCR processing is asynchronous via Celery
- Documents are soft-deleted (archived) to maintain audit trail
- Retention policy follows Austrian tax law (7 years)
- Transaction suggestions are automatically generated from OCR data
