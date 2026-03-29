/* @vitest-environment jsdom */

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

import OCRReview from '../components/documents/OCRReview';

const getDocument = vi.fn();
const getDocumentForReview = vi.fn();
const downloadDocument = vi.fn();
const retryOcr = vi.fn();
const confirmTaxData = vi.fn();

vi.mock('react-i18next', () => ({
  initReactI18next: {
    type: '3rdParty',
    init: () => undefined,
  },
  useTranslation: () => ({
    t: (key: string, fallback?: string | { defaultValue?: string }) => {
      if (typeof fallback === 'string') return fallback;
      if (fallback && typeof fallback === 'object' && typeof fallback.defaultValue === 'string') {
        return fallback.defaultValue;
      }
      return key;
    },
    i18n: {
      language: 'en',
      resolvedLanguage: 'en',
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

vi.mock('../services/aiService', () => ({
  aiService: {
    explainOCRResult: vi.fn(),
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

vi.mock('../components/ai/AIResponse', () => ({
  default: ({ content }: { content: string }) => <div>{content}</div>,
}));

vi.mock('../components/documents/BescheidImport', () => ({
  default: () => null,
}));

describe('OCRReview contract-sensitive purchase and rental flows', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    downloadDocument.mockResolvedValue(new Blob(['pdf']));
    global.URL.createObjectURL = vi.fn(() => 'blob:test');
    global.URL.revokeObjectURL = vi.fn();

    getDocumentForReview.mockResolvedValue({
      document: {
        id: 124,
        user_id: 5,
        document_type: 'purchase_contract',
        file_path: '/tmp/car-contract.pdf',
        file_name: 'car-contract.pdf',
        file_size: 1234,
        mime_type: 'application/pdf',
        confidence_score: 0.92,
        needs_review: false,
        created_at: '2026-03-18T00:00:00Z',
        updated_at: '2026-03-18T00:00:00Z',
        raw_text: '',
        ocr_result: {
          purchase_contract_kind: 'asset',
          user_contract_role: 'buyer',
          contract_role_resolution: {
            candidate: 'buyer',
            confidence: 0.91,
            source: 'party_name_match',
            evidence: ['Matched contract party to user full name.'],
            strict_would_block: false,
            mode: 'shadow',
          },
        },
      },
      extracted_data: {
        purchase_contract_kind: 'asset',
        asset_name: 'Volkswagen Golf 1.6 TDI Comfortline',
        asset_type: 'vehicle',
        purchase_price: 13800,
        purchase_date: '2026-03-18',
        buyer_name: 'FENGHONG ZHANG',
        seller_name: 'Markus Steiner',
        first_registration_date: '2018-04-15',
        vehicle_identification_number: 'WVWZZZAUZJW123456',
        license_plate: 'W-234AB',
        mileage_km: 126480,
        is_used_asset: true,
        previous_owners: 2,
        confidence: {},
      },
      suggestions: [],
    });
  });

  it('renders asset-specific purchase contract fields instead of property fields', async () => {
    render(
      <MemoryRouter>
        <OCRReview documentId={124} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(getDocumentForReview).toHaveBeenCalledWith(124);
    });

    expect(screen.getByDisplayValue('Volkswagen Golf 1.6 TDI Comfortline')).toBeInTheDocument();
    expect(screen.getByDisplayValue('vehicle')).toBeInTheDocument();
    expect(screen.getByDisplayValue('WVWZZZAUZJW123456')).toBeInTheDocument();
    expect(screen.queryByDisplayValue('Argentinierstrasse 21, 1234 Wien')).not.toBeInTheDocument();
  });

  it('renders the contract role selector and inference summary for purchase contracts', async () => {
    const { container } = render(
      <MemoryRouter>
        <OCRReview documentId={124} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(getDocumentForReview).toHaveBeenCalledWith(124);
    });

    expect(screen.getAllByRole('combobox').length).toBeGreaterThan(0);
    expect(container.querySelector('.review-contract-role-card')).not.toBeNull();
    expect(screen.getByText('Matched contract party to user full name.')).toBeInTheDocument();
  });

  it('opens linked transactions via the inline callback instead of leaving the document page', async () => {
    const onOpenTransaction = vi.fn();

    getDocumentForReview.mockResolvedValueOnce({
      document: {
        id: 126,
        user_id: 5,
        document_type: 'invoice',
        file_path: '/tmp/invoice.pdf',
        file_name: 'invoice.pdf',
        file_size: 1234,
        mime_type: 'application/pdf',
        confidence_score: 0.94,
        needs_review: false,
        transaction_id: 778,
        created_at: '2026-03-18T00:00:00Z',
        updated_at: '2026-03-18T00:00:00Z',
        raw_text: '',
        ocr_result: {},
      },
      extracted_data: {
        amount: 599,
        description: 'Invoice from JetBrains',
        confidence: {},
      },
      suggestions: [],
    });

    render(
      <MemoryRouter>
        <OCRReview documentId={126} onOpenTransaction={onOpenTransaction} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(getDocumentForReview).toHaveBeenCalledWith(126);
    });

    fireEvent.click(screen.getByRole('button', { name: 'documents.linkedEntity.open' }));
    expect(onOpenTransaction).toHaveBeenCalledWith(778);
  });

  it('renders rental role controls and a shadow warning for tenant rental contracts', async () => {
    getDocumentForReview.mockResolvedValueOnce({
      document: {
        id: 125,
        user_id: 5,
        document_type: 'rental_contract',
        file_path: '/tmp/mietvertrag.pdf',
        file_name: 'mietvertrag.pdf',
        file_size: 1234,
        mime_type: 'application/pdf',
        confidence_score: 0.88,
        needs_review: false,
        created_at: '2026-03-18T00:00:00Z',
        updated_at: '2026-03-18T00:00:00Z',
        raw_text: '',
        ocr_result: {
          user_contract_role: 'tenant',
          contract_role_resolution: {
            candidate: 'tenant',
            confidence: 0.87,
            source: 'party_name_match',
            evidence: ['Matched contract party to user full name.'],
            strict_would_block: true,
            mode: 'shadow',
          },
        },
      },
      extracted_data: {
        monthly_rent: 1200,
        property_address: 'Argentinierstrasse 21, 1234 Wien',
        tenant_name: 'FENGHONG ZHANG',
        landlord_name: 'OOHK Properties GmbH',
        start_date: '2026-03-01',
        confidence: {},
      },
      suggestions: [],
    });

    const { container } = render(
      <MemoryRouter>
        <OCRReview documentId={125} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(getDocumentForReview).toHaveBeenCalledWith(125);
    });

    expect(screen.getAllByRole('combobox').length).toBeGreaterThan(0);
    expect(screen.getByText('Matched contract party to user full name.')).toBeInTheDocument();
    expect(container.querySelector('.review-warning-compact')).not.toBeNull();
  });

  it('renders landlord rental contract fields with landlord role selected', async () => {
    getDocumentForReview.mockResolvedValueOnce({
      document: {
        id: 127,
        user_id: 5,
        document_type: 'rental_contract',
        file_path: '/tmp/vermieterin-mietvertrag.pdf',
        file_name: 'vermieterin-mietvertrag.pdf',
        file_size: 1234,
        mime_type: 'application/pdf',
        confidence_score: 0.9,
        needs_review: false,
        created_at: '2026-03-18T00:00:00Z',
        updated_at: '2026-03-18T00:00:00Z',
        raw_text: '',
        ocr_result: {
          user_contract_role: 'landlord',
          contract_role_resolution: {
            candidate: 'landlord',
            confidence: 0.94,
            source: 'party_name_match',
            evidence: ['Extracted landlord name matches the user profile.'],
            strict_would_block: false,
            mode: 'shadow',
          },
        },
      },
      extracted_data: {
        monthly_rent: 1035,
        property_address: 'Praterstrasse 40/12, 1020 Wien',
        tenant_name: 'Mag. Stefan Berger',
        landlord_name: 'DI Maria Steiner',
        start_date: '2024-01-01',
        end_date: '2026-12-31',
        contract_type: 'unbefristet',
        betriebskosten: 210,
        deposit_amount: 3000,
        confidence: {},
      },
      suggestions: [],
    });

    render(
      <MemoryRouter>
        <OCRReview documentId={127} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(getDocumentForReview).toHaveBeenCalledWith(127);
    });

    expect(screen.getAllByRole('combobox').length).toBeGreaterThan(0);
    expect(screen.getByDisplayValue('Praterstrasse 40/12, 1020 Wien')).toBeInTheDocument();
    expect(screen.getByDisplayValue('1035')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Mag. Stefan Berger')).toBeInTheDocument();
    expect(screen.getByDisplayValue('DI Maria Steiner')).toBeInTheDocument();
    expect(screen.getByDisplayValue('210')).toBeInTheDocument();
    expect(screen.getByDisplayValue('3000')).toBeInTheDocument();
    expect(screen.getByText('Extracted landlord name matches the user profile.')).toBeInTheDocument();
  });
});
