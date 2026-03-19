import React from 'react';
import { useTranslation } from 'react-i18next';
import { SuggestionCardShell, Row, fmtEur, SuggestionCardProps } from './SuggestionCardBase';

const E1kvSuggestionCard: React.FC<SuggestionCardProps> = (props) => {
  const { t } = useTranslation();
  const d = props.suggestion.data || {};
  const f = (key: string) => t(`documents.suggestion.fields.${key}`, key.replace(/_/g, ' '));
  return (
    <SuggestionCardShell
      icon="📈" title={t('documents.suggestion.importE1kv')}
      {...props} confirmActionKey="tax_data"
      confirmLabel={t('documents.suggestion.confirmTaxData')}
    >
      {d.tax_year && (
        <div className="suggestion-row" style={{ fontWeight: 600, marginBottom: 8 }}>
          <span>{t('documents.suggestion.taxYear')}</span><span>{d.tax_year}</span>
        </div>
      )}
      <div className="suggestion-details">
        {d.kapitalertraege != null && <Row label={f('kapitalertraege')} value={fmtEur(d.kapitalertraege)} />}
        {d.kest_angerechnet != null && <Row label={f('kest_angerechnet')} value={fmtEur(d.kest_angerechnet)} />}
        {d.auslaendische_kapitalertraege != null && <Row label={f('auslaendische_kapitalertraege')} value={fmtEur(d.auslaendische_kapitalertraege)} />}
        {d.krypto_gewinne != null && <Row label={f('krypto_gewinne')} value={fmtEur(d.krypto_gewinne)} />}
        {d.krypto_verluste != null && <Row label={f('krypto_verluste')} value={fmtEur(d.krypto_verluste)} />}
        {d.spekulationsgewinne != null && <Row label={f('spekulationsgewinne')} value={fmtEur(d.spekulationsgewinne)} />}
      </div>
      {d.confidence != null && (
        <div className="suggestion-confidence">
          {t('documents.suggestion.confidence')}: {(Number(d.confidence) * 100).toFixed(0)}%
        </div>
      )}
    </SuggestionCardShell>
  );
};

export default E1kvSuggestionCard;
