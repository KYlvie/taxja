import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { ArrowDownLeft, ArrowUpRight, CircleAlert, Landmark, Wallet, Waves } from 'lucide-react';
import FuturisticIcon from '../common/FuturisticIcon';
import { formatCurrency } from '../../utils/locale';
import './DashboardOverview.css';

interface DashboardOverviewProps {
  yearToDateIncome: number;
  yearToDateExpenses: number;
  estimatedTax: number;
  paidTax: number;
  remainingTax: number;
  netIncome: number;
  vatThresholdDistance?: number;
  pendingReviewCount?: number;
}

const DashboardOverview = ({
  yearToDateIncome,
  yearToDateExpenses,
  estimatedTax,
  paidTax,
  remainingTax,
  netIncome,
  vatThresholdDistance,
  pendingReviewCount,
}: DashboardOverviewProps) => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const currentLanguage = i18n.resolvedLanguage || i18n.language;

  return (
    <div className="dashboard-overview">
      <div className="overview-grid">
        <div className="overview-card income">
          <div className="card-icon">
            <FuturisticIcon icon={ArrowUpRight} tone="emerald" size="md" />
          </div>
          <div className="card-content">
            <h3>{t('dashboard.yearToDateIncome')}</h3>
            <p className="amount">{formatCurrency(yearToDateIncome, currentLanguage)}</p>
          </div>
        </div>

        <div className="overview-card expenses">
          <div className="card-icon">
            <FuturisticIcon icon={ArrowDownLeft} tone="rose" size="md" />
          </div>
          <div className="card-content">
            <h3>{t('dashboard.yearToDateExpenses')}</h3>
            <p className="amount">{formatCurrency(yearToDateExpenses, currentLanguage)}</p>
          </div>
        </div>

        <div className="overview-card tax">
          <div className="card-icon">
            <FuturisticIcon icon={Landmark} tone="amber" size="md" />
          </div>
          <div className="card-content">
            <h3>{t('dashboard.estimatedTax')}</h3>
            <p className="amount">{formatCurrency(estimatedTax, currentLanguage)}</p>
            <div className="tax-breakdown">
              <span className="paid">
                {t('dashboard.paid')}: {formatCurrency(paidTax, currentLanguage)}
              </span>
              <span className="remaining">
                {t('dashboard.remaining')}: {formatCurrency(remainingTax, currentLanguage)}
              </span>
            </div>
          </div>
        </div>

        <div className="overview-card net-income">
          <div className="card-icon">
            <FuturisticIcon icon={Wallet} tone="violet" size="md" />
          </div>
          <div className="card-content">
            <h3>{t('dashboard.netIncome')}</h3>
            <p className="amount highlight">{formatCurrency(netIncome, currentLanguage)}</p>
            <p className="subtitle">{t('dashboard.afterTaxAndSVS')}</p>
          </div>
        </div>

        {vatThresholdDistance !== undefined && vatThresholdDistance !== null && (
          <div className="overview-card vat-threshold">
            <div className="card-icon">
              <FuturisticIcon icon={Waves} tone="cyan" size="md" />
            </div>
            <div className="card-content">
              <h3>{t('dashboard.vatThresholdDistance')}</h3>
              <p className="amount">
                {formatCurrency(Math.abs(vatThresholdDistance), currentLanguage)}
              </p>
              <p className="subtitle">
                {vatThresholdDistance > 0
                  ? t('dashboard.belowThreshold')
                  : t('dashboard.aboveThreshold')}
              </p>
            </div>
          </div>
        )}

        {pendingReviewCount != null && pendingReviewCount > 0 && (
          <div
            className="overview-card pending-review"
            onClick={() => navigate('/transactions?needs_review=true')}
            style={{ cursor: 'pointer' }}
          >
            <div className="card-icon">
              <FuturisticIcon icon={CircleAlert} tone="amber" size="md" />
            </div>
            <div className="card-content">
              <h3>{t('transactions.needsReview')}</h3>
              <p className="amount">{pendingReviewCount}</p>
              <p className="subtitle">
                {t('transactions.pendingReviewCount', { count: pendingReviewCount })}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default DashboardOverview;
