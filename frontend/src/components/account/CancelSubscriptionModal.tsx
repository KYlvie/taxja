import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSubscriptionStore } from '../../stores/subscriptionStore';
import { accountService } from '../../services/accountService';

interface CancelSubscriptionModalProps {
  onClose: () => void;
  onSuccess: () => void;
}

const CANCEL_REASONS = [
  'too_expensive',
  'not_using',
  'missing_features',
  'switching_service',
  'other',
] as const;

const CancelSubscriptionModal: React.FC<CancelSubscriptionModalProps> = ({ onClose, onSuccess }) => {
  const { t } = useTranslation();
  const { subscription, currentPlan } = useSubscriptionStore();
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const formatDate = (dateString: string | null) => {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleDateString();
  };

  const handleConfirm = async () => {
    setLoading(true);
    setError('');
    try {
      await accountService.cancelSubscription(reason || undefined);
      onSuccess();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || t('common.error'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="modal-header">
          <h2>{t('account.cancelSubscription.title', 'Cancel Subscription')}</h2>
          <button className="modal-close-btn" onClick={onClose} aria-label={t('common.close')}>
            ×
          </button>
        </div>

        <div className="modal-body">
          {subscription && currentPlan && (
            <div className="subscription-summary">
              <div className="summary-row">
                <span className="summary-label">
                  {t('account.cancelSubscription.currentPlan', 'Current Plan')}
                </span>
                <span className="summary-value plan-badge">{currentPlan.name}</span>
              </div>
              <div className="summary-row">
                <span className="summary-label">
                  {t('account.cancelSubscription.expiryDate', 'Access Until')}
                </span>
                <span className="summary-value">
                  {formatDate(subscription.current_period_end)}
                </span>
              </div>
            </div>
          )}

          <p className="cancel-info">
            {t(
              'account.cancelSubscription.info',
              'Your subscription will remain active until the end of the current billing period. After that, your account will be downgraded to the free plan.'
            )}
          </p>

          <div className="form-group">
            <label htmlFor="cancel-reason">
              {t('account.cancelSubscription.reasonLabel', 'Reason for cancellation (optional)')}
            </label>
            <select
              id="cancel-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              disabled={loading}
            >
              <option value="">{t('account.cancelSubscription.selectReason', '-- Select a reason --')}</option>
              {CANCEL_REASONS.map((r) => (
                <option key={r} value={r}>
                  {t(`account.cancelSubscription.reasons.${r}`, r)}
                </option>
              ))}
            </select>
          </div>

          {error && <div className="error-message">{error}</div>}
        </div>

        <div className="modal-footer">
          <button className="btn-secondary" onClick={onClose} disabled={loading}>
            {t('common.cancel')}
          </button>
          <button className="btn-danger" onClick={handleConfirm} disabled={loading}>
            {loading
              ? t('common.loading')
              : t('account.cancelSubscription.confirm', 'Confirm Cancellation')}
          </button>
        </div>
      </div>
    </div>
  );
};

export default CancelSubscriptionModal;
