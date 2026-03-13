# Implementation Plan: Austrian Tax Management System (Taxja)

## Current Status Summary (Updated: March 4, 2026)

### Overall Progress: 33/38 tasks complete (87%)

**Backend Status:** ✅ COMPLETE
- All core features implemented and tested
- 200+ integration tests passing (auth, transactions, OCR, tax calculation, reports, AI assistant, E2E)
- Property-based tests validating tax calculations
- Comprehensive E2E tests covering all critical user journeys
- Ready for deployment

**Frontend Status:** ⚠️ NEEDS ATTENTION
- All features implemented (Tasks 25-32)
- Build currently failing due to:
  - Missing dependencies (`lucide-react`, `react-markdown`)
  - 40 TypeScript errors
  - No unit tests written
- Estimated fix time: ~1 hour

**Testing Status:** ✅ COMPLETE
- ✅ Unit tests: Comprehensive coverage with property-based tests
- ✅ Integration tests: 200+ tests covering all major workflows
  - Authentication (29 tests)
  - Transactions (31 tests)
  - OCR pipeline (31 tests)
  - Tax calculation (7 test classes)
  - Report generation (5 test classes)
  - AI Assistant (6 test classes)
  - E2E user journeys (13 comprehensive tests)
- All critical requirements validated

**Deployment Status:** ⏳ NOT STARTED
- Docker configurations ready
- Kubernetes manifests prepared
- CI/CD pipeline needs setup

### Next Steps
1. **Immediate:** Fix frontend build issues (Task 33)
2. **Short-term:** Deployment and DevOps (Tasks 35-36)
3. **Final:** Documentation and polish (Task 37-38)

---

## Overview

This implementation plan breaks down the Austrian Tax Management System into discrete, manageable coding tasks. The system is a comprehensive tax automation platform for Austrian taxpayers, featuring OCR document recognition, automatic transaction classification, tax calculation (income tax, VAT, social insurance), report generation, FinanzOnline integration, and an AI tax assistant.

The implementation follows a modular approach, building core infrastructure first, then adding features incrementally with testing at each step. Each task references specific requirements for traceability.

## Technology Stack

- **Backend**: Python 3.11+ with FastAPI
- **Frontend**: React 18+ with TypeScript and Vite
- **Database**: PostgreSQL 15+
- **Cache**: Redis 7+
- **Storage**: MinIO (S3-compatible)
- **OCR**: Tesseract 5.0+ with OpenCV
- **Testing**: pytest + Hypothesis (property-based testing)
- **Deployment**: Docker + Kubernetes

## Tasks

- [x] 1. Project setup and infrastructure
  - Initialize backend project with FastAPI, SQLAlchemy, and Alembic
  - Initialize frontend project with React, TypeScript, and Vite
  - Set up Docker Compose for local development (PostgreSQL, Redis, MinIO)
  - Configure environment variables and settings management
  - Set up CI/CD pipeline with GitHub Actions
  - _Requirements: 17.1, 17.2_


- [x] 2. Database schema and core data models
  - [x] 2.1 Create User model with encrypted fields
    - Implement User table with user_type, family_info, commuting_info
    - Implement AES-256-GCM encryption for sensitive fields (tax_number, vat_number, address)
    - Add two-factor authentication fields (two_factor_secret, two_factor_enabled)
    - _Requirements: 11.1, 11.2, 11.3, 17.1, 17.2_

  - [x] 2.2 Write property test for encryption/decryption roundtrip
    - **Property 17: Encryption/decryption roundtrip consistency**
    - **Validates: Requirements 17.1, 17.2**

  - [x] 2.3 Create Transaction model with categories
    - Implement Transaction table with type, amount, date, description
    - Add income_category and expense_category enums
    - Add is_deductible, vat_rate, vat_amount fields
    - Add document_id foreign key for OCR integration
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.7_

  - [x] 2.4 Write property test for transaction unique identifiers
    - **Property 2: Transaction unique identifier**
    - **Validates: Requirements 1.7**

  - [x] 2.5 Create Document model for OCR storage
    - Implement Document table with document_type, file_path, ocr_result
    - Add confidence_score and raw_text fields
    - Add transaction_id foreign key
    - _Requirements: 19.1, 19.8, 19.9, 24.1_

  - [x] 2.6 Create TaxConfiguration model for yearly tax rates
    - Implement TaxConfiguration table with tax_year, tax_brackets, vat_rates, svs_rates
    - Add deduction_config JSON field
    - Seed 2026 tax rates from USP official tables
    - _Requirements: 3.1, 3.2, 3.3, 3.9, 13.1, 13.2_

  - [x] 2.7 Create LossCarryforward and TaxReport models
    - Implement LossCarryforward table for multi-year loss tracking
    - Implement TaxReport table for generated reports
    - _Requirements: 36.1, 36.2, 7.1, 7.2_

  - [x] 2.8 Run database migrations and verify schema
    - Create Alembic migration scripts
    - Test migrations on clean database
    - _Requirements: 9.1, 9.2_

- [x] 3. Checkpoint - Database schema complete
  - Ensure all tests pass, ask the user if questions arise.


- [x] 4. Authentication and authorization system
  - [x] 4.1 Implement JWT authentication
    - Create authentication service with JWT token generation
    - Implement login endpoint with email/password validation
    - Implement token refresh endpoint
    - Add password hashing with bcrypt
    - _Requirements: 17.3, 17.4_

  - [x] 4.2 Implement two-factor authentication (2FA)
    - Create 2FA setup endpoint with QR code generation (pyotp)
    - Create 2FA verification endpoint
    - Add 2FA requirement to login flow
    - _Requirements: 17.5_

  - [x] 4.3 Write unit tests for authentication
    - Test JWT generation and validation
    - Test 2FA setup and verification
    - Test password hashing
    - _Requirements: 17.3, 17.4, 17.5_

  - [x] 4.4 Implement user registration and profile management
    - Create user registration endpoint
    - Create profile update endpoint
    - Add email validation
    - _Requirements: 11.1, 11.2, 11.7_

