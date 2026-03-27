/* @vitest-environment jsdom */

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DocumentUpload from '../components/documents/DocumentUpload';
import { useAIAdvisorStore } from '../stores/aiAdvisorStore';
import { useAuthStore } from '../stores/authStore';
import { useDocumentStore } from '../stores/documentStore';

const uploadDocument = vi.fn();
const uploadImageGroup = vi.fn();
const getDocument = vi.fn();
const getProcessStatus = vi.fn();
const mockNavigate = vi.fn();

vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: any) => {
      if (typeof opts === 'string') return opts;
      if (opts?.defaultValue) {
        return opts.defaultValue.replace(/\{\{(\w+)\}\}/g, (_: string, token: string) => String(opts[token] ?? ''));
      }
      return key;
    },
    i18n: { language: 'en', resolvedLanguage: 'en' },
  }),
}));

vi.mock('../services/documentService', () => ({
  documentService: {
    uploadDocument: (...args: any[]) => uploadDocument(...args),
    uploadImageGroup: (...args: any[]) => uploadImageGroup(...args),
    getDocument: (...args: any[]) => getDocument(...args),
    getProcessStatus: (...args: any[]) => getProcessStatus(...args),
  },
}));

vi.mock('../services/employerService', () => ({
  employerService: {
    detectFromDocument: vi.fn(),
    detectAnnualArchiveFromDocument: vi.fn(),
  },
}));

vi.mock('../mobile/files', () => ({
  capturePhotoAsFile: vi.fn(),
  pickNativeFiles: vi.fn(),
  supportsNativeFileActions: () => false,
}));

