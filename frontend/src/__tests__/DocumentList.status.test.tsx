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

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: string | { defaultValue?: string }) =>
      (
        {
          'documents.status.transactionCreated': 'Transaction created',
          'documents.status.contractProcessed': 'Contract processed',
          'documents.status.recognized': 'Recognized',
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
          'documents.list.name': 'File',
          'documents.list.type': 'Type',
          'documents.list.uploadDate': 'Upload date',
          'documents.list.size': 'Size',
          'documents.list.confidence': 'Confidence',
          'documents.list.status': 'Status',
          'documents.search.placeholder': 'Search',
          'documents.viewGrid': 'Grid view',
          'documents.viewList': 'List view',
          'documents.filters.clear': 'Clear filters',
          'documents.emptyGroup': 'Empty',
          'documents.types.receipt': 'Receipt',
          'documents.types.versicherungsbestaetigung': 'Insurance confirmation',
          'documents.typesShort.versicherungsbestaetigung': 'Insurance conf.',
          'documents.download': 'Download',
          'common.delete': 'Delete',
        } as Record<string, string>
      )[key] ??
      (typeof options === 'string' ? options : options?.defaultValue) ??
      key,
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

describe('DocumentList status', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.sessionStorage.clear();
    useDocumentStore.setState({
      documents: [],
      currentDocument: null,
      total: 0,
      loading: false,
      error: null,
      filters: {},
    });
  });

  it('shows transaction-created status when a document is already linked to a transaction', async () => {
    getDocuments.mockResolvedValue({
      documents: [
        {
          id: 118,
          user_id: 5,
          document_type: DocumentType.RECEIPT,
          file_path: 'users/5/documents/receipt.png',
          file_name: 'receipt.png',
          file_size: 1024,
          mime_type: 'image/png',
          confidence_score: 1,
          needs_review: false,
          transaction_id: 1151,
          ocr_result: { confirmed: true },
          ocr_status: 'completed',
          created_at: '2026-03-18T02:09:54.000Z',
          uploaded_at: '2026-03-18T02:09:54.000Z',
          updated_at: '2026-03-18T02:09:54.000Z',
          processed_at: '2026-03-18T02:09:54.000Z',
        },
      ],
      total: 1,
    });

    const { container } = render(
      <MemoryRouter>
        <DocumentList />
      </MemoryRouter>,
    );

    const yearToggle = await waitFor(() => {
      const element = container.querySelector<HTMLButtonElement>('.document-year-header--toggle');
      expect(element).not.toBeNull();
      return element!;
    });
    if (yearToggle.getAttribute('aria-expanded') === 'false') {
      fireEvent.click(yearToggle);
    }

    await waitFor(() => {
      expect(screen.getByText('Transaction created')).toBeInTheDocument();
    });

    expect(screen.queryByText('Recognized')).not.toBeInTheDocument();
  });

  it('does not show pending review for a high-confidence linked document even if OCR is not confirmed', async () => {
    getDocuments.mockResolvedValue({
      documents: [
        {
          id: 119,
          user_id: 5,
          document_type: DocumentType.INVOICE,
          file_path: 'users/5/documents/invoice.pdf',
          file_name: 'invoice.pdf',
          file_size: 1024,
          mime_type: 'application/pdf',
          confidence_score: 0.95,
          needs_review: false,
          transaction_id: 1152,
          ocr_result: { confirmed: false },
          ocr_status: 'completed',
          created_at: '2026-03-18T02:09:54.000Z',
          uploaded_at: '2026-03-18T02:09:54.000Z',
          updated_at: '2026-03-18T02:09:54.000Z',
          processed_at: '2026-03-18T02:09:54.000Z',
        },
      ],
      total: 1,
    });

    const { container } = render(
      <MemoryRouter>
        <DocumentList />
      </MemoryRouter>,
    );

    const yearToggle = await waitFor(() => {
      const element = container.querySelector<HTMLButtonElement>('.document-year-header--toggle');
      expect(element).not.toBeNull();
      return element!;
    });
    if (yearToggle.getAttribute('aria-expanded') === 'false') {
      fireEvent.click(yearToggle);
    }

    await waitFor(() => {
      expect(screen.getByText('Transaction created')).toBeInTheDocument();
    });

    expect(screen.queryByText('Pending review')).not.toBeInTheDocument();
  });

  it('renders short localized type pills while keeping the full translated label as a tooltip', async () => {
    getDocuments.mockResolvedValue({
      documents: [
        {
          id: 120,
          user_id: 5,
          document_type: DocumentType.VERSICHERUNGSBESTAETIGUNG,
          file_path: 'users/5/documents/insurance.pdf',
          file_name: 'insurance.pdf',
          file_size: 1024,
          mime_type: 'application/pdf',
          confidence_score: 1,
          needs_review: false,
          transaction_id: 1153,
          ocr_result: { confirmed: true },
          ocr_status: 'completed',
          created_at: '2026-03-18T02:09:54.000Z',
          uploaded_at: '2026-03-18T02:09:54.000Z',
          updated_at: '2026-03-18T02:09:54.000Z',
          processed_at: '2026-03-18T02:09:54.000Z',
        },
      ],
      total: 1,
    });

    const { container } = render(
      <MemoryRouter>
        <DocumentList />
      </MemoryRouter>,
    );

    const yearToggle = await waitFor(() => {
      const element = container.querySelector<HTMLButtonElement>('.document-year-header--toggle');
      expect(element).not.toBeNull();
      return element!;
    });
    if (yearToggle.getAttribute('aria-expanded') === 'false') {
      fireEvent.click(yearToggle);
    }

    const typePill = await waitFor(() => {
      const element = container.querySelector<HTMLElement>('.document-type-pill[title="Insurance confirmation"]');
      expect(element).not.toBeNull();
      expect(element).toHaveTextContent('Insurance conf.');
      return element!;
    });
    expect(typePill).toHaveAttribute('title', 'Insurance confirmation');

    const statusBadge = screen.getByText('Contract processed');
    expect(statusBadge).toHaveAttribute('title', 'Contract processed');
  });
});
