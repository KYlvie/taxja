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
  form_type: 'E1' | 'L1' | 'K1';
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

export interface BescheidImportTransaction {
  id: number;
  type: string;
  category: string;
  amount: number;
  description: string;
}

export interface BescheidImportResult {
  tax_year: number;
  taxpayer_name: string | null;
  steuernummer: string | null;
  finanzamt: string | null;
  einkommen: number | null;
  festgesetzte_einkommensteuer: number | null;
  abgabengutschrift: number | null;
  abgabennachforderung: number | null;
  transactions_created: number;
  transactions: BescheidImportTransaction[];
  confidence: number;
  bescheid_data: Record<string, unknown>;
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
}

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

export interface E1FormImportResult {
  tax_year: number;
  taxpayer_name: string | null;
  steuernummer: string | null;
  transactions_created: number;
  transactions: Array<{
    id: number;
    type: string;
    amount: number;
    description: string;
    kz: string;
  }>;
  all_kz_values: Record<string, number>;
  requires_property_linking?: boolean;
  property_linking_suggestions?: Array<{
    extracted_address?: string;
    property_id?: string;
    address?: string;
    confidence?: number;
    suggested_action?: string;
  }>;
}

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

  // Parse Einkommensteuerbescheid (preview without creating transactions)
  parseBescheid: async (ocrText: string, documentId?: number): Promise<BescheidParseResult> => {
    const response = await api.post('/tax/parse-bescheid', {
      ocr_text: ocrText,
      document_id: documentId,
    });
    return response.data;
  },

  // Import Einkommensteuerbescheid (creates transactions)
  importBescheid: async (ocrText: string, documentId?: number): Promise<BescheidImportResult> => {
    const response = await api.post('/tax/import-bescheid', {
      ocr_text: ocrText,
      document_id: documentId,
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

  // E1 Form Import
  parseE1Form: async (ocrText: string, documentId?: number): Promise<E1FormParseResult> => {
    const response = await api.post('/tax/parse-e1-form', {
      ocr_text: ocrText,
      document_id: documentId,
    });
    return response.data;
  },

  importE1Form: async (ocrText: string, documentId?: number): Promise<E1FormImportResult> => {
    const response = await api.post('/tax/import-e1-form', {
      ocr_text: ocrText,
      document_id: documentId,
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
