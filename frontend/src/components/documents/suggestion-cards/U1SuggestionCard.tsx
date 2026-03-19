import React from 'react';
import { useTranslation } from 'react-i18next';
import { SuggestionCardShell, Row, fmtEur, SuggestionCardProps } from './SuggestionCardBase';

const U1SuggestionCard: React.FC<SuggestionCardProps> = (props) => {
  const { t } = useTranslation();
  const d = props.suggestion.data || {};
  const f = (key: string) => t(`documents.suggestion.fields.${key}`, key.replace(/_/g, ' '));
  return (
    <SuggestionCardShell
      icon="🧾" title={t('documents.suggestion.importU1')}
      {...props} confirmActionKey="tax_data"
      confirmLabel={t('documents.suggestion.confirmTaxData')}
    >
      {d.tax_year && (
        <div className="suggestion-row" style={{ fontWeight: 600, marginBottom: 8 }}>
          <span>{t('documents.suggestion.taxYear')}</span><span>{d.tax_year}</span>
        </div>
      )}
      <div className="suggestion-details">
        {d.gesamtumsatz != null && <Row label={f('gesamtumsatz')} value={fmtEur(d.gesamtumsatz)} />}
        {d.umsatz_20 != null && <Row label={f('umsatz_20')} value={fmtEur(d.umsatz_20)} />}
        {d.umsatz_10 != null && <Row label={f('umsatz_10')} value={fmtEur(d.umsatz_10)} />}
        {d.umsatz_13 != null && <Row label={f('umsatz_13')} value={fmtEur(d.umsatz_13)} />}
        {d.ust_gesamt != null && <Row label={f('ust_gesamt')} value={fmtEur(d.ust_gesamt)} />}
        {d.vorsteuer != null && <Row label={f('vorsteuer')} value={fmtEur(d.vorsteuer)} />}
        {d.zahllast != null && <Row label={f('zahllast')} value={fmtEur(d.zahllast)} />}
      </div>
      {d.confidence != null && (
        <div className="suggestion-confidence">
          {t('documents.suggestion.confidence')}: {(Number(d.confidence) * 100).toFixed(0)}%
        </div>
      )}
    </SuggestionCardShell>
  );
};

export default U1SuggestionCard;
