import api from './api';
import {
  transactionTypeRequiresCategory,
  Transaction,
  TransactionFilters,
  TransactionFormData,
  ImportResult,
  PaginationParams,
  PaginatedResponse,
} from '../types/transaction';
import { normalizeTransactionCategoryKey } from '../utils/formatTransactionCategoryLabel';

export interface DeleteCheckResult {
  can_delete: boolean;
  warning_type: 'document_only' | 'document_multi' | 'recurring' | null;
  document_id: number | null;
  document_name: string | null;
  linked_transaction_count: number | null;
  is_from_recurring: boolean;
}

export interface BatchDeleteCheckResult {
  blocked: Array<{ id: number; reason: string; document_name: string | null }>;
  needs_confirmation: Array<{ id: number; warning_type: string; document_name: string | null; linked_count: number | null }>;
  safe: number[];
}

/** Map backend transaction response to frontend Transaction type */
function mapTransaction(raw: any): Transaction {
  return {
    ...raw,
    date: raw.transaction_date || raw.date,
    category:
      normalizeTransactionCategoryKey(raw.income_category || raw.expense_category || raw.category) || undefined,
    amount: Number(raw.amount),
    line_items: raw.line_items?.map((li: any) => ({
      ...li,
      category: normalizeTransactionCategoryKey(li.category) || undefined,
      amount: Number(li.amount),
      quantity: Number(li.quantity ?? 1),
      vat_rate: li.vat_rate != null ? Number(li.vat_rate) : undefined,
      vat_amount: li.vat_amount != null ? Number(li.vat_amount) : undefined,
      vat_recoverable_amount: li.vat_recoverable_amount != null
        ? Number(li.vat_recoverable_amount)
        : undefined,
      classification_confidence: li.classification_confidence != null ? Number(li.classification_confidence) : undefined,
    })) || [],
    deductible_amount: raw.deductible_amount != null ? Number(raw.deductible_amount) : undefined,
    non_deductible_amount: raw.non_deductible_amount != null ? Number(raw.non_deductible_amount) : undefined,
  };
}

