import api from './api';

export interface UserProfile {
  id: number;
  email: string;
  name: string;
  address?: string;
  tax_number?: string;
  vat_number?: string;
  user_type: string;
  user_roles?: string[];
  business_type?: string | null;
  business_name?: string | null;
  business_industry?: string | null;
  vat_status?: string | null;
  gewinnermittlungsart?: string | null;
  tax_profile_completeness: {
    is_complete_for_asset_automation: boolean;
    missing_fields: Array<'vat_status' | 'gewinnermittlungsart'>;
    source: 'persisted_user_profile';
    contract_version: 'v1';
  };
  employer_mode?: 'none' | 'occasional' | 'regular';
  employer_region?: string | null;
  commuting_distance_km?: number;
  public_transport_available?: boolean;
  telearbeit_days?: number | null;
  employer_telearbeit_pauschale?: number | null;
  num_children?: number;
  is_single_parent?: boolean;
  two_factor_enabled: boolean;
  disclaimer_accepted: boolean;
}

interface UpdateProfileData {
  name?: string;
  address?: string;
  tax_number?: string;
  vat_number?: string;
  user_type?: string;
  business_type?: string | null;
  business_name?: string | null;
  business_industry?: string | null;
  vat_status?: string | null;
  gewinnermittlungsart?: string | null;
  user_roles?: string[];
  employer_mode?: 'none' | 'occasional' | 'regular';
  employer_region?: string | null;
  commuting_distance_km?: number;
  public_transport_available?: boolean;
  telearbeit_days?: number;
  employer_telearbeit_pauschale?: number;
  num_children?: number;
  is_single_parent?: boolean;
}

export interface IndustryOption {
  value: string;
  label_de: string;
  label_en: string;
  label_zh: string;
}

interface DisclaimerAcceptance {
  accepted: boolean;
  accepted_at?: string;
}

export const userService = {
  getProfile: async (): Promise<UserProfile> => {
    const response = await api.get('/users/profile');
    return response.data;
  },

  updateProfile: async (data: UpdateProfileData): Promise<UserProfile> => {
    const response = await api.put('/users/profile', data);
    return response.data;
  },

  acceptDisclaimer: async (): Promise<DisclaimerAcceptance> => {
    const response = await api.post('/users/disclaimer/accept');
    return response.data;
  },

  getDisclaimerStatus: async (): Promise<DisclaimerAcceptance> => {
    const response = await api.get('/users/disclaimer/status');
    return response.data;
  },

  getIndustries: async (businessType: string): Promise<IndustryOption[]> => {
    const response = await api.get(`/users/industries/${businessType}`);
    return response.data.industries;
  },

  deleteAccount: async (password: string): Promise<void> => {
    await api.post('/users/account/delete', { password });
  },
};
