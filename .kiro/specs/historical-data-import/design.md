# Design Document: Historical Data Import

## Overview

The Historical Data Import feature provides a unified system for importing tax and financial data from previous years into Taxja. This feature consolidates existing document extraction capabilities (E1 forms, Einkommensteuerbescheid, Kaufvertrag) and adds new functionality for Saldenliste import, creating a comprehensive onboarding experience for new users.

The system enables users to:
- Import E1 tax declaration forms to establish historical income and deductions
- Import Einkommensteuerbescheid (tax assessments) to extract rental property details and link to properties
- Import Kaufvertrag (purchase contracts) to establish property acquisition cost basis for depreciation
- Import Saldenliste (balance lists) to establish opening account balances for comparative reporting
- Review and approve imported data before finalization
- Track import quality metrics for continuous improvement

This feature is critical for accurate multi-year tax calculations, loss carryforward tracking, and property depreciation schedules.

## Architecture

### High-Level Architecture

The historical data import system follows a pipeline architecture with four main stages:

1. **Document Upload & OCR**: Users upload PDFs or structured files (CSV/Excel), which are processed through Tesseract OCR
2. **Extraction**: Document-specific extractors parse OCR text into structured data models
3. **Import & Transformation**: Import services create transactions, properties, and other domain entities
4. **Review & Approval**: Users review extracted data and approve or reject imports

```
┌─────────────┐     ┌──────────┐     ┌───────────┐     ┌──────────┐
│   Upload    │────▶│   OCR    │────▶│ Extractor │────▶│  Import  │
│  (PDF/CSV)  │     │ (Celery) │     │  Service  │     │  Service │
└─────────────┘     └──────────┘     └───────────┘     └──────────┘
                                            │                  │
                                            ▼                  ▼
                                     ┌─────────────┐   ┌────────────┐
                                     │  Structured │   │Transactions│
                                     │    Data     │   │ Properties │
                                     └─────────────┘   └────────────┘
                                            │                  │
                                            └────────┬─────────┘
                                                     ▼
                                              ┌─────────────┐
                                              │   Review    │
                                              │     UI      │
                                              └─────────────┘
```

### Component Responsibilities


**Document Upload Handler** (`api/v1/historical_import.py`)
- Accepts PDF, CSV, Excel uploads
- Validates file types and sizes
- Queues OCR tasks for async processing
- Returns upload confirmation with task ID

**OCR Processor** (`tasks/ocr_task.py`)
- Extracts text from PDF documents using Tesseract
- Handles multi-page documents
- Stores OCR text in document metadata
- Triggers extraction pipeline on completion

**Extractors** (`services/*_extractor.py`)
- `E1FormExtractor`: Parses E1 tax declaration forms, extracts KZ values
- `BescheidExtractor`: Parses tax assessments, extracts income/deductions and property addresses
- `KaufvertragExtractor`: Parses purchase contracts, extracts property details and costs
- `SaldenlisteParser`: Parses CSV/Excel balance lists, maps to Kontenplan

**Import Services** (`services/*_import_service.py`)
- `E1FormImportService`: Creates transactions from E1 data, suggests property linking
- `BescheidImportService`: Creates transactions, uses AddressMatcher for property linking
- `KaufvertragImportService`: Creates/updates properties, initializes depreciation schedules
- `SaldenlisteImportService`: Creates opening balance transactions

**Supporting Services**
- `AddressMatcher`: Fuzzy matching of extracted addresses to existing properties
- `DuplicateDetector`: Prevents double-counting of transactions from multiple sources
- `HistoricalDepreciationService`: Calculates depreciation schedules from historical purchase dates
- `DataReconciliationService`: Identifies conflicts between documents from the same tax year

**Orchestrator** (`services/historical_import_orchestrator.py`)
- Coordinates multi-document import sessions
- Manages import workflow state
- Generates summary reports
- Handles rollback on errors

## Components and Interfaces

### API Endpoints

#### POST /api/v1/historical-import/upload
Upload a document for historical data import.

**Request:**
```json
{
  "document_type": "e1_form" | "bescheid" | "kaufvertrag" | "saldenliste",
  "tax_year": 2023,
  "file": "<multipart/form-data>",
  "session_id": "uuid" // optional, for multi-document sessions
}
```

**Response:**
```json
{
  "upload_id": "uuid",
  "document_id": 123,
  "status": "processing",
  "task_id": "celery-task-id",
  "estimated_completion": "2024-01-15T10:30:00Z"
}
```

#### GET /api/v1/historical-import/status/{upload_id}
Check the status of a document import.

**Response:**
```json
{
  "upload_id": "uuid",
  "status": "completed" | "processing" | "failed" | "review_required",
  "progress": 100,
  "extraction_data": { /* extracted structured data */ },
  "confidence": 0.85,
  "errors": []
}
```

#### POST /api/v1/historical-import/review/{upload_id}
Submit reviewed and edited extraction data.

**Request:**
```json
{
  "approved": true,
  "edited_data": { /* user-corrected extraction data */ },
  "notes": "Corrected purchase price"
}
```

**Response:**
```json
{
  "import_id": "uuid",
  "transactions_created": 15,
  "properties_created": 1,
  "properties_linked": 2,
  "summary": { /* detailed import summary */ }
}
```

