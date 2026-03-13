# OCR Module Documentation

## Overview

The OCR (Optical Character Recognition) module provides intelligent document processing for the Taxja tax management system. It automatically extracts structured data from Austrian tax documents including receipts, invoices, payslips, and more.

## Features

- **Multi-format Support**: JPEG, PNG, PDF
- **Document Classification**: Automatic identification of document types
- **Field Extraction**: Structured data extraction (dates, amounts, merchants, etc.)
- **Austrian Optimization**: Optimized for Austrian documents and merchants
- **Batch Processing**: Parallel processing of multiple documents
- **Quality Assessment**: Confidence scoring and quality suggestions
- **Celery Integration**: Asynchronous background processing

## Architecture

```
OCR Module
├── OCREngine (Main orchestrator)
├── ImagePreprocessor (Image optimization)
├── DocumentClassifier (Document type identification)
├── FieldExtractor (Data extraction)
└── MerchantDatabase (Austrian merchant recognition)
```

## Components

### 1. OCREngine

Main processing pipeline that coordinates all OCR operations.

**Key Methods**:
- `process_document(image_bytes)` - Process single document
- `process_batch(image_bytes_list)` - Process multiple documents

**Example**:
```python
from app.services.ocr_engine import OCREngine

ocr = OCREngine()
with open('receipt.jpg', 'rb') as f:
    result = ocr.process_document(f.read())

print(f"Type: {result.document_type}")
print(f"Confidence: {result.confidence_score}")
print(f"Data: {result.extracted_data}")
```

### 2. ImagePreprocessor

Optimizes images for better OCR accuracy.

**Operations**:
- Resize to optimal dimensions
- Grayscale conversion
- Deskewing (rotation correction)
- Noise removal
- Contrast enhancement (CLAHE)

**Example**:
```python
from app.services.image_preprocessor import ImagePreprocessor
import cv2

preprocessor = ImagePreprocessor()
image = cv2.imread('receipt.jpg')
processed = preprocessor.preprocess(image)

# Check quality
quality = preprocessor.get_image_quality_score(image)
suggestions = preprocessor.suggest_improvements(image)
```

### 3. DocumentClassifier

Identifies document types using pattern matching.

**Supported Types**:
- `PAYSLIP` - Lohnzettel / Gehaltsabrechnung
- `RECEIPT` - Supermarket receipts
- `INVOICE` - Rechnung
- `SVS_NOTICE` - SVS contribution notice
- `LOHNZETTEL` - Official tax wage slip
- `RENTAL_CONTRACT` - Mietvertrag
- `BANK_STATEMENT` - Kontoauszug
- `PROPERTY_TAX` - Grundsteuer

**Example**:
```python
from app.services.document_classifier import DocumentClassifier

classifier = DocumentClassifier()
doc_type, confidence = classifier.classify(image, text)

if confidence > 0.8:
    print(f"High confidence: {doc_type}")
```

### 4. FieldExtractor

Extracts structured fields from OCR text.

**Receipt Fields**:
- Date (DD.MM.YYYY)
- Total amount (€)
- Merchant name
- Line items
- VAT amounts (20%, 10%)

**Payslip Fields**:
- Gross income (Brutto)
- Net income (Netto)
- Withheld tax (Lohnsteuer)
- Social insurance contributions
- Employer name

**Invoice Fields**:
- Invoice number
- Date
- Total amount
- VAT amount
- Supplier name

**Example**:
```python
from app.services.field_extractor import FieldExtractor
from app.services.document_classifier import DocumentType

extractor = FieldExtractor()
fields = extractor.extract_fields(text, DocumentType.RECEIPT)

print(f"Date: {fields['date']}")
print(f"Amount: {fields['amount']}")
print(f"Merchant: {fields['merchant']}")
```

### 5. MerchantDatabase

Database of common Austrian merchants for recognition.

**Included Merchants**:
- Supermarkets: BILLA, SPAR, HOFER, LIDL, MERKUR, PENNY
- Hardware: OBI, bauMax, HORNBACH, BAUHAUS
- Drugstores: dm, Müller, BIPA
- Electronics: MediaMarkt, Saturn
- Office: LIBRO, PAGRO
- Furniture: IKEA, XXXLutz
- Gas stations: OMV, BP, Shell

**Example**:
```python
from app.services.merchant_database import MerchantDatabase

merchant_db = MerchantDatabase()
info = merchant_db.lookup_merchant("billa")

print(f"Official Name: {info.official_name}")
print(f"Category: {info.category}")
print(f"VAT Rate: {info.vat_rate}")
```

## Celery Tasks

### Single Document Processing

```python
from app.tasks.ocr_tasks import process_document_ocr

# Async processing
task = process_document_ocr.delay(document_id=123)
result = task.get()  # Wait for completion
```

### Batch Processing

```python
from app.tasks.ocr_tasks import batch_process_documents

# Process multiple documents in parallel
task = batch_process_documents.delay([101, 102, 103, 104])
result = task.get()

print(f"Success: {result['success_count']}")
print(f"Failed: {result['failure_count']}")
```

### Reprocess Low Confidence

```python
from app.tasks.ocr_tasks import reprocess_low_confidence_documents

# Reprocess all documents with confidence < 0.6
task = reprocess_low_confidence_documents.delay(threshold=0.6)
```

## Configuration

### OCR Settings

