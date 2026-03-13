# Confidence Scores - Quick Start Guide

## What Was Completed

✅ **Task 3.1 Sub-Task**: "Return structured data with confidence scores"

The KaufvertragExtractor now returns comprehensive confidence scores for all extracted fields, enabling intelligent decision-making about data quality.

## Quick Test

```bash
cd backend
python test_confidence_validation.py
```

Expected output:
```
✅ ALL TESTS PASSED - Confidence scoring is working correctly!
```

## Usage

```python
from app.services.kaufvertrag_extractor import KaufvertragExtractor

extractor = KaufvertragExtractor()
result = extractor.extract(ocr_text)
result_dict = extractor.to_dict(result)

# Check overall confidence
print(f"Confidence: {result_dict['confidence']:.2f}")

# Check field-level confidence
for field, conf in result_dict['field_confidence'].items():
    print(f"{field}: {conf:.2f}")
```

## Output Structure

```python
{
    # Extracted data
    "property_address": "Hauptstraße 123, 1010 Wien",
    "purchase_price": 350000.0,
    "building_value": 280000.0,
    # ... more fields ...
    
    # Confidence scores
    "field_confidence": {
        "property_address": 0.85,
        "purchase_price": 0.90,
        "building_value": 0.85,
        # ... more scores ...
    },
    "confidence": 0.87  # Overall confidence
}
```

## Confidence Levels

- **≥ 0.7**: High confidence - suitable for auto-population
- **0.5 - 0.7**: Medium confidence - review recommended  
- **< 0.5**: Low confidence - manual entry required

## Files

- **Implementation**: `backend/app/services/kaufvertrag_extractor.py`
- **Tests**: `backend/tests/test_kaufvertrag_extractor.py`
- **Validation**: `backend/test_confidence_validation.py`
- **Documentation**: `backend/docs/kaufvertrag_extractor_confidence_scores.md`
- **Summary**: `backend/TASK_3.1_CONFIDENCE_SCORES_COMPLETION.md`

## Next Steps

This feature is ready for integration with:
1. Document upload API endpoints
2. Property registration form (frontend)
3. OCR processing pipeline (Tesseract)

See `backend/docs/kaufvertrag_extractor_confidence_scores.md` for complete documentation.