- [ ] 5. Tax calculation engine - Income tax
  - [x] 5.1 Implement IncomeTaxCalculator with 2026 USP rates
    - Create IncomeTaxCalculator class with progressive tax calculation
    - Implement 7-bracket tax system (0%, 20%, 30%, 40%, 48%, 50%, 55%)
    - Calculate tax breakdown by bracket
    - Apply exemption amount (€13,539)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.9_

  - [x] 5.2 Write property test for progressive tax monotonicity
    - **Property 5: Progressive tax calculation correctness**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.7, 3.9**

  - [x] 5.3 Write unit tests comparing with USP calculator
    - Test 20+ income scenarios against official USP 2026 calculator
    - Ensure calculation error < €0.01
    - _Requirements: 3.7, 3.9_

  - [x] 5.4 Implement DeductionCalculator
    - Calculate commuting allowance (Pendlerpauschale) with distance brackets
    - Calculate home office deduction (€300/year)
    - Calculate family deductions (Kinderabsetzbetrag)
    - Calculate single parent deduction
    - _Requirements: 29.1, 29.2, 29.3, 29.4, 29.7_

  - [x] 5.5 Write property test for commuting allowance calculation
    - **Property 12: Commuting allowance calculation correctness**
    - **Validates: Requirements 29.2**

  - [x] 5.6 Implement loss carryforward logic
    - Calculate negative income as loss
    - Apply previous year losses to current taxable income
    - Track remaining loss amounts
    - _Requirements: 36.1, 36.2, 36.3, 36.5, 16.5_

  - [x] 5.7 Write property test for loss carryforward
    - **Property 21: Loss carryforward correct propagation**
    - **Validates: Requirements 36.1, 36.2, 36.5, 16.5**


- [x] 6. Tax calculation engine - VAT and SVS
  - [x] 6.1 Implement VATCalculator
    - Calculate VAT liability with small business exemption (€55,000 threshold)
    - Implement tolerance rule (€60,500 threshold)
    - Calculate output VAT (20% standard, 10% residential rental)
    - Calculate input VAT from purchases
    - Calculate net VAT payable
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.6, 4.7, 4.9, 4.10, 4.11, 4.13_

  - [x] 6.2 Write property test for VAT small business exemption
    - **Property 8: VAT small business exemption rules**
    - **Validates: Requirements 4.1, 4.6, 4.7, 4.13**

  - [x] 6.3 Write property test for VAT calculation correctness
    - **Property 9: VAT calculation correctness**
    - **Validates: Requirements 4.2, 4.3, 4.4, 4.9, 4.10, 4.11**

  - [x] 6.4 Implement SVSCalculator for social insurance
    - Calculate GSVG contributions (pension, health, accident, supplementary)
    - Calculate Neue Selbständige contributions
    - Apply minimum and maximum contribution bases
    - Implement dynamic rate calculation
    - _Requirements: 28.1, 28.2, 28.3, 28.4, 28.5, 28.6_

  - [x] 6.5 Write property test for SVS contribution base limits
    - **Property 10: SVS contribution base limits**
    - **Validates: Requirements 28.4, 28.5, 28.6**

  - [x] 6.6 Write property test for SVS deductibility
    - **Property 11: SVS contributions deductibility**
    - **Validates: Requirements 3.6, 28.7**

  - [x] 6.7 Integrate all tax calculators into TaxCalculationEngine
    - Create unified TaxCalculationEngine class
    - Calculate total tax (income tax + VAT + SVS)
    - Calculate net income
    - Generate tax breakdown
    - _Requirements: 3.5, 28.9, 34.6_

  - [x] 6.8 Write property test for tax calculation commutativity
    - **Property 6: Tax calculation commutativity**
    - **Validates: Requirements 16.1**

  - [x] 6.9 Write property test for income/expense summation invariants
    - **Property 7: Income and expense summation invariants**
    - **Validates: Requirements 16.3, 16.4**

- [x] 7. Checkpoint - Tax calculation engine complete
  - Ensure all tests pass, ask the user if questions arise.


- [ ] 8. Transaction management API
  - [x] 8.1 Implement transaction CRUD endpoints
    - Create POST /api/v1/transactions endpoint
    - Create GET /api/v1/transactions endpoint with filtering
    - Create GET /api/v1/transactions/:id endpoint
    - Create PUT /api/v1/transactions/:id endpoint
    - Create DELETE /api/v1/transactions/:id endpoint
    - _Requirements: 1.1, 1.2, 1.5, 1.6_

  - [x] 8.2 Write property test for transaction roundtrip consistency
    - **Property 1: Transaction record roundtrip consistency**
    - **Validates: Requirements 1.1, 1.2, 1.5**

  - [x] 8.3 Implement input validation for transactions
    - Validate required fields (amount, date, description)
    - Validate amount is positive
    - Validate date is not in future
    - Validate category is valid enum value
    - Return clear error messages
    - _Requirements: 1.3, 1.4, 9.1, 9.2, 9.4_

  - [x] 8.4 Write property test for input validation
    - **Property 3: Input validation rejects invalid data**
    - **Validates: Requirements 1.3, 1.4, 9.1, 9.2, 9.4**

  - [x] 8.5 Implement duplicate transaction detection
    - Create DuplicateDetector class
    - Check for same date, amount, and similar description (>80% similarity)
    - Mark duplicates in import results
    - _Requirements: 9.3, 12.9_

  - [x] 8.6 Write property test for duplicate detection
    - **Property 18: Duplicate transaction detection**
    - **Validates: Requirements 9.3, 12.9**

  - [x] 8.7 Implement multi-year data isolation
    - Filter transactions by tax year
    - Ensure year boundaries are respected
    - _Requirements: 10.1, 10.2_

  - [x] 8.8 Write property test for multi-year data isolation
    - **Property 19: Multi-year data isolation**
    - **Validates: Requirements 10.1, 10.2**


