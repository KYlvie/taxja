import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { dashboardService } from '../../services/dashboardService';
import './FlatRateComparison.css';

interface ComparisonData {
  actualAccounting: {
    grossIncome: number;
    deductibleExpenses: number;
    taxableIncome: number;
    incomeTax: number;
    netIncome: number;
  };
  flatRate: {
    grossIncome: number;
    flatRateDeduction: number;
    flatRatePercentage: number;
    taxableIncome: number;
    incomeTax: number;
    netIncome: number;
  };
  savings: number;
  recommendation: 'actual' | 'flat_rate';
  eligibility: {
    isEligible: boolean;
    reason: string;
    maxProfit: number;
  };
}

const reasonKeys: Record<string, string> = {
  not_available_employee: 'dashboard.flatRateReasonEmployee',
  not_available_gmbh: 'dashboard.flatRateReasonGmbh',
  not_available_landlord: 'dashboard.flatRateReasonLandlord',
  no_business_income: 'dashboard.flatRateReasonNoBusinessIncome',
  turnover_exceeds_limit: 'dashboard.flatRateReasonTurnover',
  eligible: 'dashboard.flatRateReasonEligible',
};

const FlatRateComparison = ({ year }: { year?: number }) => {
  const { t } = useTranslation();
  const [data, setData] = useState<ComparisonData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchComparison = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const result = await dashboardService.compareFlatRate(year);
        setData(result);
      } catch (err: any) {
        setError(err.response?.data?.detail || t('dashboard.comparisonError'));
      } finally {
        setIsLoading(false);
      }
    };

    fetchComparison();
  }, [year, t]);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('de-AT', {
      style: 'currency',
      currency: 'EUR',
    }).format(amount);
  };

  if (isLoading) {
    return (
      <div className="flat-rate-comparison">
        <h3>{t('dashboard.flatRateComparison')}</h3>
        <div className="loading">{t('common.loading')}</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flat-rate-comparison">
        <h3>{t('dashboard.flatRateComparison')}</h3>
        <p className="comparison-description">
          {t('dashboard.comparisonDescription')}
        </p>
        <div className="flat-rate-empty-state">
          <p>📊 {t('dashboard.flatRateNeedsData', 'Fügen Sie Einnahmen und Ausgaben hinzu, um den Vergleich zu berechnen.')}</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  return (
    <div className="flat-rate-comparison">
      <h3>{t('dashboard.flatRateComparison')}</h3>
      <p className="comparison-description">
        {t('dashboard.comparisonDescription')}
      </p>

      {/* Eligibility Status */}
      <div className={`eligibility-banner ${data.eligibility.isEligible ? 'eligible' : 'not-eligible'}`}>
        <div className="eligibility-icon">
          {data.eligibility.isEligible ? '✅' : '❌'}
        </div>
        <div className="eligibility-content">
          <h4>
            {data.eligibility.isEligible
              ? t('dashboard.eligibleForFlatRate')
              : t('dashboard.notEligibleForFlatRate')}
          </h4>
          <p>{t(reasonKeys[data.eligibility.reason] || data.eligibility.reason)}</p>
          {data.eligibility.isEligible && (
            <p className="max-profit">
              {t('dashboard.maxProfit')}: {formatCurrency(data.eligibility.maxProfit)}
            </p>
          )}
        </div>
      </div>

      {/* Side-by-Side Comparison */}
      <div className="comparison-grid">
        {/* Actual Accounting */}
        <div className={`comparison-card ${data.recommendation === 'actual' ? 'recommended' : ''}`}>
          {data.recommendation === 'actual' && (
            <div className="recommended-badge">
              ⭐ {t('dashboard.recommended')}
            </div>
          )}
          <h4>{t('dashboard.actualAccounting')}</h4>
          <p className="card-subtitle">
            {t('dashboard.actualAccountingSubtitle')}
          </p>

          <div className="calculation-breakdown">
            <div className="calc-row">
              <span>{t('dashboard.grossIncome')}:</span>
              <span className="amount">
                {formatCurrency(data.actualAccounting.grossIncome)}
              </span>
            </div>
            <div className="calc-row deduction">
              <span>{t('dashboard.deductibleExpenses')}:</span>
              <span className="amount">
                -{formatCurrency(data.actualAccounting.deductibleExpenses)}
              </span>
            </div>
            <div className="calc-row total">
              <span>{t('dashboard.taxableIncome')}:</span>
              <span className="amount">
                {formatCurrency(data.actualAccounting.taxableIncome)}
              </span>
            </div>
            <div className="calc-row">
              <span>{t('dashboard.incomeTax')}:</span>
              <span className="amount">
                {formatCurrency(data.actualAccounting.incomeTax)}
              </span>
            </div>
            <div className="calc-row net-income">
              <span>{t('dashboard.netIncome')}:</span>
              <span className="amount highlight">
                {formatCurrency(data.actualAccounting.netIncome)}
              </span>
            </div>
          </div>
        </div>

        {/* Flat Rate */}
        <div className={`comparison-card ${data.recommendation === 'flat_rate' ? 'recommended' : ''}`}>
          {data.recommendation === 'flat_rate' && (
            <div className="recommended-badge">
              ⭐ {t('dashboard.recommended')}
            </div>
          )}
          <h4>{t('dashboard.flatRateTax')}</h4>
          <p className="card-subtitle">
            {t('dashboard.flatRateTaxSubtitle')}
          </p>

          <div className="calculation-breakdown">
            <div className="calc-row">
              <span>{t('dashboard.grossIncome')}:</span>
              <span className="amount">
                {formatCurrency(data.flatRate.grossIncome)}
              </span>
            </div>
            <div className="calc-row deduction">
              <span>
                {t('dashboard.flatRateDeduction')} (
                {data.flatRate.flatRatePercentage}%):
              </span>
              <span className="amount">
                -{formatCurrency(data.flatRate.flatRateDeduction)}
              </span>
            </div>
            <div className="calc-row total">
              <span>{t('dashboard.taxableIncome')}:</span>
              <span className="amount">
                {formatCurrency(data.flatRate.taxableIncome)}
              </span>
            </div>
            <div className="calc-row">
              <span>{t('dashboard.incomeTax')}:</span>
              <span className="amount">
                {formatCurrency(data.flatRate.incomeTax)}
              </span>
            </div>
            <div className="calc-row net-income">
              <span>{t('dashboard.netIncome')}:</span>
              <span className="amount highlight">
                {formatCurrency(data.flatRate.netIncome)}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Savings Summary */}
      <div className={`savings-summary ${data.savings > 0 ? 'positive' : 'neutral'}`}>
        <div className="savings-content">
          <h4>{t('dashboard.potentialSavings')}</h4>
          <p className="savings-amount">
            {data.savings > 0
              ? formatCurrency(Math.abs(data.savings))
              : t('dashboard.noSavings')}
          </p>
          {data.savings > 0 && (
            <p className="savings-note">
              {data.recommendation === 'flat_rate'
                ? t('dashboard.flatRateSavesMore')
                : t('dashboard.actualAccountingSavesMore')}
            </p>
          )}
        </div>
      </div>

      {/* Disclaimer */}
      <div className="disclaimer-box">
        <p>
          ⚠️ {t('dashboard.flatRateDisclaimer')}
        </p>
      </div>
    </div>
  );
};

export default FlatRateComparison;