#### POST /api/v1/historical-import/session
Create a multi-document import session.

**Request:**
```json
{
  "tax_years": [2021, 2022, 2023],
  "document_types": ["e1_form", "bescheid", "kaufvertrag"]
}
```

**Response:**
```json
{
  "session_id": "uuid",
  "status": "active",
  "expected_documents": 9,
  "uploaded_documents": 0
}
```

#### GET /api/v1/historical-import/session/{session_id}
Get session status and summary.

**Response:**
```json
{
  "session_id": "uuid",
  "status": "in_progress" | "completed" | "failed",
  "documents": [
    {
      "upload_id": "uuid",
      "document_type": "e1_form",
      "tax_year": 2023,
      "status": "completed",
      "confidence": 0.92
    }
  ],
  "summary": {
    "total_transactions": 45,
    "total_properties": 3,
    "duplicate_transactions_prevented": 2,
    "conflicts_detected": 1
  }
}
```

### Data Models

#### HistoricalImportSession
```python
class HistoricalImportSession(Base):
    __tablename__ = "historical_import_sessions"
    
    id = Column(UUID, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    status = Column(Enum(ImportSessionStatus))  # active, completed, failed
    tax_years = Column(ARRAY(Integer))
    created_at = Column(DateTime)
    completed_at = Column(DateTime, nullable=True)
    
    # Summary metrics
    total_documents = Column(Integer, default=0)
    successful_imports = Column(Integer, default=0)
    failed_imports = Column(Integer, default=0)
    transactions_created = Column(Integer, default=0)
    properties_created = Column(Integer, default=0)
    properties_linked = Column(Integer, default=0)
    
    # Relationships
    uploads = relationship("HistoricalImportUpload", back_populates="session")
```


#### HistoricalImportUpload
```python
class HistoricalImportUpload(Base):
    __tablename__ = "historical_import_uploads"
    
    id = Column(UUID, primary_key=True)
    session_id = Column(UUID, ForeignKey("historical_import_sessions.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    document_id = Column(Integer, ForeignKey("documents.id"))
    document_type = Column(Enum(HistoricalDocumentType))  # e1_form, bescheid, kaufvertrag, saldenliste
    tax_year = Column(Integer)
    
    # Processing status
    status = Column(Enum(ImportStatus))  # uploaded, processing, extracted, review_required, approved, rejected, failed
    ocr_task_id = Column(String, nullable=True)
    extraction_confidence = Column(Numeric(3, 2), nullable=True)
    
    # Extracted data (JSONB for flexibility)
    extracted_data = Column(JSONB, nullable=True)
    edited_data = Column(JSONB, nullable=True)  # User corrections
    
    # Import results
    transactions_created = Column(ARRAY(Integer), default=[])
    properties_created = Column(ARRAY(UUID), default=[])
    properties_linked = Column(ARRAY(UUID), default=[])
    
    # Review and approval
    requires_review = Column(Boolean, default=False)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approval_notes = Column(Text, nullable=True)
    
    # Error tracking
    errors = Column(JSONB, default=[])
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    
    # Relationships
    session = relationship("HistoricalImportSession", back_populates="uploads")
    document = relationship("Document")
```

#### ImportConflict
```python
class ImportConflict(Base):
    __tablename__ = "import_conflicts"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(UUID, ForeignKey("historical_import_sessions.id"))
    upload_id_1 = Column(UUID, ForeignKey("historical_import_uploads.id"))
    upload_id_2 = Column(UUID, ForeignKey("historical_import_uploads.id"))
    
    conflict_type = Column(String)  # duplicate_transaction, conflicting_amount, conflicting_date
    field_name = Column(String)
    value_1 = Column(String)
    value_2 = Column(String)
    
    resolution = Column(String, nullable=True)  # keep_first, keep_second, manual_merge, ignore
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
```

#### ImportMetrics
```python
class ImportMetrics(Base):
    __tablename__ = "import_metrics"
    
    id = Column(Integer, primary_key=True)
    upload_id = Column(UUID, ForeignKey("historical_import_uploads.id"))
    document_type = Column(Enum(HistoricalDocumentType))
    
    # Extraction metrics
    extraction_confidence = Column(Numeric(3, 2))
    fields_extracted = Column(Integer)
    fields_total = Column(Integer)
    extraction_time_ms = Column(Integer)
    
    # Field-level accuracy (for ML training)
    field_accuracies = Column(JSONB)  # {"kz_245": 1.0, "kz_350": 0.8, ...}
    
    # User corrections
    fields_corrected = Column(Integer, default=0)
    corrections = Column(JSONB, default=[])  # [{"field": "kz_245", "extracted": "10000", "corrected": "11000"}]
    
    created_at = Column(DateTime, default=datetime.utcnow)
```

### Service Interfaces

#### HistoricalImportOrchestrator