- [x] 9. Transaction classification system
  - [x] 9.1 Implement RuleBasedClassifier
    - Create classification rules for common Austrian merchants (BILLA, SPAR, HOFER, etc.)
    - Implement pattern matching for transaction descriptions
    - Return category and confidence score
    - _Requirements: 2.1, 2.2, 26.1, 26.2, 26.3_

  - [x] 9.2 Implement MLClassifier with scikit-learn
    - Train classification model on transaction features
    - Extract features from transaction description and amount
    - Predict category with confidence score
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 9.3 Implement TransactionClassifier combining both approaches
    - Use rule-based classifier for high-confidence matches
    - Fall back to ML classifier for uncertain cases
    - Return classification result with confidence
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 9.4 Write property test for classification validity
    - **Property 4: Transaction classification returns valid category**
    - **Validates: Requirements 2.1, 2.2, 2.3**

  - [x] 9.5 Implement DeductibilityChecker
    - Define deduction rules by user type (employee, self-employed, landlord)
    - Check if expense category is deductible for user type
    - Return deductibility status and reason
    - _Requirements: 5.1, 5.2, 6.1, 6.2, 2.6_

  - [x] 9.6 Write property test for deductibility rules
    - **Property 13: Expense deductibility rules**
    - **Validates: Requirements 5.1, 5.2, 6.1, 6.2**

  - [x] 9.7 Implement learning from user corrections
    - Store user corrections in database
    - Retrain ML model periodically with correction data
    - _Requirements: 2.4, 2.5_

  - [x] 9.8 Integrate classifier with transaction creation
    - Auto-classify transactions on creation
    - Mark low-confidence classifications for review
    - _Requirements: 2.1, 2.2, 2.3_

- [x] 10. Checkpoint - Transaction management complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. OCR engine and document processing
  - [x] 11.1 Set up Tesseract OCR with German language support
    - Install Tesseract 5.0+ with deu and eng language packs
    - Configure OCR settings for Austrian documents
    - _Requirements: 19.1, 26.1_

  - [x] 11.2 Implement ImagePreprocessor
    - Resize images to optimal size
    - Enhance contrast and brightness
    - Deskew images
    - Remove noise with OpenCV
    - _Requirements: 25.5, 25.6_

  - [x] 11.3 Implement DocumentClassifier
    - Create pattern-based classifier for document types (payslip, receipt, invoice, etc.)
    - Identify Austrian document formats (Lohnzettel, SVS notice, etc.)
    - Return document type and confidence score
    - _Requirements: 19.2, 20.1, 21.1, 22.1, 26.1, 26.4_

  - [x] 11.4 Implement FieldExtractor for receipts
    - Extract date (DD.MM.YYYY format)
    - Extract total amount (€ format)
    - Extract merchant name
    - Extract line items
    - Extract VAT amounts (20%, 10%)
    - _Requirements: 19.3, 19.4, 21.2, 21.3, 21.4_

  - [x] 11.5 Implement FieldExtractor for payslips
    - Extract gross income (Brutto)
    - Extract net income (Netto)
    - Extract withheld tax (Lohnsteuer)
    - Extract social insurance contributions
    - Extract employer name
    - _Requirements: 20.2, 20.3, 20.4_

  - [x] 11.6 Implement FieldExtractor for invoices
    - Extract invoice number
    - Extract date
    - Extract total amount
    - Extract VAT amount
    - Extract supplier name
    - _Requirements: 22.2, 22.3, 22.4_

  - [x] 11.7 Implement MerchantDatabase for Austrian merchants
    - Create database of common Austrian merchants (BILLA, SPAR, HOFER, LIDL, MERKUR, OBI, etc.)
    - Map merchants to categories
    - Support user-defined merchant learning
    - _Requirements: 26.2, 26.3, 26.8_

  - [x] 11.8 Implement OCREngine main processing pipeline
    - Preprocess image
    - Run Tesseract OCR
    - Classify document type
    - Extract fields based on document type
    - Calculate overall confidence score
    - Mark low-confidence results for review
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 23.2, 25.2, 25.4_

  - [x] 11.9 Write property test for OCR data structure integrity
    - **Property 25: OCR extracted data structure integrity**
    - **Validates: Requirements 19.4, 23.2, 25.2, 25.4**

  - [x] 11.10 Implement batch OCR processing with Celery
    - Create Celery task for single document processing
    - Create batch processing endpoint
    - Implement parallel processing with task groups
    - _Requirements: 19.5, 19.6_


- [x] 12. Document storage and management
  - [x] 12.1 Implement MinIO storage service
    - Configure MinIO client with S3-compatible API
    - Implement upload, download, delete operations
    - Enable AES-256 encryption at rest
    - _Requirements: 17.1, 17.2, 24.1_

  - [x] 12.2 Implement document upload API
    - Create POST /api/v1/documents/upload endpoint
    - Validate file format (JPEG, PNG, PDF)
    - Validate file size (max 10MB)
    - Store file in MinIO
    - Save document metadata in database
    - _Requirements: 19.1, 24.2, 25.1_

  - [x] 12.3 Implement batch document upload
    - Create POST /api/v1/documents/batch-upload endpoint
    - Process multiple files in parallel
    - Return batch results with individual statuses
    - _Requirements: 19.5, 19.6_

  - [x] 12.4 Implement document retrieval and search
    - Create GET /api/v1/documents endpoint with filtering
    - Filter by document type, date range, transaction
    - Support full-text search on OCR text
    - _Requirements: 24.3, 24.4, 24.5_

  - [x] 12.5 Implement document download
    - Create GET /api/v1/documents/:id/download endpoint
    - Stream file from MinIO
    - _Requirements: 24.6_

  - [x] 12.6 Implement document archival and retention
    - Mark documents as archived when transaction deleted
    - Implement lifecycle policies for old documents
    - _Requirements: 24.7_

  - [x] 12.7 Write property test for document-transaction association
    - **Property 26: Document archival association integrity**
    - **Validates: Requirements 19.8, 19.9, 24.1, 24.7**

  - [x] 12.8 Integrate OCR with document upload
    - Trigger OCR processing on document upload
    - Store OCR results in document record
    - Create transaction suggestion from OCR data
    - _Requirements: 19.7, 19.8, 20.5, 21.6, 22.6_

