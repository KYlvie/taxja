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
  business_type?: string | null;
  business_industry?: string | null;
  employer_mode?: 'none' | 'occasional' | 'regular';
  employer_region?: string | null;
  language?: string;
}

interface LoginResponse {
  access_token: string;
  token_type: string;
  user: {
    id: number;
    email: string;
    name: string;
    user_type: string;
    employer_mode?: 'none' | 'occasional' | 'regular';
    employer_region?: string | null;
    two_factor_enabled: boolean;
    is_admin?: boolean;
  };
}

interface RegisterResponse {
  message: string;
  email: string;
}

interface VerifyEmailResponse extends LoginResponse {
  message: string;
}

export const authService = {
  login: async (credentials: LoginCredentials): Promise<LoginResponse> => {
    const response = await api.post('/auth/login', credentials);
    return response.data;
  },

  register: async (data: RegisterData): Promise<RegisterResponse> => {
    const response = await api.post('/auth/register', data);
    return response.data;
  },

  verifyEmail: async (token: string): Promise<VerifyEmailResponse> => {
    const response = await api.post(`/auth/verify-email?token=${encodeURIComponent(token)}`);
    return response.data;
  },

  resendVerification: async (email: string): Promise<{ message: string }> => {
    const response = await api.post(`/auth/resend-verification?email=${encodeURIComponent(email)}`);
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

  forgotPassword: async (email: string, language?: string): Promise<{ message: string }> => {
    const response = await api.post('/auth/forgot-password', { email, language });
    return response.data;
  },

  resetPassword: async (token: string, password: string): Promise<{ message: string }> => {
    const response = await api.post('/auth/reset-password', { token, password });
    return response.data;
  },
};
