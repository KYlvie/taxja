import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

import TaxFormPreview from '../components/reports/TaxFormPreview';
import reportService from '../services/reportService';
import { useFeatureAccess, useUpgradePrompt } from '../components/subscription/withFeatureGate';

const translationCopy: Record<string, string> = {
  'reports.taxYear': 'Tax year',
  'reports.taxForm.generate': 'Generate form',
  'reports.taxForm.exportPackage': 'Export tax package',
  'reports.taxForm.exportPackagePanelTitle': 'Export tax package',
  'reports.taxForm.exportPackagePanelDescription': 'Prepare a downloadable package for the selected tax year.',
  'reports.taxForm.exportPackagePreviewLoading': 'Checking export warnings...',
  'reports.taxForm.exportPackagePreviewFailed': 'Failed to check export warnings.',
  'reports.taxForm.exportPackageWarningTitle': 'Review these items before exporting',
  'reports.taxForm.exportPackageWarningDescription': 'You can still export the package, but these open items may reduce filing quality.',
  'reports.taxForm.exportPackageWarningPendingTransactions': 'Pending review transactions',
  'reports.taxForm.exportPackageWarningPendingDocuments': 'Pending review documents',
  'reports.taxForm.exportPackageWarningFallbackYears': 'Documents assigned by uploaded date fallback',
  'reports.taxForm.exportPackageWarningSkippedFiles': 'Files excluded from export',
  'reports.taxForm.reviewTransactionsBeforeExport': 'Review pending transactions',
  'reports.taxForm.reviewDocumentsBeforeExport': 'Review pending documents',
  'reports.taxForm.reviewDocumentsByYear': 'Review documents from this year',
  'reports.taxForm.continueExportPackage': 'Continue export anyway',
  'reports.taxForm.reviewWarningsFirst': 'Review warnings first',
  'reports.taxForm.exportPackageLoading': 'Preparing tax package...',
  'reports.taxForm.preparePackage': 'Prepare package',
  'reports.taxForm.includeFoundationMaterials': 'Include foundation materials',
  'reports.taxForm.packageScopeTransactionsCsv': 'Transaction CSV',
  'reports.taxForm.packageScopeTransactionsPdf': 'Transaction PDF',
  'reports.taxForm.packageScopeSummaryPdf': 'Summary PDF',
  'reports.taxForm.packageScopeDocuments': 'Tax-related source documents',
  'reports.taxForm.packageScopeFoundationOptional': 'Optional: foundation materials',
  'reports.taxForm.packageStatusReady': 'Ready to download',
  'reports.taxForm.packageStatusPending': 'Preparing',
  'reports.taxForm.packageDownloadSingle': 'Download package',
  'common.loading': 'Loading',
  'taxFormPreview.selectForm': 'Select form',
};

const mockT = (key: string, fallback?: string, options?: Record<string, unknown>) => {
  if (key === 'reports.taxForm.packageDownloadPart') {
    return `Download part ${String(options?.part ?? '')}`.trim();
  }
  return translationCopy[key] ?? fallback ?? key;
};

const mockI18n = {
  language: 'en-US',
};

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: mockT,
    i18n: mockI18n,
  }),
}));

vi.mock('../components/reports/YearWarning', () => ({
  default: () => null,
}));

vi.mock('../utils/exportElementToPdf', () => ({
  default: vi.fn(),
}));

vi.mock('../components/subscription/withFeatureGate', () => ({
  useFeatureAccess: vi.fn(),
  useUpgradePrompt: vi.fn(),
}));

vi.mock('../services/reportService', () => ({
  default: {
    getEligibleForms: vi.fn(),
    generateTaxForm: vi.fn(),
    generateE1aForm: vi.fn(),
    generateE1bForm: vi.fn(),
    generateL1kForm: vi.fn(),
    generateU1Form: vi.fn(),
    generateUvaForm: vi.fn(),
    downloadFilledFormPDF: vi.fn(),
    previewTaxPackageExport: vi.fn(),
    createTaxPackageExport: vi.fn(),
    getTaxPackageExportStatus: vi.fn(),
    deleteTaxPackageExport: vi.fn(),
  },
}));

const mockedReportService = vi.mocked(reportService);
const mockedUseFeatureAccess = vi.mocked(useFeatureAccess);
const mockedUseUpgradePrompt = vi.mocked(useUpgradePrompt);
const currentYear = new Date().getFullYear();
const mockedShowUpgrade = vi.fn();

const renderWithRouter = () => render(
  <MemoryRouter>
    <TaxFormPreview />
  </MemoryRouter>
);

