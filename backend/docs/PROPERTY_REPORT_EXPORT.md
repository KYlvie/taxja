# Property Report Export Documentation

## Overview

The Property Report Export feature enables landlords to export property financial reports in PDF and CSV formats. This functionality supports both income statements and depreciation schedules with multi-language support (German and English).

## Features

### Supported Report Types

1. **Income Statement**
   - Rental income breakdown
   - Expenses by category
   - Net income calculation
   - Customizable date range

2. **Depreciation Schedule**
   - Year-by-year depreciation breakdown
   - Historical (actual) depreciation
   - Future (projected) depreciation
   - Summary statistics

### Export Formats

1. **PDF Export**
   - Professional formatted reports
   - Property details in header
   - Color-coded tables
   - Multi-page support
   - Generated using ReportLab

2. **CSV Export**
   - Machine-readable format
   - Easy import into spreadsheet applications
   - Includes all report data
   - Property details in header rows

### Multi-Language Support

- **German (de)**: Default language with Austrian tax terminology
- **English (en)**: Full English translations

## API Endpoints

### Income Statement Export

#### PDF Export
```
GET /api/v1/properties/{property_id}/reports/income-statement/export/pdf
```

**Query Parameters:**
- `start_date` (optional): Start date for report (default: beginning of current year)
- `end_date` (optional): End date for report (default: today)
- `language` (optional): Language code (de, en) (default: de)

**Response:**
- Content-Type: `application/pdf`
- Content-Disposition: `attachment; filename=income_statement_{property_id}_{date}.pdf`

**Example:**
```bash
curl -X GET "https://api.taxja.com/api/v1/properties/550e8400-e29b-41d4-a716-446655440000/reports/income-statement/export/pdf?start_date=2026-01-01&end_date=2026-12-31&language=de" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  --output income_statement.pdf
```

#### CSV Export
```
GET /api/v1/properties/{property_id}/reports/income-statement/export/csv
```

**Query Parameters:**
- `start_date` (optional): Start date for report
- `end_date` (optional): End date for report
- `language` (optional): Language code (de, en) (default: de)

**Response:**
- Content-Type: `text/csv`
- Content-Disposition: `attachment; filename=income_statement_{property_id}_{date}.csv`

**Example:**
```bash
curl -X GET "https://api.taxja.com/api/v1/properties/550e8400-e29b-41d4-a716-446655440000/reports/income-statement/export/csv?language=en" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  --output income_statement.csv
```

### Depreciation Schedule Export

#### PDF Export
```
GET /api/v1/properties/{property_id}/reports/depreciation-schedule/export/pdf
```

**Query Parameters:**
- `include_future` (optional): Include future projections (default: true)
- `future_years` (optional): Number of future years to project, 1-50 (default: 10)
- `language` (optional): Language code (de, en) (default: de)

**Response:**
- Content-Type: `application/pdf`
- Content-Disposition: `attachment; filename=depreciation_schedule_{property_id}_{date}.pdf`

**Example:**
```bash
curl -X GET "https://api.taxja.com/api/v1/properties/550e8400-e29b-41d4-a716-446655440000/reports/depreciation-schedule/export/pdf?include_future=true&future_years=15&language=de" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  --output depreciation_schedule.pdf
```

#### CSV Export
```
GET /api/v1/properties/{property_id}/reports/depreciation-schedule/export/csv
```

**Query Parameters:**
- `include_future` (optional): Include future projections (default: true)
- `future_years` (optional): Number of future years to project, 1-50 (default: 10)
- `language` (optional): Language code (de, en) (default: de)

**Response:**
- Content-Type: `text/csv`
- Content-Disposition: `attachment; filename=depreciation_schedule_{property_id}_{date}.csv`

**Example:**
```bash
curl -X GET "https://api.taxja.com/api/v1/properties/550e8400-e29b-41d4-a716-446655440000/reports/depreciation-schedule/export/csv?include_future=false&language=en" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  --output depreciation_schedule.csv
```

## Service Architecture

### PropertyReportExportService

Located at: `backend/app/services/property_report_export_service.py`

**Key Methods:**

1. `export_income_statement_pdf(report_data: Dict) -> bytes`
   - Generates PDF from income statement data
   - Returns PDF as bytes

2. `export_income_statement_csv(report_data: Dict) -> str`
   - Generates CSV from income statement data
   - Returns CSV as string

3. `export_depreciation_schedule_pdf(report_data: Dict) -> bytes`
   - Generates PDF from depreciation schedule data
   - Returns PDF as bytes

4. `export_depreciation_schedule_csv(report_data: Dict) -> str`
   - Generates CSV from depreciation schedule data
   - Returns CSV as string

### PropertyReportService Integration

The `PropertyReportService` has been extended with export methods:

```python
# PDF exports
export_income_statement_pdf(property_id, start_date, end_date, language)
export_depreciation_schedule_pdf(property_id, include_future, future_years, language)

# CSV exports
export_income_statement_csv(property_id, start_date, end_date, language)
export_depreciation_schedule_csv(property_id, include_future, future_years, language)
```

## PDF Report Structure

### Income Statement PDF

1. **Header**
   - Report title (localized)
   - Property details table (address, purchase date, building value)
   - Report period

2. **Income Section**
   - Rental income
   - Total income
   - Color-coded table (blue background)

3. **Expenses Section**
   - Expenses by category
   - Total expenses
   - Color-coded table (red background)

4. **Net Income**
   - Highlighted summary box
   - Green background for positive, red for negative

5. **Footer**
   - Generation date

### Depreciation Schedule PDF

1. **Header**
   - Report title (localized)
   - Property details table (address, purchase date, building value, depreciation rate, status)

