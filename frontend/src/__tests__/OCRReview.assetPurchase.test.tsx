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

    expect(screen.getAllByText('资产购置合同').length).toBeGreaterThan(0);
    expect(screen.getByText('资产名称')).toBeInTheDocument();
    expect(screen.getByText('资产类型')).toBeInTheDocument();
    expect(screen.getByText('车架号 / VIN')).toBeInTheDocument();
    expect(screen.queryByText('房产地址')).not.toBeInTheDocument();
    expect(screen.queryByText('建筑价值')).not.toBeInTheDocument();
    expect(screen.queryByText('不动产转让税')).not.toBeInTheDocument();
  });

  it('renders the contract role selector and inference summary for purchase contracts', async () => {
    render(
      <MemoryRouter>
        <OCRReview documentId={124} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(getDocumentForReview).toHaveBeenCalledWith(124);
    });

    expect(screen.getByText('我的身份')).toBeInTheDocument();
    expect(screen.getByDisplayValue('我是买方')).toBeInTheDocument();
    expect(screen.getByText('合同身份判断')).toBeInTheDocument();
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

  it('renders rental role controls and a shadow warning for rental contracts', async () => {
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

    expect(screen.getByDisplayValue('我是租客')).toBeInTheDocument();
    expect(screen.getByText('Matched contract party to user full name.')).toBeInTheDocument();
    expect(container.querySelector('.review-warning-compact')).not.toBeNull();
  });
});
