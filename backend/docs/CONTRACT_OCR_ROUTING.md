# Contract OCR Routing Documentation

## Overview

The OCR system has been extended to automatically detect and route property contract documents (Kaufvertrag and Mietvertrag) to specialized extractors. This enables automatic extraction of property details from uploaded contract PDFs.

## Supported Contract Types

### 1. Kaufvertrag (Property Purchase Contract)
- **Document Type**: `DocumentType.KAUFVERTRAG`
- **Extractor**: `KaufvertragOCRService`
- **Key Fields Extracted**:
  - Property address (street, city, postal code)
  - Purchase price and date
  - Building value and land value
  - Buyer and seller names
  - Notary information
  - Purchase costs (Grunderwerbsteuer, notary fees, registry fees)

### 2. Mietvertrag (Rental Contract)
- **Document Type**: `DocumentType.MIETVERTRAG`
- **Extractor**: `MietvertragOCRService`
- **Key Fields Extracted**:
  - Property address
  - Monthly rent (Hauptmietzins)
  - Additional costs (Betriebskosten, Heizkosten)
  - Rental start date
  - Tenant and landlord names
  - Contract type (befristet/unbefristet)

## Architecture

### Document Classification

The `DocumentClassifier` uses pattern matching to identify contract documents:

```python
# Kaufvertrag detection patterns
keywords = [
    "kaufvertrag", "kaufpreis", "käufer", "verkäufer",
    "grundstück", "liegenschaft", "notar", "grundbuch",
    "grunderwerbsteuer", "immobilie", ...
]

# Mietvertrag detection patterns
keywords = [
    "mietvertrag", "mietzins", "hauptmietzins", "vermieter",
    "mieter", "mietobjekt", "betriebskosten", "kaution", ...
]
```

### Routing Flow

```
┌─────────────────────────────────────────────────────────┐
│                    OCREngine                             │
│                                                          │
│  1. Extract text (Tesseract or PDF text layer)         │
│  2. Classify document type                              │
│  3. Route based on classification:                      │
│                                                          │
│     ┌─────────────────────────────────────┐            │
│     │ KAUFVERTRAG or MIETVERTRAG?         │            │
│     └──────────────┬──────────────────────┘            │
│                    │                                     │
│          ┌─────────┴─────────┐                         │
│          │                   │                          │
│     ┌────▼────┐         ┌───▼────┐                    │
│     │Kaufvert-│         │Mietvert-│                    │
│     │rag OCR  │         │rag OCR  │                    │
│     │Service  │         │Service  │                    │
│     └────┬────┘         └───┬────┘                    │
│          │                   │                          │
│     ┌────▼────────────────────▼────┐                  │
│     │  Specialized Extractors      │                  │
│     │  (Pattern-based field        │                  │
│     │   extraction)                │                  │
│     └────┬─────────────────────────┘                  │
│          │                                             │
│     ┌────▼────────────────────────┐                   │
│     │  OCRResult with extracted   │                   │
│     │  structured data            │                   │
│     └─────────────────────────────┘                   │
└─────────────────────────────────────────────────────────┘
```

## Usage

### Basic Usage

```python
from app.services.ocr_engine import OCREngine

# Initialize OCR engine
engine = OCREngine()

# Process a contract document
with open("kaufvertrag.pdf", "rb") as f:
    pdf_bytes = f.read()

result = engine.process_document(pdf_bytes)

# Check document type
if result.document_type == DocumentType.KAUFVERTRAG:
    print("Kaufvertrag detected!")
    print(f"Property address: {result.extracted_data.get('property_address')}")
    print(f"Purchase price: {result.extracted_data.get('purchase_price')}")
    print(f"Confidence: {result.confidence_score}")

elif result.document_type == DocumentType.MIETVERTRAG:
    print("Mietvertrag detected!")
    print(f"Property address: {result.extracted_data.get('property_address')}")
    print(f"Monthly rent: {result.extracted_data.get('monthly_rent')}")
    print(f"Confidence: {result.confidence_score}")
```

### Direct Service Usage

For more control, you can use the specialized services directly:

```python
from app.services.kaufvertrag_ocr_service import KaufvertragOCRService
from app.services.mietvertrag_ocr_service import MietvertragOCRService

# Process Kaufvertrag
kaufvertrag_service = KaufvertragOCRService()
result = kaufvertrag_service.process_kaufvertrag(pdf_bytes)

# Access extracted data
data = result.kaufvertrag_data
print(f"Purchase price: {data.purchase_price}")
print(f"Building value: {data.building_value}")
print(f"Buyer: {data.buyer_name}")

# Validate extraction
validation = kaufvertrag_service.validate_extraction(result)
print(f"Status: {validation['status']}")
print(f"Issues: {validation['issues']}")
print(f"Recommendations: {validation['recommendations']}")
```

## Confidence Scoring

The system provides multi-level confidence scoring:

### Overall Confidence Formula

```
overall_confidence = (ocr_confidence * 0.4) + (extraction_confidence * 0.6)
```

