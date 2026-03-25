/* @vitest-environment jsdom */

import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import BilanzReport from '../components/reports/BilanzReport';
import SaldenlisteReport from '../components/reports/SaldenlisteReport';
import PeriodensaldenlisteReport from '../components/reports/PeriodensaldenlisteReport';
import TaxFormPreview from '../components/reports/TaxFormPreview';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string | { defaultValue?: string }) => {
      const translations: Record<string, string> = {
        'reports.taxYear': 'Tax year',
        'reports.bilanz.generate': 'Generate balance sheet / P&L',
        'reports.saldenliste.generate': 'Generate balances list',
        'reports.periodensaldenliste.generate': 'Generate period balances list',
        'reports.taxForm.generate': 'Generate tax forms',
        'common.loading': 'Loading',
      };
      if (translations[key]) return translations[key];
      if (typeof fallback === 'string') return fallback;
      if (fallback && typeof fallback === 'object' && typeof fallback.defaultValue === 'string') {
        return fallback.defaultValue;
      }
      return key;
    },
    i18n: { language: 'zh', resolvedLanguage: 'zh' },
  }),
}));

vi.mock('../components/common/Select', () => ({
  default: ({
    id,
    value,
    onChange,
    options,
  }: {
    id?: string;
    value?: string;
    onChange?: (value: string) => void;
    options: Array<{ value: string; label: string }>;
  }) => (
    <select
      id={id}
      data-testid={id ?? 'select'}
      value={value}
      onChange={(event) => onChange?.(event.target.value)}
    >
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  ),
}));

vi.mock('../components/reports/YearWarning', () => ({
  default: () => <div data-testid="year-warning" />,
}));

vi.mock('../services/reportService', () => ({
  default: {
    generateBilanzReport: vi.fn(),
    generateSaldenliste: vi.fn(),
    generatePeriodensaldenliste: vi.fn(),
    getEligibleForms: vi.fn().mockResolvedValue({ forms: [] }),
    generateTaxForm: vi.fn(),
    generateE1aForm: vi.fn(),
    generateE1bForm: vi.fn(),
    generateL1kForm: vi.fn(),
    generateU1Form: vi.fn(),
    generateUvaForm: vi.fn(),
  },
}));

vi.mock('../utils/exportElementToPdf', () => ({
  default: vi.fn(),
}));

vi.mock('../utils/apiError', () => ({
  getApiErrorMessage: vi.fn(() => 'Generation failed'),
  getFeatureGatePlan: vi.fn(() => null),
}));

describe('report toolbar layouts', () => {
  it('keeps tax year label, selector, and generate action in one row for Bilanz', () => {
    const { container } = render(<BilanzReport />);

    const toolbar = container.querySelector('.bilanz-generate-row');
    expect(toolbar).not.toBeNull();
    expect(toolbar).toContainElement(screen.getByText('Tax year'));
    expect(toolbar).toContainElement(screen.getByTestId('bilanz-year'));
    expect(toolbar).toContainElement(
      screen.getByRole('button', { name: 'Generate balance sheet / P&L' }),
    );
  });

  it('keeps tax year label, selector, and generate action in one row for Saldenliste', () => {
    const { container } = render(<SaldenlisteReport />);

    const toolbar = container.querySelector('.saldenliste-generate-row');
    expect(toolbar).not.toBeNull();
    expect(toolbar).toContainElement(screen.getByText('Tax year'));
    expect(toolbar).toContainElement(screen.getByTestId('saldenliste-year'));
    expect(toolbar).toContainElement(
      screen.getByRole('button', { name: 'Generate balances list' }),
    );
  });

  it('keeps tax year label, selector, and generate action in one row for Periodensaldenliste', () => {
    const { container } = render(<PeriodensaldenlisteReport />);

    const toolbar = container.querySelector('.periodensaldenliste-generate-row');
    expect(toolbar).not.toBeNull();
    expect(toolbar).toContainElement(screen.getByText('Tax year'));
    expect(toolbar).toContainElement(screen.getByTestId('periodensaldenliste-year'));
    expect(toolbar).toContainElement(
      screen.getByRole('button', { name: 'Generate period balances list' }),
    );
  });

  it('keeps tax year label, selector, and generate action in one row for tax forms', async () => {
    const { container } = render(<TaxFormPreview />);

    await waitFor(() => {
      const toolbar = container.querySelector('.tf-generate-row');
      expect(toolbar).not.toBeNull();
      expect(toolbar).toContainElement(screen.getByText('Tax year'));
      expect(toolbar).toContainElement(screen.getByTestId('tf-year'));
      expect(toolbar).toContainElement(screen.getByRole('button', { name: 'Generate tax forms' }));
    });
  });
});
