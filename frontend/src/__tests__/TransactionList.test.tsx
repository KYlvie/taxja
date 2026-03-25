/* @vitest-environment jsdom */

import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import TransactionList from '../components/transactions/TransactionList';
import { TransactionType, type Transaction } from '../types/transaction';

const translations: Record<string, string> = {
  'transactions.date': 'Date',
  'transactions.description': 'Description',
  'transactions.category': 'Category',
  'transactions.amount': 'Amount',
  'transactions.type': 'Type',
  'transactions.bankReconciled': 'Bank reconciled',
  'transactions.bankReconcileHint': 'Upload bank statements in Documents to reconcile.',
  'transactions.types.expense': 'Expense',
  'transactions.categories.other': 'Other',
  'common.actions': 'Actions',
  'common.edit': 'Edit',
  'common.delete': 'Delete',
  'transactions.noTransactions': 'No transactions',
};

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string | { defaultValue?: string }) => {
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

const noop = vi.fn();

const buildTransaction = (overrides: Partial<Transaction> = {}): Transaction => ({
  id: 1,
  type: TransactionType.EXPENSE,
  amount: 42.5,
  date: '2026-03-25',
  description: 'Utilities payment',
  category: 'other',
  is_deductible: false,
  bank_reconciled: false,
  ...overrides,
});

describe('TransactionList', () => {
  it('shows a reconciliation hint tooltip for unreconciled transactions', () => {
    render(
      <TransactionList
        transactions={[buildTransaction()]}
        onEdit={noop}
        onDelete={noop}
        onView={noop}
      />
    );

    const hint = screen.getByTitle('Upload bank statements in Documents to reconcile.');
    expect(hint).toHaveTextContent('-');
    expect(hint).toHaveAttribute(
      'aria-label',
      'Upload bank statements in Documents to reconcile.'
    );
  });

  it('keeps the existing reconciled title for reconciled transactions', () => {
    render(
      <TransactionList
        transactions={[buildTransaction({ id: 2, bank_reconciled: true })]}
        onEdit={noop}
        onDelete={noop}
        onView={noop}
      />
    );

    expect(screen.getByTitle('Bank reconciled')).toBeInTheDocument();
    expect(
      screen.queryByTitle('Upload bank statements in Documents to reconcile.')
    ).not.toBeInTheDocument();
  });
});
