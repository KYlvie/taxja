import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useSubscriptionStore } from '../../stores/subscriptionStore';
import { getLocaleForLanguage } from '../../utils/locale';
import CancelSubscriptionModal from './CancelSubscriptionModal';

const AccountManagementSection: React.FC = () => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { subscription, fetchSubscription } = useSubscriptionStore();
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [cancelSuccess, setCancelSuccess] = useState(false);

  useEffect(() => {
    fetchSubscription();
  }, [fetchSubscription]);

  const handleCancelSuccess = async () => {
    setShowCancelModal(false);
    setCancelSuccess(true);
    await fetchSubscription();
  };

  const hasActiveSubscription =
    subscription &&
    subscription.status !== 'canceled' &&
    !subscription.cancel_at_period_end;

  // Only show cancel option for paid plans (not free tier or trial)
  const hasPaidSubscription =
    hasActiveSubscription &&
    subscription.status === 'active' &&
    subscription.stripe_subscription_id;

  const formatDate = (dateString: string | null) => {
    if (!dateString) return '';
    return new Intl.DateTimeFormat(getLocaleForLanguage(i18n.resolvedLanguage || i18n.language)).format(
      new Date(dateString)
    );
  };

  return (
    <section className="profile-section danger-zone">
      <h2>{t('account.management.title', 'Account Management')}</h2>

      {/* Cancel Subscription — only visible for paid subscribers */}
      {(hasPaidSubscription || subscription?.cancel_at_period_end || cancelSuccess) && (
        <div className="account-action-block">
          <div className="account-action-info">
            <h3>{t('account.management.cancelSubscription', 'Cancel Subscription')}</h3>
            <p className="text-muted">
              {hasActiveSubscription
                ? t(
                    'account.management.cancelSubscriptionDesc',
                    'Cancel your paid subscription. You will retain access until the end of the current billing period.'
                  )
                : subscription?.cancel_at_period_end
                  ? t('account.management.subscriptionCancelPending', 'Your subscription is set to cancel on {{date}}.', {
                      date: formatDate(subscription.current_period_end),
                    })
                  : t('account.management.noActiveSubscription', 'You do not have an active paid subscription.')}
            </p>
            {cancelSuccess && (
              <p className="success-message">
                {t('account.management.cancelSuccess', 'Subscription cancelled successfully. Access continues until {{date}}.', {
                  date: formatDate(subscription?.current_period_end ?? null),
                })}
              </p>
            )}
          </div>
          <button
            className="btn-warning"
            onClick={() => setShowCancelModal(true)}
            disabled={!hasActiveSubscription}
          >
            {t('account.management.cancelSubscriptionBtn', 'Cancel Subscription')}
          </button>
        </div>
      )}

      {/* Delete Account */}
      <div className="account-action-block">
        <div className="account-action-info">
          <h3>{t('account.management.deleteAccount', 'Delete Account')}</h3>
          <p className="danger-text">
            {t(
              'account.management.deleteAccountDesc',
              'Permanently delete your account and all associated data. This action includes a 30-day cooling-off period.'
            )}
          </p>
        </div>
        <button className="btn-danger" onClick={() => navigate('/account/delete')}>
          {t('account.management.deleteAccountBtn', 'Delete Account')}
        </button>
      </div>

      {showCancelModal && (
        <CancelSubscriptionModal
          onClose={() => setShowCancelModal(false)}
          onSuccess={handleCancelSuccess}
        />
      )}
    </section>
  );
};

export default AccountManagementSection;