```python
class HistoricalImportOrchestrator:
    """Orchestrates multi-document historical data import sessions."""
    
    def __init__(self, db: Session):
        self.db = db
        self.e1_import = E1FormImportService(db)
        self.bescheid_import = BescheidImportService(db)
        self.kaufvertrag_import = KaufvertragImportService(db)
        self.saldenliste_import = SaldenlisteImportService(db)
        self.duplicate_detector = DuplicateDetector(db)
        self.reconciliation = DataReconciliationService(db)
    
    def create_session(
        self, user_id: int, tax_years: List[int], document_types: List[str]
    ) -> HistoricalImportSession:
        """Create a new import session."""
        pass
    
    def process_upload(
        self, upload_id: UUID, ocr_text: str
    ) -> Dict[str, Any]:
        """Process a single document upload through extraction and import."""
        pass
    
    def detect_conflicts(
        self, session_id: UUID
    ) -> List[ImportConflict]:
        """Detect conflicts between documents in the same session."""
        pass
    
    def finalize_session(
        self, session_id: UUID
    ) -> Dict[str, Any]:
        """Finalize a session and generate summary report."""
        pass
```

#### SaldenlisteParser

```python
class SaldenlisteParser:
    """Parse Saldenliste CSV/Excel files into structured account data."""
    
    def parse_csv(self, file_path: str) -> SaldenlisteData:
        """Parse CSV format Saldenliste."""
        pass
    
    def parse_excel(self, file_path: str) -> SaldenlisteData:
        """Parse Excel format Saldenliste."""
        pass
    
    def detect_format(self, file_path: str) -> str:
        """Auto-detect Saldenliste format (BMD, RZL, custom)."""
        pass
```


#### SaldenlisteImportService

```python
class SaldenlisteImportService:
    """Import Saldenliste balance list data into the system."""
    
    def __init__(self, db: Session):
        self.db = db
        self.parser = SaldenlisteParser()
    
    def import_saldenliste(
        self, file_path: str, user_id: int, tax_year: int
    ) -> Dict[str, Any]:
        """Import Saldenliste and create opening balance transactions."""
        pass
    
    def map_to_kontenplan(
        self, account_number: str, user_type: UserType
    ) -> Optional[str]:
        """Map imported account to standard Kontenplan."""
        pass
    
    def create_opening_balance_transactions(
        self, accounts: List[Dict], user_id: int, tax_year: int
    ) -> List[Transaction]:
        """Create transactions to establish opening balances."""
        pass
```

#### KaufvertragImportService

```python
class KaufvertragImportService:
    """Import Kaufvertrag purchase contract data into the system."""
    
    def __init__(self, db: Session):
        self.db = db
        self.extractor = KaufvertragExtractor()
        self.depreciation_service = HistoricalDepreciationService(db)
    
    def import_from_ocr_text(
        self, text: str, user_id: int, document_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Extract and import Kaufvertrag data."""
        pass
    
    def create_or_update_property(
        self, kaufvertrag_data: KaufvertragData, user_id: int
    ) -> Property:
        """Create new property or update existing with acquisition details."""
        pass
    
    def create_purchase_cost_transactions(
        self, kaufvertrag_data: KaufvertragData, user_id: int, property_id: UUID
    ) -> List[Transaction]:
        """Create expense transactions for purchase costs."""
        pass
    
    def initialize_depreciation_schedule(
        self, property_id: UUID, building_value: Decimal, purchase_date: date
    ) -> None:
        """Initialize historical depreciation schedule."""
        pass
```

#### DataReconciliationService

```python
class DataReconciliationService:
    """Detect and reconcile conflicts between imported documents."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def detect_conflicts(
        self, session_id: UUID
    ) -> List[ImportConflict]:
        """Detect conflicts between documents in a session."""
        pass
    
    def reconcile_income_amounts(
        self, e1_amount: Decimal, bescheid_amount: Decimal, category: str
    ) -> Dict[str, Any]:
        """Reconcile conflicting income amounts from E1 and Bescheid."""
        pass
    
    def suggest_resolution(
        self, conflict: ImportConflict
    ) -> str:
        """Suggest automatic resolution strategy for a conflict."""
        pass
```

### Pydantic Schemas

#### HistoricalImportUploadRequest
```python
class HistoricalImportUploadRequest(BaseModel):
    document_type: Literal["e1_form", "bescheid", "kaufvertrag", "saldenliste"]
    tax_year: int = Field(ge=2000, le=2030)
    session_id: Optional[UUID] = None
    
    @validator("tax_year")
    def validate_tax_year(cls, v):
        current_year = date.today().year
        if v > current_year:
            raise ValueError("Tax year cannot be in the future")
        if v < current_year - 10:
            raise ValueError("Tax year too old (max 10 years)")
        return v
```

#### HistoricalImportReviewRequest
```python
class HistoricalImportReviewRequest(BaseModel):
    approved: bool
    edited_data: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
```

#### ImportSessionResponse
```python
class ImportSessionResponse(BaseModel):
    session_id: UUID
    status: str
    documents: List[Dict[str, Any]]
    summary: Dict[str, Any]
    conflicts: List[Dict[str, Any]]
```

## Data Models

### SaldenlisteData
```python
@dataclass
class SaldenlisteData:
    """Structured data from a Saldenliste file."""
    tax_year: int
    company_name: Optional[str] = None
    accounts: List[AccountBalance] = field(default_factory=list)
    total_assets: Optional[Decimal] = None
    total_liabilities: Optional[Decimal] = None
    confidence: float = 0.0

@dataclass
class AccountBalance:
    """Individual account balance entry."""
    account_number: str
    account_name: str
    debit_balance: Optional[Decimal] = None
    credit_balance: Optional[Decimal] = None
    balance: Decimal = Decimal("0")
    kontenklasse: Optional[int] = None  # Mapped from account number
```

