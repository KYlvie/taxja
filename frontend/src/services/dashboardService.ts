import api from './api';
import i18n from '../i18n';
import { normalizeLanguage } from '../utils/locale';

const getCurrentLanguage = () => normalizeLanguage(i18n.resolvedLanguage || i18n.language);

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

  simulateTax: async (data: any) => {
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
};
