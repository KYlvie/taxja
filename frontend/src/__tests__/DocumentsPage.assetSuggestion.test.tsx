/* @vitest-environment jsdom */

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes, useParams } from 'react-router-dom';

import DocumentsPage from '../pages/DocumentsPage';

const getDocument = vi.fn();
const confirmAsset = vi.fn();
const downloadDocument = vi.fn();
const getProperty = vi.fn();

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

vi.mock('../components/documents/DocumentUpload', () => ({ default: () => <div data-testid="doc-upload" /> }));
vi.mock('../components/documents/DocumentList', () => ({ default: () => <div data-testid="doc-list" /> }));
vi.mock('../components/documents/OCRReview', () => ({ default: () => <div data-testid="ocr-review" /> }));
vi.mock('../components/documents/EmployerReviewPanel', () => ({ default: () => null }));
vi.mock('../components/documents/BescheidImport', () => ({ default: () => null }));
vi.mock('../components/documents/E1FormImport', () => ({ default: () => null }));
vi.mock('../components/documents/SuggestionCardFactory', () => ({
  default: ({ onConfirmAsset }: any) => (
    <button
      type="button"
      onClick={() =>
        onConfirmAsset?.({
          put_into_use_date: '2026-03-20',
          business_use_percentage: 80,
          gwg_elected: false,
          depreciation_method: 'degressive',
          degressive_afa_rate: 0.25,
        })
      }
    >
      trigger asset confirm
    </button>
  ),
}));

vi.mock('../services/documentService', () => ({
  documentService: {
    getDocument: (...args: any[]) => getDocument(...args),
    confirmAsset: (...args: any[]) => confirmAsset(...args),
    downloadDocument: (...args: any[]) => downloadDocument(...args),
  },
}));

vi.mock('../services/propertyService', () => ({
  propertyService: {
    getProperty: (...args: any[]) => getProperty(...args),
  },
}));

vi.mock('../services/transactionService', () => ({
  transactionService: {
    getById: vi.fn(),
    update: vi.fn(),
  },
}));

vi.mock('../mobile/files', () => ({
  saveBlobWithNativeShare: vi.fn(),
}));

const refreshProperties = vi.fn();
const refreshDashboard = vi.fn();

vi.mock('../stores/refreshStore', () => ({
  useRefreshStore: {
    getState: () => ({
      refreshTransactions: vi.fn(),
      refreshDashboard,
      refreshProperties,
      refreshRecurring: vi.fn(),
    }),
  },
}));

vi.mock('../stores/aiToastStore', () => ({
  aiToast: vi.fn(),
}));

