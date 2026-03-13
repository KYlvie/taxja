# MietvertragOCRService Implementation

## Overview

The `MietvertragOCRService` integrates Tesseract OCR with pattern-based extraction to automatically extract structured data from Austrian rental contracts (Mietverträge). This service is part of Phase 3 (optional) of the Property Asset Management feature.

## Implementation Summary

### Files Implemented

1. **`backend/app/services/mietvertrag_extractor.py`**
   - Pattern-based field extraction from rental contract text
   - Extracts property address, rental terms, parties, and costs
   - Comprehensive regex patterns for Austrian contract formats
   - Field-level and overall confidence scoring
   - **Status**: ✅ Fully implemented

2. **`backend/app/services/mietvertrag_ocr_service.py`**
   - Main service class integrating OCR and extraction
   - Processes PDF/image documents or pre-extracted text
   - Calculates multi-level confidence scores
   - Validates extraction results
   - **Status**: ✅ Fully implemented

3. **`backend/tests/test_mietvertrag_extractor.py`**
   - Comprehensive test suite with 40+ tests
   - Tests all extraction patterns and edge cases
   - Validates confidence scoring
   - **Status**: ✅ All tests implemented

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
│  │  (MietvertragExtractor)                    │         │
│  │  - Extract structured fields               │         │
│  │  - Calculate extraction confidence         │         │
│  └────────────────┬───────────────────────────┘         │
│                   │ MietvertragData                      │
│                   ▼                                      │
│  ┌────────────────────────────────────────────┐         │
│  │  Stage 3: Confidence Calculation           │         │
│  │  - Combine OCR + extraction confidence     │         │
│  │  - Apply penalties for missing fields      │         │
│  │  - Apply bonuses for optional fields       │         │
│  └────────────────┬───────────────────────────┘         │
│                   │                                      │
│                   ▼                                      │
│            MietvertragOCRResult                          │
└─────────────────────────────────────────────────────────┘
```

## Extracted Fields

### Critical Fields (Required for Property Registration)
- **property_address**: Full address of rental property
- **street**: Street name and number
- **city**: City name
- **postal_code**: 4-digit Austrian postal code
- **monthly_rent**: Monthly rent amount (Mietzins/Hauptmietzins)
- **rental_start_date**: Contract start date (Mietbeginn)

### Important Fields
- **tenant_name**: Tenant name (Mieter/Bestandnehmer)
- **landlord_name**: Landlord name (Vermieter/Bestandgeber)
- **betriebskosten**: Operating costs
- **heating_costs**: Heating costs (Heizkosten)
- **deposit_amount**: Security deposit (Kaution)

### Optional Fields
- **rental_end_date**: Contract end date (for fixed-term contracts)
- **utilities_included**: Whether utilities are included in rent
- **contract_type**: Unbefristet (unlimited) or Befristet (fixed-term)

## Confidence Scoring

### Overall Confidence Formula

```
base_confidence = (ocr_confidence * 0.4) + (extraction_confidence * 0.6)

# Apply penalties for missing critical fields
penalty = missing_critical_fields * 0.15

# Apply bonuses for present optional fields
bonus = present_optional_fields * 0.02

overall_confidence = base_confidence - penalty + bonus
```

### Confidence Thresholds

- **>= 0.80**: High confidence - ready for automatic processing
- **0.70 - 0.79**: Medium confidence - review recommended
- **0.50 - 0.69**: Low confidence - manual review required
- **< 0.50**: Very low confidence - manual entry recommended

## Pattern Matching Examples

### Property Address Patterns

```python
# Standard labeled formats
"Mietobjekt: Hauptstraße 123, 1010 Wien"
"Bestandobjekt: Mariahilfer Straße 45/12, 1060 Wien"
"Wohnung: Top 5, Ringstraße 88, 1010 Wien"

# Alternative formats
"gelegen in Landstraßer Hauptstraße 100, 1030 Wien"
"im Hause Hauptstraße 123, 1010 Wien"
```

### Monthly Rent Patterns

```python
# Standard formats
"Mietzins: EUR 850,00"
"Hauptmietzins: € 1.200,50"
"Nettomiete: 950,00 EUR"

# Alternative formats
"Monatliche Miete: EUR 2.500,00"
"EUR 750,00 pro Monat"
"Mietzins beträgt EUR 1.100,00"
```

### Date Patterns

```python
# Start date
"Mietbeginn: 01.03.2024"
"Vertragsbeginn: 15.06.2024"
"ab 01.01.2024"

# End date (for fixed-term contracts)
"Mietende: 31.12.2026"
"befristet bis 31.03.2027"
```

### Parties Patterns

```python
# Tenant
"Mieter: Max Mustermann, geboren am 15.05.1985"
"Bestandnehmer: Johann Huber"

# Landlord
"Vermieter: Maria Müller, geboren am 20.03.1970"
"Bestandgeber: Peter Wagner"
```

## Usage Examples

### Process PDF Document

```python
from app.services.mietvertrag_ocr_service import MietvertragOCRService

service = MietvertragOCRService()

# Read PDF file
with open("mietvertrag.pdf", "rb") as f:
    pdf_bytes = f.read()

# Process document
result = service.process_mietvertrag(pdf_bytes)

# Access extracted data
print(f"Property: {result.mietvertrag_data.property_address}")
print(f"Monthly Rent: {result.mietvertrag_data.monthly_rent}")
print(f"Start Date: {result.mietvertrag_data.rental_start_date}")
print(f"Tenant: {result.mietvertrag_data.tenant_name}")
print(f"Landlord: {result.mietvertrag_data.landlord_name}")
print(f"Overall Confidence: {result.overall_confidence}")
```

### Process Pre-Extracted Text

```python
# If you already have text (e.g., from another OCR service)
text = """
MIETVERTRAG

Vermieter: Maria Müller
Mieter: Max Mustermann

Mietobjekt: Hauptstraße 123/5, 1010 Wien

Mietbeginn: 01.03.2024
Unbefristeter Mietvertrag

Mietzins: EUR 850,00
Betriebskosten: EUR 150,00
"""

