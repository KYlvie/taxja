/* @vitest-environment jsdom */

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import DocumentsPage from '../pages/DocumentsPage';

const getDocument = vi.fn();
const getDocuments = vi.fn();
const confirmInsuranceRecurring = vi.fn();
const downloadDocument = vi.fn();
const getProperty = vi.fn();
const suggestionCardFactorySpy = vi.fn();
const refreshTransactions = vi.fn();
const refreshRecurring = vi.fn();
const refreshDashboard = vi.fn();
const aiToast = vi.fn();

vi.mock('react-i18next', () => ({
  initReactI18next: { type: '3rdParty', init: () => {} },
  useTranslation: () => ({
    t: (key: string, fallback?: string | { defaultValue?: string; reason?: string }) => {
      if (typeof fallback === 'string') return fallback;
      if (fallback && typeof fallback === 'object') {
        if (typeof fallback.defaultValue === 'string') {
          return fallback.defaultValue.replace('{{reason}}', String(fallback.reason ?? ''));
        }
      }
      return key;
    },
    i18n: { language: 'en', resolvedLanguage: 'en' },
  }),
}));

vi.mock('../components/documents/DocumentUpload', () => ({ default: () => <div data-testid="doc-upload" /> }));
vi.mock('../components/documents/DocumentList', () => ({ default: () => <div data-testid="doc-list" /> }));
vi.mock('../components/documents/OCRReview', () => ({ default: () => <div data-testid="ocr-review" /> }));
vi.mock('../components/documents/EmployerReviewPanel', () => ({ default: () => null }));
vi.mock('../components/documents/BescheidImport', () => ({ default: () => null }));
vi.mock('../components/documents/E1FormImport', () => ({ default: () => null }));
vi.mock('../documents/presentation/featureFlag', () => ({
  default: () => false,
}));
vi.mock('../components/documents/SuggestionCardFactory', () => ({
  default: (props: any) => {
    suggestionCardFactorySpy(props);
    return (
      <button
        type="button"
        onClick={() =>
          props.onConfirmInsuranceRecurring?.({
            business_use_percentage: 60,
            override_payment_amount: 89.25,
            override_payment_frequency: 'monthly',
            archive_only: props.suggestion?.type === 'archive_insurance_document',
            archive_reason_code: props.suggestion?.type === 'archive_insurance_document' ? 'not_relevant' : undefined,
          })
        }
      >
        trigger insurance confirm
      </button>
    );
  },
}));

