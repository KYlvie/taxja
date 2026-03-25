/* @vitest-environment jsdom */

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';

import DocumentsPage from '../pages/DocumentsPage';

const getDocument = vi.fn();
const getDocuments = vi.fn();
const downloadDocument = vi.fn();
const getById = vi.fn();

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location-probe">{`${location.pathname}${location.search}`}</div>;
}

vi.mock('react-i18next', () => ({
  initReactI18next: {
    type: '3rdParty',
    init: () => undefined,
  },
  useTranslation: () => ({
    i18n: {
      language: 'zh',
    },
    t: (key: string, fallback?: string | { defaultValue?: string }) => {
      if (typeof fallback === 'string') return fallback;
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
vi.mock('../components/documents/BankStatementWorkbench', () => ({
  default: ({ onOpenTransaction }: any) => (
    <button
      type="button"
      onClick={() => onOpenTransaction?.(
        1621,
        {
          id: 1621,
          type: 'expense',
          amount: '62.23',
          transaction_date: '2024-12-18',
          description: 'T-Mobile Austria GmbH',
          expense_category: 'telecommunications',
          classification_confidence: '0.90',
          bank_reconciled: true,
        },
        '2024-12-18',
        '-62.23',
      )}
    >
      Open bank transaction
    </button>
  ),
}));
vi.mock('../components/documents/EmployerReviewPanel', () => ({ default: () => null }));
vi.mock('../components/documents/BescheidImport', () => ({ default: () => null }));
vi.mock('../components/documents/E1FormImport', () => ({ default: () => null }));
vi.mock('../components/documents/SuggestionCardFactory', () => ({ default: () => null }));
vi.mock('../components/transactions/TransactionDetail', () => ({
  default: ({ transaction, hideLinkedDocumentSection, onClose }: any) => (
    <div data-testid="transaction-detail">
      <span>{transaction.description}</span>
      <span>{hideLinkedDocumentSection ? 'hide-linked-document-section' : 'show-linked-document-section'}</span>
      <button type="button" onClick={onClose}>
        close-inline-transaction
      </button>
    </div>
  ),
}));

vi.mock('../services/documentService', () => ({
  documentService: {
    getDocuments: (...args: any[]) => getDocuments(...args),
    getDocument: (...args: any[]) => getDocument(...args),
    downloadDocument: (...args: any[]) => downloadDocument(...args),
  },
}));

vi.mock('../services/transactionService', () => ({
  transactionService: {
    getById: (...args: any[]) => getById(...args),
    update: vi.fn(),
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
  aiToast: vi.fn(),
}));

describe('DocumentsPage linked transaction entry', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.URL.createObjectURL = vi.fn(() => 'blob:test');
    global.URL.revokeObjectURL = vi.fn();
    getDocuments.mockResolvedValue([{ id: 118 }]);

    getDocument.mockResolvedValue({
      id: 118,
      user_id: 1,
      document_type: 'receipt',
      file_path: '/tmp/receipt.pdf',
      file_name: 'receipt.pdf',
      file_size: 100,
      mime_type: 'application/pdf',
      confidence_score: 0.92,
      needs_review: false,
      transaction_id: 1151,
      created_at: '2026-03-17T00:00:00Z',
      updated_at: '2026-03-17T00:00:00Z',
      linked_transactions: [
        {
          transaction_id: 1151,
          description: 'OAMTC battery replacement',
          amount: 237.9,
          date: '2024-12-30',
          has_line_items: false,
        },
      ],
      ocr_result: {
        merchant: 'OAMTC',
        amount: 237.9,
        line_items: [
          {
            description: 'Battery replacement',
            amount: 237.9,
            quantity: 1,
          },
        ],
      },
    });

    downloadDocument.mockResolvedValue(new Blob(['pdf']));
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
      document_id: 118,
    });
  });

  it('opens linked transactions inline and keeps the user on the current document page', async () => {
    render(
      <MemoryRouter initialEntries={['/documents/118']}>
        <LocationProbe />
        <Routes>
          <Route path="/documents/:documentId" element={<DocumentsPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => expect(getDocument).toHaveBeenCalledWith(118));
    const openButton = await screen.findByRole('button', { name: 'Open transaction' });

    fireEvent.click(openButton);

    await waitFor(() => {
      expect(getById).toHaveBeenCalledWith(1151);
    });

    expect(screen.getByTestId('transaction-detail')).toBeInTheDocument();
    expect(screen.getByTestId('location-probe')).toHaveTextContent('/documents/118');
    expect(screen.getByText('hide-linked-document-section')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'close-inline-transaction' }));

    await waitFor(() => {
      expect(screen.queryByTestId('transaction-detail')).not.toBeInTheDocument();
    });
    expect(screen.getByTestId('location-probe')).toHaveTextContent('/documents/118');
  });
});
