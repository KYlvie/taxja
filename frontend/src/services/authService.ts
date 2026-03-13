import api from './api';

interface LoginCredentials {
  email: string;
  password: string;
  two_factor_code?: string;
}

interface RegisterData {
  email: string;
  password: string;
  name: string;
  user_type: string;
}

interface LoginResponse {
  access_token: string;
  token_type: string;
  user: {
    id: number;
    email: string;
    name: string;
    user_type: string;
    two_factor_enabled: boolean;
  };
}

export const authService = {
  login: async (credentials: LoginCredentials): Promise<LoginResponse> => {
    const response = await api.post('/auth/login', credentials);
    return response.data;
  },

  register: async (data: RegisterData): Promise<LoginResponse> => {
    const response = await api.post('/auth/register', data);
    return response.data;
  },

  logout: async (): Promise<void> => {
    await api.post('/auth/logout');
  },

  refreshToken: async (): Promise<{ access_token: string }> => {
    const response = await api.post('/auth/refresh');
    return response.data;
  },

  setup2FA: async (): Promise<{ qr_code: string; secret: string }> => {
    const response = await api.post('/auth/2fa/setup');
    return response.data;
  },

  verify2FA: async (code: string): Promise<{ success: boolean }> => {
    const response = await api.post('/auth/2fa/verify', { code });
    return response.data;
  },
};
