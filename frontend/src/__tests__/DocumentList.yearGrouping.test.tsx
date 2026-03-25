/* @vitest-environment jsdom */

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DocumentList from '../components/documents/DocumentList';
import { useDocumentStore } from '../stores/documentStore';
import { Document, DocumentType } from '../types/document';

const { getDocuments } = vi.hoisted(() => ({
  getDocuments: vi.fn(),
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: string | { defaultValue?: string }) =>
      (typeof options === 'string' ? options : options?.defaultValue) ??
      (
        {
          'documents.groups.all': 'All documents',
          'documents.groups.expense': 'Expenses',
          'documents.groups.employment': 'Employment',
          'documents.groups.self_employed': 'Self employed',
          'documents.groups.property': 'Property',
          'documents.groups.social_insurance': 'Insurance',
          'documents.groups.tax_filing': 'Tax filing',
          'documents.groups.deductions': 'Deductions',
          'documents.groups.banking': 'Banking',
          'documents.groups.other': 'Other',
          'documents.filters.allYears': 'All years',
          'documents.sortMode.label': 'Sort by',
          'documents.sortMode.uploadDate': 'Upload date',
          'documents.sortMode.documentDate': 'Document date',
          'documents.list.name': 'File',
          'documents.list.type': 'Type',
          'documents.list.uploadDate': 'Upload date',
          'documents.list.size': 'Size',
          'documents.list.confidence': 'Confidence',
          'documents.list.status': 'Status',
          'documents.pageSize': 'Page size',
          'documents.perPage': 'per page',
          'documents.search.placeholder': 'Search',
          'documents.viewGrid': 'Grid',
          'documents.viewList': 'List',
          'documents.filters.clear': 'Clear',
          'documents.filters.apply': 'Apply',
          'documents.emptyGroup': 'No documents in this group',
          'documents.types.rental_contract': 'Rental contract',
          'documents.download': 'Download',
          'common.delete': 'Delete',
          'transactions.type': 'Type',
          'transactions.deductible': 'Deductible',
          'transactions.filters.all': 'All',
          'transactions.filters.recurring': 'Recurring',
          'documents.needsReview': 'Pending review',
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

const rentalContractDocument: Document = {
  id: 901,
  user_id: 5,
  document_type: DocumentType.RENTAL_CONTRACT,
  file_path: 'users/5/documents/rental.pdf',
  file_name: 'Mietvertrag.pdf',
  file_size: 1024,
  mime_type: 'application/pdf',
  confidence_score: 0.95,
  needs_review: false,
  transaction_id: null,
  ocr_result: {
    start_date: '2024-01-15',
  },
  ocr_status: 'completed',
  created_at: '2026-03-24T10:00:00.000Z',
  updated_at: '2026-03-24T10:00:00.000Z',
  processed_at: '2026-03-24T10:00:00.000Z',
  document_date: '2024-01-15',
  document_year: 2024,
  year_basis: 'start_date',
  year_confidence: 0.85,
};

const bankStatementDocument: Document = {
  id: 902,
  user_id: 5,
  document_type: DocumentType.BANK_STATEMENT,
  file_path: 'users/5/documents/bank.pdf',
  file_name: 'Kontoauszug.pdf',
  file_size: 2048,
  mime_type: 'application/pdf',
  confidence_score: 0.95,
  needs_review: false,
  transaction_id: null,
  ocr_result: {
    statement_period: {
      start: '2024-06-26',
      end: '2024-12-19',
    },
    period_start: '2024-06-26',
    period_end: '2024-12-19',
  },
  ocr_status: 'completed',
  created_at: '2026-03-24T10:00:00.000Z',
  updated_at: '2026-03-24T10:00:00.000Z',
  processed_at: '2026-03-24T10:00:00.000Z',
  document_date: '2024-06-26',
  document_year: 2024,
  year_basis: 'statement_period_start',
  year_confidence: 1,
};

const taxYearOnlyDocument: Document = {
  id: 903,
  user_id: 5,
  document_type: DocumentType.EINKOMMENSTEUERBESCHEID,
  file_path: 'users/5/documents/bescheid.pdf',
  file_name: 'Bescheid.pdf',
  file_size: 1024,
  mime_type: 'application/pdf',
  confidence_score: 0.99,
  needs_review: false,
  transaction_id: null,
  ocr_result: {
    tax_year: 2024,
  },
  ocr_status: 'completed',
  created_at: '2026-03-24T10:00:00.000Z',
  updated_at: '2026-03-24T10:00:00.000Z',
  processed_at: '2026-03-24T10:00:00.000Z',
  document_year: 2024,
  year_basis: 'tax_year',
  year_confidence: 1,
};

describe('DocumentList year grouping', () => {
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
      sortMode: 'upload_date',
    });
  });

  it('groups by upload year when upload-date sorting is selected', async () => {
    getDocuments.mockResolvedValue({
      documents: [rentalContractDocument],
      total: 1,
    });

    render(
      <MemoryRouter>
        <DocumentList />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '2026' })).toBeInTheDocument();
    });

    expect(screen.queryByRole('button', { name: '2024' })).not.toBeInTheDocument();
  });

  it('uses the resolved document year when document-date sorting is selected', async () => {
    useDocumentStore.setState({ sortMode: 'document_date' });
    getDocuments.mockResolvedValue({
      documents: [rentalContractDocument],
      total: 1,
    });

    render(
      <MemoryRouter>
        <DocumentList />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '2024' })).toBeInTheDocument();
    });

    expect(screen.queryByRole('button', { name: '2026' })).not.toBeInTheDocument();
  });

  it('groups bank statements by the earliest statement period year in document-date mode', async () => {
    useDocumentStore.setState({ sortMode: 'document_date' });
    getDocuments.mockResolvedValue({
      documents: [bankStatementDocument],
      total: 1,
    });

    render(
      <MemoryRouter>
        <DocumentList />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '2024' })).toBeInTheDocument();
    });

    expect(screen.queryByRole('button', { name: '2026' })).not.toBeInTheDocument();
  });

  it('uses the authoritative document_year when no exact document_date exists', async () => {
    useDocumentStore.setState({ sortMode: 'document_date' });
    getDocuments.mockResolvedValue({
      documents: [taxYearOnlyDocument],
      total: 1,
    });

    render(
      <MemoryRouter>
        <DocumentList />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '2024' })).toBeInTheDocument();
    });

    expect(screen.queryByRole('button', { name: '2026' })).not.toBeInTheDocument();
  });

  it('keeps an opened year group expanded after remounting the document list', async () => {
    getDocuments.mockResolvedValue({
      documents: [rentalContractDocument],
      total: 1,
    });

    const firstRender = render(
      <MemoryRouter>
        <DocumentList />
      </MemoryRouter>,
    );

    const yearButtons = await screen.findAllByRole('button', { name: /2026/ });
    const yearButton = yearButtons.find((button) =>
      button.className.includes('document-year-header--toggle'),
    );
    expect(yearButton).toBeDefined();
    expect(screen.queryByText('Mietvertrag.pdf')).not.toBeInTheDocument();

    fireEvent.click(yearButton!);

    expect(await screen.findByText('Mietvertrag.pdf')).toBeInTheDocument();

    firstRender.unmount();

    render(
      <MemoryRouter>
        <DocumentList />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('Mietvertrag.pdf')).toBeInTheDocument();
    });
  });
});
