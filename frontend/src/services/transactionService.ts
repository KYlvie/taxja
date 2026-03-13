import api from './api';
import {
  Transaction,
  TransactionFilters,
  TransactionFormData,
  ImportResult,
  PaginationParams,
  PaginatedResponse,
} from '../types/transaction';

/** Map backend transaction response to frontend Transaction type */
function mapTransaction(raw: any): Transaction {
  return {
    ...raw,
    date: raw.transaction_date || raw.date,
    category: raw.income_category || raw.expense_category || raw.category || 'other',
    amount: Number(raw.amount),
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
    if (transaction.type === 'income') {
      payload.income_category = transaction.category;
    } else {
      payload.expense_category = transaction.category;
    }
    // Include property_id if provided
    if (transaction.property_id) {
      payload.property_id = transaction.property_id;
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
    transaction: Partial<TransactionFormData>
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
    // Map category to income_category/expense_category
    if (payload.category && payload.type) {
      if (payload.type === 'income') {
        payload.income_category = payload.category;
      } else {
        payload.expense_category = payload.category;
      }
      delete payload.category;
    }
    // Include property_id if provided (allow null to clear the link)
    if (payload.property_id !== undefined) {
      payload.property_id = payload.property_id || null;
    }
    const response = await api.put(`/transactions/${id}`, payload);
    return mapTransaction(response.data);
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/transactions/${id}`);
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