describe('TaxFormPreview tax package export panel', () => {
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(Element.prototype, 'scrollIntoView', {
      configurable: true,
      value: vi.fn(),
    });
    mockedUseFeatureAccess.mockReturnValue(true);
    mockedUseUpgradePrompt.mockReturnValue({
      showUpgrade: mockedShowUpgrade,
      UpgradePromptComponent: null,
    } as any);
    mockedShowUpgrade.mockReset();
    mockedReportService.getEligibleForms.mockResolvedValue({
      forms: [
        {
          form_type: 'E1',
          name_de: 'Einkommensteuererklaerung',
          name_en: 'Income tax return',
          name_zh: '所得税申报',
          description_de: 'Main form',
          description_en: 'Main form',
          description_zh: '主表',
          category: 'main',
          has_template: true,
          tax_year: currentYear,
        },
      ],
      user_type: 'self_employed',
    });
    mockedReportService.previewTaxPackageExport.mockResolvedValue({
      tax_year: currentYear,
      has_warnings: false,
      warnings: [],
      summary: {
        pending_tx_count: 0,
        pending_document_count: 0,
        uncertain_year_docs: 0,
        skipped_files: [],
      },
    } as any);
    mockedReportService.createTaxPackageExport.mockResolvedValue({
      export_id: 'export-1',
      status: 'ready',
      part_count: 1,
      parts: [
        {
          part_number: 1,
          file_name: 'tax-package.zip',
          download_url: 'https://example.com/tax-package.zip',
          size_bytes: 1024,
        },
      ],
    } as any);
  });

  it('shows locked tax form actions for non-pro users and opens the upgrade prompt', async () => {
    mockedUseFeatureAccess.mockReturnValue(false);

    renderWithRouter();

    await waitFor(() => {
      expect(mockedReportService.getEligibleForms).toHaveBeenCalledWith(currentYear);
    });

    fireEvent.click(screen.getByRole('button', { name: /generate form/i }));

    expect(mockedShowUpgrade).toHaveBeenCalledWith('e1_generation', 'pro');
    mockedShowUpgrade.mockClear();

    fireEvent.click(screen.getByRole('button', { name: /export tax package/i }));

    expect(mockedShowUpgrade).toHaveBeenCalledWith('e1_generation', 'pro');
    expect(mockedReportService.previewTaxPackageExport).not.toHaveBeenCalled();
  });

  it('opens the panel with the checkbox off and creates an export for the selected year and language', async () => {
    renderWithRouter();

    await waitFor(() => {
      expect(mockedReportService.getEligibleForms).toHaveBeenCalledWith(currentYear);
    });

    fireEvent.click(screen.getByRole('button', { name: /export tax package/i }));

    await waitFor(() => {
      expect(mockedReportService.previewTaxPackageExport).toHaveBeenCalledWith(currentYear, 'en', false);
    });

    const checkbox = screen.getByRole('checkbox', { name: /include foundation materials/i });
    expect(checkbox).not.toBeChecked();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /prepare package/i })).not.toBeDisabled();
    });
    fireEvent.click(screen.getByRole('button', { name: /prepare package/i }));

    await waitFor(() => {
      expect(mockedReportService.createTaxPackageExport).toHaveBeenCalledWith(currentYear, 'en', false);
    });

    expect(screen.getByText('Ready to download')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /download package/i })).toHaveAttribute(
      'href',
      'https://example.com/tax-package.zip',
    );
  });

  it('uses the newly selected year when creating the export', async () => {
    renderWithRouter();

    await waitFor(() => {
      expect(mockedReportService.getEligibleForms).toHaveBeenCalledWith(currentYear);
    });

    fireEvent.click(screen.getAllByRole('combobox')[0]);
    fireEvent.mouseDown(screen.getByRole('option', { name: String(currentYear - 1) }));

    await waitFor(() => {
      expect(mockedReportService.getEligibleForms).toHaveBeenCalledWith(currentYear - 1);
    });

    fireEvent.click(screen.getByRole('button', { name: /export tax package/i }));
    await waitFor(() => {
      expect(mockedReportService.previewTaxPackageExport).toHaveBeenCalledWith(currentYear - 1, 'en', false);
    });
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /prepare package/i })).not.toBeDisabled();
    });
    fireEvent.click(screen.getByRole('button', { name: /prepare package/i }));

    await waitFor(() => {
      expect(mockedReportService.createTaxPackageExport).toHaveBeenCalledWith(currentYear - 1, 'en', false);
    });
  });

  it('polls pending exports until download links are ready', async () => {
    mockedReportService.createTaxPackageExport.mockResolvedValue({
      export_id: 'export-2',
      status: 'pending',
    } as any);
    mockedReportService.getTaxPackageExportStatus.mockResolvedValue({
      export_id: 'export-2',
      status: 'ready',
      part_count: 2,
      parts: [
        {
          part_number: 1,
          file_name: 'tax-package_part-1.zip',
          download_url: 'https://example.com/part-1.zip',
          size_bytes: 2048,
        },
        {
          part_number: 2,
          file_name: 'tax-package_part-2.zip',
          download_url: 'https://example.com/part-2.zip',
          size_bytes: 1024,
        },
      ],
    } as any);

    const intervalCallbacks: Array<() => Promise<void> | void> = [];
    const setIntervalSpy = vi
      .spyOn(window, 'setInterval')
      .mockImplementation((handler: TimerHandler) => {
        intervalCallbacks.push(handler as () => Promise<void> | void);
        return 1 as unknown as number;
      });
    const clearIntervalSpy = vi
      .spyOn(window, 'clearInterval')
      .mockImplementation(() => undefined);

    renderWithRouter();

    await waitFor(() => {
      expect(mockedReportService.getEligibleForms).toHaveBeenCalledWith(currentYear);
    });

    fireEvent.click(screen.getByRole('button', { name: /export tax package/i }));
    await waitFor(() => {
      expect(mockedReportService.previewTaxPackageExport).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /prepare package/i })).not.toBeDisabled();
    });
    fireEvent.click(screen.getByRole('button', { name: /prepare package/i }));

    await waitFor(() => {
      expect(mockedReportService.createTaxPackageExport).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(intervalCallbacks.length).toBeGreaterThan(0);
    });
    const pollCallback = setIntervalSpy.mock.calls.find(([, delay]) => delay === 2000)?.[0] as
      | (() => Promise<void> | void)
      | undefined;
    expect(pollCallback).toBeTypeOf('function');
    await act(async () => {
      await pollCallback?.();
    });

    await waitFor(() => {
      expect(mockedReportService.getTaxPackageExportStatus).toHaveBeenCalledWith('export-2');
      expect(screen.getByRole('link', { name: /download part 1/i })).toHaveAttribute('href', 'https://example.com/part-1.zip');
    });

    expect(screen.getByRole('link', { name: /download part 1/i })).toHaveAttribute('href', 'https://example.com/part-1.zip');
    expect(screen.getByRole('link', { name: /download part 2/i })).toHaveAttribute('href', 'https://example.com/part-2.zip');
    setIntervalSpy.mockRestore();
    clearIntervalSpy.mockRestore();
  });

  it('shows export warnings before creating the package and requires a second confirmation click', async () => {
    mockedReportService.previewTaxPackageExport.mockResolvedValue({
      tax_year: currentYear,
      has_warnings: true,
      warnings: [
        { key: 'pending_tx_count', label: 'Pending review transactions', count: 2 },
        { key: 'pending_docs', label: 'Pending review documents', count: 4 },
      ],
      summary: {
        pending_tx_count: 2,
        pending_document_count: 4,
        uncertain_year_docs: 0,
        skipped_files: [],
      },
    } as any);

    renderWithRouter();

    await waitFor(() => {
      expect(mockedReportService.getEligibleForms).toHaveBeenCalledWith(currentYear);
    });

    fireEvent.click(screen.getByRole('button', { name: /export tax package/i }));

    expect(await screen.findByText('Review these items before exporting')).toBeInTheDocument();
    expect(screen.getByText('Pending review transactions: 2')).toBeInTheDocument();
    expect(screen.getByText('Pending review documents: 4')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /review pending transactions/i })).toHaveAttribute(
      'href',
      `/transactions?needs_review=true&year=${currentYear}`,
    );
    expect(screen.getByRole('link', { name: /review pending documents/i })).toHaveAttribute(
      'href',
      `/documents?needs_review=true&year=${currentYear}`,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /review warnings first/i })).not.toBeDisabled();
    });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /review warnings first/i }));
    });
    expect(mockedReportService.createTaxPackageExport).not.toHaveBeenCalled();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /continue export anyway/i })).not.toBeDisabled();
    });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /continue export anyway/i }));
    });

    await waitFor(() => {
      expect(mockedReportService.createTaxPackageExport).toHaveBeenCalledWith(currentYear, 'en', false);
    });
  });
});
