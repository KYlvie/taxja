import api from './api';

export interface AuditChecklistItem {
  category: string;
  status: 'pass' | 'warning' | 'fail';
  message: string;
  details?: string[];
}

export interface AuditChecklist {
  overall_status: 'ready' | 'needs_attention' | 'not_ready';
  items: AuditChecklistItem[];
  missing_documents: number;
  compliance_issues: number;
}

export interface DataExportResponse {
  download_url: string;
  file_size: number;
  expires_at: string;
}

export interface TaxPackageExportPart {
  part_number: number;
  file_name: string;
  download_url: string;
  size_bytes: number;
}

export interface TaxPackageExportFailure {
  reason: string;
  document_count?: number;
  estimated_total_size_bytes?: number;
  max_total_size_bytes?: number;
  max_parts?: number;
  max_documents?: number;
  largest_family?: {
    family: string;
    label: string;
    estimated_size_bytes: number;
  } | null;
  largest_files?: Array<{
    document_id: number;
    file_name: string;
    family: string;
    estimated_size_bytes: number;
  }>;
}

export interface TaxPackageExportPreviewWarning {
  key: 'pending_tx_count' | 'pending_docs' | 'uncertain_year_docs' | 'skipped_files';
  label: string;
  count: number;
}

export interface TaxPackageExportPreviewSummary {
  pending_tx_count: number;
  pending_document_count: number;
  uncertain_year_docs: number;
  skipped_files: Array<Record<string, unknown>>;
  [key: string]: unknown;
}

export interface TaxPackageExportPreview {
  tax_year: number;
  language?: string;
  include_foundation_materials?: boolean;
  has_warnings: boolean;
  summary: TaxPackageExportPreviewSummary;
  warnings: TaxPackageExportPreviewWarning[];
}

export interface TaxPackageExportStatus {
  export_id: string;
  status: 'pending' | 'processing' | 'ready' | 'failed';
  tax_year?: number;
  language?: string;
  include_foundation_materials?: boolean;
  expires_at?: string;
  part_count?: number;
  parts?: TaxPackageExportPart[];
  summary?: Record<string, unknown>;
  failure?: TaxPackageExportFailure;
}

export interface EAReportSection {
  key: string;
  label: string;
  items: Array<{
    date: string;
    description: string;
    amount: number;
    is_deductible: boolean;
  }>;
  subtotal: number;
  deductible_subtotal?: number;
}

export interface EAReport {
  report_type: string;
  tax_year: number;
  user_name: string;
  user_type: string;
  tax_number: string;
  generated_at: string;
  income_sections: EAReportSection[];
  expense_sections: EAReportSection[];
  summary: {
    total_income: number;
    total_expenses: number;
    total_deductible: number;
    betriebsergebnis: number;
    total_vat_collected: number;
    total_vat_paid: number;
    vat_balance: number;
  };
  transaction_count: number;
}

// ── Bilanz (Balance Sheet + GuV) types ──────────────────────────────
// UGB §231 Gesamtkostenverfahren GuV + UGB §224 Bilanz

export interface GuvSubItem {
  key: string;
  label: string;
  amount: number;
  amount_prior: number;
}

export interface GuvLine {
  nr: string;
  key: string;
  label: string;
  amount: number;
  amount_prior: number;
  line_type: 'income' | 'expense';
  sub_items: GuvSubItem[];
}

export interface BalanceItem {
  key: string;
  label: string;
  amount: number;
}

export interface BalanceGroup {
  key: string;
  label: string;
  items: BalanceItem[];
  subtotal: number;
}

export interface BilanzReport {
  report_type: string;
  tax_year: number;
  user_name: string;
  user_type: string;
  tax_number: string;
  generated_at: string;
  guv: {
    lines: GuvLine[];
    total_income: number;
    total_expenses: number;
    betriebsergebnis: number;
    betriebsergebnis_prior: number;
    ergebnis_vor_steuern: number;
    ergebnis_vor_steuern_prior: number;
    steuern: number;
    steuern_prior: number;
    ergebnis_nach_steuern: number;
    ergebnis_nach_steuern_prior: number;
    net_profit: number;
  };
  bilanz: {
    aktiva: BalanceGroup[];
    passiva: BalanceGroup[];
    total_aktiva: number;
    total_passiva: number;
  };
  vat_summary: {
    vat_collected: number;
    vat_paid: number;
    vat_balance: number;
  };
  transaction_count: number;
}

export interface TaxFormField {
  kz: string;
  label_de: string;
  label_en: string;
  label_zh: string;
  value: number;
  section: string;
  editable: boolean;
  note_de?: string;
}

