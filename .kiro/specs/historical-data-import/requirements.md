# Feature Requirements: Historical Data Import

## Overview

Enable users to import historical tax and financial data from previous years to establish baseline data for multi-year tax calculations, loss carryforward tracking, and property depreciation schedules. This feature consolidates and enhances existing document extraction capabilities (E1 forms, Bescheid, Kaufvertrag) into a unified historical data import workflow.

## User Stories and Requirements

### Requirement 1

**User Story:** As a new user, I want to import my previous year's E1 tax declaration form, so that the system has my historical income and deduction data for accurate tax calculations.

#### Acceptance Criteria

1. WHEN a user uploads an E1 form PDF THEN the system SHALL extract all KZ (Kennzahl) values including income categories (245, 210, 220, 350, 370, 390) and deductions (260, 261, 263, 450, 458, 459)
2. WHEN E1 data is extracted THEN the system SHALL create corresponding income and expense transactions dated to the tax year
3. WHEN rental income (KZ 350) is detected in an E1 form THEN the system SHALL suggest property linking with confidence scores
4. WHEN E1 import completes THEN the system SHALL update user profile with tax number and family information if not already set
5. WHEN E1 extraction confidence is below 0.7 THEN the system SHALL flag the import for manual review

### Requirement 2

**User Story:** As a landlord, I want to import my Einkommensteuerbescheid (tax assessment), so that the system can extract my rental property addresses and link them to my property portfolio.

#### Acceptance Criteria

1. WHEN a user uploads a Bescheid PDF THEN the system SHALL extract tax year, taxpayer name, Steuernummer, Finanzamt, and all income/deduction amounts
2. WHEN Bescheid contains Vermietung und Verpachtung details with addresses THEN the system SHALL use AddressMatcher to find matching properties with confidence scores
3. WHEN address matching confidence exceeds 0.9 THEN the system SHALL suggest auto-linking the transaction to the property
4. WHEN address matching confidence is between 0.7-0.9 THEN the system SHALL present the property as a suggestion for user confirmation
5. WHEN no matching property is found THEN the system SHALL suggest creating a new property with the extracted address

### Requirement 3

**User Story:** As a property owner, I want to import my Kaufvertrag (purchase contract), so that the system can establish the property's acquisition cost basis for depreciation calculations.

#### Acceptance Criteria

1. WHEN a user uploads a Kaufvertrag PDF THEN the system SHALL extract property address, purchase price, purchase date, value breakdown (land/building), and purchase costs
2. WHEN Kaufvertrag data is extracted THEN the system SHALL create or update a property record with acquisition details
3. WHEN building value is extracted THEN the system SHALL initialize historical depreciation schedule from the purchase date
4. WHEN purchase costs are extracted THEN the system SHALL create expense transactions for Grunderwerbsteuer, Eintragungsgebühr, and Notarkosten
5. WHEN Kaufvertrag extraction confidence is below 0.6 THEN the system SHALL require manual verification before creating property records

### Requirement 4

**User Story:** As a self-employed user, I want to import my Saldenliste (balance list) from previous years, so that the system has my historical account balances for comparative reporting.

#### Acceptance Criteria

1. WHEN a user uploads a Saldenliste CSV or Excel file THEN the system SHALL parse account numbers, account names, and balance amounts
2. WHEN Saldenliste data is imported THEN the system SHALL map accounts to the appropriate Kontenplan (EA or GmbH) based on user type
3. WHEN account balances are imported THEN the system SHALL create summary transactions for each account to establish opening balances
4. WHEN imported accounts don't match the standard Kontenplan THEN the system SHALL flag unmapped accounts for user review
5. WHEN Saldenliste contains multiple years THEN the system SHALL import each year separately and maintain year-over-year continuity

### Requirement 5

**User Story:** As a user, I want a unified import workflow that handles multiple document types, so that I can efficiently onboard my historical tax data in one session.

#### Acceptance Criteria