- [x] 13. OCR review and correction interface (Backend API)
  - [x] 13.1 Implement OCR review endpoints
    - Create GET /api/v1/documents/:id/review endpoint
    - Create POST /api/v1/documents/:id/confirm endpoint
    - Create POST /api/v1/documents/:id/correct endpoint
    - _Requirements: 23.1, 23.2, 23.3, 23.4, 23.5_

  - [x] 13.2 Implement OCR quality feedback
    - Provide suggestions when confidence < 0.6
    - Return error messages for failed OCR
    - _Requirements: 25.2, 25.3, 25.4, 25.7_

  - [x] 13.3 Write property test for OCR roundtrip validation
    - **Property 27: OCR data extraction roundtrip validation**
    - **Validates: Requirements 27.1, 27.2, 27.3, 27.4**

- [x] 14. Checkpoint - OCR and document management complete
  - Ensure all tests pass, ask the user if questions arise.


- [x] 15. Bank import and data import
  - [x] 15.1 Implement CSVParser for bank statements
    - Support common Austrian bank CSV formats
    - Parse transaction date, amount, description
    - Handle different date formats and decimal separators
    - _Requirements: 12.1, 12.2, 12.3_

  - [x] 15.2 Implement MT940Parser for bank statements
    - Parse MT940 format (SWIFT standard)
    - Extract transaction details
    - _Requirements: 12.4_

  - [x] 15.3 Implement bank import API
    - Create POST /api/v1/transactions/import endpoint
    - Support CSV and MT940 formats
    - Auto-classify imported transactions
    - Detect and filter duplicates
    - Return import summary
    - _Requirements: 12.1, 12.2, 12.5, 12.6, 12.7, 12.8, 12.9_

  - [x] 15.4 Write unit tests for CSV import
    - Test various bank CSV formats
    - Test duplicate detection
    - _Requirements: 12.1, 12.2, 12.9_

  - [x] 15.5 Implement PSD2 API client (optional)
    - Create PSD2 client for direct bank integration
    - Implement OAuth2 flow for bank authorization
    - Fetch transactions from bank API
    - _Requirements: 12.10_

- [x] 16. Report generation and export
  - [x] 16.1 Implement PDFGenerator for tax reports
    - Create PDF templates with ReportLab
    - Generate tax summary report with all sections
    - Include taxpayer information, income/expense summary, tax calculation
    - Support multi-language templates (German, English, Chinese)
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.8, 33.1, 33.2_

  - [x] 16.2 Write property test for tax report completeness
    - **Property 28: Tax report contains required information**
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.8**

  - [x] 16.3 Implement CSVGenerator for data export
    - Export transactions to CSV format
    - Include all transaction fields
    - Support custom date ranges and filters
    - _Requirements: 7.6, 14.1, 14.2_

  - [x] 16.4 Write property test for CSV export/import roundtrip
    - **Property 14: CSV export/import roundtrip consistency**
    - **Validates: Requirements 14.1, 14.2, 14.3, 14.4, 14.5**

  - [x] 16.5 Implement FinanzOnlineXMLGenerator
    - Generate XML according to FinanzOnline 2026 schema
    - Include taxpayer information (Steuernummer, name, address)
    - Include income sections (employment, rental, self-employment)
    - Include deductions (SVS, Pendlerpauschale, etc.)
    - Include tax calculation
    - _Requirements: 8.1, 8.2, 8.3, 15.1, 15.2, 15.3_

  - [x] 16.6 Write property test for XML roundtrip validation
    - **Property 15: FinanzOnline XML roundtrip validation**
    - **Validates: Requirements 15.1, 15.2, 15.3, 15.4**

  - [x] 16.7 Implement XML schema validation
    - Load FinanzOnline XSD schema
    - Validate generated XML against schema
    - Return validation errors if any
    - _Requirements: 8.1, 8.2, 15.5, 15.6_

  - [x] 16.8 Write property test for XML schema compliance
    - **Property 16: XML format complies with FinanzOnline schema**
    - **Validates: Requirements 8.1, 8.2, 15.5, 15.6**

  - [x] 16.9 Implement report generation API
    - Create POST /api/v1/reports/generate endpoint
    - Create GET /api/v1/reports/:id endpoint
    - Create GET /api/v1/reports/:id/pdf endpoint
    - Create GET /api/v1/reports/:id/xml endpoint
    - _Requirements: 7.1, 7.2, 7.5, 7.6, 7.7, 8.3_


- [x] 17. Dashboard and tax simulation
  - [x] 17.1 Implement Dashboard data aggregation
    - Calculate year-to-date income and expenses
    - Calculate estimated tax liability
    - Calculate paid vs. remaining tax
    - Calculate VAT threshold distance
    - Generate income and expense trends
    - _Requirements: 34.1, 34.2, 34.3, 34.7_

  - [x] 17.2 Implement savings suggestion generator
    - Suggest commuting allowance if not claimed
    - Suggest home office deduction if not claimed
    - Suggest flat-rate tax comparison for self-employed
    - Rank suggestions by potential savings
    - _Requirements: 34.5_

  - [x] 17.3 Implement tax calendar
    - Define important Austrian tax deadlines
    - Return upcoming deadlines
    - _Requirements: 8.7, 34.6_

  - [x] 17.4 Implement WhatIfSimulator
    - Simulate adding/removing expenses
    - Simulate income changes
    - Calculate tax difference
    - Provide explanation of changes
    - _Requirements: 34.4_

  - [x] 17.5 Write property test for what-if simulation consistency
    - **Property 24: What-if simulation consistency**
    - **Validates: Requirements 34.4**

  - [x] 17.6 Implement flat-rate tax comparison
    - Calculate tax under actual accounting (Einnahmen-Ausgaben-Rechnung)
    - Calculate tax under flat-rate system (Pauschalierung)
    - Compare both methods and show savings
    - Explain eligibility criteria
    - _Requirements: 31.1, 31.2, 31.3, 31.4, 31.5, 31.6_

  - [x] 17.7 Write property test for flat-rate comparison
    - **Property 22: Flat-rate tax comparison calculation**
    - **Validates: Requirements 31.1, 31.2, 31.3, 31.4**

  - [x] 17.8 Implement dashboard API
    - Create GET /api/v1/dashboard endpoint
    - Create GET /api/v1/dashboard/suggestions endpoint
    - Create GET /api/v1/dashboard/calendar endpoint
    - Create POST /api/v1/tax/simulate endpoint
    - Create GET /api/v1/tax/flat-rate-compare endpoint
    - _Requirements: 34.1, 34.2, 34.3, 34.4, 34.5, 34.6, 34.7_