2. **Depreciation Schedule Table**
   - Year-by-year breakdown
   - Annual depreciation
   - Accumulated depreciation
   - Remaining value
   - Projected years marked
   - Alternating row colors for readability

3. **Summary Section**
   - Total years
   - Years elapsed
   - Years projected
   - Accumulated depreciation
   - Remaining value
   - Years remaining until fully depreciated
   - Fully depreciated year (if applicable)

4. **Footer**
   - Generation date

## CSV Report Structure

### Income Statement CSV

```csv
Immobiliendetails
Adresse,Teststraße 123, 1010 Wien
Kaufdatum,2020-06-15
Gebäudewert,280000.00

Berichtszeitraum,2026-01-01 Bis 2026-12-31

Einnahmen
Mieteinnahmen,18000.00
Gesamteinnahmen,18000.00

Ausgaben
Ausgaben nach Kategorie
depreciation_afa,5600.00
property_management_fees,1200.00
Gesamtausgaben,6800.00

Nettoeinkommen,11200.00

Erstellt am,2026-03-08
```

### Depreciation Schedule CSV

```csv
Immobiliendetails
Adresse,Teststraße 123, 1010 Wien
Kaufdatum,2020-06-15
Gebäudewert,280000.00
AfA-Satz,2.00%
Status,active

AfA-Plan
Jahr,Jährliche AfA,Kumulierte AfA,Restwert,Type
2020,2800.00,2800.00,277200.00,Tatsächlich
2021,5600.00,8400.00,271600.00,Tatsächlich
2027,5600.00,42000.00,238000.00,Projiziert

Zusammenfassung
Gesamtjahre,56
Vergangene Jahre,6
Projizierte Jahre,10
Kumulierte AfA,33600.00
Restwert,246400.00
Verbleibende Jahre,44.0

Erstellt am,2026-03-08
```

## Translation Keys

### German (de)

- `income_statement`: "Einnahmen-Ausgaben-Rechnung"
- `depreciation_schedule`: "AfA-Plan"
- `property_details`: "Immobiliendetails"
- `rental_income`: "Mieteinnahmen"
- `expenses`: "Ausgaben"
- `net_income`: "Nettoeinkommen"
- `annual_depreciation`: "Jährliche AfA"
- `accumulated_depreciation`: "Kumulierte AfA"
- `remaining_value`: "Restwert"

### English (en)

- `income_statement`: "Income Statement"
- `depreciation_schedule`: "Depreciation Schedule"
- `property_details`: "Property Details"
- `rental_income`: "Rental Income"
- `expenses`: "Expenses"
- `net_income`: "Net Income"
- `annual_depreciation`: "Annual Depreciation"
- `accumulated_depreciation`: "Accumulated Depreciation"
- `remaining_value`: "Remaining Value"

## Testing

### Unit Tests

Located at: `backend/tests/test_property_report_export.py`

**Test Coverage:**
- PDF export in German and English
- CSV export in German and English
- Property details in headers
- CSV parseability
- Projected vs actual depreciation marking
- Empty expense handling
- Multi-language support

### API Integration Tests

Located at: `backend/tests/test_property_report_export_api.py`

**Test Coverage:**
- Endpoint existence
- Language parameter support
- Date range parameter support
- Projection parameter support
- Content type validation
- 404 handling for non-existent properties

### Running Tests

```bash
# Run all export tests
cd backend
pytest tests/test_property_report_export.py -v

# Run API tests
pytest tests/test_property_report_export_api.py -v

# Run with coverage
pytest tests/test_property_report_export*.py --cov=app.services.property_report_export_service
```

## Dependencies

### Python Packages

- **reportlab**: PDF generation library
- **csv**: Built-in CSV handling (Python standard library)

### Existing Services

- `PropertyReportService`: Generates report data
- `PropertyService`: Property ownership validation

## Security Considerations

1. **Authentication Required**: All export endpoints require valid JWT authentication
2. **Ownership Validation**: Users can only export reports for their own properties
3. **Input Validation**: Date ranges and parameters are validated
4. **Rate Limiting**: Consider implementing rate limits for export endpoints to prevent abuse

## Performance Considerations

1. **Caching**: Report data is cached by `PropertyReportService` (24-hour TTL)
2. **Streaming**: Large PDFs are generated in-memory but could be streamed for very large reports
3. **Async Generation**: For very large portfolios, consider async report generation with job queue

## Future Enhancements

1. **Additional Languages**: Add Chinese (zh) translations
2. **Custom Branding**: Allow users to add logos to PDF reports
3. **Email Delivery**: Option to email reports instead of downloading
4. **Batch Export**: Export multiple properties in a single ZIP file
5. **Excel Format**: Add XLSX export option with formulas
6. **Chart Generation**: Include charts and graphs in PDF reports
7. **Report Templates**: Allow users to customize report layouts

## Troubleshooting

### PDF Generation Fails

**Issue**: PDF export returns 500 error

**Solutions:**
1. Check ReportLab is installed: `pip install reportlab`
2. Verify property data is valid
3. Check server logs for detailed error messages

### CSV Encoding Issues

**Issue**: Special characters not displaying correctly

**Solutions:**
1. Ensure UTF-8 encoding is used
2. Open CSV with UTF-8 encoding in Excel/LibreOffice
3. Use `encoding='utf-8-sig'` for Excel compatibility

### Missing Translations

**Issue**: Report shows English text when German is requested

**Solutions:**
1. Verify language parameter is passed correctly
2. Check translation dictionary in `PropertyReportExportService`
3. Ensure language code is lowercase ('de', not 'DE')

## Support

For issues or questions:
- Check API documentation: `/docs` endpoint
- Review test files for usage examples
- Contact development team

---

**Last Updated**: 2026-03-08  
**Version**: 1.0  
**Status**: Production Ready
