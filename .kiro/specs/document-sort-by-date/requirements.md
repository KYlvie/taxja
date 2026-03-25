# Requirements Document

## Introduction

Taxja's document page currently sorts and groups documents exclusively by upload date (`created_at`). Users — especially those handing documents to accountants organized by fiscal year — need the ability to sort and group by the actual document date extracted via OCR (e.g. invoice date, receipt date). This feature adds a sort-mode toggle (upload date vs. document date) that affects the year-based grouping, list ordering, and ZIP export folder structure across all 9 supported locales.

## Glossary

- **Document_List**: The React component (`DocumentList.tsx`) that renders the paginated, year-grouped list of uploaded documents.
- **Sort_Mode**: A user-selectable option that determines which date field drives sorting and year-grouping. Valid values: `upload_date` (uses `uploaded_at` / `created_at`) and `document_date` (uses the OCR-extracted date).
- **Document_Date**: The primary date extracted from a document's OCR result. Resolved by checking `ocr_result.document_date`, then `ocr_result.date`, then `ocr_result.invoice_date`, then `ocr_result.receipt_date`, then `ocr_result.purchase_date`, then `ocr_result.start_date` — in that priority order.
- **Upload_Date**: The timestamp when the document was uploaded to the system (`uploaded_at` column / `created_at` frontend field).
- **Documents_API**: The FastAPI endpoint `GET /api/v1/documents` that returns paginated document lists.
- **Export_API**: The FastAPI endpoint `GET /api/v1/documents/export` that produces a ZIP archive of documents.
- **Sort_Mode_Selector**: A UI control on the documents page that lets the user switch between `upload_date` and `document_date` sort modes.

## Requirements

### Requirement 1: Sort Mode Selection

**User Story:** As a taxpayer, I want to choose whether documents are sorted by upload date or by the OCR-recognized document date, so that I can view documents in the order that matches my accounting workflow.

#### Acceptance Criteria

1. THE Document_List SHALL display a Sort_Mode_Selector with two options: sort by Upload_Date and sort by Document_Date.
2. WHEN the user selects a Sort_Mode, THE Document_List SHALL re-sort and re-group all visible documents according to the selected Sort_Mode within 300ms.
3. THE Sort_Mode_Selector SHALL default to `upload_date` to preserve existing behavior.
4. WHEN the user changes the Sort_Mode, THE Document_List SHALL persist the selected Sort_Mode in the browser's local storage so that the preference survives page reloads.
5. THE Sort_Mode_Selector labels SHALL be translated for all 9 supported locales (zh, en, de, fr, hu, bs, pl, ru, tr).

### Requirement 2: Document Date Resolution

**User Story:** As a taxpayer, I want the system to reliably extract the document date from OCR results, so that sorting by document date produces accurate year groupings.

#### Acceptance Criteria

1. THE Document_List SHALL resolve Document_Date by checking OCR result fields in this priority order: `document_date`, `date`, `invoice_date`, `receipt_date`, `purchase_date`, `start_date`.
2. WHEN none of the OCR date fields contain a valid date, THE Document_List SHALL fall back to the Upload_Date for that document.
3. THE Document_List SHALL treat a date field as valid only when the field is a non-empty string that parses to a valid calendar date.
4. WHEN a document has no OCR result at all, THE Document_List SHALL use the Upload_Date for sorting and grouping that document.

### Requirement 3: Year-Based Grouping by Sort Mode

**User Story:** As a taxpayer preparing documents for my accountant, I want documents grouped by year according to my chosen sort mode, so that I can quickly find all documents belonging to a specific fiscal year.

#### Acceptance Criteria

1. WHEN Sort_Mode is `upload_date`, THE Document_List SHALL group documents by the year of each document's Upload_Date.
2. WHEN Sort_Mode is `document_date`, THE Document_List SHALL group documents by the year of each document's resolved Document_Date.
3. THE Document_List SHALL display year groups in descending order (most recent year first).
4. WITHIN each year group, THE Document_List SHALL sort documents in descending date order according to the active Sort_Mode.

### Requirement 4: Backend Sort Mode Support

**User Story:** As a taxpayer, I want the backend to support sorting by document date, so that paginated results and date-range filters work correctly regardless of sort mode.

#### Acceptance Criteria

1. THE Documents_API SHALL accept an optional `sort_by` query parameter with values `upload_date` (default) and `document_date`.
2. WHEN `sort_by` is `upload_date`, THE Documents_API SHALL order results by the `uploaded_at` column descending.
3. WHEN `sort_by` is `document_date`, THE Documents_API SHALL order results by the resolved Document_Date descending, falling back to `uploaded_at` for documents without a valid OCR date.
4. WHEN `sort_by` is `document_date` and `start_date`/`end_date` filters are provided, THE Documents_API SHALL apply those date-range filters against the resolved Document_Date instead of `uploaded_at`.
5. IF an invalid value is provided for `sort_by`, THEN THE Documents_API SHALL return HTTP 422 with a descriptive validation error.

### Requirement 5: Materialized Document Date Column

**User Story:** As a developer, I want a dedicated database column for the resolved document date, so that backend sorting and filtering by document date is efficient and does not require JSON parsing at query time.

#### Acceptance Criteria

1. THE Document model SHALL include a nullable `document_date` column of type `DateTime`.
2. WHEN OCR processing completes for a document, THE system SHALL populate the `document_date` column with the resolved Document_Date extracted from the OCR result.
3. WHEN no valid date is found in the OCR result, THE system SHALL leave the `document_date` column as NULL.
4. THE system SHALL provide an Alembic migration that adds the `document_date` column with a default of NULL, ensuring backward compatibility with existing rows.
5. THE system SHALL include a one-time data backfill step in the migration that populates `document_date` for all existing documents that have OCR results containing a valid date.

### Requirement 6: ZIP Export with Year Folders

**User Story:** As a taxpayer, I want to export documents as a ZIP file organized into year-based folders according to my chosen sort mode, so that I can hand the accountant a neatly organized archive.

#### Acceptance Criteria

1. THE Export_API SHALL accept an optional `sort_by` query parameter with values `upload_date` (default) and `document_date`.
2. WHEN `sort_by` is `upload_date`, THE Export_API SHALL place each document file into a subfolder named by the year of its Upload_Date (e.g. `2024/invoice.pdf`).
3. WHEN `sort_by` is `document_date`, THE Export_API SHALL place each document file into a subfolder named by the year of its resolved Document_Date.
4. WHEN a document has no resolved Document_Date and `sort_by` is `document_date`, THE Export_API SHALL place that document into a subfolder named `unknown`.
5. THE Export_API SHALL handle duplicate file names within the same year folder by appending a numeric suffix (e.g. `invoice_1.pdf`).

### Requirement 7: Backward Compatibility

**User Story:** As an existing user, I want the system to behave exactly as before unless I explicitly choose a different sort mode, so that the update does not disrupt my current workflow.

#### Acceptance Criteria

1. THE Documents_API SHALL default to `upload_date` sorting when the `sort_by` parameter is omitted.
2. THE Export_API SHALL produce a flat file list (no year subfolders) when the `sort_by` parameter is omitted, preserving the current export behavior.
3. THE Document_List SHALL default to `upload_date` sort mode when no preference is stored in local storage.
4. THE Alembic migration SHALL be non-destructive: the new `document_date` column SHALL be nullable and SHALL NOT alter or remove any existing columns.
