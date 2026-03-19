/* @vitest-environment jsdom */

import { render, fireEvent, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import DocumentUpload from '../components/documents/DocumentUpload';
import { useAuthStore } from '../stores/authStore';
import { useDocumentStore } from '../stores/documentStore';
import { useAIAdvisorStore } from '../stores/aiAdvisorStore';

const uploadDocument = vi.fn();
const uploadImageGroup = vi.fn();
const getDocument = vi.fn();

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: any) => {
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

describe('DocumentUpload image grouping', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('URL', {
      ...URL,
      createObjectURL: vi.fn(() => 'blob:test-preview'),
      revokeObjectURL: vi.fn(),
    });
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

    uploadImageGroup.mockResolvedValue({
      id: 101,
      file_name: 'grouped.pdf',
      file_size: 4096,
      mime_type: 'application/pdf',
      document_type: 'other',
      uploaded_at: new Date().toISOString(),
      confidence_score: 0,
      needs_review: false,
    });
    uploadDocument.mockResolvedValue({
      id: 102,
      file_name: 'single.jpg',
      file_size: 1024,
      mime_type: 'image/jpeg',
      document_type: 'other',
      uploaded_at: new Date().toISOString(),
      confidence_score: 0,
      needs_review: false,
    });
    getDocument.mockResolvedValue({
      id: 101,
      file_name: 'grouped.pdf',
      file_size: 4096,
      mime_type: 'application/pdf',
      document_type: 'other',
      uploaded_at: new Date().toISOString(),
      confidence_score: 0,
      needs_review: false,
      processed_at: new Date().toISOString(),
      ocr_result: {},
    });
  });

  it('uses the grouped upload endpoint when multiple images are selected together', async () => {
    const { container } = render(<DocumentUpload />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;

    const files = [
      new File(['page-1'], 'page-1.jpg', { type: 'image/jpeg' }),
      new File(['page-2'], 'page-2.png', { type: 'image/png' }),
    ];

    fireEvent.change(input, { target: { files } });

    await waitFor(() => expect(container.textContent).toContain('2 张照片待处理'));
    expect(uploadImageGroup).not.toHaveBeenCalled();

    const mergeButton = Array.from(container.querySelectorAll('button')).find((button) =>
      button.textContent?.includes('合并为 1 个文档上传')
    ) as HTMLButtonElement | undefined;

    expect(mergeButton).toBeDefined();
    fireEvent.click(mergeButton!);

    await waitFor(() => expect(uploadImageGroup).toHaveBeenCalledTimes(1));
    expect(uploadDocument).not.toHaveBeenCalled();
    expect(uploadImageGroup.mock.calls[0][0]).toHaveLength(2);
  });
});
