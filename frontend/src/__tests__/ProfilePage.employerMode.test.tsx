/* @vitest-environment jsdom */

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import ProfilePage from '../pages/ProfilePage';
import { useAuthStore } from '../stores/authStore';

const getProfile = vi.fn();
const updateProfile = vi.fn();
const getIndustries = vi.fn();
const fetchSubscription = vi.fn();
const aiToast = vi.fn();

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => (typeof fallback === 'string' ? fallback : key),
    i18n: { language: 'zh', resolvedLanguage: 'zh' },
  }),
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => vi.fn(),
  };
});

vi.mock('../services/userService', () => ({
  userService: {
    getProfile: (...args: any[]) => getProfile(...args),
    updateProfile: (...args: any[]) => updateProfile(...args),
    getIndustries: (...args: any[]) => getIndustries(...args),
  },
}));

vi.mock('../stores/aiToastStore', () => ({
  aiToast: (...args: any[]) => aiToast(...args),
}));

vi.mock('../stores/subscriptionStore', () => ({
  useSubscriptionStore: () => ({
    fetchSubscription: (...args: any[]) => fetchSubscription(...args),
  }),
}));

vi.mock('../components/reports/DataExport', () => ({
  default: () => <div data-testid="data-export" />,
}));

vi.mock('../components/account/AccountManagementSection', () => ({
  default: () => <div data-testid="account-management" />,
}));

describe('ProfilePage employer mode persistence flow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({
      user: {
        id: 1,
        email: 'owner@example.com',
        name: 'Owner',
        user_type: 'self_employed',
        employer_mode: 'none',
        employer_region: null,
        two_factor_enabled: false,
      },
      token: 'token',
      isAuthenticated: true,
    });

    getIndustries.mockResolvedValue([]);
    getProfile
      .mockResolvedValueOnce({
        id: 1,
        email: 'owner@example.com',
        name: 'Owner',
        user_type: 'self_employed',
        user_roles: ['self_employed'],
        tax_profile_completeness: {
          is_complete_for_asset_automation: true,
          missing_fields: [],
          source: 'persisted_user_profile',
          contract_version: 'v1',
        },
        employer_mode: 'none',
        employer_region: '',
        two_factor_enabled: false,
        disclaimer_accepted: false,
      })
      .mockResolvedValueOnce({
        id: 1,
        email: 'owner@example.com',
        name: 'Owner',
        user_type: 'self_employed',
        user_roles: ['self_employed'],
        tax_profile_completeness: {
          is_complete_for_asset_automation: true,
          missing_fields: [],
          source: 'persisted_user_profile',
          contract_version: 'v1',
        },
        employer_mode: 'regular',
        employer_region: 'Wien',
        two_factor_enabled: false,
        disclaimer_accepted: false,
      });

    updateProfile.mockResolvedValue({
      id: 1,
      email: 'owner@example.com',
      name: 'Owner',
      user_type: 'self_employed',
      tax_profile_completeness: {
        is_complete_for_asset_automation: true,
        missing_fields: [],
        source: 'persisted_user_profile',
        contract_version: 'v1',
      },
      employer_mode: 'regular',
      employer_region: 'Wien',
      two_factor_enabled: false,
      disclaimer_accepted: false,
    });
  });

  it('submits employer_mode and rehydrates the saved profile', async () => {
    const { container } = render(
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>
    );

    await waitFor(() => expect(getProfile).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('button', { name: 'common.edit' }));

    const employerModeSelect = container.querySelector('select[name="employer_mode"]') as HTMLSelectElement;
    fireEvent.change(employerModeSelect, { target: { value: 'regular' } });

    fireEvent.click(screen.getByRole('button', { name: 'common.save' }));

    await waitFor(() => expect(updateProfile).toHaveBeenCalledTimes(1));
    expect(updateProfile.mock.calls[0][0].employer_mode).toBe('regular');

    await waitFor(() => expect(getProfile).toHaveBeenCalledTimes(2));
    await waitFor(() => expect((container.querySelector('select[name="employer_mode"]') as HTMLSelectElement).value).toBe('regular'));
    expect(useAuthStore.getState().user?.employer_mode).toBe('regular');
  });
});
