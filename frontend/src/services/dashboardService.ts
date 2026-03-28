import api from './api';
import i18n from '../i18n';
import { normalizeLanguage } from '../utils/locale';

const getCurrentLanguage = () => normalizeLanguage(i18n.resolvedLanguage || i18n.language);

export interface ProactiveReminderDto {
  id: string;
  kind: string;
  bucket: 'terminal_action' | 'snoozeable_condition' | 'time_based_repeat';
  title_key?: string;
  body_key: string;
  params?: Record<string, unknown>;
  severity?: 'high' | 'medium' | 'low';
  primary_action?: Record<string, unknown> | null;
  secondary_action?: Record<string, unknown> | null;
  link?: string | null;
  source_type?: string;
  document_id?: number | null;
  recurring_id?: number | null;
  property_id?: string | null;
  tax_year?: number | null;
  snoozed_until?: string | null;
  next_due_at?: string | null;
  legacy_type?: string;
  action_data?: Record<string, unknown>;
  action?: Record<string, unknown>;
}

export interface TaxSimulationRequest {
  [key: string]: unknown;
}

export const dashboardService = {
  getDashboardData: async (year?: number) => {
    const response = await api.get('/dashboard', { params: { year } });
    return response.data;
  },

  getSuggestions: async (year?: number) => {
    const response = await api.get('/dashboard/suggestions', {
      params: { tax_year: year, language: getCurrentLanguage() },
    });
    return response.data;
  },

  getCalendar: async (year?: number) => {
    const response = await api.get('/dashboard/calendar', {
      params: { tax_year: year, language: getCurrentLanguage() },
    });
    return response.data;
  },

  getIncomeProfile: async (year?: number) => {
    const response = await api.get('/dashboard/income-profile', {
      params: { tax_year: year, language: getCurrentLanguage() },
    });
    return response.data;
  },

  simulateTax: async (data: TaxSimulationRequest) => {
    const response = await api.post('/tax/simulate', data, { timeout: 90000 });
    return response.data;
  },

  compareFlatRate: async (year?: number) => {
    const response = await api.get('/tax/flat-rate-compare', {
      params: { tax_year: year },
    });
    return response.data;
  },

  getPropertyMetrics: async (year?: number) => {
    const response = await api.get('/dashboard/property-metrics', {
      params: { tax_year: year },
    });
    return response.data;
  },

  getAlerts: async () => {
    const response = await api.get('/dashboard/alerts');
    return response.data;
  },

  getHealthCheck: async (year?: number) => {
    const response = await api.get('/dashboard/health-check', {
      params: { tax_year: year },
    });
    return response.data;
  },

  getProactiveReminders: async (year?: number): Promise<{ items: ProactiveReminderDto[]; tax_year?: number }> => {
    const response = await api.get('/dashboard/proactive-reminders', {
      params: { tax_year: year },
    });
    return response.data;
  },

  snoozeProactiveReminder: async (id: string, days?: number) => {
    const response = await api.post(`/dashboard/proactive-reminders/${encodeURIComponent(id)}/snooze`, {
      days,
    });
    return response.data;
  },

  acknowledgeProactiveReminder: async (id: string) => {
    const response = await api.post(`/dashboard/proactive-reminders/${encodeURIComponent(id)}/ack`);
    return response.data;
  },
};
