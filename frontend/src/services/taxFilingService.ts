import api from './api';

export interface TaxFilingEntry {
  id: number;
  data_type: string;
  source_document_id: number | null;
  confirmed_at: string | null;
  data: Record<string, any>;
}

export interface TransactionCategorySummary {
  type: string;
  category: string;
  count: number;
  total: number;
  deductible_total: number;
}

export interface TransactionsSummary {
  transaction_count: number;
  income_total: number;
  expense_total: number;
  deductible_total: number;
  by_category: TransactionCategorySummary[];
}

export interface TaxFilingSummary {
  year: number;
  income: TaxFilingEntry[];
  deductions: TaxFilingEntry[];
  vat: TaxFilingEntry[];
  other: TaxFilingEntry[];
  totals: {
    total_income: number;
    total_deductions: number;
    taxable_income: number;
    estimated_tax: number;
    withheld_tax: number;
    estimated_refund: number;
    total_vat_payable: number;
  };
  conflicts: any[];
  record_count: number;
  transactions?: TransactionsSummary;
}

export const taxFilingService = {
  getAvailableYears: async (): Promise<number[]> => {
    const response = await api.get('/tax-filing/years');
    return response.data.years || [];
  },

  getSummary: async (year: number): Promise<TaxFilingSummary> => {
    const response = await api.get(`/tax-filing/${year}/summary`);
    return response.data;
  },
};
