# Historical Data Import Configuration

This document describes the configuration options for the Historical Data Import feature.

## Environment Variables

### HISTORICAL_IMPORT_MAX_FILE_SIZE_MB

**Type:** Integer  
**Default:** 50  
**Description:** Maximum file size for historical document uploads in megabytes.

This setting controls the maximum size of PDF, CSV, or Excel files that can be uploaded for historical data import. Files larger than this limit will be rejected with an error message.

**Recommended Values:**
- Development: 50 MB
- Production: 100 MB (for large multi-page documents)

**Example:**
```bash
HISTORICAL_IMPORT_MAX_FILE_SIZE_MB=100
```

### HISTORICAL_IMPORT_RETENTION_DAYS

**Type:** Integer  
**Default:** 90  
**Description:** Retention period for historical import data in days.

After this period, import sessions and extracted data may be archived or deleted. This helps manage database size and comply with data retention policies. Note that finalized transactions and properties are not affected by this setting - only the import metadata and extracted data.

**Recommended Values:**
- Development: 30 days
- Production: 90-180 days (depending on compliance requirements)

**Example:**
```bash
HISTORICAL_IMPORT_RETENTION_DAYS=180
```

### HISTORICAL_IMPORT_MIN_CONFIDENCE

**Type:** Float (0.0-1.0)  
**Default:** 0.7  
**Description:** Minimum confidence threshold for auto-approval.

Imports with extraction confidence scores below this threshold will be flagged for manual review (`requires_review=true`). This ensures that low-quality extractions are verified by users before being finalized.

**Confidence Thresholds by Document Type:**
- E1 Forms: 0.7 (structured format, high reliability)
- Einkommensteuerbescheid: 0.7 (structured format)
- Kaufvertrag: 0.6 (more variable format)
- Saldenliste: 0.8 (critical financial data)

**Recommended Values:**
- Conservative (high accuracy): 0.8
- Balanced: 0.7
- Permissive (fewer manual reviews): 0.6

**Example:**
```bash
HISTORICAL_IMPORT_MIN_CONFIDENCE=0.75
```

### HISTORICAL_IMPORT_ENABLE_AUTO_LINK

**Type:** Boolean  
**Default:** true  
**Description:** Enable automatic property linking based on address matching.

When enabled, the system will automatically link imported rental income to existing properties if the address match confidence is above 0.9. When disabled, all property links require manual approval in the review interface.

**Behavior:**
- `true`: Auto-link properties with confidence > 0.9, suggest for 0.7-0.9, create new for < 0.7
- `false`: All property links require manual approval regardless of confidence

**Recommended Values:**
- Development: true (faster testing)
- Production: true (for experienced users), false (for new users or high-risk scenarios)

**Example:**
```bash
HISTORICAL_IMPORT_ENABLE_AUTO_LINK=false
```

## Configuration in Code

These environment variables are loaded in `backend/app/core/config.py`:

```python
class Settings(BaseSettings):
    # ... existing settings ...
    
    # Historical Import Settings
    historical_import_max_file_size_mb: int = 50
    historical_import_retention_days: int = 90
    historical_import_min_confidence: float = 0.7
    historical_import_enable_auto_link: bool = True
    
    class Config:
        env_file = ".env"
```

## Usage Examples

### Checking File Size Limit

```python
from app.core.config import settings

def validate_upload_size(file_size_bytes: int) -> bool:
    max_size_bytes = settings.historical_import_max_file_size_mb * 1024 * 1024
    return file_size_bytes <= max_size_bytes
```

### Checking Confidence Threshold

```python
from app.core.config import settings

def requires_manual_review(confidence: float) -> bool:
    return confidence < settings.historical_import_min_confidence
```

### Property Auto-Linking

```python
from app.core.config import settings

def determine_property_action(match_confidence: float) -> str:
    if not settings.historical_import_enable_auto_link:
        return "suggest"  # Always require manual approval
    
    if match_confidence > 0.9:
        return "auto_link"
    elif match_confidence >= 0.7:
        return "suggest"
    else:
        return "create_new"
```

## Security Considerations

1. **File Size Limits:** Set appropriate limits to prevent denial-of-service attacks through large file uploads
2. **Retention Period:** Balance between user convenience and data minimization (GDPR compliance)
3. **Confidence Thresholds:** Higher thresholds increase accuracy but require more manual work
4. **Auto-Linking:** Disable in high-security environments to ensure all property links are manually verified

## Monitoring

Monitor these metrics to tune configuration:
- Average extraction confidence by document type
- Percentage of imports requiring manual review
- False positive rate for auto-linked properties
- User correction frequency

Adjust thresholds based on these metrics to optimize the balance between automation and accuracy.
