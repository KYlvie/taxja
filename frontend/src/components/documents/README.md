# Document Management Components

This directory contains all components related to document management and OCR functionality for the Taxja application.

## Components

### DocumentUpload
**File**: `DocumentUpload.tsx`

Handles document upload with drag-and-drop support and camera capture for mobile devices.

**Features**:
- Drag-and-drop file upload
- Multiple file upload support
- Camera capture on mobile devices
- Upload progress tracking
- Real-time status updates (uploading, processing, completed, error)
- Retry failed uploads

**Props**: None (standalone component)

**Usage**:
```tsx
import DocumentUpload from '../components/documents/DocumentUpload';

<DocumentUpload />
```

---

### OCRReview
**File**: `OCRReview.tsx`

Displays OCR extraction results and allows users to review and correct the data before creating a transaction.

**Features**:
- Document preview (image or PDF)
- Editable extracted data fields
- Confidence score indicators
- Field-level confidence highlighting
- Low-confidence field warnings
- Suggestions for improvement
- Save corrections or confirm data

**Props**:
- `documentId: number` - ID of the document to review
- `onConfirm?: () => void` - Callback when user confirms the data
- `onCancel?: () => void` - Callback when user cancels the review

**Usage**:
```tsx
import OCRReview from '../components/documents/OCRReview';

<OCRReview
  documentId={123}
  onConfirm={() => navigate('/transactions')}
  onCancel={() => navigate('/documents')}
/>
```

---

### DocumentList
**File**: `DocumentList.tsx`

Displays a list of uploaded documents with filtering, searching, and view mode options.

**Features**:
- Grid and list view modes
- Search by document name or OCR text
- Filter by document type, date range, and review status
- Pagination
- Document preview thumbnails
- Download documents
- Click to view/review documents

**Props**:
- `onDocumentSelect?: (document: Document) => void` - Optional callback when a document is selected

**Usage**:
```tsx
import DocumentList from '../components/documents/DocumentList';

<DocumentList
  onDocumentSelect={(doc) => navigate(`/documents/${doc.id}`)}
/>
```

---

## Types

### Document Types
Defined in `frontend/src/types/document.ts`:

```typescript
enum DocumentType {
  PAYSLIP = 'payslip',
  RECEIPT = 'receipt',
  INVOICE = 'invoice',
  RENTAL_CONTRACT = 'rental_contract',
  BANK_STATEMENT = 'bank_statement',
  PROPERTY_TAX = 'property_tax',
  SVS_NOTICE = 'svs_notice',
  LOHNZETTEL = 'lohnzettel',
  UNKNOWN = 'unknown',
}

interface Document {
  id: number;
  user_id: number;
  document_type: DocumentType;
  file_path: string;
  file_name: string;
  file_size: number;
  mime_type: string;
  ocr_result?: ExtractedData;
  raw_text?: string;
  confidence_score: number;
  needs_review: boolean;
  transaction_id?: number;
  created_at: string;
  updated_at: string;
}

interface ExtractedData {
  date?: string;
  amount?: number;
  merchant?: string;
  items?: LineItem[];
  vat_amounts?: Record<string, number>;
  gross_income?: number;
  net_income?: number;
  withheld_tax?: number;
  employer?: string;
  invoice_number?: string;
  supplier?: string;
  confidence?: Record<string, number>;
}

interface LineItem {
  description: string;
  amount: number;
  quantity?: number;
  is_deductible?: boolean;
  deduction_reason?: string;
}
```

---

## Services

### documentService
Defined in `frontend/src/services/documentService.ts`:

API service for document operations:
- `uploadDocument(file, onProgress)` - Upload single document
- `batchUpload(files, onProgress)` - Upload multiple documents
- `getDocuments(filters, page, pageSize)` - Get document list with filters
- `getDocument(id)` - Get single document
- `getDocumentForReview(id)` - Get document with OCR data for review
- `confirmOCR(id)` - Confirm OCR results
- `correctOCR(id, correctedData)` - Save corrected OCR data
- `downloadDocument(id)` - Download document file
- `deleteDocument(id)` - Delete document
- `getDocumentUrl(id)` - Get document preview URL

