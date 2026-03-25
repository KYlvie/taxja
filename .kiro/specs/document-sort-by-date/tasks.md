# Implementation Plan: Document Sort by Date

## Overview

Add the ability to sort and group documents by OCR-extracted document date in addition to upload date. Implementation flows backend-first (DB migration → API changes → schema updates) then frontend (store → service → components → i18n). Backward compatibility is preserved throughout — all defaults remain `upload_date`.

## Tasks

- [x] 1. Database migration and model changes
  - [x] 1.1 Add `document_date` column to Document model
    - Add `document_date = Column(Date, nullable=True, index=True)` to `backend/app/models/document.py`
    - _Requirements: 5.1_

  - [x] 1.2 Create Alembic migration `072_add_document_date_column.py`
    - Add `document_date DATE NULL` column to `documents` table
    - Create index `ix_documents_document_date` on the new column
    - Include batched data backfill (500 rows per batch) that populates `document_date` for existing rows with non-null `ocr_result`, using the priority chain: `document_date` → `date` → `invoice_date` → `receipt_date` → `purchase_date` → `start_date`
    - Migration must be non-destructive: nullable column, no existing columns altered or removed
    - _Requirements: 5.4, 5.5, 7.4_

- [x] 2. Document date resolver service
  - [x] 2.1 Create `backend/app/services/document_date_resolver.py`
    - Implement `resolve_document_date(ocr_result: Optional[dict]) -> Optional[date]` using the priority chain: `document_date`, `date`, `invoice_date`, `receipt_date`, `purchase_date`, `start_date`
    - Return `None` when no valid date is found or `ocr_result` is None/not a dict
    - Validate each field is a non-empty string that parses to a valid calendar date via `date.fromisoformat(value[:10])`
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 2.2 Write property test for document date resolver
    - **Property 1: Priority chain ordering** — given an OCR result with multiple date fields populated, `resolve_document_date` always returns the value of the highest-priority field
    - **Property 2: Fallback to None** — given an OCR result with no valid date fields (empty strings, invalid dates, missing keys), `resolve_document_date` returns None
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4**

- [x] 3. OCR pipeline integration
  - [x] 3.1 Update OCR task to populate `document_date` column
    - In `backend/app/tasks/ocr_tasks.py`, after OCR processing writes `ocr_result`, call `resolve_document_date(ocr_result)` and write the result to `document.document_date`
    - Leave `document_date` as NULL when resolver returns None
    - _Requirements: 5.2, 5.3_

- [x] 4. Checkpoint — Ensure migration, resolver, and OCR integration are correct
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Backend API: Documents endpoint sort support
  - [x] 5.1 Add `SortByOption` enum and `sort_by` query parameter to `GET /api/v1/documents`
    - Create `SortByOption(str, Enum)` with values `upload_date` and `document_date`
    - Add `sort_by: Optional[SortByOption] = Query(None)` parameter
    - When omitted or `upload_date`: `ORDER BY uploaded_at DESC` (current behavior)
    - When `document_date`: `ORDER BY COALESCE(document_date, uploaded_at) DESC`
    - When `sort_by=document_date` and `start_date`/`end_date` filters provided, apply filters against `COALESCE(document_date, uploaded_at)` instead of `uploaded_at`
    - Return HTTP 422 for invalid `sort_by` values (handled by FastAPI/Pydantic enum validation)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 7.1, 7.2, 7.3_

  - [x] 5.2 Write property test for documents API sort behavior
    - **Property 3: Sort order consistency** — for any set of documents, when `sort_by=document_date`, results are ordered by `COALESCE(document_date, uploaded_at)` descending
    - **Property 4: Default backward compatibility** — when `sort_by` is omitted, results are ordered by `uploaded_at` descending, identical to pre-feature behavior
    - **Validates: Requirements 4.1, 4.2, 4.3, 7.1, 7.2**

