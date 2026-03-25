import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useSubscriptionStore } from '../stores/subscriptionStore';
import { useConfirm } from '../hooks/useConfirm';
import { useAuthStore } from '../stores/authStore';
import { formatCurrency, getLocaleForLanguage } from '../utils/locale';
import SubpageBackLink from '../components/common/SubpageBackLink';
import './PricingPage.css';

interface PlanFeature {
  name: string;
  included: boolean;
}

interface PlanDetails {
  type: 'free' | 'plus' | 'pro';
  name: string;
  monthlyPrice: number;
  yearlyPrice: number;
  features: PlanFeature[];
  recommended?: boolean;
  monthlyCredits: number;
  overagePrice: number | null;
}

const PricingPage: React.FC = () => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('monthly');
  const [loading, setLoading] = useState(false);
  const {
    createCheckoutSession,
    subscription,
    openCustomerPortal,
    currentPlan,
    upgradeSubscription,
    downgradeSubscription,
  } = useSubscriptionStore();
  const user = useAuthStore((state) => state.user);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const currentLanguage = i18n.resolvedLanguage || i18n.language;
  const currentPlanType = currentPlan?.plan_type || 'free';
  const { confirm: showConfirm, alert: showAlert } = useConfirm();
  const isAdmin = user?.is_admin === true;

  const plans: PlanDetails[] = [
    {
      type: 'free',
      name: t('pricing.plans.free.name', 'Free'),
      monthlyPrice: 0,
      yearlyPrice: 0,
      monthlyCredits: 100,
      overagePrice: null,
      features: [
        { name: t('pricing.features.ocr_scanning', 'AI document scanning & recognition'), included: true },
        { name: t('pricing.features.ai_assistant', 'AI tax assistant'), included: true },
        { name: t('pricing.features.basic_tax_calc', 'Basic tax calculation'), included: true },
        { name: t('pricing.features.transaction_entry', 'Transaction management'), included: true },
        { name: t('pricing.features.basic_reports', 'Basic reports (annual summary, tax estimate)'), included: true },
        { name: t('pricing.features.full_tax_calc', 'Full tax calculation'), included: false },
        { name: t('pricing.features.vat_svs', 'VAT & SVS calculations'), included: false },
        { name: t('pricing.features.property_management', 'Property management'), included: false },
        { name: t('pricing.features.bank_import', 'Bank statement import'), included: false },
        { name: t('pricing.features.recurring_suggestions', 'Smart recurring suggestions'), included: false },
        { name: t('pricing.features.tax_forms', 'Tax form generation (E1, E1a, E1b...)'), included: false },
        { name: t('pricing.features.advanced_reports', 'All reports (EA, Balance Sheet, Saldenliste)'), included: false },
      ],
    },
    {
      type: 'plus',
      name: t('pricing.plans.plus.name', 'Plus'),
      monthlyPrice: 4.9,
      yearlyPrice: 49,
      recommended: true,
      monthlyCredits: 500,
      overagePrice: 0.04,
      features: [
        { name: t('pricing.features.ocr_scanning', 'AI document scanning & recognition'), included: true },
        { name: t('pricing.features.ai_assistant', 'AI tax assistant'), included: true },
        { name: t('pricing.features.full_tax_calc', 'Full tax calculation'), included: true },
        { name: t('pricing.features.vat_svs', 'VAT & SVS calculations'), included: true },
        { name: t('pricing.features.unlimited_transactions', 'Unlimited transactions'), included: true },
        { name: t('pricing.features.property_management', 'Property management'), included: true },
        { name: t('pricing.features.bank_import', 'Bank statement import'), included: true },
        { name: t('pricing.features.recurring_suggestions', 'Smart recurring suggestions'), included: true },
        { name: t('pricing.features.basic_reports', 'Basic reports'), included: true },
        { name: t('pricing.features.tax_forms', 'Tax form generation (E1, E1a, E1b...)'), included: false },
        { name: t('pricing.features.advanced_reports', 'All reports (EA, Balance Sheet, Saldenliste)'), included: false },
        { name: t('pricing.features.priority_support', 'Priority support'), included: false },
      ],
    },
    {
      type: 'pro',
      name: t('pricing.plans.pro.name', 'Pro'),
      monthlyPrice: 12.9,
      yearlyPrice: 129,
      monthlyCredits: 2000,
      overagePrice: 0.03,
      features: [
        { name: t('pricing.features.ocr_scanning', 'AI document scanning & recognition'), included: true },
        { name: t('pricing.features.ai_assistant', 'AI tax assistant'), included: true },
        { name: t('pricing.features.full_tax_calc', 'Full tax calculation'), included: true },
        { name: t('pricing.features.vat_svs', 'VAT & SVS calculations'), included: true },
        { name: t('pricing.features.unlimited_transactions', 'Unlimited transactions'), included: true },
        { name: t('pricing.features.property_management', 'Property management'), included: true },
        { name: t('pricing.features.bank_import', 'Bank statement import'), included: true },
        { name: t('pricing.features.recurring_suggestions', 'Smart recurring suggestions'), included: true },
        { name: t('pricing.features.tax_forms_pro', 'All tax forms (E1, E1a, E1b, L1, U1...)'), included: true },
        { name: t('pricing.features.advanced_reports', 'All reports (EA, Balance Sheet, Saldenliste)'), included: true },
        { name: t('pricing.features.priority_support', 'Priority support'), included: true },
      ],
    },
  ];

  const yearlyDiscount = 17;

  const handleSelectPlan = async (planType: 'free' | 'plus' | 'pro') => {
    if (planType === 'free') {
      // Downgrade to free = cancel subscription
      if (currentPlanType !== 'free' && subscription?.status === 'active') {
        const ok = await showConfirm(t('subscription.cancel_confirm_message', "Your subscription will remain active until the end of the current period. After that, you'll be downgraded to the Free plan.", { date: '' }), { title: t('subscription.cancel_confirm_title', 'Cancel Subscription?'), variant: 'warning' });
        if (ok) {
          try {
            setLoading(true);
            const { cancelSubscription } = useSubscriptionStore.getState();
            await cancelSubscription();
            await showAlert(t('subscription.cancel_success', 'Your subscription will be canceled at the end of the current period.'));
          } catch {
            await showAlert(t('pricing.errors.checkout_failed', 'Failed. Please try again.'), { variant: 'danger' });
          } finally {
            setLoading(false);
          }
        }
      } else {
        navigate('/dashboard');
      }
      return;
    }

    // If user already has this plan, open customer portal to manage it
    if (currentPlanType === planType && subscription?.status === 'active') {
      try {
        setLoading(true);
        await openCustomerPortal(`${window.location.origin}/pricing`);
      } catch {
        await showAlert(t('pricing.errors.portal_failed', 'Failed to open subscription management.'));
      } finally {
        setLoading(false);
      }
      return;
    }

    const hasActiveStripeSubscription =
      subscription?.status === 'active' && Boolean(subscription?.stripe_subscription_id);

    setLoading(true);

    try {
      const planId = planType === 'plus' ? 3 : 4;

      if (hasActiveStripeSubscription) {
        // Existing subscriber switching plan → Stripe Customer Portal
        if (tierOrder[planType] > tierOrder[currentPlanType]) {
          await upgradeSubscription(planId, billingCycle);
        } else {
          await downgradeSubscription(planId, billingCycle);
        }
      } else {
        // New subscription — create Stripe Checkout session
        const successUrl = `${window.location.origin}/checkout/success`;
        const cancelUrl = `${window.location.origin}/pricing`;
        const { url } = await createCheckoutSession(planId, billingCycle, successUrl, cancelUrl);
        window.location.href = url;
      }
    } catch (error) {
      console.error('Failed to change plan:', error);
      await showAlert(t('pricing.errors.checkout_failed', 'Failed to start checkout. Please try again.'), { variant: 'danger' });
    } finally {
      setLoading(false);
    }
  };

  const getPrice = (plan: PlanDetails) => {
    if (plan.monthlyPrice === 0) {
      return t('pricing.free', 'Free');
    }

    const price = billingCycle === 'monthly' ? plan.monthlyPrice : plan.yearlyPrice / 12;
    return formatCurrency(price, currentLanguage);
  };

  const getYearlyAmount = (plan: PlanDetails) =>
    new Intl.NumberFormat(getLocaleForLanguage(currentLanguage), {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(plan.yearlyPrice);

  const getBillingText = (plan: PlanDetails) => {
    if (plan.monthlyPrice === 0) {
      return '';
    }

    return billingCycle === 'monthly'
      ? t('pricing.per_month', '/month')
      : t('pricing.per_month_billed_yearly', '/month, billed yearly');
  };

  const tierOrder: Record<string, number> = { free: 0, plus: 1, pro: 2 };
  const isTrialing = subscription?.status === 'trialing';
  const isActive = subscription?.status === 'active';

  const isPlanDisabled = (planType: string) => {
    // Free card: disabled for trial users and paid subscribers (cancel is in Account Management)
    if (planType === 'free') {
      return isTrialing || (isActive && currentPlanType !== 'free');
    }
    // Current plan card: disabled
    if (planType === currentPlanType && isActive) return true;
    return false;
  };

  const getButtonText = (planType: 'free' | 'plus' | 'pro') => {
    // Current active plan → Current Plan
    if (planType === currentPlanType && isActive) {
      return t('pricing.buttons.current_plan', 'Current Plan');
    }

    // Free card
    if (planType === 'free') {
      if (currentPlanType === 'free' && !isTrialing) {
        return t('pricing.buttons.current_plan', 'Current Plan');
      }
      return t('pricing.buttons.get_started', 'Get Started');
    }

    // Paid subscriber switching to the other paid tier (Pro→Plus)
    if (isActive && currentPlanType !== 'free' && tierOrder[planType] < tierOrder[currentPlanType]) {
      return t('pricing.buttons.switch_plan', 'Switch Plan');
    }

    // Higher tier
    if (isActive && tierOrder[planType] > tierOrder[currentPlanType]) {
      return t('pricing.buttons.upgrade', 'Upgrade');
    }

    // Trial / free users picking a paid plan
    return t('pricing.buttons.subscribe', 'Subscribe');
  };

  return (
    <div className="pricing-page">
      <div className="pricing-header">
        <SubpageBackLink
          to={isAuthenticated ? '/dashboard' : '/'}
          label={isAuthenticated ? t('pricing.backToDashboard', 'Back to Dashboard') : t('pricing.backToHome', 'Back to Home')}
        />
        <h1>{t('pricing.title', 'Choose Your Plan')}</h1>
        <p className="pricing-subtitle">
          {t('pricing.subtitle', 'Start with a 14-day Pro trial, then choose the plan that fits your needs')}
        </p>

        {isAdmin && (
          <div className="pricing-admin-notice">
            {t('pricing.adminNotice', 'As an admin, you have full access to all features without a subscription.')}
          </div>
        )}

        <div className="billing-toggle">
          <button
            className={billingCycle === 'monthly' ? 'active' : ''}
            onClick={() => setBillingCycle('monthly')}
          >
            {t('pricing.billing.monthly', 'Monthly')}
          </button>
          <button
            className={billingCycle === 'yearly' ? 'active' : ''}
            onClick={() => setBillingCycle('yearly')}
          >
            {t('pricing.billing.yearly', 'Yearly')}
            <span className="discount-badge">
              {t('pricing.billing.save', 'Save {{percent}}%', { percent: yearlyDiscount })}
            </span>
          </button>
        </div>
      </div>

      <div className="pricing-plans">
        {plans.map((plan) => (
          <div key={plan.type} className={`pricing-card ${plan.recommended ? 'recommended' : ''} ${currentPlanType === plan.type ? 'current' : ''}`}>
            {currentPlanType === plan.type && subscription?.status === 'active' && (
              <div className="current-plan-badge">
                {t('pricing.current_plan', 'Current Plan')}
              </div>
            )}
            {plan.recommended && currentPlanType !== plan.type && (
              <div className="recommended-badge">
                {t('pricing.recommended', 'Recommended')}
              </div>
            )}

            <div className="plan-header">
              <h2>{plan.name}</h2>
              <div className="plan-price">
                <span className="price">{getPrice(plan)}</span>
                <span className="billing-text">{getBillingText(plan)}</span>
              </div>

              {billingCycle === 'yearly' && plan.monthlyPrice > 0 && (
                <div className="yearly-total">
                  {t('pricing.billed_as', 'Billed as EUR {{amount}}/year', {
                    amount: getYearlyAmount(plan),
                  })}
                </div>
              )}
            </div>

            <div className="plan-credits-info">
              <div className="credits-amount">
                {plan.monthlyCredits} {t('pricing.credits_per_month', 'credits/month')}
              </div>
              {plan.overagePrice !== null ? (
                <div className="overage-info">
                  {t('pricing.overage_price', 'Overage: €{{price}}/credit', { price: plan.overagePrice.toFixed(2) })}
                </div>
              ) : (
                <div className="no-overage">{t('pricing.no_overage', 'No overage')}</div>
              )}
              <div className="topup-available">
                {t('pricing.topup_available', 'Top-up available (12-month validity)')}
              </div>
            </div>

            <ul className="plan-features">
              {plan.features.map((feature, index) => (
                <li key={index} className={feature.included ? 'included' : 'not-included'}>
                  <span className="feature-icon">{feature.included ? '\u2713' : '\u00d7'}</span>
                  <span className="feature-text">{feature.name}</span>
                </li>
              ))}
            </ul>

            <button
              className={`plan-button ${plan.recommended ? 'primary' : 'secondary'}`}
              onClick={() => handleSelectPlan(plan.type)}
              disabled={loading || isPlanDisabled(plan.type)}
            >
              {loading ? t('pricing.buttons.loading', 'Loading...') : getButtonText(plan.type)}
            </button>
          </div>
        ))}
      </div>

      {/* Credit cost reference hidden - internal billing detail, not user-facing */}
      {isAdmin && <div className="credit-cost-reference">
        <h3>{t('pricing.cost_reference_title', 'Credit Cost Reference')} (Admin only)</h3>
        <div className="cost-table">
          <div className="cost-row">
            <span className="cost-operation">{t('pricing.cost_ocr', 'OCR Scan')}</span>
            <span className="cost-value">5 {t('pricing.credits_word', 'credits')}</span>
          </div>
          <div className="cost-row">
            <span className="cost-operation">{t('pricing.cost_ai', 'AI Conversation')}</span>
            <span className="cost-value">10 {t('pricing.credits_word', 'credits')}</span>
          </div>
          <div className="cost-row">
            <span className="cost-operation">{t('pricing.cost_transaction', 'Transaction Entry')}</span>
            <span className="cost-value">1 {t('pricing.credits_word', 'credit')}</span>
          </div>
          <div className="cost-row">
            <span className="cost-operation">{t('pricing.cost_bank', 'Bank Import')}</span>
            <span className="cost-value">3 {t('pricing.credits_word', 'credits')}</span>
          </div>
          <div className="cost-row">
            <span className="cost-operation">{t('pricing.cost_e1', 'E1 Generation')}</span>
            <span className="cost-value">20 {t('pricing.credits_word', 'credits')}</span>
          </div>
          <div className="cost-row">
            <span className="cost-operation">{t('pricing.cost_tax', 'Tax Calculation')}</span>
            <span className="cost-value">2 {t('pricing.credits_word', 'credits')}</span>
          </div>
        </div>
      </div>}

      <div className="pricing-footer">
        <p className="trial-info">
          {t('pricing.trial_info', 'New users get a 14-day Pro trial. No credit card required to start.')}
        </p>
        <p className="support-text">
          {t('pricing.support', 'Questions? Contact us at support@taxja.com')}
        </p>
      </div>
    </div>
  );
};

export default PricingPage;
