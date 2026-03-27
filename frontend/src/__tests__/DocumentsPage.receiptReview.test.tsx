/* @vitest-environment jsdom */

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import DocumentsPage from '../pages/DocumentsPage';

const getDocument = vi.fn();
const getDocuments = vi.fn();
const downloadDocument = vi.fn();
const correctOCR = vi.fn();
const getById = vi.fn();
const updateTransaction = vi.fn();
const aiToast = vi.fn();

vi.mock('react-i18next', () => ({
  initReactI18next: {
    type: '3rdParty',
    init: () => undefined,
  },
  useTranslation: () => ({
    i18n: {
      language: 'en',
    },
    t: (key: string, fallback?: string | { defaultValue?: string }) => {
      const translations: Record<string, string> = {
        'documents.ocr.quantity': 'Qty',
        'documents.ocr.category': 'Category',
        'transactions.categories.maintenance': 'Maintenance',
        'transactions.categories.other': 'Other',
        'transactions.categories.fuel': 'Fuel',
      };
      if (typeof fallback === 'string') return fallback;
      if (translations[key]) return translations[key];
      if (fallback && typeof fallback === 'object' && typeof fallback.defaultValue === 'string') {
        return fallback.defaultValue;
      }
      return key;
    },
  }),
}));

vi.mock('../components/documents/DocumentUpload', () => ({ default: () => <div data-testid="doc-upload" /> }));
vi.mock('../components/documents/DocumentList', () => ({ default: () => <div data-testid="doc-list" /> }));
vi.mock('../components/documents/OCRReview', () => ({ default: () => <div data-testid="ocr-review" /> }));
vi.mock('../components/common/Select', () => ({
  default: ({ value, onChange, options = [], placeholder, ...props }: any) => (
    <select
      data-testid={props.id || props['aria-label'] || 'mock-select'}
      value={value || ''}
      onChange={(event) => onChange?.(event.target.value)}
      {...props}
    >
      {placeholder ? <option value="">{placeholder}</option> : null}
      {options.map((option: any) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  ),
}));
vi.mock('../components/documents/EmployerReviewPanel', () => ({ default: () => null }));
vi.mock('../components/documents/BescheidImport', () => ({ default: () => null }));
vi.mock('../components/documents/E1FormImport', () => ({ default: () => null }));
vi.mock('../components/documents/SuggestionCardFactory', () => ({
  default: (props: any) => (
    <div
      data-testid="suggestion-card"
      data-disabled={props.confirmDisabled ? 'true' : 'false'}
      data-disabled-reason={props.confirmDisabledReason || ''}
    >
      {props.confirmDisabledReason || 'suggestion-enabled'}
    </div>
  ),
}));
vi.mock('../documents/presentation/featureFlag', () => ({
  default: () => true,
}));

vi.mock('../services/documentService', () => ({
  documentService: {
    getDocuments: (...args: any[]) => getDocuments(...args),
    getDocument: (...args: any[]) => getDocument(...args),
    downloadDocument: (...args: any[]) => downloadDocument(...args),
    correctOCR: (...args: any[]) => correctOCR(...args),
  },
}));

vi.mock('../services/transactionService', () => ({
  transactionService: {
    getById: (...args: any[]) => getById(...args),
    update: (...args: any[]) => updateTransaction(...args),
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
      refreshProperties: vi.fn(),
      refreshRecurring: vi.fn(),
    }),
  },
}));

vi.mock('../stores/aiToastStore', () => ({
  aiToast: (...args: any[]) => aiToast(...args),
}));

