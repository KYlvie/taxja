/**
 * Checkout Success Page
 * 
 * Displayed after successful Stripe checkout.
 * Per Requirement 7.4: Show activated plan details.
 */

import React, { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useSubscriptionStore } from '../stores/subscriptionStore';
import './CheckoutSuccess.css';

const CheckoutSuccess: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { fetchSubscription, currentPlan } = useSubscriptionStore();
  
  const sessionId = searchParams.get('session_id');
  
  useEffect(() => {
    // Fetch updated subscription after successful checkout
    fetchSubscription();
  }, [fetchSubscription]);
  
  const handleContinue = () => {
    navigate('/dashboard');
  };
  
  const handleViewSubscription = () => {
    navigate('/pricing');
  };
  
  return (
    <div className="checkout-success">
      <div className="success-card">
        <div className="success-icon">
          <svg width="80" height="80" viewBox="0 0 80 80" fill="none">
            <circle cx="40" cy="40" r="40" fill="#D1FAE5" />
            <path
              d="M25 40L35 50L55 30"
              stroke="#10B981"
              strokeWidth="4"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
        
        <h1>{t('checkout.success_title', 'Payment Successful!')}</h1>
        
        <p className="success-message">
          {t('checkout.success_message',
            'Thank you for subscribing! Your payment has been processed successfully.'
          )}
        </p>
        
        {currentPlan && (
          <div className="plan-activated">
            <div className="plan-badge">
              {currentPlan.name}
            </div>
            <p>
              {t('checkout.plan_activated', 'Your {{plan}} plan is now active!', {
                plan: currentPlan.name
              })}
            </p>
          </div>
        )}
        
        <div className="success-details">
          <div className="detail-item">
            <span className="detail-icon">✓</span>
            <span>{t('checkout.detail_1', 'Full access to all features')}</span>
          </div>
          <div className="detail-item">
            <span className="detail-icon">✓</span>
            <span>{t('checkout.detail_2', 'Billing starts today')}</span>
          </div>
          <div className="detail-item">
            <span className="detail-icon">✓</span>
            <span>{t('checkout.detail_3', 'Cancel anytime')}</span>
          </div>
        </div>
        
        {sessionId && (
          <div className="session-info">
            <small>
              {t('checkout.session_id', 'Session ID')}: {sessionId.substring(0, 20)}...
            </small>
          </div>
        )}
        
        <div className="success-actions">
          <button className="btn-primary" onClick={handleContinue}>
            {t('checkout.continue_dashboard', 'Continue to Dashboard')}
          </button>
          <button className="btn-secondary" onClick={handleViewSubscription}>
            {t('checkout.view_subscription', 'View Subscription Details')}
          </button>
        </div>
        
        <p className="support-text">
          {t('checkout.support',
            'Questions? Contact us at support@taxja.com'
          )}
        </p>
      </div>
    </div>
  );
};

export default CheckoutSuccess;
