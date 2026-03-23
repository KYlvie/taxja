/* @vitest-environment jsdom */

import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import DocumentsPage from '../pages/DocumentsPage';

const getDocument = vi.fn();
const downloadDocument = vi.fn();

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string | { defaultValue?: string }) => {
      const translations: Record<string, string> = {
        'documents.reprocess': '重新处理文档',
        'documents.reprocessing': '重新处理中...',
        'documents.download': '下载',
        'common.back': '返回',
        'documents.types.receipt': '收据',
        'documents.confidence': '置信度',
      };
      if (typeof fallback === 'string') return fallback;
      if (translations[key]) return translations[key];
      if (fallback && typeof fallback === 'object' && typeof fallback.defaultValue === 'string') {
        return fallback.defaultValue;
      }
      return key;
    },
    i18n: {
      language: 'zh',
      resolvedLanguage: 'zh',
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
    retryOcr: vi.fn(),
  },
}));

vi.mock('../services/transactionService', () => ({
  transactionService: {
    getById: vi.fn(),
    update: vi.fn(),
  },
}));

vi.mock('../services/propertyService', () => ({
  propertyService: {
    getById: vi.fn(),
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

describe('DocumentsPage reprocess availability', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.URL.createObjectURL = vi.fn(() => 'blob:test');
    global.URL.revokeObjectURL = vi.fn();

    getDocument.mockResolvedValue({
      id: 321,
      user_id: 1,
      document_type: 'receipt',
      file_path: '/tmp/no-ocr-yet.pdf',
      file_name: 'no-ocr-yet.pdf',
      file_size: 2048,
      mime_type: 'application/pdf',
      confidence_score: 0,
      needs_review: false,
      created_at: '2026-03-20T00:00:00Z',
      updated_at: '2026-03-20T00:00:00Z',
      processed_at: null,
      ocr_result: null,
    });
    downloadDocument.mockResolvedValue(new Blob(['pdf']));
  });

  it('shows the reprocess action even when OCR has not succeeded yet', async () => {
    render(
      <MemoryRouter initialEntries={['/documents/321']}>
        <Routes>
          <Route path="/documents/:documentId" element={<DocumentsPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => expect(getDocument).toHaveBeenCalledWith(321));

    expect(
      await screen.findByRole('button', { name: '重新处理文档' })
    ).toBeInTheDocument();
  });
});