function renderDocumentsPage() {
  return render(
    <MemoryRouter initialEntries={['/documents/101']}>
      <Routes>
        <Route path="/documents/:documentId" element={<DocumentsPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('DocumentsPage receipt review flow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.URL.createObjectURL = vi.fn(() => 'blob:test');
    global.URL.revokeObjectURL = vi.fn();
    getDocuments.mockResolvedValue([{ id: 101 }]);

    const documentDetail = {
      id: 101,
      user_id: 1,
      document_type: 'receipt',
      file_path: '/tmp/receipt.pdf',
      file_name: 'receipt.pdf',
      file_size: 100,
      mime_type: 'application/pdf',
      confidence_score: 0.92,
      needs_review: false,
      created_at: '2026-03-17T00:00:00Z',
      updated_at: '2026-03-17T00:00:00Z',
      ocr_result: {
        merchant: 'Billa',
        amount: 4.99,
        line_items: [
          {
            description: 'Druckerpapier A4',
            amount: 4.99,
            quantity: 1,
            vat_rate: 20,
            category: 'maintenance',
            is_deductible: true,
            deduction_reason: 'Office supplies',
          },
        ],
      },
    };

    getDocument
      .mockResolvedValueOnce(documentDetail)
      .mockResolvedValueOnce(documentDetail);
    downloadDocument.mockResolvedValue(new Blob(['pdf']));
    correctOCR.mockResolvedValue(documentDetail);
    getById.mockResolvedValue(null);
  });

  it('shows the expense review summary first and enters edit mode before saving', async () => {
    const { container } = renderDocumentsPage();

    await waitFor(() => expect(getDocument).toHaveBeenCalledWith(101));
    await waitFor(() => expect(container.querySelector('.receipt-review-name')?.textContent).toBe('Druckerpapier A4'));

    expect(container.querySelector('.receipt-review-card h5')).not.toBeNull();
    expect(container.querySelector('.receipt-review-summary')).not.toBeNull();
    expect(container.querySelector('.receipt-review-batch-actions')).not.toBeNull();
    expect(container.querySelector('.receipt-review-reason-input')).toBeNull();
    expect(container.querySelector('.receipt-review-meta')?.textContent).toContain('Maintenance');
    expect(container.querySelector('.receipt-review-meta')?.textContent).not.toContain('maintenance');

    const editButton = container.querySelector('.receipt-review-edit-btn') as HTMLButtonElement;
    fireEvent.click(editButton);

    const reasonInput = container.querySelector('.receipt-review-reason-input') as HTMLInputElement;
    expect(reasonInput).not.toBeNull();

    const toggleButtons = container.querySelectorAll('.receipt-review-toggle');
    expect(toggleButtons).toHaveLength(2);
    fireEvent.click(toggleButtons[1] as HTMLButtonElement);
    fireEvent.change(reasonInput, { target: { value: 'manual correction' } });
    fireEvent.click(container.querySelector('.receipt-review-actions .btn-primary') as HTMLButtonElement);

    await waitFor(() => expect(correctOCR).toHaveBeenCalledTimes(1));
    const correctedPayload = correctOCR.mock.calls[0][1];
    expect(correctedPayload.line_items[0].is_deductible).toBe(false);
    expect(correctedPayload.line_items[0].deduction_reason).toBe('manual correction');
  });

  it('keeps receipt-style review for income documents while hiding expense-only controls', async () => {
    const incomeDocumentDetail = {
      id: 101,
      user_id: 1,
      document_type: 'receipt',
      file_path: '/tmp/income-receipt.pdf',
      file_name: 'income-receipt.pdf',
      file_size: 100,
      mime_type: 'application/pdf',
      confidence_score: 0.92,
      needs_review: false,
      created_at: '2026-03-17T00:00:00Z',
      updated_at: '2026-03-17T00:00:00Z',
      ocr_result: {
        merchant: 'ACME Studio',
        amount: 299,
        _transaction_type: 'income',
        line_items: [
          {
            description: 'Projekt Rechnung',
            amount: 299,
            quantity: 1,
            vat_rate: 20,
            is_deductible: null,
            deduction_reason: '',
          },
        ],
      },
    };

    getDocument.mockReset();
    getDocument
      .mockResolvedValueOnce(incomeDocumentDetail)
      .mockResolvedValueOnce(incomeDocumentDetail);
    correctOCR.mockResolvedValue(incomeDocumentDetail);

    const { container } = renderDocumentsPage();

    await waitFor(() => expect(getDocument).toHaveBeenCalledWith(101));
    await waitFor(() => expect(container.querySelector('.receipt-review-name')?.textContent).toBe('Projekt Rechnung'));

    expect(container.querySelector('.receipt-review-card h5')).not.toBeNull();
    expect(container.querySelector('.receipt-review-summary')).toBeNull();
    expect(container.querySelector('.receipt-review-batch-actions')).toBeNull();
    expect(container.querySelector('.receipt-review-reason-input')).toBeNull();
    expect(container.querySelector('.receipt-review-reason-text')?.textContent).not.toBe('');

    const editButton = container.querySelector('.receipt-review-edit-btn') as HTMLButtonElement;
    fireEvent.click(editButton);

    expect(container.querySelectorAll('.receipt-review-toggle')).toHaveLength(0);
    expect(container.querySelector('.receipt-review-reason-input')).toBeNull();
    fireEvent.click(container.querySelector('.receipt-review-actions .btn-primary') as HTMLButtonElement);

    await waitFor(() => expect(correctOCR).toHaveBeenCalledTimes(1));
    const correctedPayload = correctOCR.mock.calls[0][1];
    expect(correctedPayload.line_items[0].description).toBe('Projekt Rechnung');
  });

  it('routes receipt family documents with needs_review=true into the receipt workbench instead of OCRReview', async () => {
    const reviewDocumentDetail = {
      id: 101,
      user_id: 1,
      document_type: 'receipt',
      file_path: '/tmp/review-receipt.pdf',
      file_name: 'review-receipt.pdf',
      file_size: 100,
      mime_type: 'application/pdf',
      confidence_score: 0.92,
      needs_review: true,
      created_at: '2026-03-17T00:00:00Z',
      updated_at: '2026-03-17T00:00:00Z',
      ocr_result: {
        merchant: 'Billa',
        amount: 4.99,
        _transaction_type: 'expense',
        commercial_document_semantics: 'receipt',
        line_items: [
          {
            description: 'Review Receipt Item',
            amount: 4.99,
            quantity: 1,
            vat_rate: 20,
            is_deductible: true,
            deduction_reason: 'Office supplies',
          },
        ],
      },
    };

    getDocument.mockReset();
    getDocument
      .mockResolvedValueOnce(reviewDocumentDetail)
      .mockResolvedValueOnce(reviewDocumentDetail);

    const { container } = renderDocumentsPage();

    await waitFor(() => expect(getDocument).toHaveBeenCalledWith(101));
    await waitFor(() => expect(container.querySelector('.receipt-review-name')?.textContent).toBe('Review Receipt Item'));

    expect(screen.queryByTestId('ocr-review')).toBeNull();
    expect(container.querySelector('.receipt-breakdown-card')).not.toBeNull();
  });

  it('lets users expand and collapse individual receipts in multi-receipt documents', async () => {
    const multiReceiptDocumentDetail = {
      id: 101,
      user_id: 1,
      document_type: 'receipt',
      file_path: '/tmp/multi-receipt.pdf',
      file_name: 'multi-receipt.pdf',
      file_size: 100,
      mime_type: 'application/pdf',
      confidence_score: 0.92,
      needs_review: false,
      created_at: '2026-03-17T00:00:00Z',
      updated_at: '2026-03-17T00:00:00Z',
      ocr_result: {
        merchant: 'BRUNN',
        amount: 225.6,
        date: '2024-07-25',
        line_items: [
          {
            description: 'Primary receipt item',
            amount: 225.6,
            quantity: 1,
            category: 'other',
            is_deductible: false,
          },
        ],
        _additional_receipts: [
          {
            merchant: 'Hornbach',
            amount: 35.98,
            date: '2024-11-26',
            line_items: [
              {
                description: 'Second receipt item',
                amount: 35.98,
                quantity: 1,
                category: 'maintenance',
                is_deductible: true,
              },
            ],
          },
          {
            merchant: 'Billa',
            amount: 12.5,
            date: '2024-12-10',
            line_items: [
              {
                description: 'Third receipt item',
                amount: 12.5,
                quantity: 1,
                category: 'other',
                is_deductible: false,
              },
            ],
          },
        ],
      },
    };

    getDocument.mockReset();
    getDocument
      .mockResolvedValueOnce(multiReceiptDocumentDetail)
      .mockResolvedValueOnce(multiReceiptDocumentDetail);
    correctOCR.mockResolvedValue(multiReceiptDocumentDetail);

    const { container } = renderDocumentsPage();

    await waitFor(() => expect(getDocument).toHaveBeenCalledWith(101));
    await waitFor(() => expect(container.querySelectorAll('.receipt-breakdown-card')).toHaveLength(3));

    expect(screen.queryAllByText('Primary receipt item')).toHaveLength(0);
    expect(screen.queryAllByText('Second receipt item')).toHaveLength(0);
    expect(screen.queryAllByText('Third receipt item')).toHaveLength(0);

    const toggleButtons = container.querySelectorAll('.receipt-breakdown-toggle-btn');
    expect(toggleButtons).toHaveLength(3);

    fireEvent.click(toggleButtons[1] as HTMLButtonElement);
    await waitFor(() => expect(screen.queryAllByText('Second receipt item').length).toBeGreaterThan(0));

    fireEvent.click(toggleButtons[1] as HTMLButtonElement);
    await waitFor(() => expect(screen.queryAllByText('Second receipt item')).toHaveLength(0));
  });

  it('keeps proforma receipts in the workbench while disabling suggestion actions and hiding expense quick actions', async () => {
    const proformaDocumentDetail = {
      id: 101,
      user_id: 1,
      document_type: 'receipt',
      file_path: '/tmp/proforma.pdf',
      file_name: 'proforma.pdf',
      file_size: 100,
      mime_type: 'application/pdf',
      confidence_score: 0.92,
      needs_review: false,
      created_at: '2026-03-17T00:00:00Z',
      updated_at: '2026-03-17T00:00:00Z',
      ocr_result: {
        merchant: 'ACME Supplies',
        amount: 129.5,
        _transaction_type: 'expense',
        commercial_document_semantics: 'proforma',
        line_items: [
          {
            description: 'Proforma Item',
            amount: 129.5,
            quantity: 1,
            vat_rate: 20,
            is_deductible: null,
            deduction_reason: '',
          },
        ],
        import_suggestion: {
          type: 'create_property',
          status: 'pending',
          data: { address: 'Wien 1010' },
        },
      },
    };

    getDocument.mockReset();
    getDocument
      .mockResolvedValueOnce(proformaDocumentDetail)
      .mockResolvedValueOnce(proformaDocumentDetail);

    const { container } = renderDocumentsPage();

    await waitFor(() => expect(getDocument).toHaveBeenCalledWith(101));
    await waitFor(() => expect(container.querySelector('.receipt-review-name')?.textContent).toBe('Proforma Item'));

    expect(container.querySelector('.receipt-review-batch-actions')).toBeNull();
    expect(container.querySelector('.receipt-review-summary')).toBeNull();
    expect(screen.getByTestId('suggestion-card')).toHaveAttribute('data-disabled', 'true');
    expect(screen.getByTestId('suggestion-card').getAttribute('data-disabled-reason')).toContain('proforma');
  });

  it('shows category editing in the receipt workbench and syncs the chosen category to the linked transaction', async () => {
    const linkedTransaction = {
      id: 77,
      type: 'expense',
      amount: 68.32,
      date: '2024-10-03',
      description: 'Eni Service-Station',
      category: 'other',
      is_deductible: false,
      line_items: [
        {
          description: 'Diesel fuel purchase',
          amount: 68.32,
          quantity: 1,
          category: 'other',
          is_deductible: false,
          deduction_reason: 'Initial guess',
          sort_order: 0,
        },
      ],
    };

    const documentDetail = {
      id: 101,
      user_id: 1,
      transaction_id: 77,
      linked_transactions: [
        {
          transaction_id: 77,
          description: 'Eni Service-Station',
          amount: 68.32,
          date: '2024-10-03',
          has_line_items: true,
        },
      ],
      document_type: 'receipt',
      file_path: '/tmp/fuel-receipt.pdf',
      file_name: 'fuel-receipt.pdf',
      file_size: 100,
      mime_type: 'application/pdf',
      confidence_score: 0.92,
      needs_review: false,
      created_at: '2026-03-17T00:00:00Z',
      updated_at: '2026-03-17T00:00:00Z',
      ocr_result: {
        merchant: 'Eni Service-Station',
        amount: 68.32,
        _transaction_type: 'expense',
        line_items: [
          {
            description: 'Diesel fuel purchase',
            amount: 68.32,
            quantity: 1,
            category: 'other',
            is_deductible: false,
            deduction_reason: 'Initial guess',
          },
        ],
      },
    };

    getDocument.mockReset();
    getDocument.mockResolvedValue(documentDetail);
    getById.mockResolvedValue(linkedTransaction);
    correctOCR.mockResolvedValue(documentDetail);
    updateTransaction.mockResolvedValue({
      ...linkedTransaction,
      category: 'fuel',
      line_items: [
        {
          ...linkedTransaction.line_items[0],
          category: 'fuel',
        },
      ],
    });

    const { container } = renderDocumentsPage();

    await waitFor(() => expect(getDocument).toHaveBeenCalledWith(101));
    await waitFor(() => expect(getById).toHaveBeenCalledWith(77));
    await waitFor(() => expect(container.querySelector('.receipt-review-category-value')?.textContent).toContain('Other'));
    expect(screen.getByTestId('receipt-category-0')).toBeDisabled();
    expect(screen.getByTestId('receipt-item-category-0-0')).toBeDisabled();

    fireEvent.click(container.querySelector('.receipt-review-edit-btn') as HTMLButtonElement);

    const receiptCategorySelect = screen.getByTestId('receipt-category-0') as HTMLSelectElement;
    const lineItemCategorySelect = screen.getByTestId('receipt-item-category-0-0') as HTMLSelectElement;
    expect(receiptCategorySelect).not.toBeDisabled();
    expect(lineItemCategorySelect).not.toBeDisabled();

    fireEvent.change(receiptCategorySelect, { target: { value: 'fuel' } });
    fireEvent.change(lineItemCategorySelect, { target: { value: 'fuel' } });
    fireEvent.click(container.querySelector('.receipt-review-actions .btn-primary') as HTMLButtonElement);

    await waitFor(() => expect(updateTransaction).toHaveBeenCalledTimes(1));

    const transactionPayload = updateTransaction.mock.calls[0][1];
    expect(transactionPayload.type).toBe('expense');
    expect(transactionPayload.category).toBe('fuel');
    expect(transactionPayload.suppress_rule_learning).toBe(true);
    expect(transactionPayload.line_items[0].category).toBe('fuel');
    expect(correctOCR).toHaveBeenCalledTimes(1);
    expect(correctOCR.mock.calls[0][1].line_items[0].category).toBe('fuel');
  });

  it('switches a linked receipt from expense to income and clears deductibility before syncing', async () => {
    const linkedTransaction = {
      id: 91,
      type: 'expense',
      amount: 299,
      date: '2024-10-03',
      description: 'ACME Studio Invoice',
      category: 'professional_services',
      is_deductible: true,
      line_items: [
        {
          description: 'Projekt Rechnung',
          amount: 299,
          quantity: 1,
          category: 'professional_services',
          is_deductible: true,
          deduction_reason: 'Initial guess',
          sort_order: 0,
        },
      ],
    };

    const documentDetail = {
      id: 101,
      user_id: 1,
      transaction_id: 91,
      linked_transactions: [
        {
          transaction_id: 91,
          description: 'ACME Studio Invoice',
          amount: 299,
          date: '2024-10-03',
          has_line_items: true,
        },
      ],
      document_type: 'invoice',
      file_path: '/tmp/income-invoice.pdf',
      file_name: 'income-invoice.pdf',
      file_size: 100,
      mime_type: 'application/pdf',
      confidence_score: 0.92,
      needs_review: false,
      created_at: '2026-03-17T00:00:00Z',
      updated_at: '2026-03-17T00:00:00Z',
      ocr_result: {
        merchant: 'ACME Studio',
        amount: 299,
        _transaction_type: 'expense',
        line_items: [
          {
            description: 'Projekt Rechnung',
            amount: 299,
            quantity: 1,
            category: 'professional_services',
            is_deductible: true,
            deduction_reason: 'Initial guess',
          },
        ],
      },
    };

    getDocument.mockReset();
    getDocument.mockResolvedValue(documentDetail);
    getById.mockResolvedValue(linkedTransaction);
    correctOCR.mockResolvedValue(documentDetail);
    updateTransaction.mockResolvedValue({
      ...linkedTransaction,
      type: 'income',
      category: 'business',
      is_deductible: false,
      line_items: [
        {
          ...linkedTransaction.line_items[0],
          category: 'business',
          is_deductible: false,
          deduction_reason: undefined,
        },
      ],
    });

    const { container } = renderDocumentsPage();

    await waitFor(() => expect(getDocument).toHaveBeenCalledWith(101));
    await waitFor(() => expect(getById).toHaveBeenCalledWith(91));

    fireEvent.click(container.querySelector('.receipt-review-edit-btn') as HTMLButtonElement);
    fireEvent.click(screen.getAllByText('Income')[0] as HTMLButtonElement);

    const receiptCategorySelect = screen.getByTestId('receipt-category-0') as HTMLSelectElement;
    expect(receiptCategorySelect.value).toBe('');
    fireEvent.change(receiptCategorySelect, { target: { value: 'business' } });
    fireEvent.click(container.querySelector('.receipt-review-actions .btn-primary') as HTMLButtonElement);

    await waitFor(() => expect(updateTransaction).toHaveBeenCalledTimes(1));

    const correctedPayload = correctOCR.mock.calls[0][1];
    expect(correctedPayload._transaction_type).toBe('income');
    expect(correctedPayload.line_items[0].is_deductible).toBe(false);
    expect(correctedPayload.line_items[0].deduction_reason).toBeUndefined();

    const transactionPayload = updateTransaction.mock.calls[0][1];
    expect(transactionPayload.type).toBe('income');
    expect(transactionPayload.category).toBe('business');
    expect(transactionPayload.is_deductible).toBe(false);
    expect(transactionPayload.deduction_reason).toBeUndefined();
    expect(transactionPayload.line_items[0].category).toBe('business');
    expect(transactionPayload.line_items[0].is_deductible).toBe(false);
  });

  it('labels linked income line items as income details', async () => {
    const linkedTransaction = {
      id: 333,
      type: 'income',
      amount: 3500,
      date: '2024-10-03',
      description: 'Consulting income',
      category: 'business',
      is_deductible: false,
      line_items: [
        {
          description: 'Consulting income',
          amount: 3500,
          quantity: 1,
          category: 'business',
          is_deductible: false,
          sort_order: 0,
        },
      ],
    };

    const documentDetail = {
      id: 101,
      user_id: 1,
      transaction_id: 333,
      linked_transactions: [
        {
          transaction_id: 333,
          description: 'Consulting income',
          amount: 3500,
          date: '2024-10-03',
          has_line_items: true,
        },
      ],
      document_type: 'invoice',
      file_path: '/tmp/income-invoice.pdf',
      file_name: 'income-invoice.pdf',
      file_size: 100,
      mime_type: 'application/pdf',
      confidence_score: 0.92,
      needs_review: false,
      created_at: '2026-03-17T00:00:00Z',
      updated_at: '2026-03-17T00:00:00Z',
      ocr_result: {
        merchant: 'ACME Studio',
        amount: 3500,
        _transaction_type: 'income',
        line_items: [
          {
            description: 'Consulting income',
            amount: 3500,
            quantity: 1,
            category: 'business',
            is_deductible: false,
          },
        ],
      },
    };

    getDocument.mockReset();
    getDocument.mockResolvedValue(documentDetail);
    getById.mockResolvedValue(linkedTransaction);

    renderDocumentsPage();

    await waitFor(() => expect(getDocument).toHaveBeenCalledWith(101));
    await waitFor(() => expect(getById).toHaveBeenCalledWith(333));

    fireEvent.click(screen.getByRole('button', { name: 'Expand details' }));

    expect(screen.getAllByText('Income details').length).toBeGreaterThan(1);
    expect(screen.queryByText('Linked')).not.toBeInTheDocument();
  });

  it('prefers final transaction type over stale OCR direction when rendering receipt-family documents', async () => {
    const linkedTransaction = {
      id: 1726,
      type: 'income',
      amount: 96,
      date: '2024-01-02',
      description: 'Invoice from Notion Labs Inc. (#INV-NOT-2024-AT-8812)',
      category: 'other_income',
      is_deductible: false,
      line_items: [
        {
          description: 'Notion Plus Plan — Annual (Jan–Dec 2024)',
          amount: 96,
          quantity: 1,
          category: 'other_income',
          is_deductible: false,
          sort_order: 0,
        },
      ],
    };

    const documentDetail = {
      id: 101,
      user_id: 1,
      transaction_id: 1726,
      linked_transactions: [
        {
          transaction_id: 1726,
          description: 'Invoice from Notion Labs Inc. (#INV-NOT-2024-AT-8812)',
          amount: 96,
          date: '2024-01-02',
          has_line_items: true,
        },
      ],
      document_type: 'invoice',
      file_path: '/tmp/notion.pdf',
      file_name: 'A13_Notion_SaaS_Annual.pdf',
      file_size: 100,
      mime_type: 'application/pdf',
      confidence_score: 0.95,
      needs_review: false,
      created_at: '2026-03-26T00:00:00Z',
      updated_at: '2026-03-26T00:00:00Z',
      ocr_result: {
        merchant: 'Notion Labs Inc.',
        amount: 96,
        final_transaction_type: 'income',
        final_transaction_type_source: 'linked_transaction',
        _transaction_type: 'expense',
        document_transaction_direction: 'expense',
        line_items: [
          {
            description: 'Notion Plus Plan — Annual (Jan–Dec 2024)',
            amount: 96,
            quantity: 1,
            category: 'other_income',
            is_deductible: false,
          },
        ],
      },
    };

    getDocument.mockReset();
    getDocument.mockResolvedValue(documentDetail);
    getById.mockResolvedValue(linkedTransaction);

    const { container } = renderDocumentsPage();

    await waitFor(() => expect(getDocument).toHaveBeenCalledWith(101));
    await waitFor(() => expect(getById).toHaveBeenCalledWith(1726));
    await waitFor(() => expect(container.querySelector('.receipt-review-card h5')).not.toBeNull());

    expect(screen.queryByText('Expense')).toBeNull();
    expect(screen.getAllByText('Income')[0]).toBeInTheDocument();
  });

  it('preserves unit amounts when switching a multi-quantity linked invoice from income to expense', async () => {
    const linkedTransaction = {
      id: 1333,
      type: 'income',
      amount: 876.46,
      date: '2024-03-31',
      description: 'Consulting invoice',
      category: 'business',
      is_deductible: false,
      line_items: [
        {
          description: 'Workshop package',
          amount: 438.23,
          quantity: 2,
          category: 'business',
          is_deductible: false,
          sort_order: 0,
        },
      ],
    };

    const documentDetail = {
      id: 101,
      user_id: 1,
      transaction_id: 1333,
      linked_transactions: [
        {
          transaction_id: 1333,
          description: 'Consulting invoice',
          amount: 876.46,
          date: '2024-03-31',
          has_line_items: true,
        },
      ],
      document_type: 'invoice',
      file_path: '/tmp/consulting-invoice.pdf',
      file_name: 'consulting-invoice.pdf',
      file_size: 100,
      mime_type: 'application/pdf',
      confidence_score: 0.92,
      needs_review: false,
      created_at: '2026-03-17T00:00:00Z',
      updated_at: '2026-03-17T00:00:00Z',
      ocr_result: {
        merchant: 'Consulting Vendor',
        amount: 876.46,
        _transaction_type: 'income',
        line_items: [
          {
            description: 'Workshop package',
            amount: 876.46,
            quantity: 2,
            category: 'business',
            is_deductible: false,
          },
        ],
      },
    };

    getDocument.mockReset();
    getDocument.mockResolvedValue(documentDetail);
    getById.mockResolvedValue(linkedTransaction);
    correctOCR.mockResolvedValue(documentDetail);
    updateTransaction.mockResolvedValue({
      ...linkedTransaction,
      type: 'expense',
      category: 'professional_services',
    });

    const { container } = renderDocumentsPage();

    await waitFor(() => expect(getDocument).toHaveBeenCalledWith(101));
    await waitFor(() => expect(getById).toHaveBeenCalledWith(1333));

    fireEvent.click(container.querySelector('.receipt-review-edit-btn') as HTMLButtonElement);
    fireEvent.click(screen.getAllByText('Expense')[0] as HTMLButtonElement);

    const receiptCategorySelect = screen.getByTestId('receipt-category-0') as HTMLSelectElement;
    fireEvent.change(receiptCategorySelect, { target: { value: 'professional_services' } });
    fireEvent.click(container.querySelector('.receipt-review-actions .btn-primary') as HTMLButtonElement);

    await waitFor(() => expect(updateTransaction).toHaveBeenCalledTimes(1));

    const transactionPayload = updateTransaction.mock.calls[0][1];
    expect(transactionPayload.type).toBe('expense');
    expect(transactionPayload.category).toBe('professional_services');
    expect(transactionPayload.line_items[0].amount).toBe(438.23);
    expect(transactionPayload.line_items[0].quantity).toBe(2);
  });

  it('allocates invoice VAT when syncing net line items to a linked transaction', async () => {
    const linkedTransaction = {
      id: 1483,
      type: 'expense',
      amount: 14640,
      date: '2024-03-31',
      description: 'Invoice from DI Maria Steiner',
      category: 'professional_services',
      is_deductible: true,
      line_items: [
        {
          description: 'IT-Beratung Softwarearchitektur (Jan-Mar 2024 120 Std.)',
          amount: 10200,
          quantity: 1,
          category: 'professional_services',
          is_deductible: true,
          deduction_reason: 'Initial guess',
          sort_order: 0,
        },
        {
          description: 'Workshop Anforderungsanalyse (2 Tage)',
          amount: 2000,
          quantity: 1,
          category: 'professional_services',
          is_deductible: true,
          deduction_reason: 'Initial guess',
          sort_order: 1,
        },
      ],
    };

    const documentDetail = {
      id: 101,
      user_id: 1,
      transaction_id: 1483,
      linked_transactions: [
        {
          transaction_id: 1483,
          description: 'Invoice from DI Maria Steiner',
          amount: 14640,
          date: '2024-03-31',
          has_line_items: true,
        },
      ],
      document_type: 'invoice',
      file_path: '/tmp/service-invoice.pdf',
      file_name: 'service-invoice.pdf',
      file_size: 100,
      mime_type: 'application/pdf',
      confidence_score: 0.92,
      needs_review: false,
      created_at: '2026-03-17T00:00:00Z',
      updated_at: '2026-03-17T00:00:00Z',
      ocr_result: {
        merchant: 'DI Maria Steiner',
        amount: 14640,
        vat_amount: 2440,
        vat_rate: 20,
        _transaction_type: 'expense',
        line_items: [
          {
            description: 'IT-Beratung Softwarearchitektur (Jan-Mar 2024 120 Std.)',
            amount: 10200,
            quantity: 1,
            category: 'professional_services',
            is_deductible: true,
          },
          {
            description: 'Workshop Anforderungsanalyse (2 Tage)',
            amount: 2000,
            quantity: 1,
            category: 'professional_services',
            is_deductible: true,
          },
        ],
      },
    };

    getDocument.mockReset();
    getDocument.mockResolvedValue(documentDetail);
    getById.mockResolvedValue(linkedTransaction);
    correctOCR.mockResolvedValue(documentDetail);
    updateTransaction.mockResolvedValue(linkedTransaction);

    const { container } = renderDocumentsPage();

    await waitFor(() => expect(getDocument).toHaveBeenCalledWith(101));
    await waitFor(() => expect(getById).toHaveBeenCalledWith(1483));
    fireEvent.click(container.querySelector('.receipt-review-edit-btn') as HTMLButtonElement);
    fireEvent.click(container.querySelector('.receipt-review-actions .btn-primary') as HTMLButtonElement);

    await waitFor(() => expect(updateTransaction).toHaveBeenCalledTimes(1));
    const transactionPayload = updateTransaction.mock.calls[0][1];
    expect(transactionPayload.vat_amount).toBe(2440);
    expect(transactionPayload.line_items[0].amount).toBe(10200);
    expect(transactionPayload.line_items[0].vat_amount).toBe(2040);
    expect(transactionPayload.line_items[0].vat_recoverable_amount).toBe(2040);
    expect(transactionPayload.line_items[1].amount).toBe(2000);
    expect(transactionPayload.line_items[1].vat_amount).toBe(400);
    expect(transactionPayload.line_items[1].vat_recoverable_amount).toBe(400);
  });

  it('explains when the OCR save succeeded but linked transaction sync is blocked by a VAT mismatch', async () => {
    const linkedTransaction = {
      id: 1483,
      type: 'expense',
      amount: 14640,
      date: '2024-03-31',
      description: 'Invoice from DI Maria Steiner',
      category: 'professional_services',
      is_deductible: true,
      line_items: [
        {
          description: 'IT-Beratung Softwarearchitektur (Jan-Mar 2024 120 Std.)',
          amount: 10200,
          quantity: 1,
          category: 'professional_services',
          is_deductible: true,
          sort_order: 0,
        },
        {
          description: 'Workshop Anforderungsanalyse (2 Tage)',
          amount: 2000,
          quantity: 1,
          category: 'professional_services',
          is_deductible: true,
          sort_order: 1,
        },
      ],
    };

    const documentDetail = {
      id: 101,
      user_id: 1,
      transaction_id: 1483,
      linked_transactions: [
        {
          transaction_id: 1483,
          description: 'Invoice from DI Maria Steiner',
          amount: 14640,
          date: '2024-03-31',
          has_line_items: true,
        },
      ],
      document_type: 'invoice',
      file_path: '/tmp/service-invoice.pdf',
      file_name: 'service-invoice.pdf',
      file_size: 100,
      mime_type: 'application/pdf',
      confidence_score: 0.92,
      needs_review: false,
      created_at: '2026-03-17T00:00:00Z',
      updated_at: '2026-03-17T00:00:00Z',
      ocr_result: {
        merchant: 'DI Maria Steiner',
        amount: 14640,
        vat_amount: 2440,
        vat_rate: 20,
        _transaction_type: 'expense',
        line_items: [
          {
            description: 'IT-Beratung Softwarearchitektur (Jan-Mar 2024 120 Std.)',
            amount: 10200,
            quantity: 1,
            category: 'professional_services',
            is_deductible: true,
          },
          {
            description: 'Workshop Anforderungsanalyse (2 Tage)',
            amount: 2000,
            quantity: 1,
            category: 'professional_services',
            is_deductible: true,
          },
        ],
      },
    };

    getDocument.mockReset();
    getDocument.mockResolvedValue(documentDetail);
    getById.mockResolvedValue(linkedTransaction);
    correctOCR.mockResolvedValue(documentDetail);
    updateTransaction.mockRejectedValue({
      response: {
        data: {
          error: {
            message: 'An unexpected error occurred: ValueError: Line items do not reconcile with the parent amount. Expected 14640.00, reconstructed 12200.00.',
          },
        },
      },
      message: 'Request failed with status code 500',
    });

    const { container } = renderDocumentsPage();

    await waitFor(() => expect(getDocument).toHaveBeenCalledWith(101));
    await waitFor(() => expect(getById).toHaveBeenCalledWith(1483));
    fireEvent.click(container.querySelector('.receipt-review-edit-btn') as HTMLButtonElement);
    fireEvent.click(container.querySelector('.receipt-review-actions .btn-primary') as HTMLButtonElement);

    await waitFor(() => expect(updateTransaction).toHaveBeenCalledTimes(1));
    await waitFor(() => {
      expect(container.querySelector('.receipt-review-result.error')?.textContent)
        .toContain('Document details were saved, but the linked transaction was not updated.');
    });
    expect(container.querySelector('.receipt-review-result.error')?.textContent)
      .toContain('The invoice total');
    expect(container.querySelector('.receipt-review-result.error')?.textContent)
      .toContain('€14,640.00');
    expect(container.querySelector('.receipt-review-result.error')?.textContent)
      .toContain('€12,200.00');
    expect(aiToast).toHaveBeenCalledWith(
      expect.stringContaining('Document details were saved, but the linked transaction was not updated.'),
      'error',
    );
  });
});
