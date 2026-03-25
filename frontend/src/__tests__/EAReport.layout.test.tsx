/* @vitest-environment jsdom */

import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import EAReport from '../components/reports/EAReport';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string | { defaultValue?: string }) => {
      const translations: Record<string, string> = {
        'reports.taxYear': 'Tax year',
        'reports.ea.generate': 'Generate income statement (E/A Rechnung)',
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
      data-testid="ea-year-select"
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
    generateEAReport: vi.fn(),
  },
}));

vi.mock('../utils/exportElementToPdf', () => ({
  default: vi.fn(),
}));

vi.mock('../utils/apiError', () => ({
  getApiErrorMessage: vi.fn(() => 'Generation failed'),
  getFeatureGatePlan: vi.fn(() => null),
}));

describe('EAReport layout', () => {
  it('keeps tax year label, year selector, and generate action in one toolbar row', () => {
    const { container } = render(<EAReport />);

    const toolbar = container.querySelector('.ea-generate-row');
    expect(toolbar).not.toBeNull();

    expect(toolbar).toContainElement(screen.getByText('Tax year'));
    expect(toolbar).toContainElement(screen.getByTestId('ea-year-select'));
    expect(
      toolbar
    ).toContainElement(screen.getByRole('button', { name: 'Generate income statement (E/A Rechnung)' }));
  });
});