describe('DocumentUpload terminal polling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockNavigate.mockReset();

    useAuthStore.setState({
      user: null,
      token: null,
      isAuthenticated: false,
    });
    useDocumentStore.setState({
      documents: [],
      currentDocument: null,
      total: 0,
      loading: false,
      error: null,
      filters: {},
    });
    useAIAdvisorStore.getState().clearMessages();

    uploadDocument.mockResolvedValue({
      id: 325,
      user_id: 1,
      document_type: 'receipt',
      file_path: '/docs/uploaded.pdf',
      file_name: 'Screenshot 2026-03-17 010627.png',
      file_size: 1024,
      mime_type: 'application/pdf',
      confidence_score: 0,
      needs_review: false,
      created_at: '2026-03-23T23:38:23.000Z',
      updated_at: '2026-03-23T23:38:23.000Z',
      uploaded_at: '2026-03-23T23:38:23.000Z',
    });

    getDocument
      .mockResolvedValueOnce({
        id: 325,
        user_id: 1,
        document_type: 'receipt',
        file_path: '/docs/uploaded.pdf',
        file_name: 'Screenshot 2026-03-17 010627.png',
        file_size: 1024,
        mime_type: 'application/pdf',
        confidence_score: 0.8,
        needs_review: false,
        created_at: '2026-03-23T23:38:23.000Z',
        updated_at: '2026-03-24T00:12:04.000Z',
        uploaded_at: '2026-03-23T23:38:23.000Z',
        ocr_status: 'processing',
        ocr_result: {
          merchant: 'INTERSPAR',
          amount: 18.42,
          _pipeline: {
            current_state: 'first_result_available',
          },
        },
      })
      .mockResolvedValueOnce({
        id: 325,
        user_id: 1,
        document_type: 'receipt',
        file_path: '/docs/uploaded.pdf',
        file_name: 'Screenshot 2026-03-17 010627.png',
        file_size: 1024,
        mime_type: 'application/pdf',
        confidence_score: 0.95,
        needs_review: false,
        created_at: '2026-03-23T23:38:23.000Z',
        updated_at: '2026-03-24T00:14:20.000Z',
        uploaded_at: '2026-03-23T23:38:23.000Z',
        processed_at: '2026-03-24T00:14:20.000Z',
        ocr_status: 'completed',
        ocr_result: {
          merchant: 'INTERSPAR',
          amount: 18.42,
          confirmed: false,
          _pipeline: {
            current_state: 'completed',
          },
        },
      });
  });

  it('waits for terminal OCR completion before marking the upload complete', async () => {
    const onDocumentsSubmitted = vi.fn();
    const { container } = render(<DocumentUpload onDocumentsSubmitted={onDocumentsSubmitted} />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;

    fireEvent.change(input, {
      target: {
        files: [new File(['receipt'], 'Screenshot 2026-03-17 010627.pdf', { type: 'application/pdf' })],
      },
    });

    await waitFor(() => expect(uploadDocument).toHaveBeenCalledTimes(1));

    await waitFor(() => expect(getDocument).toHaveBeenCalledTimes(1), { timeout: 4000 });
    expect(screen.queryByRole('button', { name: 'View document' })).not.toBeInTheDocument();
    expect(useDocumentStore.getState().documents[0]).toEqual(
      expect.objectContaining({
        id: 325,
        confidence_score: 0.8,
        ocr_status: 'processing',
      }),
    );

    await waitFor(() => expect(getDocument).toHaveBeenCalledTimes(2), { timeout: 7000 });
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'View document' })).toBeInTheDocument();
    });
    expect(useDocumentStore.getState().documents[0]).toEqual(
      expect.objectContaining({
        id: 325,
        confidence_score: 0.95,
        processed_at: '2026-03-24T00:14:20.000Z',
        ocr_status: 'completed',
      }),
    );
    expect(onDocumentsSubmitted).toHaveBeenCalled();
    expect(onDocumentsSubmitted).toHaveBeenLastCalledWith([
      expect.objectContaining({
        id: 325,
        confidence_score: 0.95,
        ocr_status: 'completed',
      }),
    ]);
  }, 15000);

  it('keeps per-file progress state stable even after removing another completed upload', async () => {
    uploadDocument
      .mockResolvedValueOnce({
        id: 401,
        user_id: 1,
        document_type: 'receipt',
        file_path: '/docs/401.pdf',
        file_name: 'one.pdf',
        file_size: 1024,
        mime_type: 'application/pdf',
        confidence_score: 0,
        needs_review: false,
        created_at: '2026-03-23T23:38:23.000Z',
        updated_at: '2026-03-23T23:38:23.000Z',
        uploaded_at: '2026-03-23T23:38:23.000Z',
      })
      .mockResolvedValueOnce({
        id: 402,
        user_id: 1,
        document_type: 'receipt',
        file_path: '/docs/402.pdf',
        file_name: 'two.pdf',
        file_size: 1024,
        mime_type: 'application/pdf',
        confidence_score: 0,
        needs_review: false,
        created_at: '2026-03-23T23:38:23.000Z',
        updated_at: '2026-03-23T23:38:23.000Z',
        uploaded_at: '2026-03-23T23:38:23.000Z',
      })
      .mockResolvedValueOnce({
        id: 403,
        user_id: 1,
        document_type: 'receipt',
        file_path: '/docs/403.pdf',
        file_name: 'three.pdf',
        file_size: 1024,
        mime_type: 'application/pdf',
        confidence_score: 0,
        needs_review: false,
        created_at: '2026-03-23T23:38:23.000Z',
        updated_at: '2026-03-23T23:38:23.000Z',
        uploaded_at: '2026-03-23T23:38:23.000Z',
      });

    getDocument
      .mockResolvedValueOnce({
        id: 401,
        user_id: 1,
        document_type: 'receipt',
        file_path: '/docs/401.pdf',
        file_name: 'one.pdf',
        file_size: 1024,
        mime_type: 'application/pdf',
        confidence_score: 0.95,
        needs_review: false,
        created_at: '2026-03-23T23:38:23.000Z',
        updated_at: '2026-03-24T00:14:20.000Z',
        uploaded_at: '2026-03-23T23:38:23.000Z',
        processed_at: '2026-03-24T00:14:20.000Z',
        ocr_status: 'completed',
        ocr_result: { merchant: 'ONE', amount: 1, _pipeline: { current_state: 'completed' } },
      })
      .mockResolvedValueOnce({
        id: 402,
        user_id: 1,
        document_type: 'receipt',
        file_path: '/docs/402.pdf',
        file_name: 'two.pdf',
        file_size: 1024,
        mime_type: 'application/pdf',
        confidence_score: 0.8,
        needs_review: false,
        created_at: '2026-03-23T23:38:23.000Z',
        updated_at: '2026-03-24T00:12:04.000Z',
        uploaded_at: '2026-03-23T23:38:23.000Z',
        ocr_status: 'processing',
        ocr_result: { merchant: 'TWO', amount: 2, _pipeline: { current_state: 'first_result_available' } },
      })
      .mockResolvedValueOnce({
        id: 403,
        user_id: 1,
        document_type: 'receipt',
        file_path: '/docs/403.pdf',
        file_name: 'three.pdf',
        file_size: 1024,
        mime_type: 'application/pdf',
        confidence_score: 0.8,
        needs_review: false,
        created_at: '2026-03-23T23:38:23.000Z',
        updated_at: '2026-03-24T00:12:04.000Z',
        uploaded_at: '2026-03-23T23:38:23.000Z',
        ocr_status: 'processing',
        ocr_result: { merchant: 'THREE', amount: 3, _pipeline: { current_state: 'first_result_available' } },
      })
      .mockResolvedValueOnce({
        id: 402,
        user_id: 1,
        document_type: 'receipt',
        file_path: '/docs/402.pdf',
        file_name: 'two.pdf',
        file_size: 1024,
        mime_type: 'application/pdf',
        confidence_score: 0.95,
        needs_review: false,
        created_at: '2026-03-23T23:38:23.000Z',
        updated_at: '2026-03-24T00:15:20.000Z',
        uploaded_at: '2026-03-23T23:38:23.000Z',
        processed_at: '2026-03-24T00:15:20.000Z',
        ocr_status: 'completed',
        ocr_result: { merchant: 'TWO', amount: 2, _pipeline: { current_state: 'completed' } },
      })
      .mockResolvedValueOnce({
        id: 403,
        user_id: 1,
        document_type: 'receipt',
        file_path: '/docs/403.pdf',
        file_name: 'three.pdf',
        file_size: 1024,
        mime_type: 'application/pdf',
        confidence_score: 0.95,
        needs_review: false,
        created_at: '2026-03-23T23:38:23.000Z',
        updated_at: '2026-03-24T00:16:20.000Z',
        uploaded_at: '2026-03-23T23:38:23.000Z',
        processed_at: '2026-03-24T00:16:20.000Z',
        ocr_status: 'completed',
        ocr_result: { merchant: 'THREE', amount: 3, _pipeline: { current_state: 'completed' } },
      });

    const { container } = render(<DocumentUpload />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;

    fireEvent.change(input, {
      target: {
        files: [
          new File(['one'], 'one.pdf', { type: 'application/pdf' }),
          new File(['two'], 'two.pdf', { type: 'application/pdf' }),
          new File(['three'], 'three.pdf', { type: 'application/pdf' }),
        ],
      },
    });

    await waitFor(() => expect(uploadDocument).toHaveBeenCalledTimes(3), { timeout: 5000 });
    await waitFor(() => {
      expect(screen.getByText('one.pdf')).toBeInTheDocument();
      expect(screen.getByText('two.pdf')).toBeInTheDocument();
      expect(screen.getByText('three.pdf')).toBeInTheDocument();
    }, { timeout: 3000 });
    await waitFor(() => expect(screen.getAllByRole('button', { name: 'View document' }).length).toBeGreaterThanOrEqual(2), { timeout: 5000 });

    const removeButtons = screen.getAllByLabelText('Remove');
    fireEvent.click(removeButtons[0]);

    await waitFor(() => expect(screen.queryByText('two.pdf')).not.toBeInTheDocument(), { timeout: 3000 });
    await waitFor(() => expect(screen.getByText('one.pdf')).toBeInTheDocument(), { timeout: 3000 });
    await waitFor(() => expect(screen.getByText('three.pdf')).toBeInTheDocument(), { timeout: 3000 });
    await waitFor(() => {
      const viewButtons = screen.getAllByRole('button', { name: 'View document' });
      expect(viewButtons.length).toBeGreaterThanOrEqual(2);
    }, { timeout: 10000 });
  }, 20000);
});
