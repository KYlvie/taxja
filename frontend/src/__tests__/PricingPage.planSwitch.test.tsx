/* @vitest-environment jsdom */

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, beforeEach, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

import PricingPage from '../pages/PricingPage';

const createCheckoutSession = vi.fn();
const openCustomerPortal = vi.fn();
const upgradeSubscription = vi.fn();
const downgradeSubscription = vi.fn();

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string, options?: Record<string, string | number>) => {
      if (typeof fallback !== 'string') {
        return _key;
      }
      if (!options) {
        return fallback;
      }
      return Object.entries(options).reduce(
        (text, [name, value]) => text.replace(`{{${name}}}`, String(value)),
        fallback,
      );
    },
    i18n: {
      resolvedLanguage: 'en',
      language: 'en',
    },
  }),
}));

vi.mock('../stores/subscriptionStore', () => ({
  useSubscriptionStore: () => ({
    createCheckoutSession,
    openCustomerPortal,
    upgradeSubscription,
    downgradeSubscription,
    currentPlan: { plan_type: 'plus' },
    subscription: {
      status: 'active',
      stripe_subscription_id: 'sub_test_123',
    },
  }),
}));

vi.mock('../stores/authStore', () => ({
  useAuthStore: (selector: (state: { user: { is_admin: boolean } | null; isAuthenticated: boolean }) => unknown) =>
    selector({
      user: { is_admin: false },
      isAuthenticated: true,
    }),
}));

vi.mock('../hooks/useConfirm', () => ({
  useConfirm: () => ({
    confirm: vi.fn(),
    alert: vi.fn(),
  }),
}));

describe('PricingPage plan switching', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    openCustomerPortal.mockResolvedValue(undefined);
    createCheckoutSession.mockResolvedValue({
      session_id: 'cs_test_123',
      url: 'https://checkout.stripe.com/test',
    });
    upgradeSubscription.mockResolvedValue(undefined);
    downgradeSubscription.mockResolvedValue(undefined);
  });

  it('uses the Stripe-backed upgrade path when a paid subscriber selects a higher paid plan', async () => {
    render(
      <MemoryRouter>
        <PricingPage />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Upgrade' }));

    await waitFor(() => {
      expect(upgradeSubscription).toHaveBeenCalledWith(4, 'monthly');
    });

    expect(createCheckoutSession).not.toHaveBeenCalled();
    expect(openCustomerPortal).not.toHaveBeenCalled();
    expect(downgradeSubscription).not.toHaveBeenCalled();
  });
});
