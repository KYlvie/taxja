/* @vitest-environment jsdom */

import { render, screen, waitFor } from '@testing-library/react';
import { describe, beforeEach, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import CheckoutSuccess from '../pages/CheckoutSuccess';

const fetchSubscription = vi.fn();
const fetchCreditBalance = vi.fn();
const syncCheckoutSession = vi.fn();

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string, options?: Record<string, string>) => {
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
  }),
}));

vi.mock('../stores/subscriptionStore', () => ({
  useSubscriptionStore: () => ({
    fetchSubscription,
    fetchCreditBalance,
    syncCheckoutSession,
    currentPlan: { name: 'Pro' },
  }),
}));

describe('CheckoutSuccess sync', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    syncCheckoutSession.mockResolvedValue(undefined);
    fetchSubscription.mockResolvedValue(undefined);
    fetchCreditBalance.mockResolvedValue(undefined);
  });

  it('reconciles the checkout session before showing updated plan state', async () => {
    render(
      <MemoryRouter initialEntries={['/checkout/success?session_id=cs_test_sync_123']}>
        <Routes>
          <Route path="/checkout/success" element={<CheckoutSuccess />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(syncCheckoutSession).toHaveBeenCalledWith('cs_test_sync_123');
    });

    expect(fetchSubscription).not.toHaveBeenCalled();
    expect(fetchCreditBalance).not.toHaveBeenCalled();
    expect(await screen.findByText('Your Pro plan is now active!')).toBeInTheDocument();
  });
});
