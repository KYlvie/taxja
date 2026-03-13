/**
 * Subscription Status Component
 * 
 * Displays current plan, subscription period, trial countdown, and usage stats.
 * Per Requirement 7.3: Show subscription details and usage.
 */

import React, { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useSubscriptionStore } from '../../stores/subscriptionStore';
import './SubscriptionStatus.css';

const SubscriptionStatus: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { subscription, currentPlan, usage, fetchSubscription, fetchUsage } = useSubscriptionStore();
  
  useEffect(() => {
    fetchSubscription();
    fetchUsage();
  }, [fetchSubscription, fetchUsage]);
  
  if (!subscription || !currentPlan) {
    return null;
  }
  
  const getPlanBadgeClass = () => {
    switch (currentPlan.plan_type) {
      case 'pro':
        return 'plan-badge-pro';
      case 'plus':
        return 'plan-badge-plus';
      default:
        return 'plan-badge-free';
    }
  };
  
  const getStatusBadgeClass = () => {
    switch (subscription.status) {
      case 'active':
        return 'status-badge-active';
      case 'trialing':
        return 'status-badge-trial';
      case 'past_due':
        return 'status-badge-warning';
      case 'canceled':
        return 'status-badge-canceled';
      default:
        return 'status-badge-default';
    }
  };
  
  const formatDate = (dateString: string | null) => {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleDateString();
  };
  
  const getDaysRemaining = () => {
    if (!subscription.current_period_end) return null;
    
    const endDate = new Date(subscription.current_period_end);
    const now = new Date();
    const diffTime = endDate.getTime() - now.getTime();
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    return diffDays > 0 ? diffDays : 0;
  };
  
  const daysRemaining = getDaysRemaining();
  const isTrialing = subscription.status === 'trialing';
  
  return (
    <div className="subscription-status">
      <div className="status-header">
        <div className="plan-info">
          <span className={`plan-badge ${getPlanBadgeClass()}`}>
            {currentPlan.name}
          </span>
          <span className={`status-badge ${getStatusBadgeClass()}`}>
            {t(`subscription.status.${subscription.status}`, subscription.status)}
          </span>
        </div>
        
        <button
          className="manage-button"
          onClick={() => navigate('/subscription/manage')}
        >
          {t('subscription.manage', 'Manage Subscription')}
        </button>
      </div>
      
      {isTrialing && daysRemaining !== null && (
        <div className="trial-countdown">
          <div className="trial-icon">🎉</div>
          <div className="trial-text">
            <strong>
              {t('subscription.trial_days_remaining', '{{days}} days remaining', {
                days: daysRemaining
              })}
            </strong>
            <span>
              {t('subscription.trial_message', 'in your Pro trial. Upgrade to keep all features!')}
            </span>
          </div>
        </div>
      )}
      
      <div className="subscription-details">
        <div className="detail-item">
          <span className="detail-label">
            {t('subscription.period_start', 'Period Start')}
          </span>
          <span className="detail-value">
            {formatDate(subscription.current_period_start)}
          </span>
        </div>
        
        <div className="detail-item">
          <span className="detail-label">
            {t('subscription.period_end', 'Period End')}
          </span>
          <span className="detail-value">
            {formatDate(subscription.current_period_end)}
          </span>
        </div>
        
        {subscription.billing_cycle && (
          <div className="detail-item">
            <span className="detail-label">
              {t('subscription.billing_cycle', 'Billing Cycle')}
            </span>
            <span className="detail-value">
              {t(`subscription.billing.${subscription.billing_cycle}`, subscription.billing_cycle)}
            </span>
          </div>
        )}
        
        {subscription.cancel_at_period_end && (
          <div className="cancellation-notice">
            ⚠️ {t('subscription.cancel_notice', 'Your subscription will be canceled at the end of the current period')}
          </div>
        )}
      </div>
      
      {usage && (
        <div className="usage-summary">
          <h3>{t('subscription.usage_title', 'Usage This Period')}</h3>
          <div className="usage-grid">
            {Object.entries(usage).map(([key, data]) => (
              <div key={key} className="usage-item">
                <div className="usage-label">
                  {t(`subscription.resources.${key}`, key)}
                </div>
                <div className="usage-bar">
                  <div
                    className={`usage-fill ${data.is_exceeded ? 'exceeded' : data.is_warning ? 'warning' : 'normal'}`}
                    style={{ width: `${Math.min(data.percentage, 100)}%` }}
                  />
                </div>
                <div className="usage-text">
                  {data.limit === -1
                    ? t('subscription.unlimited', 'Unlimited')
                    : `${data.current} / ${data.limit}`
                  }
                  {data.is_exceeded && (
                    <span className="exceeded-badge">
                      {t('subscription.quota_exceeded', 'Exceeded')}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default SubscriptionStatus;
