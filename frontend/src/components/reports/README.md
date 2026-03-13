# Reports Components

This directory contains components for tax report generation, preview, audit checklist, and data export functionality.

## Components

### ReportGenerator
Allows users to generate tax reports in different formats (PDF, XML, CSV) for a selected tax year.

**Features:**
- Tax year selection (current year and 4 previous years)
- Report type selection (PDF, XML, CSV)
- Language selection for PDF reports (German, English, Chinese)
- Automatic download after generation
- Error handling and success feedback

**Usage:**
```tsx
import ReportGenerator from './components/reports/ReportGenerator';

<ReportGenerator onReportGenerated={(reportId) => console.log(reportId)} />
```

### ReportPreview
Displays a preview of generated reports (PDF or XML).

**Features:**
- PDF preview in iframe
- XML content display with syntax formatting
- Download button
- Loading and error states

**Usage:**
```tsx
import ReportPreview from './components/reports/ReportPreview';

<ReportPreview reportId={123} reportType="pdf" />
```

### AuditChecklist
Displays audit readiness checklist with compliance status.

**Features:**
- Overall audit readiness status (ready/needs attention/not ready)
- Detailed checklist items with pass/warning/fail status
- Missing documents count
- Compliance issues count
- Expandable details for each item
- Disclaimer about audit preparation

**Usage:**
```tsx
import AuditChecklist from './components/reports/AuditChecklist';

<AuditChecklist taxYear={2026} />
```

### DataExport
Allows users to export all their data (GDPR compliance).

**Features:**
- Export all user data as ZIP archive
- Includes: profile, transactions, documents, reports, settings
- Confirmation dialog before export
- GDPR compliance information
- Security notice

**Usage:**
```tsx
import DataExport from './components/reports/DataExport';

<DataExport />
```

## Service

### reportService
API service for report-related operations.

**Methods:**
- `generateReport(request)` - Generate a new tax report
- `getReport(reportId)` - Get report metadata
- `getReports(taxYear?)` - Get all reports for user
- `downloadPDF(reportId)` - Download PDF report
- `downloadXML(reportId)` - Download XML report
- `previewReport(reportId)` - Get PDF blob URL for preview
- `getXMLContent(reportId)` - Get XML content as text
- `getAuditChecklist(taxYear)` - Get audit readiness checklist
- `exportUserData()` - Export all user data (GDPR)
- `downloadExportedData(url)` - Download exported data ZIP

## Styling

Each component has its own CSS file with:
- Responsive design (mobile-first)
- Loading states with spinners
- Error and success alerts
- Accessible color schemes
- Consistent spacing and typography

## Requirements Mapping

- **30.1**: ReportGenerator - Tax report generation with year, type, and language selection
- **30.2**: ReportPreview - PDF and XML preview functionality
- **30.3**: AuditChecklist - Audit readiness checklist with compliance status
- **30.4**: DataExport - GDPR-compliant data export

## Backend API Endpoints

These components expect the following backend endpoints:

- `POST /api/v1/reports/generate` - Generate report
- `GET /api/v1/reports/:id` - Get report metadata
- `GET /api/v1/reports` - List reports
- `GET /api/v1/reports/:id/pdf` - Download PDF
- `GET /api/v1/reports/:id/xml` - Download XML
- `GET /api/v1/reports/audit-checklist` - Get audit checklist
- `POST /api/v1/reports/export-user-data` - Export user data

## Translation Keys

Required translation keys in i18n files:

```json
{
  "reports": {
    "generateReport": "Generate Tax Report",
    "taxYear": "Tax Year",
    "reportType": "Report Type",
    "language": "Language",
    "generate": "Generate Report",
    "preview": "Preview",
    "generationError": "Failed to generate report",
    "generationSuccess": "Report generated successfully",
    "previewError": "Failed to load preview",
    "downloadError": "Failed to download report",
    "aboutReports": "About Reports",
    "pdfDescription": "Comprehensive tax summary for printing or review",
    "xmlDescription": "FinanzOnline-compatible format for electronic filing",
    "csvDescription": "Transaction data export for spreadsheet analysis",
    "types": {
      "pdf": "PDF Report",
      "xml": "XML (FinanzOnline)",
      "csv": "CSV Export"
    },
    "audit": {
      "title": "Audit Readiness Checklist",
      "subtitle": "Tax year {{year}}",
      "loadError": "Failed to load audit checklist",
      "status": {
        "ready": "Ready for Audit",
        "needs_attention": "Needs Attention",
        "not_ready": "Not Ready"
      },
      "missingDocuments": "{{count}} missing documents",
      "complianceIssues": "{{count}} compliance issues",
      "allGood": "All checks passed",
      "categories": {
        "transactions": "Transaction Records",
        "documents": "Supporting Documents",
        "deductions": "Deduction Documentation",
        "vat": "VAT Calculations",
        "completeness": "Data Completeness"
      },
      "disclaimer": {
        "title": "Important Notice",
        "text": "This checklist is for reference only. Final audit requirements may vary. Consult a Steuerberater for complex situations."
      }
    },
    "export": {
      "title": "Export Your Data",
      "subtitle": "Download all your data (GDPR compliance)",
      "whatIsIncluded": "What's Included",
      "format": "Export Format",
      "formatDescription": "All data is exported as a ZIP archive containing JSON files and original documents.",
      "gdprTitle": "GDPR Compliance",
      "gdprText": "You have the right to access and export all your personal data. This export includes everything we store about you.",
      "startExport": "Start Export",
      "confirmTitle": "Confirm Data Export",
      "confirmText": "This will create a complete export of all your data. The download may take a few moments.",
      "error": "Failed to export data",
      "success": "Data exported successfully",
      "securityTitle": "Secure Export",
      "securityText": "Your exported data is encrypted and will be automatically deleted from our servers after 24 hours.",
      "includes": {
        "profile": "User profile and settings",
        "transactions": "All transaction records",
        "documents": "Uploaded documents and OCR data",
        "reports": "Generated tax reports",
        "settings": "Preferences and configurations"
      }
    }
  },
  "languages": {
    "german": "Deutsch",
    "english": "English",
    "chinese": "中文"
  }
}
```
