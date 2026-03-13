import api from './api';

export interface PropertyLoan {
  id: number;
  property_id: string;
  user_id: number;
  lender_name: string;
  loan_amount: number;
  interest_rate: number;
  start_date: string;
  end_date?: string;
  monthly_payment?: number;
  is_active: boolean;
  loan_contract_document_id?: number;
  created_at: string;
  updated_at: string;
}

export const loanService = {
  /**
   * Get all loans for the current user
   * GET /api/v1/property-loans
   */
  list: async (): Promise<PropertyLoan[]> => {
    const response = await api.get('/property-loans');
    return response.data;
  },

  /**
   * Get loans for a specific property
   * GET /api/v1/property-loans/property/{property_id}
   */
  getByProperty: async (propertyId: string): Promise<PropertyLoan[]> => {
    const response = await api.get(`/property-loans/property/${propertyId}`);
    return response.data;
  },

  /**
   * Get a specific loan
   * GET /api/v1/property-loans/{id}
   */
  get: async (id: number): Promise<PropertyLoan> => {
    const response = await api.get(`/property-loans/${id}`);
    return response.data;
  },
};
