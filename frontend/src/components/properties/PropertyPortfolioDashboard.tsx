import React, { useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { usePropertyStore } from '../../stores/propertyStore';
import { PropertyStatus } from '../../types/property';
import SubpageBackLink from '../common/SubpageBackLink';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import './PropertyPortfolioDashboard.css';

interface PortfolioMetrics {
  totalBuildingValue: number;
  totalAnnualDepreciation: number;
  totalRentalIncome: number;
  totalPropertyExpenses: number;
  netRentalIncome: number;
  activePropertiesCount: number;
}

interface PropertyComparisonData {
  address: string;
  rentalIncome: number;
  expenses: number;
  netIncome: number;
}

interface DepreciationScheduleData {
  year: number;
  depreciation: number;
}

export const PropertyPortfolioDashboard: React.FC = () => {
  const { t } = useTranslation();
  const { properties, isLoading, fetchProperties } = usePropertyStore();

  useEffect(() => {
    fetchProperties(false); // Fetch only active properties
  }, [fetchProperties]);

  // Calculate portfolio metrics
  const portfolioMetrics = useMemo((): PortfolioMetrics => {
    const activeProperties = properties.filter(
      (p) => p.status === PropertyStatus.ACTIVE
    );

    const totalBuildingValue = activeProperties.reduce(
      (sum, p) => sum + p.building_value,
      0
    );

    // Calculate annual depreciation for each property
    const totalAnnualDepreciation = activeProperties.reduce((sum, p) => {
      const annualDepreciation = p.building_value * p.depreciation_rate;
      return sum + annualDepreciation;
    }, 0);

    // Note: In a real implementation, these would come from transaction data
    // For now, we'll use placeholder values that would be fetched from the API
    const totalRentalIncome = 0;
    const totalPropertyExpenses = 0;
    const netRentalIncome = totalRentalIncome - totalPropertyExpenses;

    return {
      totalBuildingValue,
      totalAnnualDepreciation,
      totalRentalIncome,
      totalPropertyExpenses,
      netRentalIncome,
      activePropertiesCount: activeProperties.length,
    };
  }, [properties]);

  // Prepare property comparison data for bar chart
  const propertyComparisonData = useMemo((): PropertyComparisonData[] => {
    const activeProperties = properties.filter(
      (p) => p.status === PropertyStatus.ACTIVE
    );

    return activeProperties.map((property) => ({
      address: property.address.length > 30 
        ? property.address.substring(0, 30) + '...' 
        : property.address,
      rentalIncome: 0, // Would come from transaction data
      expenses: 0, // Would come from transaction data
      netIncome: 0, // Would be calculated from transactions
    }));
  }, [properties]);

  // Prepare depreciation schedule data for line chart
  const depreciationScheduleData = useMemo((): DepreciationScheduleData[] => {
    const currentYear = new Date().getFullYear();
    const years = 10; // Show 10-year projection
    const activeProperties = properties.filter(
      (p) => p.status === PropertyStatus.ACTIVE
    );

    const scheduleData: DepreciationScheduleData[] = [];

    for (let i = 0; i < years; i++) {
      const year = currentYear + i;
      
      // Calculate total depreciation for this year across all properties
      const totalDepreciation = activeProperties.reduce((sum, property) => {
        const purchaseYear = new Date(property.purchase_date).getFullYear();
        
        // Only include depreciation if property was purchased before this year
        if (purchaseYear <= year) {
          const annualDepreciation = property.building_value * property.depreciation_rate;
          
          // Check if property is fully depreciated
          const yearsOwned = year - purchaseYear;
          const totalDepreciated = annualDepreciation * yearsOwned;
          
          if (totalDepreciated < property.building_value) {
            return sum + annualDepreciation;
          }
        }
        
        return sum;
      }, 0);

      scheduleData.push({
        year,
        depreciation: totalDepreciation,
      });
    }

    return scheduleData;
  }, [properties]);

  // Format currency
  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat('de-AT', {
      style: 'currency',
      currency: 'EUR',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  };

  if (isLoading) {
    return (
      <div className="portfolio-dashboard">
        <div className="loading-state">
          <div className="spinner"></div>
          <p>{t('common.loading')}</p>
        </div>
      </div>
    );
  }

  if (portfolioMetrics.activePropertiesCount === 0) {
    return (
      <div className="portfolio-dashboard">
        <div className="empty-state">
          <h2>{t('properties.portfolio.noProperties')}</h2>
          <p>{t('properties.portfolio.noPropertiesDescription')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="portfolio-dashboard">
      <div className="dashboard-header">
        <SubpageBackLink to="/advanced" />
        <h1>{t('properties.portfolio.title')}</h1>
        <p className="subtitle">{t('properties.portfolio.subtitle')}</p>
      </div>

      {/* Portfolio Metrics Cards */}
      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-icon">🏢</div>
          <div className="metric-content">
            <h3>{t('properties.portfolio.activeProperties')}</h3>
            <p className="metric-value">{portfolioMetrics.activePropertiesCount}</p>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-icon">💰</div>
          <div className="metric-content">
            <h3>{t('properties.portfolio.totalBuildingValue')}</h3>
            <p className="metric-value">{formatCurrency(portfolioMetrics.totalBuildingValue)}</p>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-icon">📉</div>
          <div className="metric-content">
            <h3>{t('properties.portfolio.totalAnnualDepreciation')}</h3>
            <p className="metric-value">{formatCurrency(portfolioMetrics.totalAnnualDepreciation)}</p>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-icon">📈</div>
          <div className="metric-content">
            <h3>{t('properties.portfolio.totalRentalIncome')}</h3>
            <p className="metric-value">{formatCurrency(portfolioMetrics.totalRentalIncome)}</p>
            <p className="metric-label">{t('properties.portfolio.currentYear')}</p>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-icon">💸</div>
          <div className="metric-content">
            <h3>{t('properties.portfolio.totalExpenses')}</h3>
            <p className="metric-value">{formatCurrency(portfolioMetrics.totalPropertyExpenses)}</p>
            <p className="metric-label">{t('properties.portfolio.currentYear')}</p>
          </div>
        </div>

        <div className="metric-card highlight">
          <div className="metric-icon">✅</div>
          <div className="metric-content">
            <h3>{t('properties.portfolio.netRentalIncome')}</h3>
            <p className="metric-value">{formatCurrency(portfolioMetrics.netRentalIncome)}</p>
            <p className="metric-label">{t('properties.portfolio.currentYear')}</p>
          </div>
        </div>
      </div>

      {/* Property Comparison Chart */}
      {propertyComparisonData.length > 0 && (
        <div className="chart-section">
          <h2>{t('properties.portfolio.propertyComparison')}</h2>
          <p className="chart-description">
            {t('properties.portfolio.propertyComparisonDescription')}
          </p>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height={400}>
              <BarChart
                data={propertyComparisonData}
                margin={{ top: 20, right: 30, left: 20, bottom: 80 }}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis 
                  dataKey="address" 
                  angle={-45}
                  textAnchor="end"
                  height={100}
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
                <Legend />
                <Bar 
                  dataKey="rentalIncome" 
                  fill="#4CAF50" 
                  name={t('properties.portfolio.rentalIncome')}
                />
                <Bar 
                  dataKey="expenses" 
                  fill="#FF9800" 
                  name={t('properties.portfolio.expenses')}
                />
                <Bar 
                  dataKey="netIncome" 
                  fill="#2196F3" 
                  name={t('properties.portfolio.netIncome')}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Depreciation Schedule Chart */}
      {depreciationScheduleData.length > 0 && (
        <div className="chart-section">
          <h2>{t('properties.portfolio.depreciationSchedule')}</h2>
          <p className="chart-description">
            {t('properties.portfolio.depreciationScheduleDescription')}
          </p>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height={400}>
              <LineChart
                data={depreciationScheduleData}
                margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis 
                  dataKey="year"
                  label={{ 
                    value: t('properties.portfolio.year'), 
                    position: 'insideBottom', 
                    offset: -10 
                  }}
                />
                <YAxis 
                  label={{ 
                    value: t('properties.portfolio.annualDepreciation'), 
                    angle: -90, 
                    position: 'insideLeft' 
                  }}
                />
                <Tooltip 
                  formatter={(value: number) => formatCurrency(value)}
                  labelFormatter={(label) => `${t('properties.portfolio.year')}: ${label}`}
                />
                <Legend />
                <Line 
                  type="monotone" 
                  dataKey="depreciation" 
                  stroke="#9C27B0" 
                  strokeWidth={2}
                  name={t('properties.portfolio.totalDepreciation')}
                  dot={{ r: 4 }}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Property Comparison Table */}
      <div className="table-section">
        <h2>{t('properties.portfolio.propertyComparisonTable')}</h2>
        <div className="table-container">
          <table className="comparison-table">
            <thead>
              <tr>
                <th>{t('properties.address')}</th>
                <th>{t('properties.buildingValue')}</th>
                <th>{t('properties.portfolio.rentalIncome')}</th>
                <th>{t('properties.portfolio.expenses')}</th>
                <th>{t('properties.portfolio.netIncome')}</th>
                <th>{t('properties.portfolio.annualDepreciation')}</th>
              </tr>
            </thead>
            <tbody>
              {properties
                .filter((p) => p.status === PropertyStatus.ACTIVE)
                .map((property) => {
                  const annualDepreciation = property.building_value * property.depreciation_rate;
                  const rentalIncome = 0; // Would come from transaction data
                  const expenses = 0; // Would come from transaction data
                  const netIncome = rentalIncome - expenses;

                  return (
                    <tr key={property.id}>
                      <td className="address-cell">{property.address}</td>
                      <td>{formatCurrency(property.building_value)}</td>
                      <td>{formatCurrency(rentalIncome)}</td>
                      <td>{formatCurrency(expenses)}</td>
                      <td className={netIncome >= 0 ? 'positive' : 'negative'}>
                        {formatCurrency(netIncome)}
                      </td>
                      <td>{formatCurrency(annualDepreciation)}</td>
                    </tr>
                  );
                })}
            </tbody>
            <tfoot>
              <tr className="total-row">
                <td><strong>{t('properties.portfolio.total')}</strong></td>
                <td><strong>{formatCurrency(portfolioMetrics.totalBuildingValue)}</strong></td>
                <td><strong>{formatCurrency(portfolioMetrics.totalRentalIncome)}</strong></td>
                <td><strong>{formatCurrency(portfolioMetrics.totalPropertyExpenses)}</strong></td>
                <td className={portfolioMetrics.netRentalIncome >= 0 ? 'positive' : 'negative'}>
                  <strong>{formatCurrency(portfolioMetrics.netRentalIncome)}</strong>
                </td>
                <td><strong>{formatCurrency(portfolioMetrics.totalAnnualDepreciation)}</strong></td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    </div>
  );
};
