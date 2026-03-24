/* @vitest-environment jsdom */

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import TransactionsPage from '../pages/TransactionsPage';
import { useTransactionStore } from '../stores/transactionStore';

const getAll = vi.fn();
const markReviewed = vi.fn();
const aiToast = vi.fn();

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (
      key: string,
      fallback?: string | { defaultValue?: string; count?: number },
      options?: { count?: number }
    ) => {
      if (typeof fallback === 'string') {
        return typeof options?.count === 'number'
          ? fallback.replace('{{count}}', String(options.count))
          : fallback;
      }
      if (fallback && typeof fallback === 'object' && typeof fallback.defaultValue === 'string') {
        return typeof fallback.count === 'number'
          ? fallback.defaultValue.replace('{{count}}', String(fallback.count))
          : fallback.defaultValue;
      }
      return key;
    },
  }),
}));

vi.mock('../components/transactions/TransactionFilters', () => ({
  default: ({ filters }: { filters?: { needs_review?: boolean } }) => (
    <div data-testid="transaction-filters">
      {filters?.needs_review ? 'needs-review-on' : 'needs-review-off'}
    </div>
  ),
}));

vi.mock('../components/transactions/TransactionList', () => ({
  default: () => <div data-testid="transaction-list" />,
}));

vi.mock('../components/transactions/TransactionForm', () => ({
  default: () => <div data-testid="transaction-form" />,
}));

vi.mock('../components/transactions/TransactionDetail', () => ({
  default: () => <div data-testid="transaction-detail" />,
}));

vi.mock('../services/transactionService', () => ({
  transactionService: {
    getAll: (...args: any[]) => getAll(...args),
    markReviewed: (...args: any[]) => markReviewed(...args),
    getById: vi.fn(),
    deleteCheck: vi.fn(),
    delete: vi.fn(),
    batchDelete: vi.fn(),
    pause: vi.fn(),
    resume: vi.fn(),
    exportCSV: vi.fn(),
    exportPDF: vi.fn(),
  },
}));

vi.mock('../mobile/files', () => ({
  saveBlobWithNativeShare: vi.fn(),
}));

vi.mock('../stores/refreshStore', () => ({
  useRefreshStore: (selector: any) => selector({ transactionsVersion: 0 }),
}));

vi.mock('../stores/aiToastStore', () => ({
  aiToast: (...args: any[]) => aiToast(...args),
}));

vi.mock('../hooks/useAIConfirmation', () => ({
  useAIConfirmation: () => ({
    confirm: vi.fn(),
    alert: vi.fn(),
  }),
}));

describe('TransactionsPage bulk confirm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useTransactionStore.setState({
      transactions: [],
      filters: {},
      selectedTransaction: null,
      isLoading: false,
      error: null,
      pagination: { page: 1, pageSize: 20, total: 0 },
    });

    getAll
      .mockResolvedValueOnce({
        items: [],
        total: 0,
        page: 1,
        page_size: 20,
        total_pages: 0,
        available_years: [],
        needs_review_count: 2,
      })
      .mockResolvedValueOnce({
        items: [
          {
            id: 41,
            type: 'expense',
            amount: 33,
            date: '2024-06-26',
            description: 'T-Mobile Austria GmbH',
            needs_review: true,
          },
          {
            id: 42,
            type: 'expense',
            amount: 69.26,
            date: '2024-08-16',
            description: 'T-Mobile Austria GmbH',
            needs_review: true,
          },
        ],
        total: 2,
        page: 1,
        page_size: 100,
        total_pages: 1,
        available_years: [],
        needs_review_count: 2,
      })
      .mockResolvedValueOnce({
        items: [],
        total: 0,
        page: 1,
        page_size: 20,
        total_pages: 0,
        available_years: [],
        needs_review_count: 0,
      });

    markReviewed.mockImplementation(async (id: number) => ({
      id,
      type: 'expense',
      amount: 33,
      date: '2024-06-26',
      description: `transaction-${id}`,
      needs_review: false,
      reviewed: true,
    }));
  });

  it('marks all currently filtered review items as reviewed', async () => {
    render(
      <MemoryRouter initialEntries={['/transactions']}>
        <Routes>
          <Route path="/transactions" element={<TransactionsPage />} />
        </Routes>
      </MemoryRouter>,
    );

    const confirmButton = await screen.findByRole('button', { name: 'One-click confirm' });
    fireEvent.click(confirmButton);

    await waitFor(() => {
      expect(markReviewed).toHaveBeenCalledTimes(2);
    });
    expect(markReviewed).toHaveBeenNthCalledWith(1, 41);
    expect(markReviewed).toHaveBeenNthCalledWith(2, 42);

    await waitFor(() => {
      expect(aiToast).toHaveBeenCalledWith('Confirmed 2 items.', 'success');
    });
  });

  it('applies the review filter from the reports quick link on first load', async () => {
    getAll.mockReset();
    getAll.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
      total_pages: 0,
      available_years: [],
      needs_review_count: 4,
    });

    render(
      <MemoryRouter initialEntries={['/transactions?needs_review=true']}>
        <Routes>
          <Route path="/transactions" element={<TransactionsPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(getAll).toHaveBeenCalledWith(
        expect.objectContaining({ needs_review: true }),
        expect.objectContaining({ page: 1, page_size: 20 }),
      );
    });

    expect(await screen.findByText('needs-review-on')).toBeInTheDocument();
  });
});
