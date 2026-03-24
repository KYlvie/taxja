import React from 'react';
import { useTranslation } from 'react-i18next';
import { SuggestionCardShell, Row, fmtEur, SuggestionCardProps } from './SuggestionCardBase';
import { formatDocumentFieldLabel } from '../../../utils/documentFieldLabel';

const formatSuggestionValue = (value: unknown, t: ReturnType<typeof useTranslation>['t']) => {
  if (typeof value === 'number') {
    return fmtEur(value);
  }

  if (typeof value === 'boolean') {
    return value ? t('common.yes') : t('common.no');
  }

  return String(value ?? '-');
};

/** Fallback card for unknown tax form suggestion types - renders all fields generically. */
const GenericTaxFormCard: React.FC<SuggestionCardProps> = (props) => {
  const { t } = useTranslation();
  const d = props.suggestion.data || {};
  const entries = Object.entries(d).filter(
    ([key]) => !['type', 'status', 'confidence', 'raw_fields'].includes(key),
  );
  const hasLoss = d.gewinn_verlust != null && Number(d.gewinn_verlust) < 0;

  return (
    <SuggestionCardShell
      icon="TF"
      title={t('documents.suggestion.confirmTaxData')}
      {...props}
      confirmActionKey="tax_data"
      confirmLabel={t('documents.suggestion.confirmTaxData')}
    >
      {d.tax_year && (
        <div className="suggestion-row" style={{ fontWeight: 600, marginBottom: 8 }}>
          <span>{t('documents.suggestion.taxYear')}</span>
          <span>{d.tax_year}</span>
        </div>
      )}

      <div className="suggestion-details">
        {entries.map(([key, value]) => {
          if (key === 'tax_year' || value == null || value === '' || typeof value === 'object') {
            return null;
          }

          return (
            <Row
              key={key}
              label={formatDocumentFieldLabel(key, t)}
              value={formatSuggestionValue(value, t)}
            />
          );
        })}

        {entries
          .filter(([, value]) => typeof value === 'object' && !Array.isArray(value) && value != null)
          .map(([key, value]) => (
            <div key={key} className="suggestion-nested-block">
              <div className="suggestion-nested-title">{formatDocumentFieldLabel(key, t)}</div>
              {Object.entries(value as Record<string, unknown>).map(([subKey, subValue]) => (
                <Row
                  key={subKey}
                  label={formatDocumentFieldLabel(subKey, t)}
                  value={formatSuggestionValue(subValue, t)}
                />
              ))}
            </div>
          ))}

        {entries
          .filter(([, value]) => Array.isArray(value))
          .map(([key, value]) => (
            <div key={key} style={{ marginTop: 8 }}>
              <div className="suggestion-nested-title">{formatDocumentFieldLabel(key, t)}</div>
              {(value as unknown[]).slice(0, 10).map((item, index) => (
                <div key={index} className="suggestion-array-item">
                  {typeof item === 'object' && item != null ? (
                    Object.entries(item as Record<string, unknown>).map(([itemKey, itemValue]) => (
                      <Row
                        key={itemKey}
                        label={formatDocumentFieldLabel(itemKey, t)}
                        value={formatSuggestionValue(itemValue, t)}
                      />
                    ))
                  ) : (
                    <span style={{ fontSize: '0.85rem' }}>{String(item)}</span>
                  )}
                </div>
              ))}
              {(value as unknown[]).length > 10 && (
                <div style={{ fontSize: '0.8rem', color: '#6b7280', padding: '4px 12px' }}>
                  ...{t('documents.suggestion.andMore', { count: (value as unknown[]).length - 10 })}
                </div>
              )}
            </div>
          ))}
      </div>

      {hasLoss && (
        <div className="suggestion-loss-banner">
          <span>!</span>
          <span>{t('documents.suggestion.lossDetected')}</span>
        </div>
      )}

      {d.confidence != null && (
        <div className="suggestion-confidence">
          {t('documents.suggestion.confidence')}: {(Number(d.confidence) * 100).toFixed(0)}%
        </div>
      )}
    </SuggestionCardShell>
  );
};

export default GenericTaxFormCard;