### Enums

```python
class HistoricalDocumentType(str, Enum):
    E1_FORM = "e1_form"
    BESCHEID = "bescheid"
    KAUFVERTRAG = "kaufvertrag"
    SALDENLISTE = "saldenliste"

class ImportStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"

class ImportSessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property Reflection

After analyzing all acceptance criteria, I identified several areas where properties can be consolidated:

**Consolidation Opportunities:**
1. Properties 1.5, 3.5, and 7.5 all test confidence thresholds triggering review flags - these can be combined into a single comprehensive property
2. Properties 2.3, 2.4, and 2.5 all test action determination based on confidence scores - these can be combined
3. Properties 6.1, 6.2, 6.3 all test validation rules - these can be grouped as validation invariants
4. Properties 8.1, 8.2, 8.3 all test logging/metrics capture - these can be combined into a comprehensive logging property

**Redundancy Elimination:**
- Property 1.2 (creating transactions from KZ values) is subsumed by more specific properties for each document type
- Property 5.4 (generating summary reports) is an output property that's covered by testing the summary generation function directly

The following properties represent the unique, non-redundant validation requirements:

### Property 1: E1 KZ Extraction Completeness

*For any* valid E1 form OCR text containing KZ codes, the extractor should successfully extract all present KZ values and map them to the correct field names in E1FormData.

**Validates: Requirements 1.1**

### Property 2: Transaction Creation from Extracted Data

*For any* extracted document data (E1FormData, BescheidData, KaufvertragData) with non-zero income or expense values, the import service should create corresponding transactions with correct type, category, amount, and tax year.

**Validates: Requirements 1.2, 2.1, 3.2**

### Property 3: Rental Income Property Linking Suggestions

*For any* imported document containing rental income (KZ 350 in E1, V+V in Bescheid), the import service should generate property linking suggestions with confidence scores.

**Validates: Requirements 1.3, 2.2**

### Property 4: User Profile Update Idempotence

*For any* extracted document data containing tax number or family information, if the user profile already has these values, they should not be overwritten; if the profile lacks these values, they should be set.

**Validates: Requirements 1.4**

### Property 5: Confidence-Based Review Flagging

*For any* document extraction with confidence score below the threshold (0.7 for E1/Bescheid, 0.6 for Kaufvertrag), the system should set requires_review flag and prevent automatic finalization.

**Validates: Requirements 1.5, 3.5, 7.5**

### Property 6: Address Matching Action Determination

*For any* property address match result, the suggested action should be "auto_link" when confidence > 0.9, "suggest" when 0.7 ≤ confidence ≤ 0.9, and "create_new" when confidence < 0.7 or no matches found.

**Validates: Requirements 2.3, 2.4, 2.5**

### Property 7: Kaufvertrag Depreciation Schedule Initialization

*For any* Kaufvertrag with extracted building value and purchase date, the import service should initialize a historical depreciation schedule starting from the purchase date with the correct AfA rate based on building age.

**Validates: Requirements 3.3**

### Property 8: Purchase Cost Transaction Creation

*For any* Kaufvertrag with extracted purchase costs (Grunderwerbsteuer, Eintragungsgebühr, Notarkosten), the import service should create corresponding expense transactions with correct amounts and categories.

**Validates: Requirements 3.4**

### Property 9: Saldenliste Account Mapping Consistency

*For any* account in a Saldenliste, the account should be mapped to the correct Kontenplan (EA or GmbH) based on user type, and unmapped accounts should be flagged for review.

**Validates: Requirements 4.2, 4.4**

### Property 10: Opening Balance Transaction Creation

*For any* imported Saldenliste account balance, a corresponding opening balance transaction should be created with the correct account, amount, and tax year.

**Validates: Requirements 4.3**

### Property 11: Multi-Year Saldenliste Continuity

*For any* Saldenliste containing multiple years, each year should be imported separately, and the closing balance of year N should equal the opening balance of year N+1.

**Validates: Requirements 4.5**

### Property 12: Duplicate Transaction Prevention

*For any* set of documents uploaded in the same session, if multiple documents contain the same transaction data (same amount, date, category), only one transaction should be created.

**Validates: Requirements 5.2**

### Property 13: Conflict Detection Between Documents

*For any* two documents from the same tax year with overlapping data fields (e.g., E1 KZ 245 and Bescheid employment income), if the values differ by more than a threshold (e.g., 1%), a conflict should be flagged.

**Validates: Requirements 5.3**

### Property 14: Import Error Data Preservation

*For any* import operation that encounters an error, all successfully imported data prior to the error should be preserved and accessible for recovery.

**Validates: Requirements 5.5**

### Property 15: Income Category Validation

*For any* imported transaction with an income category, the category should be one of the 7 valid Austrian Einkunftsarten (employment, self-employment, business, rental, capital gains, agriculture, other).

**Validates: Requirements 6.1**

### Property 16: Deduction Limit Validation

*For any* imported deduction transaction, the amount should comply with Austrian tax law limits (e.g., Werbungskosten Pauschale ≤ €132, Pendlerpauschale within valid ranges).

**Validates: Requirements 6.2**

### Property 17: Loss Carryforward Record Creation

*For any* historical data showing negative income (losses) in a tax year, a loss carryforward record should be created with the correct amount and year tracking.

**Validates: Requirements 6.4**

### Property 18: User Edit Propagation

*For any* user edit to extracted data in the review interface, the corresponding database records (transactions, properties) should be updated to reflect the edited values.

**Validates: Requirements 7.2**

### Property 19: Approval State Locking

*For any* import that is approved by the user, all created transactions should be marked as reviewed and locked from automatic modifications (e.g., by duplicate detector or reconciliation).

**Validates: Requirements 7.3**

### Property 20: Rejection Cleanup

*For any* import that is rejected by the user, all associated transactions, property links, and depreciation schedules should be deleted, allowing clean re-import.

**Validates: Requirements 7.4**

### Property 21: Import Metrics Logging

*For any* document import operation, the system should log extraction confidence, field-level accuracy, processing time, and any errors to the import_metrics table.

**Validates: Requirements 8.1, 8.2**

### Property 22: User Correction Training Data Capture

*For any* user correction to extracted data, the system should record the original extracted value, corrected value, and field name as training data for ML model improvement.

**Validates: Requirements 8.3**


## Error Handling

### Error Categories

**Extraction Errors**
- OCR failure (unreadable PDF, corrupted file)
- Parsing errors (unexpected document format)
- Low confidence extraction (< threshold)
- Missing required fields

**Import Errors**
- Database constraint violations
- Duplicate transaction detection
- Invalid data (negative amounts where positive expected)
- Foreign key violations (invalid user_id, property_id)

**Validation Errors**
- Tax law compliance violations
- Out-of-range values
- Invalid date ranges
- Conflicting data between documents

**System Errors**
- Celery task failures
- Database connection errors
- File storage errors
- Timeout errors

### Error Handling Strategies

**Graceful Degradation**
```python
try:
    extracted_data = extractor.extract(ocr_text)
