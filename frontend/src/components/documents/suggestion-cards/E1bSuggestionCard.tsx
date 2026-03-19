import React from 'react';
import { useTranslation } from 'react-i18next';
import { SuggestionCardShell, Row, fmtEur, SuggestionCardProps } from './SuggestionCardBase';

const E1bSuggestionCard: React.FC<SuggestionCardProps> = (props) => {
  const { t } = useTranslation();
  const d = props.suggestion.data || {};
  const f = (key: string) => t(`documents.suggestion.fields.${key}`, key.replace(/_/g, ' '));
  return (
    <SuggestionCardShell
      icon="🏘️" title={t('documents.suggestion.importE1b')}
      {...props} confirmActionKey="tax_data"
      confirmLabel={t('documents.suggestion.confirmTaxData')}
    >
      {d.tax_year && (
        <div className="suggestion-row" style={{ fontWeight: 600, marginBottom: 8 }}>
          <span>{t('documents.suggestion.taxYear')}</span><span>{d.tax_year}</span>
        </div>
      )}
      <div className="suggestion-details">
        {d.mieteinnahmen_gesamt != null && <Row label={f('mieteinnahmen_gesamt')} value={fmtEur(d.mieteinnahmen_gesamt)} />}
        {d.werbungskosten_gesamt != null && <Row label={f('werbungskosten_gesamt')} value={fmtEur(d.werbungskosten_gesamt)} />}
        {d.einkuenfte_vv != null && <Row label={f('einkuenfte_vv')} value={fmtEur(d.einkuenfte_vv)} />}
      </div>
      {/* Properties list */}
      {Array.isArray(d.properties) && d.properties.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <div className="suggestion-nested-title">{f('properties')} ({d.properties.length})</div>
          {d.properties.map((prop: any, idx: number) => (
            <div key={idx} className="suggestion-nested-block" style={{ marginBottom: 4 }}>
              {prop.address && <Row label={f('address')} value={prop.address} />}
              {prop.matched_property_name && (
                <Row className="suggestion-match" label={f('matched_property')} value={prop.matched_property_name} />
              )}
              {prop.mieteinnahmen != null && <Row label={f('mieteinnahmen')} value={fmtEur(prop.mieteinnahmen)} />}
              {prop.werbungskosten != null && <Row label={f('werbungskosten')} value={fmtEur(prop.werbungskosten)} />}
              {prop.afa != null && <Row label={f('afa')} value={fmtEur(prop.afa)} />}
            </div>
          ))}
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

export default E1bSuggestionCard;