1. WHEN a user initiates historical data import THEN the system SHALL present a guided workflow showing E1, Bescheid, Kaufvertrag, and Saldenliste import options
2. WHEN multiple documents are uploaded in sequence THEN the system SHALL detect duplicate data and prevent double-counting of transactions
3. WHEN documents from the same tax year are imported THEN the system SHALL reconcile conflicting data and highlight discrepancies for user resolution
4. WHEN all imports complete THEN the system SHALL generate a summary report showing transactions created, properties linked, and data quality metrics
5. WHEN import errors occur THEN the system SHALL provide clear error messages with suggestions for resolution without losing already-imported data

### Requirement 6

**User Story:** As a user, I want the system to validate imported historical data against Austrian tax rules, so that I can trust the accuracy of my tax calculations.

#### Acceptance Criteria

1. WHEN historical transactions are imported THEN the system SHALL validate that income categories match Austrian Einkunftsarten (7 categories)
2. WHEN deduction amounts are imported THEN the system SHALL verify they comply with Austrian tax law limits (e.g., Werbungskosten Pauschale, Pendlerpauschale)
3. WHEN property depreciation is calculated from historical data THEN the system SHALL apply correct AfA rates (1.5% for buildings, 2% for pre-1915)
4. WHEN loss carryforward is detected in historical data THEN the system SHALL create loss carryforward records with proper year tracking
5. WHEN validation errors are found THEN the system SHALL flag specific issues with references to relevant tax law sections

### Requirement 7

**User Story:** As a user, I want to review and approve imported historical data before it's finalized, so that I can correct any extraction errors.

#### Acceptance Criteria

1. WHEN document extraction completes THEN the system SHALL display extracted data in an editable review interface
2. WHEN a user edits extracted values THEN the system SHALL update the corresponding transactions or property records
3. WHEN a user approves imported data THEN the system SHALL mark transactions as reviewed and lock them from automatic modifications
4. WHEN a user rejects imported data THEN the system SHALL delete the associated transactions and allow re-import
5. WHEN extraction confidence is low (<0.7) THEN the system SHALL require explicit user approval before finalizing the import

### Requirement 8

**User Story:** As a system administrator, I want to track import success rates and common extraction errors, so that I can improve the OCR and extraction algorithms.

#### Acceptance Criteria

1. WHEN any document import occurs THEN the system SHALL log extraction confidence scores, field-level accuracy, and processing time
2. WHEN extraction errors occur THEN the system SHALL capture the error type, affected fields, and document characteristics
3. WHEN users correct extracted data THEN the system SHALL record the corrections as training data for ML model improvement
4. WHEN import analytics are requested THEN the system SHALL provide aggregated metrics by document type, tax year, and user type
5. WHEN extraction patterns change THEN the system SHALL alert administrators to potential OCR or parsing issues

## Non-Functional Requirements

### Performance
- Document OCR processing SHALL complete within 30 seconds for standard PDFs (<10 pages)
- Batch import of multiple documents SHALL process asynchronously with progress tracking
- Historical data import SHALL not block current-year transaction entry

### Security
- Imported documents SHALL be encrypted at rest using AES-256
- Historical data SHALL be isolated by user_id with no cross-user access
- Document deletion SHALL cascade to remove all associated extracted data

### Usability
- Import workflow SHALL support German, English, and Chinese languages
- Error messages SHALL be clear and actionable for non-technical users
- Mobile-responsive interface SHALL support document upload via camera

### Data Quality
- Extraction confidence scores SHALL be calibrated to minimize false positives
- Duplicate detection SHALL prevent importing the same document twice
- Data reconciliation SHALL preserve user-entered data over imported data when conflicts occur

## Success Metrics

- 80% of E1 forms extracted with confidence >0.8
- 70% of Bescheid addresses automatically matched to properties
- 90% of Kaufvertrag purchase prices extracted correctly
- 95% of users complete historical import without support intervention
- Average import time <5 minutes for 3-year historical data

## Dependencies

- Existing OCR infrastructure (Tesseract + OpenCV)
- E1FormExtractor, BescheidExtractor, KaufvertragExtractor services
- AddressMatcher for property linking
- HistoricalDepreciationService for property depreciation
- DuplicateDetector for transaction deduplication

## Out of Scope

- Importing bank statements (covered by separate transaction import feature)
- Importing foreign tax documents (non-Austrian)
- Automated filing with FinanzOnline (system is reference only)
- Importing pre-2015 data (tax law changes make older data less relevant)
