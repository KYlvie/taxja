# Kaufvertrag Extractor - Confidence Scores Documentation

## Overview

The `KaufvertragExtractor` returns structured data with confidence scores for each extracted field. This allows downstream systems to make informed decisions about data quality and whether manual review is needed.

## Confidence Score Levels

### Overall Confidence
- **High (≥ 0.7)**: Data is reliable, can be used for automatic property registration
- **Medium (0.5 - 0.7)**: Data should be reviewed by user before use
- **Low (< 0.5)**: Significant manual review required, many fields missing

### Field-Level Confidence
Each extracted field has its own confidence score:

- **0.95**: Exact match with high certainty (e.g., postal code)
- **0.90**: Strong pattern match (e.g., purchase price with clear formatting)
- **0.85**: Good pattern match (e.g., property address, dates)
- **0.80**: Reasonable match (e.g., names, fees)
- **0.75**: Acceptable match with some ambiguity (e.g., notary name)
- **0.50**: Estimated value (e.g., building/land split when not explicitly stated)

## Output Structure

The `to_dict()` method returns a dictionary with the following structure:

```python
{
    # Property information
    "property_address": "Hauptstraße 123, 1010 Wien",
    "street": "Hauptstraße 123",
    "city": "Wien",
    "postal_code": "1010",
    
    # Purchase details
    "purchase_price": 350000.0,
    "purchase_date": "2020-06-15T00:00:00",
    
    # Value breakdown
    "building_value": 280000.0,
    "land_value": 70000.0,
    
    # Purchase costs
    "grunderwerbsteuer": 12250.0,
    "notary_fees": 3500.0,
    "registry_fees": 1050.0,
    
    # Parties
    "buyer_name": "Max Mustermann",
    "seller_name": "Maria Musterfrau",
    
    # Notary information
    "notary_name": "Dr. Hans Schmidt",
    "notary_location": "Wien",
    
    # Building details
    "construction_year": 1985,
    "property_type": "Wohnung",
    
    # Confidence scores
    "field_confidence": {
        "property_address": 0.85,
        "street": 0.90,
        "city": 0.90,
        "postal_code": 0.95,
        "purchase_price": 0.90,
        "purchase_date": 0.85,
        "building_value": 0.85,
        "land_value": 0.85,
        "buyer_name": 0.80,
        "seller_name": 0.80,
        "notary_name": 0.75,
        "construction_year": 0.85
    },
    "confidence": 0.87
}
```

## Usage Examples

### Example 1: High Confidence Extraction

```python
from app.services.kaufvertrag_extractor import KaufvertragExtractor

extractor = KaufvertragExtractor()

text = """
KAUFVERTRAG

Liegenschaft: Hauptstraße 123, 1010 Wien
Kaufpreis: EUR 350.000,00
Gebäudewert: EUR 280.000,00
Grundwert: EUR 70.000,00

Kaufdatum: 15.06.2020
Käufer: Max Mustermann
Verkäufer: Maria Musterfrau
"""

result = extractor.extract(text)
result_dict = extractor.to_dict(result)

if result_dict['confidence'] >= 0.7:
    # High confidence - can auto-populate property form
    print("✓ High confidence extraction")
    print(f"  Address: {result_dict['property_address']}")
    print(f"  Price: €{result_dict['purchase_price']:,.2f}")
else:
    # Low confidence - require manual review
    print("⚠ Low confidence - manual review required")
```

### Example 2: Field-Level Confidence Checking

```python
result = extractor.extract(text)
result_dict = extractor.to_dict(result)

# Check confidence for critical fields
critical_fields = ['property_address', 'purchase_price', 'purchase_date']

for field in critical_fields:
    confidence = result_dict['field_confidence'].get(field, 0.0)
    value = result_dict.get(field)
    
    if confidence >= 0.8:
        print(f"✓ {field}: {value} (confidence: {confidence:.2f})")
    elif confidence >= 0.5:
        print(f"⚠ {field}: {value} (confidence: {confidence:.2f}) - review recommended")
    else:
        print(f"✗ {field}: {value} (confidence: {confidence:.2f}) - manual entry required")
```

### Example 3: Handling Estimated Values

```python
result = extractor.extract(text)
result_dict = extractor.to_dict(result)

# Check if building/land values were estimated
building_conf = result_dict['field_confidence'].get('building_value', 0.0)
land_conf = result_dict['field_confidence'].get('land_value', 0.0)

if building_conf == 0.5 and land_conf == 0.5:
    print("⚠ Building/land values were estimated using 80/20 rule")
    print(f"  Building: €{result_dict['building_value']:,.2f} (80%)")
    print(f"  Land: €{result_dict['land_value']:,.2f} (20%)")
    print("  Please verify these values in the contract")
else:
    print("✓ Building/land values extracted from contract")
```

## Integration with Property Registration

When integrating with the property registration API:

```python
result = extractor.extract(ocr_text)
result_dict = extractor.to_dict(result)

# Prepare property registration data
property_data = {
    "street": result_dict['street'],
    "city": result_dict['city'],
    "postal_code": result_dict['postal_code'],
    "purchase_price": result_dict['purchase_price'],
    "purchase_date": result_dict['purchase_date'],
    "building_value": result_dict['building_value'],
    "construction_year": result_dict['construction_year'],
}

# Include confidence metadata for frontend
metadata = {
    "extraction_confidence": result_dict['confidence'],
    "field_confidence": result_dict['field_confidence'],
    "requires_review": result_dict['confidence'] < 0.7
}

# Return to frontend for user review
return {
    "property_data": property_data,
    "metadata": metadata
}
```

## Confidence Calculation Algorithm

The overall confidence is calculated as a weighted average:

1. **Critical fields** (weight: 2.0):
   - `property_address`
   - `purchase_price`
   - `purchase_date`

2. **Important fields** (weight: 1.0):
   - `street`, `city`, `postal_code`
   - `building_value`
   - `buyer_name`, `seller_name`

3. **Formula**:
   ```
   confidence = (sum of weighted field confidences) / (total weight)
   ```

4. **Example**:
   - If all critical fields are extracted with 0.9 confidence: 2.0 * 0.9 * 3 = 5.4
   - If all important fields are extracted with 0.8 confidence: 1.0 * 0.8 * 6 = 4.8
   - Total weight: 2.0 * 3 + 1.0 * 6 = 12.0
   - Overall confidence: (5.4 + 4.8) / 12.0 = 0.85

## Best Practices

1. **Always check overall confidence** before auto-populating forms
2. **Flag low-confidence fields** for user review in the UI
3. **Show confidence scores** to users so they understand data quality
4. **Require manual confirmation** when confidence < 0.7
5. **Log confidence scores** for monitoring extraction quality over time
6. **Use field-level confidence** to prioritize which fields need review

## Testing

Run the validation script to verify confidence scoring:

```bash
cd backend
python test_confidence_validation.py
```

This will test:
- Comprehensive extraction with high confidence
- Minimal extraction with low confidence
- Structured output format validation
- Field-level confidence score ranges

## Future Improvements

Potential enhancements to confidence scoring:

1. **Machine learning-based confidence**: Train a model to predict confidence based on OCR quality
2. **Context-aware scoring**: Adjust confidence based on document structure and formatting
3. **Cross-field validation**: Increase confidence when multiple fields corroborate each other
4. **Historical accuracy tracking**: Adjust confidence based on past extraction accuracy