export const transactionService = {
  getAll: async (
    filters?: TransactionFilters,
    pagination?: PaginationParams
  ): Promise<PaginatedResponse<Transaction>> => {
    // Map frontend filter names to backend query param names
    const params: Record<string, any> = { ...pagination };
    if (filters) {
      if (filters.start_date) params.date_from = filters.start_date;
      if (filters.end_date) params.date_to = filters.end_date;
      if (filters.type) params.type = filters.type;
      if (filters.search) params.search = filters.search;
      if (filters.is_deductible !== undefined) params.is_deductible = filters.is_deductible;
      if (filters.is_recurring !== undefined) params.is_recurring = filters.is_recurring;
      if (filters.needs_review !== undefined) params.needs_review = filters.needs_review;
    }
    const response = await api.get('/transactions', { params });
    const data = response.data;
    const rawItems = data.transactions || data.items || [];
    return {
      items: rawItems.map(mapTransaction),
      total: data.total || 0,
      page: data.page || 1,
      page_size: data.page_size || 50,
      total_pages: data.total_pages || 0,
    };
  },

  getById: async (id: number): Promise<Transaction> => {
    const response = await api.get(`/transactions/${id}`);
    return mapTransaction(response.data);
  },

  create: async (transaction: TransactionFormData): Promise<Transaction> => {
    // Map frontend field names to backend schema
    const payload: Record<string, any> = {
      type: transaction.type,
      amount: Number(transaction.amount),
      transaction_date: transaction.date,
      description: transaction.description,
      document_id: transaction.document_id,
    };
    // Backend expects income_category or expense_category, not generic "category"
    if (transactionTypeRequiresCategory(transaction.type) && transaction.category) {
      if (transaction.type === 'income') {
        payload.income_category = transaction.category;
      } else {
        payload.expense_category = transaction.category;
      }
    }
    // Include property_id if provided
    if (transaction.property_id) {
      payload.property_id = transaction.property_id;
    }
    if (transaction.line_items) {
      payload.line_items = transaction.line_items.map((lineItem, idx) => ({
        ...lineItem,
        amount: Number(lineItem.amount),
        quantity: Number(lineItem.quantity ?? 1),
        vat_rate: lineItem.vat_rate != null ? Number(lineItem.vat_rate) : undefined,
        vat_amount: lineItem.vat_amount != null ? Number(lineItem.vat_amount) : undefined,
        vat_recoverable_amount: lineItem.vat_recoverable_amount != null
          ? Number(lineItem.vat_recoverable_amount)
          : undefined,
        sort_order: lineItem.sort_order ?? idx,
      }));
    }
    // Recurring fields
    if (transaction.is_recurring) {
      payload.is_recurring = true;
      payload.recurring_frequency = transaction.recurring_frequency || 'monthly';
      payload.recurring_start_date = transaction.recurring_start_date || transaction.date;
      if (transaction.recurring_end_date) payload.recurring_end_date = transaction.recurring_end_date;
      if (transaction.recurring_day_of_month) payload.recurring_day_of_month = transaction.recurring_day_of_month;
    }
    const response = await api.post('/transactions', payload);
    return mapTransaction(response.data);
  },

  update: async (
    id: number,
    transaction: Partial<TransactionFormData> & {
      reviewed?: boolean;
      locked?: boolean;
      line_items?: any[];
      suppress_rule_learning?: boolean;
    }
  ): Promise<Transaction> => {
    const payload: Record<string, any> = { ...transaction };
    // Map date -> transaction_date
    if (payload.date) {
      payload.transaction_date = payload.date;
      delete payload.date;
    }
    // Map amount to number
    if (payload.amount !== undefined) {
      payload.amount = Number(payload.amount);
    }
    if (payload.line_items) {
      payload.line_items = payload.line_items.map((lineItem: any, idx: number) => ({
        ...lineItem,
        amount: Number(lineItem.amount),
        quantity: Number(lineItem.quantity ?? 1),
        vat_rate: lineItem.vat_rate != null ? Number(lineItem.vat_rate) : undefined,
        vat_amount: lineItem.vat_amount != null ? Number(lineItem.vat_amount) : undefined,
        vat_recoverable_amount: lineItem.vat_recoverable_amount != null
          ? Number(lineItem.vat_recoverable_amount)
          : undefined,
        sort_order: lineItem.sort_order ?? idx,
      }));
    }
    // Map category to income_category/expense_category
    if (payload.category !== undefined && payload.type && transactionTypeRequiresCategory(payload.type)) {
      if (payload.type === 'income') {
        payload.income_category = payload.category;
      } else {
        payload.expense_category = payload.category;
      }
    }
    delete payload.category;
    // Include property_id if provided (allow null to clear the link)
    if (payload.property_id !== undefined) {
      payload.property_id = payload.property_id || null;
    }
    // Recurring fields
    if (payload.is_recurring !== undefined) {
      if (payload.is_recurring) {
        payload.recurring_frequency = payload.recurring_frequency || 'monthly';
        payload.recurring_start_date = payload.recurring_start_date || payload.transaction_date || payload.date;
        // Keep recurring_end_date and recurring_day_of_month if provided
      } else {
        // Turning off recurring — clear recurring fields
        payload.recurring_frequency = null;
        payload.recurring_start_date = null;
        payload.recurring_end_date = null;
        payload.recurring_day_of_month = null;
      }
    }
    const response = await api.put(`/transactions/${id}`, payload);
    return mapTransaction(response.data);
  },

  deleteCheck: async (id: number): Promise<DeleteCheckResult> => {
    const response = await api.get(`/transactions/${id}/delete-check`);
    return response.data;
  },

  delete: async (id: number, force?: boolean): Promise<void> => {
    await api.delete(`/transactions/${id}`, { params: force ? { force: true } : undefined });
  },

  batchDelete: async (ids: number[], force?: boolean): Promise<any> => {
    const response = await api.post('/transactions/batch-delete', { ids, force: force ?? false });
    return response.data;
  },

  importCSV: async (file: File): Promise<ImportResult> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/transactions/import', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  pause: async (id: number): Promise<Transaction> => {
    const response = await api.post(`/transactions/${id}/pause`);
    return mapTransaction(response.data);
  },

  resume: async (id: number): Promise<Transaction> => {
    const response = await api.post(`/transactions/${id}/resume`);
    return mapTransaction(response.data);
  },

  markReviewed: async (id: number): Promise<Transaction> => {
    const response = await api.post(`/transactions/${id}/review`);
    return mapTransaction(response.data);
  },

  exportCSV: async (filters?: TransactionFilters): Promise<Blob> => {
    const params: Record<string, any> = {};
    if (filters) {
      if (filters.start_date) params.start_date = filters.start_date;
      if (filters.end_date) params.end_date = filters.end_date;
      if (filters.type) params.type = filters.type;
    }
    const response = await api.get('/transactions/export', {
      params,
      responseType: 'blob',
    });
    return response.data;
  },
};
