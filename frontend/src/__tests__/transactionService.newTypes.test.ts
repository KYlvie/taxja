import { beforeEach, describe, expect, it, vi } from 'vitest';

const { apiMock } = vi.hoisted(() => ({
  apiMock: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock('../services/api', () => ({
  default: apiMock,
}));

import { transactionService } from '../services/transactionService';
import { TransactionType } from '../types/transaction';

describe('transactionService new transaction types', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('omits income/expense categories for liability repayment transactions', async () => {
    apiMock.post.mockResolvedValue({
      data: {
        id: 1,
        type: 'liability_repayment',
        amount: '602.08',
        transaction_date: '2026-01-20',
        description: 'Loan principal repayment',
        income_category: null,
        expense_category: null,
        is_deductible: false,
      },
    });

    const result = await transactionService.create({
      type: TransactionType.LIABILITY_REPAYMENT,
      amount: 602.08,
      date: '2026-01-20',
      description: 'Loan principal repayment',
    });

    const payload = apiMock.post.mock.calls[0][1];
    expect(payload).toMatchObject({
      type: 'liability_repayment',
      amount: 602.08,
      transaction_date: '2026-01-20',
      description: 'Loan principal repayment',
    });
    expect(payload).not.toHaveProperty('income_category');
    expect(payload).not.toHaveProperty('expense_category');
    expect(result.category).toBeUndefined();
  });

  it('still maps expense categories for expense transactions', async () => {
    apiMock.post.mockResolvedValue({
      data: {
        id: 2,
        type: 'expense',
        amount: '99.00',
        transaction_date: '2026-01-20',
        description: 'Office supplies',
        expense_category: 'office_supplies',
        is_deductible: true,
      },
    });

    await transactionService.create({
      type: TransactionType.EXPENSE,
      amount: 99,
      date: '2026-01-20',
      description: 'Office supplies',
      category: 'office_supplies',
    });

    expect(apiMock.post.mock.calls[0][1]).toMatchObject({
      type: 'expense',
      expense_category: 'office_supplies',
    });
  });
});