export interface TaxFormData {
  form_type: 'E1' | 'L1' | 'K1' | 'E1a' | 'E1b' | 'L1k' | 'U1' | 'UVA';
  form_name_de: string;
  form_name_en: string;
  form_name_zh: string;
  tax_year: number;
  user_name: string;
  tax_number: string;
  generated_at: string;
  fields: TaxFormField[];
  summary: {
    [key: string]: number | Record<string, number> | undefined;
    rental_by_property?: Record<string, number>;
    property_expenses?: Record<string, number>;
    property_depreciation?: number;
  };
  disclaimer_de: string;
  disclaimer_en: string;
  disclaimer_zh: string;
  finanzonline_url: string;
  form_download_url: string;
  // E1b specific: per-property data
  properties?: Array<{
    property_id: string;
    address: string;
    fields: TaxFormField[];
    summary: Record<string, number>;
  }>;
  aggregate_summary?: Record<string, number>;
  // L1k specific: per-child data
  children?: Array<{
    name: string;
    birth_date: string;
    fields: TaxFormField[];
  }>;
}

export interface EligibleForm {
  form_type: string;
  name_de: string;
  name_en: string;
  name_zh: string;
  description_de: string;
  description_en: string;
  description_zh: string;
  category: string;
  has_template?: boolean;
  tax_year?: number;
}

export interface EligibleFormsResponse {
  forms: EligibleForm[];
  user_type: string;
}

// ── Saldenliste mit VJ (Balance List with Prior Year Comparison) types ──
export interface SaldenlisteAccount {
  konto: string;
  label: string;
  current_saldo: number;
  prior_saldo: number;
  deviation_abs: number;
  deviation_pct: number | null;
}

export interface SaldenlisteGroup {
  kontenklasse: number;
  label: string;
  accounts: SaldenlisteAccount[];
  subtotal_current: number;
  subtotal_prior: number;
  subtotal_deviation_abs: number;
  subtotal_deviation_pct: number | null;
}

export interface SaldenlisteSummary {
  aktiva_current: number;
  aktiva_prior: number;
  passiva_current: number;
  passiva_prior: number;
  ertrag_current: number;
  ertrag_prior: number;
  aufwand_current: number;
  aufwand_prior: number;
  gewinn_verlust_current: number;
  gewinn_verlust_prior: number;
}

export interface SaldenlisteReport {
  report_type: string;
  tax_year: number;
  comparison_year: number;
  user_name: string;
  user_type: string;
  generated_at: string;
  groups: SaldenlisteGroup[];
  summary: SaldenlisteSummary;
}

// ── Periodensaldenliste (Period Balance List) types ──────────────────
export interface PeriodensaldenlisteAccount {
  konto: string;
  label: string;
  months: number[]; // 12 elements
  gesamt: number;
}

export interface PeriodensaldenlisteGroup {
  kontenklasse: number;
  label: string;
  accounts: PeriodensaldenlisteAccount[];
  subtotal_months: number[]; // 12 elements
  subtotal_gesamt: number;
}

export interface PeriodensaldenlisteSummary {
  aktiva_months: number[];
  aktiva_gesamt: number;
  passiva_months: number[];
  passiva_gesamt: number;
  ertrag_months: number[];
  ertrag_gesamt: number;
  aufwand_months: number[];
  aufwand_gesamt: number;
  gewinn_verlust_months: number[];
  gewinn_verlust_gesamt: number;
}

export interface PeriodensaldenlisteReport {
  report_type: string;
  tax_year: number;
  user_name: string;
  user_type: string;
  generated_at: string;
  groups: PeriodensaldenlisteGroup[];
  summary: PeriodensaldenlisteSummary;
}

// ── Einkommensteuerbescheid (Annual Tax Assessment) types ────────────
export interface BescheidParseResult {
  tax_year: number | null;
  taxpayer_name: string | null;
  finanzamt: string | null;
  steuernummer: string | null;
  einkommen: number | null;
  festgesetzte_einkommensteuer: number | null;
  abgabengutschrift: number | null;
  abgabennachforderung: number | null;
  einkuenfte_nichtselbstaendig: number | null;
  einkuenfte_vermietung: number | null;
  vermietung_details: Array<{ address: string; amount: number }>;
  werbungskosten_pauschale: number | null;
  telearbeitspauschale: number | null;
  confidence: number;
  requires_property_linking?: boolean;
  property_linking_suggestions?: Array<{
    extracted_address: string;
    matched_property_id: string | null;
    confidence_score: number;
    suggested_action: string;
    match_details?: {
      street_match?: boolean;
      postal_code_match?: boolean;
      city_match?: boolean;
    };
  }>;
  [key: string]: unknown;
}