- [x] 18. Employee tax refund optimization (Arbeitnehmerveranlagung)
  - [x] 18.1 Implement Lohnzettel OCR extraction
    - Extract gross income, withheld tax, withheld SVS
    - Extract employer name and tax year
    - _Requirements: 37.1, 37.2_

  - [x] 18.2 Implement refund calculator
    - Calculate actual tax liability with deductions
    - Compare with withheld tax from Lohnzettel
    - Calculate refund or additional payment amount
    - Generate explanation
    - _Requirements: 37.3, 37.4, 37.5_

  - [x] 18.3 Write property test for refund calculation
    - **Property 23: Employee tax refund calculation correctness**
    - **Validates: Requirements 37.3, 37.4**

  - [x] 18.4 Implement refund API
  - [x] 18.4 Implement refund API
    - Create POST /api/v1/tax/calculate-refund endpoint
    - Create POST /api/v1/tax/calculate-refund-from-transactions endpoint
    - Create GET /api/v1/tax/refund-estimate endpoint
    - Display refund estimate on dashboard
    - _Requirements: 37.6, 37.7_

- [x] 19. Checkpoint - Core backend features complete
  - All core backend features have been implemented and tested
  - Employee refund calculator ready for frontend integration
  - Ready to proceed with audit/compliance features or frontend development

- [x] 20. Audit readiness and compliance
  - [x] 20.1 Implement audit checklist generator
    - Check all transactions have supporting documents
    - Check all deductions are properly documented
    - Check VAT calculations are correct
    - Generate missing document warnings
    - _Requirements: 32.1, 32.2, 32.3, 32.4, 32.5, 32.6_

  - [x] 20.2 Implement GDPR data export
    - Export all user data to JSON
    - Include transactions, documents, tax reports
    - Create ZIP archive with documents
    - _Requirements: 17.6, 17.7_

  - [x] 20.3 Implement GDPR data deletion
    - Delete all user data from database
    - Delete all documents from storage
    - Log deletion in audit log
    - _Requirements: 17.8_

  - [x] 20.4 Implement audit logging
    - Log all user actions (login, transaction create/update/delete, report generation)
    - Store IP address, user agent, timestamp
    - Create audit log query API
    - _Requirements: 17.9_

  - [x] 20.5 Implement disclaimer service
    - Store disclaimer text in multiple languages
    - Check if user accepted disclaimer
    - Require disclaimer acceptance on first use
    - _Requirements: 17.11_

- [x] 21. Tax rate update and admin features
  - [x] 21.1 Implement tax rate update service
    - Create new TaxConfiguration for new year
    - Copy previous year as template
    - Validate tax bracket continuity and rate progression
    - _Requirements: 13.1, 13.2, 13.5_

  - [x] 21.2 Implement admin API for tax rate updates
    - Create POST /api/v1/admin/tax-config endpoint
    - Create PUT /api/v1/admin/tax-config/:year endpoint
    - Notify users of tax rate updates
    - _Requirements: 3.12, 13.3, 13.6_

  - [x] 21.3 Write property test for tax rate update isolation
    - **Property 20: Tax rate updates don't affect historical data**
    - **Validates: Requirements 13.3, 13.4**

  - [x] 21.4 Implement year archival service
    - Generate final reports for all users
    - Move old documents to archive storage
    - Mark transactions as archived
    - _Requirements: 10.3, 10.4, 10.5_

- [x] 22. Error handling and recovery
  - [x] 22.1 Implement global error handlers
    - Handle validation errors with clear messages
    - Handle authentication/authorization errors
    - Handle OCR errors with suggestions
    - Handle tax calculation errors
    - Log all errors
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5_

  - [x] 22.2 Implement data backup service
    - Create daily database backups
    - Create document storage backups
    - Store backups in remote location
    - _Requirements: 18.6_

  - [x] 22.3 Implement data recovery service
    - Restore from backup
    - Validate restored data integrity
    - _Requirements: 18.7_


- [x] 23. AI Tax Assistant with RAG
  - [x] 23.1 Set up vector database for knowledge base
    - Install and configure vector database (e.g., Pinecone, Weaviate, or ChromaDB)
    - Create embeddings for Austrian tax law documents
    - Index 2026 USP tax tables and regulations
    - Index common tax questions and answers
    - _Requirements: 38.2, 38.9_

  - [x] 23.2 Implement document embedding pipeline
    - Split tax documents into chunks
    - Generate embeddings using sentence transformers
    - Store embeddings in vector database
    - _Requirements: 38.2, 38.9_

  - [x] 23.3 Implement RAG retrieval service
    - Query vector database with user question
    - Retrieve top-k relevant document chunks
    - Rank results by relevance
    - _Requirements: 38.2_

  - [x] 23.4 Implement AI Assistant service with LLM integration
    - Integrate with LLM API (OpenAI GPT-4, Anthropic Claude, or local model)
    - Construct prompt with retrieved context and user data
    - Include user's current year transactions and tax summary
    - Generate response in user's language (German, English, Chinese)
    - Append disclaimer to every response
    - _Requirements: 38.2, 38.3, 38.4_

  - [x] 23.5 Implement chat history management
    - Store chat messages in database
    - Retrieve conversation history for context
    - Limit history to recent messages
    - _Requirements: 38.5_

  - [x] 23.6 Implement AI Assistant API endpoints
    - Create POST /api/v1/ai/chat endpoint
    - Create GET /api/v1/ai/history endpoint
    - Create DELETE /api/v1/ai/history endpoint (clear history)
    - _Requirements: 38.1, 38.5, 38.6_

  - [x] 23.7 Implement AI-powered OCR explanation
    - Generate natural language explanation of OCR results
    - Explain why certain items are/aren't deductible
    - _Requirements: 38.7_

  - [x] 23.8 Implement AI-powered what-if suggestions
    - Analyze user's tax situation
    - Suggest optimization strategies
    - Explain potential savings
    - _Requirements: 38.8_

  - [x] 23.9 Implement knowledge base refresh mechanism
    - Admin endpoint to update knowledge base
    - Re-index documents when tax laws change
    - _Requirements: 38.10_

  - [x] 23.10 Write unit tests for AI Assistant
    - Test RAG retrieval accuracy
    - Test response generation
    - Test disclaimer inclusion
    - Test multi-language support
    - _Requirements: 38.2, 38.3, 38.4_

