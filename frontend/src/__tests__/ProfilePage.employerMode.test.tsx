/* @vitest-environment jsdom */

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
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
    getProfile: (...args: unknown[]) => getProfile(...args),
    updateProfile: (...args: unknown[]) => updateProfile(...args),
    getIndustries: (...args: unknown[]) => getIndustries(...args),
  },
}));

vi.mock('../stores/aiToastStore', () => ({
  aiToast: (...args: unknown[]) => aiToast(...args),
}));

vi.mock('../stores/subscriptionStore', () => ({
  useSubscriptionStore: () => ({
    fetchSubscription: (...args: unknown[]) => fetchSubscription(...args),
  }),
}));

vi.mock('../components/reports/DataExport', () => ({
  default: () => <div data-testid="data-export" />,
}));

vi.mock('../components/account/AccountManagementSection', () => ({
  default: () => <div data-testid="account-management" />,
}));

const BUSINESS_SUBCATEGORY_REQUIRED = '\u8bf7\u9009\u62e9\u5177\u4f53\u884c\u4e1a/\u8425\u4e1a\u5b50\u7c7b\u3002';

const openCustomSelect = (container: HTMLElement, name: string) => {
  const nativeSelect = container.querySelector(`select[name="${name}"]`) as HTMLSelectElement | null;
  const trigger = nativeSelect?.parentElement?.querySelector('button[role="combobox"]') as HTMLButtonElement | null;

  if (!trigger) {
    throw new Error(`Could not find select trigger for ${name}`);
  }

  fireEvent.click(trigger);
};

const chooseCustomOption = (label: string) => {
  const listbox = screen.getByRole('listbox');
  fireEvent.mouseDown(within(listbox).getByRole('option', { name: label }));
};

describe('ProfilePage employer mode persistence flow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    HTMLElement.prototype.scrollIntoView = vi.fn();
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
      </MemoryRouter>,
    );

    await waitFor(() => expect(getProfile).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('button', { name: 'common.edit' }));

    openCustomSelect(container, 'employer_mode');
    chooseCustomOption('Occasionally');
    openCustomSelect(container, 'employer_mode');
    chooseCustomOption('Regularly');

    fireEvent.click(screen.getByRole('button', { name: 'common.save' }));

    await waitFor(() => expect(updateProfile).toHaveBeenCalledTimes(1));
    expect(updateProfile.mock.calls[0][0].employer_mode).toBe('regular');

    await waitFor(() => expect(getProfile).toHaveBeenCalledTimes(2));
    await waitFor(() =>
      expect((container.querySelector('select[name="employer_mode"]') as HTMLSelectElement).value).toBe('regular'),
    );
    expect(useAuthStore.getState().user?.employer_mode).toBe('regular');
  });

  it('submits num_children and rehydrates the saved family fields', async () => {
    getProfile.mockReset();
    updateProfile.mockReset();

    getProfile
      .mockResolvedValueOnce({
        id: 1,
        email: 'owner@example.com',
        name: 'Owner',
        user_type: 'employee',
        user_roles: ['employee'],
        tax_profile_completeness: {
          is_complete_for_asset_automation: false,
          missing_fields: [],
          source: 'persisted_user_profile',
          contract_version: 'v1',
        },
        num_children: 1,
        is_single_parent: false,
        two_factor_enabled: false,
        disclaimer_accepted: false,
      })
      .mockResolvedValueOnce({
        id: 1,
        email: 'owner@example.com',
        name: 'Owner',
        user_type: 'employee',
        user_roles: ['employee'],
        tax_profile_completeness: {
          is_complete_for_asset_automation: false,
          missing_fields: [],
          source: 'persisted_user_profile',
          contract_version: 'v1',
        },
        num_children: 3,
        is_single_parent: true,
        two_factor_enabled: false,
        disclaimer_accepted: false,
      });

    updateProfile.mockResolvedValue({
      id: 1,
      email: 'owner@example.com',
      name: 'Owner',
      user_type: 'employee',
      user_roles: ['employee'],
      tax_profile_completeness: {
        is_complete_for_asset_automation: false,
        missing_fields: [],
        source: 'persisted_user_profile',
        contract_version: 'v1',
      },
      num_children: 3,
      is_single_parent: true,
      two_factor_enabled: false,
      disclaimer_accepted: false,
    });

    const { container } = render(
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(getProfile).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('button', { name: 'common.edit' }));

    const childrenInput = container.querySelector('input[name="num_children"]') as HTMLInputElement;
    fireEvent.change(childrenInput, { target: { value: '3' } });

    const singleParentCheckbox = container.querySelector('input[name="is_single_parent"]') as HTMLInputElement;
    fireEvent.click(singleParentCheckbox);

    fireEvent.click(screen.getByRole('button', { name: 'common.save' }));

    await waitFor(() => expect(updateProfile).toHaveBeenCalledTimes(1));
    expect(updateProfile.mock.calls[0][0].num_children).toBe(3);
    expect(updateProfile.mock.calls[0][0].is_single_parent).toBe(true);

    await waitFor(() => expect(getProfile).toHaveBeenCalledTimes(2));
    await waitFor(() =>
      expect((container.querySelector('input[name="num_children"]') as HTMLInputElement).value).toBe('3'),
    );
    expect((container.querySelector('input[name="is_single_parent"]') as HTMLInputElement).checked).toBe(true);
    expect(useAuthStore.getState().user?.num_children).toBe(3);
    expect(useAuthStore.getState().user?.is_single_parent).toBe(true);
  });

  it('requires a business subcategory before saving a self-employed profile', async () => {
    getProfile.mockReset();
    updateProfile.mockReset();
    getIndustries.mockResolvedValue([
      {
        value: 'trainer',
        label_de: 'Trainer',
        label_en: 'Trainer',
        label_zh: 'Trainer',
      },
    ]);

    getProfile.mockResolvedValueOnce({
      id: 1,
      email: 'owner@example.com',
      name: 'Owner',
      user_type: 'self_employed',
      user_roles: ['self_employed'],
      business_type: 'freiberufler',
      business_industry: '',
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
    });

    const { container } = render(
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(getIndustries).toHaveBeenCalledWith('freiberufler'));

    fireEvent.click(screen.getByRole('button', { name: 'common.edit' }));
    fireEvent.click(screen.getByRole('button', { name: 'common.save' }));

    expect(updateProfile).not.toHaveBeenCalled();
    expect(screen.getByText(BUSINESS_SUBCATEGORY_REQUIRED)).toBeInTheDocument();
    expect(container.querySelector('select[name="business_industry"]')).toBeInTheDocument();
  });
});
