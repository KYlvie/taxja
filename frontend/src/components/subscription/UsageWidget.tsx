import React, { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useSubscriptionStore } from '../../stores/subscriptionStore';
import { formatDate } from '../../utils/locale';
import './UsageWidget.css';

interface UsageWidgetProps {
  compact?: boolean;
}

const UsageWidget: React.FC<UsageWidgetProps> = ({ compact = false }) => {
  const { t, i18n } = useTranslation();
  const { usage, fetchUsage } = useSubscriptionStore();
  const currentLanguage = i18n.resolvedLanguage || i18n.language;

  useEffect(() => {
    void fetchUsage();

    const interval = setInterval(() => {
      void fetchUsage();
    }, 5 * 60 * 1000);

    return () => clearInterval(interval);
  }, [fetchUsage]);

  if (!usage) {
    return null;
  }

  const getColorClass = (data: any) => {
    if (data.is_exceeded) {
      return 'exceeded';
    }

    if (data.is_warning) {
      return 'warning';
    }

    return 'normal';
  };

  const resourceLabels: Record<string, string> = {
    transactions: t('usage.transactions', 'Transactions'),
    ocr_scans: t('usage.ocr_scans', 'Document Scans'),
    ai_conversations: t('usage.ai_conversations', 'AI Conversations'),
  };

  if (compact) {
    return (
      <div className="usage-widget compact">
        {Object.entries(usage).map(([key, data]) => (
          <div key={key} className="usage-item-compact">
            <div className="usage-bar-compact">
              <div
                className={`usage-fill ${getColorClass(data)}`}
                style={{ width: `${Math.min(data.percentage, 100)}%` }}
              />
            </div>
            <span className="usage-label-compact">{resourceLabels[key]}</span>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="usage-widget">
      <div className="widget-header">
        <h3>{t('usage.title', 'Resource Usage')}</h3>
        <span className="reset-info">
          {t('usage.resets_on', 'Resets: {{date}}', {
            date: formatDate(Object.values(usage)[0].reset_date, currentLanguage),
          })}
        </span>
      </div>

      <div className="usage-list">
        {Object.entries(usage).map(([key, data]) => (
          <div key={key} className="usage-row">
            <div className="usage-header-row">
              <span className="resource-name">{resourceLabels[key]}</span>
              <span className={`usage-value ${getColorClass(data)}`}>
                {data.limit === -1
                  ? t('usage.unlimited', 'Unlimited')
                  : `${data.current} / ${data.limit}`}
              </span>
            </div>

            <div className="progress-bar">
              <div
                className={`progress-fill ${getColorClass(data)}`}
                style={{ width: `${Math.min(data.percentage, 100)}%` }}
              />
            </div>

            {data.is_exceeded && (
              <div className="usage-alert exceeded">
                {t('usage.quota_exceeded', 'Quota exceeded')}
              </div>
            )}

            {data.is_warning && !data.is_exceeded && (
              <div className="usage-alert warning">
                {t('usage.quota_warning', 'Approaching limit ({{percent}}%)', {
                  percent: Math.round(data.percentage),
                })}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default UsageWidget;
