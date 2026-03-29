/* @vitest-environment jsdom */

import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import LiabilityOverviewPage from '../pages/LiabilityOverviewPage';
import en from '../i18n/locales/en.json';

const getSummary = vi.fn();
const list = vi.fn();
const get = vi.fn();

const translate = (
  key: string,
  fallbackOrOptions?: string | { defaultValue?: string } | Record<string, unknown>,
  params?: Record<string, unknown>,
) => {
  const fromLocale = key.split('.').reduce<unknown>((current, segment) => {
    if (current && typeof current === 'object' && segment in (current as Record<string, unknown>)) {
      return (current as Record<string, unknown>)[segment];
    }
    return undefined;
  }, en);

  const interpolationParams =
    fallbackOrOptions &&
    typeof fallbackOrOptions === 'object' &&
    !('defaultValue' in fallbackOrOptions)
      ? (fallbackOrOptions as Record<string, unknown>)
      : params;

  if (typeof fromLocale === 'string') {
    return fromLocale.replace(/\{\{(\w+)\}\}/g, (_, token) =>
      String(interpolationParams?.[token] ?? ''),
    );
  }

  if (typeof fallbackOrOptions === 'string') {
    return fallbackOrOptions;
  }

  if (
    fallbackOrOptions &&
    typeof fallbackOrOptions === 'object' &&
    'defaultValue' in fallbackOrOptions &&
    typeof fallbackOrOptions.defaultValue === 'string'
  ) {
    return fallbackOrOptions.defaultValue.replace(/\{\{(\w+)\}\}/g, (_, token) =>
      String(interpolationParams?.[token] ?? ''),
    );
  }

  return key;
};

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: translate,
    i18n: { language: 'en' },
  }),
}));

vi.mock('../services/liabilityService', () => ({
  liabilityService: {
    getSummary: (...args: unknown[]) => getSummary(...args),
    list: (...args: unknown[]) => list(...args),
    get: (...args: unknown[]) => get(...args),
  },
}));

describe('LiabilityOverviewPage', () => {
  beforeEach(() => {
    class ResizeObserverMock {
      observe() {}
      unobserve() {}
      disconnect() {}
    }

    vi.stubGlobal('ResizeObserver', ResizeObserverMock);
  });

  beforeEach(() => {
    vi.clearAllMocks();

    getSummary.mockResolvedValue({
      total_assets: 250000,
      total_liabilities: 181000,
      net_worth: 69000,
      active_liability_count: 1,
      monthly_debt_service: 950,
      annual_deductible_interest: 4800,
    });

    list.mockResolvedValue({
      total: 1,
      active_count: 1,
      items: [
        {
          id: 10,
          user_id: 1,
          liability_type: 'property_loan',
          source_type: 'document_confirmed',
          display_name: 'Sparkasse Mortgage',
          currency: 'EUR',
          lender_name: 'Sparkasse',
          principal_amount: 250000,
          outstanding_balance: 181000,
          interest_rate: 3.25,
          start_date: '2024-01-01',
          end_date: '2049-01-01',
          monthly_payment: 950,
          tax_relevant: true,
          tax_relevance_reason: 'Rental property financing',
          report_category: 'darlehen_und_kredite',
          linked_property_id: 'property-1',
          linked_loan_id: 7,
          source_document_id: 99,
          is_active: true,
          can_edit_directly: false,
          can_deactivate_directly: false,
          edit_via_document: true,
          requires_supporting_document: false,
          recommended_document_type: 'loan_contract',
          notes: null,
          created_at: '2026-03-22T00:00:00Z',
          updated_at: '2026-03-22T00:00:00Z',
        },
      ],
    });

    get.mockResolvedValue({
      id: 10,
      user_id: 1,
      liability_type: 'property_loan',
      source_type: 'document_confirmed',
      display_name: 'Sparkasse Mortgage',
      currency: 'EUR',
      lender_name: 'Sparkasse',
      principal_amount: 250000,
      outstanding_balance: 181000,
      interest_rate: 3.25,
      start_date: '2024-01-01',
      end_date: '2049-01-01',
      monthly_payment: 950,
      tax_relevant: true,
      tax_relevance_reason: 'Rental property financing',
      report_category: 'darlehen_und_kredite',
      linked_property_id: 'property-1',
      linked_loan_id: 7,
      source_document_id: 99,
      is_active: true,
      can_edit_directly: false,
      can_deactivate_directly: false,
      edit_via_document: true,
      requires_supporting_document: false,
      recommended_document_type: 'loan_contract',
      notes: null,
      created_at: '2026-03-22T00:00:00Z',
      updated_at: '2026-03-22T00:00:00Z',
      related_transactions: [],
      related_recurring_transactions: [],
    });
  });

  it('shows summary, liability portfolio, and individual liability report', async () => {
    render(
      <MemoryRouter>
        <LiabilityOverviewPage />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(
        screen.getByRole('heading', { level: 1, name: /Liability Overview/i }),
      ).toBeInTheDocument(),
    );

    expect(screen.getAllByText(/Liabilities/i).length).toBeGreaterThan(0);
    expect(screen.getByRole('heading', { name: /Liability Mix/i })).toBeInTheDocument();
    expect(screen.getAllByText('Sparkasse Mortgage').length).toBeGreaterThan(0);
    expect(screen.getByRole('heading', { name: /Individual Liability Report/i })).toBeInTheDocument();
    expect(screen.getByText(/Track balances, repayment progress/i)).toBeInTheDocument();
    expect(getSummary).toHaveBeenCalledTimes(1);
    expect(list).toHaveBeenCalledWith(true);
    expect(get).toHaveBeenCalledWith(10);
  });
});
