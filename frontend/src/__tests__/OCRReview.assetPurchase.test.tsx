/* @vitest-environment jsdom */

import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

import OCRReview from '../components/documents/OCRReview';

const getDocument = vi.fn();
const getDocumentForReview = vi.fn();
const downloadDocument = vi.fn();

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

describe('OCRReview asset purchase contracts', () => {
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

    expect(screen.getByText('资产购置合同')).toBeInTheDocument();
    expect(screen.getByText('资产名称')).toBeInTheDocument();
    expect(screen.getByText('资产类型')).toBeInTheDocument();
    expect(screen.getByText('车架号 / VIN')).toBeInTheDocument();
    expect(screen.queryByText('房产地址')).not.toBeInTheDocument();
    expect(screen.queryByText('建筑价值')).not.toBeInTheDocument();
    expect(screen.queryByText('不动产转让税')).not.toBeInTheDocument();
  });
});
