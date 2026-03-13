/**
 * Feature Gate Higher-Order Component
 * 
 * Wraps components to enforce feature-based access control.
 * Per Requirements 2.1, 2.2, 7.2: Show upgrade prompt when access denied.
 */

import React, { useState, useEffect, ComponentType } from 'react';
import { useSubscriptionStore } from '../../stores/subscriptionStore';
import UpgradePrompt from './UpgradePrompt';

export type Feature =
  | 'ocr_scanning'
  | 'unlimited_ocr'
  | 'ai_assistant'
  | 'e1_generation'
  | 'advanced_reports'
  | 'api_access'
  | 'unlimited_transactions'
  | 'multi_language'
  | 'vat_calc'
  | 'svs_calc';

export type PlanType = 'free' | 'plus' | 'pro';

interface FeatureGateConfig {
  feature: Feature;
  requiredPlan: PlanType;
  featureBenefits?: string[];
  fallback?: React.ReactNode;
}

/**
 * HOC to wrap components with feature gating
 * 
 * Usage:
 * const ProtectedComponent = withFeatureGate(MyComponent, {
 *   feature: 'ai_assistant',
 *   requiredPlan: 'pro'
 * });
 */
export function withFeatureGate<P extends object>(
  WrappedComponent: ComponentType<P>,
  config: FeatureGateConfig
) {
  return function FeatureGatedComponent(props: P) {
    const { currentPlan } = useSubscriptionStore();
    const [showUpgradePrompt, setShowUpgradePrompt] = useState(false);
    const [hasAccess, setHasAccess] = useState(false);
    
    useEffect(() => {
      if (!currentPlan) {
        setHasAccess(false);
        return;
      }
      
      // Check if user's plan has access to the feature
      const access = checkFeatureAccess(
        currentPlan.plan_type,
        config.feature,
        currentPlan.features
      );
      
      setHasAccess(access);
      
      // Show upgrade prompt if no access
      if (!access) {
        setShowUpgradePrompt(true);
      }
    }, [currentPlan]);
    
    if (!hasAccess) {
      if (config.fallback) {
        return <>{config.fallback}</>;
      }
      
      return (
        <>
          <UpgradePrompt
            isOpen={showUpgradePrompt}
            onClose={() => setShowUpgradePrompt(false)}
            feature={config.feature}
            requiredPlan={config.requiredPlan}
            featureBenefits={config.featureBenefits}
          />
          <div className="feature-locked">
            <div className="lock-icon">🔒</div>
            <p>This feature requires {config.requiredPlan.toUpperCase()} plan</p>
            <button onClick={() => setShowUpgradePrompt(true)}>
              Upgrade Now
            </button>
          </div>
        </>
      );
    }
    
    return <WrappedComponent {...props} />;
  };
}

/**
 * Hook to check feature access
 * 
 * Usage:
 * const hasAccess = useFeatureAccess('ai_assistant');
 */
export function useFeatureAccess(feature: Feature): boolean {
  const { currentPlan } = useSubscriptionStore();
  
  if (!currentPlan) return false;
  
  return checkFeatureAccess(
    currentPlan.plan_type,
    feature,
    currentPlan.features
  );
}

/**
 * Hook to trigger upgrade prompt
 * 
 * Usage:
 * const showUpgrade = useUpgradePrompt();
 * showUpgrade('ai_assistant', 'pro');
 */
export function useUpgradePrompt() {
  const [promptState, setPromptState] = useState<{
    isOpen: boolean;
    feature: Feature;
    requiredPlan: PlanType;
  }>({
    isOpen: false,
    feature: 'ai_assistant',
    requiredPlan: 'pro',
  });
  
  const showUpgrade = (feature: Feature, requiredPlan: PlanType) => {
    setPromptState({
      isOpen: true,
      feature,
      requiredPlan,
    });
  };
  
  const closePrompt = () => {
    setPromptState(prev => ({ ...prev, isOpen: false }));
  };
  
  return {
    showUpgrade,
    UpgradePromptComponent: (
      <UpgradePrompt
        isOpen={promptState.isOpen}
        onClose={closePrompt}
        feature={promptState.feature}
        requiredPlan={promptState.requiredPlan}
      />
    ),
  };
}

/**
 * Helper function to check feature access
 */
function checkFeatureAccess(
  planType: PlanType,
  feature: Feature,
  planFeatures: Record<string, boolean>
): boolean {
  // Check if feature is explicitly enabled in plan
  if (planFeatures[feature]) {
    return true;
  }
  
  // Plan hierarchy check
  const planHierarchy: Record<PlanType, number> = {
    free: 0,
    plus: 1,
    pro: 2,
  };
  
  // Feature requirements
  const featureRequirements: Record<Feature, PlanType> = {
    ocr_scanning: 'plus',
    unlimited_ocr: 'pro',
    ai_assistant: 'pro',
    e1_generation: 'pro',
    advanced_reports: 'pro',
    api_access: 'pro',
    unlimited_transactions: 'plus',
    multi_language: 'plus',
    vat_calc: 'plus',
    svs_calc: 'plus',
  };
  
  const requiredPlan = featureRequirements[feature];
  if (!requiredPlan) return true; // Feature not restricted
  
  return planHierarchy[planType] >= planHierarchy[requiredPlan];
}

/**
 * Component to show feature locked state
 */
export const FeatureLockedBanner: React.FC<{
  feature: Feature;
  requiredPlan: PlanType;
  onUpgrade?: () => void;
}> = ({ feature, requiredPlan, onUpgrade }) => {
  const [showPrompt, setShowPrompt] = useState(false);
  
  const handleUpgrade = () => {
    if (onUpgrade) {
      onUpgrade();
    } else {
      setShowPrompt(true);
    }
  };
  
  return (
    <>
      <div className="feature-locked-banner">
        <div className="banner-content">
          <span className="lock-icon">🔒</span>
          <span className="banner-text">
            This feature requires {requiredPlan.toUpperCase()} plan
          </span>
        </div>
        <button className="upgrade-button" onClick={handleUpgrade}>
          Upgrade
        </button>
      </div>
      
      <UpgradePrompt
        isOpen={showPrompt}
        onClose={() => setShowPrompt(false)}
        feature={feature}
        requiredPlan={requiredPlan}
      />
    </>
  );
};
