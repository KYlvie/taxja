/* @vitest-environment jsdom */

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import DocumentsPage from '../pages/DocumentsPage';

const getDocument = vi.fn();
const getDocuments = vi.fn();
const downloadDocument = vi.fn();
const confirmMock = vi.fn();

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
      if (typeof fallback === 'string') return fallback;
      if (fallback && typeof fallback === 'object' && typeof fallback.defaultValue === 'string') {
        return fallback.defaultValue;
      }
      return key;
    },
  }),
}));

vi.mock('../hooks/useConfirm', () => ({
  useConfirm: () => ({
    confirm: (...args: any[]) => confirmMock(...args),
  }),
}));

vi.mock('../components/documents/DocumentUpload', () => ({ default: () => <div data-testid="doc-upload" /> }));
vi.mock('../components/documents/DocumentList', () => ({ default: () => <div data-testid="doc-list" /> }));
vi.mock('../components/documents/BankStatementWorkbench', () => ({
  default: () => <div data-testid="bank-workbench">bank statement workbench</div>,
}));
vi.mock('../components/documents/EmployerReviewPanel', () => ({ default: () => null }));
vi.mock('../components/documents/BescheidImport', () => ({ default: () => null }));
vi.mock('../components/documents/E1FormImport', () => ({ default: () => null }));
vi.mock('../components/documents/SuggestionCardFactory', () => ({ default: () => null }));
vi.mock('../components/transactions/TransactionDetail', () => ({ default: () => null }));
vi.mock('../components/common/RobotMascot', () => ({ default: () => null }));
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
vi.mock('../mobile/files', () => ({
  saveBlobWithNativeShare: vi.fn(),
}));
vi.mock('../documents/presentation/featureFlag', () => ({
  default: () => true,
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
    getById: vi.fn(),
  },
}));
vi.mock('../services/propertyService', () => ({
  propertyService: {
    getProperty: vi.fn(),
  },
}));

vi.mock('../components/documents/OCRReview', () => ({
  default: (props: any) => (
    <div data-testid="ocr-review">
      <div data-testid="ocr-template">{props.presentationTemplate}</div>
      <div data-testid="ocr-editable">{String(Boolean(props.allowDocumentTypeEdit))}</div>
      <button type="button" onClick={() => void props.onDocumentTypeDraftChange?.('svs_notice')}>
        switch-to-svs
      </button>
      <button type="button" onClick={() => void props.onDocumentTypeDraftChange?.('bank_statement')}>
        switch-to-bank
      </button>
    </div>
  ),
}));

function renderDocumentsPage(path = '/documents/201') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/documents/:documentId" element={<DocumentsPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('DocumentsPage type locking and template switching', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.URL.createObjectURL = vi.fn(() => 'blob:test');
    global.URL.revokeObjectURL = vi.fn();
    getDocuments.mockResolvedValue([{ id: 201 }]);
    downloadDocument.mockResolvedValue(new Blob(['pdf']));
  });

  it('lets other documents confirm-switch into tax and bank templates immediately', async () => {
    getDocument.mockResolvedValue({
      id: 201,
      user_id: 1,
      document_type: 'other',
      file_path: '/tmp/other.pdf',
      file_name: 'other.pdf',
      file_size: 100,
      mime_type: 'application/pdf',
      confidence_score: 0.82,
      needs_review: true,
      created_at: '2026-03-27T00:00:00Z',
      updated_at: '2026-03-27T00:00:00Z',
      ocr_result: {},
    });
    confirmMock.mockResolvedValue(true);

    renderDocumentsPage();

    await waitFor(() => expect(getDocument).toHaveBeenCalledWith(201));
    await screen.findByTestId('ocr-review');
    expect(screen.getByTestId('ocr-template')).toHaveTextContent('generic_review');
    expect(screen.getByTestId('ocr-editable')).toHaveTextContent('true');

    fireEvent.click(screen.getByText('switch-to-svs'));
    await waitFor(() => expect(confirmMock).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByTestId('ocr-template')).toHaveTextContent('tax_import'));

    fireEvent.click(screen.getByText('switch-to-bank'));
    await waitFor(() => expect(screen.getByTestId('bank-workbench')).toBeInTheDocument());
  });

  it('keeps current template when the user cancels the switch confirmation', async () => {
    getDocument.mockResolvedValue({
      id: 201,
      user_id: 1,
      document_type: 'other',
      file_path: '/tmp/other.pdf',
      file_name: 'other.pdf',
      file_size: 100,
      mime_type: 'application/pdf',
      confidence_score: 0.82,
      needs_review: true,
      created_at: '2026-03-27T00:00:00Z',
      updated_at: '2026-03-27T00:00:00Z',
      ocr_result: {},
    });
    confirmMock.mockResolvedValue(false);

    renderDocumentsPage();

    await screen.findByTestId('ocr-review');
    fireEvent.click(screen.getByText('switch-to-svs'));

    await waitFor(() => expect(confirmMock).toHaveBeenCalled());
    expect(screen.getByTestId('ocr-template')).toHaveTextContent('generic_review');
  });

  it('keeps already recognized invoice documents on the receipt workbench route', async () => {
    getDocument.mockResolvedValue({
      id: 201,
      user_id: 1,
      document_type: 'invoice',
      file_path: '/tmp/invoice.pdf',
      file_name: 'invoice.pdf',
      file_size: 100,
      mime_type: 'application/pdf',
      confidence_score: 0.95,
      needs_review: true,
      created_at: '2026-03-27T00:00:00Z',
      updated_at: '2026-03-27T00:00:00Z',
      ocr_result: {
        _transaction_type: 'expense',
        commercial_document_semantics: 'standard_invoice',
      },
    });

    renderDocumentsPage();

    await waitFor(() => expect(getDocument).toHaveBeenCalledWith(201));
    expect(screen.queryByTestId('ocr-review')).not.toBeInTheDocument();
    expect(screen.queryByText('switch-to-svs')).not.toBeInTheDocument();
    expect(screen.getByText('documents.types.invoice')).toBeInTheDocument();
    expect(screen.getByText('OCR-detected receipt')).toBeInTheDocument();
  });
});
