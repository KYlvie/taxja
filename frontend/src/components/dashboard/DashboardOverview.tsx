import { useTranslation } from 'react-i18next';
import './DashboardOverview.css';

interface DashboardOverviewProps {
  yearToDateIncome: number;
  yearToDateExpenses: number;
  estimatedTax: number;
  paidTax: number;
  remainingTax: number;
  netIncome: number;
  vatThresholdDistance?: number;
}

const DashboardOverview = ({
  yearToDateIncome,
  yearToDateExpenses,
  estimatedTax,
  paidTax,
  remainingTax,
  netIncome,
  vatThresholdDistance,
}: DashboardOverviewProps) => {
  const { t } = useTranslation();

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('de-AT', {
      style: 'currency',
      currency: 'EUR',
    }).format(amount);
  };

  return (
    <div className="dashboard-overview">
      <div className="overview-grid">
        <div className="overview-card income">
          <div className="card-icon">📈</div>
          <div className="card-content">
            <h3>{t('dashboard.yearToDateIncome')}</h3>
            <p className="amount">{formatCurrency(yearToDateIncome)}</p>
          </div>
        </div>

        <div className="overview-card expenses">
          <div className="card-icon">📉</div>
          <div className="card-content">
            <h3>{t('dashboard.yearToDateExpenses')}</h3>
            <p className="amount">{formatCurrency(yearToDateExpenses)}</p>
          </div>
        </div>

        <div className="overview-card tax">
          <div className="card-icon">💰</div>
          <div className="card-content">
            <h3>{t('dashboard.estimatedTax')}</h3>
            <p className="amount">{formatCurrency(estimatedTax)}</p>
            <div className="tax-breakdown">
              <span className="paid">
                {t('dashboard.paid')}: {formatCurrency(paidTax)}
              </span>
              <span className="remaining">
                {t('dashboard.remaining')}: {formatCurrency(remainingTax)}
              </span>
            </div>
          </div>
        </div>

        <div className="overview-card net-income">
          <div className="card-icon">💵</div>
          <div className="card-content">
            <h3>{t('dashboard.netIncome')}</h3>
            <p className="amount highlight">{formatCurrency(netIncome)}</p>
            <p className="subtitle">{t('dashboard.afterTaxAndSVS')}</p>
          </div>
        </div>

        {vatThresholdDistance !== undefined && (
          <div className="overview-card vat-threshold">
            <div className="card-icon">📊</div>
            <div className="card-content">
              <h3>{t('dashboard.vatThresholdDistance')}</h3>
              <p className="amount">{formatCurrency(vatThresholdDistance)}</p>
              <p className="subtitle">
                {vatThresholdDistance > 0
                  ? t('dashboard.belowThreshold')
                  : t('dashboard.aboveThreshold')}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default DashboardOverview;