except ExtractionError as e:
    # Log error and mark for manual review
    upload.status = ImportStatus.REVIEW_REQUIRED
    upload.errors.append({
        "type": "extraction_error",
        "message": str(e),
        "timestamp": datetime.utcnow()
    })
    upload.extraction_confidence = 0.0
    db.commit()
    return {"status": "review_required", "errors": upload.errors}
```

**Partial Success Handling**
```python
def import_e1_data(data: E1FormData, user_id: int) -> Dict[str, Any]:
    """Import E1 data with partial success handling."""
    results = {
        "transactions_created": [],
        "errors": [],
        "partial_success": False
    }
    
    # Try to import each KZ value independently
    for kz_code, amount in data.all_kz_values.items():
        try:
            txn = create_transaction_from_kz(kz_code, amount, user_id)
            results["transactions_created"].append(txn.id)
        except Exception as e:
            results["errors"].append({
                "kz_code": kz_code,
                "error": str(e)
            })
            results["partial_success"] = True
    
    return results
```

**Rollback on Critical Errors**
```python
def finalize_import(upload_id: UUID) -> None:
    """Finalize import with rollback on critical errors."""
    savepoint = db.begin_nested()
    try:
        # Create all transactions
        transactions = create_transactions(upload_id)
        # Link properties
        link_properties(upload_id)
        # Update user profile
        update_user_profile(upload_id)
        
        savepoint.commit()
    except CriticalError as e:
        savepoint.rollback()
        mark_import_failed(upload_id, str(e))
        raise
```

**Retry Logic for Transient Errors**
```python
@celery_app.task(bind=True, max_retries=3)
def process_ocr(self, document_id: int):
    """Process OCR with retry logic."""
    try:
        text = extract_text_from_pdf(document_id)
        return text
    except TransientError as e:
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=2 ** self.request.retries)
    except PermanentError as e:
        # Don't retry, mark as failed
        mark_document_failed(document_id, str(e))
        raise
```

### Error Messages

Error messages should be:
- **Clear**: Explain what went wrong in plain language
- **Actionable**: Suggest how to fix the problem
- **Localized**: Support German, English, Chinese

**Example Error Messages:**
```python
ERROR_MESSAGES = {
    "extraction_low_confidence": {
        "de": "Die Datenextraktion war unsicher (Konfidenz: {confidence}%). Bitte überprüfen Sie die extrahierten Daten manuell.",
        "en": "Data extraction had low confidence ({confidence}%). Please review the extracted data manually.",
        "zh": "数据提取置信度较低（{confidence}%）。请手动检查提取的数据。"
    },
    "duplicate_transaction": {
        "de": "Diese Transaktion wurde bereits importiert. Duplikat verhindert.",
        "en": "This transaction was already imported. Duplicate prevented.",
        "zh": "此交易已导入。已防止重复。"
    },
    "invalid_tax_year": {
        "de": "Ungültiges Steuerjahr: {year}. Muss zwischen {min_year} und {max_year} liegen.",
        "en": "Invalid tax year: {year}. Must be between {min_year} and {max_year}.",
        "zh": "无效的税务年度：{year}。必须在 {min_year} 和 {max_year} 之间。"
    }
}
```

## Testing Strategy

### Dual Testing Approach

The historical data import feature requires both unit tests and property-based tests for comprehensive coverage:

**Unit Tests** - Focus on:
- Specific document format examples (real E1 forms, Bescheid samples)
- Edge cases (empty documents, malformed PDFs, missing fields)
- Integration points (API endpoints, Celery tasks, database operations)
- Error conditions (OCR failures, validation errors, conflicts)

**Property-Based Tests** - Focus on:
- Universal extraction properties (any valid E1 should extract KZ values)
- Transaction creation invariants (extracted data → transactions mapping)
- Confidence threshold behaviors (any confidence < 0.7 → review required)
- Data reconciliation properties (duplicate detection, conflict resolution)

### Property Test Configuration

All property-based tests will use the Hypothesis library with minimum 100 iterations:

```python
from hypothesis import given, settings
from hypothesis.strategies import decimals, integers, text

