import api from './api';

export interface RecurringTransactionItem {
  id: number;
  user_id: number;
  recurring_type: string;
  property_id?: string;
  loan_id?: number;
  description: string;
  amount: number;
  transaction_type: string;
  category: string;
  frequency: string;
  start_date: string;
  end_date?: string;
  day_of_month?: number;
  template?: string;
  notes?: string;
  is_active: boolean;
  paused_at?: string;
  last_generated_date?: string;
  next_generation_date?: string;
  created_at: string;
  updated_at: string;
}

export interface RecurringTransactionListResponse {
  items: RecurringTransactionItem[];
  total: number;
  active_count: number;
  paused_count: number;
}

export interface UpdateAndRegenerateData {
  description?: string;
  amount?: number;
  frequency?: string;
  end_date?: string;
  day_of_month?: number;
  notes?: string;
  category?: string;
  apply_from?: string;
}

export interface ConvertToRecurringData {
  frequency: string;
  start_date: string;
  end_date?: string;
  day_of_month?: number;
  notes?: string;
}

export const recurringTransactionService = {
  getAll: async (activeOnly = false): Promise<RecurringTransactionListResponse> => {
    const response = await api.get('/recurring-transactions', {
      params: { active_only: activeOnly },
    });
    return response.data;
  },

  getById: async (id: number): Promise<RecurringTransactionItem> => {
    const response = await api.get(`/recurring-transactions/${id}`);
    return response.data;
  },

  updateAndRegenerate: async (
    id: number,
    data: UpdateAndRegenerateData
  ): Promise<RecurringTransactionItem> => {
    const response = await api.put(`/recurring-transactions/${id}/update-and-regenerate`, data);
    return response.data;
  },

  convertFromTransaction: async (
    transactionId: number,
    data: ConvertToRecurringData
  ): Promise<RecurringTransactionItem> => {
    const response = await api.post(
      `/recurring-transactions/convert-from-transaction`,
      data,
      { params: { transaction_id: transactionId } }
    );
    return response.data;
  },

  pause: async (id: number): Promise<RecurringTransactionItem> => {
    const response = await api.post(`/recurring-transactions/${id}/pause`);
    return response.data;
  },

  resume: async (id: number): Promise<RecurringTransactionItem> => {
    const response = await api.post(`/recurring-transactions/${id}/resume`);
    return response.data;
  },

  stop: async (id: number): Promise<RecurringTransactionItem> => {
    const response = await api.post(`/recurring-transactions/${id}/stop`);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/recurring-transactions/${id}`);
  },
};
