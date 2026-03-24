/* @vitest-environment jsdom */

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

import OCRReview from '../components/documents/OCRReview';

const getDocumentForReview = vi.fn();
const getDocument = vi.fn();
const downloadDocument = vi.fn();
const retryOcr = vi.fn();
const confirmTaxData = vi.fn();
const aiToast = vi.fn();

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string | { defaultValue?: string }) => {
      const translations: Record<string, string> = {
        'documents.reprocess': '重新处理文档',
        'documents.reprocessing': '重新处理中...',
        'documents.reprocessStarted': '已开始重新处理文档，当前结果会保留到新结果完成',
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

vi.mock('../services/documentService', () => ({
  documentService: {
    getDocument: (...args: any[]) => getDocument(...args),
    getDocumentForReview: (...args: any[]) => getDocumentForReview(...args),
    downloadDocument: (...args: any[]) => downloadDocument(...args),
    retryOcr: (...args: any[]) => retryOcr(...args),
    confirmTaxData: (...args: any[]) => confirmTaxData(...args),
    correctOCR: vi.fn(),
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
  aiToast: (...args: any[]) => aiToast(...args),
}));

vi.mock('../components/documents/BescheidImport', () => ({
  default: () => null,
}));

describe('OCRReview reprocess action', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.URL.createObjectURL = vi.fn(() => 'blob:test');
    global.URL.revokeObjectURL = vi.fn();
    downloadDocument.mockResolvedValue(new Blob(['pdf']));
    retryOcr.mockResolvedValue({});
    getDocument.mockResolvedValue({
      id: 124,
      ocr_result: { _pipeline: { current_state: 'completed' } },
    });
    getDocumentForReview.mockResolvedValue({
      document: {
        id: 124,
        user_id: 5,
        document_type: 'receipt',
        file_path: '/tmp/review.pdf',
        file_name: 'review.pdf',
        file_size: 1234,
        mime_type: 'application/pdf',
        confidence_score: 0.42,
        needs_review: true,
        created_at: '2026-03-18T00:00:00Z',
        updated_at: '2026-03-18T00:00:00Z',
        raw_text: 'old text',
        ocr_result: {
          merchant: 'Billa',
        },
      },
      extracted_data: {
        merchant: 'Billa',
        confidence: {},
      },
      suggestions: [],
    });
  });

  it('shows the reprocess action for review-mode documents and keeps one shared entry point', async () => {
    render(
      <MemoryRouter>
        <OCRReview documentId={124} />
      </MemoryRouter>
    );

    await waitFor(() => expect(getDocumentForReview).toHaveBeenCalledWith(124));

    fireEvent.click(await screen.findByRole('button', { name: '重新处理文档' }));

    await waitFor(() => expect(retryOcr).toHaveBeenCalledWith(124));
    expect(aiToast).toHaveBeenCalledWith(
      '已开始重新处理文档，当前结果会保留到新结果完成',
      'success'
    );
  });
});
