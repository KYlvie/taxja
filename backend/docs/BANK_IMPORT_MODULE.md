# Bank Import Module Documentation

## Overview

The Bank Import Module enables users to import transactions from Austrian bank statements in multiple formats. It supports CSV files from major Austrian banks and the MT940 SWIFT standard format. The module includes automatic transaction classification and duplicate detection.

## Supported Formats

### CSV Format

Supports the following Austrian banks:
- **Raiffeisen**: Standard Raiffeisen CSV export format
- **Erste Bank**: Erste Bank CSV format with Valutadatum
- **Sparkasse**: Sparkasse CSV format with Buchungstag
- **Bank Austria**: Bank Austria CSV format
- **Generic**: Auto-detection for other CSV formats

### MT940 Format

Supports the SWIFT MT940 standard format used by most Austrian banks for electronic statements.

### PSD2 API (Optional)

Direct bank integration via PSD2 (Payment Services Directive 2) for real-time transaction fetching with user consent.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Bank Import API                          │
│  POST /api/v1/transactions/import                           │
│  POST /api/v1/transactions/preview                          │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  BankImportService                           │
│  - Orchestrates import process                              │
│  - Handles format detection                                 │
│  - Manages duplicate detection                              │
│  - Triggers auto-classification                             │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  CSVParser   │   │ MT940Parser  │   │ PSD2Client   │
│              │   │              │   │              │
│ - Parse CSV  │   │ - Parse      │   │ - OAuth2     │
│ - Detect     │   │   MT940      │   │ - Fetch      │
│   bank       │   │ - Extract    │   │   trans.     │
│   format     │   │   fields     │   │              │
└──────────────┘   └──────────────┘   └──────────────┘
```

## Components

### 1. CSVParser

**File**: `app/services/csv_parser.py`

Parses CSV files from Austrian banks with support for:
- Multiple date formats (DD.MM.YYYY, DD/MM/YYYY, YYYY-MM-DD, etc.)
- Austrian decimal format (1.234,56)
- International decimal format (1,234.56)
- Multiple delimiters (semicolon, comma, tab)
- Automatic bank format detection

**Usage**:

```python
from app.services.csv_parser import CSVParser, BankFormat

# Auto-detect bank format
parser = CSVParser()
transactions = parser.parse(csv_content)

# Specify bank format
parser = CSVParser(bank_format=BankFormat.RAIFFEISEN)
transactions = parser.parse(csv_content)

# Validate before parsing
validation = parser.validate_csv(csv_content)
if validation["valid"]:
    print(f"Found {validation['transaction_count']} transactions")
```

**Supported Bank Formats**:

| Bank | Column Names | Date Format | Decimal Separator |
|------|-------------|-------------|-------------------|
| Raiffeisen | Buchungsdatum, Betrag, Buchungstext | DD.MM.YYYY | , (comma) |
| Erste Bank | Valutadatum, Betrag, Verwendungszweck | DD.MM.YYYY | , (comma) |
| Sparkasse | Buchungstag, Betrag, Verwendungszweck | DD.MM.YYYY | , (comma) |
| Bank Austria | Buchungsdatum, Betrag, Buchungstext | DD/MM/YYYY | , (comma) |

### 2. MT940Parser

**File**: `app/services/mt940_parser.py`

Parses MT940 SWIFT standard format bank statements.

**MT940 Format Structure**:
- `:20:` - Transaction Reference Number
- `:25:` - Account Number
- `:28C:` - Statement Number
- `:60F:` - Opening Balance
- `:61:` - Transaction Details (date, amount, type)
- `:86:` - Additional Information (description)
- `:62F:` - Closing Balance

**Usage**:

```python
from app.services.mt940_parser import MT940Parser

parser = MT940Parser()
transactions = parser.parse(mt940_content)

# Validate before parsing
validation = parser.validate_mt940(mt940_content)
if validation["valid"]:
    print(f"Found {validation['transaction_count']} transactions")
