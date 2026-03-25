import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import TaxFormPreview from '../components/reports/TaxFormPreview';
import reportService from '../services/reportService';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => {
      const copy: Record<string, string> = {
        'reports.taxYear': 'Tax year',
        'reports.taxForm.generate': 'Generate form',
        'reports.taxForm.downloadPDF': 'Download PDF',
        'reports.ea.print': 'Print',
        'common.loading': 'Loading',
        'taxFormPreview.selectForm': 'Select form',
        'taxFormPreview.bmfHeader': 'Federal Ministry of Finance',
        'taxFormPreview.republic': 'Republic of Austria',
        'taxFormPreview.taxNumber': 'Tax number',
        'taxFormPreview.nameOrCompany': 'Name / Company',
        'taxFormPreview.assessmentYear': 'Assessment year',
        'taxFormPreview.generatedAt': 'Generated at {{date}}',
        'taxFormPreview.taxFilingAssistant': 'Tax filing assistant',
        'reports.taxForm.summary': 'Summary',
      };
      return copy[key] ?? fallback ?? key;
    },
    i18n: {
      language: 'en',
    },
  }),
}));

vi.mock('../components/reports/YearWarning', () => ({
  default: () => null,
}));

vi.mock('../utils/exportElementToPdf', () => ({
  default: vi.fn(),
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
  },
}));

const mockedReportService = vi.mocked(reportService);

const currentYear = new Date().getFullYear();

Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
  value: vi.fn(),
  writable: true,
});

const makeFormData = (taxYear: number) => ({
  form_type: 'E1' as const,
  form_name_de: 'E1',
  form_name_en: 'E1',
  form_name_zh: 'E1',
  tax_year: taxYear,
  user_name: 'Test User',
  tax_number: 'N/A',
  generated_at: '2026-03-25',
  fields: [],
  summary: {},
  disclaimer_de: '',
  disclaimer_en: '',
  disclaimer_zh: '',
  finanzonline_url: '',
  form_download_url: '',
});

describe('TaxFormPreview', () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.clearAllMocks();
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
    mockedReportService.generateTaxForm.mockImplementation(async (taxYear: number) => makeFormData(taxYear));
  });

  it('shows the generate button again after changing year', async () => {
    render(<TaxFormPreview />);

    await waitFor(() => {
      expect(mockedReportService.getEligibleForms).toHaveBeenCalledWith(currentYear);
    });

    fireEvent.click(screen.getByRole('button', { name: 'Generate form' }));

    await waitFor(() => {
      expect(mockedReportService.generateTaxForm).toHaveBeenCalledWith(currentYear);
    });

    expect(screen.getByRole('button', { name: /print/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /generate form/i })).not.toBeInTheDocument();

    fireEvent.click(screen.getAllByRole('combobox')[0]);
    fireEvent.mouseDown(screen.getByRole('option', { name: String(currentYear - 1) }));

    await waitFor(() => {
      expect(mockedReportService.getEligibleForms).toHaveBeenCalledWith(currentYear - 1);
    });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /generate form/i })).toBeInTheDocument();
    });

    expect(screen.queryByRole('button', { name: /print/i })).not.toBeInTheDocument();
    expect(mockedReportService.generateTaxForm).toHaveBeenCalledTimes(1);
  });
});
