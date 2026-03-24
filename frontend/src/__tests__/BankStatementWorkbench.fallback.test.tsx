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
const confirmCreateLine = vi.fn();
const matchExistingLine = vi.fn();
const ignoreLine = vi.fn();
const undoCreateLine = vi.fn();
const unmatchLine = vi.fn();
const aiToast = vi.fn();
const navigate = vi.fn();
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

const createDeferred = <T,>() => {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
};

vi.mock('react-i18next', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-i18next')>();
  return {
    ...actual,
    useTranslation: () => translationApi,
  };
});

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return {
    ...actual,
    useNavigate: () => navigate,
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
    confirmCreateLine: (...args: any[]) => confirmCreateLine(...args),
    matchExistingLine: (...args: any[]) => matchExistingLine(...args),
    ignoreLine: (...args: any[]) => ignoreLine(...args),
    undoCreateLine: (...args: any[]) => undoCreateLine(...args),
    unmatchLine: (...args: any[]) => unmatchLine(...args),
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
    confirmBankTransactions.mockReset();
    downloadDocument.mockReset();
    getDocument.mockReset();
    initializeFromDocument.mockReset();
    getLines.mockReset();
    getImport.mockReset();
    confirmCreateLine.mockReset();
    matchExistingLine.mockReset();
    ignoreLine.mockReset();
    undoCreateLine.mockReset();
    unmatchLine.mockReset();
    navigate.mockReset();
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

  it('renders object-based statement periods from the remote workbench summary without crashing', async () => {
    initializeFromDocument.mockResolvedValue({
      id: 12,
      source_type: 'document',
      source_document_id: 326,
      bank_name: 'Magenta Bank',
      iban: 'AT602011183744980900',
      statement_period: {
        start: '2024-07-01',
        end: '2024-12-31',
      },
      tax_year: 2024,
      created_at: '2026-03-24T00:00:04Z',
      updated_at: '2026-03-24T00:00:04Z',
      total_count: 1,
      auto_created_count: 0,
      matched_existing_count: 0,
      pending_review_count: 1,
      ignored_count: 0,
    });
    getLines.mockResolvedValue([]);

    render(<BankStatementWorkbench document={makeFallbackDocument()} />);

    await waitFor(() => expect(screen.getByText('Import summary')).toBeInTheDocument());
    expect(screen.getByText('01/07/2024 - 31/12/2024')).toBeInTheDocument();
  });

  it('loads the remote import summary without waiting for the preview download to finish', async () => {
    const previewGate = createDeferred<Blob>();
    downloadDocument.mockImplementation(() => previewGate.promise);
    initializeFromDocument.mockResolvedValue({
      id: 12,
      source_type: 'document',
      source_document_id: 326,
      bank_name: 'Fast Bank',
      iban: 'AT009999999999999999',
      statement_period: {
        start: '2024-07-01',
        end: '2024-12-31',
      },
      tax_year: 2024,
      created_at: '2026-03-24T00:00:04Z',
      updated_at: '2026-03-24T00:00:04Z',
      total_count: 7,
      auto_created_count: 5,
      matched_existing_count: 1,
      pending_review_count: 1,
      ignored_count: 0,
    });
    getLines.mockResolvedValue([]);

    render(<BankStatementWorkbench document={makeFallbackDocument()} />);

    await waitFor(() => expect(screen.getByText('Fast Bank')).toBeInTheDocument());
    expect(screen.getByText('Loading preview...')).toBeInTheDocument();
    expect(screen.getByText('7')).toBeInTheDocument();

    previewGate.resolve(new Blob(['statement'], { type: 'image/png' }));

    await waitFor(() => expect(global.URL.createObjectURL).toHaveBeenCalled());
  });

  it('shows a view transaction action for auto-created remote lines', async () => {
    initializeFromDocument.mockResolvedValue({
      id: 12,
      source_type: 'document',
      source_document_id: 326,
      bank_name: 'Magenta Bank',
      iban: 'AT602011183744980900',
      statement_period: {
        start: '2024-07-01',
        end: '2024-12-31',
      },
      tax_year: 2024,
      created_at: '2026-03-24T00:00:04Z',
      updated_at: '2026-03-24T00:00:04Z',
      total_count: 1,
      auto_created_count: 1,
      matched_existing_count: 0,
      pending_review_count: 0,
      ignored_count: 0,
    });
    getLines.mockResolvedValue([
      {
        id: 88,
        line_date: '2024-12-18',
        amount: '-62.23',
        counterparty: 'T-Mobile Austria GmbH',
        purpose: 'Mobile invoice December',
        raw_reference: 'Mobile invoice December',
        normalized_fingerprint: 'fp-1',
        review_status: 'auto_created',
        suggested_action: 'create_new',
        confidence_score: '0.90',
        linked_transaction_id: 1621,
        created_transaction_id: 1621,
        linked_transaction: {
          id: 1621,
          amount: '62.23',
          transaction_date: '2024-12-18',
          description: 'T-Mobile Austria GmbH',
        },
        created_transaction: {
          id: 1621,
          amount: '62.23',
          transaction_date: '2024-12-18',
          description: 'T-Mobile Austria GmbH',
        },
      },
    ]);

    render(<BankStatementWorkbench document={makeFallbackDocument()} />);

    await waitFor(() => expect(screen.getByText('Import summary')).toBeInTheDocument());
    fireEvent.click(screen.getAllByRole('button', { name: 'View transaction' })[0]);

    expect(navigate).toHaveBeenCalledWith('/transactions?transactionId=1621');
  });

  it('normalizes orphaned remote line states back to pending review in the UI', async () => {
    initializeFromDocument.mockResolvedValue({
      id: 12,
      source_type: 'document',
      source_document_id: 326,
      bank_name: 'Magenta Bank',
      iban: 'AT602011183744980900',
      statement_period: {
        start: '2024-07-01',
        end: '2024-12-31',
      },
      tax_year: 2024,
      created_at: '2026-03-24T00:00:04Z',
      updated_at: '2026-03-24T00:00:04Z',
      total_count: 1,
      auto_created_count: 0,
      matched_existing_count: 0,
      pending_review_count: 1,
      ignored_count: 0,
    });
    getLines.mockResolvedValue([
      {
        id: 188,
        line_date: '2024-12-18',
        amount: '-62.23',
        counterparty: 'T-Mobile Austria GmbH',
        purpose: 'Mobile invoice December',
        raw_reference: 'Mobile invoice December',
        normalized_fingerprint: 'stale-fp-1',
        review_status: 'auto_created',
        suggested_action: 'create_new',
        confidence_score: '0.90',
        linked_transaction_id: null,
        created_transaction_id: null,
        linked_transaction: null,
        created_transaction: null,
      },
    ]);

    render(<BankStatementWorkbench document={makeFallbackDocument()} />);

    await waitFor(() => expect(screen.getByText('Import summary')).toBeInTheDocument());
    expect(screen.getAllByText('Pending review').length).toBeGreaterThan(0);
    expect(screen.getAllByRole('button', { name: 'Create transaction' }).length).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: 'View transaction' })).not.toBeInTheDocument();
  });

  it('undoes an auto-created remote line back to pending review', async () => {
    const autoCreatedLine = {
      id: 88,
      line_date: '2024-12-18',
      amount: '-62.23',
      counterparty: 'T-Mobile Austria GmbH',
      purpose: 'Mobile invoice December',
      raw_reference: 'Mobile invoice December',
      normalized_fingerprint: 'fp-1',
      review_status: 'auto_created',
      suggested_action: 'create_new',
      confidence_score: '0.90',
      linked_transaction_id: 1621,
      created_transaction_id: 1621,
      linked_transaction: {
        id: 1621,
        amount: '62.23',
        transaction_date: '2024-12-18',
        description: 'T-Mobile Austria GmbH',
      },
      created_transaction: {
        id: 1621,
        amount: '62.23',
        transaction_date: '2024-12-18',
        description: 'T-Mobile Austria GmbH',
      },
    };
    const pendingLine = {
      ...autoCreatedLine,
      review_status: 'pending_review',
      linked_transaction_id: null,
      created_transaction_id: null,
      linked_transaction: null,
      created_transaction: null,
    };

    initializeFromDocument.mockResolvedValue({
      id: 12,
      source_type: 'document',
      source_document_id: 326,
      bank_name: 'Magenta Bank',
      iban: 'AT602011183744980900',
      statement_period: {
        start: '2024-07-01',
        end: '2024-12-31',
      },
      tax_year: 2024,
      created_at: '2026-03-24T00:00:04Z',
      updated_at: '2026-03-24T00:00:04Z',
      total_count: 1,
      auto_created_count: 1,
      matched_existing_count: 0,
      pending_review_count: 0,
      ignored_count: 0,
    });
    getLines
      .mockResolvedValueOnce([autoCreatedLine])
      .mockResolvedValueOnce([pendingLine]);
    getImport.mockResolvedValue({
      id: 12,
      source_type: 'document',
      source_document_id: 326,
      bank_name: 'Magenta Bank',
      iban: 'AT602011183744980900',
      statement_period: {
        start: '2024-07-01',
        end: '2024-12-31',
      },
      tax_year: 2024,
      created_at: '2026-03-24T00:00:04Z',
      updated_at: '2026-03-24T00:00:05Z',
      total_count: 1,
      auto_created_count: 0,
      matched_existing_count: 0,
      pending_review_count: 1,
      ignored_count: 0,
    });
    undoCreateLine.mockResolvedValue({
      success: true,
      line: pendingLine,
    });

    render(<BankStatementWorkbench document={makeFallbackDocument()} />);

    await waitFor(() => expect(screen.getByText('Import summary')).toBeInTheDocument());
    fireEvent.click(screen.getAllByRole('button', { name: 'Undo create' })[0]);

    await waitFor(() => expect(undoCreateLine).toHaveBeenCalledWith(88));
    await waitFor(() => expect(getImport).toHaveBeenCalledWith(12));
    await waitFor(() => expect(screen.getAllByRole('button', { name: 'Create transaction' }).length).toBeGreaterThan(0));
  });

  it('shows pending match suggestions as action hints without treating them as linked transactions', async () => {
    const pendingSuggestedMatchLine = {
      id: 87,
      line_date: '2024-12-21',
      amount: '1200.00',
      counterparty: 'Salary GmbH',
      purpose: 'Payroll',
      raw_reference: 'Payroll',
      normalized_fingerprint: 'fp-suggested-match',
      review_status: 'pending_review',
      suggested_action: 'match_existing',
      confidence_score: '0.82',
      linked_transaction_id: 2001,
      created_transaction_id: null,
      linked_transaction: {
        id: 2001,
        amount: '1200.00',
        transaction_date: '2024-12-22',
        description: 'Suggested salary match',
      },
      created_transaction: null,
    };

    initializeFromDocument.mockResolvedValue({
      id: 12,
      source_type: 'document',
      source_document_id: 326,
      bank_name: 'Magenta Bank',
      iban: 'AT602011183744980900',
      statement_period: {
        start: '2024-07-01',
        end: '2024-12-31',
      },
      tax_year: 2024,
      created_at: '2026-03-24T00:00:04Z',
      updated_at: '2026-03-24T00:00:04Z',
      total_count: 1,
      auto_created_count: 0,
      matched_existing_count: 0,
      pending_review_count: 1,
      ignored_count: 0,
    });
    getLines.mockResolvedValue([pendingSuggestedMatchLine]);

    render(<BankStatementWorkbench document={makeFallbackDocument()} />);

    await waitFor(() => expect(screen.getByText('Import summary')).toBeInTheDocument());
    expect(screen.getAllByText('Suggested match').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Suggested salary match').length).toBeGreaterThan(0);
    expect(screen.getAllByRole('button', { name: 'Match existing' }).length).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: 'View transaction' })).not.toBeInTheDocument();
  });

  it('unmatches a remote line back to pending review and clears the previous match candidate', async () => {
    const matchedLine = {
      id: 89,
      line_date: '2024-12-22',
      amount: '1200.00',
      counterparty: 'Salary GmbH',
      purpose: 'Payroll',
      raw_reference: 'Payroll',
      normalized_fingerprint: 'fp-2',
      review_status: 'matched_existing',
      suggested_action: 'match_existing',
      confidence_score: '0.82',
      linked_transaction_id: 2001,
      created_transaction_id: null,
      linked_transaction: {
        id: 2001,
        amount: '1200.00',
        transaction_date: '2024-12-22',
        description: 'Salary GmbH',
      },
      created_transaction: null,
    };
    const pendingLine = {
      ...matchedLine,
      review_status: 'pending_review',
      suggested_action: 'create_new',
      linked_transaction_id: null,
      linked_transaction: null,
    };

    initializeFromDocument.mockResolvedValue({
      id: 12,
      source_type: 'document',
      source_document_id: 326,
      bank_name: 'Magenta Bank',
      iban: 'AT602011183744980900',
      statement_period: {
        start: '2024-07-01',
        end: '2024-12-31',
      },
      tax_year: 2024,
      created_at: '2026-03-24T00:00:04Z',
      updated_at: '2026-03-24T00:00:04Z',
      total_count: 1,
      auto_created_count: 0,
      matched_existing_count: 1,
      pending_review_count: 0,
      ignored_count: 0,
    });
    getLines
      .mockResolvedValueOnce([matchedLine])
      .mockResolvedValueOnce([pendingLine]);
    getImport.mockResolvedValue({
      id: 12,
      source_type: 'document',
      source_document_id: 326,
      bank_name: 'Magenta Bank',
      iban: 'AT602011183744980900',
      statement_period: {
        start: '2024-07-01',
        end: '2024-12-31',
      },
      tax_year: 2024,
      created_at: '2026-03-24T00:00:04Z',
      updated_at: '2026-03-24T00:00:05Z',
      total_count: 1,
      auto_created_count: 0,
      matched_existing_count: 0,
      pending_review_count: 1,
      ignored_count: 0,
    });
    unmatchLine.mockResolvedValue({
      success: true,
      line: pendingLine,
    });

    render(<BankStatementWorkbench document={makeFallbackDocument()} />);

    await waitFor(() => expect(screen.getByText('Import summary')).toBeInTheDocument());
    fireEvent.click(screen.getAllByRole('button', { name: 'Unmatch' })[0]);

    await waitFor(() => expect(unmatchLine).toHaveBeenCalledWith(89));
    await waitFor(() => expect(getImport).toHaveBeenCalledWith(12));
    await waitFor(() => expect(screen.getAllByRole('button', { name: 'Create transaction' }).length).toBeGreaterThan(0));
    expect(screen.queryByRole('button', { name: 'Match existing' })).not.toBeInTheDocument();
  });
});