```

### 3. BankImportService

**File**: `app/services/bank_import_service.py`

High-level service that orchestrates the import process.

**Features**:
- Format detection and parsing
- Auto-classification of transactions
- Duplicate detection
- Error handling and reporting
- Preview functionality

**Usage**:

```python
from app.services.bank_import_service import BankImportService, ImportFormat

service = BankImportService()

# Import transactions
result = service.import_transactions(
    file_content=csv_content,
    import_format=ImportFormat.CSV,
    user=current_user,
    tax_year=2026,
    auto_classify=True,
    skip_duplicates=True,
)

print(f"Imported: {result.imported_count}")
print(f"Duplicates: {result.duplicate_count}")
print(f"Errors: {result.error_count}")

# Preview import
preview = service.preview_import(
    file_content=csv_content,
    import_format=ImportFormat.CSV,
)
```

### 4. PSD2Client (Optional)

**File**: `app/services/psd2_client.py`

Client for direct bank integration via PSD2 API.

**Features**:
- OAuth2 authorization flow
- Account listing
- Transaction fetching
- Balance retrieval
- Token refresh

**Usage**:

```python
from app.services.psd2_client import PSD2Client, PSD2Provider

# Initialize client
client = PSD2Client(
    provider=PSD2Provider.RAIFFEISEN,
    client_id="your_client_id",
    client_secret="your_client_secret",
    redirect_uri="https://taxja.at/callback",
)

# Step 1: Get authorization URL
auth_url = client.get_authorization_url(state="random_state")
# Redirect user to auth_url

# Step 2: Exchange code for token (after callback)
token_data = client.exchange_code_for_token(authorization_code)

# Step 3: Fetch transactions
accounts = client.get_accounts()
transactions = client.get_transactions(
    account_id=accounts[0]["id"],
    date_from=datetime(2026, 1, 1),
    date_to=datetime(2026, 12, 31),
)
```

## API Endpoints

### POST /api/v1/transactions/import

Import transactions from bank statement file.

**Request**:
- `file`: Bank statement file (multipart/form-data)
- `import_format`: "csv" or "mt940"
- `tax_year`: Tax year for transactions
- `auto_classify`: Auto-classify transactions (default: true)
- `skip_duplicates`: Skip duplicate transactions (default: true)
- `bank_format`: Specific bank format for CSV (optional)

**Response**:
```json
{
  "success": true,
  "message": "Imported 45 of 50 transactions",
  "result": {
    "total_count": 50,
    "imported_count": 45,
    "duplicate_count": 5,
    "error_count": 0,
    "transactions": [...],
    "duplicates": [...],
    "errors": []
  }
}
```

### POST /api/v1/transactions/preview

Preview import without saving to database.

**Request**:
- `file`: Bank statement file
- `import_format`: "csv" or "mt940"
- `bank_format`: Specific bank format (optional)

**Response**:
```json
{
  "success": true,
  "preview": {
    "valid": true,
    "total_count": 50,
    "income_count": 10,
    "expense_count": 40,
    "total_income": "5000.00",
    "total_expenses": "3500.00",
    "date_range": {
      "start": "2026-01-01",
      "end": "2026-12-31"
    },
    "detected_format": "raiffeisen",
    "sample_transactions": [...]
  }
}
```

### GET /api/v1/transactions/formats

Get supported formats and banks.

**Response**:
```json
{
  "import_formats": [
    {
      "value": "csv",
      "label": "CSV",
      "description": "Comma-separated values format",
      "extensions": [".csv"]
    },
    {
      "value": "mt940",
      "label": "MT940",
      "description": "SWIFT MT940 standard format",
      "extensions": [".mt940", ".sta", ".txt"]
    }
  ],
  "bank_formats": [...]
}
```

## Features

### Automatic Classification

Imported transactions are automatically classified using the TransactionClassifier:
- Rule-based classification for known merchants
- ML-based classification for unknown transactions
- Deductibility checking based on user type
- Confidence scoring

### Duplicate Detection

The DuplicateDetector identifies duplicate transactions based on:
- Same date
- Same amount
- Similar description (>80% similarity)

Duplicates are:
- Reported in import results
- Optionally skipped during import
- Logged for user review

### Error Handling

The import process handles various errors gracefully:
- Invalid file format
- Parsing errors
- Missing required fields
- Invalid data types
- Encoding issues

Errors are:
- Logged with details
- Reported in import results
- Do not stop the entire import process

## Testing

### Unit Tests

**File**: `backend/tests/test_csv_import.py`

Tests cover:
- CSV parsing for all supported banks
- Date format parsing
- Decimal format parsing (Austrian and international)
- Delimiter detection
- Bank format auto-detection
- Duplicate detection
- Error handling
- Import service functionality

**Run tests**:
```bash
cd backend
pytest tests/test_csv_import.py -v
```

### Test Data

Example CSV files for testing:

**Raiffeisen Format**:
```csv
Buchungsdatum;Betrag;Buchungstext;Referenz
31.12.2026;-123,45;BILLA DANKT 1234;REF123
15.12.2026;2500,00;Gehalt Dezember;SAL456
```

**Erste Bank Format**:
```csv
Valutadatum;Betrag;Verwendungszweck;Belegnummer
31.12.2026;-50,00;SPAR DANKT;BEL001
20.12.2026;1500,00;Miete Jänner 2027;BEL002
```

**MT940 Format**:
```
:20:STATEMENT123
:25:AT611904300234573201
:28C:00001/001
:60F:C261201EUR10000,00
:61:2612310101DR123,45NMSCNONREF
:86:BILLA DANKT 1234
:62F:C261231EUR9876,55
```

## Configuration

### Environment Variables

```bash
# PSD2 Configuration (optional)
PSD2_RAIFFEISEN_CLIENT_ID=your_client_id
PSD2_RAIFFEISEN_CLIENT_SECRET=your_client_secret
PSD2_ERSTE_BANK_CLIENT_ID=your_client_id
PSD2_ERSTE_BANK_CLIENT_SECRET=your_client_secret