- **OCR Confidence (40%)**: Quality of text extraction from document
- **Extraction Confidence (60%)**: Quality of pattern matching and field extraction

### Penalties and Bonuses

**Penalties** (15% per missing field):
- Missing critical fields (address, price/rent, date)

**Bonuses** (2% per field):
- Presence of optional high-value fields

### Confidence Thresholds

- **< 0.5**: Low confidence - manual review strongly recommended
- **0.5 - 0.7**: Medium confidence - verify critical fields
- **> 0.7**: High confidence - ready for use

## Integration with Property Management

The extracted data can be used to pre-fill property registration forms:

```python
from app.services.property_service import PropertyService

# Extract contract data
result = engine.process_document(kaufvertrag_bytes)

if result.document_type == DocumentType.KAUFVERTRAG:
    # Pre-fill property creation form
    property_data = {
        "street": result.extracted_data.get("street"),
        "city": result.extracted_data.get("city"),
        "postal_code": result.extracted_data.get("postal_code"),
        "purchase_date": result.extracted_data.get("purchase_date"),
        "purchase_price": result.extracted_data.get("purchase_price"),
        "building_value": result.extracted_data.get("building_value"),
        "construction_year": result.extracted_data.get("construction_year"),
    }
    
    # User reviews and confirms before saving
    property_service = PropertyService(db)
    property = property_service.create_property(user_id, property_data)
```

## Error Handling

The routing system includes comprehensive error handling:

```python
try:
    result = engine.process_document(pdf_bytes)
    
    if result.needs_review:
        # Low confidence - prompt user for review
        print(f"Confidence: {result.confidence_score}")
        print(f"Suggestions: {result.suggestions}")
    
except ValueError as e:
    # OCR or extraction failed
    print(f"Processing failed: {str(e)}")
```

## Testing

### Unit Tests

```bash
# Run contract routing tests
pytest tests/test_contract_ocr_routing.py -v

# Run Kaufvertrag OCR tests
pytest tests/test_kaufvertrag_ocr_service.py -v

# Run Mietvertrag extractor tests
pytest tests/test_mietvertrag_extractor.py -v
```

### Test Coverage

The implementation includes tests for:
- Document type detection and classification
- Routing to correct extractor
- Field extraction accuracy
- Confidence score calculation
- Error handling
- Non-contract document handling

## Performance Considerations

### PDF Text Layer Detection

The system first attempts to extract text directly from PDFs (if they have a text layer):

```python
if image_bytes[:5] == b"%PDF-":
    pdf_text = self._extract_text_from_pdf(image_bytes)
    if pdf_text and len(pdf_text.strip()) > 20:
        # Use PDF text layer (much faster than OCR)
        raw_text = pdf_text.strip()
```

This is significantly faster than Tesseract OCR for digital PDFs.

### Lazy Loading

Contract extractors are imported only when needed:

```python
if doc_type == DocumentType.KAUFVERTRAG:
    from app.services.kaufvertrag_ocr_service import KaufvertragOCRService
    service = KaufvertragOCRService()
```

This reduces memory usage when processing non-contract documents.

## Future Enhancements

### Phase 3 Features (Optional)

1. **Enhanced Address Matching**: Integrate with AddressMatcher for property linking
2. **Multi-page Contract Support**: Handle contracts spanning multiple pages
3. **Handwritten Contract Support**: Improve OCR for handwritten sections
4. **Contract Validation**: Cross-reference extracted data with external sources
5. **Batch Processing**: Process multiple contracts simultaneously

## Troubleshooting

### Low Confidence Scores

**Problem**: Confidence score < 0.5

**Solutions**:
1. Ensure document is high-resolution (150+ DPI)
2. Check if document is scanned clearly (no blur, good lighting)
3. Verify document is in German (primary language supported)
4. Try rescanning document at higher quality

### Missing Fields

**Problem**: Critical fields not extracted

**Solutions**:
1. Check if field exists in document
2. Verify field format matches expected patterns
3. Review raw_text to see what OCR extracted
4. Consider manual entry for missing fields

### Wrong Document Type

**Problem**: Contract classified as wrong type

**Solutions**:
1. Check if document has clear type indicators (e.g., "KAUFVERTRAG" header)
2. Verify document is not ambiguous (contains both Kaufvertrag and Mietvertrag keywords)
3. Use direct service if classification is incorrect

## API Integration

For API endpoint integration, see:
- `backend/app/api/v1/endpoints/documents.py` - Document upload endpoints
- `backend/app/api/v1/endpoints/properties.py` - Property creation with OCR data

## Related Documentation

- [Property Asset Management Design](../../../.kiro/specs/property-asset-management/design.md)
- [Kaufvertrag Extractor](../app/services/kaufvertrag_extractor.py)
- [Mietvertrag Extractor](../app/services/mietvertrag_extractor.py)
- [OCR Engine](../app/services/ocr_engine.py)

---

**Last Updated**: 2026-03-08  
**Version**: 1.0  
**Status**: Implemented (Phase 3 - Optional Feature)
