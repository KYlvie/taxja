import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { formatCurrency as formatLocalizedCurrency } from '../../utils/locale';
import './RefundEstimate.css';

interface RefundEstimateProps {
  estimatedRefund?: number;
  withheldTax?: number;
  calculatedTax?: number;
  hasLohnzettel?: boolean;
}

const icons = {
  noData: '\u{1F4B0}',
  positive: '\u{1F389}',
  hint: '\u{1F4A1}',
  warning: '\u26A0\uFE0F',
  balanced: '\u2705',
} as const;

const RefundEstimate = ({
  estimatedRefund,
  withheldTax,
  calculatedTax,
  hasLohnzettel = false,
}: RefundEstimateProps) => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();

  const formatCurrency = (amount: number) =>
    formatLocalizedCurrency(amount, i18n.resolvedLanguage || i18n.language);

  const handleCalculateRefund = () => {
    navigate('/reports');
  };

  if (estimatedRefund === undefined) {
    return (
      <div className="refund-estimate no-data">
        <div className="refund-icon" aria-hidden="true">
          {icons.noData}
        </div>
        <div className="refund-content">
          <h3>{t('dashboard.employeeRefund')}</h3>
          <p className="refund-description">{t('dashboard.refundDescription')}</p>
          <button className="calculate-button" onClick={handleCalculateRefund}>
            {t('dashboard.calculateRefund')}
          </button>
        </div>
      </div>
    );
  }

  if (estimatedRefund > 0) {
    return (
      <div className="refund-estimate positive">
        <div className="refund-header">
          <div className="refund-icon" aria-hidden="true">
            {icons.positive}
          </div>
          <h3>{t('dashboard.estimatedRefund')}</h3>
        </div>

        <div className="refund-amount-box">
          <p className="refund-label">{t('dashboard.youMayReceive')}</p>
          <p className="refund-amount positive">{formatCurrency(estimatedRefund)}</p>
        </div>

        <div className="refund-breakdown">
          <div className="breakdown-row">
            <span>{t('dashboard.withheldTax')}:</span>
            <span className="amount">
              {withheldTax !== undefined ? formatCurrency(withheldTax) : '-'}
            </span>
          </div>
          <div className="breakdown-row">
            <span>{t('dashboard.calculatedTax')}:</span>
            <span className="amount">
              {calculatedTax !== undefined ? formatCurrency(calculatedTax) : '-'}
            </span>
          </div>
          <div className="breakdown-row total">
            <span>{t('dashboard.refund')}:</span>
            <span className="amount highlight">{formatCurrency(estimatedRefund)}</span>
          </div>
        </div>

        <div className="refund-actions">
          <button className="primary-button" onClick={handleCalculateRefund}>
            {t('dashboard.viewDetails')}
          </button>
          {!hasLohnzettel && (
            <p className="upload-reminder">
              <span aria-hidden="true">{icons.hint}</span> {t('dashboard.uploadLohnzettelReminder')}
            </p>
          )}
        </div>
      </div>
    );
  }

  if (estimatedRefund < 0) {
    return (
      <div className="refund-estimate negative">
        <div className="refund-header">
          <div className="refund-icon" aria-hidden="true">
            {icons.warning}
          </div>
          <h3>{t('dashboard.additionalPayment')}</h3>
        </div>

        <div className="refund-amount-box">
          <p className="refund-label">{t('dashboard.youMayOwe')}</p>
          <p className="refund-amount negative">{formatCurrency(Math.abs(estimatedRefund))}</p>
        </div>

        <div className="refund-breakdown">
          <div className="breakdown-row">
            <span>{t('dashboard.withheldTax')}:</span>
            <span className="amount">
              {withheldTax !== undefined ? formatCurrency(withheldTax) : '-'}
            </span>
          </div>
          <div className="breakdown-row">
            <span>{t('dashboard.calculatedTax')}:</span>
            <span className="amount">
              {calculatedTax !== undefined ? formatCurrency(calculatedTax) : '-'}
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
          <button className="primary-button" onClick={handleCalculateRefund}>
            {t('dashboard.viewDetails')}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="refund-estimate neutral">
      <div className="refund-header">
        <div className="refund-icon" aria-hidden="true">
          {icons.balanced}
        </div>
        <h3>{t('dashboard.taxesBalanced')}</h3>
      </div>

      <div className="refund-amount-box">
        <p className="refund-description">{t('dashboard.noRefundOrPayment')}</p>
      </div>

      <div className="refund-actions">
        <button className="secondary-button" onClick={handleCalculateRefund}>
          {t('dashboard.viewDetails')}
        </button>
      </div>
    </div>
  );
};

export default RefundEstimate;
