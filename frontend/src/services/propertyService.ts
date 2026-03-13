import api from './api';
import {
  Property,
  PropertyCreate,
  PropertyUpdate,
  PropertyListResponse,
  PropertyDetailResponse,
  PropertyMetrics,
} from '../types/property';

/** Map backend property response to frontend Property type */
function mapProperty(raw: any): Property {
  return {
    id: raw.id,
    user_id: raw.user_id,
    property_type: raw.property_type,
    rental_percentage: raw.rental_percentage,
    address: raw.address,
    street: raw.street,
    city: raw.city,
    postal_code: raw.postal_code,
    purchase_date: raw.purchase_date,
    purchase_price: Number(raw.purchase_price),
    building_value: Number(raw.building_value),
    land_value: raw.land_value ? Number(raw.land_value) : undefined,
    grunderwerbsteuer: raw.grunderwerbsteuer ? Number(raw.grunderwerbsteuer) : undefined,
    notary_fees: raw.notary_fees ? Number(raw.notary_fees) : undefined,
    registry_fees: raw.registry_fees ? Number(raw.registry_fees) : undefined,
    construction_year: raw.construction_year,
    depreciation_rate: Number(raw.depreciation_rate),
    status: raw.status,
    sale_date: raw.sale_date,
    kaufvertrag_document_id: raw.kaufvertrag_document_id,
    mietvertrag_document_id: raw.mietvertrag_document_id,
    created_at: raw.created_at,
    updated_at: raw.updated_at,
  };
}

