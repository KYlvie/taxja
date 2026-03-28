import { isAxiosError } from 'axios';
import api from './api';
import {
  DisposalRequest,
  Property,
  PropertyCreate,
  PropertyDetailResponse,
  PropertyListResponse,
  PropertyMetrics,
  PropertyUpdate,
  RentalContract,
} from '../types/property';
import { Transaction } from '../types/transaction';

type UnknownRecord = Record<string, unknown>;

interface PropertyRaw extends UnknownRecord {
  id: string;
  user_id: number;
  asset_type?: string;
  sub_category?: string | null;
  name?: string;
  property_type: Property['property_type'];
  rental_percentage: number | string;
  address: string;
  street: string;
  city: string;
  postal_code: string;
  purchase_date: string;
  purchase_price: number | string;
  building_value: number | string;
  land_value?: number | string | null;
  grunderwerbsteuer?: number | string | null;
  notary_fees?: number | string | null;
  registry_fees?: number | string | null;
  construction_year?: number;
  depreciation_rate: number | string;
  useful_life_years?: number | null;
  acquisition_kind?: string | null;
  put_into_use_date?: string | null;
  is_used_asset?: boolean | null;
  first_registration_date?: string | null;
  prior_owner_usage_years?: number | string | null;
  business_use_percentage?: number | string | null;
  comparison_basis?: string | null;
  comparison_amount?: number | string | null;
  gwg_eligible?: boolean | null;
  gwg_elected?: boolean | null;
  depreciation_method?: string | null;
  degressive_afa_rate?: number | string | null;
  useful_life_source?: string | null;
  income_tax_cost_cap?: number | string | null;
  income_tax_depreciable_base?: number | string | null;
  vat_recoverable_status?: string | null;
  ifb_candidate?: boolean | null;
  ifb_rate?: number | string | null;
  ifb_rate_source?: string | null;
  recognition_decision?: string | null;
  policy_confidence?: number | string | null;
  supplier?: string | null;
  accumulated_depreciation?: number | string | null;
  disposal_reason?: string | null;
  status: Property['status'];
  sale_date?: string;
  kaufvertrag_document_id?: number;
  mietvertrag_document_id?: number;
  annual_depreciation?: number | string | null;
  remaining_value?: number | string | null;
  created_at: string;
  updated_at: string;
}

interface PropertyMetricsRaw extends UnknownRecord {
  property_id: string;
  accumulated_depreciation: number | string;
  remaining_depreciable_value: number | string;
  annual_depreciation: number | string;
  total_rental_income: number | string;
  total_expenses: number | string;
  net_rental_income: number | string;
  years_remaining?: number;
  warnings?: unknown[];
}

interface PropertyListResponseRaw extends UnknownRecord {
  total?: number;
  properties?: PropertyRaw[];
  include_archived?: boolean;
}

interface PropertyDetailResponseRaw extends PropertyRaw {
  metrics?: PropertyMetricsRaw;
}

interface PropertyDeleteImpact {
  transaction_count: number;
  recurring_count: number;
  loan_count: number;
}

interface PropertyDeleteImpactResponse extends UnknownRecord {
  deleted: boolean;
  impact: PropertyDeleteImpact;
}

interface PropertyTransactionsResponseRaw extends UnknownRecord {
  transactions?: PropertyTransactionRaw[];
}

interface PropertyTransactionRaw extends UnknownRecord {
  transaction_date?: string;
  date?: string;
  income_category?: string;
  expense_category?: string;
  category?: string;
  amount: number | string;
}

const toOptionalNumber = (value: unknown): number | undefined => (
  value === null || value === undefined || value === ''
    ? undefined
    : Number(value)
);

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (isAxiosError(error)) {
    const detail = error.response?.data;
    if (typeof detail === 'object' && detail !== null && 'detail' in detail && typeof detail.detail === 'string') {
      return detail.detail;
    }
    if (typeof error.message === 'string' && error.message) {
      return error.message;
    }
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  return fallback;
};