@settings(max_examples=100)
@given(
    kz_245=decimals(min_value=0, max_value=1000000, places=2),
    kz_350=decimals(min_value=-100000, max_value=100000, places=2),
    tax_year=integers(min_value=2015, max_value=2030)
)
def test_e1_transaction_creation_property(kz_245, kz_350, tax_year):
    """
    Feature: historical-data-import, Property 2: Transaction Creation from Extracted Data
    
    For any extracted E1FormData with non-zero KZ values, the import service
    should create corresponding transactions with correct type, category, amount, and tax year.
    """
    # Create E1FormData with generated values
    e1_data = E1FormData(
        tax_year=tax_year,
        kz_245=kz_245 if kz_245 > 0 else None,
        kz_350=kz_350 if kz_350 != 0 else None
    )
    
    # Import data
    result = e1_import_service.import_e1_data(e1_data, test_user.id)
    
    # Verify transactions created
    transactions = result["transactions"]
    
    if kz_245 and kz_245 > 0:
        employment_txn = next(t for t in transactions if t["kz"] == "245")
        assert employment_txn["type"] == "income"
        assert employment_txn["category"] == "employment"
        assert Decimal(str(employment_txn["amount"])) == kz_245
    
    if kz_350 and kz_350 != 0:
        rental_txn = next(t for t in transactions if t["kz"] == "350")
        expected_type = "income" if kz_350 > 0 else "expense"
        assert rental_txn["type"] == expected_type
        assert Decimal(str(rental_txn["amount"])) == abs(kz_350)
