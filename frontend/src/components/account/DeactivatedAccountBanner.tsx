import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import './AccountManagement.css';

interface DeactivatedAccountBannerProps {
  coolingOffDaysRemaining: number;
  onReactivate: () => Promise<void> | void;
}

const DeactivatedAccountBanner: React.FC<DeactivatedAccountBannerProps> = ({
  coolingOffDaysRemaining,
  onReactivate,
}) => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleReactivate = async () => {
    setLoading(true);
    setError('');
    try {
      await onReactivate();
      setSuccess(true);
    } catch (err: any) {
      setError(
        err.response?.data?.detail || err.message || t('common.error', 'An error occurred')
      );
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="deactivated-banner deactivated-banner--success" role="alert">
        <p>{t('account.deactivated.reactivated', 'Your account has been reactivated. Please log in again.')}</p>
      </div>
    );
  }

  return (
    <div className="deactivated-banner" role="alert">
      <div className="deactivated-banner-content">
        <h3>{t('account.deactivated.title', 'Your account has been deactivated')}</h3>
        <p>
          {t('account.deactivated.daysRemaining', 'Your data will be permanently deleted in {{days}} days.', {
            days: coolingOffDaysRemaining,
          })}
        </p>
        {error && <p className="error-message">{error}</p>}
      </div>
      <button
        className="btn-primary"
        onClick={handleReactivate}
        disabled={loading}
      >
        {loading
          ? t('common.loading', 'Loading...')
          : t('account.deactivated.reactivate', 'Reactivate Account')}
      </button>
    </div>
  );
};

export default DeactivatedAccountBanner;
