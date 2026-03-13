# KaufvertragOCRService Implementation

## Overview

The `KaufvertragOCRService` integrates Tesseract OCR with pattern-based extraction to automatically extract structured data from Austrian property purchase contracts (Kaufverträge). This service is part of Phase 3 (optional) of the Property Asset Management feature.

## Implementation Summary

### Files Created

1. **`backend/app/services/kaufvertrag_ocr_service.py`**
   - Main service class integrating OCR and extraction
   - Processes PDF/image documents or pre-extracted text
   - Calculates multi-level confidence scores
   - Validates extraction results

2. **`backend/tests/test_kaufvertrag_ocr_service.py`**
   - Comprehensive test suite with 20 tests
   - Tests OCR integration, confidence calculation, validation
   - Integration tests with real extractor
   - All tests passing ✅

### Files Modified

1. **`backend/app/services/document_classifier.py`**
   - Added `EINKOMMENSTEUERBESCHEID` to DocumentType enum

2. **`backend/app/services/property_service.py`**
   - Added missing `Dict` and `Any` imports

3. **`backend/app/api/v1/endpoints/properties.py`**
   - Added missing `List`, `Dict`, `Any`, and `Body` imports

## Architecture

### Two-Stage Processing Pipeline

```
┌─────────────────────────────────────────────────────────┐
│                  Stage 1: OCR                            │
│  ┌────────────────────────────────────────────┐         │
│  │  Tesseract OCR (via OCREngine)             │         │
│  │  - Extract text from PDF/image             │         │
│  │  - Calculate OCR confidence (0.0-1.0)      │         │
│  └────────────────┬───────────────────────────┘         │
│                   │ raw_text                             │
│                   ▼                                      │
│  ┌────────────────────────────────────────────┐         │
│  │  Stage 2: Pattern Extraction               │         │
│  │  (KaufvertragExtractor)                    │         │
│  │  - Extract structured fields               │         │
│  │  - Calculate extraction confidence         │         │
│  └────────────────┬───────────────────────────┘         │
│                   │                                      │
│                   ▼                                      │
│  ┌────────────────────────────────────────────┐         │
│  │  Stage 3: Confidence Calculation           │         │
│  │  - Combine OCR + extraction confidence     │         │
│  │  - Apply penalties/bonuses                 │         │
│  │  - Validate data consistency               │         │
│  └────────────────┬───────────────────────────┘         │
│                   │                                      │
│                   ▼                                      │
│  ┌────────────────────────────────────────────┐         │
│  │  KaufvertragOCRResult                      │         │
│  │  - Extracted data                          │         │
│  │  - Confidence scores                       │         │
│  │  - Validation status                       │         │
│  └────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────┘
```

## Key Features

### 1. Extracted Fields

**Critical Fields** (required for property registration):
- Property address (street, city, postal code)
- Purchase price
- Purchase date

**Important Fields**:
- Building value and land value
- Buyer and seller names
- Notary name and location
- Construction year
- Purchase costs (Grunderwerbsteuer, notary fees, registry fees)

### 2. Confidence Scoring

**Overall Confidence Formula**:
```
overall_confidence = (ocr_confidence * 0.4) + (extraction_confidence * 0.6)
```

**Penalties** (15% per missing field):
- Missing property address
- Missing purchase price
- Missing purchase date

**Bonuses** (2% per field):
- Buyer name present
- Seller name present
- Building value present
- Notary name present

**Confidence Thresholds**:
- `< 0.5`: Low confidence - manual review strongly recommended
- `0.5 - 0.7`: Medium confidence - verify critical fields
- `> 0.7`: High confidence - ready for use

### 3. Validation

The service validates:
- **Critical fields presence**: Address, price, date
- **Data consistency**: Building value ≤ purchase price
- **Value breakdown**: Building + land = purchase price (within tolerance)
- **Date reasonableness**: Purchase date not in future
- **OCR quality**: Flags low-quality scans

**Validation Statuses**:
- `ready`: All critical fields present, high confidence
- `requires_review`: All fields present but low confidence or warnings
- `requires_manual_entry`: Missing critical fields

### 4. Error Handling

- Graceful handling of OCR failures
- Validation of extracted text length
- Exception handling with descriptive error messages
- Recommendations for improving results

## Usage

### Basic Usage

```python
from app.services.kaufvertrag_ocr_service import KaufvertragOCRService

# Initialize service
service = KaufvertragOCRService()

# Process PDF document
with open("kaufvertrag.pdf", "rb") as f:
    pdf_bytes = f.read()

result = service.process_kaufvertrag(pdf_bytes)

# Access extracted data
data = result.kaufvertrag_data
print(f"Property: {data.property_address}")
print(f"Price: {data.purchase_price}")
print(f"Date: {data.purchase_date}")
print(f"Confidence: {result.overall_confidence}")
```

