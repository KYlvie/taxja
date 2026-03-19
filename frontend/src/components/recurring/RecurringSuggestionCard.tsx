import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useConfirm } from '../../hooks/useConfirm';

interface RecurringSuggestionCardProps {
  description: string;
  amount: number;
  frequency: string;
  occurrences: number;
  confidence: number;
  suggestedDayOfMonth: number;
  transactionType: string;
  category: string;
  propertyId?: string;
  onAccept: () => Promise<void>;
  onDismiss: () => void;
}

export const RecurringSuggestionCard: React.FC<RecurringSuggestionCardProps> = ({
  description,
  amount,
  frequency,
  occurrences,
  confidence,
  suggestedDayOfMonth,
  transactionType,
  category: _category,
  propertyId: _propertyId,
  onAccept,
  onDismiss,
}) => {
  const { t } = useTranslation();
  const { alert: showAlert } = useConfirm();
  const [loading, setLoading] = useState(false);

  const handleAccept = async () => {
    try {
      setLoading(true);
      await onAccept();
    } catch (error) {
      console.error('Failed to accept suggestion:', error);
      await showAlert(t('recurring.suggestions.acceptFailed'), { variant: 'danger' });
    } finally {
      setLoading(false);
    }
  };

  const getFrequencyText = () => {
    switch (frequency) {
      case 'monthly':
        return t('recurring.frequency.monthly');
      case 'quarterly':
        return t('recurring.frequency.quarterly');
      case 'annually':
        return t('recurring.frequency.annually');
      case 'weekly':
        return t('recurring.frequency.weekly');
      case 'biweekly':
        return t('recurring.frequency.biweekly');
      default:
        return frequency;
    }
  };

  const getConfidenceColor = () => {
    if (confidence >= 0.9) return 'text-green-600';
    if (confidence >= 0.75) return 'text-blue-600';
    return 'text-yellow-600';
  };

  const getConfidenceIcon = () => {
    if (confidence >= 0.9) return '\u2713\u2713\u2713';
    if (confidence >= 0.75) return '\u2713\u2713';
    return '\u2713';
  };

  return (
    <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border-2 border-blue-200 rounded-lg p-4 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="text-3xl">{'\uD83D\uDCA1'}</div>

        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <h3 className="font-semibold text-blue-900">{t('recurring.suggestions.smartSuggestion')}</h3>
            <span className={`text-xs font-medium ${getConfidenceColor()}`}>
              {getConfidenceIcon()} {Math.round(confidence * 100)}%
            </span>
          </div>

          <p className="text-sm text-blue-800 mb-3">
            {t('recurring.suggestions.detectedPattern', {
              occurrences,
              description,
              amount: amount.toFixed(2),
              frequency: getFrequencyText().toLowerCase(),
            })}
          </p>

          <div className="bg-white rounded p-3 mb-3 text-sm">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <span className="text-gray-600">{t('recurring.form.amount')}:</span>
                <span className="ml-2 font-medium">{`\u20AC${amount.toFixed(2)}`}</span>
              </div>
              <div>
                <span className="text-gray-600">{t('recurring.frequency.label')}:</span>
                <span className="ml-2 font-medium">{getFrequencyText()}</span>
              </div>
              <div>
                <span className="text-gray-600">{t('recurring.suggestions.dayOfMonth')}:</span>
                <span className="ml-2 font-medium">{`${suggestedDayOfMonth}.`}</span>
              </div>
              <div>
                <span className="text-gray-600">{t('recurring.suggestions.type')}:</span>
                <span className="ml-2 font-medium">
                  {transactionType === 'income' ? t('recurring.type.income') : t('recurring.type.expense')}
                </span>
              </div>
            </div>
          </div>

          <div className="flex gap-2">
            <button
              onClick={onDismiss}
              className="px-4 py-2 text-sm text-gray-600 hover:bg-white rounded transition-colors"
              disabled={loading}
            >
              {t('recurring.suggestions.notNow')}
            </button>
            <button
              onClick={() => void handleAccept()}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors flex items-center gap-2"
              disabled={loading}
            >
              {loading ? (
                <>
                  <span className="animate-spin">{'\u23F3'}</span>
                  {t('common.saving')}
                </>
              ) : (
                <>
                  <span>{'\uD83E\uDD16'}</span>
                  {t('recurring.suggestions.enableAuto')}
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
