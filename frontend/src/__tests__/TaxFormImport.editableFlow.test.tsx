/* @vitest-environment jsdom */

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import BescheidImport from '../components/documents/BescheidImport';
import E1FormImport from '../components/documents/E1FormImport';
import zh from '../i18n/locales/zh.json';

const parseBescheid = vi.fn();
const importBescheid = vi.fn();
const parseE1Form = vi.fn();
const importE1Form = vi.fn();
const downloadDocument = vi.fn();

const translate = (key: string, fallback?: string | { defaultValue?: string }, options?: Record<string, unknown>) => {
  const fromLocale = key.split('.').reduce<unknown>((current, segment) => {
    if (current && typeof current === 'object' && segment in (current as Record<string, unknown>)) {
      return (current as Record<string, unknown>)[segment];
    }
    return undefined;
  }, zh);

  if (typeof fromLocale === 'string') {
    return fromLocale.replace(/\{\{(\w+)\}\}/g, (_, token) => String(options?.[token] ?? ''));
  }

  if (typeof fallback === 'string') {
    return fallback;
  }

  if (fallback && typeof fallback === 'object' && typeof fallback.defaultValue === 'string') {
    return fallback.defaultValue;
  }

  return key;
};

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: translate,
    i18n: { language: 'zh' },
  }),
}));

vi.mock('../services/reportService', () => ({
  default: {
    parseBescheid: (...args: any[]) => parseBescheid(...args),
    importBescheid: (...args: any[]) => importBescheid(...args),
    parseE1Form: (...args: any[]) => parseE1Form(...args),
    importE1Form: (...args: any[]) => importE1Form(...args),
  },
}));

vi.mock('../services/documentService', () => ({
  documentService: {
    downloadDocument: (...args: any[]) => downloadDocument(...args),
  },
}));

vi.mock('../components/properties/PropertyLinkingSuggestions', () => ({
  default: () => null,
}));

describe('Tax-form import editable confirmation flow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    downloadDocument.mockResolvedValue(new Blob(['pdf'], { type: 'application/pdf' }));
    Object.defineProperty(globalThis.URL, 'createObjectURL', {
      writable: true,
      configurable: true,
      value: vi.fn(() => 'blob:preview'),
    });
    Object.defineProperty(globalThis.URL, 'revokeObjectURL', {
      writable: true,
      configurable: true,
      value: vi.fn(),
    });

    importBescheid.mockResolvedValue({
      message: 'saved',
      tax_filing_data_id: 91,
      data_type: 'einkommensteuerbescheid',
      tax_year: 2024,
      saved_data: {},
      document_id: 14,
    });
    importE1Form.mockResolvedValue({
      message: 'saved',
      tax_filing_data_id: 92,
      data_type: 'e1_form',
      tax_year: 2025,
      saved_data: {},
      document_id: 21,
    });
  });

  it('submits edited E1 data as tax-data confirmation', async () => {
    render(
      <MemoryRouter>
        <E1FormImport
          ocrText="E1 OCR text"
          documentId={21}
          initialParseResult={{
            tax_year: 2025,
            taxpayer_name: 'Erika Musterfrau',
            steuernummer: '12 345/6789',
            confidence: 0.66,
            all_kz_values: {
              kz_9040: 1200,
            },
          }}
        />
      </MemoryRouter>
    );

    expect(await screen.findByTitle(translate('documents.preview'))).toBeInTheDocument();

    const taxNumberInput = screen.getByDisplayValue('12 345/6789');
    fireEvent.change(taxNumberInput, { target: { value: '11 222/3333' } });

    const kzInput = screen.getByDisplayValue('1200');
    fireEvent.change(kzInput, { target: { value: '1500' } });

    fireEvent.click(screen.getByRole('button', { name: translate('documents.taxData.confirmButton') }));

    await waitFor(() => expect(importE1Form).toHaveBeenCalledTimes(1));
    expect(importE1Form).toHaveBeenCalledWith(
      'E1 OCR text',
      21,
      expect.objectContaining({
        steuernummer: '11 222/3333',
        all_kz_values: {
          kz_9040: '1500',
        },
      })
    );
  });

  it('submits edited Bescheid data as tax-data confirmation', async () => {
    render(
      <MemoryRouter>
        <BescheidImport
          ocrText="Bescheid OCR text"
          documentId={14}
          initialParseResult={{
            tax_year: 2024,
            taxpayer_name: 'Erika Musterfrau',
            finanzamt: 'Wien 1/23',
            steuernummer: '98 765/4321',
            einkommen: 8000,
            festgesetzte_einkommensteuer: 574.6,
            abgabengutschrift: 0,
            abgabennachforderung: 574.6,
            einkuenfte_nichtselbstaendig: 0,
            einkuenfte_vermietung: 0,
            vermietung_details: [],
            werbungskosten_pauschale: 132,
            telearbeitspauschale: 0,
            confidence: 0.72,
          }}
        />
      </MemoryRouter>
    );

    expect(await screen.findByTitle(translate('documents.preview'))).toBeInTheDocument();

    const taxOfficeInput = screen.getByDisplayValue('Wien 1/23');
    fireEvent.change(taxOfficeInput, { target: { value: 'Wien 2/20/21/22' } });

    const taxInput = screen.getAllByDisplayValue('574.6')[0];
    fireEvent.change(taxInput, { target: { value: '500.0' } });

    fireEvent.click(screen.getByRole('button', { name: translate('documents.taxData.confirmButton') }));

    await waitFor(() => expect(importBescheid).toHaveBeenCalledTimes(1));
    expect(importBescheid).toHaveBeenCalledWith(
      'Bescheid OCR text',
      14,
      expect.objectContaining({
        finanzamt: 'Wien 2/20/21/22',
        festgesetzte_einkommensteuer: '500.0',
      })
    );
  });
});
