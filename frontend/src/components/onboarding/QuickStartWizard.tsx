import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import './QuickStartWizard.css';

interface QuickStartWizardProps {
  onComplete: () => void;
  onSkip: () => void;
}

export const QuickStartWizard = ({ onComplete, onSkip }: QuickStartWizardProps) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [currentStep] = useState(0);

  const steps = [
    {
      title: t('onboarding.welcome.title'),
      description: t('onboarding.welcome.description'),
      icon: '👋',
      action: {
        label: t('onboarding.welcome.getStarted'),
        onClick: () => {
          onComplete();
          navigate('/documents');
        },
      },
    },
  ];

  const currentStepData = steps[currentStep];

  return (
    <div className="quick-start-overlay">
      <div className="quick-start-modal">
        <button className="skip-button" onClick={onSkip}>
          {t('onboarding.skip')}
        </button>

        <div className="step-indicator">
          {steps.map((_, index) => (
            <div
              key={index}
              className={`step-dot ${index === currentStep ? 'active' : ''} ${
                index < currentStep ? 'completed' : ''
              }`}
            />
          ))}
        </div>

        <div className="step-content">
          <div className="step-icon">{currentStepData.icon}</div>
          <h2 className="step-title">{currentStepData.title}</h2>
          <p className="step-description">{currentStepData.description}</p>

          <div className="step-actions">
            <button
              className="btn btn-primary"
              onClick={currentStepData.action.onClick}
            >
              {currentStepData.action.label}
            </button>
          </div>
        </div>

        <div className="step-footer">
          <p className="step-help">
            💡 {t('onboarding.help')}
          </p>
        </div>
      </div>
    </div>
  );
};