# Import Settings
MAX_IMPORT_FILE_SIZE=10485760  # 10MB
IMPORT_BATCH_SIZE=1000
```

## Best Practices

### For Users

1. **Preview before importing**: Always use the preview endpoint to validate the file
2. **Check duplicates**: Review duplicate transactions before skipping
3. **Verify classifications**: Review auto-classified transactions for accuracy
4. **Use correct format**: Select the correct bank format for better accuracy

### For Developers

1. **Handle encoding**: Support both UTF-8 and ISO-8859-1 encodings
2. **Validate input**: Always validate file format and content before parsing
3. **Log errors**: Log all parsing errors for debugging
4. **Test edge cases**: Test with various date and decimal formats
5. **Handle large files**: Implement streaming for large CSV files

## Troubleshooting

### Common Issues

**Issue**: CSV parsing fails with "Could not parse CSV file"
- **Solution**: Check delimiter (semicolon vs comma) and encoding

**Issue**: Dates not parsed correctly
- **Solution**: Verify date format matches expected format (DD.MM.YYYY)

**Issue**: Amounts incorrect
- **Solution**: Check decimal separator (comma vs dot)

**Issue**: All transactions marked as duplicates
- **Solution**: Adjust duplicate detection threshold or disable skip_duplicates

**Issue**: PSD2 authorization fails
- **Solution**: Verify client credentials and redirect URI match registration

## Future Enhancements

1. **Additional bank formats**: Support for more Austrian banks
2. **PDF parsing**: Extract transactions from PDF statements
3. **Batch import**: Import multiple files at once
4. **Import scheduling**: Automatic periodic imports via PSD2
5. **Import history**: Track all imports with rollback capability
6. **Smart mapping**: Learn user-specific column mappings

## References

- [Berlin Group NextGenPSD2 Framework](https://www.berlin-group.org/)
- [SWIFT MT940 Specification](https://www.swift.com/standards/mt-messages)
- [Austrian Banking Standards](https://www.stuzza.at/)
- [PSD2 Directive](https://ec.europa.eu/info/law/payment-services-psd-2-directive-eu-2015-2366_en)
