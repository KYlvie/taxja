/* @vitest-environment jsdom */

import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import DocumentsPage from '../pages/DocumentsPage';

const getDocuments = vi.fn();
const confirmOCR = vi.fn();
const getExportYears = vi.fn();
const getExportZipUrl = vi.fn();
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
    getExportYears: (...args: any[]) => getExportYears(...args),
    getExportZipUrl: (...args: any[]) => getExportZipUrl(...args),
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
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: vi.fn(),
    });
    getDocuments.mockResolvedValue({ documents: [] });
    confirmOCR.mockResolvedValue(undefined);
    getExportYears.mockResolvedValue([
      { year: 2026, count: 3, total_size_bytes: 5 * 1024 * 1024 },
      { year: 2024, count: 4, total_size_bytes: 180 * 1024 * 1024 },
    ]);
    getExportZipUrl.mockReturnValue('/api/v1/documents/export-zip?sort_by=document_date&document_year=2024');
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

  it('opens an export dialog, lets the user choose a document year, and starts a direct download', async () => {
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => undefined);

    render(
      <MemoryRouter initialEntries={['/documents']}>
        <Routes>
          <Route path="/documents" element={<DocumentsPage />} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole('button', { name: 'Export ZIP' }));

    expect(await screen.findByText('Choose the file year to export. The year is based on the document attribution year, not the upload year.')).toBeInTheDocument();
    expect(getExportYears).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole('combobox'));
    fireEvent.mouseDown(await screen.findByRole('option', { name: '2024 (4)' }));

    await waitFor(() => {
      expect(screen.getByText(/180 MB/)).toBeInTheDocument();
    });
    expect(
      screen.getByText(
        'Large export detected. The browser will download it directly so the page does not need to keep the full ZIP in memory.',
      ),
    ).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole('button', { name: 'Export ZIP' }).at(-1)!);

    expect(getExportZipUrl).toHaveBeenCalledWith({}, { documentYear: 2024 });
    expect(clickSpy).toHaveBeenCalledTimes(1);

    clickSpy.mockRestore();
  });
});
