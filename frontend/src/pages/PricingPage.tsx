/**
 * Pricing Page Component
 * 
 * Displays three-column plan comparison with monthly/yearly toggle.
 * Per Requirements 1.4, 1.5, 1.6, 7.1, 7.6: Plan comparison and trial activation.
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useSubscriptionStore } from '../stores/subscriptionStore';
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
}

const PricingPage: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('monthly');
  const [loading, setLoading] = useState(false);
  const { createCheckoutSession, subscription } = useSubscriptionStore();
  
  // Plan definitions per Requirements 1.4, 1.5, 1.6
  const plans: PlanDetails[] = [
    {
      type: 'free',
      name: t('pricing.plans.free.name', 'Free'),
      monthlyPrice: 0,
      yearlyPrice: 0,
      features: [
        { name: t('pricing.features.transactions_limit', '50 transactions/month'), included: true },
        { name: t('pricing.features.basic_tax_calc', 'Basic tax calculation'), included: true },
        { name: t('pricing.features.german_only', 'German language only'), included: true },
        { name: t('pricing.features.ocr', 'OCR scanning'), included: false },
        { name: t('pricing.features.ai_assistant', 'AI Tax Assistant'), included: false },
        { name: t('pricing.features.e1_generation', 'E1 form generation'), included: false },
      ],
    },
    {
      type: 'plus',
      name: t('pricing.plans.plus.name', 'Plus'),
      monthlyPrice: 4.90,
      yearlyPrice: 49.00,
      recommended: true,
      features: [
        { name: t('pricing.features.unlimited_transactions', 'Unlimited transactions'), included: true },
        { name: t('pricing.features.ocr_limit', '20 OCR scans/month'), included: true },
        { name: t('pricing.features.full_tax_calc', 'Full tax calculation'), included: true },
        { name: t('pricing.features.multi_language', 'Multi-language (DE, EN, ZH)'), included: true },
        { name: t('pricing.features.vat_svs', 'VAT & SVS calculations'), included: true },
        { name: t('pricing.features.ai_assistant', 'AI Tax Assistant'), included: false },
        { name: t('pricing.features.e1_generation', 'E1 form generation'), included: false },
      ],
    },
    {
      type: 'pro',
      name: t('pricing.plans.pro.name', 'Pro'),
      monthlyPrice: 9.90,
      yearlyPrice: 99.00,
      features: [
        { name: t('pricing.features.everything_plus', 'Everything in Plus'), included: true },
        { name: t('pricing.features.unlimited_ocr', 'Unlimited OCR scanning'), included: true },
        { name: t('pricing.features.ai_assistant', 'AI Tax Assistant'), included: true },
        { name: t('pricing.features.e1_generation', 'E1 form generation'), included: true },
        { name: t('pricing.features.advanced_reports', 'Advanced reports'), included: true },
        { name: t('pricing.features.priority_support', 'Priority support'), included: true },
        { name: t('pricing.features.api_access', 'API access'), included: true },
      ],
    },
  ];
  
  // Calculate yearly discount (17%)
  const yearlyDiscount = 17;
  
  const handleSelectPlan = async (planType: 'free' | 'plus' | 'pro') => {
    if (planType === 'free') {
      // Free plan - just navigate to dashboard
      navigate('/dashboard');
      return;
    }
    
    setLoading(true);
    
    try {
      // Get plan ID from backend (would need to fetch plans first in real implementation)
      const planId = planType === 'plus' ? 2 : 3; // Assuming IDs: 1=Free, 2=Plus, 3=Pro
      
      const successUrl = `${window.location.origin}/checkout/success`;
      const cancelUrl = `${window.location.origin}/pricing`;
      
      const { url } = await createCheckoutSession(
        planId,
        billingCycle,
        successUrl,
        cancelUrl
      );
      
      // Redirect to Stripe checkout
      window.location.href = url;
    } catch (error) {
      console.error('Failed to create checkout session:', error);
      alert(t('pricing.errors.checkout_failed', 'Failed to start checkout. Please try again.'));
    } finally {
      setLoading(false);
    }
  };
  
  const getPrice = (plan: PlanDetails) => {
    if (plan.monthlyPrice === 0) return t('pricing.free', 'Free');
    
    const price = billingCycle === 'monthly' ? plan.monthlyPrice : plan.yearlyPrice / 12;
    return `€${price.toFixed(2)}`;
  };
  
  const getBillingText = (plan: PlanDetails) => {
    if (plan.monthlyPrice === 0) return '';
    
    if (billingCycle === 'monthly') {
      return t('pricing.per_month', '/month');
    } else {
      return t('pricing.per_month_billed_yearly', '/month, billed yearly');
    }
  };
  
  const getButtonText = (planType: 'free' | 'plus' | 'pro') => {
    // Check if user is on trial
    if (subscription?.status === 'trialing') {
      return t('pricing.buttons.start_trial', 'Start 14-Day Pro Trial');
    }
    
    // Check current plan
    if (subscription?.plan_id) {
      // Would need to compare with actual plan - simplified here
      return t('pricing.buttons.upgrade', 'Upgrade');
    }
    
    if (planType === 'free') {
      return t('pricing.buttons.get_started', 'Get Started');
    }
    
    return t('pricing.buttons.subscribe', 'Subscribe');
  };
  
  return (
    <div className="pricing-page">
      <div className="pricing-header">
        <h1>{t('pricing.title', 'Choose Your Plan')}</h1>
        <p className="pricing-subtitle">
          {t('pricing.subtitle', 'Start with a 14-day Pro trial, then choose the plan that fits your needs')}
        </p>
        
        {/* Billing cycle toggle */}
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
          <div
            key={plan.type}
            className={`pricing-card ${plan.recommended ? 'recommended' : ''}`}
          >
            {plan.recommended && (
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
                  {t('pricing.billed_as', 'Billed as €{{amount}}/year', {
                    amount: plan.yearlyPrice.toFixed(2)
                  })}
                </div>
              )}
            </div>
            
            <ul className="plan-features">
              {plan.features.map((feature, index) => (
                <li key={index} className={feature.included ? 'included' : 'not-included'}>
                  <span className="feature-icon">
                    {feature.included ? '✓' : '×'}
                  </span>
                  <span className="feature-text">{feature.name}</span>
                </li>
              ))}
            </ul>
            
            <button
              className={`plan-button ${plan.recommended ? 'primary' : 'secondary'}`}
              onClick={() => handleSelectPlan(plan.type)}
              disabled={loading}
            >
              {loading ? t('pricing.buttons.loading', 'Loading...') : getButtonText(plan.type)}
            </button>
          </div>
        ))}
      </div>
      
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