vi.mock('../services/documentService', () => ({
  documentService: {
    getDocument: (...args: any[]) => getDocument(...args),
    getDocuments: (...args: any[]) => getDocuments(...args),
    confirmInsuranceRecurring: (...args: any[]) => confirmInsuranceRecurring(...args),
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

vi.mock('../stores/refreshStore', () => ({
  useRefreshStore: {
    getState: () => ({
      refreshTransactions,
      refreshDashboard,
      refreshProperties: vi.fn(),
      refreshRecurring,
    }),
  },
}));

vi.mock('../stores/aiToastStore', () => ({
  aiToast: (...args: any[]) => aiToast(...args),
}));

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={['/documents/301']}>
      <Routes>
        <Route path="/documents/:documentId" element={<DocumentsPage />} />
      </Routes>
    </MemoryRouter>,
  );

describe('DocumentsPage insurance suggestion flow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    downloadDocument.mockResolvedValue(new Blob(['pdf']));
    getDocuments.mockResolvedValue({ documents: [{ id: 301 }] });
    getProperty.mockResolvedValue(null);
    global.URL.createObjectURL = vi.fn(() => 'blob:test');
    global.URL.revokeObjectURL = vi.fn();
  });

  it('forwards the insurance confirmation payload and refreshes recurring state', async () => {
    getDocument
      .mockResolvedValueOnce({
        id: 301,
        user_id: 1,
        document_type: 'invoice',
        file_path: '/tmp/insurance.pdf',
        file_name: 'insurance.pdf',
        file_size: 100,
        mime_type: 'application/pdf',
        confidence_score: 0.95,
        needs_review: false,
        created_at: '2026-03-28T00:00:00Z',
        updated_at: '2026-03-28T00:00:00Z',
        ocr_result: {
          import_suggestion: {
            type: 'create_insurance_recurring',
            status: 'pending',
            data: {
              insurer_name: 'Generali',
              insurance_type: 'KFZ',
              payment_amount: 89.25,
              payment_frequency: 'monthly',
              input_fields: ['business_use_percentage'],
            },
          },
        },
      })
      .mockResolvedValueOnce({
        id: 301,
        user_id: 1,
        document_type: 'invoice',
        file_path: '/tmp/insurance.pdf',
        file_name: 'insurance.pdf',
        file_size: 100,
        mime_type: 'application/pdf',
        confidence_score: 0.95,
        needs_review: false,
        created_at: '2026-03-28T00:00:00Z',
        updated_at: '2026-03-28T00:00:00Z',
        ocr_result: {
          import_suggestion: {
            type: 'create_insurance_recurring',
            status: 'confirmed',
            recurring_id: 77,
          },
        },
      });
    confirmInsuranceRecurring.mockResolvedValue({ recurring_id: 77 });

    renderPage();

    await waitFor(() => expect(getDocument).toHaveBeenCalledWith(301));
    fireEvent.click(screen.getByRole('button', { name: 'trigger insurance confirm' }));

    await waitFor(() => {
      expect(confirmInsuranceRecurring).toHaveBeenCalledWith(301, {
        business_use_percentage: 60,
        override_payment_amount: 89.25,
        override_payment_frequency: 'monthly',
        archive_only: false,
        archive_reason_code: undefined,
      });
    });

    expect(refreshRecurring).toHaveBeenCalled();
    expect(refreshTransactions).toHaveBeenCalled();
    expect(refreshDashboard).toHaveBeenCalled();
    expect(aiToast).toHaveBeenCalledWith('Insurance recurring created', 'success');
  });

  it('renders the archive-only outcome banner instead of the suggestion card', async () => {
    getDocument.mockResolvedValue({
      id: 301,
      user_id: 1,
      document_type: 'invoice',
      file_path: '/tmp/insurance.pdf',
      file_name: 'insurance.pdf',
      file_size: 100,
      mime_type: 'application/pdf',
      confidence_score: 0.95,
      needs_review: false,
      created_at: '2026-03-28T00:00:00Z',
      updated_at: '2026-03-28T00:00:00Z',
      ocr_result: {
        import_suggestion: {
          type: 'archive_insurance_document',
          status: 'confirmed',
          resolution: 'archive_only',
          archive_reason_code: 'not_relevant',
          data: {
            insurer_name: 'GRAWE',
          },
        },
      },
    });

    renderPage();

    await waitFor(() => expect(getDocument).toHaveBeenCalledWith(301));
    expect(screen.getByText(/This insurance document was archived without creating recurring/)).toBeInTheDocument();
    expect(screen.getByText(/not_relevant/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'trigger insurance confirm' })).not.toBeInTheDocument();
  });

  it('keeps recurring and transactions untouched after archive-only confirmation', async () => {
    getDocument
      .mockResolvedValueOnce({
        id: 301,
        user_id: 1,
        document_type: 'invoice',
        file_path: '/tmp/insurance.pdf',
        file_name: 'insurance.pdf',
        file_size: 100,
        mime_type: 'application/pdf',
        confidence_score: 0.95,
        needs_review: false,
        created_at: '2026-03-28T00:00:00Z',
        updated_at: '2026-03-28T00:00:00Z',
        ocr_result: {
          import_suggestion: {
            type: 'archive_insurance_document',
            status: 'pending',
            data: {
              insurer_name: 'GRAWE',
              insurance_type: 'Private KV',
              document_subtype: 'polizze',
            },
          },
        },
      })
      .mockResolvedValueOnce({
        id: 301,
        user_id: 1,
        document_type: 'invoice',
        file_path: '/tmp/insurance.pdf',
        file_name: 'insurance.pdf',
        file_size: 100,
        mime_type: 'application/pdf',
        confidence_score: 0.95,
        needs_review: false,
        created_at: '2026-03-28T00:00:00Z',
        updated_at: '2026-03-28T00:00:00Z',
        ocr_result: {
          import_suggestion: {
            type: 'archive_insurance_document',
            status: 'confirmed',
            resolution: 'archive_only',
            archive_reason_code: 'not_relevant',
          },
        },
      });
    confirmInsuranceRecurring.mockResolvedValue({
      archive_only: true,
      resolution: 'archive_only',
      archive_reason_code: 'not_relevant',
    });

    renderPage();

    await waitFor(() => expect(getDocument).toHaveBeenCalledWith(301));
    fireEvent.click(screen.getByRole('button', { name: 'trigger insurance confirm' }));

    await waitFor(() => {
      expect(confirmInsuranceRecurring).toHaveBeenCalledWith(301, {
        business_use_percentage: 60,
        override_payment_amount: 89.25,
        override_payment_frequency: 'monthly',
        archive_only: true,
        archive_reason_code: 'not_relevant',
      });
    });

    expect(refreshRecurring).not.toHaveBeenCalled();
    expect(refreshTransactions).not.toHaveBeenCalled();
    expect(refreshDashboard).toHaveBeenCalled();
    expect(aiToast).toHaveBeenCalledWith('Insurance document archived without creating recurring', 'success');
    expect(screen.getByText(/archived without creating recurring/)).toBeInTheDocument();
  });

  it('surfaces backend validation errors when insurance confirmation fails', async () => {
    getDocument.mockResolvedValue({
      id: 301,
      user_id: 1,
      document_type: 'invoice',
      file_path: '/tmp/insurance.pdf',
      file_name: 'insurance.pdf',
      file_size: 100,
      mime_type: 'application/pdf',
      confidence_score: 0.95,
      needs_review: false,
      created_at: '2026-03-28T00:00:00Z',
      updated_at: '2026-03-28T00:00:00Z',
      ocr_result: {
        import_suggestion: {
          type: 'create_insurance_recurring',
          status: 'pending',
          data: {
            insurer_name: 'Generali',
            insurance_type: 'KFZ',
            payment_amount: 89.25,
            payment_frequency: 'monthly',
            input_fields: ['business_use_percentage'],
          },
        },
      },
    });
    confirmInsuranceRecurring.mockRejectedValue({
      response: {
        data: {
          detail: 'business_use_percentage ist erforderlich',
        },
      },
    });

    renderPage();

    await waitFor(() => expect(getDocument).toHaveBeenCalledWith(301));
    fireEvent.click(screen.getByRole('button', { name: 'trigger insurance confirm' }));

    await waitFor(() => {
      expect(confirmInsuranceRecurring).toHaveBeenCalled();
    });

    await waitFor(() => {
      const lastProps = suggestionCardFactorySpy.mock.calls.at(-1)?.[0];
      expect(lastProps?.confirmResult).toEqual({
        type: 'error',
        message: 'business_use_percentage ist erforderlich',
      });
    });
    expect(refreshRecurring).not.toHaveBeenCalled();
    expect(refreshTransactions).not.toHaveBeenCalled();
    expect(aiToast).not.toHaveBeenCalled();
  });
});
