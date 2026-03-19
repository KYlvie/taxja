import React from 'react';
import { useTranslation } from 'react-i18next';
import { SuggestionCardShell, Row, fmtEur, SuggestionCardProps } from './SuggestionCardBase';

/** Fallback card for unknown tax form suggestion types — renders all fields generically */
const GenericTaxFormCard: React.FC<SuggestionCardProps> = (props) => {
  const { t } = useTranslation();
  const d = props.suggestion.data || {};
  const entries = Object.entries(d).filter(
    ([k]) => !['type', 'status', 'confidence', 'raw_fields'].includes(k)
  );
  const hasLoss = d.gewinn_verlust != null && Number(d.gewinn_verlust) < 0;
  return (
    <SuggestionCardShell
      icon="📄" title={t('documents.suggestion.confirmTaxData')}
      {...props} confirmActionKey="tax_data"
      confirmLabel={t('documents.suggestion.confirmTaxData')}
    >
      {d.tax_year && (
        <div className="suggestion-row" style={{ fontWeight: 600, marginBottom: 8 }}>
          <span>{t('documents.suggestion.taxYear')}</span><span>{d.tax_year}</span>
        </div>
      )}
      <div className="suggestion-details">
        {entries.map(([key, val]) => {
          if (key === 'tax_year' || val == null || val === '' || typeof val === 'object') return null;
          const label = t(`documents.suggestion.fields.${key}`, key.replace(/_/g, ' '));
          const display = typeof val === 'number'
            ? fmtEur(val)
            : typeof val === 'boolean'
              ? (val ? '✅' : '—')
              : String(val);
          return <Row key={key} label={label} value={display} />;
        })}
        {/* Nested objects */}
        {entries.filter(([, val]) => typeof val === 'object' && !Array.isArray(val) && val != null).map(([key, val]) => (
          <div key={key} className="suggestion-nested-block">
            <div className="suggestion-nested-title">{t(`documents.suggestion.fields.${key}`, key.replace(/_/g, ' '))}</div>
            {Object.entries(val as Record<string, any>).map(([sk, sv]) => (
              <Row key={sk} label={t(`documents.suggestion.fields.${sk}`, sk.replace(/_/g, ' '))}
                value={typeof sv === 'number' ? fmtEur(sv) : String(sv ?? '—')} />
            ))}
          </div>
        ))}
        {/* Arrays */}
        {entries.filter(([, val]) => Array.isArray(val)).map(([key, val]) => (
          <div key={key} style={{ marginTop: 8 }}>
            <div className="suggestion-nested-title">{t(`documents.suggestion.fields.${key}`, key.replace(/_/g, ' '))}</div>
            {(val as any[]).slice(0, 10).map((item, idx) => (
              <div key={idx} className="suggestion-array-item">
                {typeof item === 'object' && item != null
                  ? Object.entries(item).map(([ik, iv]) => (
                      <Row key={ik} label={t(`documents.suggestion.fields.${ik}`, ik.replace(/_/g, ' '))}
                        value={typeof iv === 'number' ? fmtEur(iv) : String(iv ?? '—')} />
                    ))
                  : <span style={{ fontSize: '0.85rem' }}>{String(item)}</span>
                }
              </div>
            ))}
            {(val as any[]).length > 10 && (
              <div style={{ fontSize: '0.8rem', color: '#6b7280', padding: '4px 12px' }}>
                ...{t('documents.suggestion.andMore', { count: (val as any[]).length - 10 })}
              </div>
            )}
          </div>
        ))}
      </div>
      {hasLoss && (
        <div className="suggestion-loss-banner">
          <span>📉</span><span>{t('documents.suggestion.lossDetected')}</span>
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