### With Validation

```python
# Validate extraction
validation = service.validate_extraction(result)

if validation["status"] == "ready":
    # Use data directly
    property_data = {
        "street": data.street,
        "city": data.city,
        "postal_code": data.postal_code,
        "purchase_price": data.purchase_price,
        "purchase_date": data.purchase_date,
        "building_value": data.building_value,
    }
elif validation["status"] == "requires_review":
    # Show warnings to user
    print("Warnings:", validation["warnings"])
    print("Recommendations:", validation["recommendations"])
else:
    # Requires manual entry
    print("Issues:", validation["issues"])
```

### From Pre-Extracted Text

```python
# Skip OCR stage if text is already available
text = "KAUFVERTRAG\n\nLiegenschaft: Hauptstraße 123, 1010 Wien\n..."
result = service.process_kaufvertrag_from_text(text)
```

## Integration with Property Management

The extracted data can pre-fill property registration forms:

```python
from app.services.property_service import PropertyService

# Extract contract data
result = service.process_kaufvertrag(pdf_bytes)

# Validate before using
validation = service.validate_extraction(result)

if validation["status"] in ["ready", "requires_review"]:
    # Pre-fill property form
    property_data = PropertyCreate(
        street=result.kaufvertrag_data.street,
        city=result.kaufvertrag_data.city,
        postal_code=result.kaufvertrag_data.postal_code,
        purchase_date=result.kaufvertrag_data.purchase_date,
        purchase_price=result.kaufvertrag_data.purchase_price,
        building_value=result.kaufvertrag_data.building_value,
        construction_year=result.kaufvertrag_data.construction_year,
    )
    
    # User reviews and confirms
    property_service = PropertyService(db)
    property = property_service.create_property(user_id, property_data)
```

## Test Coverage

### Test Suite Statistics
- **Total Tests**: 20
- **Passing**: 20 ✅
- **Coverage**: Comprehensive

### Test Categories

1. **Initialization Tests** (1 test)
   - Service initialization

2. **Processing Tests** (6 tests)
   - Process from text
   - Process with mock OCR
   - Insufficient text handling
   - OCR failure handling
   - Extraction failure handling
   - Minimal contract processing

3. **Confidence Calculation Tests** (3 tests)
   - All fields present
   - Missing critical fields
   - Bonus fields impact

4. **Validation Tests** (7 tests)
   - Ready status
   - Requires manual entry
   - Requires review
   - Building value exceeds price
   - Value mismatch detection
   - Future date detection
   - Low confidence recommendations

5. **Integration Tests** (2 tests)
   - Full extraction pipeline
   - Confidence score reasonableness

6. **Utility Tests** (1 test)
   - Dictionary conversion

## Performance Considerations

### PDF Text Layer Detection

The service first attempts to extract text directly from PDFs with text layers (much faster than OCR):

```python
if pdf_bytes[:5] == b"%PDF-":
    pdf_text = self._extract_text_from_pdf(pdf_bytes)
    if pdf_text and len(pdf_text.strip()) > 20:
        # Use PDF text layer (fast)
        raw_text = pdf_text.strip()
```

### Lazy Loading

The OCR engine and extractor are initialized only when needed, reducing memory usage.

## Future Enhancements

### Phase 3+ Features (Optional)

1. **Enhanced Address Matching**: Integrate with AddressMatcher for automatic property linking
2. **Multi-page Support**: Handle contracts spanning multiple pages
3. **Handwritten Support**: Improve OCR for handwritten sections
4. **Cross-validation**: Verify extracted data with external sources
5. **Batch Processing**: Process multiple contracts simultaneously

## Related Documentation

- [KaufvertragExtractor](../app/services/kaufvertrag_extractor.py) - Pattern-based field extraction
- [Contract OCR Routing](CONTRACT_OCR_ROUTING.md) - Document classification and routing
- [Property Asset Management Design](../../.kiro/specs/property-asset-management/design.md)
- [OCR Engine](../app/services/ocr_engine.py) - Tesseract OCR integration

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

### Wrong Values

**Problem**: Extracted values are incorrect

**Solutions**:
1. Check OCR confidence score
2. Review raw_text for OCR errors
3. Verify document quality
4. Use validation warnings to identify issues

---

**Implementation Date**: 2026-03-08  
**Version**: 1.0  
**Status**: Completed ✅  
**Test Status**: All 20 tests passing ✅
