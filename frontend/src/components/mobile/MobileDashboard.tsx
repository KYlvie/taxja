import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Bot, Camera, FileText, Plus, ReceiptText, Sparkles, TrendingDown, TrendingUp, Wallet } from 'lucide-react';
import FuturisticIcon from '../common/FuturisticIcon';
import { getLocaleForLanguage } from '../../utils/locale';
import './MobileDashboard.css';

interface MobileDashboardProps {
  summary: {
    yearToDateIncome: number;
    yearToDateExpenses: number;
    estimatedTax: number;
    netIncome: number;
    refundEstimate?: number;
  };
  upcomingDeadlines: Array<{
    title: string;
    date: string;
    daysUntil: number;
  }>;
}

export const MobileDashboard = ({ summary, upcomingDeadlines }: MobileDashboardProps) => {
  const { t, i18n } = useTranslation();

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat(getLocaleForLanguage(i18n.language), {
      style: 'currency',
      currency: 'EUR'
    }).format(amount);
  };

  return (
    <div className="mobile-dashboard">
      {/* Quick Stats Cards */}
      <div className="mobile-stats-grid">
        <div className="mobile-stat-card primary">
          <div className="mobile-stat-icon">
            <FuturisticIcon icon={Wallet} tone="slate" size="md" />
          </div>
          <div className="mobile-stat-content">
            <div className="mobile-stat-label">{t('dashboard.netIncome')}</div>
            <div className="mobile-stat-value">{formatCurrency(summary.netIncome)}</div>
          </div>
        </div>

        {summary.refundEstimate && summary.refundEstimate > 0 && (
          <div className="mobile-stat-card success">
            <div className="mobile-stat-icon">
              <FuturisticIcon icon={Sparkles} tone="slate" size="md" />
            </div>
            <div className="mobile-stat-content">
              <div className="mobile-stat-label">{t('dashboard.refundEstimate')}</div>
              <div className="mobile-stat-value">{formatCurrency(summary.refundEstimate)}</div>
            </div>
          </div>
        )}

        <div className="mobile-stat-card">
          <div className="mobile-stat-icon">
            <FuturisticIcon icon={TrendingUp} tone="emerald" size="md" />
          </div>
          <div className="mobile-stat-content">
            <div className="mobile-stat-label">{t('dashboard.income')}</div>
            <div className="mobile-stat-value">{formatCurrency(summary.yearToDateIncome)}</div>
          </div>
        </div>

        <div className="mobile-stat-card">
          <div className="mobile-stat-icon">
            <FuturisticIcon icon={TrendingDown} tone="rose" size="md" />
          </div>
          <div className="mobile-stat-content">
            <div className="mobile-stat-label">{t('dashboard.expenses')}</div>
            <div className="mobile-stat-value">{formatCurrency(summary.yearToDateExpenses)}</div>
          </div>
        </div>

        <div className="mobile-stat-card warning">
          <div className="mobile-stat-icon">
            <FuturisticIcon icon={ReceiptText} tone="slate" size="md" />
          </div>
          <div className="mobile-stat-content">
            <div className="mobile-stat-label">{t('dashboard.estimatedTax')}</div>
            <div className="mobile-stat-value">{formatCurrency(summary.estimatedTax)}</div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="mobile-quick-actions">
        <h3>{t('dashboard.quickActions')}</h3>
        <div className="mobile-action-grid">
          <Link to="/documents" className="mobile-action-button">
            <div className="mobile-action-icon">
              <FuturisticIcon icon={Camera} tone="cyan" size="lg" />
            </div>
            <div className="mobile-action-label">{t('actions.scanReceipt')}</div>
          </Link>

          <Link to="/transactions" className="mobile-action-button">
            <div className="mobile-action-icon">
              <FuturisticIcon icon={Plus} tone="violet" size="lg" />
            </div>
            <div className="mobile-action-label">{t('actions.addTransaction')}</div>
          </Link>

          <Link to="/reports" className="mobile-action-button">
            <div className="mobile-action-icon">
              <FuturisticIcon icon={FileText} tone="amber" size="lg" />
            </div>
            <div className="mobile-action-label">{t('actions.generateReport')}</div>
          </Link>

          <Link to="/ai-assistant" className="mobile-action-button">
            <div className="mobile-action-icon">
              <FuturisticIcon icon={Bot} tone="violet" size="lg" />
            </div>
            <div className="mobile-action-label">{t('actions.askAI')}</div>
          </Link>
        </div>
      </div>

      {/* Upcoming Deadlines */}
      {upcomingDeadlines.length > 0 && (
        <div className="mobile-deadlines">
          <h3>{t('dashboard.upcomingDeadlines')}</h3>
          <div className="mobile-deadline-list">
            {upcomingDeadlines.slice(0, 3).map((deadline, index) => (
              <div key={index} className="mobile-deadline-item">
                <div className="mobile-deadline-date">
                  <div className="mobile-deadline-day">
                    {new Date(deadline.date).getDate()}
                  </div>
                  <div className="mobile-deadline-month">
                    {new Date(deadline.date).toLocaleDateString(getLocaleForLanguage(i18n.language), { month: 'short' })}
                  </div>
                </div>
                <div className="mobile-deadline-content">
                  <div className="mobile-deadline-title">{deadline.title}</div>
                  <div className="mobile-deadline-countdown">
                    {deadline.daysUntil === 0
                      ? t('deadline.today')
                      : deadline.daysUntil === 1
                      ? t('deadline.tomorrow')
                      : t('deadline.inDays', { days: deadline.daysUntil })}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
