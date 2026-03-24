/* @vitest-environment jsdom */

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import BankStatementWorkbench from '../components/documents/BankStatementWorkbench';

const confirmBankTransactions = vi.fn();
const downloadDocument = vi.fn();
const getDocument = vi.fn();
const initializeFromDocument = vi.fn();
const getLines = vi.fn();
const getImport = vi.fn();
const aiToast = vi.fn();
const translationApi = {
  t: (
    key: string,
    fallback?: string | { defaultValue?: string },
    options?: Record<string, unknown>,
  ) => {
    if (typeof fallback === 'string') {
      return typeof options?.count === 'number'
        ? fallback.replace('{{count}}', String(options.count))
        : fallback;
    }
    if (fallback && typeof fallback === 'object' && typeof fallback.defaultValue === 'string') {
      return fallback.defaultValue;
    }
    return key;
  },
  i18n: {
    language: 'en',
    resolvedLanguage: 'en',
  },
};

const makeFallbackDocument = (overrides: Record<string, unknown> = {}) => ({
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
    import_suggestion: {
      type: 'import_bank_statement',
      status: 'pending',
      data: {
        bank_name: 'Magenta Bank',
        iban: 'AT602011183744980900',
        transactions: [
          {
            date: '2024-12-18',
            amount: -62.23,
            counterparty: 'T-Mobile Austria GmbH',
            reference: 'Mobile invoice December',
            transaction_type: 'debit',
          },
        ],
      },
    },
    transactions: [
      {
        date: '2024-12-18',
        amount: -62.23,
        counterparty: 'T-Mobile Austria GmbH',
        reference: 'Mobile invoice December',
        transaction_type: 'debit',
      },
    ],
  },
  ...overrides,
});

vi.mock('react-i18next', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-i18next')>();
  return {
    ...actual,
    useTranslation: () => translationApi,
  };
});

vi.mock('../components/common/SubpageBackLink', () => ({
  default: () => <div data-testid="back-link" />,
}));

