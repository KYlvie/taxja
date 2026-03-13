import api from './api';

interface UserProfile {
  id: number;
  email: string;
  name: string;
  address?: string;
  tax_number?: string;
  vat_number?: string;
  user_type: string;
  commuting_distance_km?: number;
  public_transport_available?: boolean;
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
  commuting_distance_km?: number;
  public_transport_available?: boolean;
  num_children?: number;
  is_single_parent?: boolean;
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
};
