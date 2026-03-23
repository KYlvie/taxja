/* @vitest-environment jsdom */

import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import FlatRateComparison from '../components/dashboard/FlatRateComparison';

const compareFlatRate = vi.fn();

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => (typeof fallback === 'string' ? fallback : key),
    i18n: { language: 'en', resolvedLanguage: 'en' },
  }),
}));

vi.mock('../services/dashboardService', () => ({
  dashboardService: {
    compareFlatRate: (...args: any[]) => compareFlatRate(...args),
  },
}));

describe('FlatRateComparison', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows the basic exemption explicitly when flat-rate taxable income includes it', async () => {
    compareFlatRate.mockResolvedValue({
      actualAccounting: {
        grossIncome: 10200,
        deductibleExpenses: 0,
        taxableIncome: 10200,
        incomeTax: 0,
        netIncome: 10200,
      },
      flatRate: {
        grossIncome: 10200,
        flatRateDeduction: 612,
        flatRatePercentage: 6,
        basicExemption: 1438.2,
        taxableIncome: 8149.8,
        incomeTax: 0,
        netIncome: 10200,
      },
      savings: 0,
      recommendation: 'actual',
      eligibility: {
        isEligible: true,
        reason: 'eligible',
        maxProfit: 220000,
      },
    });

    render(<FlatRateComparison year={2026} />);

    await waitFor(() => {
      expect(compareFlatRate).toHaveBeenCalledWith(2026);
    });

    expect(screen.getByText('Basic exemption (15%):')).toBeInTheDocument();
    expect(
      screen.getByText(
        'Taxable income here already reflects both the flat-rate deduction and the 15% basic exemption (Grundfreibetrag).'
      )
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        'The flat-rate method lowers taxable income here, but both methods currently lead to the same income tax.'
      )
    ).toBeInTheDocument();
  });
});