Located in `app/core/ocr_config.py`:

```python
class OCRConfig:
    TESSERACT_CONFIG = '--oem 3 --psm 6 -l deu+eng'
    CONFIDENCE_THRESHOLD = 0.6
    IMAGE_MAX_WIDTH = 2000
    IMAGE_MAX_HEIGHT = 2000
    SUPPORTED_FORMATS = ['jpg', 'jpeg', 'png', 'pdf']
    MAX_FILE_SIZE_MB = 10
```

### Environment Variables

```bash
# Tesseract path (Windows)
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe

# MinIO/S3 storage
MINIO_ENDPOINT=http://localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=taxja-documents
```

## API Integration

### Upload and Process Document

```python
from fastapi import UploadFile
from app.services.ocr_engine import OCREngine
from app.services.storage_service import StorageService

async def upload_document(file: UploadFile, user_id: int):
    # Read file
    image_bytes = await file.read()
    
    # Validate
    ocr = OCREngine()
    if not ocr.validate_file_size(len(image_bytes)):
        raise ValueError("File too large")
    
    # Store in MinIO
    storage = StorageService()
    file_path = f"users/{user_id}/documents/{file.filename}"
    storage.upload_file(image_bytes, file_path)
    
    # Process OCR asynchronously
    from app.tasks.ocr_tasks import process_document_ocr_from_bytes
    task = process_document_ocr_from_bytes.delay(image_bytes, user_id)
    
    return {"task_id": task.id, "file_path": file_path}
```

## Performance

### Benchmarks

- Single document: ~1-3 seconds
- Batch (10 documents): ~5-10 seconds (parallel)
- Image preprocessing: ~100-200ms
- Text extraction: ~500-1000ms
- Field extraction: ~50-100ms

### Optimization Tips

1. **Use batch processing** for multiple documents
2. **Preprocess images** before OCR for better accuracy
3. **Cache results** in Redis for repeated requests
4. **Use Celery** for background processing
5. **Adjust PSM mode** based on document layout

## Error Handling

### Common Issues

**1. Tesseract not found**
```
Error: Tesseract OCR failed: tesseract is not installed
```
Solution: Install Tesseract (see TESSERACT_SETUP.md)

**2. Low confidence**
```
Confidence: 0.35 (needs review)
```
Solution: Improve image quality, better lighting, higher resolution

**3. Missing fields**
```
Date could not be extracted
```
Solution: Check document format, ensure text is clear

### Handling Low Confidence

```python
result = ocr.process_document(image_bytes)

if result.needs_review:
    print("Manual review required")
    print("Suggestions:")
    for suggestion in result.suggestions:
        print(f"  - {suggestion}")
    
    # Prompt user to verify/correct data
    verified_data = prompt_user_verification(result.extracted_data)
```

## Testing

### Unit Tests

```bash
cd backend
pytest tests/test_ocr_properties.py -v
```

### Property-Based Tests

The OCR module includes comprehensive property-based tests using Hypothesis:

- **Property 25**: OCR data structure integrity
- Validates serialization roundtrip
- Checks confidence score bounds
- Verifies field extraction consistency

### Manual Testing

```bash
cd backend
python examples/ocr_demo.py
```

## Best Practices

### 1. Image Quality

- **Resolution**: Minimum 800x600, recommended 1200x900
- **DPI**: 300 DPI for best results
- **Lighting**: Even, bright lighting without shadows
- **Focus**: Sharp, clear text
- **Angle**: Straight-on, not tilted

### 2. Document Preparation

- Flatten documents (no folds or wrinkles)
- Clean background (plain surface)
- Full document visible (no cropping)
- Good contrast between text and background

### 3. Error Handling

```python
try:
    result = ocr.process_document(image_bytes)
    
    if result.confidence_score < 0.6:
        # Low confidence - request manual review
        return {"status": "needs_review", "data": result.extracted_data}
    
    # High confidence - auto-process
    return {"status": "success", "data": result.extracted_data}
    
except Exception as e:
    logger.error(f"OCR failed: {e}")
    return {"status": "error", "message": str(e)}
```

### 4. User Feedback

Always provide feedback to users:

```python
if result.needs_review:
    message = "OCR completed with low confidence. Please review the extracted data."
    
    if result.suggestions:
        message += "\n\nSuggestions:\n"
        message += "\n".join(f"• {s}" for s in result.suggestions)
    
    return {"message": message, "data": result.extracted_data}
```

## Future Enhancements

- [ ] ML-based document classification
- [ ] Custom Tesseract training for Austrian documents
- [ ] Support for handwritten text
- [ ] Multi-page PDF processing
- [ ] Real-time OCR preview
- [ ] OCR result caching
- [ ] Advanced table extraction
- [ ] Integration with Google Cloud Vision API (optional)

## References

- [Tesseract Documentation](https://tesseract-ocr.github.io/)
- [OpenCV Documentation](https://docs.opencv.org/)
- [Austrian Tax Terms Glossary](./austrian_tax_glossary.md)
- [Tesseract Setup Guide](./TESSERACT_SETUP.md)

## Support

For issues or questions:
1. Check the [Tesseract Setup Guide](./TESSERACT_SETUP.md)
2. Review error logs in `logs/ocr.log`
3. Run the demo script: `python examples/ocr_demo.py`
4. Check Celery worker logs: `celery -A app.celery_app worker --loglevel=info`