export interface TaxDataConfirmResult {
  message: string;
  tax_filing_data_id: number;
  data_type: string;
  tax_year: number | null;
  saved_data: Record<string, unknown>;
  document_id?: number | null;
  already_confirmed?: boolean;
}

export type BescheidImportResult = TaxDataConfirmResult;

// ── E1 Form types ────────────────────────────────────────────────────
export interface E1FormParseResult {
  tax_year: number | null;
  taxpayer_name: string | null;
  steuernummer: string | null;
  confidence: number;
  all_kz_values: Record<string, number>;
  requires_property_linking?: boolean;
  property_linking_suggestions?: Array<{
    extracted_address?: string;
    property_id?: string;
    address?: string;
    confidence?: number;
    suggested_action?: string;
  }>;
  [key: string]: unknown;
}

export type E1FormImportResult = TaxDataConfirmResult;

const reportService = {
  // Get audit checklist
  getAuditChecklist: async (taxYear: number): Promise<AuditChecklist> => {
    const response = await api.get('/reports/audit-checklist', {
      params: { tax_year: taxYear },
    });
    return response.data;
  },

  // Export all user data (GDPR) - returns blob directly
  exportUserData: async (): Promise<DataExportResponse> => {
    const response = await api.post('/reports/export-user-data');
    return response.data;
  },

  // Export user data as direct file download
  exportUserDataDirect: async (): Promise<Blob> => {
    const response = await api.post('/reports/export-user-data', null, {
      responseType: 'blob',
    });
    return response.data;
  },

  // Download exported data
  downloadExportedData: async (downloadUrl: string): Promise<Blob> => {
    const response = await api.get(downloadUrl, {
      responseType: 'blob',
    });
    return response.data;
  },

  // Generate E/A Rechnung
  generateEAReport: async (taxYear: number, language: string = 'de'): Promise<EAReport> => {
    const response = await api.post('/reports/ea-report', {
      tax_year: taxYear,
      language,
    });
    return response.data;
  },

  // Generate tax form (E1 or L1)
  generateTaxForm: async (taxYear: number): Promise<TaxFormData> => {
    const response = await api.post('/reports/tax-form', {
      tax_year: taxYear,
    });
    return response.data;
  },

  // Download pre-filled E1/L1 PDF
  downloadTaxFormPDF: async (taxYear: number): Promise<Blob> => {
    const response = await api.post('/reports/tax-form-pdf', {
      tax_year: taxYear,
    }, { responseType: 'blob' });
    return response.data;
  },

  // Get eligible forms for current user
  getEligibleForms: async (taxYear?: number): Promise<EligibleFormsResponse> => {
    const params = taxYear ? { tax_year: taxYear } : {};
    const response = await api.get('/reports/eligible-forms', { params });
    return response.data;
  },

  // Generate E1a Beilage (sole proprietor)
  generateE1aForm: async (taxYear: number): Promise<TaxFormData> => {
    const response = await api.post('/reports/tax-form-e1a', {
      tax_year: taxYear,
    });
    return response.data;
  },

  // Generate E1b Beilage (per-property rental)
  generateE1bForm: async (taxYear: number, propertyId?: string): Promise<TaxFormData> => {
    const response = await api.post('/reports/tax-form-e1b', {
      tax_year: taxYear,
      property_id: propertyId || null,
    });
    return response.data;
  },

  // Generate L1k Beilage (employee with children)
  generateL1kForm: async (taxYear: number): Promise<TaxFormData> => {
    const response = await api.post('/reports/tax-form-l1k', {
      tax_year: taxYear,
    });
    return response.data;
  },

  // Generate U1 annual VAT return
  generateU1Form: async (taxYear: number): Promise<TaxFormData> => {
    const response = await api.post('/reports/tax-form-u1', {
      tax_year: taxYear,
    });
    return response.data;
  },

  // Generate UVA (VAT pre-return) annual summary
  generateUvaForm: async (taxYear: number): Promise<TaxFormData> => {
    const response = await api.post('/reports/uva-annual', {
      tax_year: taxYear,
    });
    return response.data;
  },

  // Download filled PDF for any form type
  downloadFilledFormPDF: async (formType: string, taxYear: number, propertyId?: number): Promise<Blob> => {
    const response = await api.post('/reports/tax-form-pdf', {
      form_type: formType,
      tax_year: taxYear,
      property_id: propertyId || null,
    }, { responseType: 'blob' });
    return response.data;
  },

  // Create prepared yearly tax package export
  previewTaxPackageExport: async (
    taxYear: number,
    language: string = 'de',
    includeFoundationMaterials: boolean = false,
  ): Promise<TaxPackageExportPreview> => {
    const response = await api.post('/reports/tax-package/exports/preview', {
      tax_year: taxYear,
      language,
      include_foundation_materials: includeFoundationMaterials,
    });
    return response.data;
  },

  createTaxPackageExport: async (
    taxYear: number,
    language: string = 'de',
    includeFoundationMaterials: boolean = false,
  ): Promise<TaxPackageExportStatus> => {
    const response = await api.post('/reports/tax-package/exports', {
      tax_year: taxYear,
      language,
      include_foundation_materials: includeFoundationMaterials,
    });
    return response.data;
  },

  getTaxPackageExportStatus: async (exportId: string): Promise<TaxPackageExportStatus> => {
    const response = await api.get(`/reports/tax-package/exports/${exportId}`);
    return response.data;
  },

  deleteTaxPackageExport: async (exportId: string): Promise<void> => {
    await api.delete(`/reports/tax-package/exports/${exportId}`);
  },

  // Download E/A Rechnung PDF
  downloadEAReportPDF: async (taxYear: number, language: string = 'de'): Promise<Blob> => {
    const response = await api.post('/reports/ea-report-pdf', {
      tax_year: taxYear,
      language,
    }, { responseType: 'blob' });
    return response.data;
  },

  // Reclassify transactions (re-run classification + deductibility checks)
  reclassifyTransactions: async (taxYear?: number): Promise<{ message: string; updated: number }> => {
    const params = taxYear ? { tax_year: taxYear } : {};
    const response = await api.post('/transactions/reclassify', null, { params });
    return response.data;
  },

  // Generate Bilanz (Balance Sheet + GuV) report
  generateBilanzReport: async (taxYear: number, language: string = 'de'): Promise<BilanzReport> => {
    const response = await api.post('/reports/bilanz-report', {
      tax_year: taxYear,
      language,
    });
    return response.data;
  },

  // Generate Saldenliste mit Vorjahresvergleich
  generateSaldenliste: async (taxYear: number, language: string = 'de'): Promise<SaldenlisteReport> => {
    const response = await api.post('/reports/saldenliste', { tax_year: taxYear, language });
    return response.data;
  },

  // Generate Periodensaldenliste
  generatePeriodensaldenliste: async (taxYear: number, language: string = 'de'): Promise<PeriodensaldenlisteReport> => {
    const response = await api.post('/reports/periodensaldenliste', { tax_year: taxYear, language });
    return response.data;
  },

  // Parse Einkommensteuerbescheid (preview without persisting)
  parseBescheid: async (ocrText: string, documentId?: number): Promise<BescheidParseResult> => {
    const response = await api.post('/tax/parse-bescheid', {
      ocr_text: ocrText,
      document_id: documentId,
    });
    return response.data;
  },

  // Confirm Einkommensteuerbescheid data into TaxFilingData
  importBescheid: async (
    ocrText: string,
    documentId?: number,
    editedData?: Record<string, unknown>,
  ): Promise<BescheidImportResult> => {
    const response = await api.post('/tax/import-bescheid', {
      ocr_text: ocrText,
      document_id: documentId,
      edited_data: editedData,
    });
    return response.data;
  },

  // Upload Bescheid PDF/image and extract text synchronously (no Celery needed)
  uploadBescheid: async (file: File): Promise<BescheidParseResult & { raw_text: string }> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/tax/upload-bescheid', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 30000,
    });
    return response.data;
  },

  // E1 Form preview
  parseE1Form: async (ocrText: string, documentId?: number): Promise<E1FormParseResult> => {
    const response = await api.post('/tax/parse-e1-form', {
      ocr_text: ocrText,
      document_id: documentId,
    });
    return response.data;
  },

  importE1Form: async (
    ocrText: string,
    documentId?: number,
    editedData?: Record<string, unknown>,
  ): Promise<E1FormImportResult> => {
    const response = await api.post('/tax/import-e1-form', {
      ocr_text: ocrText,
      document_id: documentId,
      edited_data: editedData,
    });
    return response.data;
  },

  uploadE1Form: async (file: File): Promise<E1FormParseResult & { raw_text: string }> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/tax/upload-e1-form', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 30000,
    });
    return response.data;
  },
};

export default reportService;
