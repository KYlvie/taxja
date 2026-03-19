import React from 'react';
import { useTranslation } from 'react-i18next';
import { useSubscriptionStore } from '../../stores/subscriptionStore';
import './CreditTopup.css';

const TOPUP_PACKAGES = [
  { id: 1, name: 'Small', credits: 100, price: 4.99 },
  { id: 2, name: 'Medium', credits: 300, price: 12.99 },
  { id: 3, name: 'Large', credits: 1000, price: 39.99 },
];

const CreditTopup: React.FC = () => {
  const { t } = useTranslation();
  const { creditLoading, createTopupCheckout } = useSubscriptionStore();

  const handlePurchase = async (packageId: number) => {
    try {
      const result = await createTopupCheckout(
        packageId,
        `${window.location.origin}/checkout/success`,
        `${window.location.origin}/pricing`,
      );
      if (result.url) {
        window.location.href = result.url;
      }
    } catch (error) {
      console.error('Topup checkout failed:', error);
    }
  };

  const getPricePerCredit = (pkg: typeof TOPUP_PACKAGES[0]) => {
    return (pkg.price / pkg.credits).toFixed(3);
  };

  return (
    <div className="credit-topup">
      <h3>{t('credits.topup_title', 'Buy Credits')}</h3>
      <p className="topup-subtitle">
        {t('credits.topup_subtitle', 'Top-up credits are valid for 12 months.')}
      </p>
      <div className="topup-packages">
        {TOPUP_PACKAGES.map((pkg) => (
          <div key={pkg.id} className="topup-card">
            <div className="topup-name">{pkg.name}</div>
            <div className="topup-credits">{pkg.credits} {t('credits.credits_word', 'credits')}</div>
            <div className="topup-price">€{pkg.price.toFixed(2)}</div>
            <div className="topup-unit">€{getPricePerCredit(pkg)}/{t('credits.per_credit_short', 'cr')}</div>
            <button
              className="topup-buy-btn"
              onClick={() => handlePurchase(pkg.id)}
              disabled={creditLoading}
            >
              {creditLoading ? '...' : t('credits.buy', 'Buy')}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};

export default CreditTopup;