- [x] 24. Checkpoint - Backend implementation complete
  - Ensure all tests pass, ask the user if questions arise.


- [x] 25. Frontend - Project setup and core infrastructure
  - [x] 25.1 Initialize React project with TypeScript and Vite
    - Set up project structure
    - Configure TypeScript
    - Install core dependencies (React Router, Zustand, React Hook Form, Zod)
    - Configure Vite build settings
    - _Requirements: 35.1_

  - [x] 25.2 Set up internationalization (i18next)
    - Install i18next and react-i18next
    - Create translation files for German, English, Chinese
    - Implement language switcher
    - Detect browser language on first visit
    - _Requirements: 33.1, 33.2, 33.3, 33.4, 33.5, 33.6_

  - [x] 25.3 Set up state management with Zustand
    - Create auth store (user, token, login/logout)
    - Create transaction store
    - Create document store
    - Create dashboard store
    - _Requirements: 35.1_

  - [x] 25.4 Set up routing with React Router
    - Define routes for all pages
    - Implement protected routes
    - Implement navigation guards
    - _Requirements: 35.1_

  - [x] 25.5 Set up API client with axios
    - Create axios instance with base URL
    - Add request interceptor for auth token
    - Add response interceptor for error handling
    - _Requirements: 17.3, 17.4_

  - [x] 25.6 Implement responsive layout components
    - Create AppLayout with header, sidebar, main content
    - Create mobile-friendly navigation
    - Implement responsive breakpoints
    - _Requirements: 35.1, 35.2, 35.3, 35.6_

- [x] 26. Frontend - Authentication and user management
  - [x] 26.1 Implement login page
    - Create login form with email and password
    - Add 2FA token input
    - Handle login errors
    - Redirect to dashboard on success
    - _Requirements: 17.3, 17.4, 17.5_

  - [x] 26.2 Implement registration page
    - Create registration form
    - Validate email and password
    - Handle registration errors
    - _Requirements: 11.1, 11.2_

  - [x] 26.3 Implement 2FA setup page
    - Display QR code for 2FA setup
    - Verify 2FA token
    - Enable 2FA on success
    - _Requirements: 17.5_

  - [x] 26.4 Implement user profile page
    - Display user information
    - Edit user profile (name, address, tax number)
    - Update commuting information
    - Update family information
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6_

  - [x] 26.5 Implement disclaimer acceptance modal
    - Show disclaimer on first login
    - Require acceptance before proceeding
    - Support multi-language disclaimer
    - _Requirements: 17.11_


- [x] 27. Frontend - Transaction management
  - [x] 27.1 Implement transaction list page
    - Display transactions in table/list view
    - Filter by date range, type, category
    - Sort by date, amount
    - Pagination
    - _Requirements: 1.1, 1.2, 1.5_

  - [x] 27.2 Implement transaction create/edit form
    - Form fields: type, amount, date, description, category
    - Validate required fields
    - Show deductibility status
    - Link to supporting document
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 27.3 Implement transaction detail view
    - Display all transaction information
    - Show linked document
    - Show classification confidence
    - Allow editing and deletion
    - _Requirements: 1.5, 1.6_

  - [x] 27.4 Implement bulk transaction import
    - Upload CSV file
    - Preview imported transactions
    - Review and confirm import
    - Show duplicate warnings
    - _Requirements: 12.1, 12.2, 12.5, 12.6, 12.7, 12.8_

- [x] 28. Frontend - Document management and OCR
  - [x] 28.1 Implement document upload page
    - Drag-and-drop file upload
    - Camera capture on mobile devices
    - Multiple file upload
    - Show upload progress
    - _Requirements: 19.1, 35.4_

  - [x] 28.2 Implement OCR review interface
    - Display document image
    - Display extracted data in editable form
    - Show confidence scores
    - Highlight low-confidence fields
    - Allow manual correction
    - Confirm and create transaction
    - _Requirements: 19.7, 23.1, 23.2, 23.3, 23.4, 23.5_

  - [x] 28.3 Implement receipt item deductibility checker
    - Display receipt line items
    - Show deductibility status for each item
    - Allow user to confirm/override
    - Calculate total deductible amount
    - _Requirements: 21.5_

  - [x] 28.4 Implement document list and search
    - Display documents in grid/list view
    - Filter by document type, date
    - Search by OCR text
    - View document details
    - Download original document
    - _Requirements: 24.3, 24.4, 24.5, 24.6_

  - [x] 28.5 Implement OCR error handling UI
    - Show clear error messages
    - Provide suggestions for improvement
    - Allow manual data entry fallback
    - _Requirements: 25.2, 25.3, 25.4, 25.7, 25.8_


