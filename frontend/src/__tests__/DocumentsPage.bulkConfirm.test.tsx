/* @vitest-environment jsdom */

import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import DocumentsPage from '../pages/DocumentsPage';

const getDocuments = vi.fn();
const confirmOCR = vi.fn();
const aiToast = vi.fn();

vi.mock('react-i18next', () => ({
  initReactI18next: {
    type: '3rdParty',
    init: () => undefined,
  },
  useTranslation: () => ({
    t: (
      key: string,
      fallback?: string | { defaultValue?: string; count?: number },
      options?: { count?: number }
    ) => {
      if (typeof fallback === 'string') {
        return typeof options?.count === 'number'
          ? fallback.replace('{{count}}', String(options.count))
          : fallback;
      }
      if (fallback && typeof fallback === 'object' && typeof fallback.defaultValue === 'string') {
        return typeof fallback.count === 'number'
          ? fallback.defaultValue.replace('{{count}}', String(fallback.count))
          : fallback.defaultValue;
      }
      return key;
    },
    i18n: {
      language: 'en',
      resolvedLanguage: 'en',
    },
  }),
}));

vi.mock('../components/documents/DocumentUpload', () => ({ default: () => <div data-testid="doc-upload" /> }));
vi.mock('../components/documents/DocumentList', () => ({
  default: ({ onSummaryChange }: any) => {
    React.useEffect(() => {
      onSummaryChange?.({
        totalCount: 5,
        reviewCount: 3,
        confirmableIds: [11, 12, 13],
      });
    }, [onSummaryChange]);

    return <div data-testid="doc-list" />;
  },
}));
vi.mock('../components/documents/OCRReview', () => ({ default: () => <div data-testid="ocr-review" /> }));
vi.mock('../components/documents/EmployerReviewPanel', () => ({ default: () => null }));
vi.mock('../components/documents/DocumentActionGate', () => ({ default: ({ children }: any) => <>{children}</> }));
vi.mock('../components/documents/DocumentPresentationRouter', () => ({ default: () => null }));
vi.mock('../components/documents/SuggestionCardFactory', () => ({ default: () => null }));

vi.mock('../services/documentService', () => ({
  documentService: {
    getDocuments: (...args: any[]) => getDocuments(...args),
    confirmOCR: (...args: any[]) => confirmOCR(...args),
    exportZip: vi.fn(),
  },
}));

vi.mock('../services/transactionService', () => ({
  transactionService: {
    getById: vi.fn(),
    update: vi.fn(),
  },
}));

vi.mock('../services/propertyService', () => ({
  propertyService: {
    getById: vi.fn(),
  },
}));

vi.mock('../mobile/files', () => ({
  saveBlobWithNativeShare: vi.fn(),
}));

vi.mock('../stores/refreshStore', () => ({
  useRefreshStore: {
    getState: () => ({
      refreshTransactions: vi.fn(),
      refreshDashboard: vi.fn(),
      refreshProperties: vi.fn(),
      refreshRecurring: vi.fn(),
    }),
  },
}));

vi.mock('../stores/aiToastStore', () => ({
  aiToast: (...args: any[]) => aiToast(...args),
}));

vi.mock('../documents/presentation/featureFlag', () => ({
  default: () => false,
}));

describe('DocumentsPage bulk confirm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getDocuments.mockResolvedValue({ documents: [] });
    confirmOCR.mockResolvedValue(undefined);
  });

  it('confirms all summary-provided reviewable documents from the list header action', async () => {
    render(
      <MemoryRouter initialEntries={['/documents']}>
        <Routes>
          <Route path="/documents" element={<DocumentsPage />} />
        </Routes>
      </MemoryRouter>,
    );

    const confirmButton = await screen.findByRole('button', { name: 'One-click confirm' });
    fireEvent.click(confirmButton);

    await waitFor(() => {
      expect(confirmOCR).toHaveBeenCalledTimes(3);
    });
    expect(confirmOCR).toHaveBeenNthCalledWith(1, 11);
    expect(confirmOCR).toHaveBeenNthCalledWith(2, 12);
    expect(confirmOCR).toHaveBeenNthCalledWith(3, 13);

    await waitFor(() => {
      expect(aiToast).toHaveBeenCalledWith('Confirmed 3 items.', 'success');
    });
  });
});
