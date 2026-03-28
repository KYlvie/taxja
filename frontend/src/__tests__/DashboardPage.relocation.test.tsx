/* @vitest-environment jsdom */

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import DashboardPage from '../pages/DashboardPage';
import { useAuthStore } from '../stores/authStore';
import { useDashboardStore } from '../stores/dashboardStore';

const getDashboardData = vi.fn();
const getSuggestions = vi.fn();

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => (typeof fallback === 'string' ? fallback : key),
    i18n: { language: 'en', resolvedLanguage: 'en' },
  }),
}));

vi.mock('../services/dashboardService', () => ({
  dashboardService: {
    getDashboardData: (...args: any[]) => getDashboardData(...args),
    getSuggestions: (...args: any[]) => getSuggestions(...args),
  },
}));

vi.mock('../components/dashboard/DashboardOverview', () => ({
  default: () => <div data-testid="dashboard-overview">Dashboard overview</div>,
}));

vi.mock('../components/dashboard/TrendCharts', () => ({
  default: () => <div data-testid="trend-charts">Trend charts</div>,
}));

vi.mock('../components/documents/DocumentUpload', () => ({
  default: ({ onDocumentsSubmitted }: { onDocumentsSubmitted?: (documents: Array<{ id: number }>) => void }) => (
    <button
      data-testid="dashboard-document-upload"
      onClick={() => onDocumentsSubmitted?.([{ id: 42 }])}
    >
      Upload document
    </button>
  ),
}));

vi.mock('../components/recurring/RecurringSuggestionsList', () => ({
  RecurringSuggestionsList: () => <div data-testid="recurring-suggestions">Recurring suggestions</div>,
}));

describe('DashboardPage relocation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useDashboardStore.setState({
      data: null,
      deadlines: [],
      suggestions: [],
      isLoading: false,
    });
    useAuthStore.setState({
      user: {
        id: 1,
        email: 'mixed@example.com',
        name: 'Mixed User',
        user_type: 'mixed',
        employer_mode: 'regular',
        two_factor_enabled: false,
        onboarding_completed: true,
      },
      token: 'token',
      isAuthenticated: true,
    });

    getDashboardData.mockResolvedValue({
      yearToDateIncome: 1500,
      yearToDateExpenses: 500,
      estimatedTax: 300,
      paidTax: 200,
      remainingTax: 100,
      netIncome: 700,
      estimatedRefund: 0,
      withheldTax: 200,
      calculatedTax: 200,
      hasLohnzettel: true,
      monthlyData: [{ month: 1, income: 100, expenses: 50 }],
      incomeCategoryData: [{ category: 'consulting', amount: 100 }],
      expenseCategoryData: [{ category: 'office', amount: 50 }],
      yearOverYearData: {},
    });
    getSuggestions.mockResolvedValue({ suggestions: [] });
  });

  it('keeps dashboard focused and no longer renders tax-tools sections inline', async () => {
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByTestId('dashboard-overview')).toBeInTheDocument());
    expect(screen.getByTestId('trend-charts')).toBeInTheDocument();
    expect(screen.queryByText('Tax position')).not.toBeInTheDocument();
    expect(screen.queryByText('Asset overview')).not.toBeInTheDocument();
    expect(screen.queryByText('AI tax advisor')).not.toBeInTheDocument();
    expect(screen.queryByText('Employer workbench')).not.toBeInTheDocument();
  });

  it('keeps the dashboard in place when upload finishes', async () => {
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/documents/:id" element={<div data-testid="document-route">Document route</div>} />
          <Route path="/documents" element={<div data-testid="documents-route">Documents route</div>} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByTestId('dashboard-document-upload')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('dashboard-document-upload'));

    await waitFor(() => expect(screen.getByTestId('dashboard-overview')).toBeInTheDocument());
    expect(screen.queryByTestId('document-route')).not.toBeInTheDocument();
  });
});
