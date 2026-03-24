/* @vitest-environment jsdom */

import type { ReactNode } from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import RegisterPage from '../pages/auth/RegisterPage';

const registerRequest = vi.fn();
const getIndustries = vi.fn();

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => (typeof fallback === 'string' ? fallback : key),
    i18n: { language: 'zh', resolvedLanguage: 'zh' },
  }),
  Trans: ({ children }: { children?: ReactNode }) => children ?? null,
}));

vi.mock('../services/authService', () => ({
  authService: {
    register: (...args: unknown[]) => registerRequest(...args),
    resendVerification: vi.fn(),
  },
}));

vi.mock('../services/userService', () => ({
  userService: {
    getIndustries: (...args: unknown[]) => getIndustries(...args),
  },
}));

vi.mock('../components/common/LanguageSwitcher', () => ({
  default: () => <div data-testid="language-switcher" />,
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

describe('RegisterPage optional profile fields', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    HTMLElement.prototype.scrollIntoView = vi.fn();
    getIndustries.mockResolvedValue([
      {
        value: 'trainer',
        label_de: 'Trainer',
        label_en: 'Trainer',
        label_zh: 'Trainer',
      },
    ]);
    registerRequest.mockResolvedValue({
      message: 'verification_email_sent',
      email: 'owner@example.com',
    });
  });

  it('sends optional profile fields when the user fills them during registration', async () => {
    const { container } = render(
      <MemoryRouter>
        <RegisterPage />
      </MemoryRouter>,
    );

    fireEvent.change(container.querySelector('input[name="email"]') as HTMLInputElement, {
      target: { value: 'owner@example.com' },
    });
    fireEvent.change(container.querySelector('input[name="name"]') as HTMLInputElement, {
      target: { value: 'Owner' },
    });
    fireEvent.change(container.querySelector('input[name="password"]') as HTMLInputElement, {
      target: { value: 'StrongPass123!' },
    });
    fireEvent.change(container.querySelector('input[name="confirmPassword"]') as HTMLInputElement, {
      target: { value: 'StrongPass123!' },
    });

    const roleCheckboxes = container.querySelectorAll('.role-checkboxes input[type="checkbox"]');
    fireEvent.click(roleCheckboxes[2]);

    openCustomSelect(container, 'businessType');
    chooseCustomOption('auth.businessTypes.freiberufler');

    await waitFor(() => expect(getIndustries).toHaveBeenCalledWith('freiberufler'));

    fireEvent.change(container.querySelector('input[name="businessName"]') as HTMLInputElement, {
      target: { value: 'Profile Studio' },
    });
    openCustomSelect(container, 'businessIndustry');
    chooseCustomOption('Trainer');
    openCustomSelect(container, 'vatStatus');
    chooseCustomOption('Regular VAT');
    openCustomSelect(container, 'gewinnermittlungsart');
    chooseCustomOption('Einnahmen-Ausgaben-Rechnung');
    fireEvent.change(container.querySelector('input[name="numChildren"]') as HTMLInputElement, {
      target: { value: '2' },
    });
    fireEvent.click(container.querySelector('input[name="isSingleParent"]') as HTMLInputElement);
    fireEvent.click(container.querySelector('.legal-consent-label input[type="checkbox"]') as HTMLInputElement);

    fireEvent.click(screen.getByRole('button', { name: 'auth.register' }));

    await waitFor(() => expect(registerRequest).toHaveBeenCalledTimes(1));
    expect(registerRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        email: 'owner@example.com',
        name: 'Owner',
        user_type: 'mixed',
        user_roles: ['employee', 'self_employed'],
        business_type: 'freiberufler',
        business_name: 'Profile Studio',
        business_industry: 'trainer',
        vat_status: 'regelbesteuert',
        gewinnermittlungsart: 'ea_rechnung',
        num_children: 2,
        is_single_parent: true,
      }),
    );
  });

  it('blocks registration until a self-employed user chooses a business subcategory', async () => {
    const { container } = render(
      <MemoryRouter>
        <RegisterPage />
      </MemoryRouter>,
    );

    fireEvent.change(container.querySelector('input[name="email"]') as HTMLInputElement, {
      target: { value: 'owner@example.com' },
    });
    fireEvent.change(container.querySelector('input[name="name"]') as HTMLInputElement, {
      target: { value: 'Owner' },
    });
    fireEvent.change(container.querySelector('input[name="password"]') as HTMLInputElement, {
      target: { value: 'StrongPass123!' },
    });
    fireEvent.change(container.querySelector('input[name="confirmPassword"]') as HTMLInputElement, {
      target: { value: 'StrongPass123!' },
    });

    const roleCheckboxes = container.querySelectorAll('.role-checkboxes input[type="checkbox"]');
    fireEvent.click(roleCheckboxes[2]);

    openCustomSelect(container, 'businessType');
    chooseCustomOption('auth.businessTypes.freiberufler');
    fireEvent.click(container.querySelector('.legal-consent-label input[type="checkbox"]') as HTMLInputElement);

    await waitFor(() => expect(getIndustries).toHaveBeenCalledWith('freiberufler'));
    fireEvent.click(screen.getByRole('button', { name: 'auth.register' }));

    expect(registerRequest).not.toHaveBeenCalled();
    expect(screen.getByText(BUSINESS_SUBCATEGORY_REQUIRED)).toBeInTheDocument();
  });
});
