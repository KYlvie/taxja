import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import './RefundEstimate.css';

interface RefundEstimateProps {
  estimatedRefund?: number;
  withheldTax?: number;
  calculatedTax?: number;
  hasLohnzettel?: boolean;
}

const RefundEstimate = ({
  estimatedRefund,
  withheldTax,
  calculatedTax,
  hasLohnzettel = false,
}: RefundEstimateProps) => {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('de-AT', {
      style: 'currency',
      currency: 'EUR',
    }).format(amount);
  };

  const handleCalculateRefund = () => {
    navigate('/reports');
  };

  // If no refund data available
  if (estimatedRefund === undefined) {
    return (
      <div className="refund-estimate no-data">
        <div className="refund-icon">💰</div>
        <div className="refund-content">
          <h3>{t('dashboard.employeeRefund')}</h3>
          <p className="refund-description">
            {t('dashboard.refundDescription')}
          </p>
          <button
            className="calculate-button"
            onClick={handleCalculateRefund}
          >
            {t('dashboard.calculateRefund')}
          </button>
        </div>
      </div>
    );
  }

  // If refund is positive (user gets money back)
  if (estimatedRefund > 0) {
    return (
      <div className="refund-estimate positive">
        <div className="refund-header">
          <div className="refund-icon">🎉</div>
          <h3>{t('dashboard.estimatedRefund')}</h3>
        </div>

        <div className="refund-amount-box">
          <p className="refund-label">{t('dashboard.youMayReceive')}</p>
          <p className="refund-amount positive">
            {formatCurrency(estimatedRefund)}
          </p>
        </div>

        <div className="refund-breakdown">
          <div className="breakdown-row">
            <span>{t('dashboard.withheldTax')}:</span>
            <span className="amount">
              {withheldTax !== undefined
                ? formatCurrency(withheldTax)
                : '-'}
            </span>
          </div>
          <div className="breakdown-row">
            <span>{t('dashboard.calculatedTax')}:</span>
            <span className="amount">
              {calculatedTax !== undefined
                ? formatCurrency(calculatedTax)
                : '-'}
            </span>
          </div>
          <div className="breakdown-row total">
            <span>{t('dashboard.refund')}:</span>
            <span className="amount highlight">
              {formatCurrency(estimatedRefund)}
            </span>
          </div>
        </div>

        <div className="refund-actions">
          <button
            className="primary-button"
            onClick={handleCalculateRefund}
          >
            {t('dashboard.viewDetails')}
          </button>
          {!hasLohnzettel && (
            <p className="upload-reminder">
              💡 {t('dashboard.uploadLohnzettelReminder')}
            </p>
          )}
        </div>
      </div>
    );
  }

  // If refund is negative (user owes money)
  if (estimatedRefund < 0) {
    return (
      <div className="refund-estimate negative">
        <div className="refund-header">
          <div className="refund-icon">⚠️</div>
          <h3>{t('dashboard.additionalPayment')}</h3>
        </div>

        <div className="refund-amount-box">
          <p className="refund-label">{t('dashboard.youMayOwe')}</p>
          <p className="refund-amount negative">
            {formatCurrency(Math.abs(estimatedRefund))}
          </p>
        </div>

        <div className="refund-breakdown">
          <div className="breakdown-row">
            <span>{t('dashboard.withheldTax')}:</span>
            <span className="amount">
              {withheldTax !== undefined
                ? formatCurrency(withheldTax)
                : '-'}
            </span>
          </div>
          <div className="breakdown-row">
            <span>{t('dashboard.calculatedTax')}:</span>
            <span className="amount">
              {calculatedTax !== undefined
                ? formatCurrency(calculatedTax)
                : '-'}
            </span>
          </div>
          <div className="breakdown-row total">
            <span>{t('dashboard.additionalPayment')}:</span>
            <span className="amount highlight negative">
              {formatCurrency(Math.abs(estimatedRefund))}
            </span>
          </div>
        </div>

        <div className="refund-actions">
          <button
            className="primary-button"
            onClick={handleCalculateRefund}
          >
            {t('dashboard.viewDetails')}
          </button>
        </div>
      </div>
    );
  }

  // If refund is exactly zero
  return (
    <div className="refund-estimate neutral">
      <div className="refund-header">
        <div className="refund-icon">✅</div>
        <h3>{t('dashboard.taxesBalanced')}</h3>
      </div>

      <div className="refund-amount-box">
        <p className="refund-description">
          {t('dashboard.noRefundOrPayment')}
        </p>
      </div>

      <div className="refund-actions">
        <button
          className="secondary-button"
          onClick={handleCalculateRefund}
        >
          {t('dashboard.viewDetails')}
        </button>
      </div>
    </div>
  );
};

export default RefundEstimate;
