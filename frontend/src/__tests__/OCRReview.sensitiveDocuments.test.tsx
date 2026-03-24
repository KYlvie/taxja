/* @vitest-environment jsdom */

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

import OCRReview from '../components/documents/OCRReview';

const getDocument = vi.fn();
const getDocumentForReview = vi.fn();
const downloadDocument = vi.fn();
const retryOcr = vi.fn();
const confirmTaxData = vi.fn();
const correctOCR = vi.fn();
const confirmOCR = vi.fn();

vi.mock('react-i18next', () => ({
  initReactI18next: {
    type: '3rdParty',
    init: () => {},
  },
  useTranslation: () => ({
    t: (key: string, fallback?: string | { defaultValue?: string }) => {
      if (typeof fallback === 'string') return fallback;
      if (fallback && typeof fallback === 'object' && typeof fallback.defaultValue === 'string') {
        return fallback.defaultValue;
      }
      return key;
    },
    i18n: {
      language: 'zh',
    },
  }),
}));

vi.mock('../services/documentService', () => ({
  documentService: {
    getDocument: (...args: any[]) => getDocument(...args),
    getDocumentForReview: (...args: any[]) => getDocumentForReview(...args),
    downloadDocument: (...args: any[]) => downloadDocument(...args),
    retryOcr: (...args: any[]) => retryOcr(...args),
    confirmTaxData: (...args: any[]) => confirmTaxData(...args),
    correctOCR: (...args: any[]) => correctOCR(...args),
    confirmOCR: (...args: any[]) => confirmOCR(...args),
  },
}));

vi.mock('../stores/refreshStore', () => ({
  useRefreshStore: {
    getState: () => ({
      refreshRecurring: vi.fn(),
      refreshProperties: vi.fn(),
      refreshTransactions: vi.fn(),
    }),
  },
}));

vi.mock('../stores/aiToastStore', () => ({
  aiToast: vi.fn(),
}));

vi.mock('../components/documents/BescheidImport', () => ({
  default: () => null,
}));

