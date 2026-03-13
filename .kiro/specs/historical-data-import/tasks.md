# Implementation Plan: Historical Data Import

## Overview

This implementation plan breaks down the Historical Data Import feature into actionable coding tasks. The feature consolidates existing document extraction capabilities (E1 forms, Einkommensteuerbescheid, Kaufvertrag) and adds new functionality for Saldenliste import, creating a comprehensive onboarding experience for new users.

## Current State

The following components are already implemented:
- Database models: `HistoricalImportSession`, `HistoricalImportUpload`, `ImportConflict`, `ImportMetrics`
- Import services: `E1FormImportService`, `BescheidImportService`
- Extractors: `E1FormExtractor`, `BescheidExtractor`, `KaufvertragExtractor`
- Supporting services: `AddressMatcher`, `DuplicateDetector`, `HistoricalDepreciationService`
- Saldenliste service: `SaldenlisteService` (generates reports, includes Kontenplan mapping)

## Tasks

- [x] 1. Core API Infrastructure
  - [x] 1.1 Create historical import API endpoints module
    - Create `backend/app/api/v1/endpoints/historical_import.py`
    - Implement POST `/api/v1/historical-import/upload` endpoint (upload document, classify type, create HistoricalImportUpload)
    - Implement GET `/api/v1/historical-import/status/{upload_id}` endpoint (check processing status)
    - Implement POST `/api/v1/historical-import/session` endpoint (create multi-document session)
    - Implement GET `/api/v1/historical-import/session/{session_id}` endpoint (get session summary)
    - Implement POST `/api/v1/historical-import/review/{upload_id}` endpoint (review/edit/approve/reject)
    - Add router to main API router in `backend/app/api/v1/router.py`

  - [x] 1.2 Create Pydantic schemas for historical import
    - Create `backend/app/schemas/historical_import.py`
    - Implement `HistoricalImportUploadRequest` (file, document_type, tax_year)
    - Implement `HistoricalImportStatusResponse` (status, extracted_data, confidence, requires_review)
    - Implement `HistoricalImportReviewRequest` (edited_data, approved, notes)
    - Implement `ImportSessionRequest` and `ImportSessionResponse`
    - Add validators for tax_year (2000-2030, not future, max 10 years old)

  - [x] 1.3 Enhance OCR task for historical import workflow
    - Modify `backend/app/tasks/ocr_task.py` to support historical import
    - Add task chaining: OCR → Extract → Import (call appropriate service)
    - Implement progress tracking and status updates to HistoricalImportUpload
    - Add error handling with retry logic for transient errors
    - Store OCR results and extracted data in HistoricalImportUpload.extracted_data

  - [x] 1.4 Write unit tests for API endpoints
    - Test POST /upload with valid and invalid requests
    - Test GET /status with various upload states
    - Test session creation and retrieval
    - Test review/approve/reject workflow
    - Test authentication and authorization

- [x] 2. Saldenliste Parser and Import
  - [x] 2.1 Create SaldenlisteParser service
    - Create `backend/app/services/saldenliste_parser.py`
    - Implement `SaldenlisteData` and `AccountBalance` dataclasses
    - Implement `parse_csv()` method for CSV format
    - Implement `parse_excel()` method using openpyxl
    - Implement `detect_format()` for auto-detection (BMD, RZL, custom)
    - Add account number normalization logic
    - Note: Kontenplan mapping already exists in `saldenliste_service.py`

  - [x] 2.2 Create SaldenlisteImportService
    - Create `backend/app/services/saldenliste_import_service.py`
    - Implement `import_saldenliste()` method (parse → map → create transactions)
    - Implement `create_opening_balance_transactions()` method
    - Add multi-year continuity validation (closing balance N = opening balance N+1)
    - Integrate with HistoricalImportUpload model
    - Reuse Kontenplan mapping from `saldenliste_service.py`

  - [x] 2.3 Write unit tests for Saldenliste import
    - Test CSV parsing with sample files
    - Test Excel parsing with sample files
    - Test format auto-detection
    - Test multi-year continuity validation
    - Test opening balance transaction creation

- [x] 3. Kaufvertrag Import Enhancement
  - [x] 3.1 Create KaufvertragImportService
    - Create `backend/app/services/kaufvertrag_import_service.py`
    - Implement `import_from_ocr_text()` method (extract → create property → create transactions)
    - Implement `create_or_update_property()` method (with deduplication)
    - Implement `create_purchase_cost_transactions()` method (Grunderwerbsteuer, Eintragungsgebühr, Notarkosten)
    - Implement `initialize_depreciation_schedule()` method
    - Integrate with existing `KaufvertragExtractor` and `HistoricalDepreciationService`
    - Use `AddressMatcher` for property deduplication

  - [x] 3.2 Write unit tests for Kaufvertrag import
    - Test property creation with sample Kaufvertrag data
    - Test property deduplication logic
    - Test depreciation schedule initialization
    - Test purchase cost transaction creation

