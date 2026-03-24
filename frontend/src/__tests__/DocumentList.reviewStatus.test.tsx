/* @vitest-environment jsdom */

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import DocumentList from '../components/documents/DocumentList';
import { useDocumentStore } from '../stores/documentStore';
import { DocumentType } from '../types/document';

const { getDocuments } = vi.hoisted(() => ({
  getDocuments: vi.fn(),
}));

const { confirmOCR } = vi.hoisted(() => ({
  confirmOCR: vi.fn(),
}));

const translations: Record<string, string> = {
  'documents.status.pendingReview': 'Pending review',
  'documents.status.transactionCreated': 'Transaction created',
  'documents.groups.all': 'All documents',
  'documents.groups.expense': 'Expenses',
  'documents.groups.employment': 'Employment',
  'documents.groups.self_employed': 'Self employed',
  'documents.groups.property': 'Property',
  'documents.groups.social_insurance': 'Social insurance',
  'documents.groups.tax_filing': 'Tax filing',
  'documents.groups.deductions': 'Deductions',
  'documents.groups.banking': 'Banking',
  'documents.groups.other': 'Other',
  'documents.types.receipt': 'Receipt',
  'documents.title': 'Documents',
  'documents.filters.needsReview': 'Needs review',
  'documents.review.confirmed': 'Reviewed',
  'documents.review.confirmedSuccess': 'Document confirmed',
  'documents.reviewActionFailed': 'Review failed',
  'documents.pageSize': 'Page size',
  'documents.perPage': 'per page',
  'common.export': 'Export',
};

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (
      key: string,
      options?: string | { defaultValue?: string; count?: number }
    ) => {
      const defaultValue =
        typeof options === 'string' ? options : options?.defaultValue;
      const template = translations[key] ?? defaultValue ?? key;

      if (typeof options === 'object' && options && typeof options.count === 'number') {
        return template.replace('{{count}}', String(options.count));
      }

      return template;
    },
    i18n: { language: 'en', resolvedLanguage: 'en' },
  }),
}));

vi.mock('../services/documentService', () => ({
  documentService: {
    getDocuments,
    deleteDocument: vi.fn(),
    downloadDocument: vi.fn(),
    confirmOCR,
  },
}));

vi.mock('../stores/aiAdvisorStore', () => ({
  useAIAdvisorStore: (
    selector: (state: { pushMessage: ReturnType<typeof vi.fn> }) => unknown
  ) => selector({ pushMessage: vi.fn() }),
}));

vi.mock('../stores/aiToastStore', () => ({
  aiToast: vi.fn(),
}));

vi.mock('../mobile/files', () => ({
  saveBlobWithNativeShare: vi.fn(),
}));

describe('DocumentList review status', () => {
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

  it('reports the filtered summary without rendering the legacy export UI', async () => {
    const onSummaryChange = vi.fn();

    getDocuments.mockResolvedValue({
      documents: [
        {
          id: 201,
          user_id: 7,
          document_type: DocumentType.RECEIPT,
          file_path: 'users/7/documents/receipt.png',
          file_name: 'receipt.png',
          file_size: 1024,
          mime_type: 'image/png',
          confidence_score: 0.98,
          needs_review: true,
          transaction_id: 998,
          ocr_result: { confirmed: true },
          ocr_status: 'completed',
          created_at: '2026-03-18T02:09:54.000Z',
          updated_at: '2026-03-18T02:09:54.000Z',
          processed_at: '2026-03-18T02:09:54.000Z',
        },
      ],
      total: 1,
    });

    render(
      <MemoryRouter>
        <DocumentList onSummaryChange={onSummaryChange} />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(onSummaryChange).toHaveBeenCalledWith({
        totalCount: 1,
        reviewCount: 1,
        confirmableIds: [],
      });
    });

    expect(screen.getAllByText('All documents').length).toBeGreaterThan(0);
    expect(screen.queryByText('ZIP')).not.toBeInTheDocument();
  });

  it('confirms a pending-review document directly from the list action', async () => {
    const pendingReviewDocument = {
      id: 301,
      user_id: 7,
      document_type: DocumentType.RECEIPT,
      file_path: 'users/7/documents/tmobile.pdf',
      file_name: 'T-Mobile.pdf',
      file_size: 240000,
      mime_type: 'application/pdf',
      confidence_score: 0.66,
      needs_review: true,
      transaction_id: null,
      ocr_result: { confirmed: false },
      ocr_status: 'completed',
      created_at: '2026-03-24T10:00:00.000Z',
      updated_at: '2026-03-24T10:00:00.000Z',
      processed_at: '2026-03-24T10:00:00.000Z',
    };

    getDocuments
      .mockResolvedValueOnce({
        documents: [pendingReviewDocument],
        total: 1,
      })
      .mockResolvedValueOnce({
        documents: [{ ...pendingReviewDocument, transaction_id: 998, ocr_result: { confirmed: true } }],
        total: 1,
      });

    render(
      <MemoryRouter>
        <DocumentList />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(getDocuments).toHaveBeenCalled();
    });

    const yearToggle = screen.getByRole('button', { expanded: false });
    fireEvent.click(yearToggle);

    confirmOCR.mockResolvedValue(undefined);

    const reviewButton = await screen.findByRole('button', { name: 'Reviewed' });
    fireEvent.click(reviewButton);

    await waitFor(() => {
      expect(confirmOCR).toHaveBeenCalledWith(301);
    });

    expect(getDocuments).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole('button', { name: 'Reviewed' })).not.toBeInTheDocument();
    expect(screen.getByText('Transaction created')).toBeInTheDocument();
  });

  it('confirms the document directly instead of opening the detail flow', async () => {
    const onDocumentSelect = vi.fn();
    const pendingReviewDocument = {
      id: 401,
      user_id: 7,
      document_type: DocumentType.RECEIPT,
      file_path: 'users/7/documents/versicherung.pdf',
      file_name: 'Versicherung.pdf',
      file_size: 240000,
      mime_type: 'application/pdf',
      confidence_score: 0.8,
      needs_review: true,
      transaction_id: null,
      ocr_result: { confirmed: false },
      ocr_status: 'completed',
      created_at: '2026-03-24T10:00:00.000Z',
      updated_at: '2026-03-24T10:00:00.000Z',
      processed_at: '2026-03-24T10:00:00.000Z',
    };

    getDocuments
      .mockResolvedValueOnce({
        documents: [pendingReviewDocument],
        total: 1,
      })
      .mockResolvedValueOnce({
        documents: [{ ...pendingReviewDocument, transaction_id: 18, ocr_result: { confirmed: true } }],
        total: 1,
      });
    confirmOCR.mockResolvedValue(undefined);

    render(
      <MemoryRouter>
        <DocumentList onDocumentSelect={onDocumentSelect} />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(getDocuments).toHaveBeenCalled();
    });

    const yearToggle = screen.getByRole('button', { expanded: false });
    fireEvent.click(yearToggle);

    const reviewButton = await screen.findByRole('button', { name: 'Reviewed' });
    fireEvent.click(reviewButton);

    await waitFor(() => {
      expect(confirmOCR).toHaveBeenCalledWith(401);
    });

    expect(onDocumentSelect).not.toHaveBeenCalled();
  });
});
