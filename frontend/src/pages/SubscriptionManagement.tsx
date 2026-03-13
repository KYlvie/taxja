/**
 * Subscription Management Page
 * 
 * Full subscription management interface with plan changes and cancellation.
 * Per Requirements 6.1, 6.2, 6.3, 7.3: Manage subscription lifecycle.
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useSubscriptionStore } from '../stores/subscriptionStore';
import './SubscriptionManagement.css';

const SubscriptionManagement: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const {
    subscription,
    currentPlan,
    fetchSubscription,
    cancelSubscription,
    reactivateSubscription,
    loading,
    error,
  } = useSubscriptionStore();
  
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [showChangePlanModal, setShowChangePlanModal] = useState(false);
  
  useEffect(() => {
    fetchSubscription();
  }, [fetchSubscription]);
  
  if (!subscription || !currentPlan) {
    return (
      <div className="subscription-management">
        <div className="loading-state">
          {t('subscription.loading', 'Loading subscription details...')}
        </div>
      </div>
    );
  }
  
  const handleCancelSubscription = async () => {
    try {
      await cancelSubscription();
      setShowCancelModal(false);
      alert(t('subscription.cancel_success', 'Your subscription will be canceled at the end of the current period.'));
    } catch (err) {
      alert(t('subscription.cancel_error', 'Failed to cancel subscription. Please try again.'));
    }
  };
  
  const handleReactivateSubscription = async () => {
    try {
      await reactivateSubscription();
      alert(t('subscription.reactivate_success', 'Your subscription has been reactivated!'));
    } catch (err) {
      alert(t('subscription.reactivate_error', 'Failed to reactivate subscription. Please try again.'));
    }
  };
  
  const handleChangePlan = () => {
    setShowChangePlanModal(true);
  };
  
  const confirmChangePlan = () => {
    navigate('/pricing');
  };
  
  const formatDate = (dateString: string | null) => {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };
  
  const getPlanPrice = () => {
    if (currentPlan.plan_type === 'free') return t('subscription.free', 'Free');
    
    const price = subscription.billing_cycle === 'yearly'
      ? currentPlan.yearly_price
      : currentPlan.monthly_price;
    
    const period = subscription.billing_cycle === 'yearly'
      ? t('subscription.per_year', '/year')
      : t('subscription.per_month', '/month');
    
    return `€${price.toFixed(2)}${period}`;
  };
  
  const canCancel = subscription.status === 'active' && !subscription.cancel_at_period_end;
  const canReactivate = subscription.cancel_at_period_end;
  const isTrialing = subscription.status === 'trialing';
  
  return (
    <div className="subscription-management">
      <div className="page-header">
        <button className="back-button" onClick={() => navigate(-1)}>
          ← {t('common.back', 'Back')}
        </button>
        <h1>{t('subscription.manage_title', 'Manage Subscription')}</h1>
      </div>
      
      {error && (
        <div className="error-banner">
          {error}
        </div>
      )}
      
      {/* Current Plan Section */}
      <div className="management-section">
        <h2>{t('subscription.current_plan', 'Current Plan')}</h2>
        <div className="plan-card">
          <div className="plan-card-header">
            <div>
              <h3>{currentPlan.name}</h3>
              <p className="plan-price">{getPlanPrice()}</p>
            </div>
            <span className={`status-badge status-${subscription.status}`}>
              {t(`subscription.status.${subscription.status}`, subscription.status)}
            </span>
          </div>
          
          {isTrialing && (
            <div className="trial-banner">
              🎉 {t('subscription.trial_active', 'You\'re on a free trial until {{date}}', {
                date: formatDate(subscription.current_period_end)
              })}
            </div>
          )}
          
          <div className="plan-details">
            <div className="detail-row">
              <span>{t('subscription.billing_cycle', 'Billing Cycle')}</span>
              <strong>
                {subscription.billing_cycle
                  ? t(`subscription.billing.${subscription.billing_cycle}`, subscription.billing_cycle)
                  : t('subscription.not_applicable', 'N/A')
                }
              </strong>
            </div>
            <div className="detail-row">
              <span>{t('subscription.next_billing', 'Next Billing Date')}</span>
              <strong>{formatDate(subscription.current_period_end)}</strong>
            </div>
            {subscription.cancel_at_period_end && (
              <div className="detail-row warning">
                <span>⚠️ {t('subscription.canceling', 'Canceling')}</span>
                <strong>{t('subscription.ends_on', 'Ends {{date}}', {
                  date: formatDate(subscription.current_period_end)
                })}</strong>
              </div>
            )}
          </div>
          
          <div className="plan-actions">
            <button
              className="btn-secondary"
              onClick={handleChangePlan}
              disabled={loading}
            >
              {t('subscription.change_plan', 'Change Plan')}
            </button>
            
            {canReactivate ? (
              <button
                className="btn-primary"
                onClick={handleReactivateSubscription}
                disabled={loading}
              >
                {t('subscription.reactivate', 'Reactivate Subscription')}
              </button>
            ) : canCancel && (
              <button
                className="btn-danger"
                onClick={() => setShowCancelModal(true)}
                disabled={loading}
              >
                {t('subscription.cancel', 'Cancel Subscription')}
              </button>
            )}
          </div>
        </div>
      </div>
      
      {/* Payment Method Section */}
      {subscription.stripe_customer_id && (
        <div className="management-section">
          <h2>{t('subscription.payment_method', 'Payment Method')}</h2>
          <div className="payment-card">
            <p className="payment-info">
              {t('subscription.payment_managed', 'Payment method is managed through Stripe.')}
            </p>
            <button
              className="btn-secondary"
              onClick={() => window.open('https://billing.stripe.com/p/login/test_xxx', '_blank')}
            >
              {t('subscription.manage_payment', 'Manage Payment Method')}
            </button>
          </div>
        </div>
      )}
      
      {/* Billing History Section */}
      <div className="management-section">
        <h2>{t('subscription.billing_history', 'Billing History')}</h2>
        <div className="billing-history">
          <p className="empty-state">
            {t('subscription.no_history', 'No billing history available yet.')}
          </p>
        </div>
      </div>
      
      {/* Cancel Confirmation Modal */}
      {showCancelModal && (
        <>
          <div className="modal-overlay" onClick={() => setShowCancelModal(false)} />
          <div className="confirmation-modal">
            <h3>{t('subscription.cancel_confirm_title', 'Cancel Subscription?')}</h3>
            <p>
              {t('subscription.cancel_confirm_message',
                'Your subscription will remain active until {{date}}. After that, you\'ll be downgraded to the Free plan.',
                { date: formatDate(subscription.current_period_end) }
              )}
            </p>
            <div className="modal-actions">
              <button
                className="btn-danger"
                onClick={handleCancelSubscription}
                disabled={loading}
              >
                {t('subscription.confirm_cancel', 'Yes, Cancel')}
              </button>
              <button
                className="btn-secondary"
                onClick={() => setShowCancelModal(false)}
              >
                {t('common.nevermind', 'Nevermind')}
              </button>
            </div>
          </div>
        </>
      )}
      
      {/* Change Plan Modal */}
      {showChangePlanModal && (
        <>
          <div className="modal-overlay" onClick={() => setShowChangePlanModal(false)} />
          <div className="confirmation-modal">
            <h3>{t('subscription.change_plan_title', 'Change Plan')}</h3>
            <p>
              {t('subscription.change_plan_message',
                'You\'ll be redirected to the pricing page to select a new plan.'
              )}
            </p>
            <div className="modal-actions">
              <button
                className="btn-primary"
                onClick={confirmChangePlan}
              >
                {t('subscription.continue', 'Continue')}
              </button>
              <button
                className="btn-secondary"
                onClick={() => setShowChangePlanModal(false)}
              >
                {t('common.cancel', 'Cancel')}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default SubscriptionManagement;