- [x] 6. Backend API: Export ZIP sort support
  - [x] 6.1 Add `sort_by` query parameter to `GET /api/v1/documents/export-zip`
    - When omitted: flat file list with no year subfolders (current behavior preserved)
    - When `upload_date`: files placed in `{year}/` subfolders based on `uploaded_at`
    - When `document_date`: files placed in `{year}/` subfolders based on `document_date`, with `unknown/` subfolder for documents where `document_date` is NULL
    - Handle duplicate filenames within the same folder by appending numeric suffix (e.g. `invoice_1.pdf`)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 7.2_

  - [x] 6.2 Write property test for export ZIP folder structure
    - **Property 5: Year folder correctness** — when `sort_by=document_date`, every document with a non-null `document_date` is placed in a folder matching its document date year; documents with null `document_date` are placed in `unknown/`
    - **Property 6: No duplicate filenames** — within any single year folder, all filenames are unique (suffixed as needed)
    - **Validates: Requirements 6.2, 6.3, 6.4, 6.5**

- [x] 7. Backend schema update
  - [x] 7.1 Add `document_date` field to Pydantic `DocumentDetail` schema
    - Add `document_date: Optional[date] = None` to `backend/app/schemas/document.py` so the frontend receives the materialized date
    - _Requirements: 5.1_

- [x] 8. Checkpoint — Ensure all backend changes are correct
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Frontend: Zustand store and service layer
  - [x] 9.1 Add `sortMode` state to document store
    - In `frontend/src/stores/documentStore.ts`, add `sortMode: SortMode` (type `'upload_date' | 'document_date'`) and `setSortMode(mode: SortMode)` action
    - On initialization, read from `localStorage` key `taxja_doc_sort_mode` with fallback to `'upload_date'`
    - `setSortMode` persists to localStorage and triggers document re-fetch
    - _Requirements: 1.3, 1.4_

  - [x] 9.2 Update document service to pass `sort_by` parameter
    - In `frontend/src/services/documentService.ts`, pass `sort_by` query param to `GET /api/v1/documents` when sort mode is not the default
    - Similarly pass `sort_by` to the export ZIP endpoint when provided
    - _Requirements: 4.1, 6.1_

- [x] 10. Frontend: Document date resolver utility
  - [x] 10.1 Create `frontend/src/utils/documentDateResolver.ts`
    - Implement `resolveDocumentDate(doc: Document): Date` using the priority chain on `doc.ocr_result`, falling back to `doc.created_at`
    - _Requirements: 2.1, 2.2, 2.4_

  - [x] 10.2 Write unit tests for `resolveDocumentDate`
    - Test priority chain ordering, fallback to `created_at`, handling of missing/invalid OCR fields
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 11. Frontend: DocumentList component updates
  - [x] 11.1 Add `SortModeSelector` UI control to DocumentList
    - Add a `<Select>` control in the toolbar area of `frontend/src/components/documents/DocumentList.tsx`
    - Wire to `documentStore.setSortMode`
    - Default selection: `upload_date`
    - _Requirements: 1.1, 1.2, 1.3_

  - [x] 11.2 Update year-grouping and sorting logic in DocumentList
    - When `upload_date` mode: group/sort by `doc.created_at` (current behavior)
    - When `document_date` mode: group/sort by `resolveDocumentDate(doc)`
    - Year groups displayed in descending order, documents within each group sorted descending by active sort mode date
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 12. Frontend: i18n translations for all 9 locales
  - [x] 12.1 Add translation keys for sort mode selector
    - Add keys `documents.sortMode.label`, `documents.sortMode.uploadDate`, `documents.sortMode.documentDate` to all 9 locale files: zh, en, de, fr, hu, bs, pl, ru, tr
    - _Requirements: 1.5_

- [x] 13. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests use the Hypothesis library (backend) and vitest (frontend)
- Backend changes are ordered first to ensure the API contract is stable before frontend integration
- Backward compatibility is maintained at every step: all defaults remain `upload_date`
