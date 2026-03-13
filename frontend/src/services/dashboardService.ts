import api from './api';

export const dashboardService = {
  getDashboardData: async (year?: number) => {
    const response = await api.get('/dashboard', { params: { year } });
    return response.data;
  },

  getSuggestions: async () => {
    const response = await api.get('/dashboard/suggestions');
    return response.data;
  },

  getCalendar: async () => {
    const response = await api.get('/dashboard/calendar');
    return response.data;
  },

  getIncomeProfile: async (year?: number) => {
    const response = await api.get('/dashboard/income-profile', { params: { tax_year: year } });
    return response.data;
  },

  simulateTax: async (data: any) => {
    const response = await api.post('/tax/simulate', data);
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
};
