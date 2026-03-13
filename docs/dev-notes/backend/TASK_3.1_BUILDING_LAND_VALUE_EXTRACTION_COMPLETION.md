# Task 3.1 Sub-task Completion: Building and Land Value Extraction

## Task Details
**Task ID:** Extract: building_value and land_value split if available  
**Parent Task:** Task 3.1 - Create Contract OCR Extractor (Kaufvertrag)  
**Status:** ✅ Completed  
**Date:** 2026-03-07

## Implementation Summary

Successfully implemented extraction of building value (Gebäudewert) and land value (Grundwert/Bodenwert) from Austrian property purchase contracts (Kaufverträge).

## What Was Implemented

### 1. Explicit Value Extraction
The `_extract_value_breakdown()` method in `KaufvertragExtractor` now extracts:

- **Building Value (Gebäudewert)**: Recognizes multiple German terms
  - "Gebäudewert"
  - "Wert des Gebäudes"
  
- **Land Value (Grundwert/Bodenwert)**: Recognizes multiple German terms
  - "Grundwert"
  - "Bodenwert"
  - "Wert des Grundstücks"

### 2. Automatic 80/20 Estimation
When building/land split is not explicitly stated in the contract:
- Building value: 80% of purchase price (Austrian tax convention)
- Land value: 20% of purchase price
- Lower confidence score (0.5) for estimates vs explicit values (0.85)

### 3. Enhanced Number Format Parsing
Fixed `_parse_amount()` method to handle various Austrian number formats:
- `280.000,00` → 280000.00 (standard Austrian format)
- `280.000` → 280000.00 (without decimals)
- `280000,00` → 280000.00 (without thousand separator)
- `1.234.567,89` → 1234567.89 (multiple thousand separators)

**Key improvement:** Detects when dots are thousand separators (groups of 3 digits) vs decimal separators.

## Files Modified

1. **backend/app/services/kaufvertrag_extractor.py**
   - Enhanced `_extract_value_breakdown()` patterns to accept optional decimal places
   - Fixed `_parse_amount()` to correctly parse Austrian number formats with dots as thousand separators

## Files Created

1. **backend/tests/test_kaufvertrag_extractor.py**
   - Comprehensive test suite with 15+ test cases
   - Tests explicit value extraction
   - Tests 80/20 estimation fallback
   - Tests alternative German terminology
   - Tests various number formats
   - Tests complete contract extraction

2. **backend/test_kaufvertrag_standalone.py**
   - Standalone test script for quick validation
   - Runs without full app configuration
   - 5 core test scenarios

## Test Results

All tests passing ✅

```
✓ Test 1: Explicit building and land values extracted correctly
✓ Test 2: 80/20 estimation works correctly
✓ Test 3: Alternative German terms recognized
✓ Test 4: 'Bodenwert' term recognized
✓ Test 5: Complete contract extraction successful (confidence: 0.87)
```

## Usage Example

```python
from app.services.kaufvertrag_extractor import KaufvertragExtractor

extractor = KaufvertragExtractor()

# Example 1: Explicit values in contract
text = """
Kaufpreis: EUR 350.000,00
Gebäudewert: EUR 280.000,00
Grundwert: EUR 70.000,00
"""
result = extractor.extract(text)
# result.building_value = Decimal("280000.00")
# result.land_value = Decimal("70000.00")
# result.field_confidence["building_value"] = 0.85

# Example 2: Estimation when not specified
text = """
Kaufpreis: EUR 300.000,00
Liegenschaft: Teststraße 1, 1020 Wien
"""
result = extractor.extract(text)
# result.building_value = Decimal("240000.00")  # 80% estimate
# result.land_value = Decimal("60000.00")       # 20% estimate
# result.field_confidence["building_value"] = 0.5  # Lower confidence
```

## Austrian Tax Law Compliance

The implementation follows Austrian tax conventions:
- **Building value** is the depreciable portion (subject to AfA)
- **Land value** is not depreciable
- Standard split: ~80% building, ~20% land (when not explicitly stated)
- Explicit contract values take precedence over estimates

## Integration Points

This extraction capability integrates with:
1. **Property Registration** (Task 1.1): Auto-populate building_value and land_value fields
2. **AfA Calculator** (Task 1.5): Uses building_value for depreciation calculations
3. **Property Form** (Task 1.14): Pre-fills form from extracted contract data

## Confidence Scoring

- **High confidence (0.85)**: Explicit values found in contract text
- **Medium confidence (0.5)**: Estimated using 80/20 rule
- **Overall confidence**: Weighted average of all extracted fields

## Next Steps

This sub-task completes the building/land value extraction requirement for Task 3.1. Remaining work for Task 3.1:
- Integration with OCR service (Tesseract) for PDF processing
- API endpoint for contract upload and extraction
- Frontend component for contract upload UI

## Notes

- Handles OCR errors with flexible pattern matching (ä, ö, ü variations)
- Validates extracted values (must be > 0, building_value ≤ purchase_price)
- Graceful fallback to estimation when explicit values not found
- Per-field confidence scoring for transparency
