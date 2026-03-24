import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import api from '../services/api';

interface User {
  id: number;
  email: string;
  name: string;
  user_type: string;
  user_roles?: string[];
  business_type?: string | null;
  business_name?: string | null;
  business_industry?: string | null;
  vat_status?: string | null;
  gewinnermittlungsart?: string | null;
  employer_mode?: 'none' | 'occasional' | 'regular';
  employer_region?: string | null;
  commuting_distance_km?: number;
  public_transport_available?: boolean;
  telearbeit_days?: number | null;
  employer_telearbeit_pauschale?: number | null;
  num_children?: number;
  is_single_parent?: boolean;
  language?: string;
  two_factor_enabled: boolean;
  disclaimer_accepted?: boolean;
  is_admin?: boolean;
  onboarding_completed?: boolean;
}

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (user: User, token: string) => void;
  logout: () => void;
  updateUser: (user: Partial<User>) => void;
  completeOnboarding: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      login: (user, token) =>
        set({
          user,
          token, // Stored for native/Bearer fallback; web primarily uses cookies
          isAuthenticated: true,
        }),
      logout: () => {
        sessionStorage.removeItem('taxja_ai_greeting_shown');
        set({
          user: null,
          token: null,
          isAuthenticated: false,
        });
      },
      updateUser: (userData) =>
        set((state) => ({
          user: state.user ? { ...state.user, ...userData } : null,
        })),
      completeOnboarding: () => {
        set((state) => ({
          user: state.user ? { ...state.user, onboarding_completed: true } : null,
        }));
        api.post('/auth/onboarding-complete').catch((err) => {
          console.error('Failed to persist onboarding status:', err);
        });
      },
    }),
    {
      name: 'auth-storage',
    }
  )
);
