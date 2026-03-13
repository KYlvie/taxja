import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { PropertyComparison } from './PropertyComparison';
import { propertyService } from '../../services/propertyService';

// Mock the property service
vi.mock('../../services/propertyService', () => ({
  propertyService: {
    comparePortfolio: vi.fn(),
  },
}));

// Mock react-i18next
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

// Mock recharts to avoid rendering issues in tests
vi.mock('recharts', () => ({
  BarChart: ({ children }: any) => <div data-testid="bar-chart">{children}</div>,
  Bar: () => <div data-testid="bar" />,
  XAxis: () => <div data-testid="x-axis" />,
  YAxis: () => <div data-testid="y-axis" />,
  CartesianGrid: () => <div data-testid="cartesian-grid" />,
  Tooltip: () => <div data-testid="tooltip" />,
  Legend: () => <div data-testid="legend" />,
  ResponsiveContainer: ({ children }: any) => <div data-testid="responsive-container">{children}</div>,
}));

describe('PropertyComparison', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially', () => {
    vi.mocked(propertyService.comparePortfolio).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );

    render(<PropertyComparison />);
    
    expect(screen.getByText('common.loading')).toBeInTheDocument();
  });

  it('renders empty state when no properties', async () => {
    vi.mocked(propertyService.comparePortfolio).mockResolvedValue([]);

    render(<PropertyComparison />);

    await waitFor(() => {
      expect(screen.getByText('properties.portfolio.noProperties')).toBeInTheDocument();
    });
  });

  it('renders comparison data with chart and table', async () => {
    const mockData = [
      {
        property_id: '1',
        address: 'Test Street 1',
        property_type: 'rental',
        purchase_price: 300000,
        rental_income: 15000,
        expenses: 5000,
        net_income: 10000,
        rental_yield: 3.33,
        expense_ratio: 33.33,
        depreciation: 6000,
        accumulated_depreciation: 12000,
      },
      {
        property_id: '2',
        address: 'Test Street 2',
        property_type: 'rental',
        purchase_price: 400000,
        rental_income: 20000,
        expenses: 8000,
        net_income: 12000,
        rental_yield: 3.0,
        expense_ratio: 40.0,
        depreciation: 8000,
        accumulated_depreciation: 16000,
      },
    ];

    vi.mocked(propertyService.comparePortfolio).mockResolvedValue(mockData);

    render(<PropertyComparison />);

    await waitFor(() => {
      expect(screen.getByText('properties.portfolio.propertyComparison')).toBeInTheDocument();
    });

    // Check that chart is rendered
    expect(screen.getByTestId('bar-chart')).toBeInTheDocument();

    // Check that table is rendered with data
    expect(screen.getByText('Test Street 1')).toBeInTheDocument();
    expect(screen.getByText('Test Street 2')).toBeInTheDocument();
  });

  it('handles API errors gracefully', async () => {
    const errorMessage = 'Failed to load comparison data';
    vi.mocked(propertyService.comparePortfolio).mockRejectedValue(
      new Error(errorMessage)
    );

    render(<PropertyComparison />);

    await waitFor(() => {
      expect(screen.getByText(errorMessage)).toBeInTheDocument();
    });
  });

  it('allows year filtering', async () => {
    const mockData = [
      {
        property_id: '1',
        address: 'Test Street 1',
        property_type: 'rental',
        purchase_price: 300000,
        rental_income: 15000,
        expenses: 5000,
        net_income: 10000,
        rental_yield: 3.33,
        expense_ratio: 33.33,
        depreciation: 6000,
        accumulated_depreciation: 12000,
      },
    ];

    vi.mocked(propertyService.comparePortfolio).mockResolvedValue(mockData);

    render(<PropertyComparison />);

    await waitFor(() => {
      expect(screen.getByLabelText('dashboard.taxYear')).toBeInTheDocument();
    });

    // Verify the year select is present
    const yearSelect = screen.getByLabelText('dashboard.taxYear') as HTMLSelectElement;
    expect(yearSelect).toBeInTheDocument();
    expect(yearSelect.value).toBe(new Date().getFullYear().toString());
  });
});
