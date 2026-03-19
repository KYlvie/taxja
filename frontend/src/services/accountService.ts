import api from './api';

export interface CancellationImpact {
  transaction_count: number;
  document_count: number;
  tax_report_count: number;
  property_count: number;
  has_active_subscription: boolean;
  subscription_days_remaining: number | null;
  cooling_off_days: number;
}

export interface DeactivateAccountRequest {
  password: string;
  reason?: string;
  two_factor_code?: string;
  confirmation_word: string;
}

export interface DataExportStatus {
  status: 'pending' | 'processing' | 'ready' | 'failed';
  download_url: string | null;
  expires_at: string | null;
}

export const accountService = {
  getCancellationImpact: async (): Promise<CancellationImpact> => {
    const response = await api.post('/account/cancellation-impact');
    return response.data;
  },

  deactivateAccount: async (data: DeactivateAccountRequest): Promise<void> => {
    await api.post('/account/deactivate', data);
  },

  reactivateAccount: async (token: string): Promise<void> => {
    await api.post(`/account/reactivate?reactivation_token=${encodeURIComponent(token)}`);
  },

  requestDataExport: async (password: string): Promise<{ task_id: string; status?: string; download_url?: string }> => {
    const response = await api.post('/account/export-data', { encryption_password: password });
    return response.data;
  },

  getExportStatus: async (taskId: string): Promise<DataExportStatus> => {
    const response = await api.get(`/account/export-status/${taskId}`);
    return response.data;
  },

  cancelSubscription: async (reason?: string): Promise<void> => {
    await api.post('/subscriptions/cancel', reason ? { reason } : undefined);
  },
};