```

### Test Coverage Requirements

- **Unit Test Coverage**: Minimum 85% line coverage for import services
- **Property Test Coverage**: All 22 correctness properties must have corresponding property tests
- **Integration Test Coverage**: All API endpoints must have integration tests
- **E2E Test Coverage**: Complete import workflow (upload → extract → review → approve) must have E2E test

### Test Data

**Synthetic Test Documents**
- Generate synthetic E1 forms with known KZ values for property testing
- Create Bescheid samples with various address formats for matching tests
- Build Kaufvertrag examples with different value breakdowns

**Real Document Samples** (anonymized)
- Collect real E1 forms, Bescheid, Kaufvertrag samples from users (with consent)
- Anonymize personal data (names, addresses, Steuernummer)
- Use for regression testing and extraction accuracy validation

**Edge Case Documents**
- Handwritten forms (low OCR quality)
- Multi-page documents
- Documents with unusual formatting
- Documents with missing sections


## Implementation Approach

### Phase 1: Core Infrastructure (Week 1-2)

**Database Models**
1. Create `historical_import_sessions` table with Alembic migration
2. Create `historical_import_uploads` table
3. Create `import_conflicts` table
4. Create `import_metrics` table
5. Add indexes for performance (user_id, session_id, tax_year)

**API Endpoints**
1. Implement `POST /api/v1/historical-import/upload`
2. Implement `GET /api/v1/historical-import/status/{upload_id}`
3. Implement `POST /api/v1/historical-import/session`
4. Implement `GET /api/v1/historical-import/session/{session_id}`

**Celery Tasks**
1. Enhance existing OCR task to support historical import workflow
2. Add task status tracking and progress updates
3. Implement task chaining (OCR → Extract → Import)

### Phase 2: Saldenliste Support (Week 3)

**Parser Implementation**
1. Implement `SaldenlisteParser` for CSV format
2. Add Excel format support using `openpyxl`
3. Implement format auto-detection (BMD, RZL, custom)
4. Add account number normalization

**Import Service**
1. Implement `SaldenlisteImportService`
2. Add Kontenplan mapping logic (EA vs GmbH)
3. Implement opening balance transaction creation
4. Add multi-year continuity validation

**Testing**
1. Unit tests for parser with sample CSV/Excel files
2. Property tests for account mapping consistency
3. Integration tests for full Saldenliste import workflow

### Phase 3: Kaufvertrag Enhancement (Week 4)

**Import Service**
1. Implement `KaufvertragImportService` (currently only extractor exists)
2. Add property creation/update logic
3. Implement purchase cost transaction creation
4. Integrate with `HistoricalDepreciationService`

**Property Linking**
1. Add address matching for Kaufvertrag addresses
2. Implement property deduplication (prevent creating duplicate properties)
3. Add confidence scoring for property matches

**Testing**
1. Unit tests for property creation logic
2. Property tests for depreciation schedule initialization
3. Integration tests with existing property management

### Phase 4: Orchestration & Reconciliation (Week 5)

**Orchestrator**
1. Implement `HistoricalImportOrchestrator`
2. Add session management (create, track, finalize)
3. Implement multi-document coordination
4. Add progress tracking and status updates

**Reconciliation Service**
1. Implement `DataReconciliationService`
2. Add conflict detection algorithms
3. Implement automatic resolution strategies
4. Add user-facing conflict resolution UI support

**Duplicate Detection**
1. Enhance existing `DuplicateDetector` for historical imports
2. Add cross-document duplicate detection
3. Implement fuzzy matching for similar transactions
4. Add confidence scoring for duplicate matches

### Phase 5: Review UI & Finalization (Week 6)

**Review Interface**
1. Implement `POST /api/v1/historical-import/review/{upload_id}`
2. Add edit support for extracted data
3. Implement approval/rejection workflow
4. Add conflict resolution interface

**Summary Reports**
1. Implement session summary generation
2. Add data quality metrics calculation
3. Create PDF export for import summary
4. Add email notifications for completed imports

**Error Handling**
1. Implement comprehensive error logging
2. Add user-friendly error messages (i18n)
3. Implement partial success handling
4. Add rollback mechanisms for critical errors

### Phase 6: Analytics & Optimization (Week 7-8)

**Metrics & Analytics**
1. Implement `ImportMetrics` logging
2. Add extraction accuracy tracking
3. Create admin dashboard for import analytics
4. Implement anomaly detection for extraction patterns

**ML Training Data**
1. Implement correction capture for ML training
2. Add field-level accuracy tracking
3. Create training data export for model retraining
4. Implement feedback loop for extractor improvement

**Performance Optimization**
1. Add Redis caching for frequently accessed data
2. Optimize database queries with proper indexes
3. Implement batch processing for large imports
4. Add progress streaming for long-running operations

**Documentation**
1. Write API documentation with examples
2. Create user guide for historical import workflow
3. Document common issues and troubleshooting
4. Add developer documentation for extending extractors

### Migration Strategy

**Existing Data**
- No migration needed for existing E1/Bescheid imports (already in transactions table)
- Add `import_source` field to existing transactions if not present
- Backfill `import_source` for historical imports

**Backward Compatibility**
- Existing E1FormImportService and BescheidImportService remain functional
- New orchestrator wraps existing services without breaking changes
- API versioning ensures no breaking changes to existing endpoints

### Deployment Considerations

**Database Migrations**
```bash
# Create new tables
alembic revision --autogenerate -m "Add historical import tables"
alembic upgrade head
```

**Environment Variables**
```bash
# Add to .env
HISTORICAL_IMPORT_MAX_FILE_SIZE_MB=50
HISTORICAL_IMPORT_RETENTION_DAYS=90
HISTORICAL_IMPORT_MIN_CONFIDENCE=0.7
HISTORICAL_IMPORT_ENABLE_AUTO_LINK=true
```

**Celery Configuration**
```python
# Add to celery config
CELERY_TASK_ROUTES = {
    'app.tasks.ocr_task.process_historical_import': {'queue': 'historical_import'},
}
```

**MinIO Buckets**
```bash
# Create bucket for historical import documents
mc mb minio/historical-imports
mc policy set download minio/historical-imports
```

### Monitoring & Observability

**Metrics to Track**
- Import success rate by document type
- Average extraction confidence by document type
- Processing time (OCR, extraction, import)
- Error rate by error type
- User review rate (% of imports requiring review)
- Conflict detection rate
- Duplicate prevention rate

**Logging**
```python
import logging

logger = logging.getLogger(__name__)

# Log all import operations
logger.info(
    "Historical import started",
    extra={
        "upload_id": upload_id,
        "user_id": user_id,
        "document_type": document_type,
        "tax_year": tax_year
    }
)

