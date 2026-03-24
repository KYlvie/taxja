/* @vitest-environment jsdom */

import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import BankStatementWorkbench from '../components/documents/BankStatementWorkbench';

const downloadDocument = vi.fn();
const initializeFromDocument = vi.fn();
const getLines = vi.fn();
const getImport = vi.fn();

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string | { defaultValue?: string }) => {
      if (typeof fallback === 'string') return fallback;
      if (fallback && typeof fallback === 'object' && typeof fallback.defaultValue === 'string') {
        return fallback.defaultValue;
      }
      return key;
    },
    i18n: {
      language: 'en',
      resolvedLanguage: 'en',
    },
  }),
}));

vi.mock('../components/common/SubpageBackLink', () => ({
  default: () => <div data-testid="back-link" />,
}));

vi.mock('../services/documentService', () => ({
  documentService: {
    downloadDocument: (...args: any[]) => downloadDocument(...args),
    getDocument: vi.fn(),
  },
}));

vi.mock('../services/bankImportService', () => ({
  bankImportService: {
    initializeFromDocument: (...args: any[]) => initializeFromDocument(...args),
    getLines: (...args: any[]) => getLines(...args),
    getImport: (...args: any[]) => getImport(...args),
  },
}));

vi.mock('../mobile/files', () => ({
  saveBlobWithNativeShare: vi.fn(),
}));

vi.mock('../stores/refreshStore', () => ({
  useRefreshStore: {
    getState: () => ({
      refreshTransactions: vi.fn(),
      refreshDashboard: vi.fn(),
    }),
  },
}));

vi.mock('../stores/aiToastStore', () => ({
  aiToast: vi.fn(),
}));

describe('BankStatementWorkbench local fallback', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.URL.createObjectURL = vi.fn(() => 'blob:test');
    global.URL.revokeObjectURL = vi.fn();

    downloadDocument.mockResolvedValue(new Blob(['statement']));
    initializeFromDocument.mockRejectedValue({
      response: {
        status: 404,
        data: {
          detail: 'Not Found',
        },
      },
    });
  });

  it('shows extracted transaction rows in a table when the bank import workbench endpoint is unavailable', async () => {
    render(
      <BankStatementWorkbench
        document={{
          id: 326,
          user_id: 46,
          document_type: 'BANK_STATEMENT' as any,
          file_path: '/tmp/t-mobile.pdf',
          file_name: 'T-Mobile.pdf',
          file_size: 1024,
          mime_type: 'image/png',
          confidence_score: 0.27,
          needs_review: true,
          created_at: '2026-03-24T00:00:00Z',
          updated_at: '2026-03-24T00:00:00Z',
          uploaded_at: '2026-03-24T00:00:00Z',
          processed_at: '2026-03-24T00:00:04Z',
          ocr_result: {
            bank_name: 'Magenta Bank',
            iban: 'AT602011183744980900',
            taxpayer_name: 'T-Mobile Customer',
            period_start: '2024-07-01',
            period_end: '2024-12-31',
            opening_balance: 12.45,
            closing_balance: -64.26,
            transactions: [
              {
                date: '2024-12-18',
                amount: -62.23,
                counterparty: 'T-Mobile Austria GmbH',
                reference: 'Mobile invoice December',
                transaction_type: 'debit',
              },
              {
                date: '2024-12-22',
                amount: 1200,
                counterparty: 'Salary GmbH',
                reference: 'Payroll',
                transaction_type: 'credit',
              },
            ],
          },
        }}
      />
    );

    await waitFor(() => expect(downloadDocument).toHaveBeenCalledWith(326));
    await waitFor(() => expect(screen.getByText('Extracted transaction lines')).toBeInTheDocument());

    expect(screen.getByText('This bank statement is shown as extracted transaction lines because the bank import workbench is unavailable in this environment.')).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Date' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Counterparty' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Purpose' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Amount' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Direction' })).toBeInTheDocument();
    expect(screen.getByText('Mobile invoice December')).toBeInTheDocument();
    expect(screen.getByText('Payroll')).toBeInTheDocument();
    expect(screen.getByText('Debit')).toBeInTheDocument();
    expect(screen.getByText('Credit')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Create transaction' })).not.toBeInTheDocument();
  });
});
