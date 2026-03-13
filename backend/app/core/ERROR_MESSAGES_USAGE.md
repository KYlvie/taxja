# Error Messages Usage Guide

This guide explains how to use the localized error messages module in the historical data import feature.

## Overview

The `error_messages.py` module provides comprehensive, localized error messages for all common failure scenarios in the historical data import workflow. Messages are available in:
- **German (de)** - Default language
- **English (en)**
- **Chinese (zh)**

## Basic Usage

```python
from app.core.error_messages import get_error_message

# Simple error message (no parameters)
message = get_error_message("duplicate_transaction", "de")
# Returns: "Diese Transaktion wurde bereits importiert. Duplikat verhindert."

# Error message with parameters
message = get_error_message(
    "extraction_low_confidence", 
    "en", 
    confidence=65
)
# Returns: "Data extraction had low confidence (65%). Please review the extracted data manually."

# Multiple parameters
message = get_error_message(
    "invalid_tax_year",
    "de",
    year=2035,
    min_year=2015,
    max_year=2024
)
# Returns: "Ungültiges Steuerjahr: 2035. Muss zwischen 2015 und 2024 liegen."
```

## Integration with Services

### In Import Services

```python
from app.core.error_messages import get_error_message

class E1FormImportService:
    def import_e1_data(self, data: E1FormData, user_id: int, language: str = "de"):
        try:
            # Import logic...
            pass
        except ValueError as e:
            error_msg = get_error_message(
                "import_failed",
                language,
                error=str(e)
            )
            logger.error(error_msg)
            raise ValueError(error_msg)
```

### In Orchestrator

```python
from app.core.error_messages import get_error_message

class HistoricalImportOrchestrator:
    def process_upload(self, upload_id: UUID, language: str = "de"):
        upload = self.db.query(HistoricalImportUpload).filter(...).first()
        
        if not upload:
            error_msg = get_error_message(
                "upload_not_found",
                language,
                upload_id=str(upload_id)
            )
            raise ValueError(error_msg)
        
        # Check confidence threshold
        if upload.extraction_confidence < self.CONFIDENCE_THRESHOLD_E1:
            upload.requires_review = True
            upload.errors.append({
                "type": "low_confidence",
                "message": get_error_message(
                    "extraction_low_confidence",
                    language,
                    confidence=int(upload.extraction_confidence * 100)
                )
            })
```

### In API Endpoints

```python
from fastapi import HTTPException
from app.core.error_messages import get_error_message

@router.post("/historical-import/upload")
async def upload_document(
    request: HistoricalImportUploadRequest,
    language: str = "de"
):
    try:
        # Upload logic...
        pass
    except ValueError as e:
        error_msg = get_error_message(
            "file_too_large",
            language,
            size=file_size_mb,
            max_size=50
        )
        raise HTTPException(status_code=400, detail=error_msg)
```

## Error Categories

### Extraction Errors
- `extraction_low_confidence` - Low confidence extraction requiring review
- `extraction_failed` - General extraction failure
- `ocr_failed` - OCR processing failure
- `ocr_timeout` - OCR processing timeout
- `parsing_error` - Document parsing error
- `missing_required_field` - Required field missing from extraction
- `invalid_document_format` - Invalid document format

### Validation Errors
- `invalid_tax_year` - Tax year out of valid range
- `tax_year_future` - Tax year in the future
- `tax_year_too_old` - Tax year too old
- `invalid_amount` - Invalid amount value
- `invalid_date` - Invalid date format
- `invalid_category` - Invalid category
- `amount_exceeds_limit` - Amount exceeds allowed limit
- `negative_amount_not_allowed` - Negative amount not allowed

### Duplicate and Conflict Errors
- `duplicate_transaction` - Transaction already imported
- `duplicate_transaction_detected` - Possible duplicate detected
- `conflict_detected` - Conflict between documents
- `conflicting_amounts` - Conflicting amounts between documents
- `duplicate_property` - Property already exists

### Import Errors
- `import_failed` - General import failure
- `transaction_creation_failed` - Failed to create transaction
- `property_creation_failed` - Failed to create property
- `property_linking_failed` - Failed to link property
- `depreciation_schedule_failed` - Failed to create depreciation schedule

### File Errors
- `file_too_large` - File exceeds size limit
- `file_type_not_supported` - Unsupported file type
- `file_corrupted` - Corrupted or unreadable file
- `file_not_found` - File not found

### Database Errors
- `user_not_found` - User not found
- `upload_not_found` - Upload not found
- `session_not_found` - Session not found
- `property_not_found` - Property not found
- `database_error` - General database error

