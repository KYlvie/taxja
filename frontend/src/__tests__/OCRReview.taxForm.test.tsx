/* @vitest-environment jsdom */

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

import OCRReview from '../components/documents/OCRReview';

const getDocument = vi.fn();
const getDocumentForReview = vi.fn();
const downloadDocument = vi.fn();
const correctOCR = vi.fn();
const confirmOCR = vi.fn();
const confirmTaxData = vi.fn();
const retryOcr = vi.fn();

vi.mock('react-i18next', () => ({
  initReactI18next: {
    type: '3rdParty',
    init: () => {},
  },
  useTranslation: () => ({
    t: (key: string, fallback?: string | { defaultValue?: string }) => {
      if (typeof fallback === 'string') return fallback;
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
    correctOCR: (...args: any[]) => correctOCR(...args),
    confirmOCR: (...args: any[]) => confirmOCR(...args),
    confirmTaxData: (...args: any[]) => confirmTaxData(...args),
    retryOcr: (...args: any[]) => retryOcr(...args),
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
  aiToast: vi.fn(),
}));

vi.mock('../components/documents/BescheidImport', () => ({
  default: () => null,
}));

describe('OCRReview tax-form mode', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    downloadDocument.mockResolvedValue(new Blob(['pdf']));
    getDocument.mockResolvedValue({
      id: 187,
      ocr_result: { _pipeline: { current_state: 'completed' } },
    });
    global.URL.createObjectURL = vi.fn(() => 'blob:test');
    global.URL.revokeObjectURL = vi.fn();

    getDocumentForReview.mockResolvedValue({
      document: {
        id: 187,
        user_id: 5,
        document_type: 'u1_form',
        file_path: '/tmp/u1.pdf',
        file_name: 'u1.pdf',
        file_size: 1234,
        mime_type: 'application/pdf',
        confidence_score: 0.25,
        needs_review: true,
        created_at: '2026-03-20T00:00:00Z',
        updated_at: '2026-03-20T00:00:00Z',
        raw_text: 'U1 data',
        ocr_result: {
          tax_year: 2019,
          kz_029: 13684.4,
        },
      },
      extracted_data: {
        tax_year: 2019,
        kz_029: 13684.4,
        confidence: {
          tax_year: 0.9,
          kz_029: 0.82,
        },
      },
      suggestions: [],
    });
  });

  it('uses tax-data confirmation flow instead of transaction creation for U1 forms', async () => {
    render(
      <MemoryRouter>
        <OCRReview documentId={187} />
      </MemoryRouter>
    );

    await waitFor(() => expect(getDocumentForReview).toHaveBeenCalledWith(187));

    expect(screen.queryByText('documents.review.transactionType')).not.toBeInTheDocument();
    expect(screen.getByText('KZ 029')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }));

    await waitFor(() => expect(correctOCR).toHaveBeenCalledWith(
      187,
      expect.objectContaining({
        tax_year: 2019,
        kz_029: 13684.4,
        _document_type: 'u1_form',
      })
    ));

    expect(correctOCR.mock.calls[0][1]).not.toHaveProperty('_transaction_type');
    await waitFor(() => expect(confirmOCR).toHaveBeenCalledWith(187));
    expect(confirmTaxData).not.toHaveBeenCalled();
  });

  it('shows tax-archive wording for E1A/E1B style tax attachments', async () => {
    getDocumentForReview.mockResolvedValueOnce({
      document: {
        id: 188,
        user_id: 5,
        document_type: 'e1a_beilage',
        file_path: '/tmp/e1a.pdf',
        file_name: 'e1a.pdf',
        file_size: 1234,
        mime_type: 'application/pdf',
        confidence_score: 0.33,
        needs_review: true,
        created_at: '2026-03-20T00:00:00Z',
        updated_at: '2026-03-20T00:00:00Z',
        raw_text: 'E1a data',
        ocr_result: {
          tax_year: 2025,
          betriebseinnahmen: 15000,
        },
      },
      extracted_data: {
        tax_year: 2025,
        betriebseinnahmen: 15000,
        confidence: {
          tax_year: 0.9,
          betriebseinnahmen: 0.85,
        },
      },
      suggestions: [],
    });

    render(
      <MemoryRouter>
        <OCRReview documentId={188} />
      </MemoryRouter>
    );

    await waitFor(() => expect(getDocumentForReview).toHaveBeenCalledWith(188));

    expect(screen.getByText('Confirm')).toBeInTheDocument();
    expect(screen.getByText(/税务档案/)).toBeInTheDocument();
    expect(screen.queryByText('documents.review.transactionType')).not.toBeInTheDocument();
  });
  it('hides generic invoice-style fields for Einkommensteuerbescheid reviews', async () => {
    getDocumentForReview.mockResolvedValueOnce({
      document: {
        id: 189,
        user_id: 5,
        document_type: 'einkommensteuerbescheid',
        file_path: '/tmp/bescheid.pdf',
        file_name: 'bescheid.pdf',
        file_size: 1234,
        mime_type: 'application/pdf',
        confidence_score: 0.95,
        needs_review: true,
        created_at: '2026-03-20T00:00:00Z',
        updated_at: '2026-03-20T00:00:00Z',
        raw_text: 'Bescheid data',
        ocr_result: {
          tax_year: 2023,
          festgesetzte_einkommensteuer: 8957.5,
          abgabennachforderung: 957.5,
        },
      },
      extracted_data: {
        tax_year: 2023,
        bescheid_datum: '2024-09-15',
        aktenzahl: 'FV-625207/2024',
        faellig_am: '2024-10-15',
        festgesetzte_einkommensteuer: 8957.5,
        abgabennachforderung: 957.5,
        amount: 957.5,
        date: '2024-09-15',
        merchant: 'Bundesministerium fuer Finanzen',
        issuer: 'Bundesministerium fuer Finanzen',
        recipient: 'DI Maria Steiner',
        description: 'Einkommensteuerbescheid fuer das Jahr 2023',
        document_date: '2024-09-15',
        document_year: 2024,
        year_basis: 'date',
        year_confidence: 0.85,
        confidence: {
          tax_year: 0.9,
          festgesetzte_einkommensteuer: 0.95,
          abgabennachforderung: 0.9,
        },
      },
      suggestions: [
        'Bitte ueberpruefen Sie das Feld "Datum".',
        'Bitte ueberpruefen Sie das Feld "Betrag".',
        'Bitte ueberpruefen Sie das Feld "issuer".',
        'Bitte ueberpruefen Sie das Feld "festgesetzte_einkommensteuer".',
      ],
    });

    render(
      <MemoryRouter>
        <OCRReview documentId={189} />
      </MemoryRouter>
    );

    await waitFor(() => expect(getDocumentForReview).toHaveBeenCalledWith(189));

    expect(screen.getByText('Tax Year')).toBeInTheDocument();
    expect(screen.getByText('Bescheid Datum')).toBeInTheDocument();
    expect(screen.getByText('Aktenzahl')).toBeInTheDocument();
    expect(screen.getByText('Faellig Am')).toBeInTheDocument();
    expect(screen.getByText('Festgesetzte Einkommensteuer')).toBeInTheDocument();
    expect(screen.getByText('Abgabennachforderung')).toBeInTheDocument();
    expect(screen.queryByText('Amount')).not.toBeInTheDocument();
    expect(screen.queryByText('Date')).not.toBeInTheDocument();
    expect(screen.queryByText('Merchant')).not.toBeInTheDocument();
    expect(screen.queryByText('Issuer')).not.toBeInTheDocument();
    expect(screen.queryByText('Recipient')).not.toBeInTheDocument();
    expect(screen.queryByText(/Bitte ueberpruefen Sie das Feld "Datum"\./)).not.toBeInTheDocument();
    expect(screen.queryByText(/Bitte ueberpruefen Sie das Feld "Betrag"\./)).not.toBeInTheDocument();
    expect(screen.queryByText(/Bitte ueberpruefen Sie das Feld "issuer"\./)).not.toBeInTheDocument();
    expect(screen.getByText(/Bitte ueberpruefen Sie das Feld "Festgesetzte Einkommensteuer"\./)).toBeInTheDocument();
  });
});
