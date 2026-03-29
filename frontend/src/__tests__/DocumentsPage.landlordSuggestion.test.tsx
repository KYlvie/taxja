/* @vitest-environment jsdom */

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import DocumentsPage from '../pages/DocumentsPage';

const getDocument = vi.fn();
const getDocuments = vi.fn();
const confirmRecurring = vi.fn();
const downloadDocument = vi.fn();
const getProperty = vi.fn();
const suggestionCardFactorySpy = vi.fn();
const refreshRecurring = vi.fn();
const refreshDashboard = vi.fn();
const aiToast = vi.fn();

vi.mock('react-i18next', () => ({
  initReactI18next: { type: '3rdParty', init: () => {} },
  useTranslation: () => ({
    t: (key: string, fallback?: string | { defaultValue?: string }) => {
      if (typeof fallback === 'string') return fallback;
      if (fallback && typeof fallback === 'object' && typeof fallback.defaultValue === 'string') {
        return fallback.defaultValue;
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
      <button type="button" onClick={() => props.onConfirmRecurring?.()}>
        trigger landlord recurring confirm
      </button>
    );
  },
}));

vi.mock('../services/documentService', () => ({
  documentService: {
    getDocument: (...args: any[]) => getDocument(...args),
    getDocuments: (...args: any[]) => getDocuments(...args),
    confirmRecurring: (...args: any[]) => confirmRecurring(...args),
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
      refreshTransactions: vi.fn(),
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
    <MemoryRouter initialEntries={['/documents/401']}>
      <Routes>
        <Route path="/documents/:documentId" element={<DocumentsPage />} />
      </Routes>
    </MemoryRouter>,
  );

describe('DocumentsPage landlord rental recurring flow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    downloadDocument.mockResolvedValue(new Blob(['pdf']));
    getDocuments.mockResolvedValue({ documents: [{ id: 401 }] });
    getProperty.mockResolvedValue(null);
    global.URL.createObjectURL = vi.fn(() => 'blob:test');
    global.URL.revokeObjectURL = vi.fn();
  });

  it('forwards landlord recurring confirmations and refreshes recurring state', async () => {
    getDocument
      .mockResolvedValueOnce({
        id: 401,
        user_id: 1,
        document_type: 'invoice',
        file_path: '/tmp/mietvertrag.pdf',
        file_name: 'mietvertrag.pdf',
        file_size: 100,
        mime_type: 'application/pdf',
        confidence_score: 0.95,
        needs_review: false,
        created_at: '2026-03-28T00:00:00Z',
        updated_at: '2026-03-28T00:00:00Z',
        ocr_result: {
          import_suggestion: {
            type: 'create_recurring_income',
            status: 'pending',
            data: {
              monthly_rent: 1035,
              address: 'Praterstrasse 40/12, 1020 Wien',
              matched_property_id: 'prop-1020',
              matched_property_address: 'Praterstrasse 40/12, 1020 Wien',
            },
          },
        },
      })
      .mockResolvedValueOnce({
        id: 401,
        user_id: 1,
        document_type: 'invoice',
        file_path: '/tmp/mietvertrag.pdf',
        file_name: 'mietvertrag.pdf',
        file_size: 100,
        mime_type: 'application/pdf',
        confidence_score: 0.95,
        needs_review: false,
        created_at: '2026-03-28T00:00:00Z',
        updated_at: '2026-03-28T00:00:00Z',
        ocr_result: {
          import_suggestion: {
            type: 'create_recurring_income',
            status: 'confirmed',
            recurring_id: 81,
          },
        },
      });
    confirmRecurring.mockResolvedValue({ recurring_id: 81 });

    renderPage();

    await waitFor(() => expect(getDocument).toHaveBeenCalledWith(401));
    fireEvent.click(screen.getByRole('button', { name: 'trigger landlord recurring confirm' }));

    await waitFor(() => {
      expect(confirmRecurring).toHaveBeenCalledWith(401);
    });

    expect(refreshRecurring).toHaveBeenCalled();
    expect(refreshDashboard).toHaveBeenCalled();
    expect(aiToast).toHaveBeenCalledWith('documents.suggestion.recurringCreated', 'success');
  });

  it('surfaces backend validation errors when landlord recurring confirmation fails', async () => {
    getDocument.mockResolvedValue({
      id: 401,
      user_id: 1,
      document_type: 'invoice',
      file_path: '/tmp/mietvertrag.pdf',
      file_name: 'mietvertrag.pdf',
      file_size: 100,
      mime_type: 'application/pdf',
      confidence_score: 0.95,
      needs_review: false,
      created_at: '2026-03-28T00:00:00Z',
      updated_at: '2026-03-28T00:00:00Z',
      ocr_result: {
        import_suggestion: {
          type: 'create_recurring_income',
          status: 'pending',
          data: {
            monthly_rent: 1035,
            address: 'Praterstrasse 40/12, 1020 Wien',
          },
        },
      },
    });
    confirmRecurring.mockRejectedValue({
      response: {
        data: {
          detail: 'Unable to create recurring income',
        },
      },
    });

    renderPage();

    await waitFor(() => expect(getDocument).toHaveBeenCalledWith(401));
    fireEvent.click(screen.getByRole('button', { name: 'trigger landlord recurring confirm' }));

    await waitFor(() => {
      expect(confirmRecurring).toHaveBeenCalledWith(401);
    });

    await waitFor(() => {
      const lastProps = suggestionCardFactorySpy.mock.calls.at(-1)?.[0];
      expect(lastProps?.confirmResult).toEqual({
        type: 'error',
        message: 'Unable to create recurring income',
      });
    });

    expect(refreshRecurring).not.toHaveBeenCalled();
    expect(refreshDashboard).not.toHaveBeenCalled();
    expect(aiToast).not.toHaveBeenCalled();
  });
});
