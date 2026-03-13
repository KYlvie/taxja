# ContractUpload Component

## Overview

The `ContractUpload` component allows users to upload property contract documents (Kaufvertrag or Mietvertrag) and automatically extract property data using OCR technology. This component is part of the Property Asset Management feature (Task D.3.4).

## Features

- **Drag-and-drop file upload** with click-to-select fallback
- **File validation** (type and size)
- **OCR processing** with confidence scoring
- **Editable extracted data** for user review and correction
- **Multi-language support** (German, English, Chinese)
- **Responsive design** for mobile and desktop

## Supported Contract Types

### Kaufvertrag (Purchase Contract)
Extracts:
- Property address (street, city, postal code)
- Purchase date
- Purchase price
- Building value
- Grunderwerbsteuer (property transfer tax)
- Notary fees
- Registry fees

### Mietvertrag (Rental Contract)
Extracts:
- Property address
- Rental start date
- Monthly rent
- Additional costs
- Tenant/landlord information

## Usage

```tsx
import { ContractUpload } from '../components/properties';

function PropertyRegistration() {
  const handleExtracted = (propertyData, contractData) => {
    // Pre-fill PropertyForm with extracted data
    console.log('Property data:', propertyData);
    console.log('Contract metadata:', contractData);
  };

  const handleCancel = () => {
    // Handle cancellation
  };

  return (
    <ContractUpload
      onExtracted={handleExtracted}
      onCancel={handleCancel}
    />
  );
}
```

## Props

### `onExtracted`
- **Type**: `(data: Partial<PropertyFormData>, contractData: ContractData) => void`
- **Required**: Yes
- **Description**: Callback function called when data is successfully extracted and confirmed by the user

### `onCancel`
- **Type**: `() => void`
- **Required**: Yes
- **Description**: Callback function called when the user cancels the upload process

## Data Flow

1. **Upload**: User selects or drops a PDF/image file
2. **Validation**: File type and size are validated
3. **Upload**: File is uploaded to the backend via `documentService.uploadDocument()`
4. **OCR Processing**: Backend processes the document using Tesseract OCR
5. **Extraction**: Contract-specific extractors parse the OCR text
6. **Review**: User reviews and can edit the extracted data
7. **Confirmation**: User confirms and data is passed to parent component via `onExtracted`

## File Validation

- **Supported formats**: PDF, JPG, PNG
- **Maximum size**: 10MB
- **Validation errors**:
  - `invalidFileType`: File is not PDF or image
  - `fileTooLarge`: File exceeds 10MB limit

## Confidence Scoring

The component displays confidence badges based on OCR extraction quality:

- **High Confidence** (≥80%): Green badge, data likely accurate
- **Medium Confidence** (60-79%): Yellow badge, review recommended
- **Low Confidence** (<60%): Red badge, careful review required

When confidence is below 80%, a warning message is displayed prompting the user to carefully review the data.

## States

The component manages the following states:

- `idle`: Initial state, showing upload zone
- `uploading`: File is being uploaded (shows progress bar)
- `processing`: OCR is processing the document
- `extracted`: Data has been extracted (shows review form)
- `error`: An error occurred (shows error message with retry option)

## Integration with PropertyForm

The extracted data is mapped to `PropertyFormData` format:

```typescript
{
  street: string;
  city: string;
  postal_code: string;
  purchase_date: string;
  purchase_price: string;
  building_value: string;
  notary_fees: string;
  grunderwerbsteuer: string;
  registry_fees: string;
}
```

This data can be directly used to pre-fill the `PropertyForm` component.

## Backend Integration

The component integrates with the following backend services:

### Document Upload
```
POST /api/v1/documents/upload
Content-Type: multipart/form-data
```

### OCR Review
```
GET /api/v1/documents/{document_id}/review
```

## Styling

The component uses CSS custom properties for theming:

- `--primary-color`: Primary brand color
- `--bg-secondary`: Secondary background
- `--border-color`: Border color
- `--text-primary`: Primary text color
- `--success-light`, `--warning-light`, `--error-light`: Status colors

## Accessibility

- Keyboard navigation support
- ARIA labels for screen readers
- Focus management for form inputs
- Clear error messages

## Error Handling

The component handles the following error scenarios:

1. **Invalid file type**: Shows error message, allows retry
2. **File too large**: Shows error message, allows retry
3. **Upload failure**: Shows error with retry button
4. **OCR processing failure**: Shows error with retry button
5. **Low confidence extraction**: Shows warning, allows manual correction

## Testing

The component includes comprehensive tests:

```bash
npm run test ContractUpload.test.tsx
```

Test coverage includes:
- Initial render
- File validation
- Upload flow
- Data extraction
- User editing
- Confirmation callback
- Error handling
- Retry functionality

## Future Enhancements

- Support for multi-page documents
- Batch upload of multiple contracts
- Document preview before upload
- Save extracted data for later review
- Integration with document management system

## Related Components

- `PropertyForm`: Uses extracted data to pre-fill property registration
- `DocumentUpload`: General document upload component
- `OCRReview`: Generic OCR review component

## Backend Services

- `KaufvertragOCRService`: Extracts data from purchase contracts
- `MietvertragOCRService`: Extracts data from rental contracts
- `OCREngine`: Tesseract OCR wrapper

## Translation Keys

All text is internationalized using i18next:

```
properties.contractUpload.title
properties.contractUpload.subtitle
properties.contractUpload.dropZoneTitle
properties.contractUpload.dropZoneText
properties.contractUpload.supportedFormats
properties.contractUpload.kaufvertragTitle
properties.contractUpload.kaufvertragDesc
properties.contractUpload.mietvertragTitle
properties.contractUpload.mietvertragDesc
properties.contractUpload.selectFile
properties.contractUpload.uploading
properties.contractUpload.processing
properties.contractUpload.extractedData
properties.contractUpload.confidenceHigh
properties.contractUpload.confidenceMedium
properties.contractUpload.confidenceLow
properties.contractUpload.lowConfidenceWarning
properties.contractUpload.mietvertragInfo
properties.contractUpload.uploadAnother
properties.contractUpload.useData
properties.contractUpload.errorTitle
properties.contractUpload.uploadError
properties.contractUpload.invalidFileType
properties.contractUpload.fileTooLarge
properties.contractUpload.retry
```

## License

Part of the Taxja Austrian Tax Management Platform.