describe('DocumentsPage asset suggestion confirmation', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    getDocument
      .mockResolvedValueOnce({
        id: 201,
        user_id: 1,
        document_type: 'invoice',
        file_path: '/tmp/asset.pdf',
        file_name: 'asset.pdf',
        file_size: 100,
        mime_type: 'application/pdf',
        confidence_score: 0.93,
        needs_review: false,
        created_at: '2026-03-18T00:00:00Z',
        updated_at: '2026-03-18T00:00:00Z',
        ocr_result: {
          import_suggestion: {
            type: 'create_asset',
            status: 'pending',
            data: {
              asset_type: 'computer',
              name: 'Laptop',
            },
          },
        },
      })
      .mockResolvedValueOnce({
        id: 201,
        user_id: 1,
        document_type: 'invoice',
        file_path: '/tmp/asset.pdf',
        file_name: 'asset.pdf',
        file_size: 100,
        mime_type: 'application/pdf',
        confidence_score: 0.93,
        needs_review: false,
        created_at: '2026-03-18T00:00:00Z',
        updated_at: '2026-03-18T00:00:00Z',
        ocr_result: {
          asset_outcome: {
            type: 'create_asset',
            status: 'confirmed',
            asset_id: 'asset-1',
            decision: 'create_asset_suggestion',
            source: 'user_confirmation',
          },
        },
      });

    confirmAsset.mockResolvedValue({ asset_id: 'asset-1' });
    getProperty.mockResolvedValue({
      id: 'asset-1',
      user_id: 1,
      asset_type: 'computer',
      name: 'Laptop',
      property_type: 'rental',
      rental_percentage: 100,
      address: '',
      street: '',
      city: '',
      postal_code: '',
      purchase_date: '2026-03-10',
      purchase_price: 1499,
      building_value: 1249.17,
      depreciation_rate: 0.3333,
      put_into_use_date: '2026-03-20',
      business_use_percentage: 80,
      depreciation_method: 'degressive',
      ifb_candidate: true,
      annual_depreciation: 416.39,
      remaining_value: 832.78,
      status: 'active',
      created_at: '2026-03-18T00:00:00Z',
      updated_at: '2026-03-18T00:00:00Z',
    });
    downloadDocument.mockResolvedValue(new Blob(['pdf']));
    global.URL.createObjectURL = vi.fn(() => 'blob:test');
    global.URL.revokeObjectURL = vi.fn();
  });

  const AssetRoute = () => {
    const { propertyId } = useParams();
    return <div data-testid="asset-route">asset:{propertyId}</div>;
  };

  it('forwards the asset confirmation payload to documentService.confirmAsset and navigates to the asset detail page', async () => {
    render(
      <MemoryRouter initialEntries={['/documents/201']}>
        <Routes>
          <Route path="/documents/:documentId" element={<DocumentsPage />} />
          <Route path="/properties/:propertyId" element={<AssetRoute />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => expect(getDocument).toHaveBeenCalledWith(201));

    fireEvent.click(screen.getByRole('button', { name: 'trigger asset confirm' }));

    await waitFor(() => {
      expect(confirmAsset).toHaveBeenCalledWith(201, {
        put_into_use_date: '2026-03-20',
        business_use_percentage: 80,
        gwg_elected: false,
        depreciation_method: 'degressive',
        degressive_afa_rate: 0.25,
      });
    });

    expect(refreshProperties).toHaveBeenCalled();
    expect(refreshDashboard).toHaveBeenCalled();
    await waitFor(() => {
      expect(screen.getByTestId('asset-route')).toHaveTextContent('asset:asset-1');
    });
  });

  it('shows a linked asset summary when the document already has a final asset outcome', async () => {
    getDocument.mockReset();
    getDocument.mockResolvedValue({
      id: 201,
      user_id: 1,
      document_type: 'invoice',
      file_path: '/tmp/asset.pdf',
      file_name: 'asset.pdf',
      file_size: 100,
      mime_type: 'application/pdf',
      confidence_score: 0.93,
      needs_review: false,
      created_at: '2026-03-18T00:00:00Z',
      updated_at: '2026-03-18T00:00:00Z',
      ocr_result: {
        asset_outcome: {
          type: 'create_asset',
          status: 'confirmed',
          asset_id: 'asset-1',
          decision: 'create_asset_suggestion',
          source: 'user_confirmation',
        },
      },
    });

    render(
      <MemoryRouter initialEntries={['/documents/201']}>
        <Routes>
          <Route path="/documents/:documentId" element={<DocumentsPage />} />
          <Route path="/properties/:propertyId" element={<AssetRoute />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => expect(getProperty).toHaveBeenCalledWith('asset-1'));
    expect(screen.getByText('已创建资产')).toBeInTheDocument();
    expect(screen.getByText('Laptop')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '前往查看资产' })).toBeInTheDocument();
  });
  it('falls back to legacy confirmed asset suggestions for linked asset display', async () => {
    getDocument.mockReset();
    getDocument.mockResolvedValue({
      id: 201,
      user_id: 1,
      document_type: 'invoice',
      file_path: '/tmp/asset.pdf',
      file_name: 'asset.pdf',
      file_size: 100,
      mime_type: 'application/pdf',
      confidence_score: 0.93,
      needs_review: false,
      created_at: '2026-03-18T00:00:00Z',
      updated_at: '2026-03-18T00:00:00Z',
      ocr_result: {
        import_suggestion: {
          type: 'create_asset',
          status: 'confirmed',
          asset_id: 'asset-1',
          data: {
            asset_type: 'computer',
            name: 'Laptop',
          },
        },
      },
    });

    render(
      <MemoryRouter initialEntries={['/documents/201']}>
        <Routes>
          <Route path="/documents/:documentId" element={<DocumentsPage />} />
          <Route path="/properties/:propertyId" element={<AssetRoute />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => expect(getProperty).toHaveBeenCalledWith('asset-1'));
    expect(screen.getByText('Laptop')).toBeInTheDocument();
  });
});
