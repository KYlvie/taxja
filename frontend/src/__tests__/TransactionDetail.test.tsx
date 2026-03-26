/* @vitest-environment jsdom */

import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import TransactionDetail from '../components/transactions/TransactionDetail';
import { TransactionType, type Transaction } from '../types/transaction';

const navigateMock = vi.fn();
const noop = vi.fn();

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string | { defaultValue?: string }) => {
      const translations: Record<string, string> = {
        'transactions.transactionDetails': 'Transaction Details',
        'transactions.type': 'Type',
        'transactions.types.income': 'Income',
        'transactions.amount': 'Amount',
        'transactions.date': 'Date',
        'transactions.category': 'Category',
        'transactions.description': 'Description',
        'transactions.taxInformation': 'Tax Information',
        'transactions.lineItems.title': 'Line Items',
        'transactions.notDeductible': 'Not deductible',
        'transactions.deductibleYes': 'Deductible',
        'transactions.lineItems.deductibleTotal': 'Deductible total',
        'transactions.lineItems.nonDeductibleTotal': 'Non-deductible total',
        'common.close': 'Close',
        'common.edit': 'Edit',
        'common.delete': 'Delete',
        'transactions.confirmDelete': 'Delete transaction?',
      };

      if (translations[key]) return translations[key];
      if (typeof fallback === 'string') return fallback;
      if (fallback && typeof fallback === 'object' && typeof fallback.defaultValue === 'string') {
        return fallback.defaultValue;
      }
      return key;
    },
    i18n: { language: 'en', resolvedLanguage: 'en' },
  }),
}));

vi.mock('react-router-dom', () => ({
  useNavigate: () => navigateMock,
}));

vi.mock('../hooks/useConfirm', () => ({
  useConfirm: () => ({
    confirm: vi.fn().mockResolvedValue(true),
  }),
}));

const buildTransaction = (overrides: Partial<Transaction> = {}): Transaction => ({
  id: 99,
  type: TransactionType.INCOME,
  amount: 13000,
  date: '2024-06-30',
  description: 'Invoice income',
  category: 'self_employment',
  is_deductible: false,
  deductible_amount: 0,
  non_deductible_amount: 13000,
  line_items: [
    {
      description: 'Security audit',
      amount: 9500,
      quantity: 1,
      category: 'self_employment',
      is_deductible: false,
      sort_order: 0,
    },
  ],
  ...overrides,
});

describe('TransactionDetail', () => {
  it('hides deductibility badges and totals for income transactions', () => {
    render(
      <TransactionDetail
        transaction={buildTransaction()}
        onEdit={noop}
        onDelete={noop}
        onClose={noop}
      />
    );

    expect(screen.getByText('Line Items')).toBeInTheDocument();
    expect(screen.queryByText('Tax Information')).not.toBeInTheDocument();
    expect(screen.queryByText('Not deductible')).not.toBeInTheDocument();
    expect(screen.queryByText('Deductible total')).not.toBeInTheDocument();
    expect(screen.queryByText('Non-deductible total')).not.toBeInTheDocument();
  });
});