/** Map backend property response to frontend Property type */
function mapProperty(raw: PropertyRaw): Property {
  return {
    id: raw.id,
    user_id: raw.user_id,
    asset_type: raw.asset_type || 'real_estate',
    sub_category: raw.sub_category ?? undefined,
    name: raw.name,
    property_type: raw.property_type,
    rental_percentage: Number(raw.rental_percentage),
    address: raw.address,
    street: raw.street,
    city: raw.city,
    postal_code: raw.postal_code,
    purchase_date: raw.purchase_date,
    purchase_price: Number(raw.purchase_price),
    building_value: Number(raw.building_value),
    land_value: toOptionalNumber(raw.land_value),
    grunderwerbsteuer: toOptionalNumber(raw.grunderwerbsteuer),
    notary_fees: toOptionalNumber(raw.notary_fees),
    registry_fees: toOptionalNumber(raw.registry_fees),
    construction_year: raw.construction_year,
    depreciation_rate: Number(raw.depreciation_rate),
    useful_life_years: raw.useful_life_years ?? undefined,
    acquisition_kind: raw.acquisition_kind ?? undefined,
    put_into_use_date: raw.put_into_use_date ?? undefined,
    is_used_asset: raw.is_used_asset ?? undefined,
    first_registration_date: raw.first_registration_date ?? undefined,
    prior_owner_usage_years: toOptionalNumber(raw.prior_owner_usage_years),
    business_use_percentage: toOptionalNumber(raw.business_use_percentage),
    comparison_basis: raw.comparison_basis ?? undefined,
    comparison_amount: toOptionalNumber(raw.comparison_amount),
    gwg_eligible: raw.gwg_eligible ?? undefined,
    gwg_elected: raw.gwg_elected ?? undefined,
    depreciation_method: raw.depreciation_method ?? undefined,
    degressive_afa_rate: toOptionalNumber(raw.degressive_afa_rate),
    useful_life_source: raw.useful_life_source ?? undefined,
    income_tax_cost_cap: toOptionalNumber(raw.income_tax_cost_cap),
    income_tax_depreciable_base: toOptionalNumber(raw.income_tax_depreciable_base),
    vat_recoverable_status: raw.vat_recoverable_status ?? undefined,
    ifb_candidate: raw.ifb_candidate ?? undefined,
    ifb_rate: toOptionalNumber(raw.ifb_rate),
    ifb_rate_source: raw.ifb_rate_source ?? undefined,
    recognition_decision: raw.recognition_decision ?? undefined,
    policy_confidence: toOptionalNumber(raw.policy_confidence),
    supplier: raw.supplier ?? undefined,
    accumulated_depreciation: toOptionalNumber(raw.accumulated_depreciation),
    disposal_reason: raw.disposal_reason ?? undefined,
    status: raw.status,
    sale_date: raw.sale_date,
    kaufvertrag_document_id: raw.kaufvertrag_document_id,
    mietvertrag_document_id: raw.mietvertrag_document_id,
    annual_depreciation: toOptionalNumber(raw.annual_depreciation),
    remaining_value: toOptionalNumber(raw.remaining_value),
    created_at: raw.created_at,
    updated_at: raw.updated_at,
  };
}

