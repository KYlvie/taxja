/* @vitest-environment jsdom */

import { fireEvent, render, waitFor, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DocumentUpload from '../components/documents/DocumentUpload';
import { useAuthStore } from '../stores/authStore';
import { useDocumentStore } from '../stores/documentStore';
import { useAIAdvisorStore } from '../stores/aiAdvisorStore';

const uploadDocument = vi.fn();
const uploadImageGroup = vi.fn();
const getDocument = vi.fn();
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
    i18n: { language: 'zh', resolvedLanguage: 'zh' },
  }),
}));

vi.mock('../services/documentService', () => ({
  documentService: {
    uploadDocument: (...args: any[]) => uploadDocument(...args),
    uploadImageGroup: (...args: any[]) => uploadImageGroup(...args),
    getDocument: (...args: any[]) => getDocument(...args),
  },
}));

vi.mock('../services/employerService', () => ({
  employerService: {},
}));

vi.mock('../mobile/files', () => ({
  capturePhotoAsFile: vi.fn(),
  pickNativeFiles: vi.fn(),
  supportsNativeFileActions: () => false,
}));

describe('DocumentUpload duplicate reuse flow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockNavigate.mockReset();
    useAuthStore.setState({
      user: null,
      token: null,
      isAuthenticated: false,
    });
    useDocumentStore.setState({
      documents: [
        {
          id: 101,
          user_id: 1,
          document_type: 'receipt' as any,
          file_path: '/docs/existing.pdf',
          file_name: 'existing.pdf',
          file_size: 256,
          mime_type: 'application/pdf',
          confidence_score: 0.7,
          needs_review: false,
          created_at: '2026-03-18T00:00:00Z',
          updated_at: '2026-03-18T00:00:00Z',
        },
      ],
      currentDocument: null,
      total: 1,
      loading: false,
      error: null,
      filters: {},
    });
    useAIAdvisorStore.getState().clearMessages();

    uploadDocument.mockResolvedValue({
      id: 101,
      file_name: 'existing.pdf',
      file_size: 256,
      mime_type: 'application/pdf',
      document_type: 'receipt',
      uploaded_at: new Date().toISOString(),
      deduplicated: true,
      duplicate_of_document_id: 101,
      message: 'Duplicate document detected. Existing document reused.',
    });

    getDocument.mockResolvedValue({
      id: 101,
      user_id: 1,
      document_type: 'receipt',
      file_path: '/docs/existing.pdf',
      file_name: 'existing.pdf',
      file_size: 256,
      mime_type: 'application/pdf',
      confidence_score: 0.9,
      needs_review: false,
      created_at: '2026-03-18T00:00:00Z',
      updated_at: '2026-03-18T01:00:00Z',
      processed_at: new Date().toISOString(),
      ocr_result: { merchant: 'Billa', amount: 4.99 },
    });
  });

  it('marks duplicate uploads as reused and keeps one document in the store', async () => {
    const onDocumentsSubmitted = vi.fn();
    const { container } = render(<DocumentUpload onDocumentsSubmitted={onDocumentsSubmitted} />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;

    fireEvent.change(input, {
      target: {
        files: [new File(['same-content'], 'existing.pdf', { type: 'application/pdf' })],
      },
    });

    await waitFor(() => expect(uploadDocument).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(getDocument).toHaveBeenCalledWith(101));
    await waitFor(() => {
      expect(
        screen.getByText((content) => content.includes('重复文件，已复用现有文档'))
      ).toBeInTheDocument();
    });

    const state = useDocumentStore.getState();
    expect(state.documents).toHaveLength(1);
    expect(state.documents[0].id).toBe(101);
    expect(onDocumentsSubmitted).toHaveBeenCalledWith([
      expect.objectContaining({ id: 101 }),
    ]);

    const proactiveMessages = useAIAdvisorStore.getState().messages;
    expect(proactiveMessages).toEqual([
      expect.objectContaining({
        type: 'upload_success',
        link: '/documents/101',
        linkLabel: 'View document',
      }),
    ]);
  });

  it('opens the completed upload row when the user clicks it', async () => {
    const { container } = render(<DocumentUpload />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;

    fireEvent.change(input, {
      target: {
        files: [new File(['same-content'], 'existing.pdf', { type: 'application/pdf' })],
      },
    });

    const completedRow = await screen.findByRole('button', { name: 'View document' });
    fireEvent.click(completedRow);

    expect(mockNavigate).toHaveBeenCalledWith('/documents/101');
  });
});
