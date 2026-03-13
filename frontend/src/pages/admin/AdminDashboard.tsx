import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import './AdminDashboard.css';

interface RevenueMetrics {
  mrr: number;
  arr: number;
  growth_rate: number;
}

interface SubscriptionStats {
  free: number;
  plus: number;
  pro: number;
  total: number;
}

interface ConversionMetrics {
  trial_to_paid: number;
  free_to_paid: number;
}

interface ChurnMetrics {
  overall_rate: number;
  by_plan: {
    plus: number;
    pro: number;
  };
}

const AdminDashboard: React.FC = () => {
  const { t } = useTranslation();
  const [revenue, setRevenue] = useState<RevenueMetrics | null>(null);
  const [subscriptions, setSubscriptions] = useState<SubscriptionStats | null>(null);
  const [conversion, setConversion] = useState<ConversionMetrics | null>(null);
  const [churn, setChurn] = useState<ChurnMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      
      // Fetch revenue metrics
      const revenueRes = await fetch('/api/v1/admin/analytics/revenue');
      const revenueData = await revenueRes.json();
      setRevenue(revenueData);

      // Fetch subscription stats
      const subsRes = await fetch('/api/v1/admin/analytics/subscriptions');
      const subsData = await subsRes.json();
      setSubscriptions(subsData);

      // Fetch conversion metrics
      const convRes = await fetch('/api/v1/admin/analytics/conversion');
      const convData = await convRes.json();
      setConversion(convData);

      // Fetch churn metrics
      const churnRes = await fetch('/api/v1/admin/analytics/churn');
      const churnData = await churnRes.json();
      setChurn(churnData);
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="admin-dashboard loading">{t('common.loading')}</div>;
  }

  return (
    <div className="admin-dashboard">
      <h1>{t('admin.dashboard.title')}</h1>

      {/* Revenue Metrics */}
      <section className="metrics-section">
        <h2>{t('admin.dashboard.revenue')}</h2>
        <div className="metrics-cards">
          <div className="metric-card">
            <div className="metric-label">{t('admin.metrics.mrr')}</div>
            <div className="metric-value">€{revenue?.mrr.toFixed(2)}</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">{t('admin.metrics.arr')}</div>
            <div className="metric-value">€{revenue?.arr.toFixed(2)}</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">{t('admin.metrics.growth')}</div>
            <div className="metric-value">{revenue?.growth_rate.toFixed(1)}%</div>
          </div>
        </div>
      </section>

      {/* Subscription Distribution */}
      <section className="metrics-section">
        <h2>{t('admin.dashboard.subscriptions')}</h2>
        <div className="subscription-chart">
          <div className="chart-bar">
            <div className="bar free" style={{ width: `${(subscriptions?.free || 0) / (subscriptions?.total || 1) * 100}%` }}>
              <span>Free: {subscriptions?.free}</span>
            </div>
          </div>
          <div className="chart-bar">
            <div className="bar plus" style={{ width: `${(subscriptions?.plus || 0) / (subscriptions?.total || 1) * 100}%` }}>
              <span>Plus: {subscriptions?.plus}</span>
            </div>
          </div>
          <div className="chart-bar">
            <div className="bar pro" style={{ width: `${(subscriptions?.pro || 0) / (subscriptions?.total || 1) * 100}%` }}>
              <span>Pro: {subscriptions?.pro}</span>
            </div>
          </div>
        </div>
      </section>

      {/* Conversion & Churn */}
      <section className="metrics-section">
        <div className="metrics-grid">
          <div className="metric-group">
            <h3>{t('admin.dashboard.conversion')}</h3>
            <div className="metric-item">
              <span>{t('admin.metrics.trial_to_paid')}</span>
              <strong>{conversion?.trial_to_paid.toFixed(1)}%</strong>
            </div>
            <div className="metric-item">
              <span>{t('admin.metrics.free_to_paid')}</span>
              <strong>{conversion?.free_to_paid.toFixed(1)}%</strong>
            </div>
          </div>
          <div className="metric-group">
            <h3>{t('admin.dashboard.churn')}</h3>
            <div className="metric-item">
              <span>{t('admin.metrics.overall_churn')}</span>
              <strong>{churn?.overall_rate.toFixed(1)}%</strong>
            </div>
            <div className="metric-item">
              <span>Plus {t('admin.metrics.churn')}</span>
              <strong>{churn?.by_plan.plus.toFixed(1)}%</strong>
            </div>
            <div className="metric-item">
              <span>Pro {t('admin.metrics.churn')}</span>
              <strong>{churn?.by_plan.pro.toFixed(1)}%</strong>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};

export default AdminDashboard;
