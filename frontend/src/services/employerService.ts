import api from './api';

export type EmployerMonthStatus =
  | 'unknown'
  | 'payroll_detected'
  | 'missing_confirmation'
  | 'no_payroll_confirmed'
  | 'archived_year_only';

export type EmployerAnnualArchiveStatus = 'pending_confirmation' | 'archived';

export interface EmployerMonthDocumentLink {
  document_id: number;
  file_name: string;
  document_type: string;
  relation_type: string;
}

export interface EmployerMonth {
  id: number;
  year_month: string;
  status: EmployerMonthStatus;
  source_type?: string | null;
  payroll_signal?: string | null;
  confidence?: number | null;
  employee_count?: number | null;
  gross_wages?: number | null;
  net_paid?: number | null;
  employer_social_cost?: number | null;
  lohnsteuer?: number | null;
  db_amount?: number | null;
  dz_amount?: number | null;
  kommunalsteuer?: number | null;
  special_payments?: number | null;
  notes?: string | null;
  confirmed_at?: string | null;
  last_signal_at?: string | null;
  documents: EmployerMonthDocumentLink[];
}

export interface EmployerDocumentDetectionResult {
  detected: boolean;
  reason?: string | null;
  month?: EmployerMonth | null;
}

export interface EmployerAnnualArchiveDocumentLink {
  document_id: number;
  file_name: string;
  document_type: string;
  relation_type: string;
}

export interface EmployerAnnualArchive {
  id: number;
  tax_year: number;
  status: EmployerAnnualArchiveStatus;
  source_type?: string | null;
  archive_signal?: string | null;
  confidence?: number | null;
  employer_name?: string | null;
  gross_income?: number | null;
  withheld_tax?: number | null;
  notes?: string | null;
  confirmed_at?: string | null;
  last_signal_at?: string | null;
  documents: EmployerAnnualArchiveDocumentLink[];
}

export interface EmployerAnnualArchiveDetectionResult {
  detected: boolean;
  reason?: string | null;
  archive?: EmployerAnnualArchive | null;
}

export interface EmployerDocumentReviewContext {
  supported: boolean;
  reason?: string | null;
  document_id: number;
  document_type: string;
  candidate_year_month?: string | null;
  candidate_tax_year?: number | null;
  month?: EmployerMonth | null;
  annual_archive?: EmployerAnnualArchive | null;
}

export interface EmployerOverview {
  year: number;
  employer_mode: 'none' | 'occasional' | 'regular';
  total_months: number;
  payroll_months: number;
  missing_confirmation_months: number;
  no_payroll_months: number;
  unknown_months: number;
  next_deadline?: string | null;
  next_deadline_label?: string | null;
}

export interface EmployerMonthSummaryUpdate {
  employee_count?: number;
  gross_wages?: number;
  net_paid?: number;
  employer_social_cost?: number;
  lohnsteuer?: number;
  db_amount?: number;
  dz_amount?: number;
  kommunalsteuer?: number;
  special_payments?: number;
  notes?: string;
}

export const employerService = {
  getOverview: async (year: number): Promise<EmployerOverview> => {
    const response = await api.get('/employer/overview', { params: { year } });
    return response.data;
  },

  getMonths: async (year: number): Promise<EmployerMonth[]> => {
    const response = await api.get('/employer/months', { params: { year } });
    return response.data;
  },

  getAnnualArchives: async (): Promise<EmployerAnnualArchive[]> => {
    const response = await api.get('/employer/annual-archives');
    return response.data;
  },

  getDocumentReviewContext: async (documentId: number): Promise<EmployerDocumentReviewContext> => {
    const response = await api.get(`/employer/documents/${documentId}/review-context`);
    return response.data;
  },

  detectFromDocument: async (documentId: number): Promise<EmployerDocumentDetectionResult> => {
    const response = await api.post(`/employer/documents/${documentId}/detect`);
    return response.data;
  },

  detectAnnualArchiveFromDocument: async (
    documentId: number
  ): Promise<EmployerAnnualArchiveDetectionResult> => {
    const response = await api.post(`/employer/documents/${documentId}/detect-annual-archive`);
    return response.data;
  },

  confirmPayroll: async (payload: {
    year_month: string;
    document_id?: number;
    payroll_signal?: string;
    source_type?: string;
    confidence?: number;
  } & EmployerMonthSummaryUpdate): Promise<EmployerMonth> => {
    const response = await api.post('/employer/months/confirm-payroll', payload);
    return response.data;
  },

  confirmAnnualArchive: async (payload: {
    tax_year: number;
    document_id?: number;
    archive_signal?: string;
    source_type?: string;
    confidence?: number;
    employer_name?: string;
    gross_income?: number;
    withheld_tax?: number;
    notes?: string;
  }): Promise<EmployerAnnualArchive> => {
    const response = await api.post('/employer/annual-archives/confirm', payload);
    return response.data;
  },

  confirmNoPayroll: async (year_month: string, note?: string): Promise<EmployerMonth> => {
    const response = await api.post('/employer/months/confirm-no-payroll', { year_month, note });
    return response.data;
  },

  markMissingConfirmation: async (payload: {
    year_month: string;
    document_id?: number;
    payroll_signal?: string;
    source_type?: string;
    confidence?: number;
  }): Promise<EmployerMonth> => {
    const response = await api.post('/employer/months/mark-missing-confirmation', payload);
    return response.data;
  },

  updateMonth: async (year_month: string, payload: EmployerMonthSummaryUpdate): Promise<EmployerMonth> => {
    const response = await api.put(`/employer/months/${encodeURIComponent(year_month)}`, payload);
    return response.data;
  },
};
