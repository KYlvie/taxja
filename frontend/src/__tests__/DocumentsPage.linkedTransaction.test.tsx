/* @vitest-environment jsdom */

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';

import DocumentsPage from '../pages/DocumentsPage';

const getDocument = vi.fn();
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
vi.mock('../components/documents/EmployerReviewPanel', () => ({ default: () => null }));
vi.mock('../components/documents/BescheidImport', () => ({ default: () => null }));
vi.mock('../components/documents/E1FormImport', () => ({ default: () => null }));
vi.mock('../components/documents/SuggestionCardFactory', () => ({ default: () => null }));

vi.mock('../services/documentService', () => ({
  documentService: {
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
      ocr_result: {
        merchant: 'OAMTC',
        amount: 237.9,
        line_items: [],
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
    });
  });

  it('shows a direct linked-transaction button and navigates to the matching transaction', async () => {
    render(
      <MemoryRouter initialEntries={['/documents/118']}>
        <Routes>
          <Route path="/documents/:documentId" element={<DocumentsPage />} />
          <Route path="/transactions" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => expect(getDocument).toHaveBeenCalledWith(118));
    const openButton = await screen.findByRole('button', { name: 'Open transaction' });

    fireEvent.click(openButton);

    await waitFor(() => {
      expect(screen.getByTestId('location-probe')).toHaveTextContent('/transactions?transactionId=1151');
    });
  });
});
