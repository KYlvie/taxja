import React from 'react';
import { useTranslation } from 'react-i18next';
import { SuggestionCardShell, Row, fmtEur, SuggestionCardProps } from './SuggestionCardBase';

const E1aSuggestionCard: React.FC<SuggestionCardProps> = (props) => {
  const { t } = useTranslation();
  const d = props.suggestion.data || {};
  const f = (key: string) => t(`documents.suggestion.fields.${key}`, key.replace(/_/g, ' '));
  const hasLoss = d.gewinn_verlust != null && Number(d.gewinn_verlust) < 0;
  return (
    <SuggestionCardShell
      icon="💼" title={t('documents.suggestion.importE1a')}
      {...props} confirmActionKey="tax_data"
      confirmLabel={t('documents.suggestion.confirmTaxData')}
    >
      {d.tax_year && (
        <div className="suggestion-row" style={{ fontWeight: 600, marginBottom: 8 }}>
          <span>{t('documents.suggestion.taxYear')}</span><span>{d.tax_year}</span>
        </div>
      )}
      <div className="suggestion-details">
        {d.betriebseinnahmen != null && <Row label={f('betriebseinnahmen')} value={fmtEur(d.betriebseinnahmen)} />}
        {d.betriebsausgaben != null && <Row label={f('betriebsausgaben')} value={fmtEur(d.betriebsausgaben)} />}
        {d.gewinn_verlust != null && <Row label={f('gewinn_verlust')} value={fmtEur(d.gewinn_verlust)} />}
        {d.svs_beitraege != null && <Row label={f('svs_beitraege')} value={fmtEur(d.svs_beitraege)} />}
        {d.gewinnfreibetrag != null && <Row label={f('gewinnfreibetrag')} value={fmtEur(d.gewinnfreibetrag)} />}
        {d.afa_gesamt != null && <Row label={f('afa_gesamt')} value={fmtEur(d.afa_gesamt)} />}
      </div>
      {hasLoss && (
        <div className="suggestion-loss-banner">
          <span>📉</span>
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

export default E1aSuggestionCard;