---

## State Management

### documentStore
Defined in `frontend/src/stores/documentStore.ts`:

Zustand store for document state management:
- `documents: Document[]` - List of documents
- `currentDocument: Document | null` - Currently selected document
- `total: number` - Total document count
- `loading: boolean` - Loading state
- `error: string | null` - Error message
- `filters: DocumentFilter` - Active filters
- `setDocuments(documents, total)` - Set document list
- `setCurrentDocument(document)` - Set current document
- `addDocument(document)` - Add new document
- `updateDocument(id, updates)` - Update document
- `removeDocument(id)` - Remove document
- `setLoading(loading)` - Set loading state
- `setError(error)` - Set error message
- `setFilters(filters)` - Set filters
- `clearFilters()` - Clear all filters

---

## Styling

All components have corresponding CSS files with:
- Responsive design (mobile-first approach)
- Consistent color scheme matching Taxja brand
- Smooth transitions and hover effects
- Accessibility considerations
- Mobile breakpoints at 768px

---

## Integration

### Main Page Integration
The `DocumentsPage` component integrates all document components:

```tsx
import DocumentUpload from '../components/documents/DocumentUpload';
import DocumentList from '../components/documents/DocumentList';
import OCRReview from '../components/documents/OCRReview';

// Tab-based interface
// - List tab: Shows DocumentList
// - Upload tab: Shows DocumentUpload
// - Review mode: Shows OCRReview when document needs review
```

---

## Requirements Mapping

This implementation satisfies the following requirements:

### Task 28.1 - Document Upload Page
- ✅ Drag-and-drop file upload
- ✅ Camera capture on mobile devices
- ✅ Multiple file upload
- ✅ Show upload progress
- **Requirements**: 19.1, 35.4

### Task 28.2 - OCR Review Interface
- ✅ Display document image
- ✅ Display extracted data in editable form
- ✅ Show confidence scores
- ✅ Highlight low-confidence fields
- ✅ Allow manual correction
- ✅ Confirm and create transaction
- **Requirements**: 19.7, 23.1, 23.2, 23.3, 23.4, 23.5

### Task 28.3 - Receipt Item Deductibility Checker
- ✅ Display receipt line items
- ✅ Show deductibility status for each item
- ✅ Allow user to confirm/override
- ✅ Calculate total deductible amount
- **Requirements**: 21.5

### Task 28.4 - Document List and Search
- ✅ Display documents in grid/list view
- ✅ Filter by document type, date
- ✅ Search by OCR text
- ✅ View document details
- ✅ Download original document
- **Requirements**: 24.3, 24.4, 24.5, 24.6

### Task 28.5 - OCR Error Handling UI
- ✅ Show clear error messages
- ✅ Provide suggestions for improvement
- ✅ Allow manual data entry fallback
- **Requirements**: 25.2, 25.3, 25.4, 25.7, 25.8

---

## Testing

To test these components:

1. **Document Upload**:
   - Test drag-and-drop functionality
   - Test file selection
   - Test camera capture on mobile
   - Test multiple file upload
   - Test error handling for invalid files

2. **OCR Review**:
   - Test with high-confidence OCR results
   - Test with low-confidence results
   - Test field editing
   - Test data correction and saving

3. **Receipt Item Checker**:
   - Test toggling deductibility
   - Test adding/editing reasons
   - Test total calculations

4. **Document List**:
   - Test grid and list views
   - Test filtering and searching
   - Test pagination
   - Test document download

5. **Error Handling**:
   - Test with various error types
   - Test retry functionality
   - Test manual entry fallback

---

## Future Enhancements

Potential improvements for future iterations:

1. **Batch OCR Review**: Review multiple documents at once
2. **Document Comparison**: Compare similar documents
3. **Smart Suggestions**: AI-powered deductibility suggestions
4. **Document Templates**: Save common document types as templates
5. **Offline Support**: PWA offline document viewing
6. **Document Sharing**: Share documents with tax advisors
7. **Advanced Search**: Full-text search across all OCR content
8. **Document Versioning**: Track document updates and corrections