export const propertyService = {
  createProperty: async (data: PropertyCreate): Promise<Property> => {
    try {
      const payload: Record<string, unknown> = {
        street: data.street,
        city: data.city,
        postal_code: data.postal_code,
        purchase_date: data.purchase_date,
        purchase_price: Number(data.purchase_price),
      };

      if (data.property_type) payload.property_type = data.property_type;
      if (data.rental_percentage !== undefined) payload.rental_percentage = Number(data.rental_percentage);
      if (data.building_value !== undefined) payload.building_value = Number(data.building_value);
      if (data.construction_year) payload.construction_year = data.construction_year;
      if (data.depreciation_rate !== undefined) payload.depreciation_rate = Number(data.depreciation_rate);
      if (data.grunderwerbsteuer !== undefined) payload.grunderwerbsteuer = Number(data.grunderwerbsteuer);
      if (data.notary_fees !== undefined) payload.notary_fees = Number(data.notary_fees);
      if (data.registry_fees !== undefined) payload.registry_fees = Number(data.registry_fees);

      const response = await api.post('/properties', payload);
      return mapProperty(response.data as PropertyRaw);
    } catch (error: unknown) {
      console.error('Error creating property:', error);
      throw error;
    }
  },

  getProperties: async (includeArchived: boolean = false): Promise<PropertyListResponse> => {
    try {
      const response = await api.get('/properties', {
        params: { include_archived: includeArchived },
      });
      const data = response.data as PropertyListResponseRaw;

      return {
        total: data.total || 0,
        properties: (data.properties || []).map(mapProperty),
        include_archived: data.include_archived || false,
      };
    } catch (error: unknown) {
      console.error('Error fetching properties:', error);
      throw error;
    }
  },

  getProperty: async (id: string): Promise<PropertyDetailResponse> => {
    try {
      const response = await api.get(`/properties/${id}`);
      const data = response.data as PropertyDetailResponseRaw;
      const property = mapProperty(data);

      const metrics = data.metrics
        ? {
            property_id: data.metrics.property_id,
            accumulated_depreciation: Number(data.metrics.accumulated_depreciation),
            remaining_depreciable_value: Number(data.metrics.remaining_depreciable_value),
            annual_depreciation: Number(data.metrics.annual_depreciation),
            total_rental_income: Number(data.metrics.total_rental_income),
            total_expenses: Number(data.metrics.total_expenses),
            net_rental_income: Number(data.metrics.net_rental_income),
            years_remaining: data.metrics.years_remaining,
            warnings: data.metrics.warnings || [],
          }
        : undefined;

      return {
        ...property,
        metrics,
      };
    } catch (error: unknown) {
      console.error('Error fetching property:', error);
      throw error;
    }
  },

  updateProperty: async (id: string, data: PropertyUpdate): Promise<Property> => {
    try {
      const payload: Record<string, unknown> = {};

      if (data.property_type) payload.property_type = data.property_type;
      if (data.rental_percentage !== undefined) payload.rental_percentage = Number(data.rental_percentage);
      if (data.street) payload.street = data.street;
      if (data.city) payload.city = data.city;
      if (data.postal_code) payload.postal_code = data.postal_code;
      if (data.purchase_date) payload.purchase_date = data.purchase_date;
      if (data.purchase_price !== undefined) payload.purchase_price = Number(data.purchase_price);
      if (data.building_value !== undefined) payload.building_value = Number(data.building_value);
      if (data.construction_year) payload.construction_year = data.construction_year;
      if (data.depreciation_rate !== undefined) payload.depreciation_rate = Number(data.depreciation_rate);
      if (data.grunderwerbsteuer !== undefined) payload.grunderwerbsteuer = Number(data.grunderwerbsteuer);
      if (data.notary_fees !== undefined) payload.notary_fees = Number(data.notary_fees);
      if (data.registry_fees !== undefined) payload.registry_fees = Number(data.registry_fees);
      if (data.status) payload.status = data.status;
      if (data.sale_date) payload.sale_date = data.sale_date;

      const response = await api.put(`/properties/${id}`, payload);
      return mapProperty(response.data as PropertyRaw);
    } catch (error: unknown) {
      console.error('Error updating property:', error);
      throw error;
    }
  },

  archiveProperty: async (id: string, saleDate: string): Promise<Property> => {
    try {
      const response = await api.post(`/properties/${id}/archive`, {
        sale_date: saleDate,
      });
      return mapProperty(response.data as PropertyRaw);
    } catch (error: unknown) {
      console.error('Error archiving property:', error);
      throw error;
    }
  },

  disposeProperty: async (id: string, data: DisposalRequest): Promise<Property> => {
    try {
      const response = await api.post(`/properties/${id}/dispose`, data);
      return mapProperty(response.data as PropertyRaw);
    } catch (error: unknown) {
      console.error('Error disposing property:', error);
      throw error;
    }
  },

  checkDeleteImpact: async (id: string): Promise<PropertyDeleteImpactResponse> => {
    try {
      const response = await api.delete(`/properties/${id}?force=false`);
      return (response.data as PropertyDeleteImpactResponse) || {
        deleted: true,
        impact: { transaction_count: 0, recurring_count: 0, loan_count: 0 },
      };
    } catch (error: unknown) {
      if (isAxiosError(error) && error.response?.status === 404) {
        return {
          deleted: true,
          impact: { transaction_count: 0, recurring_count: 0, loan_count: 0 },
        };
      }
      console.error('Error checking delete impact:', error);
      throw error;
    }
  },

  deleteProperty: async (id: string, force: boolean = true): Promise<void> => {
    try {
      await api.delete(`/properties/${id}?force=${force}`);
    } catch (error: unknown) {
      console.error('Error deleting property:', error);
      throw error;
    }
  },

  linkTransaction: async (propertyId: string, transactionId: number): Promise<void> => {
    try {
      await api.post(`/properties/${propertyId}/link-transaction`, {
        transaction_id: transactionId,
      });
    } catch (error: unknown) {
      console.error('Error linking transaction:', error);
      throw error;
    }
  },

  unlinkTransaction: async (propertyId: string, transactionId: number): Promise<void> => {
    try {
      await api.delete(`/properties/${propertyId}/unlink-transaction/${transactionId}`);
    } catch (error: unknown) {
      console.error('Error unlinking transaction:', error);
      throw error;
    }
  },

  getPropertyTransactions: async (propertyId: string, year?: number): Promise<Transaction[]> => {
    try {
      const response = await api.get(`/properties/${propertyId}/transactions`, {
        params: year ? { year } : undefined,
      });
      const responseData = response.data as PropertyTransactionsResponseRaw | PropertyTransactionRaw[];
      const rawItems = Array.isArray(responseData) ? responseData : responseData.transactions || [];

      return rawItems.map((item) => ({
        ...(item as UnknownRecord),
        date: item.transaction_date || item.date || '',
        category: item.income_category || item.expense_category || item.category || 'other',
        amount: Number(item.amount),
      })) as Transaction[];
    } catch (error: unknown) {
      console.error('Error fetching property transactions:', error);
      throw error;
    }
  },

  previewHistoricalDepreciation: async (propertyId: string): Promise<UnknownRecord> => {
    try {
      const response = await api.get(`/properties/${propertyId}/historical-depreciation`);
      return response.data as UnknownRecord;
    } catch (error: unknown) {
      console.error('Error previewing historical depreciation:', error);
      throw error;
    }
  },

  backfillDepreciation: async (propertyId: string): Promise<UnknownRecord> => {
    try {
      const response = await api.post(`/properties/${propertyId}/backfill-depreciation`);
      return response.data as UnknownRecord;
    } catch (error: unknown) {
      console.error('Error backfilling depreciation:', error);
      throw error;
    }
  },

  comparePortfolio: async (
    year?: number,
    sortBy: string = 'net_income',
    sortOrder: string = 'desc'
  ): Promise<UnknownRecord[]> => {
    try {
      const response = await api.get('/properties/portfolio/compare', {
        params: {
          sort_by: sortBy,
          sort_order: sortOrder,
          ...(year ? { year } : {}),
        },
      });
      return (response.data as UnknownRecord[]) || [];
    } catch (error: unknown) {
      console.error('Error comparing portfolio:', error);
      throw error;
    }
  },

  getPropertyMetrics: async (propertyId: string, year?: number): Promise<PropertyMetrics> => {
    try {
      const response = await api.get(`/properties/${propertyId}/metrics`, {
        params: year ? { year } : undefined,
      });
      const data = response.data as PropertyMetricsRaw;

      return {
        property_id: data.property_id,
        accumulated_depreciation: Number(data.accumulated_depreciation),
        remaining_depreciable_value: Number(data.remaining_depreciable_value),
        annual_depreciation: Number(data.annual_depreciation),
        total_rental_income: Number(data.total_rental_income),
        total_expenses: Number(data.total_expenses),
        net_rental_income: Number(data.net_rental_income),
        years_remaining: data.years_remaining,
        warnings: data.warnings || [],
      };
    } catch (error: unknown) {
      console.error('Error fetching property metrics:', error);
      throw error;
    }
  },

  getRentalContracts: async (propertyId: string): Promise<RentalContract[]> => {
    try {
      const response = await api.get(`/properties/${propertyId}/rental-contracts`);
      return (response.data as RentalContract[]) || [];
    } catch (error: unknown) {
      console.error('Error fetching rental contracts:', error);
      throw error;
    }
  },

  recalculateRental: async (propertyId: string): Promise<Property> => {
    try {
      const response = await api.post(`/properties/${propertyId}/recalculate-rental`);
      return mapProperty(response.data as PropertyRaw);
    } catch (error: unknown) {
      console.error('Error recalculating rental:', error);
      throw error;
    }
  },

  createAsset: async (data: {
    asset_type: string;
    name: string;
    sub_category?: string;
    purchase_date: string;
    purchase_price: number;
    supplier?: string;
    business_use_percentage?: number;
    useful_life_years?: number;
  }): Promise<Property> => {
    try {
      const response = await api.post('/properties/assets', data);
      return mapProperty(response.data as PropertyRaw);
    } catch (error: unknown) {
      console.error('Error creating asset:', error);
      throw error;
    }
  },

  getAssets: async (includeArchived: boolean = false): Promise<{ total: number; assets: Property[] }> => {
    try {
      const response = await api.get('/properties/assets', {
        params: { include_archived: includeArchived },
      });
      const data = response.data as { total?: number; assets?: PropertyRaw[] };
      return {
        total: data.total || 0,
        assets: (data.assets || []).map(mapProperty),
      };
    } catch (error: unknown) {
      console.error('Error fetching assets:', error);
      throw error;
    }
  },
};

export { getErrorMessage };