### Review and Approval Errors
- `invalid_review_state` - Upload cannot be reviewed in current state
- `approval_failed` - Approval failed
- `rejection_failed` - Rejection failed
- `finalization_failed` - Finalization failed

### Document-Specific Errors

#### Saldenliste
- `saldenliste_parse_error` - Saldenliste parsing error
- `unmapped_accounts` - Accounts could not be mapped
- `account_mapping_failed` - Account mapping failed
- `balance_mismatch` - Balance mismatch detected
- `continuity_check_failed` - Continuity check failed

#### Kaufvertrag
- `missing_purchase_price` - Purchase price missing
- `missing_purchase_date` - Purchase date missing
- `missing_property_address` - Property address missing
- `invalid_building_value` - Invalid building value

#### E1 Form
- `invalid_kz_code` - Invalid KZ code
- `kz_extraction_incomplete` - KZ extraction incomplete

#### Bescheid
- `address_matching_failed` - Address matching failed
- `multiple_address_matches` - Multiple address matches found

### Session Errors
- `session_already_completed` - Session already completed
- `session_failed` - Session failed

### Generic Errors
- `unknown_error` - Unknown error occurred
- `operation_timeout` - Operation timed out
- `permission_denied` - Permission denied

## Helper Functions

### Get All Error Keys
```python
from app.core.error_messages import get_all_error_keys

keys = get_all_error_keys()
# Returns: ['extraction_low_confidence', 'duplicate_transaction', ...]
```

### Get Error Dictionary
```python
from app.core.error_messages import get_error_dict

error_dict = get_error_dict("duplicate_transaction")
# Returns: {
#     'de': 'Diese Transaktion wurde bereits importiert. Duplikat verhindert.',
#     'en': 'This transaction was already imported. Duplicate prevented.',
#     'zh': '此交易已导入。已防止重复。'
# }
```

## Best Practices

1. **Always specify language**: Pass the user's preferred language to `get_error_message()`
2. **Use appropriate error keys**: Choose the most specific error key for the situation
3. **Provide all required parameters**: Ensure all placeholder parameters are provided
4. **Log errors with context**: Include error messages in logs with additional context
5. **Store errors in database**: Save localized error messages in `HistoricalImportUpload.errors`

## Example: Complete Error Handling Flow

```python
from app.core.error_messages import get_error_message
import logging

logger = logging.getLogger(__name__)

def process_saldenliste(file_path: str, user_id: int, language: str = "de"):
    """Process Saldenliste with comprehensive error handling."""
    try:
        # Parse file
        saldenliste_data = parser.parse_csv(file_path)
        
        # Check for unmapped accounts
        unmapped = [acc for acc in saldenliste_data.accounts if not acc.kontenklasse]
        if unmapped:
            error_msg = get_error_message(
                "unmapped_accounts",
                language,
                count=len(unmapped)
            )
            logger.warning(error_msg, extra={
                "user_id": user_id,
                "unmapped_count": len(unmapped)
            })
            # Store error but continue processing
            upload.errors.append({
                "type": "unmapped_accounts",
                "message": error_msg,
                "details": [acc.account_number for acc in unmapped]
            })
        
        # Create transactions
        transactions = create_opening_balance_transactions(
            saldenliste_data.accounts,
            user_id
        )
        
        return {
            "success": True,
            "transactions_created": len(transactions),
            "warnings": upload.errors
        }
        
    except ValueError as e:
        error_msg = get_error_message(
            "saldenliste_parse_error",
            language,
            error=str(e)
        )
        logger.error(error_msg, extra={
            "user_id": user_id,
            "file_path": file_path
        }, exc_info=True)
        
        upload.status = ImportStatus.FAILED
        upload.errors.append({
            "type": "parsing_error",
            "message": error_msg
        })
        
        raise ValueError(error_msg)
```

## Testing

Run the standalone tests to verify error messages:

```bash
python backend/tests/core/test_error_messages_standalone.py
```

Or use pytest (requires environment setup):

```bash
cd backend
pytest tests/test_error_messages.py -v
```

## Adding New Error Messages

To add a new error message:

1. Add the error key and translations to `ERROR_MESSAGES` dictionary in `error_messages.py`
2. Ensure all three languages (de, en, zh) are provided
3. Use consistent parameter naming (e.g., `{field_name}`, `{amount}`, `{error}`)
4. Add test cases to verify the new error message
5. Document the new error in this usage guide

Example:

```python
ERROR_MESSAGES = {
    # ... existing errors ...
    
    "new_error_key": {
        "de": "Deutscher Fehlertext mit {parameter}.",
        "en": "English error text with {parameter}.",
        "zh": "中文错误文本与 {parameter}。",
    },
}
```
