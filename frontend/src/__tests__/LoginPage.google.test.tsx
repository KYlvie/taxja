/* @vitest-environment jsdom */

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import LoginPage from '../pages/auth/LoginPage';
import { useAuthStore } from '../stores/authStore';

const googleLoginRequest = vi.fn();
const getProfile = vi.fn();
const reactivateAccount = vi.fn();
const navigate = vi.fn();

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => (typeof fallback === 'string' ? fallback : key),
    i18n: { language: 'en', resolvedLanguage: 'en' },
  }),
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigate,
    useLocation: () => ({ pathname: '/login', search: '' }),
  };
});

vi.mock('../services/authService', () => ({
  authService: {
    login: vi.fn(),
    loginWithGoogle: (...args: any[]) => googleLoginRequest(...args),
    resendVerification: vi.fn(),
  },
}));

vi.mock('../services/userService', () => ({
  userService: {
    getProfile: (...args: any[]) => getProfile(...args),
  },
}));

vi.mock('../services/accountService', () => ({
  accountService: {
    reactivateAccount: (...args: any[]) => reactivateAccount(...args),
  },
}));

vi.mock('../components/auth/GoogleSignInButton', () => ({
  default: ({ onCredential }: { onCredential: (credential: string) => void }) => (
    <button type="button" onClick={() => onCredential('google-credential')}>
      Continue with Google
    </button>
  ),
}));

vi.mock('../components/common/LanguageSwitcher', () => ({
  default: () => <div data-testid="language-switcher" />,
}));

vi.mock('../components/account/DeactivatedAccountBanner', () => ({
  default: () => <div data-testid="deactivated-banner" />,
}));

describe('LoginPage Google sign-in', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({
      user: null,
      token: null,
      isAuthenticated: false,
    });

    vi.stubEnv('VITE_GOOGLE_CLIENT_ID', 'google-client-id');

    googleLoginRequest.mockResolvedValue({
      access_token: 'token-google',
      token_type: 'bearer',
      user: {
        id: 7,
        email: 'owner@example.com',
        name: 'Owner',
        user_type: 'employee',
        employer_mode: 'none',
        employer_region: null,
        two_factor_enabled: false,
      },
    });

    getProfile.mockResolvedValue({
      id: 7,
      email: 'owner@example.com',
      name: 'Owner',
      user_type: 'employee',
      employer_mode: 'none',
      employer_region: null,
      two_factor_enabled: false,
      disclaimer_accepted: false,
    });
  });

  it('logs the user in via Google and then hydrates the full profile', async () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Continue with Google' }));

    await waitFor(() => expect(googleLoginRequest).toHaveBeenCalledWith('google-credential'));
    await waitFor(() => expect(getProfile).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(useAuthStore.getState().user?.email).toBe('owner@example.com'));

    expect(useAuthStore.getState().token).toBe('token-google');
    expect(navigate).toHaveBeenCalledWith('/dashboard');
  });
});