- [x] 4. Orchestration and Reconciliation
  - [x] 4.1 Create HistoricalImportOrchestrator
    - Create `backend/app/services/historical_import_orchestrator.py`
    - Implement `create_session()` method (create HistoricalImportSession)
    - Implement `process_upload()` method to coordinate extraction and import
      - Route to appropriate service based on document_type
      - Update HistoricalImportUpload with results
      - Handle errors and set requires_review flag
    - Implement `finalize_session()` method with summary generation
    - Add session state management (active, completed, failed)
    - Integrate with all import services (E1, Bescheid, Kaufvertrag, Saldenliste)

  - [x] 4.2 Create DataReconciliationService
    - Create `backend/app/services/data_reconciliation_service.py`
    - Implement `detect_conflicts()` method (compare same tax year, same field across documents)
    - Implement `reconcile_income_amounts()` method (E1 vs Bescheid income comparison)
    - Implement `suggest_resolution()` method (use higher confidence source)
    - Create ImportConflict records for detected conflicts (>1% difference threshold)

  - [x] 4.3 Enhance DuplicateDetector for cross-document detection
    - Modify `backend/app/services/duplicate_detector.py`
    - Add `detect_cross_document_duplicates()` method
    - Implement fuzzy matching for similar transactions (same amount, date, category)
    - Add confidence scoring for duplicate matches
    - Prevent duplicates across E1, Bescheid, and other sources

  - [x] 4.4 Write unit tests for orchestration
    - Test session creation and management
    - Test multi-document coordination
    - Test conflict detection logic
    - Test duplicate prevention

- [x] 5. Review Interface and Finalization
  - [x] 5.1 Implement review and approval logic in orchestrator
    - Add `review_upload()` method to HistoricalImportOrchestrator
    - Support editing extracted data (store in edited_data field)
    - Implement approval workflow (approved=true → finalize import)
    - Implement rejection workflow (approved=false → cleanup)
    - Update HistoricalImportUpload status and metadata

  - [x] 5.2 Implement data finalization logic
    - Add `finalize_upload()` method to orchestrator
    - Create transactions from approved extracted data
    - Link properties based on approved suggestions
    - Mark transactions as reviewed and locked (prevent auto-modifications)
    - Update user profile with extracted tax information

  - [x] 5.3 Implement rejection cleanup logic
    - Add `reject_upload()` method to orchestrator
    - Delete all associated transactions on rejection
    - Remove property links created during import
    - Delete depreciation schedules
    - Allow clean re-import after rejection

  - [x] 5.4 Write unit tests for review workflow
    - Test approval with valid edited data
    - Test rejection with cleanup
    - Test partial edits
    - Test validation errors
    - Test transaction locking after approval

- [x] 6. Metrics and Analytics
  - [x] 6.1 Implement ImportMetrics logging in orchestrator
    - Add metrics logging to all import operations
    - Log extraction confidence, field-level accuracy, processing time
    - Log errors and warnings
    - Create ImportMetrics records in database (already modeled)

  - [x] 6.2 Implement user correction capture for ML training
    - Capture original extracted value vs corrected value in review workflow
    - Store field name and correction type
    - Add to ImportMetrics.corrections JSONB field
    - Calculate field-level accuracy metrics

  - [x] 6.3 Write unit tests for metrics and analytics
    - Test metrics logging for successful imports
    - Test metrics logging for failed imports
    - Test correction capture
    - Test field-level accuracy calculation

- [x] 7. Error Handling and Validation
  - [x] 7.1 Implement comprehensive error handling in orchestrator
    - Add graceful degradation for extraction errors (partial success)
    - Implement rollback mechanisms for critical errors
    - Implement retry logic for transient errors (OCR, network)
    - Store error details in HistoricalImportUpload.errors

  - [x] 7.2 Create localized error messages
    - Create error message dictionary with de, en, zh translations
    - Add error messages for extraction failures, validation errors, conflicts
    - Implement error message formatting with parameters
    - Use i18next format for consistency with frontend

  - [x] 7.3 Write unit tests for error handling
    - Test graceful degradation
    - Test partial success scenarios
    - Test rollback on critical errors
    - Test retry logic

- [x] 8. Integration and Documentation
  - [x] 8.1 Wire all components together
    - Integrate orchestrator with API endpoints
    - Connect all import services to orchestrator
    - Wire review workflow to finalization logic
    - Add metrics logging to all operations

  - [x] 8.2 Add environment configuration
    - Add HISTORICAL_IMPORT_MAX_FILE_SIZE_MB to .env.example
    - Add HISTORICAL_IMPORT_RETENTION_DAYS to .env.example
    - Add HISTORICAL_IMPORT_MIN_CONFIDENCE to .env.example
    - Add HISTORICAL_IMPORT_ENABLE_AUTO_LINK to .env.example
    - Document configuration options

  - [x] 8.3 Create MinIO bucket for historical imports
    - Add bucket creation to deployment scripts
    - Set appropriate access policies
    - Document bucket structure

  - [x] 8.4 Write integration tests for complete workflow
    - Test complete upload → extract → review → approve workflow
    - Test multi-document session workflow
    - Test conflict resolution workflow
    - Test rejection and re-import workflow

  - [x] 8.5 Write E2E test for historical import
    - Test complete user journey from upload to finalized import
    - Test with real anonymized document samples
    - Verify all data correctly created in database

## Notes

- All Python code should follow Black formatting (line length 100), Ruff linting, and MyPy type checking
- Database models (HistoricalImportSession, HistoricalImportUpload, ImportConflict, ImportMetrics) are already created
- Existing services (E1FormImportService, BescheidImportService, AddressMatcher, DuplicateDetector, HistoricalDepreciationService) should be reused and enhanced
- All API endpoints should use FastAPI with proper authentication and authorization
- All schemas should use Pydantic with comprehensive validation
- OCR processing should use Celery for async execution
- Error messages should be localized (German, English, Chinese) using i18next format
- Focus on incremental implementation - each phase should be testable independently
