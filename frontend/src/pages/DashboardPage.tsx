import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import Select from '../components/common/Select';
import { useDashboardStore } from '../stores/dashboardStore';
import { useAuthStore } from '../stores/authStore';
import { dashboardService } from '../services/dashboardService';
import DashboardOverview from '../components/dashboard/DashboardOverview';
import TrendCharts from '../components/dashboard/TrendCharts';
import DocumentUpload from '../components/documents/DocumentUpload';
import type { Document as TaxDocument } from '../types/document';
import { getShortMonthLabels, normalizeLanguage } from '../utils/locale';
import { useRefreshStore } from '../stores/refreshStore';
import { useSubscriptionStore } from '../stores/subscriptionStore';
import './DashboardPage.css';

const DashboardPage = () => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const {
    data,
    isLoading,
    setData,
    setLoading,
  } = useDashboardStore();

  const currentYear = new Date().getFullYear();
  const [selectedYear, setSelectedYear] = useState(currentYear);
  const [activeYears, setActiveYears] = useState<number[]>([]);
  const [chartData, setChartData] = useState<any>(null);
  const { user } = useAuthStore();
  const dashboardVersion = useRefreshStore((s) => s.dashboardVersion);
  const currentLanguage = normalizeLanguage(i18n.resolvedLanguage || i18n.language);

  const yearOptions = activeYears.length > 0 ? activeYears : [currentYear];

  const { subscription, fetchSubscription } = useSubscriptionStore();
  useEffect(() => { fetchSubscription(); }, [fetchSubscription]);

  const trialDaysRemaining = (() => {
    if (subscription?.status !== 'trialing' || !subscription.current_period_end) return null;
    const diff = new Date(subscription.current_period_end).getTime() - Date.now();
    const days = Math.ceil(diff / 86400000);
    return days > 0 ? days : 0;
  })();

  const completeOnboarding = useAuthStore((s) => s.completeOnboarding);

  const handleDashboardUploadSubmitted = useCallback((_documents: TaxDocument[]) => {
    if (user && !user.onboarding_completed) {
      completeOnboarding();
    }
  }, [user, completeOnboarding]);

  const buildChartData = useCallback((dashboardData: any) => {
    const monthNames = getShortMonthLabels(currentLanguage);
    const colors = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#6366f1', '#84cc16'];
    setChartData({
      monthlyData: (dashboardData.monthlyData || []).map((m: any) => ({
        month: monthNames[(m.month || 1) - 1] || `M${m.month}`,
        income: m.income || 0,
        expenses: m.expenses || 0,
      })),
      incomeCategoryData: (dashboardData.incomeCategoryData || []).map((c: any, i: number) => ({
        name: c.category || c.name || 'Other',
        value: c.amount || c.value || 0,
        color: c.color || colors[i % colors.length],
      })),
      expenseCategoryData: (dashboardData.expenseCategoryData || []).map((c: any, i: number) => ({
        name: c.category || c.name || 'Other',
        value: c.amount || c.value || 0,
        color: c.color || colors[i % colors.length],
      })),
      yearOverYearData: dashboardData.yearOverYearData,
    });
  }, [currentLanguage]);

  useEffect(() => {
    const hasActivity = (d: any) =>
      d && ((d.yearToDateIncome || 0) > 0 || (d.yearToDateExpenses || 0) > 0 || (d.pendingReviewCount || 0) > 0);

    const fetchData = async () => {
      setLoading(true);

      try {
        let dashboardData = await dashboardService.getDashboardData(selectedYear);

        // Scan all candidate years to find which ones have data
        const foundYears: number[] = [];
        if (hasActivity(dashboardData)) foundYears.push(selectedYear);

        for (let y = currentYear; y >= currentYear - 5; y--) {
          if (y === selectedYear) continue;
          try {
            const probe = await dashboardService.getDashboardData(y);
            if (hasActivity(probe)) {
              foundYears.push(y);
              if (!hasActivity(dashboardData) && selectedYear === currentYear) {
                dashboardData = probe;
                setSelectedYear(y);
              }
            }
          } catch { /* skip */ }
        }
        setActiveYears(foundYears.sort((a, b) => b - a));
        setData(dashboardData);
        buildChartData(dashboardData);
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error);
      } finally {
        setLoading(false);
      }
    };

    void fetchData();
  }, [
    buildChartData,
    currentYear,
    dashboardVersion,
    selectedYear,
    setData,
    setLoading,
  ]);

  if (isLoading) {
    return (
      <div className="dashboard-page">
        <div className="loading">{t('common.loading')}</div>
      </div>
    );
  }

  const hasAnyActivity = data && (
    data.yearToDateIncome > 0 ||
    data.yearToDateExpenses > 0 ||
    (data.pendingReviewCount ?? 0) > 0
  );


  const trialBanner = trialDaysRemaining !== null ? (
    <div className="dashboard-trial-banner">
      <span className="dashboard-trial-days">{trialDaysRemaining}</span>
      <span className="dashboard-trial-text">
        {t('dashboard.trialRemaining', '{{days}} days left in your Pro trial', { days: trialDaysRemaining })}
      </span>
      <button className="btn-link" onClick={() => navigate('/pricing')}>
        {t('dashboard.trialUpgrade', 'Upgrade now')}
      </button>
    </div>
  ) : null;

  if (!hasAnyActivity) {
    return (
      <div className="dashboard-page">
        {trialBanner}
        <div className="dashboard-header">
          <div className="dashboard-header-top">
            <div>
              <h1>{t('dashboard.welcomeTitle', 'Welcome to Taxja!')}</h1>
              <p className="dashboard-subtitle">
                {t('dashboard.welcomeSubtitle', 'Upload your first document to get started.')}
              </p>
            </div>
            {activeYears.length > 0 && (
              <div className="year-selector">
                <label htmlFor="tax-year-select">{t('dashboard.taxYear', 'Tax Year')}</label>
                <Select id="tax-year-select" value={String(selectedYear)} onChange={v => setSelectedYear(Number(v))}
                  options={yearOptions.map(y => ({ value: String(y), label: String(y) }))} size="sm" />
              </div>
            )}
          </div>
        </div>
        <DocumentUpload onDocumentsSubmitted={handleDashboardUploadSubmitted} />
      </div>
    );
  }

  return (
    <div className="dashboard-page">
      {trialBanner}
      <div className="dashboard-header">
        <div className="dashboard-header-top">
          <div>
            <h1>{t('dashboard.title')}</h1>
            <p className="dashboard-subtitle">{t('dashboard.subtitle')}</p>
          </div>
          <div className="year-selector">
            <label htmlFor="tax-year-select">{t('dashboard.taxYear', 'Tax Year')}</label>
            <Select id="tax-year-select" value={String(selectedYear)} onChange={v => setSelectedYear(Number(v))}
              options={yearOptions.map(y => ({ value: String(y), label: String(y) }))} size="sm" />
          </div>
        </div>
      </div>

      <DocumentUpload onDocumentsSubmitted={handleDashboardUploadSubmitted} />

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

      {chartData && (
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
