import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import api from '../../services/api';
import { getLocaleForLanguage } from '../../utils/locale';
import GovernancePanel from '../../components/admin/GovernancePanel';
import './AdminDashboard.css';

interface RevenueData {
  mrr: number;
  arr: number;
  active_subscriptions: number;
  plan_distribution: Record<string, number>;
}

interface SubscriptionData {
  by_status: Record<string, number>;
  by_plan: Record<string, number>;
}

interface ConversionData {
  trial_users: number;
  converted_users: number;
  conversion_rate: number;
}

interface ChurnData {
  period_days: number;
  churn_by_plan: Record<string, { canceled: number; active: number; churn_rate: number }>;
}

type AdminTab = 'business' | 'governance';

const AdminDashboard: React.FC = () => {
  const { t, i18n } = useTranslation();
  const [activeTab, setActiveTab] = useState<AdminTab>('business');
  const [revenue, setRevenue] = useState<RevenueData | null>(null);
  const [subscriptions, setSubscriptions] = useState<SubscriptionData | null>(null);
  const [conversion, setConversion] = useState<ConversionData | null>(null);
  const [churn, setChurn] = useState<ChurnData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const locale = getLocaleForLanguage(i18n.resolvedLanguage || i18n.language);

  useEffect(() => { fetchDashboardData(); }, []);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      setError(null);

      const [revenueRes, subsRes, convRes, churnRes] = await Promise.allSettled([
        api.get('/admin/analytics/revenue'),
        api.get('/admin/analytics/subscriptions'),
        api.get('/admin/analytics/conversion'),
        api.get('/admin/analytics/churn'),
      ]);

      if (revenueRes.status === 'fulfilled') setRevenue(revenueRes.value.data);
      if (subsRes.status === 'fulfilled') setSubscriptions(subsRes.value.data);
      if (convRes.status === 'fulfilled') setConversion(convRes.value.data);
      if (churnRes.status === 'fulfilled') setChurn(churnRes.value.data);

      // Log any failed requests for debugging
      [revenueRes, subsRes, convRes, churnRes].forEach((res, i) => {
        if (res.status === 'rejected') {
          const names = ['revenue', 'subscriptions', 'conversion', 'churn'];
          console.error(`Admin analytics ${names[i]} failed:`, res.reason);
        }
      });
    } catch (err) {
      console.error('Failed to fetch dashboard data:', err);
      setError(t('admin.dashboard.fetchError'));
    } finally {
      setLoading(false);
    }
  };

  const fmtCurrency = (value: number) =>
    new Intl.NumberFormat(locale, { style: 'currency', currency: 'EUR', minimumFractionDigits: 2 }).format(value);

  const planLabel = (plan: string) => {
    const key = `pricing.plans.${plan}.name`;
    const label = t(key);
    return label === key ? plan : label;
  };

  const statusLabel = (status: string) => {
    const key = `admin.status.${status}`;
    const label = t(key);
    return label === key ? status : label;
  };

  if (loading) return <div className="admin-dashboard loading">{t('common.loading')}</div>;
  if (error) return (
    <div className="admin-dashboard error">
      <p>{error}</p>
      <button type="button" onClick={fetchDashboardData}>{t('common.retry')}</button>
    </div>
  );

  // Plan distribution — max for bar width
  const planEntries = Object.entries(subscriptions?.by_plan ?? {});
  const maxPlanCount = Math.max(...planEntries.map(([, c]) => c), 1);

  // Status order
  const statusOrder = ['active', 'trialing', 'past_due', 'canceled'];
  const statusEntries = Object.entries(subscriptions?.by_status ?? {})
    .sort(([a], [b]) => statusOrder.indexOf(a) - statusOrder.indexOf(b));

  return (
    <div className="admin-dashboard">
      {/* Header */}
      <div className="adm-page-header">
        <h1>{t('admin.dashboard.title')}</h1>
        <p className="adm-page-subtitle">
          {t('admin.dashboard.subtitle', 'Real-time overview of subscriptions, revenue, and user activity')}
        </p>
        <div className="adm-tabs">
          <button
            type="button"
            className={`adm-tab ${activeTab === 'business' ? 'active' : ''}`}
            onClick={() => setActiveTab('business')}
          >
            💰 {t('admin.dashboard.businessTab', 'Business')}
          </button>
          <button
            type="button"
            className={`adm-tab ${activeTab === 'governance' ? 'active' : ''}`}
            onClick={() => setActiveTab('governance')}
          >
            🤖 {t('admin.dashboard.governanceTab', 'AI Governance')}
          </button>
        </div>
      </div>

      {activeTab === 'governance' ? (
        <GovernancePanel />
      ) : (
      <>
      {/* KPI cards */}
      <div className="adm-kpi-row">
        <div className="adm-kpi">
          <div className="adm-kpi-icon revenue">💰</div>
          <div className="adm-kpi-label">{t('admin.metrics.mrr')}</div>
          <div className="adm-kpi-value">{fmtCurrency(revenue?.mrr ?? 0)}</div>
        </div>
        <div className="adm-kpi">
          <div className="adm-kpi-icon arr">📈</div>
          <div className="adm-kpi-label">{t('admin.metrics.arr')}</div>
          <div className="adm-kpi-value">{fmtCurrency(revenue?.arr ?? 0)}</div>
        </div>
        <div className="adm-kpi">
          <div className="adm-kpi-icon subs">👥</div>
          <div className="adm-kpi-label">{t('admin.metrics.activeSubs')}</div>
          <div className="adm-kpi-value">{revenue?.active_subscriptions ?? 0}</div>
        </div>
      </div>

      {/* Plan distribution + Status */}
      <div className="adm-grid-2">
        <div className="adm-section">
          <h3 className="adm-section-title">
            <span className="adm-section-icon">📊</span>
            {t('admin.dashboard.subscriptions')}
          </h3>
          <div className="adm-plan-bars">
            {planEntries.map(([plan, count]) => (
              <div className="adm-plan-row" key={plan}>
                <span className="adm-plan-name">{planLabel(plan)}</span>
                <div className="adm-plan-bar-track">
                  <div
                    className={`adm-plan-bar-fill ${plan}`}
                    style={{ width: `${(count / maxPlanCount) * 100}%` }}
                  >
                    <span className="adm-plan-bar-count">{count}</span>
                  </div>
                </div>
                <span className="adm-plan-count">{count}</span>
              </div>
            ))}
            {planEntries.length === 0 && (
              <p className="adm-empty">{t('admin.metrics.noData', 'No data')}</p>
            )}
          </div>
        </div>

        <div className="adm-section">
          <h3 className="adm-section-title">
            <span className="adm-section-icon">🔄</span>
            {t('admin.dashboard.statusBreakdown', 'Status Breakdown')}
          </h3>
          <div className="adm-status-list">
            {statusEntries.map(([status, count]) => (
              <div className="adm-status-row" key={status}>
                <span className="adm-status-label">
                  <span className={`adm-status-dot ${status}`} />
                  {statusLabel(status)}
                </span>
                <span className="adm-status-count">{count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Conversion + Churn */}
      <div className="adm-grid-2">
        <div className="adm-section">
          <h3 className="adm-section-title">
            <span className="adm-section-icon">🎯</span>
            {t('admin.dashboard.conversion')}
          </h3>
          <div className="adm-metric-rows">
            <div className="adm-metric-row">
              <span className="adm-metric-label">{t('admin.metrics.trialUsers')}</span>
              <span className="adm-metric-value">{conversion?.trial_users ?? 0}</span>
            </div>
            <div className="adm-metric-row">
              <span className="adm-metric-label">{t('admin.metrics.convertedUsers')}</span>
              <span className="adm-metric-value">{conversion?.converted_users ?? 0}</span>
            </div>
            <div className="adm-metric-row">
              <span className="adm-metric-label">{t('admin.metrics.conversionRate')}</span>
              <span className="adm-metric-value highlight">
                {(conversion?.conversion_rate ?? 0).toFixed(1)}%
              </span>
            </div>
          </div>
        </div>

        <div className="adm-section">
          <h3 className="adm-section-title">
            <span className="adm-section-icon">📉</span>
            {t('admin.dashboard.churnPeriod', { days: churn?.period_days ?? 30 })}
          </h3>
          <div className="adm-metric-rows">
            {Object.entries(churn?.churn_by_plan ?? {}).map(([plan, data]) => (
              <div className="adm-metric-row" key={plan}>
                <span className="adm-metric-label">{planLabel(plan)}</span>
                <span className={`adm-metric-value ${data.churn_rate > 5 ? 'danger' : 'success'}`}>
                  {data.churn_rate.toFixed(1)}%
                  <span style={{ fontSize: '0.75rem', fontWeight: 400, marginLeft: 6, color: 'var(--color-text-muted)' }}>
                    ({data.canceled}/{data.active})
                  </span>
                </span>
              </div>
            ))}
            {Object.keys(churn?.churn_by_plan ?? {}).length === 0 && (
              <p className="adm-empty">{t('admin.metrics.noChurnData')}</p>
            )}
          </div>
        </div>
      </div>
      </>
      )}
    </div>
  );
};

export default AdminDashboard;