- [x] 29. Frontend - Dashboard and visualization
  - [x] 29.1 Implement dashboard overview
    - Display year-to-date income and expenses
    - Display estimated tax liability
    - Display paid vs. remaining tax
    - Display net income
    - Show VAT threshold distance (if applicable)
    - _Requirements: 34.1, 34.2, 34.3, 34.7_

  - [x] 29.2 Implement income and expense trend charts
    - Monthly income/expense bar chart
    - Category breakdown pie chart
    - Year-over-year comparison
    - Use Recharts library
    - _Requirements: 34.1_

  - [x] 29.3 Implement savings suggestions panel
    - Display top 3 savings suggestions
    - Show potential savings amount
    - Link to action (e.g., update profile for commuting allowance)
    - _Requirements: 34.5_

  - [x] 29.4 Implement tax calendar widget
    - Display upcoming tax deadlines
    - Highlight overdue items
    - _Requirements: 8.7, 34.6_

  - [x] 29.5 Implement what-if simulator
    - Input form for expense/income changes
    - Real-time tax calculation
    - Display tax difference
    - Show explanation
    - _Requirements: 34.4_

  - [x] 29.6 Implement flat-rate comparison view
    - Display side-by-side comparison
    - Show tax under actual accounting
    - Show tax under flat-rate system
    - Highlight savings
    - Explain eligibility
    - _Requirements: 31.1, 31.2, 31.3, 31.4, 31.5, 31.6_

  - [x] 29.7 Implement employee refund estimate widget
    - Display estimated refund amount prominently
    - Link to refund calculator
    - _Requirements: 37.6, 37.7_

- [x] 30. Frontend - Reports and export
  - [x] 30.1 Implement tax report generation page
    - Select tax year
    - Select report type (PDF, XML, CSV)
    - Select language for PDF
    - Generate and download report
    - _Requirements: 7.1, 7.2, 7.5, 7.6, 7.7_

  - [x] 30.2 Implement report preview
    - Display PDF preview in browser
    - Show XML structure
    - _Requirements: 7.5_

  - [x] 30.3 Implement audit checklist view
    - Display audit readiness checklist
    - Show missing documents warnings
    - Show compliance issues
    - _Requirements: 32.1, 32.2, 32.3, 32.4, 32.5_

  - [x] 30.4 Implement data export page
    - Export all user data (GDPR)
    - Download as ZIP archive
    - _Requirements: 17.6, 17.7_


- [x] 31. Frontend - AI Tax Assistant interface
  - [x] 31.1 Implement AI chat widget
    - Floating chat button on all pages (bottom-right corner)
    - Expandable chat window
    - Mobile-friendly full-screen chat
    - _Requirements: 38.1_

  - [x] 31.2 Implement chat interface
    - Message input with send button
    - Display conversation history
    - Show typing indicator while AI responds
    - Auto-scroll to latest message
    - _Requirements: 38.1, 38.5_

  - [x] 31.3 Implement AI response rendering
    - Render markdown in AI responses
    - Display disclaimer prominently at end of each response
    - Support multi-language responses
    - _Requirements: 38.3, 38.4_

  - [x] 31.4 Implement suggested questions
    - Display common tax questions as quick buttons
    - Context-aware suggestions based on current page
    - _Requirements: 38.1_

  - [x] 31.5 Implement chat history management
    - View past conversations
    - Clear chat history
    - _Requirements: 38.5, 38.6_

  - [x] 31.6 Integrate AI with OCR review
    - "Ask AI about this document" button on OCR review page
    - AI explains OCR results and deductibility
    - _Requirements: 38.7_

  - [x] 31.7 Integrate AI with what-if simulator
    - "Ask AI for suggestions" button on simulator
    - AI provides optimization recommendations
    - _Requirements: 38.8_

- [x] 32. Frontend - PWA and mobile optimization
  - [x] 32.1 Configure PWA with Workbox
    - Create service worker
    - Configure caching strategies
    - Add offline fallback page
    - _Requirements: 35.1, 35.5_

  - [x] 32.2 Create PWA manifest
    - Define app name, icons, theme colors
    - Configure display mode (standalone)
    - _Requirements: 35.1_

  - [x] 32.3 Implement mobile-specific features
    - Camera integration for document capture
    - Touch-optimized UI components
    - Simplified mobile dashboard
    - _Requirements: 35.4, 35.6_

  - [x] 32.4 Optimize for mobile performance
    - Lazy load routes and components
    - Optimize images
    - Minimize bundle size
    - _Requirements: 35.1, 35.2, 35.3_

- [ ] 33. Checkpoint - Frontend implementation complete
  - _Status: NEEDS ATTENTION - All features implemented but build issues exist_
  - _Issues:_
    - Missing npm dependencies: `lucide-react`, `react-markdown`
    - 40 TypeScript errors (unused variables, type mismatches, missing types)
    - 8 ESLint warnings (React Hook dependencies)
    - No frontend unit tests written yet
  - _Action Required:_
    - Install missing dependencies
    - Fix TypeScript errors
    - Verify build passes
    - Consider writing basic smoke tests
  - _Estimated fix time: ~1 hour_


- [x] 34. Integration testing and end-to-end testing
  - [x] 34.1 Write integration tests for authentication flow
    - Test user registration
    - Test login with 2FA
    - Test token refresh
    - _Requirements: 17.3, 17.4, 17.5_
    - _Status: COMPLETE - 29 tests implemented_

  - [x] 34.2 Write integration tests for transaction management
    - Test transaction CRUD operations
    - Test transaction classification
    - Test duplicate detection
    - _Requirements: 1.1, 1.2, 1.5, 1.6, 2.1, 2.2, 9.3_
    - _Status: COMPLETE - 31 tests implemented_

  - [x] 34.3 Write integration tests for OCR pipeline
    - Test document upload and OCR processing
    - Test OCR review and correction
    - Test transaction creation from OCR
    - _Requirements: 19.1, 19.7, 23.1, 23.3_
    - _Status: COMPLETE - 31 tests implemented_

  - [x] 34.4 Write integration tests for tax calculation
    - Test end-to-end tax calculation
    - Test with various user types and scenarios
    - Verify calculation accuracy
    - _Requirements: 3.1, 3.5, 4.1, 28.1_
    - _Status: COMPLETE - 7 test classes covering employees, self-employed, landlords, mixed income, loss carryforward, accuracy validation, and complete workflows_

  - [x] 34.5 Write integration tests for report generation
    - Test PDF generation
    - Test XML generation and validation
    - Test CSV export/import roundtrip
    - _Requirements: 7.1, 7.5, 8.1, 14.1_
    - _Status: COMPLETE - 5 test classes covering PDF (multi-language), XML (FinanzOnline schema), CSV export/import roundtrip, and complete report workflows_

  - [x] 34.6 Write integration tests for AI Assistant
    - Test chat message flow
    - Test RAG retrieval
    - Test response generation
    - Test disclaimer inclusion
    - _Requirements: 38.1, 38.2, 38.3, 38.4_
    - _Status: COMPLETE - 6 test classes covering chat flow, RAG retrieval, multi-language support, disclaimer inclusion, OCR integration, and what-if integration_

  - [x] 34.7 Write end-to-end tests for critical user journeys
    - Test complete tax filing workflow
    - Test OCR to transaction to report flow
    - Test employee refund calculation flow
    - _Requirements: All core requirements_
    - _Status: COMPLETE - 11 test classes with 13 comprehensive E2E tests covering all critical workflows (tax filing, OCR, refund, mixed income, loss carryforward, data export, audit, simulation, multi-language, security, system integration)_