describe('OCRReview sensitive document panels', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    downloadDocument.mockResolvedValue(new Blob(['pdf']));
    correctOCR.mockResolvedValue({});
    confirmOCR.mockResolvedValue({});
    global.URL.createObjectURL = vi.fn(() => 'blob:test');
    global.URL.revokeObjectURL = vi.fn();
  });

  it('shows a confirm action for pending generic review documents', async () => {
    getDocumentForReview.mockResolvedValueOnce({
      document: {
        id: 300,
        user_id: 7,
        document_type: 'receipt',
        file_path: '/tmp/pending-receipt.pdf',
        file_name: 'pending-receipt.pdf',
        file_size: 1000,
        mime_type: 'application/pdf',
        confidence_score: 0.42,
        needs_review: true,
        created_at: '2026-03-20T00:00:00Z',
        updated_at: '2026-03-20T00:00:00Z',
        raw_text: '',
        ocr_result: {},
      },
      extracted_data: {
        amount: 18.5,
        date: '2026-03-01',
        merchant: 'Billa',
        confidence: {},
      },
      suggestions: [],
    });

    render(
      <MemoryRouter>
        <OCRReview documentId={300} />
      </MemoryRouter>
    );

    await waitFor(() => expect(getDocumentForReview).toHaveBeenCalledWith(300));
    expect(screen.getByRole('button', { name: 'Confirm' })).toBeInTheDocument();
  });

  it('uses persisted confirmation state from ocr_result for the primary action', async () => {
    getDocumentForReview.mockResolvedValueOnce({
      document: {
        id: 304,
        user_id: 7,
        document_type: 'svs_notice',
        file_path: '/tmp/svs-confirmed.pdf',
        file_name: 'svs-confirmed.pdf',
        file_size: 1000,
        mime_type: 'application/pdf',
        confidence_score: 0.95,
        needs_review: false,
        created_at: '2026-03-20T00:00:00Z',
        updated_at: '2026-03-20T00:00:00Z',
        raw_text: '',
        ocr_result: {
          confirmed: true,
          confirmed_at: '2026-03-23T22:35:01.536798',
          confirmed_by: 46,
        },
      },
      extracted_data: {
        tax_year: 2024,
        taxpayer_name: 'Mag. Eva Wimmer',
        confidence: {},
      },
      suggestions: [],
    });

    render(
      <MemoryRouter>
        <OCRReview documentId={304} />
      </MemoryRouter>
    );

    await waitFor(() => expect(getDocumentForReview).toHaveBeenCalledWith(304));

    const saveButton = screen.getByRole('button', { name: 'Save' });
    expect(saveButton).toBeInTheDocument();

    fireEvent.click(saveButton);

    await waitFor(() => expect(correctOCR).toHaveBeenCalledTimes(1));
    expect(confirmOCR).not.toHaveBeenCalled();
  });

  it('renders borrower-only role controls for loan contracts', async () => {
    getDocumentForReview.mockResolvedValueOnce({
      document: {
        id: 301,
        user_id: 7,
        document_type: 'loan_contract',
        file_path: '/tmp/loan.pdf',
        file_name: 'loan.pdf',
        file_size: 1000,
        mime_type: 'application/pdf',
        confidence_score: 0.84,
        needs_review: false,
        created_at: '2026-03-20T00:00:00Z',
        updated_at: '2026-03-20T00:00:00Z',
        raw_text: '',
        ocr_result: {
          user_contract_role: 'borrower',
          contract_role_resolution: {
            candidate: 'borrower',
            confidence: 0.9,
            source: 'party_name_match',
            evidence: ['Matched borrower name with current user.'],
            strict_would_block: false,
          },
        },
      },
      extracted_data: {
        loan_amount: 250000,
        interest_rate: 3.2,
        user_contract_role: 'borrower',
        confidence: {},
      },
      suggestions: [],
    });

    render(
      <MemoryRouter>
        <OCRReview documentId={301} />
      </MemoryRouter>
    );

    await waitFor(() => expect(getDocumentForReview).toHaveBeenCalledWith(301));
    expect(screen.getByText('我的身份')).toBeInTheDocument();
    expect(screen.getByDisplayValue('我是借款方')).toBeInTheDocument();
    expect(screen.getByText('Matched borrower name with current user.')).toBeInTheDocument();
  });

  it('renders policy-holder role controls for insurance documents', async () => {
    getDocumentForReview.mockResolvedValueOnce({
      document: {
        id: 302,
        user_id: 7,
        document_type: 'versicherungsbestaetigung',
        file_path: '/tmp/insurance.pdf',
        file_name: 'insurance.pdf',
        file_size: 1000,
        mime_type: 'application/pdf',
        confidence_score: 0.8,
        needs_review: false,
        created_at: '2026-03-20T00:00:00Z',
        updated_at: '2026-03-20T00:00:00Z',
        raw_text: '',
        ocr_result: {
          user_contract_role: 'policy_holder',
          contract_role_resolution: {
            candidate: 'policy_holder',
            confidence: 0.88,
            source: 'party_name_match',
            evidence: ['Matched insured party with current user.'],
            strict_would_block: false,
          },
        },
      },
      extracted_data: {
        praemie: 120,
        insurance_type: 'health',
        user_contract_role: 'policy_holder',
        confidence: {},
      },
      suggestions: [],
    });

    render(
      <MemoryRouter>
        <OCRReview documentId={302} />
      </MemoryRouter>
    );

    await waitFor(() => expect(getDocumentForReview).toHaveBeenCalledWith(302));
    expect(screen.getByDisplayValue('我是投保方')).toBeInTheDocument();
    expect(screen.getByText('Matched insured party with current user.')).toBeInTheDocument();
  });

  it('keeps transaction type controls alongside invoice semantics guidance', async () => {
    getDocumentForReview.mockResolvedValueOnce({
      document: {
        id: 303,
        user_id: 7,
        document_type: 'invoice',
        file_path: '/tmp/invoice.pdf',
        file_name: 'invoice.pdf',
        file_size: 1000,
        mime_type: 'application/pdf',
        confidence_score: 0.71,
        needs_review: false,
        created_at: '2026-03-20T00:00:00Z',
        updated_at: '2026-03-20T00:00:00Z',
        raw_text: '',
        ocr_result: {
          document_transaction_direction: 'unknown',
          commercial_document_semantics: 'proforma',
          transaction_direction_resolution: {
            candidate: 'unknown',
            confidence: 0.42,
            source: 'manual_override',
            evidence: ['Detected the word Proforma in the document text.'],
            semantics: 'proforma',
            is_reversal: false,
            strict_would_block: true,
          },
        },
      },
      extracted_data: {
        amount: 900,
        date: '2026-03-01',
        merchant: 'Cloud Vendor GmbH',
        document_transaction_direction: 'unknown',
        commercial_document_semantics: 'proforma',
        confidence: {},
      },
      suggestions: [],
    });

    render(
      <MemoryRouter>
        <OCRReview documentId={303} />
      </MemoryRouter>
    );

    await waitFor(() => expect(getDocumentForReview).toHaveBeenCalledWith(303));
    expect(screen.getByText('documents.review.transactionType')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'transactions.types.income' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'transactions.types.expense' })).toBeInTheDocument();
    expect(screen.getByText(/保留原来的“发票”文档类型/)).toBeInTheDocument();
    expect(screen.getByText('单据语义（附加分类）')).toBeInTheDocument();
    expect(screen.getByText('单据方向与场景判断')).toBeInTheDocument();
    expect(screen.getAllByText('暂不确定').length).toBeGreaterThan(0);
    expect(screen.getAllByText('形式发票').length).toBeGreaterThan(0);
    expect(screen.getByText('Detected the word Proforma in the document text.')).toBeInTheDocument();
    expect(screen.getByText(/真正进账的收入\/支出仍由上方的交易类型决定/)).toBeInTheDocument();
  });

  it('keeps receipt semantics additive for receipt documents', async () => {
    getDocumentForReview.mockResolvedValueOnce({
      document: {
        id: 304,
        user_id: 7,
        document_type: 'receipt',
        file_path: '/tmp/receipt.pdf',
        file_name: 'receipt.pdf',
        file_size: 1000,
        mime_type: 'application/pdf',
        confidence_score: 0.88,
        needs_review: false,
        created_at: '2026-03-20T00:00:00Z',
        updated_at: '2026-03-20T00:00:00Z',
        raw_text: '',
        ocr_result: {
          document_transaction_direction: 'expense',
          commercial_document_semantics: 'receipt',
          transaction_direction_resolution: {
            candidate: 'expense',
            confidence: 0.77,
            source: 'merchant_counterparty',
            evidence: ['Receipt counterparty appears to be the merchant.'],
            semantics: 'receipt',
            is_reversal: false,
            strict_would_block: false,
          },
        },
      },
      extracted_data: {
        amount: 48.7,
        date: '2026-03-02',
        merchant: 'OMV',
        document_transaction_direction: 'expense',
        commercial_document_semantics: 'receipt',
        confidence: {},
      },
      suggestions: [],
    });

    render(
      <MemoryRouter>
        <OCRReview documentId={304} />
      </MemoryRouter>
    );

    await waitFor(() => expect(getDocumentForReview).toHaveBeenCalledWith(304));
    expect(screen.getByText('documents.review.transactionType')).toBeInTheDocument();
    expect(screen.getAllByText('收银小票').length).toBeGreaterThan(0);
    expect(screen.getByText(/保留原来的“收据”文档类型/)).toBeInTheDocument();
    expect(screen.getByText('单据方向与场景判断')).toBeInTheDocument();
    expect(screen.getByText('这是一笔支出')).toBeInTheDocument();
    expect(screen.getByText('Receipt counterparty appears to be the merchant.')).toBeInTheDocument();
    expect(screen.getByText(/超市\/商户小票通常是支出侧/)).toBeInTheDocument();
  });

  it('saves receipt semantics while aligning direction with the selected transaction type', async () => {
    getDocumentForReview.mockResolvedValueOnce({
      document: {
        id: 305,
        user_id: 7,
        document_type: 'receipt',
        file_path: '/tmp/receipt-primary.pdf',
        file_name: 'receipt-primary.pdf',
        file_size: 1000,
        mime_type: 'application/pdf',
        confidence_score: 0.88,
        needs_review: false,
        created_at: '2026-03-20T00:00:00Z',
        updated_at: '2026-03-20T00:00:00Z',
        raw_text: '',
        ocr_result: {
          document_transaction_direction: 'expense',
          commercial_document_semantics: 'receipt',
          transaction_direction_resolution: {
            candidate: 'expense',
            confidence: 0.77,
            source: 'merchant_counterparty',
            evidence: ['Receipt counterparty appears to be the merchant.'],
            semantics: 'receipt',
            is_reversal: false,
            strict_would_block: false,
          },
        },
      },
      extracted_data: {
        amount: 48.7,
        date: '2026-03-02',
        merchant: 'OMV',
        document_transaction_direction: 'expense',
        commercial_document_semantics: 'receipt',
        confidence: {},
      },
      suggestions: [],
    });

    render(
      <MemoryRouter>
        <OCRReview documentId={305} />
      </MemoryRouter>
    );

    await waitFor(() => expect(getDocumentForReview).toHaveBeenCalledWith(305));

    fireEvent.click(screen.getByRole('button', { name: 'transactions.types.income' }));
    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }));

    await waitFor(() => expect(correctOCR).toHaveBeenCalledTimes(1));
    expect(correctOCR).toHaveBeenCalledWith(
      305,
      expect.objectContaining({
        _document_type: 'receipt',
        _transaction_type: 'income',
        document_transaction_direction: 'income',
        commercial_document_semantics: 'receipt',
      })
    );
  });

  it('does not save receipt transaction-type changes when cancel is pressed', async () => {
    getDocumentForReview.mockResolvedValueOnce({
      document: {
        id: 306,
        user_id: 7,
        document_type: 'receipt',
        file_path: '/tmp/receipt-cancel.pdf',
        file_name: 'receipt-cancel.pdf',
        file_size: 1000,
        mime_type: 'application/pdf',
        confidence_score: 0.88,
        needs_review: false,
        created_at: '2026-03-20T00:00:00Z',
        updated_at: '2026-03-20T00:00:00Z',
        raw_text: '',
        ocr_result: {
          document_transaction_direction: 'expense',
          commercial_document_semantics: 'receipt',
        },
      },
      extracted_data: {
        amount: 15.5,
        date: '2026-03-03',
        merchant: 'Cafe Test',
        document_transaction_direction: 'expense',
        commercial_document_semantics: 'receipt',
        confidence: {},
      },
      suggestions: [],
    });

    render(
      <MemoryRouter>
        <OCRReview documentId={306} />
      </MemoryRouter>
    );

    await waitFor(() => expect(getDocumentForReview).toHaveBeenCalledWith(306));

    fireEvent.click(screen.getByRole('button', { name: 'transactions.types.income' }));
    fireEvent.click(screen.getByRole('button', { name: 'common.cancel' }));

    expect(correctOCR).not.toHaveBeenCalled();
  });
});
