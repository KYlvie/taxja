/* @vitest-environment jsdom */

import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DocumentList from '../components/documents/DocumentList';
import { useDocumentStore } from '../stores/documentStore';
import { DocumentType } from '../types/document';

const { getDocuments } = vi.hoisted(() => ({
  getDocuments: vi.fn(),
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: string | { defaultValue?: string }) =>
      (typeof options === 'string' ? options : options?.defaultValue) ??
      (
        {
          'documents.status.processing': 'Processing',
          'documents.status.recognized': 'Recognized',
          'documents.failed': 'Failed',
          'documents.groups.all': 'All documents',
          'documents.groups.expense': 'Receipts',
          'documents.groups.employment': 'Employment',
          'documents.groups.self_employed': 'Self employed',
          'documents.groups.property': 'Property',
          'documents.groups.social_insurance': 'Insurance',
          'documents.groups.tax_filing': 'Tax filing',
          'documents.groups.deductions': 'Deductions',
          'documents.groups.banking': 'Banking',
          'documents.groups.other': 'Other',
          'documents.list.name': 'File',
          'documents.list.type': 'Type',
          'documents.list.uploadDate': 'Date',
          'documents.list.size': 'Size',
          'documents.list.confidence': 'Confidence',
          'documents.list.status': 'Status',
          'documents.search.placeholder': 'Search',
          'documents.viewGrid': 'Grid',
          'documents.viewList': 'List',
          'documents.filters.clear': 'Clear',
          'documents.emptyGroup': 'Empty',
          'documents.types.other': 'Other',
          'documents.download': 'Download',
          'common.delete': 'Delete',
        } as Record<string, string>
      )[key] ?? key,
    i18n: { language: 'en', resolvedLanguage: 'en' },
  }),
}));

vi.mock('../services/documentService', () => ({
  documentService: {
    getDocuments,
    deleteDocument: vi.fn(),
    downloadDocument: vi.fn(),
  },
}));

vi.mock('../stores/aiAdvisorStore', () => ({
  useAIAdvisorStore: (
    selector: (state: { pushMessage: ReturnType<typeof vi.fn> }) => unknown
  ) => selector({ pushMessage: vi.fn() }),
}));

vi.mock('../mobile/files', () => ({
  saveBlobWithNativeShare: vi.fn(),
}));

describe('DocumentList processing refresh', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useDocumentStore.setState({
      documents: [],
      currentDocument: null,
      total: 0,
      loading: false,
      error: null,
      filters: {},
    });
  });

  it('auto-refreshes visible processing documents until a terminal result arrives', async () => {
    getDocuments
      .mockResolvedValueOnce({
        documents: [
          {
            id: 325,
            user_id: 5,
            document_type: DocumentType.OTHER,
            file_path: 'users/5/documents/uploaded.pdf',
            file_name: 'Screenshot 2026-03-17 010627.png',
            file_size: 1024,
            mime_type: 'application/pdf',
            confidence_score: 0.8,
            needs_review: false,
            ocr_result: { _pipeline: { current_state: 'finalizing' } },
            ocr_status: 'processing',
            created_at: '2026-03-23T23:38:23.000Z',
            updated_at: '2026-03-24T00:12:04.000Z',
          },
        ],
        total: 1,
      })
      .mockResolvedValueOnce({
        documents: [
          {
            id: 325,
            user_id: 5,
            document_type: DocumentType.OTHER,
            file_path: 'users/5/documents/uploaded.pdf',
            file_name: 'Screenshot 2026-03-17 010627.png',
            file_size: 1024,
            mime_type: 'application/pdf',
            confidence_score: 0.95,
            needs_review: false,
            ocr_status: 'completed',
            created_at: '2026-03-23T23:38:23.000Z',
            updated_at: '2026-03-24T00:14:20.000Z',
            processed_at: '2026-03-24T00:14:20.000Z',
          },
        ],
        total: 1,
      });

    render(
      <MemoryRouter>
        <DocumentList />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('Processing')).toBeInTheDocument();
      expect(screen.getAllByText('80%').length).toBeGreaterThan(0);
    });

    await waitFor(() => expect(getDocuments).toHaveBeenCalledTimes(2), { timeout: 7000 });
    await waitFor(() => {
      expect(screen.getByText('Recognized')).toBeInTheDocument();
      expect(screen.getAllByText('95%').length).toBeGreaterThan(0);
    });
  }, 15000);
});
