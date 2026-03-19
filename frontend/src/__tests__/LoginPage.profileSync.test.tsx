/* @vitest-environment jsdom */

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import LoginPage from '../pages/auth/LoginPage';
import { useAuthStore } from '../stores/authStore';

const loginRequest = vi.fn();
const getProfile = vi.fn();
const reactivateAccount = vi.fn();
const navigate = vi.fn();

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => (typeof fallback === 'string' ? fallback : key),
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
    login: (...args: any[]) => loginRequest(...args),
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

vi.mock('../components/common/LanguageSwitcher', () => ({
  default: () => <div data-testid="language-switcher" />,
}));

vi.mock('../components/account/DeactivatedAccountBanner', () => ({
  default: () => <div data-testid="deactivated-banner" />,
}));

describe('LoginPage profile sync', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({
      user: null,
      token: null,
      isAuthenticated: false,
    });

    loginRequest.mockResolvedValue({
      access_token: 'token-123',
      token_type: 'bearer',
      user: {
        id: 1,
        email: 'owner@example.com',
        name: 'Owner',
        user_type: 'self_employed',
        employer_mode: 'none',
        employer_region: null,
        two_factor_enabled: false,
      },
    });

    getProfile.mockResolvedValue({
      id: 1,
      email: 'owner@example.com',
      name: 'Owner',
      user_type: 'self_employed',
      employer_mode: 'regular',
      employer_region: 'Wien',
      two_factor_enabled: false,
      disclaimer_accepted: false,
    });
  });

  it('hydrates the auth store with the full profile after login', async () => {
    const { container } = render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

    const emailInput = container.querySelector('input[type="email"]') as HTMLInputElement;
    const passwordInput = container.querySelector('input[type="password"]') as HTMLInputElement;

    fireEvent.change(emailInput, {
      target: { value: 'owner@example.com' },
    });
    fireEvent.change(passwordInput, {
      target: { value: 'StrongPass123!' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'auth.login' }));

    await waitFor(() => expect(loginRequest).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(getProfile).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(useAuthStore.getState().user?.employer_mode).toBe('regular'));

    expect(useAuthStore.getState().user?.employer_region).toBe('Wien');
    expect(navigate).toHaveBeenCalledWith('/dashboard');
  });
});