vi.mock('../services/documentService', () => ({
  documentService: {
    confirmBankTransactions: (...args: any[]) => confirmBankTransactions(...args),
    downloadDocument: (...args: any[]) => downloadDocument(...args),
    getDocument: (...args: any[]) => getDocument(...args),
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
  aiToast: (...args: unknown[]) => aiToast(...args),
}));

describe('BankStatementWorkbench local fallback', () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    global.URL.createObjectURL = vi.fn(() => 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4////fwAJ+wP9KobjigAAAABJRU5ErkJggg==');
    global.URL.revokeObjectURL = vi.fn();

    confirmBankTransactions.mockResolvedValue({
      imported: 0,
      imported_count: 0,
      remaining_count: 1,
      skipped_duplicates: 0,
      suggestion_status: 'pending',
      created_transaction_ids: [],
      classified: 0,
      message: '',
    });
    downloadDocument.mockResolvedValue(new Blob(['statement'], { type: 'image/png' }));
    getDocument.mockResolvedValue(makeFallbackDocument());
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
          ...makeFallbackDocument(),
          ocr_result: {
            ...makeFallbackDocument().ocr_result,
            import_suggestion: {
              ...makeFallbackDocument().ocr_result.import_suggestion,
              data: {
                ...makeFallbackDocument().ocr_result.import_suggestion.data,
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
            },
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
    expect(screen.getAllByText('Mobile invoice December').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Payroll').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Debit').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Credit').length).toBeGreaterThan(0);
  });

  it('rebuilds fallback rows from the refreshed document instead of marking them imported optimistically', async () => {
    const document = makeFallbackDocument();
    getDocument.mockResolvedValue(document);

    render(<BankStatementWorkbench document={document} />);

    await waitFor(() => expect(screen.getByText('Extracted transaction lines')).toBeInTheDocument());
    await waitFor(() => expect(screen.getAllByText('Create transaction').length).toBeGreaterThan(0));

    fireEvent.click(screen.getAllByText('Create transaction')[0]);

    await waitFor(() => expect(confirmBankTransactions).toHaveBeenCalledWith(326, [0], [
      {
        date: '2024-12-18',
        amount: -62.23,
        counterparty: 'T-Mobile Austria GmbH',
        purpose: 'Mobile invoice December',
        raw_reference: 'Mobile invoice December',
        fingerprint: '2024-12-18|-62.23|t-mobile austria gmbh|mobile invoice december',
      },
    ]));
    await waitFor(() => expect(getDocument).toHaveBeenCalledWith(326));
    expect(screen.getAllByText('Create transaction').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Pending review').length).toBeGreaterThan(0);
    expect(aiToast).toHaveBeenCalledWith('No new transactions were created.', 'warning');
  });

  it('shows an info toast when fallback lines were already imported', async () => {
    const document = makeFallbackDocument();
    getDocument.mockResolvedValue(document);
    confirmBankTransactions.mockResolvedValue({
      imported: 0,
      imported_count: 1,
      remaining_count: 0,
      skipped_duplicates: 1,
      suggestion_status: 'confirmed',
      created_transaction_ids: [],
      classified: 0,
      message: '',
    });

    render(<BankStatementWorkbench document={document} />);

    await waitFor(() => expect(screen.getByText('Extracted transaction lines')).toBeInTheDocument());
    fireEvent.click(screen.getAllByText('Create transaction')[0]);

    await waitFor(() => expect(confirmBankTransactions).toHaveBeenCalled());
    expect(aiToast).toHaveBeenCalledWith('This statement line was already imported.', 'info');
  });

  it('confirms all pending fallback lines with the full snapshot and shows a batch success toast', async () => {
    const document = {
      ...makeFallbackDocument(),
      ocr_result: {
        ...makeFallbackDocument().ocr_result,
        import_suggestion: {
          ...makeFallbackDocument().ocr_result.import_suggestion,
          data: {
            ...makeFallbackDocument().ocr_result.import_suggestion.data,
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
        },
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
    };
    const updatedDocument = {
      ...document,
      ocr_result: {
        ...document.ocr_result,
        import_suggestion: {
          ...document.ocr_result.import_suggestion,
          fallback_imported_fingerprints: [
            '2024-12-18|-62.23|t-mobile austria gmbh|mobile invoice december',
            '2024-12-22|1200.00|salary gmbh|payroll',
          ],
        },
      },
    };
    getDocument.mockResolvedValue(updatedDocument);
    confirmBankTransactions.mockResolvedValue({
      imported: 2,
      imported_count: 2,
      remaining_count: 0,
      skipped_duplicates: 0,
      suggestion_status: 'confirmed',
      created_transaction_ids: [901, 902],
      classified: 2,
      message: '',
    });

    render(<BankStatementWorkbench document={document} />);

    await waitFor(() => expect(screen.getByText('Extracted transaction lines')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }));

    await waitFor(() => expect(confirmBankTransactions).toHaveBeenCalledWith(326, [0, 1], [
      {
        date: '2024-12-18',
        amount: -62.23,
        counterparty: 'T-Mobile Austria GmbH',
        purpose: 'Mobile invoice December',
        raw_reference: 'Mobile invoice December',
        fingerprint: '2024-12-18|-62.23|t-mobile austria gmbh|mobile invoice december',
      },
      {
        date: '2024-12-22',
        amount: 1200,
        counterparty: 'Salary GmbH',
        purpose: 'Payroll',
        raw_reference: 'Payroll',
        fingerprint: '2024-12-22|1200.00|salary gmbh|payroll',
      },
    ]));
    await waitFor(() => expect(getDocument).toHaveBeenCalledWith(326));
    expect(aiToast).toHaveBeenCalledWith('Created 2 transactions.', 'success');
    expect(screen.getAllByText('Auto-created').length).toBeGreaterThan(0);
  });
});
