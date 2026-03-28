import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import Select from '../common/Select';
import { propertyService } from '../../services/propertyService';
import SubpageBackLink from '../common/SubpageBackLink';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { getLocaleForLanguage } from '../../utils/locale';
import { getErrorMessage } from '../../services/propertyService';
import './PropertyComparison.css';

interface PropertyComparisonData {
  property_id: string;
  address: string;
  property_type: string;
  purchase_price: number;
  rental_income: number;
  expenses: number;
  net_income: number;
  rental_yield: number;
  expense_ratio: number;
  depreciation: number;
  accumulated_depreciation: number;
}

type SortField = 'address' | 'rental_income' | 'expenses' | 'net_income' | 'rental_yield' | 'expense_ratio';
type SortOrder = 'asc' | 'desc';

type PropertyComparisonProps = {
  embedded?: boolean;
};

export const PropertyComparison: React.FC<PropertyComparisonProps> = ({ embedded = false }) => {
  const { t, i18n } = useTranslation();
  const [comparisons, setComparisons] = useState<PropertyComparisonData[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Filters
  const [year, setYear] = useState<number>(new Date().getFullYear());
  const [sortBy, setSortBy] = useState<SortField>('net_income');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');

  // Fetch comparison data
  useEffect(() => {
    fetchComparisons();
  }, [year, sortBy, sortOrder]);

  const fetchComparisons = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const data = await propertyService.comparePortfolio(year, sortBy, sortOrder);
      setComparisons(data);
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Failed to load comparison data'));
    } finally {
      setIsLoading(false);
    }
  }, [year, sortBy, sortOrder]);

  // Prepare chart data
  const chartData = useMemo(() => {
    return comparisons.map(comp => ({
      address: comp.address.length > 25 ? comp.address.substring(0, 25) + '...' : comp.address,
      [t('properties.portfolio.rentalIncome')]: comp.rental_income,
      [t('properties.portfolio.expenses')]: comp.expenses,
      [t('properties.portfolio.netIncome')]: comp.net_income,
    }));
  }, [comparisons, t]);

  // Format currency
  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat(getLocaleForLanguage(i18n.language), {
      style: 'currency',
      currency: 'EUR',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  };

  // Format percentage
  const formatPercentage = (value: number): string => {
    return `${value.toFixed(2)}%`;
  };

  // Handle sort
  const handleSort = (field: SortField) => {
    if (sortBy === field) {
      // Toggle order if same field
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      // New field, default to desc
      setSortBy(field);
      setSortOrder('desc');
    }
  };

  // Get sort indicator
  const getSortIndicator = (field: SortField) => {
    if (sortBy !== field) return null;
    return sortOrder === 'asc' ? ' ↑' : ' ↓';
  };

  // Generate year options (current year and 5 years back)
  const yearOptions = useMemo(() => {
    const currentYear = new Date().getFullYear();
    const years = [];
    for (let i = 0; i < 6; i++) {
      years.push(currentYear - i);
    }
    return years;
  }, []);

  if (isLoading) {
    return (
      <div className="property-comparison">
        <div className="loading-state">
          <div className="spinner"></div>
          <p>{t('common.loading')}</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="property-comparison">
        <div className="error-state">
          <p className="error-message">{error}</p>
          <button onClick={fetchComparisons} className="btn-retry">
            {t('common.retry')}
          </button>
        </div>
      </div>
    );
  }

  if (comparisons.length === 0) {
    return (
      <div className="property-comparison">
        <div className="empty-state">
          <h2>{t('properties.portfolio.noProperties')}</h2>
          <p>{t('properties.portfolio.noPropertiesDescription')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`property-comparison${embedded ? ' property-comparison--embedded' : ''}`}>
      {/* Header with filters */}
      <div className="comparison-header">
        {!embedded && (
          <div className="header-content">
            <SubpageBackLink to="/advanced" />
            <h2>{t('properties.portfolio.propertyComparison')}</h2>
            <p className="subtitle">{t('properties.portfolio.propertyComparisonDescription')}</p>
          </div>
        )}
        
        <div className="filters">
          <div className="filter-group">
            <label htmlFor="year-filter">{t('dashboard.taxYear')}</label>
            <Select id="year-filter" value={String(year)} onChange={v => setYear(Number(v))}
              options={yearOptions.map(y => ({ value: String(y), label: String(y) }))} size="sm" />
          </div>
        </div>
      </div>

      {/* Bar Chart */}
      <div className="chart-section">
        <div className="chart-container">
          <ResponsiveContainer width="100%" height={400}>
            <BarChart
              data={chartData}
              margin={{ top: 20, right: 30, left: 20, bottom: 100 }}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis 
                dataKey="address" 
                angle={-45}
                textAnchor="end"
                height={120}
                interval={0}
              />
              <YAxis 
                label={{ 
                  value: t('properties.portfolio.amount'), 
                  angle: -90, 
                  position: 'insideLeft' 
                }}
              />
              <Tooltip 
                formatter={(value: number) => formatCurrency(value)}
                labelStyle={{ color: '#333' }}
              />
              <Legend wrapperStyle={{ paddingTop: '20px' }} />
              <Bar 
                dataKey={t('properties.portfolio.rentalIncome')}
                fill="#4CAF50" 
              />
              <Bar 
                dataKey={t('properties.portfolio.expenses')}
                fill="#FF9800" 
              />
              <Bar 
                dataKey={t('properties.portfolio.netIncome')}
                fill="#2196F3" 
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Sortable Table */}
      <div className="table-section">
        <div className="table-container">
          <table className="comparison-table">
            <thead>
              <tr>
                <th 
                  onClick={() => handleSort('address')}
                  className="sortable"
                >
                  {t('properties.address')}{getSortIndicator('address')}
                </th>
                <th 
                  onClick={() => handleSort('rental_income')}
                  className="sortable"
                >
                  {t('properties.portfolio.rentalIncome')}{getSortIndicator('rental_income')}
                </th>
                <th 
                  onClick={() => handleSort('expenses')}
                  className="sortable"
                >
                  {t('properties.portfolio.expenses')}{getSortIndicator('expenses')}
                </th>
                <th 
                  onClick={() => handleSort('net_income')}
                  className="sortable"
                >
                  {t('properties.portfolio.netIncome')}{getSortIndicator('net_income')}
                </th>
                <th 
                  onClick={() => handleSort('rental_yield')}
                  className="sortable"
                >
                  {t('properties.rentalYield')}{getSortIndicator('rental_yield')}
                </th>
                <th 
                  onClick={() => handleSort('expense_ratio')}
                  className="sortable"
                >
                  {t('properties.expenseRatio')}{getSortIndicator('expense_ratio')}
                </th>
              </tr>
            </thead>
            <tbody>
              {comparisons.map((comp) => (
                <tr key={comp.property_id}>
                  <td className="address-cell" title={comp.address}>
                    {comp.address}
                  </td>
                  <td className="number-cell">{formatCurrency(comp.rental_income)}</td>
                  <td className="number-cell">{formatCurrency(comp.expenses)}</td>
                  <td className={`number-cell ${comp.net_income >= 0 ? 'positive' : 'negative'}`}>
                    {formatCurrency(comp.net_income)}
                  </td>
                  <td className="number-cell">{formatPercentage(comp.rental_yield)}</td>
                  <td className="number-cell">{formatPercentage(comp.expense_ratio)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="total-row">
                <td><strong>{t('properties.portfolio.total')}</strong></td>
                <td className="number-cell">
                  <strong>{formatCurrency(comparisons.reduce((sum, c) => sum + c.rental_income, 0))}</strong>
                </td>
                <td className="number-cell">
                  <strong>{formatCurrency(comparisons.reduce((sum, c) => sum + c.expenses, 0))}</strong>
                </td>
                <td className="number-cell">
                  <strong>{formatCurrency(comparisons.reduce((sum, c) => sum + c.net_income, 0))}</strong>
                </td>
                <td className="number-cell">-</td>
                <td className="number-cell">-</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    </div>
  );
};
