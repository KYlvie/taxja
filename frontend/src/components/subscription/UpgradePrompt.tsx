/**
 * Upgrade Prompt Modal Component
 * 
 * Triggered when accessing restricted features.
 * Per Requirements 2.2, 7.2: Show upgrade prompt with feature benefits.
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import './UpgradePrompt.css';

interface UpgradePromptProps {
  isOpen: boolean;
  onClose: () => void;
  feature: string;
  requiredPlan: 'free' | 'plus' | 'pro';
  featureBenefits?: string[];
}

const UpgradePrompt: React.FC<UpgradePromptProps> = ({
  isOpen,
  onClose,
  feature,
  requiredPlan,
  featureBenefits = [],
}) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  
  if (!isOpen) return null;
  
  const handleUpgrade = () => {
    navigate('/pricing');
    onClose();
  };
  
  const getPlanName = () => {
    return requiredPlan === 'pro' 
      ? t('upgrade.plans.pro', 'Pro')
      : t('upgrade.plans.plus', 'Plus');
  };
  
  const getFeatureName = () => {
    const featureNames: Record<string, string> = {
      ocr_scanning: t('upgrade.features.ocr_scanning', 'OCR Scanning'),
      unlimited_ocr: t('upgrade.features.unlimited_ocr', 'Unlimited OCR'),
      ai_assistant: t('upgrade.features.ai_assistant', 'AI Tax Assistant'),
      e1_generation: t('upgrade.features.e1_generation', 'E1 Form Generation'),
      advanced_reports: t('upgrade.features.advanced_reports', 'Advanced Reports'),
      api_access: t('upgrade.features.api_access', 'API Access'),
      unlimited_transactions: t('upgrade.features.unlimited_transactions', 'Unlimited Transactions'),
    };
    
    return featureNames[feature] || feature;
  };
  
  const defaultBenefits = requiredPlan === 'pro' ? [
    t('upgrade.benefits.pro.1', 'Unlimited OCR scanning'),
    t('upgrade.benefits.pro.2', 'AI-powered tax assistance'),
    t('upgrade.benefits.pro.3', 'Automatic E1 form generation'),
    t('upgrade.benefits.pro.4', 'Advanced analytics and reports'),
    t('upgrade.benefits.pro.5', 'Priority customer support'),
  ] : [
    t('upgrade.benefits.plus.1', 'Unlimited transactions'),
    t('upgrade.benefits.plus.2', '20 OCR scans per month'),
    t('upgrade.benefits.plus.3', 'Full tax calculations'),
    t('upgrade.benefits.plus.4', 'Multi-language support'),
    t('upgrade.benefits.plus.5', 'VAT & SVS calculations'),
  ];
  
  const benefits = featureBenefits.length > 0 ? featureBenefits : defaultBenefits;
  
  return (
    <>
      <div className="modal-overlay" onClick={onClose} />
      <div className="upgrade-prompt-modal">
        <button className="modal-close" onClick={onClose} aria-label="Close">
          ×
        </button>
        
        <div className="modal-icon">
          <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
            <circle cx="32" cy="32" r="32" fill="#FEF3C7" />
            <path
              d="M32 16L36.5 25.5L47 27L39.5 34L41.5 44.5L32 39.5L22.5 44.5L24.5 34L17 27L27.5 25.5L32 16Z"
              fill="#F59E0B"
            />
          </svg>
        </div>
        
        <h2 className="modal-title">
          {t('upgrade.title', 'Upgrade to {{plan}}', { plan: getPlanName() })}
        </h2>
        
        <p className="modal-description">
          {t('upgrade.description', 
            '{{feature}} is available on the {{plan}} plan. Upgrade now to unlock this feature and more!',
            { feature: getFeatureName(), plan: getPlanName() }
          )}
        </p>
        
        <div className="benefits-section">
          <h3>{t('upgrade.benefits_title', 'What you\'ll get:')}</h3>
          <ul className="benefits-list">
            {benefits.map((benefit, index) => (
              <li key={index}>
                <span className="benefit-icon">✓</span>
                <span>{benefit}</span>
              </li>
            ))}
          </ul>
        </div>
        
        <div className="modal-actions">
          <button className="btn-upgrade" onClick={handleUpgrade}>
            {t('upgrade.button', 'Upgrade Now')}
          </button>
          <button className="btn-cancel" onClick={onClose}>
            {t('upgrade.cancel', 'Maybe Later')}
          </button>
        </div>
        
        <p className="trial-note">
          {t('upgrade.trial_note', '✨ Start with a 14-day free trial of Pro plan')}
        </p>
      </div>
    </>
  );
};

export default UpgradePrompt;