export const propertyService = {
  /**
   * Create a new property
   * POST /api/v1/properties
   */
  createProperty: async (data: PropertyCreate): Promise<Property> => {
    try {
      const payload: Record<string, any> = {
        street: data.street,
        city: data.city,
        postal_code: data.postal_code,
        purchase_date: data.purchase_date,
        purchase_price: Number(data.purchase_price),
      };

      // Add optional fields if provided
      if (data.property_type) payload.property_type = data.property_type;
      if (data.rental_percentage !== undefined) payload.rental_percentage = Number(data.rental_percentage);
      if (data.building_value !== undefined) payload.building_value = Number(data.building_value);
      if (data.construction_year) payload.construction_year = data.construction_year;
      if (data.depreciation_rate !== undefined) payload.depreciation_rate = Number(data.depreciation_rate);
      if (data.grunderwerbsteuer !== undefined) payload.grunderwerbsteuer = Number(data.grunderwerbsteuer);
      if (data.notary_fees !== undefined) payload.notary_fees = Number(data.notary_fees);
      if (data.registry_fees !== undefined) payload.registry_fees = Number(data.registry_fees);

      const response = await api.post('/properties', payload);
      return mapProperty(response.data);
    } catch (error: any) {
      console.error('Error creating property:', error);
      throw error;
    }
  },

  /**
   * Get list of properties
   * GET /api/v1/properties
   */
  getProperties: async (includeArchived: boolean = false): Promise<PropertyListResponse> => {
    try {
      const params: Record<string, any> = {
        include_archived: includeArchived,
      };

      const response = await api.get('/properties', { params });
      const data = response.data;

      return {
        total: data.total || 0,
        properties: (data.properties || []).map(mapProperty),
        include_archived: data.include_archived || false,
      };
    } catch (error: any) {
      console.error('Error fetching properties:', error);
      throw error;
    }
  },

  /**
   * Get single property by ID
   * GET /api/v1/properties/{id}
   */
  getProperty: async (id: string): Promise<PropertyDetailResponse> => {
    try {
      const response = await api.get(`/properties/${id}`);
      const property = mapProperty(response.data);

      // Map metrics if present
      const metrics = response.data.metrics
        ? {
            property_id: response.data.metrics.property_id,
            accumulated_depreciation: Number(response.data.metrics.accumulated_depreciation),
            remaining_depreciable_value: Number(response.data.metrics.remaining_depreciable_value),
            annual_depreciation: Number(response.data.metrics.annual_depreciation),
            total_rental_income: Number(response.data.metrics.total_rental_income),
            total_expenses: Number(response.data.metrics.total_expenses),
            net_rental_income: Number(response.data.metrics.net_rental_income),
            years_remaining: response.data.metrics.years_remaining,
          }
        : undefined;

      return {
        ...property,
        metrics,
      };
    } catch (error: any) {
      console.error('Error fetching property:', error);
      throw error;
    }
  },

  /**
   * Update property
   * PUT /api/v1/properties/{id}
   */
  updateProperty: async (id: string, data: PropertyUpdate): Promise<Property> => {
    try {
      const payload: Record<string, any> = {};

      // Only include fields that are provided
      if (data.property_type) payload.property_type = data.property_type;
      if (data.rental_percentage !== undefined) payload.rental_percentage = Number(data.rental_percentage);
      if (data.street) payload.street = data.street;
      if (data.city) payload.city = data.city;
      if (data.postal_code) payload.postal_code = data.postal_code;
      if (data.building_value !== undefined) payload.building_value = Number(data.building_value);
      if (data.construction_year) payload.construction_year = data.construction_year;
      if (data.depreciation_rate !== undefined) payload.depreciation_rate = Number(data.depreciation_rate);
      if (data.grunderwerbsteuer !== undefined) payload.grunderwerbsteuer = Number(data.grunderwerbsteuer);
      if (data.notary_fees !== undefined) payload.notary_fees = Number(data.notary_fees);
      if (data.registry_fees !== undefined) payload.registry_fees = Number(data.registry_fees);
      if (data.status) payload.status = data.status;
      if (data.sale_date) payload.sale_date = data.sale_date;

      const response = await api.put(`/properties/${id}`, payload);
      return mapProperty(response.data);
    } catch (error: any) {
      console.error('Error updating property:', error);
      throw error;
    }
  },

  /**
   * Archive property (mark as sold)
   * POST /api/v1/properties/{id}/archive
   */
  archiveProperty: async (id: string, saleDate: string): Promise<Property> => {
    try {
      const response = await api.post(`/properties/${id}/archive`, {
        sale_date: saleDate,
      });
      return mapProperty(response.data);
    } catch (error: any) {
      console.error('Error archiving property:', error);
      throw error;
    }
  },

  /**
   * Delete property
   * DELETE /api/v1/properties/{id}
   */
  deleteProperty: async (id: string): Promise<void> => {
    try {
      await api.delete(`/properties/${id}`);
    } catch (error: any) {
      console.error('Error deleting property:', error);
      throw error;
    }
  },

  /**
   * Link transaction to property
   * POST /api/v1/properties/{propertyId}/link-transaction
   */
  linkTransaction: async (propertyId: string, transactionId: number): Promise<void> => {
    try {
      await api.post(`/properties/${propertyId}/link-transaction`, {
        transaction_id: transactionId,
      });
    } catch (error: any) {
      console.error('Error linking transaction:', error);
      throw error;
    }
  },

  /**
   * Unlink transaction from property
   * DELETE /api/v1/properties/{propertyId}/unlink-transaction/{transactionId}
   */
  unlinkTransaction: async (propertyId: string, transactionId: number): Promise<void> => {
    try {
      await api.delete(`/properties/${propertyId}/unlink-transaction/${transactionId}`);
    } catch (error: any) {
      console.error('Error unlinking transaction:', error);
      throw error;
    }
  },

  /**
   * Get transactions linked to property
   * GET /api/v1/properties/{propertyId}/transactions
   */
  getPropertyTransactions: async (propertyId: string, year?: number): Promise<any[]> => {
    try {
      const params: Record<string, any> = {};
      if (year) params.year = year;

      const response = await api.get(`/properties/${propertyId}/transactions`, { params });
      return response.data.transactions || response.data || [];
    } catch (error: any) {
      console.error('Error fetching property transactions:', error);
      throw error;
    }
  },

  /**
   * Preview historical depreciation backfill
   * GET /api/v1/properties/{propertyId}/historical-depreciation
   */
  previewHistoricalDepreciation: async (propertyId: string): Promise<any> => {
    try {
      const response = await api.get(`/properties/${propertyId}/historical-depreciation`);
      return response.data;
    } catch (error: any) {
      console.error('Error previewing historical depreciation:', error);
      throw error;
    }
  },

  /**
   * Execute historical depreciation backfill
   * POST /api/v1/properties/{propertyId}/backfill-depreciation
   */
  backfillDepreciation: async (propertyId: string): Promise<any> => {
    try {
      const response = await api.post(`/properties/${propertyId}/backfill-depreciation`);
      return response.data;
    } catch (error: any) {
      console.error('Error backfilling depreciation:', error);
      throw error;
    }
  },

  /**
   * Compare portfolio properties
   * GET /api/v1/properties/portfolio/compare
   */
  comparePortfolio: async (
    year?: number,
    sortBy: string = 'net_income',
    sortOrder: string = 'desc'
  ): Promise<any[]> => {
    try {
      const params: Record<string, any> = {
        sort_by: sortBy,
        sort_order: sortOrder,
      };
      if (year) params.year = year;

      const response = await api.get('/properties/portfolio/compare', { params });
      return response.data || [];
    } catch (error: any) {
      console.error('Error comparing portfolio:', error);
      throw error;
    }
  },

  /**
   * Get property metrics with warnings
   * GET /api/v1/properties/{propertyId}/metrics
   */
  getPropertyMetrics: async (propertyId: string, year?: number): Promise<PropertyMetrics> => {
    try {
      const params: Record<string, any> = {};
      if (year) params.year = year;

      const response = await api.get(`/properties/${propertyId}/metrics`, { params });
      const data = response.data;

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
    } catch (error: any) {
      console.error('Error fetching property metrics:', error);
      throw error;
    }
  },
};
