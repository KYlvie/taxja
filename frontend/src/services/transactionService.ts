import api from './api';
import {
  ImportResult,
  LineItem,
  PaginatedResponse,
  PaginationParams,
  Transaction,
  TransactionFilters,
  TransactionFormData,
  transactionTypeRequiresCategory,
} from '../types/transaction';
import { normalizeTransactionCategoryKey } from '../utils/formatTransactionCategoryLabel';

type UnknownRecord = Record<string, unknown>;

interface DeleteCheckResult {
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

interface TransactionLineItemRaw extends UnknownRecord {
  amount: number | string;
  quantity?: number | string;
  category?: string;
  vat_rate?: number | string | null;
  vat_amount?: number | string | null;
  vat_recoverable_amount?: number | string | null;
  classification_confidence?: number | string | null;
}

interface TransactionRaw extends UnknownRecord {
  transaction_date?: string;
  date?: string;
  income_category?: string;
  expense_category?: string;
  category?: string;
  amount: number | string;
  line_items?: TransactionLineItemRaw[];
  deductible_amount?: number | string | null;
  non_deductible_amount?: number | string | null;
}

interface TransactionsListResponseRaw extends UnknownRecord {
  transactions?: TransactionRaw[];
  items?: TransactionRaw[];
  total?: number;
  page?: number;
  page_size?: number;
  total_pages?: number;
  available_years?: Array<number | string>;
  needs_review_count?: number;
}

type TransactionUpdatePayload = Partial<TransactionFormData> & {
  reviewed?: boolean;
  locked?: boolean;
  line_items?: LineItem[];
  suppress_rule_learning?: boolean;
};

const mapLineItem = (lineItem: TransactionLineItemRaw): LineItem => ({
  ...(lineItem as unknown as LineItem),
  category: normalizeTransactionCategoryKey(lineItem.category) || undefined,
  amount: Number(lineItem.amount),
  quantity: Number(lineItem.quantity ?? 1),
  vat_rate: lineItem.vat_rate != null ? Number(lineItem.vat_rate) : undefined,
  vat_amount: lineItem.vat_amount != null ? Number(lineItem.vat_amount) : undefined,
  vat_recoverable_amount: lineItem.vat_recoverable_amount != null
    ? Number(lineItem.vat_recoverable_amount)
    : undefined,
  classification_confidence: lineItem.classification_confidence != null
    ? Number(lineItem.classification_confidence)
    : undefined,
});

/** Map backend transaction response to frontend Transaction type */
function mapTransaction(raw: TransactionRaw): Transaction {
  return {
    ...(raw as unknown as Transaction),
    date: raw.transaction_date || raw.date || '',
    category:
      normalizeTransactionCategoryKey(raw.income_category || raw.expense_category || raw.category) || undefined,
    amount: Number(raw.amount),
    line_items: raw.line_items?.map(mapLineItem) || [],
    deductible_amount: raw.deductible_amount != null ? Number(raw.deductible_amount) : undefined,
    non_deductible_amount: raw.non_deductible_amount != null ? Number(raw.non_deductible_amount) : undefined,
  };
}

const mapPayloadLineItems = (lineItems: LineItem[]): LineItem[] => (
  lineItems.map((lineItem, idx) => ({
    ...lineItem,
    amount: Number(lineItem.amount),
    quantity: Number(lineItem.quantity ?? 1),
    vat_rate: lineItem.vat_rate != null ? Number(lineItem.vat_rate) : undefined,
    vat_amount: lineItem.vat_amount != null ? Number(lineItem.vat_amount) : undefined,
    vat_recoverable_amount: lineItem.vat_recoverable_amount != null
      ? Number(lineItem.vat_recoverable_amount)
      : undefined,
    sort_order: lineItem.sort_order ?? idx,
  }))
);

const mapTransactionFilterParams = (
  filters?: TransactionFilters,
  pagination?: PaginationParams
): Record<string, unknown> => {
  const params: Record<string, unknown> = { ...pagination };
  if (!filters) return params;

  if (filters.start_date) params.date_from = filters.start_date;
  if (filters.end_date) params.date_to = filters.end_date;
  if (filters.type) params.type = filters.type;
  if (filters.search) params.search = filters.search;
  if (filters.is_deductible !== undefined) params.is_deductible = filters.is_deductible;
  if (filters.is_recurring !== undefined) params.is_recurring = filters.is_recurring;
  if (filters.needs_review !== undefined) params.needs_review = filters.needs_review;

  return params;
};

export const transactionService = {
  getAll: async (
    filters?: TransactionFilters,
    pagination?: PaginationParams
  ): Promise<PaginatedResponse<Transaction>> => {
    const response = await api.get('/transactions', {
      params: mapTransactionFilterParams(filters, pagination),
    });
    const data = response.data as TransactionsListResponseRaw;
    const rawItems = data.transactions || data.items || [];
    return {
      items: rawItems.map(mapTransaction),
      total: data.total || 0,
      page: data.page || 1,
      page_size: data.page_size || 50,
      total_pages: data.total_pages || 0,
      available_years: Array.isArray(data.available_years)
        ? data.available_years
            .map((year) => Number(year))
            .filter((year) => Number.isFinite(year))
        : [],
      needs_review_count: data.needs_review_count ?? 0,
    };
  },

  getById: async (id: number): Promise<Transaction> => {
    const response = await api.get(`/transactions/${id}`);
    return mapTransaction(response.data as TransactionRaw);
  },

  create: async (transaction: TransactionFormData): Promise<Transaction> => {
    const payload: Record<string, unknown> = {
      type: transaction.type,
      amount: Number(transaction.amount),
      transaction_date: transaction.date,
      description: transaction.description,
      document_id: transaction.document_id,
    };

    if (transactionTypeRequiresCategory(transaction.type) && transaction.category) {
      if (transaction.type === 'income') {
        payload.income_category = transaction.category;
      } else {
        payload.expense_category = transaction.category;
      }
    }

    if (transaction.property_id) {
      payload.property_id = transaction.property_id;
    }

    if (transaction.line_items) {
      payload.line_items = mapPayloadLineItems(transaction.line_items);
    }

    if (transaction.is_recurring) {
      payload.is_recurring = true;
      payload.recurring_frequency = transaction.recurring_frequency || 'monthly';
      payload.recurring_start_date = transaction.recurring_start_date || transaction.date;
      if (transaction.recurring_end_date) payload.recurring_end_date = transaction.recurring_end_date;
      if (transaction.recurring_day_of_month) payload.recurring_day_of_month = transaction.recurring_day_of_month;
    }

    const response = await api.post('/transactions', payload);
    return mapTransaction(response.data as TransactionRaw);
  },

  update: async (id: number, transaction: TransactionUpdatePayload): Promise<Transaction> => {
    const payload: Record<string, unknown> = { ...transaction };

    if (typeof payload.date === 'string' && payload.date) {
      payload.transaction_date = payload.date;
      delete payload.date;
    }

    if (payload.amount !== undefined) {
      payload.amount = Number(payload.amount);
    }

    if (Array.isArray(payload.line_items)) {
      payload.line_items = mapPayloadLineItems(payload.line_items as LineItem[]);
    }

    if (
      payload.category !== undefined &&
      typeof payload.type === 'string' &&
      transactionTypeRequiresCategory(payload.type)
    ) {
      if (payload.type === 'income') {
        payload.income_category = payload.category;
      } else {
        payload.expense_category = payload.category;
      }
    }
    delete payload.category;

    if (payload.property_id !== undefined) {
      payload.property_id = payload.property_id || null;
    }

    if (payload.is_recurring !== undefined) {
      if (payload.is_recurring) {
        payload.recurring_frequency = payload.recurring_frequency || 'monthly';
        payload.recurring_start_date =
          payload.recurring_start_date || payload.transaction_date || payload.date;
      } else {
        payload.recurring_frequency = null;
        payload.recurring_start_date = null;
        payload.recurring_end_date = null;
        payload.recurring_day_of_month = null;
      }
    }

    const response = await api.put(`/transactions/${id}`, payload);
    return mapTransaction(response.data as TransactionRaw);
  },

  deleteCheck: async (id: number): Promise<DeleteCheckResult> => {
    const response = await api.get(`/transactions/${id}/delete-check`);
    return response.data as DeleteCheckResult;
  },

  delete: async (id: number, force?: boolean): Promise<void> => {
    await api.delete(`/transactions/${id}`, {
      params: force ? { force: true } : undefined,
    });
  },

  batchDelete: async (ids: number[], force?: boolean): Promise<BatchDeleteCheckResult | UnknownRecord> => {
    const response = await api.post('/transactions/batch-delete', { ids, force: force ?? false });
    return response.data as BatchDeleteCheckResult | UnknownRecord;
  },

  importCSV: async (file: File): Promise<ImportResult> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/transactions/import', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data as ImportResult;
  },

  pause: async (id: number): Promise<Transaction> => {
    const response = await api.post(`/transactions/${id}/pause`);
    return mapTransaction(response.data as TransactionRaw);
  },

  resume: async (id: number): Promise<Transaction> => {
    const response = await api.post(`/transactions/${id}/resume`);
    return mapTransaction(response.data as TransactionRaw);
  },

  markReviewed: async (id: number): Promise<Transaction> => {
    const response = await api.post(`/transactions/${id}/review`);
    return mapTransaction(response.data as TransactionRaw);
  },

  exportCSV: async (filters?: TransactionFilters): Promise<Blob> => {
    const response = await api.get('/transactions/export', {
      params: mapTransactionFilterParams(filters),
      responseType: 'blob',
    });
    return response.data as Blob;
  },

  exportPDF: async (filters?: TransactionFilters): Promise<Blob> => {
    const response = await api.get('/transactions/export/pdf', {
      params: mapTransactionFilterParams(filters),
      responseType: 'blob',
    });
    return response.data as Blob;
  },
};
