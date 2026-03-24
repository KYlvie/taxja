/* @vitest-environment jsdom */

import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import AssetInsightsPage from '../pages/AssetInsightsPage';

const getProperties = vi.fn();
const getAssets = vi.fn();
const getProperty = vi.fn();
const getPropertyMetrics = vi.fn();

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    i18n: { language: 'en', resolvedLanguage: 'en' },
  }),
}));

vi.mock('../services/propertyService', () => ({
  propertyService: {
    getProperties: (...args: any[]) => getProperties(...args),
    getAssets: (...args: any[]) => getAssets(...args),
    getProperty: (...args: any[]) => getProperty(...args),
  },
}));

vi.mock('../services/dashboardService', () => ({
  dashboardService: {
    getPropertyMetrics: (...args: any[]) => getPropertyMetrics(...args),
  },
}));

vi.mock('../components/properties/PropertyComparison', () => ({
  PropertyComparison: () => <div data-testid="property-comparison">Property comparison</div>,
}));

vi.mock('../components/properties/PropertyReports', () => ({
  default: () => <div data-testid="property-reports">Property reports</div>,
}));

describe('AssetInsightsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    getProperties.mockResolvedValue({
      total: 1,
      properties: [{ id: 'property-1', address: 'Main Street 1' }],
      include_archived: true,
    });
    getAssets.mockResolvedValue({
      total: 1,
      assets: [{ id: 'asset-1', asset_type: 'computer', name: 'MacBook' }],
    });
    getProperty.mockResolvedValue({ id: 'property-1', address: 'Main Street 1' });
    getPropertyMetrics.mockResolvedValue({
      has_properties: true,
      active_properties_count: 1,
      total_rental_income: 0,
      total_property_expenses: 0,
      net_rental_income: 0,
    });
  });

  it('keeps overview, comparison, and single-asset reporting under the asset area', async () => {
    render(
      <MemoryRouter>
        <AssetInsightsPage />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: /Asset overview & comparison/i })).toBeInTheDocument(),
    );

    expect(screen.getByRole('link', { name: /Back/i })).toHaveAttribute('href', '/advanced');
    expect(screen.getByText('Tracked assets')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByTestId('property-comparison')).toBeInTheDocument();
    expect(screen.getByTestId('property-reports')).toBeInTheDocument();
  });
});