result = service.process_mietvertrag_from_text(text)
```

### Validate Extraction

```python
# Validate extraction and get recommendations
validation = service.validate_extraction(result)

print(f"Status: {validation['status']}")
print(f"Issues: {validation['issues']}")
print(f"Warnings: {validation['warnings']}")
print(f"Recommendations: {validation['recommendations']}")

# Check critical fields
if validation['status'] == 'ready':
    print("✅ Ready for automatic processing")
elif validation['status'] == 'requires_review':
    print("⚠️ Manual review recommended")
else:
    print("❌ Manual entry required")
```

### Convert to Dictionary

```python
# Convert result to dictionary for API response
result_dict = result.to_dict()

# Returns:
{
    "extracted_data": {
        "property_address": "Hauptstraße 123/5, 1010 Wien",
        "street": "Hauptstraße 123/5",
        "city": "Wien",
        "postal_code": "1010",
        "monthly_rent": 850.00,
        "rental_start_date": "2024-03-01T00:00:00",
        "tenant_name": "Max Mustermann",
        "landlord_name": "Maria Müller",
        "betriebskosten": 150.00,
        "utilities_included": False,
        "contract_type": "Unbefristet",
        "confidence": 0.85
    },
    "raw_text": "...",
    "ocr_confidence": 0.92,
    "extraction_confidence": 0.80,
    "overall_confidence": 0.85,
    "confidence_breakdown": {
        "ocr_quality": 0.92,
        "pattern_matching": 0.80
    }
}
```

## Integration with Property Management

### Pre-fill Property Form

```python
# Extract data from rental contract
result = service.process_mietvertrag(pdf_bytes)
data = result.mietvertrag_data

# Pre-fill property registration form
property_data = {
    "street": data.street,
    "city": data.city,
    "postal_code": data.postal_code,
    "property_type": "rental",  # Inferred from Mietvertrag
    "rental_percentage": 100.0,  # Full rental property
}

# User reviews and confirms before saving
```

### Link to Existing Property

```python
# Use AddressMatcher to find existing properties
from app.services.address_matcher import AddressMatcher

matcher = AddressMatcher(db)
matches = matcher.match_address(data.property_address, user_id)

if matches and matches[0].confidence > 0.9:
    # High confidence match - suggest linking
    property = matches[0].property
    print(f"Found matching property: {property.address}")
else:
    # No match - suggest creating new property
    print("No matching property found. Create new?")
```

## Error Handling

### Common Issues and Solutions

1. **Insufficient OCR Text**
   ```python
   # Error: "OCR extracted insufficient text"
   # Solution: Document may be low quality or not a rental contract
   # - Try rescanning at higher resolution
   # - Ensure document is a Mietvertrag
   ```

2. **Missing Critical Fields**
   ```python
   # Validation status: "requires_manual_entry"
   # Solution: Manually enter missing fields
   validation = service.validate_extraction(result)
   for issue in validation['issues']:
       print(f"Missing: {issue}")
   ```

3. **Low Confidence**
   ```python
   # Overall confidence < 0.5
   # Solution: Review all extracted fields
   if result.overall_confidence < 0.5:
       print("⚠️ Low confidence - manual review required")
       # Display all fields for user review
   ```

## Testing

### Run Tests

```bash
cd backend
pytest tests/test_mietvertrag_extractor.py -v
pytest tests/test_mietvertrag_ocr_service.py -v
```

### Test Coverage

- ✅ Property address extraction (standard, reversed, with apartment numbers)
- ✅ Monthly rent extraction (various formats, thousand separators)
- ✅ Contract dates (start date, end date, various formats)
- ✅ Additional costs (Betriebskosten, Heizkosten, Kaution)
- ✅ Utilities information (included/excluded)
- ✅ Parties extraction (tenant, landlord, with titles)
- ✅ Contract type detection (Unbefristet, Befristet)
- ✅ Complete contract extraction
- ✅ Edge cases and error handling
- ✅ Confidence scoring
- ✅ Dictionary conversion

## Performance Considerations

### Processing Time

- **OCR Stage**: 2-5 seconds (depends on document size and quality)
- **Extraction Stage**: < 100ms (pattern matching is fast)
- **Total**: ~2-5 seconds per document

### Optimization Tips

1. **Pre-process Images**: Improve OCR quality by enhancing contrast
2. **Cache Results**: Store extracted data to avoid re-processing
3. **Batch Processing**: Process multiple contracts in parallel

## Future Enhancements

### Potential Improvements

1. **Machine Learning**: Train ML model for field extraction
2. **Multi-page Support**: Handle contracts spanning multiple pages
3. **Table Extraction**: Extract rent payment schedules
4. **Signature Detection**: Verify contract is signed
5. **Language Support**: Support contracts in English

## Related Services

- **KaufvertragOCRService**: Extracts data from purchase contracts
- **AddressMatcher**: Matches addresses to existing properties
- **PropertyService**: Manages property registration
- **OCREngine**: Tesseract OCR wrapper

## Task Status

✅ **Task D.3.3 - Implement MietvertragExtractor: COMPLETE**

All required functionality has been implemented:
- ✅ Extract property address
- ✅ Extract rental_start_date and monthly_rent
- ✅ Extract tenant/landlord names
- ✅ Return confidence scores
- ✅ Comprehensive test coverage
- ✅ Documentation complete

---

**Document Version**: 1.0  
**Last Updated**: 2026-03-08  
**Status**: Implementation Complete
