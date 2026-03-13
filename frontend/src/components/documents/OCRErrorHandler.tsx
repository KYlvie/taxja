import React from 'react';
import { useTranslation } from 'react-i18next';
import './OCRErrorHandler.css';

interface OCRErrorHandlerProps {
  error: string;
  confidenceScore?: number;
  onRetry?: () => void;
  onManualEntry?: () => void;
}

const OCRErrorHandler: React.FC<OCRErrorHandlerProps> = ({
  error,
  confidenceScore,
  onRetry,
  onManualEntry,
}) => {
  const { t } = useTranslation();

  const getErrorType = () => {
    if (error.includes('format')) return 'format';
    if (error.includes('size')) return 'size';
    if (error.includes('quality') || error.includes('clarity')) return 'quality';
    if (confidenceScore !== undefined && confidenceScore < 0.6) return 'low-confidence';
    return 'general';
  };

  const errorType = getErrorType();

  const getSuggestions = () => {
    switch (errorType) {
      case 'format':
        return [
          t('documents.errors.suggestions.format.1'),
          t('documents.errors.suggestions.format.2'),
          t('documents.errors.suggestions.format.3'),
        ];
      case 'size':
        return [
          t('documents.errors.suggestions.size.1'),
          t('documents.errors.suggestions.size.2'),
          t('documents.errors.suggestions.size.3'),
        ];
      case 'quality':
        return [
          t('documents.errors.suggestions.quality.1'),
          t('documents.errors.suggestions.quality.2'),
          t('documents.errors.suggestions.quality.3'),
          t('documents.errors.suggestions.quality.4'),
          t('documents.errors.suggestions.quality.5'),
        ];
      case 'low-confidence':
        return [
          t('documents.errors.suggestions.lowConfidence.1'),
          t('documents.errors.suggestions.lowConfidence.2'),
          t('documents.errors.suggestions.lowConfidence.3'),
        ];
      default:
        return [
          t('documents.errors.suggestions.general.1'),
          t('documents.errors.suggestions.general.2'),
        ];
    }
  };

  const getBestPractices = () => {
    return [
      {
        icon: '💡',
        title: t('documents.errors.bestPractices.lighting.title'),
        description: t('documents.errors.bestPractices.lighting.description'),
      },
      {
        icon: '📐',
        title: t('documents.errors.bestPractices.angle.title'),
        description: t('documents.errors.bestPractices.angle.description'),
      },
      {
        icon: '🔍',
        title: t('documents.errors.bestPractices.focus.title'),
        description: t('documents.errors.bestPractices.focus.description'),
      },
      {
        icon: '📏',
        title: t('documents.errors.bestPractices.frame.title'),
        description: t('documents.errors.bestPractices.frame.description'),
      },
    ];
  };

  const suggestions = getSuggestions();
  const bestPractices = getBestPractices();

  return (
    <div className="ocr-error-handler">
      <div className="error-header">
        <div className="error-icon">⚠️</div>
        <div className="error-content">
          <h3>{t('documents.errors.title')}</h3>
          <p className="error-message">{error}</p>
          {confidenceScore !== undefined && (
            <p className="confidence-info">
              {t('documents.errors.confidence')}: {(confidenceScore * 100).toFixed(0)}%
            </p>
          )}
        </div>
      </div>

      <div className="error-suggestions">
        <h4>{t('documents.errors.suggestionsTitle')}</h4>
        <ul>
          {suggestions.map((suggestion, index) => (
            <li key={index}>{suggestion}</li>
          ))}
        </ul>
      </div>

      <div className="best-practices">
        <h4>{t('documents.errors.bestPracticesTitle')}</h4>
        <div className="practices-grid">
          {bestPractices.map((practice, index) => (
            <div key={index} className="practice-item">
              <div className="practice-icon">{practice.icon}</div>
              <div className="practice-content">
                <h5>{practice.title}</h5>
                <p>{practice.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="error-actions">
        {onRetry && (
          <button className="btn btn-primary" onClick={onRetry}>
            📷 {t('documents.errors.retake')}
          </button>
        )}
        {onManualEntry && (
          <button className="btn btn-secondary" onClick={onManualEntry}>
            ✏️ {t('documents.errors.manualEntry')}
          </button>
        )}
      </div>

      <div className="error-tips">
        <div className="tip-box">
          <strong>💡 {t('documents.errors.tip')}:</strong>{' '}
          {t('documents.errors.tipContent')}
        </div>
      </div>
    </div>
  );
};

export default OCRErrorHandler;
