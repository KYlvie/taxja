/* @vitest-environment jsdom */

import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import TransactionsPage from '../pages/TransactionsPage';
import { useTransactionStore } from '../stores/transactionStore';

const getAll = vi.fn();
const getById = vi.fn();
const deleteCheck = vi.fn();
const deleteTransaction = vi.fn();

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string | { defaultValue?: string }) => {
      if (typeof fallback === 'string') return fallback;
      if (fallback && typeof fallback === 'object' && typeof fallback.defaultValue === 'string') {
        return fallback.defaultValue;
      }
      return key;
    },
  }),
}));

vi.mock('../components/transactions/TransactionFilters', () => ({
  default: () => <div data-testid="transaction-filters" />,
}));

vi.mock('../components/transactions/TransactionList', () => ({
  default: () => <div data-testid="transaction-list" />,
}));

vi.mock('../components/transactions/TransactionForm', () => ({
  default: () => <div data-testid="transaction-form" />,
}));

vi.mock('../components/transactions/TransactionDetail', () => ({
  default: ({ transaction }: any) => <div>{`detail-${transaction.id}`}</div>,
}));

vi.mock('../services/transactionService', () => ({
  transactionService: {
    getAll: (...args: any[]) => getAll(...args),
    getById: (...args: any[]) => getById(...args),
    deleteCheck: (...args: any[]) => deleteCheck(...args),
    delete: (...args: any[]) => deleteTransaction(...args),
  },
}));

vi.mock('../mobile/files', () => ({
  saveBlobWithNativeShare: vi.fn(),
}));

vi.mock('../stores/refreshStore', () => ({
  useRefreshStore: (selector: any) => selector({ transactionsVersion: 0 }),
}));

vi.mock('../stores/aiToastStore', () => ({
  aiToast: vi.fn(),
}));

describe('TransactionsPage deep link flow', () => {
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

    getAll.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
      total_pages: 0,
    });
    getById.mockResolvedValue({
      id: 1151,
      type: 'expense',
      amount: 237.9,
      transaction_date: '2024-12-30',
      date: '2024-12-30',
      description: 'OAMTC battery replacement',
      expense_category: 'maintenance',
      category: 'maintenance',
      line_items: [],
    });
    deleteCheck.mockResolvedValue({ warning_type: null });
    deleteTransaction.mockResolvedValue(undefined);
  });

  it('opens transaction detail directly when transactionId query param is present', async () => {
    render(
      <MemoryRouter initialEntries={['/transactions?transactionId=1151']}>
        <Routes>
          <Route path="/transactions" element={<TransactionsPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => expect(getById).toHaveBeenCalledWith(1151));
    expect(screen.getByText('detail-1151')).toBeInTheDocument();
  });
});