# Log extraction results
logger.info(
    "Extraction completed",
    extra={
        "upload_id": upload_id,
        "confidence": confidence,
        "fields_extracted": len(extracted_data),
        "extraction_time_ms": extraction_time
    }
)
```

**Alerts**
- Alert when extraction confidence drops below threshold for multiple documents
- Alert when error rate exceeds 10% in a 1-hour window
- Alert when OCR processing time exceeds 60 seconds
- Alert when database connection pool is exhausted

### Security Considerations

**Data Encryption**
- All uploaded documents encrypted at rest (AES-256)
- OCR text stored encrypted in database
- Extracted data encrypted in JSONB columns

**Access Control**
- Users can only access their own imports (enforce user_id filtering)
- Admin role required for analytics and metrics access
- Document deletion cascades to remove all extracted data

**Audit Trail**
- Log all user actions (upload, review, approve, reject)
- Track who made corrections to extracted data
- Maintain immutable audit log for compliance

**Data Retention**
- Uploaded documents retained for 90 days (configurable)
- Extracted data retained indefinitely (needed for tax calculations)
- Failed imports cleaned up after 30 days

### Scalability Considerations

**Horizontal Scaling**
- Celery workers can be scaled independently
- API servers are stateless and can be load balanced
- Database read replicas for analytics queries

**Vertical Scaling**
- OCR processing is CPU-intensive (consider GPU acceleration)
- Database needs sufficient memory for JSONB indexing
- Redis cache sized for session data

**Performance Targets**
- OCR processing: < 30 seconds for 10-page PDF
- Extraction: < 5 seconds per document
- Import: < 10 seconds for 50 transactions
- API response time: < 200ms (excluding async operations)


## Design Decisions and Rationale

### Why Unified Orchestrator?

**Decision**: Create a single `HistoricalImportOrchestrator` that coordinates all document types rather than separate import flows.

**Rationale**:
- Users often import multiple document types in one session (E1 + Bescheid + Kaufvertrag)
- Centralized orchestration enables cross-document conflict detection
- Easier to implement duplicate prevention across document types
- Simplified session management and progress tracking
- Better user experience with unified workflow

### Why JSONB for Extracted Data?

**Decision**: Store extracted data in JSONB columns rather than normalized tables.

**Rationale**:
- Document structures vary significantly (E1 has different fields than Bescheid)
- Flexibility to add new fields without schema migrations
- Efficient querying with PostgreSQL JSONB indexes
- Easier to store user corrections alongside original extractions
- Simplifies audit trail (complete before/after snapshots)

### Why Separate Import Sessions?

**Decision**: Create explicit `HistoricalImportSession` model rather than implicit grouping.

**Rationale**:
- Users need to track multi-document import progress
- Session provides transaction boundary for rollback
- Enables batch operations (approve all, reject all)
- Facilitates conflict resolution across documents
- Better analytics (success rate per session vs per document)

### Why Confidence-Based Review?

**Decision**: Require manual review for low-confidence extractions rather than auto-importing all data.

**Rationale**:
- Tax data accuracy is critical (errors have legal/financial consequences)
- Low confidence indicates potential OCR or parsing errors
- User review improves data quality
- Corrections provide training data for ML improvement
- Builds user trust in the system

### Why Property-Based Testing?

**Decision**: Use Hypothesis for property-based testing in addition to unit tests.

**Rationale**:
- Historical import has many edge cases (various document formats, amounts, dates)
- Property tests validate universal invariants (e.g., any KZ value → transaction)
- Catches bugs that unit tests miss (unexpected input combinations)
- Aligns with Austrian tax law (rules apply universally, not just to examples)
- Provides higher confidence in correctness

### Why Async OCR Processing?

**Decision**: Use Celery for OCR processing rather than synchronous API calls.

**Rationale**:
- OCR can take 30+ seconds for multi-page documents
- Prevents API timeout errors
- Enables progress tracking and cancellation
- Allows horizontal scaling of OCR workers
- Better user experience (upload returns immediately)

## Future Enhancements

### Phase 2 Features (Post-MVP)

**Batch Import**
- Upload multiple documents at once (drag-and-drop folder)
- Automatic document type detection using ML
- Parallel processing of multiple documents
- Bulk approval/rejection interface

**Smart Conflict Resolution**
- ML-based conflict resolution suggestions
- Historical pattern analysis (user's typical choices)
- Automatic resolution for low-risk conflicts
- Confidence scoring for resolution suggestions

**Enhanced Property Matching**
- Use cadastral numbers (Grundstücksnummer) for exact matching
- Integrate with Austrian land registry (Grundbuch) API
- Historical address lookup (handle address changes)
- Fuzzy matching with Levenshtein distance

**Advanced Analytics**
- Extraction accuracy trends over time
- Document quality scoring (OCR readability)
- User behavior analysis (common corrections)
- Predictive modeling for extraction confidence

**Mobile Optimization**
- Camera-based document capture
- On-device OCR preprocessing
- Offline mode with sync
- Progressive Web App enhancements

### Integration Opportunities

**FinanzOnline Integration**
- Fetch E1 forms directly from FinanzOnline
- Validate imported data against FinanzOnline records
- Pre-fill forms with imported historical data

**Bank Integration**
- Match imported transactions to bank statements
- Reconcile discrepancies automatically
- Suggest missing transactions

**Accounting Software Integration**
- Import from BMD, RZL, DATEV
- Export to accounting software formats
- Bidirectional sync for Saldenliste

## Conclusion

The Historical Data Import feature provides a comprehensive solution for onboarding users with existing tax data. By consolidating and enhancing existing extraction capabilities (E1, Bescheid, Kaufvertrag) and adding new functionality (Saldenliste, orchestration, reconciliation), the system enables users to quickly establish accurate historical baselines for multi-year tax calculations.

The design prioritizes:
- **Data Quality**: Confidence-based review, validation, conflict detection
- **User Experience**: Unified workflow, clear error messages, progress tracking
- **Correctness**: Property-based testing, comprehensive validation, audit trails
- **Scalability**: Async processing, horizontal scaling, performance optimization
- **Maintainability**: Modular architecture, clear interfaces, comprehensive testing

The phased implementation approach (8 weeks) allows for iterative development and testing, with each phase delivering incremental value. The property-based testing strategy ensures correctness across the wide variety of document formats and edge cases encountered in real-world Austrian tax documents.
