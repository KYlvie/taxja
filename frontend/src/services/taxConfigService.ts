import api from './api';

export interface SupportedYearsResponse {
  years: number[];
  default_year: number;
}

export interface TaxConfigSummary {
  id: number;
  tax_year: number;
  tax_brackets: Array<{ lower: number; upper: number | null; rate: number }>;
  exemption_amount: number;
  vat_rates: Record<string, number>;
  svs_rates: Record<string, number>;
  deduction_config: Record<string, any>;
  created_at: string | null;
  updated_at: string | null;
}

// Cached supported years to avoid repeated API calls
let cachedYears: number[] | null = null;
let cacheTimestamp = 0;
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

const taxConfigService = {
  /** Get supported tax years from the database */
  getSupportedYears: async (): Promise<SupportedYearsResponse> => {
    const now = Date.now();
    if (cachedYears && now - cacheTimestamp < CACHE_TTL) {
      return {
        years: cachedYears,
        default_year: cachedYears[cachedYears.length - 1],
      };
    }
    try {
      const response = await api.get('/tax-configs/supported-years');
      cachedYears = response.data.years;
      cacheTimestamp = now;
      return response.data;
    } catch {
      // Fallback if API unavailable
      return { years: [2023, 2024, 2025, 2026], default_year: 2026 };
    }
  },

  /** Invalidate the cached years (call after admin creates/deletes a config) */
  invalidateCache: () => {
    cachedYears = null;
    cacheTimestamp = 0;
  },

  /** List all tax configurations (admin) */
  listConfigs: async (): Promise<TaxConfigSummary[]> => {
    const response = await api.get('/tax-configs/');
    return response.data;
  },

  /** Get a single year's config (admin) */
  getConfig: async (year: number): Promise<TaxConfigSummary> => {
    const response = await api.get(`/tax-configs/${year}`);
    return response.data;
  },

  /** Create a new year config (admin) */
  createConfig: async (data: any): Promise<TaxConfigSummary> => {
    const response = await api.post('/tax-configs/', data);
    taxConfigService.invalidateCache();
    return response.data;
  },

  /** Update a year config (admin) */
  updateConfig: async (year: number, data: any): Promise<TaxConfigSummary> => {
    const response = await api.put(`/tax-configs/${year}`, data);
    taxConfigService.invalidateCache();
    return response.data;
  },

  /** Delete a year config (admin) */
  deleteConfig: async (year: number): Promise<void> => {
    await api.delete(`/tax-configs/${year}`);
    taxConfigService.invalidateCache();
  },

  /** Clone a year's config to a new year (admin) */
  cloneConfig: async (
    sourceYear: number,
    targetYear: number
  ): Promise<TaxConfigSummary> => {
    const response = await api.post(
      `/tax-configs/${sourceYear}/clone?target_year=${targetYear}`
    );
    taxConfigService.invalidateCache();
    return response.data;
  },
};

export default taxConfigService;
