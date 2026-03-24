/* @vitest-environment jsdom */

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ClassificationRules from '../components/transactions/ClassificationRules';

const apiGet = vi.fn();
const apiDelete = vi.fn();
const aiToast = vi.fn();

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string | { defaultValue?: string }) => {
      const translations: Record<string, string> = {
        'transactions.categories.vehicle': 'Vehicle',
        'transactions.categories.groceries': 'Groceries',
        'transactions.deductibleYes': 'Deductible',
        'transactions.notDeductible': 'Not deductible',
        'transactions.types.expense': 'Expense',
        'transactions.types.income': 'Income',
      };
      if (typeof fallback === 'string') return fallback;
      if (translations[key]) return translations[key];
      if (fallback && typeof fallback === 'object' && typeof fallback.defaultValue === 'string') {
        return fallback.defaultValue;
      }
      return key;
    },
    i18n: { language: 'de-AT' },
  }),
}));

vi.mock('../services/api', () => ({
  default: {
    get: (...args: unknown[]) => apiGet(...args),
    delete: (...args: unknown[]) => apiDelete(...args),
  },
}));

vi.mock('../stores/aiToastStore', () => ({
  aiToast: (...args: unknown[]) => aiToast(...args),
}));

vi.mock('../components/common/ConfirmDialog', () => ({
  default: ({
    isOpen,
    confirmText,
    cancelText,
    onConfirm,
    onCancel,
  }: {
    isOpen: boolean;
    confirmText: string;
    cancelText: string;
    onConfirm: () => void;
    onCancel: () => void;
  }) =>
    isOpen ? (
      <div>
        <button type="button" onClick={onCancel}>
          {cancelText}
        </button>
        <button type="button" onClick={onConfirm}>
          {confirmText}
        </button>
      </div>
    ) : null,
}));

describe('ClassificationRules', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads both rule sections and renders a non-empty derived reason for classification rules', async () => {
    apiGet
      .mockResolvedValueOnce({
        data: [
          {
            id: 1,
            normalized_description: 'interspar breakfast groceries',
            original_description: 'INTERSPAR breakfast groceries',
            txn_type: 'expense',
            category: 'groceries',
            hit_count: 4,
            confidence: 0.92,
            rule_type: 'strict',
            frozen: false,
            conflict_count: 0,
            last_hit_at: null,
            created_at: null,
          },
        ],
      })
      .mockResolvedValueOnce({
        data: [
          {
            id: 7,
            normalized_description: 'omv guest shuttle fuel',
            original_description: 'OMV guest shuttle fuel',
            expense_category: 'vehicle',
            is_deductible: true,
            reason: 'Guest transport for lodging business',
            hit_count: 2,
            last_hit_at: '2026-03-22T10:00:00Z',
            created_at: '2026-03-20T10:00:00Z',
            updated_at: '2026-03-22T10:00:00Z',
          },
        ],
      });

    render(<ClassificationRules />);

    await waitFor(() => expect(apiGet).toHaveBeenCalledTimes(2));

    expect(screen.getByText('Category rules')).toBeInTheDocument();
    expect(screen.getByText('Deductibility overrides')).toBeInTheDocument();
    expect(screen.getByText('INTERSPAR breakfast groceries')).toBeInTheDocument();
    expect(screen.getByText('OMV guest shuttle fuel')).toBeInTheDocument();
    expect(screen.getByText('Vehicle')).toBeInTheDocument();
    expect(screen.getByText('Deductible')).toBeInTheDocument();
    expect(screen.getByText('Saved from your manual category correction.')).toBeInTheDocument();
  });

  it('supports bulk deleting selected classification rules', async () => {
    apiGet
      .mockResolvedValueOnce({
        data: [
          {
            id: 1,
            normalized_description: 'parking one',
            original_description: 'Parking One',
            txn_type: 'expense',
            category: 'vehicle',
            hit_count: 1,
            confidence: 1,
            rule_type: 'strict',
            frozen: false,
            conflict_count: 0,
            last_hit_at: null,
            created_at: null,
          },
          {
            id: 2,
            normalized_description: 'parking two',
            original_description: 'Parking Two',
            txn_type: 'expense',
            category: 'vehicle',
            hit_count: 1,
            confidence: 1,
            rule_type: 'strict',
            frozen: false,
            conflict_count: 0,
            last_hit_at: null,
            created_at: null,
          },
        ],
      })
      .mockResolvedValueOnce({ data: [] });
    apiDelete.mockResolvedValue({ data: { deleted: true } });

    render(<ClassificationRules />);

    await waitFor(() => expect(screen.getByText('Parking One')).toBeInTheDocument());

    const categorySection = screen.getByText('Category rules').closest('section');
    expect(categorySection).not.toBeNull();
    const section = categorySection as HTMLElement;

    fireEvent.click(within(section).getByLabelText('Select all category rules'));
    fireEvent.click(within(section).getByRole('button', { name: 'Delete selected (2)' }));
    const deleteButtons = screen.getAllByRole('button', { name: 'Delete' });
    fireEvent.click(deleteButtons[deleteButtons.length - 1]);

    await waitFor(() => expect(apiDelete).toHaveBeenNthCalledWith(1, '/classification-rules/1'));
    await waitFor(() => expect(apiDelete).toHaveBeenNthCalledWith(2, '/classification-rules/2'));
    await waitFor(() => expect(screen.queryByText('Parking One')).not.toBeInTheDocument());
    await waitFor(() => expect(screen.queryByText('Parking Two')).not.toBeInTheDocument());
    expect(aiToast).toHaveBeenCalled();
  });

  it('paginates long classification rule lists', async () => {
    apiGet
      .mockResolvedValueOnce({
        data: Array.from({ length: 12 }, (_, index) => ({
          id: index + 1,
          normalized_description: `rule ${index + 1}`,
          original_description: `Rule ${index + 1}`,
          txn_type: 'expense',
          category: 'vehicle',
          hit_count: 1,
          confidence: 1,
          rule_type: 'strict',
          frozen: false,
          conflict_count: 0,
          last_hit_at: null,
          created_at: null,
        })),
      })
      .mockResolvedValueOnce({ data: [] });

    render(<ClassificationRules />);

    await waitFor(() => expect(screen.getByText('Rule 1')).toBeInTheDocument());
    expect(screen.queryByText('Rule 11')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '2' }));

    await waitFor(() => expect(screen.getByText('Rule 11')).toBeInTheDocument());
    expect(screen.queryByText('Rule 1')).not.toBeInTheDocument();
  });

  it('shows both empty sections when no rules exist yet', async () => {
    apiGet
      .mockResolvedValueOnce({ data: [] })
      .mockResolvedValueOnce({ data: [] });

    render(<ClassificationRules />);

    await waitFor(() => expect(apiGet).toHaveBeenCalledTimes(2));

    expect(screen.getByText('Category rules')).toBeInTheDocument();
    expect(screen.getByText('Deductibility overrides')).toBeInTheDocument();
    expect(
      screen.getByText('No category rules yet. They will appear after you correct a transaction category.')
    ).toBeInTheDocument();
    expect(
      screen.getByText('No deductibility overrides yet. They will appear after you mark a transaction or receipt item deductible or non-deductible.')
    ).toBeInTheDocument();
  });
});
