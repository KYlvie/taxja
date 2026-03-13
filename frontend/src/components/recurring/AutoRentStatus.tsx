import React from 'react';
import { useTranslation } from 'react-i18next';

interface AutoRentStatusProps {
  isEnabled: boolean;
  amount?: number;
  nextDate?: string;
  onEdit?: () => void;
  onDisable?: () => void;
}

export const AutoRentStatus: React.FC<AutoRentStatusProps> = ({
  isEnabled,
  amount,
  nextDate,
  onEdit,
  onDisable,
}) => {
  const { t } = useTranslation();

  if (!isEnabled) {
    return null;
  }

  return (
    <div className="bg-green-50 border border-green-200 rounded-lg p-3 flex items-center justify-between">
      <div className="flex items-center gap-2">
        <span className="text-green-600">✓</span>
        <div>
          <p className="text-sm font-medium text-green-900">
            {t('recurring.quickSetup.autoRentEnabled')}
          </p>
          {amount && (
            <p className="text-xs text-green-700">
              €{amount.toFixed(2)}/月
              {nextDate && ` • ${t('recurring.nextGeneration')}: ${new Date(nextDate).toLocaleDateString()}`}
            </p>
          )}
        </div>
      </div>
      <div className="flex gap-2">
        {onEdit && (
          <button
            onClick={onEdit}
            className="text-xs text-green-700 hover:text-green-900 underline"
          >
            {t('common.edit')}
          </button>
        )}
        {onDisable && (
          <button
            onClick={onDisable}
            className="text-xs text-red-600 hover:text-red-800 underline"
          >
            {t('recurring.quickSetup.disable')}
          </button>
        )}
      </div>
    </div>
  );
};
