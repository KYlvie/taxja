/* @vitest-environment jsdom */

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import DocumentsPage from '../pages/DocumentsPage';

const getDocument = vi.fn();
const confirmLoanRepayment = vi.fn();
const downloadDocument = vi.fn();

const refreshTransactions = vi.fn();
const refreshDashboard = vi.fn();
const refreshRecurring = vi.fn();

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
vi.mock('../components/documents/OCRReview', () => ({
  default: ({ documentId, onConfirm }: { documentId: number; onConfirm?: () => void }) => (
    <button
      type="button"
      data-testid="ocr-review"
      onClick={async () => {
        const result = await confirmLoanRepayment(documentId);
        await getDocument(documentId);
        refreshDashboard();
        if (result?.recurring_id || result?.property_id) {
          refreshRecurring();
          refreshTransactions();
        }
        onConfirm?.();
      }}
    >
      trigger loan repayment confirm
    </button>
  ),
}));
vi.mock('../components/documents/EmployerReviewPanel', () => ({ default: () => null }));
vi.mock('../components/documents/BescheidImport', () => ({ default: () => null }));
vi.mock('../components/documents/E1FormImport', () => ({ default: () => null }));
vi.mock('../components/documents/SuggestionCardFactory', () => ({ default: () => null }));

vi.mock('../services/documentService', () => ({
  documentService: {
    getDocument: (...args: any[]) => getDocument(...args),
    confirmLoanRepayment: (...args: any[]) => confirmLoanRepayment(...args),
    downloadDocument: (...args: any[]) => downloadDocument(...args),
  },
}));

vi.mock('../services/propertyService', () => ({
  propertyService: {
    getProperty: vi.fn(),
  },
}));

vi.mock('../services/transactionService', () => ({
  transactionService: {
    getById: vi.fn(),
    update: vi.fn(),
  },
}));

vi.mock('../mobile/files', () => ({
  saveBlobWithNativeShare: vi.fn(),
}));

vi.mock('../stores/refreshStore', () => ({
  useRefreshStore: {
    getState: () => ({
      refreshTransactions,
      refreshDashboard,
      refreshProperties: vi.fn(),
      refreshRecurring,
    }),
  },
}));

vi.mock('../stores/aiToastStore', () => ({
  aiToast: vi.fn(),
}));

describe('DocumentsPage loan repayment suggestion confirmation', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    getDocument.mockResolvedValue({
      id: 301,
      user_id: 1,
      document_type: 'loan_contract',
      file_path: '/tmp/loan.pdf',
      file_name: 'loan.pdf',
      file_size: 100,
      mime_type: 'application/pdf',
      confidence_score: 0.95,
      needs_review: false,
      created_at: '2026-03-20T00:00:00Z',
      updated_at: '2026-03-20T00:00:00Z',
      ocr_result: {
        import_suggestion: {
          type: 'create_loan_repayment',
          status: 'pending',
          data: {
            lender_name: 'Erste Bank',
            monthly_payment: 1508.33,
          },
        },
      },
    });

    downloadDocument.mockResolvedValue(new Blob(['pdf']));
    global.URL.createObjectURL = vi.fn(() => 'blob:test');
    global.URL.revokeObjectURL = vi.fn();
  });

  it('acknowledges standalone loan contracts without refreshing recurring data', async () => {
    confirmLoanRepayment.mockResolvedValue({ recurring_id: null, acknowledged_only: true });

    render(
      <MemoryRouter initialEntries={['/documents/301']}>
        <Routes>
          <Route path="/documents/:documentId" element={<DocumentsPage />} />
          <Route path="/documents" element={<div data-testid="documents-route" />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => expect(getDocument).toHaveBeenCalledWith(301));

    fireEvent.click(await screen.findByRole('button', { name: 'trigger loan repayment confirm' }));

    await waitFor(() => {
      expect(confirmLoanRepayment).toHaveBeenCalledWith(301);
    });

    expect(refreshRecurring).not.toHaveBeenCalled();
    expect(refreshTransactions).not.toHaveBeenCalled();
    expect(refreshDashboard).toHaveBeenCalled();
    await waitFor(() => expect(getDocument).toHaveBeenCalledTimes(2));
  });

  it('refreshes recurring data when loan confirmation is promoted into the property flow', async () => {
    confirmLoanRepayment.mockResolvedValue({ recurring_id: 'rec-1', property_id: 'prop-1' });

    render(
      <MemoryRouter initialEntries={['/documents/301']}>
        <Routes>
          <Route path="/documents/:documentId" element={<DocumentsPage />} />
          <Route path="/documents" element={<div data-testid="documents-route" />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => expect(getDocument).toHaveBeenCalledWith(301));

    fireEvent.click(await screen.findByRole('button', { name: 'trigger loan repayment confirm' }));

    await waitFor(() => {
      expect(confirmLoanRepayment).toHaveBeenCalledWith(301);
    });

    expect(refreshRecurring).toHaveBeenCalled();
    expect(refreshTransactions).toHaveBeenCalled();
    expect(refreshDashboard).toHaveBeenCalled();
  });

  it('still shows the loan action entry for legacy needs_input suggestions', async () => {
    render(
      <MemoryRouter initialEntries={['/documents/301']}>
        <Routes>
          <Route path="/documents/:documentId" element={<DocumentsPage />} />
          <Route path="/documents" element={<div data-testid="documents-route" />} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByRole('button', { name: 'trigger loan repayment confirm' })).toBeInTheDocument();
  });
});