- [x] 35. Deployment and DevOps
  - [x] 35.1 Create Docker images
    - Create Dockerfile for backend (FastAPI)
    - Create Dockerfile for frontend (Nginx + static files)
    - Create Dockerfile for OCR worker (Celery)
    - _Requirements: 17.1, 17.2_

  - [x] 35.2 Create Docker Compose for local development
    - Configure all services (backend, frontend, PostgreSQL, Redis, MinIO, Celery)
    - Set up networking and volumes
    - _Requirements: 17.1, 17.2_

  - [x] 35.3 Create Kubernetes deployment manifests
    - Create deployments for all services
    - Create services and ingress
    - Configure secrets and config maps
    - Set up horizontal pod autoscaling
    - _Requirements: 17.1, 17.2_

  - [x] 35.4 Set up CI/CD pipeline
    - Configure GitHub Actions workflow
    - Run tests on every commit
    - Build and push Docker images
    - Deploy to staging on merge to main
    - Manual approval for production deployment
    - _Requirements: 17.1, 17.2_

  - [x] 35.5 Configure monitoring and logging
    - Set up Prometheus for metrics
    - Set up Grafana dashboards
    - Configure log aggregation
    - Set up alerts for errors and performance issues
    - _Requirements: 18.1, 18.5_

  - [x] 35.6 Set up backup and disaster recovery
    - Configure automated database backups
    - Configure document storage backups
    - Test backup restoration
    - _Requirements: 18.6, 18.7_

  - [x] 35.7 Configure SSL/TLS certificates
    - Set up Let's Encrypt for automatic certificate renewal
    - Configure TLS 1.3
    - Set up security headers
    - _Requirements: 17.2_


- [x] 36. Performance optimization and security hardening
  - [x] 36.1 Implement caching layer with Redis
    - Cache tax calculation results
    - Cache user session data
    - Implement cache invalidation on data changes
    - _Requirements: 3.5, 17.3_

  - [x] 36.2 Optimize database queries
    - Add indexes for common queries
    - Implement database connection pooling
    - Optimize N+1 queries
    - _Requirements: 1.5, 10.1_

  - [x] 36.3 Implement rate limiting
    - Rate limit API endpoints
    - Rate limit OCR processing
    - Rate limit AI chat requests
    - _Requirements: 17.3, 38.1_

  - [x] 36.4 Implement security headers
    - Add HSTS, CSP, X-Frame-Options headers
    - Configure CORS properly
    - _Requirements: 17.2_

  - [x] 36.5 Conduct security audit
    - Test for SQL injection vulnerabilities
    - Test for XSS vulnerabilities
    - Test authentication and authorization
    - Test data encryption
    - _Requirements: 17.1, 17.2, 17.3, 17.4_

  - [x] 36.6 Optimize frontend bundle size
    - Code splitting by route
    - Tree shaking unused code
    - Compress assets
    - _Requirements: 35.1, 35.2_

  - [x] 36.7 Implement performance monitoring
    - Track API response times
    - Track OCR processing times
    - Track frontend page load times
    - Set up performance alerts
    - _Requirements: 18.5_

- [x] 37. Documentation and final polish
  - [x] 37.1 Write API documentation
    - Document all API endpoints with OpenAPI/Swagger
    - Include request/response examples
    - Document error codes
    - _Requirements: All API requirements_

  - [x] 37.2 Write user documentation
    - Create user guide in German, English, Chinese
    - Document common workflows
    - Create FAQ section
    - _Requirements: 33.1, 33.2_

  - [x] 37.3 Write developer documentation
    - Document architecture and design decisions
    - Document deployment procedures
    - Document testing strategy
    - _Requirements: All requirements_

  - [x] 37.4 Create demo data and seed scripts
    - Create sample users with different profiles
    - Create sample transactions and documents
    - Create sample tax scenarios
    - _Requirements: All requirements_

  - [x] 37.5 Conduct user acceptance testing
    - Test with real Austrian tax scenarios
    - Verify calculations against official USP calculator
    - Test all user workflows
    - _Requirements: All requirements_

  - [x] 37.6 Final bug fixes and polish
    - Fix any remaining bugs
    - Improve error messages
    - Polish UI/UX
    - _Requirements: All requirements_

- [x] 38. Final checkpoint - System ready for production
  - _Status: NEARLY READY_
  - _Blockers:_
    - Frontend build issues (Task 33) - ~1 hour to fix
    - Deployment not configured (Task 35) - ~8-12 hours
    - Performance optimization needed (Task 36) - ~6-8 hours
    - Documentation incomplete (Task 37) - ~4-6 hours
  - _Estimated completion: 20-28 hours remaining_
  - _Backend: 100% complete with comprehensive test coverage_
  - _Frontend: Features complete, needs build fixes_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP delivery
- Each task references specific requirements for traceability
- Property-based tests validate universal correctness properties using Hypothesis
- Unit tests validate specific examples and edge cases
- Integration tests validate end-to-end workflows
- The implementation follows an incremental approach: infrastructure → core features → advanced features → frontend → deployment
- Checkpoints ensure validation at key milestones
- All tax calculations must be verified against official Austrian USP 2026 calculator (error < €0.01)
- All sensitive data must be encrypted at rest (AES-256) and in transit (TLS 1.3)
- All AI responses must include disclaimer about not providing tax advice
- System must support German, English, and Chinese languages throughout

