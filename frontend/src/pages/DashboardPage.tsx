import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';
import { useDashboardStore } from '../stores/dashboardStore';
import { useAuthStore } from '../stores/authStore';
import { dashboardService } from '../services/dashboardService';
import DashboardOverview from '../components/dashboard/DashboardOverview';
import TrendCharts from '../components/dashboard/TrendCharts';
import SavingsSuggestions from '../components/dashboard/SavingsSuggestions';
import TaxCalendar from '../components/dashboard/TaxCalendar';
import WhatIfSimulator from '../components/dashboard/WhatIfSimulator';
import FlatRateComparison from '../components/dashboard/FlatRateComparison';
import RefundEstimate from '../components/dashboard/RefundEstimate';
import IncomeTypeHint from '../components/dashboard/IncomeTypeHint';
import { RecurringSuggestionsList } from '../components/recurring/RecurringSuggestionsList';
import { QuickActions } from '../components/dashboard/QuickActions';
import './DashboardPage.css';

const DashboardPage = () => {
  const { t } = useTranslation();
  const {
    data,
    deadlines,
    suggestions,
    isLoading,
    setData,
    setDeadlines,
    setSuggestions,
    setLoading,
  } = useDashboardStore();

  const currentYear = new Date().getFullYear();
  const [selectedYear, setSelectedYear] = useState(currentYear);
  const [chartData, setChartData] = useState<any>(null);
  const [propertyMetrics, setPropertyMetrics] = useState<any>(null);
  const { user } = useAuthStore();
  const navigate = useNavigate();
  const isGmbH = user?.user_type === 'gmbh';
  const isLandlordOrMixed = user?.user_type === 'landlord' || user?.user_type === 'mixed';

  // Generate year options: current year down to 5 years ago
  const yearOptions = Array.from({ length: 6 }, (_, i) => currentYear - i);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        // Fetch main dashboard data for selected year
        const dashboardData = await dashboardService.getDashboardData(selectedYear);
        setData(dashboardData);

        // Fetch property metrics for landlord/mixed users
        if (isLandlordOrMixed) {
          try {
            const metrics = await dashboardService.getPropertyMetrics(selectedYear);
            setPropertyMetrics(metrics);
          } catch (error) {
            console.error('Failed to fetch property metrics:', error);
            setPropertyMetrics(null);
          }
        }

        // Fetch suggestions — map API shape to component shape
        try {
          const suggestionsResp = await dashboardService.getSuggestions();
          const rawSuggestions = suggestionsResp?.suggestions || [];
          const mapped = rawSuggestions.map((s: any, i: number) => ({
            id: i + 1,
            title: s.title || '',
            description: s.description || '',
            potentialSavings: s.potential_savings || 0,
            actionLink: s.type === 'missing_deduction' ? '/transactions'
              : s.type === 'action_needed' ? '/documents'
              : s.type === 'getting_started' ? '/documents'
              : '/transactions',
            actionLabel: undefined,
          }));
          setSuggestions(mapped);
        } catch {
          setSuggestions([]);
        }

        // Fetch calendar deadlines — map API shape to component shape
        try {
          const calendarResp = await dashboardService.getCalendar();
          const rawDeadlines = calendarResp?.deadlines || [];
          const today = new Date().toISOString().split('T')[0];
          const mapped = rawDeadlines.map((d: any, i: number) => ({
            id: i + 1,
            title: d.title || '',
            date: d.date || '',
            description: d.description || '',
            isOverdue: d.date < today,
          }));
          setDeadlines(mapped);
        } catch {
          setDeadlines([]);
        }

        // Set chart data from dashboard response — map backend shapes to component shapes
        const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        const COLORS = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#6366f1', '#84cc16'];

        const mappedMonthly = (dashboardData.monthlyData || []).map((m: any) => ({
          month: MONTH_NAMES[(m.month || 1) - 1] || `M${m.month}`,
          income: m.income || 0,
          expenses: m.expenses || 0,
        }));

        const mappedIncomeCat = (dashboardData.incomeCategoryData || []).map((c: any, i: number) => ({
          name: c.category || c.name || 'Other',
          value: c.amount || c.value || 0,
          color: c.color || COLORS[i % COLORS.length],
        }));

        const mappedExpenseCat = (dashboardData.expenseCategoryData || []).map((c: any, i: number) => ({
          name: c.category || c.name || 'Other',
          value: c.amount || c.value || 0,
          color: c.color || COLORS[i % COLORS.length],
        }));

        setChartData({
          monthlyData: mappedMonthly,
          incomeCategoryData: mappedIncomeCat,
          expenseCategoryData: mappedExpenseCat,
          yearOverYearData: dashboardData.yearOverYearData,
        });

      } catch (error) {
        console.error('Failed to fetch dashboard data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [selectedYear, setData, setDeadlines, setSuggestions, setLoading, isLandlordOrMixed]);

  if (isLoading) {
    return (
      <div className="dashboard-page">
        <div className="loading">{t('common.loading')}</div>
      </div>
    );
  }

  const hasTransactions = data && (data.yearToDateIncome > 0 || data.yearToDateExpenses > 0);

  return (
    <div className="dashboard-page">
      <div className="dashboard-header">
        <div className="dashboard-header-top">
          <div>
            <h1>{t('dashboard.title')}</h1>
            <p className="dashboard-subtitle">{t('dashboard.subtitle')}</p>
          </div>
          <div className="year-selector">
            <label htmlFor="tax-year-select">{t('dashboard.taxYear', 'Steuerjahr')}</label>
            <select
              id="tax-year-select"
              value={selectedYear}
              onChange={(e) => setSelectedYear(Number(e.target.value))}
            >
              {yearOptions.map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Income Type Mismatch Hint */}
      <IncomeTypeHint />

      {/* Quick Actions Panel */}
      <QuickActions />

      {/* Employee Refund Estimate — not shown for GmbH */}
      {!isGmbH && hasTransactions && (
        <RefundEstimate
          estimatedRefund={data?.estimatedRefund}
          withheldTax={data?.withheldTax}
          calculatedTax={data?.calculatedTax}
          hasLohnzettel={data?.hasLohnzettel}
        />
      )}

      {/* GmbH KöSt Summary */}
      {isGmbH && data?.gmbhTax && (
        <div className="dashboard-summary-card">
          <h3 className="dashboard-summary-title">{t('dashboard.gmbhTax.title', 'Körperschaftsteuer (KöSt)')}</h3>
          <div className="dashboard-summary-grid">
            <div>
              <div className="dashboard-summary-label">{t('dashboard.gmbhTax.koest', 'KöSt (23%)')}</div>
              <div className="dashboard-summary-value">€ {data.gmbhTax.koest.toLocaleString('de-AT', { minimumFractionDigits: 2 })}</div>
            </div>
            <div>
              <div className="dashboard-summary-label">{t('dashboard.gmbhTax.profitAfterKoest', 'Gewinn nach KöSt')}</div>
              <div className="dashboard-summary-value">€ {data.gmbhTax.profitAfterKoest.toLocaleString('de-AT', { minimumFractionDigits: 2 })}</div>
            </div>
            <div>
              <div className="dashboard-summary-label">{t('dashboard.gmbhTax.kest', 'KESt auf Dividende (27,5%)')}</div>
              <div className="dashboard-summary-value">€ {data.gmbhTax.kestOnDividend.toLocaleString('de-AT', { minimumFractionDigits: 2 })}</div>
            </div>
            <div>
              <div className="dashboard-summary-label">{t('dashboard.gmbhTax.totalBurden', 'Gesamtsteuerbelastung')}</div>
              <div className="dashboard-summary-value text-danger">€ {data.gmbhTax.totalTaxBurden.toLocaleString('de-AT', { minimumFractionDigits: 2 })}</div>
            </div>
            <div>
              <div className="dashboard-summary-label">{t('dashboard.gmbhTax.effectiveRate', 'Effektiver Steuersatz')}</div>
              <div className="dashboard-summary-value">{(data.gmbhTax.effectiveTotalRate * 100).toFixed(1)}%</div>
            </div>
            <div>
              <div className="dashboard-summary-label">{t('dashboard.gmbhTax.mindestKoest', 'Mindest-KöSt')}</div>
              <div className="dashboard-summary-value">€ {data.gmbhTax.mindestKoest.toLocaleString('de-AT', { minimumFractionDigits: 2 })}</div>
            </div>
          </div>
        </div>
      )}

      {/* Property Portfolio Summary for Landlords */}
      {isLandlordOrMixed && propertyMetrics?.has_properties && (
        <div className="dashboard-summary-card">
          <div className="dashboard-summary-header">
            <h3 className="dashboard-summary-title">{t('properties.portfolio.title', 'Immobilienportfolio')}</h3>
            <Link to="/properties" className="dashboard-summary-link">
              {t('common.viewDetails', 'Details anzeigen')} &rarr;
            </Link>
          </div>
          <div className="dashboard-summary-grid">
            <div>
              <div className="dashboard-summary-label">{t('properties.portfolio.activeProperties', 'Aktive Immobilien')}</div>
              <div className="dashboard-summary-value">{propertyMetrics.active_properties_count}</div>
            </div>
            <div>
              <div className="dashboard-summary-label">{t('properties.portfolio.totalRentalIncome', 'Mieteinnahmen gesamt')}</div>
              <div className="dashboard-summary-value text-success">
                € {propertyMetrics.total_rental_income.toLocaleString('de-AT', { minimumFractionDigits: 2 })}
              </div>
            </div>
            <div>
              <div className="dashboard-summary-label">{t('properties.portfolio.totalExpenses', 'Ausgaben gesamt')}</div>
              <div className="dashboard-summary-value text-warning">
                € {propertyMetrics.total_property_expenses.toLocaleString('de-AT', { minimumFractionDigits: 2 })}
              </div>
            </div>
            <div>
              <div className="dashboard-summary-label">{t('properties.portfolio.netRentalIncome', 'Netto-Mieteinnahmen')}</div>
              <div className={`dashboard-summary-value ${propertyMetrics.net_rental_income >= 0 ? 'text-success' : 'text-danger'}`}>
                € {propertyMetrics.net_rental_income.toLocaleString('de-AT', { minimumFractionDigits: 2 })}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Dashboard Overview Cards */}
      {data && (
        <DashboardOverview
          yearToDateIncome={data.yearToDateIncome}
          yearToDateExpenses={data.yearToDateExpenses}
          estimatedTax={data.estimatedTax}
          paidTax={data.paidTax}
          remainingTax={data.remainingTax}
          netIncome={data.netIncome}
          vatThresholdDistance={data.vatThresholdDistance}
        />
      )}

      {/* Quick Start Guide for new users */}
      {!hasTransactions && (
        <div className="dashboard-quick-start">
          <h3>🚀 {t('dashboard.quickStart.title', 'Erste Schritte')}</h3>
          <div className="quick-start-grid">
            <div className="quick-start-card" onClick={() => navigate('/transactions')} role="button" tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && navigate('/transactions')}>
              <span className="quick-start-icon">📝</span>
              <span className="quick-start-label">{t('dashboard.quickStart.addTransaction', 'Transaktion hinzufügen')}</span>
            </div>
            <div className="quick-start-card" onClick={() => navigate('/documents')} role="button" tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && navigate('/documents')}>
              <span className="quick-start-icon">📄</span>
              <span className="quick-start-label">{t('dashboard.quickStart.uploadDocument', 'Beleg hochladen')}</span>
            </div>
            <div className="quick-start-card" onClick={() => navigate('/profile')} role="button" tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && navigate('/profile')}>
              <span className="quick-start-icon">👤</span>
              <span className="quick-start-label">{t('dashboard.quickStart.setupProfile', 'Profil einrichten')}</span>
            </div>
          </div>
        </div>
      )}

      {/* Savings Suggestions */}
      {suggestions.length > 0 && (
        <SavingsSuggestions suggestions={suggestions} />
      )}

      {/* Recurring Transaction Suggestions */}
      <div style={{ marginBottom: '2rem' }}>
        <RecurringSuggestionsList />
      </div>

      {/* Tax Calendar */}
      {deadlines.length > 0 && <TaxCalendar deadlines={deadlines} />}

      {/* Trend Charts — only when there's data */}
      {hasTransactions && chartData && (
        <TrendCharts
          monthlyData={chartData.monthlyData}
          incomeCategoryData={chartData.incomeCategoryData}
          expenseCategoryData={chartData.expenseCategoryData}
          yearOverYearData={chartData.yearOverYearData}
        />
      )}

      {/* What-If Simulator */}
      <WhatIfSimulator />

      {/* Flat-Rate Comparison — not applicable for GmbH */}
      {!isGmbH && <FlatRateComparison year={selectedYear} />}
    </div>
  );
};

export default DashboardPage;
