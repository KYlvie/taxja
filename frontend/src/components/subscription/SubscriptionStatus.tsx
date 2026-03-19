/**
 * Subscription Status Component
 * 
 * Displays current plan, subscription period, trial countdown, and credit usage.
 * Per Requirement 7.3, 11.1, 11.2: Show subscription details and unified credit display.
 */

import React, { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useSubscriptionStore } from '../../stores/subscriptionStore';
import './SubscriptionStatus.css';

const SubscriptionStatus: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const {
    subscription,
    currentPlan,
    creditBalance,
    creditCosts,
    creditLoading,
    fetchSubscription,
    fetchCreditBalance,
    fetchCreditCosts,
    toggleOverage,
  } = useSubscriptionStore();

  useEffect(() => {
    fetchSubscription();
    fetchCreditBalance();
    fetchCreditCosts();
  }, [fetchSubscription, fetchCreditBalance, fetchCreditCosts]);

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

  const getEstimatedOperations = () => {
    if (!creditBalance || creditCosts.length === 0) return [];
    const available = creditBalance.available_without_overage;
    const estimates: { operation: string; count: number }[] = [];

    const operationLabels: Record<string, string> = {
      ocr_scan: 'OCR Scans',
      ai_conversation: 'AI Conversations',
      transaction_entry: 'Transactions',
      bank_import: 'Bank Imports',
      e1_generation: 'E1 Generations',
      tax_calc: 'Tax Calculations',
    };

    for (const cost of creditCosts) {
      if (cost.credit_cost > 0) {
        estimates.push({
          operation: operationLabels[cost.operation] || cost.operation,
          count: Math.floor(available / cost.credit_cost),
        });
      }
    }
    return estimates;
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

      {creditBalance && (
        <div className="credit-summary">
          <h3>{t('subscription.credits_title', 'Credits')}</h3>

          {/* Plan balance bar */}
          <div className="credit-item">
            <div className="credit-label">
              {t('subscription.plan_credits', 'Plan')}
            </div>
            <div className="credit-bar">
              <div
                className={`credit-fill ${creditBalance.plan_balance === 0 ? 'depleted' : creditBalance.plan_balance < creditBalance.monthly_credits * 0.2 ? 'low' : 'normal'}`}
                style={{ width: `${creditBalance.monthly_credits > 0 ? Math.min((creditBalance.plan_balance / creditBalance.monthly_credits) * 100, 100) : 0}%` }}
              />
            </div>
            <div className="credit-text">
              {creditBalance.plan_balance} / {creditBalance.monthly_credits}
            </div>
          </div>

          {/* Topup balance */}
          <div className="credit-item">
            <div className="credit-label">
              {t('subscription.topup_credits', 'Top-up')}
            </div>
            <div className="credit-bar">
              <div
                className="credit-fill topup"
                style={{ width: `${creditBalance.topup_balance > 0 ? Math.min((creditBalance.topup_balance / Math.max(creditBalance.monthly_credits, 100)) * 100, 100) : 0}%` }}
              />
            </div>
            <div className="credit-text">
              {creditBalance.topup_balance} {t('subscription.remaining', 'remaining')}
            </div>
          </div>

          {/* Overage toggle - only for Plus/Pro */}
          {currentPlan && currentPlan.plan_type !== 'free' && (
            <div className="overage-section">
              <div className="overage-toggle-row">
                <div className="overage-info">
                  <span className="overage-label">⚡ {t('subscription.overage_enabled', 'Overages')}</span>
                  {creditBalance.overage_price_per_credit && (
                    <span className="overage-price">
                      €{creditBalance.overage_price_per_credit.toFixed(2)} {t('subscription.per_credit', 'per credit')}
                    </span>
                  )}
                </div>
                <label className="toggle-switch" aria-label={t('subscription.toggle_overage', 'Toggle overage')}>
                  <input
                    type="checkbox"
                    checked={creditBalance.overage_enabled}
                    onChange={(e) => toggleOverage(e.target.checked)}
                    disabled={creditLoading}
                  />
                  <span className="toggle-slider"></span>
                </label>
              </div>

              {creditBalance.overage_credits_used > 0 && (
                <div className="overage-usage">
                  {t('subscription.overage_this_period', "This period's overage")}: {creditBalance.overage_credits_used} {t('subscription.credits_word', 'credits')} (€{creditBalance.estimated_overage_cost.toFixed(2)})
                </div>
              )}

              {creditBalance.has_unpaid_overage && (
                <div className="overage-warning">
                  ⚠️ {t('subscription.unpaid_overage', 'You have unpaid overage charges. Please settle to continue using overage.')}
                </div>
              )}
            </div>
          )}

          {/* Estimated operations */}
          {getEstimatedOperations().length > 0 && (
            <div className="credit-estimates">
              <div className="estimates-label">
                {t('subscription.estimated_usage', 'Approximate remaining')}:
              </div>
              <div className="estimates-grid">
                {getEstimatedOperations().slice(0, 4).map((est) => (
                  <span key={est.operation} className="estimate-chip">
                    ~{est.count} {est.operation}
                  </span>
                ))}
              </div>
              <div className="estimates-disclaimer">
                {t('subscription.estimates_disclaimer', 'Estimates based on standard cost table. Actual usage may vary.')}
              </div>
            </div>
          )}
        </div>
      )}

    </div>
  );
};

export default SubscriptionStatus;
