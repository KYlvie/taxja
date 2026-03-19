import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDashboardStore } from '../stores/dashboardStore';
import { useAuthStore } from '../stores/authStore';
import { dashboardService } from '../services/dashboardService';
import DashboardOverview from '../components/dashboard/DashboardOverview';
import TrendCharts from '../components/dashboard/TrendCharts';
import IncomeTypeHint from '../components/dashboard/IncomeTypeHint';
import { RecurringSuggestionsList } from '../components/recurring/RecurringSuggestionsList';
import { QuickActions } from '../components/dashboard/QuickActions';
import { formatCurrency, getShortMonthLabels, normalizeLanguage } from '../utils/locale';
import { useRefreshStore } from '../stores/refreshStore';
import './DashboardPage.css';

const DashboardPage = () => {
  const { t, i18n } = useTranslation();
  const {
    data,
    isLoading,
    setData,
    setSuggestions,
    setLoading,
  } = useDashboardStore();

  const currentYear = new Date().getFullYear();
  const [selectedYear, setSelectedYear] = useState(currentYear);
  const [chartData, setChartData] = useState<any>(null);
  const { user } = useAuthStore();
  const dashboardVersion = useRefreshStore((s) => s.dashboardVersion);
  const isGmbH = user?.user_type === 'gmbh';
  const currentLanguage = normalizeLanguage(i18n.resolvedLanguage || i18n.language);
  const formatMoney = (amount: number) => formatCurrency(amount, currentLanguage);

  const yearOptions = Array.from({ length: 6 }, (_, i) => currentYear - i);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);

      try {
        const dashboardData = await dashboardService.getDashboardData(selectedYear);
        setData(dashboardData);

        try {
          const suggestionsResp = await dashboardService.getSuggestions(selectedYear);
          const rawSuggestions = suggestionsResp?.suggestions || [];
          const mapped = rawSuggestions.map((suggestion: any, index: number) => ({
            id: index + 1,
            title: suggestion.title || '',
            description: suggestion.description || '',
            potentialSavings: suggestion.potential_savings || 0,
            actionLink: suggestion.action_url || '/transactions',
            actionLabel: suggestion.action_label || undefined,
            type: suggestion.type,
            documentType: suggestion.document_type,
          }));
          setSuggestions(mapped);
        } catch {
          setSuggestions([]);
        }

        const monthNames = getShortMonthLabels(currentLanguage);
        const colors = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#6366f1', '#84cc16'];

        const mappedMonthly = (dashboardData.monthlyData || []).map((month: any) => ({
          month: monthNames[(month.month || 1) - 1] || `M${month.month}`,
          income: month.income || 0,
          expenses: month.expenses || 0,
        }));

        const mappedIncomeCat = (dashboardData.incomeCategoryData || []).map((category: any, index: number) => ({
          name: category.category || category.name || 'Other',
          value: category.amount || category.value || 0,
          color: category.color || colors[index % colors.length],
        }));

        const mappedExpenseCat = (dashboardData.expenseCategoryData || []).map((category: any, index: number) => ({
          name: category.category || category.name || 'Other',
          value: category.amount || category.value || 0,
          color: category.color || colors[index % colors.length],
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

    void fetchData();
  }, [
    currentLanguage,
    dashboardVersion,
    selectedYear,
    setData,
    setLoading,
    setSuggestions,
  ]);

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
            <label htmlFor="tax-year-select">{t('dashboard.taxYear', 'Tax Year')}</label>
            <select
              id="tax-year-select"
              value={selectedYear}
              onChange={(e) => setSelectedYear(Number(e.target.value))}
            >
              {yearOptions.map((year) => (
                <option key={year} value={year}>
                  {year}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <IncomeTypeHint />
      <QuickActions />

      {isGmbH && data?.gmbhTax && (
        <div className="dashboard-summary-card">
          <h3 className="dashboard-summary-title">
            {t('dashboard.gmbhTax.title', 'Corporate Income Tax')}
          </h3>
          <div className="dashboard-summary-grid">
            <div>
              <div className="dashboard-summary-label">{t('dashboard.gmbhTax.koest', 'Corporate Tax (23%)')}</div>
              <div className="dashboard-summary-value">{formatMoney(data.gmbhTax.koest)}</div>
            </div>
            <div>
              <div className="dashboard-summary-label">
                {t('dashboard.gmbhTax.profitAfterKoest', 'Profit After Corporate Tax')}
              </div>
              <div className="dashboard-summary-value">{formatMoney(data.gmbhTax.profitAfterKoest)}</div>
            </div>
            <div>
              <div className="dashboard-summary-label">
                {t('dashboard.gmbhTax.kest', 'Dividend Withholding Tax (27.5%)')}
              </div>
              <div className="dashboard-summary-value">{formatMoney(data.gmbhTax.kestOnDividend)}</div>
            </div>
            <div>
              <div className="dashboard-summary-label">
                {t('dashboard.gmbhTax.totalBurden', 'Total Tax Burden')}
              </div>
              <div className="dashboard-summary-value text-danger">
                {formatMoney(data.gmbhTax.totalTaxBurden)}
              </div>
            </div>
            <div>
              <div className="dashboard-summary-label">
                {t('dashboard.gmbhTax.effectiveRate', 'Effective Tax Rate')}
              </div>
              <div className="dashboard-summary-value">
                {(data.gmbhTax.effectiveTotalRate * 100).toFixed(1)}%
              </div>
            </div>
            <div>
              <div className="dashboard-summary-label">
                {t('dashboard.gmbhTax.mindestKoest', 'Minimum Corporate Tax')}
              </div>
              <div className="dashboard-summary-value">{formatMoney(data.gmbhTax.mindestKoest)}</div>
            </div>
          </div>
        </div>
      )}

      {data && (
        <DashboardOverview
          yearToDateIncome={data.yearToDateIncome}
          yearToDateExpenses={data.yearToDateExpenses}
          estimatedTax={data.estimatedTax}
          paidTax={data.paidTax}
          remainingTax={data.remainingTax}
          netIncome={data.netIncome}
          vatThresholdDistance={data.vatThresholdDistance}
          pendingReviewCount={data.pendingReviewCount}
        />
      )}

      {/* Quick Start removed — QuickActions already covers the same actions */}

      <RecurringSuggestionsList />

      {hasTransactions && chartData && (
        <TrendCharts
          monthlyData={chartData.monthlyData}
          incomeCategoryData={chartData.incomeCategoryData}
          expenseCategoryData={chartData.expenseCategoryData}
          yearOverYearData={chartData.yearOverYearData}
        />
      )}
    </div>
  );
};

export default DashboardPage;
