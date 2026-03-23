/* @vitest-environment jsdom */

import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import TaxToolsPage from '../pages/TaxToolsPage';
import { useAuthStore } from '../stores/authStore';

const getAvailableYears = vi.fn();
const getSummary = vi.fn();
const getDashboardData = vi.fn();

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => (typeof fallback === 'string' ? fallback : key),
    i18n: { language: 'en', resolvedLanguage: 'en' },
  }),
}));

vi.mock('../services/taxFilingService', () => ({
  taxFilingService: {
    getAvailableYears: (...args: any[]) => getAvailableYears(...args),
    getSummary: (...args: any[]) => getSummary(...args),
  },
}));

vi.mock('../services/dashboardService', () => ({
  dashboardService: {
    getDashboardData: (...args: any[]) => getDashboardData(...args),
  },
}));

vi.mock('../components/dashboard/RefundEstimate', () => ({
  default: () => <div data-testid="refund-estimate">Refund estimate</div>,
}));

vi.mock('../components/dashboard/AITaxAdvisor', () => ({
  default: () => <div data-testid="ai-tax-advisor">AI tax advisor</div>,
}));

vi.mock('../components/documents/EmployerDocumentsWorkbench', () => ({
  default: () => <div data-testid="employer-workbench">Employer workbench</div>,
}));

vi.mock('../components/dashboard/WhatIfSimulator', () => ({
  default: () => <div data-testid="what-if-simulator">What if simulator</div>,
}));

vi.mock('../components/dashboard/FlatRateComparison', () => ({
  default: () => <div data-testid="flat-rate-comparison">Flat rate comparison</div>,
}));

describe('TaxToolsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    useAuthStore.setState({
      user: {
        id: 1,
        email: 'user@example.com',
        name: 'User',
        user_type: 'mixed',
        employer_mode: 'regular',
        employer_region: 'Wien',
        two_factor_enabled: false,
      },
      token: 'token',
      isAuthenticated: true,
    });

    getAvailableYears.mockResolvedValue([2026]);
    getSummary.mockResolvedValue({
      year: 2026,
      income: [],
      deductions: [],
      vat: [],
      other: [],
      totals: {
        total_income: 0,
        total_deductions: 0,
        taxable_income: 0,
        estimated_tax: 0,
        withheld_tax: 0,
        estimated_refund: 0,
        total_vat_payable: 0,
      },
      conflicts: [],
      record_count: 0,
    });
    getDashboardData.mockResolvedValue({
      yearToDateIncome: 1000,
      yearToDateExpenses: 300,
      estimatedRefund: 0,
      withheldTax: 200,
      calculatedTax: 200,
      hasLohnzettel: true,
    });
  });

  it('keeps tax tools focused on tax modules without duplicating asset insights', async () => {
    render(
      <MemoryRouter>
        <TaxToolsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByRole('heading', { name: /Tax position/i })).toBeInTheDocument());
    expect(screen.getByRole('link', { name: /Back/i })).toHaveAttribute('href', '/advanced');
    expect(screen.getByTestId('refund-estimate')).toBeInTheDocument();
    expect(screen.getByTestId('ai-tax-advisor')).toBeInTheDocument();
    expect(screen.getByTestId('employer-workbench')).toBeInTheDocument();
    expect(screen.getByTestId('what-if-simulator')).toBeInTheDocument();
    expect(screen.getByTestId('flat-rate-comparison')).toBeInTheDocument();
    expect(
      screen.queryByRole('heading', { name: /Asset overview & comparison/i }),
    ).not.toBeInTheDocument();
  });
});
