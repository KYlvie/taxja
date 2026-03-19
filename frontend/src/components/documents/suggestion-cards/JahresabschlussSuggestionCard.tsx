import React from 'react';
import { useTranslation } from 'react-i18next';
import { SuggestionCardShell, Row, fmtEur, SuggestionCardProps } from './SuggestionCardBase';

const JahresabschlussSuggestionCard: React.FC<SuggestionCardProps> = (props) => {
  const { t } = useTranslation();
  const d = props.suggestion.data || {};
  const f = (key: string) => t(`documents.suggestion.fields.${key}`, key.replace(/_/g, ' '));
  const hasLoss = d.gewinn_verlust != null && Number(d.gewinn_verlust) < 0;
  return (
    <SuggestionCardShell
      icon="📊" title={t('documents.suggestion.importJahresabschluss')}
      {...props} confirmActionKey="tax_data"
      confirmLabel={t('documents.suggestion.confirmTaxData')}
    >
      {d.tax_year && (
        <div className="suggestion-row" style={{ fontWeight: 600, marginBottom: 8 }}>
          <span>{t('documents.suggestion.taxYear')}</span><span>{d.tax_year}</span>
        </div>
      )}
      <div className="suggestion-details">
        {d.einnahmen_gesamt != null && <Row label={f('einnahmen_gesamt')} value={fmtEur(d.einnahmen_gesamt)} />}
        {d.ausgaben_gesamt != null && <Row label={f('ausgaben_gesamt')} value={fmtEur(d.ausgaben_gesamt)} />}
        {d.gewinn_verlust != null && <Row label={f('gewinn_verlust')} value={fmtEur(d.gewinn_verlust)} />}
        {d.afa_gesamt != null && <Row label={f('afa_gesamt')} value={fmtEur(d.afa_gesamt)} />}
        {d.personalkosten != null && <Row label={f('personalkosten')} value={fmtEur(d.personalkosten)} />}
        {d.mietaufwand != null && <Row label={f('mietaufwand')} value={fmtEur(d.mietaufwand)} />}
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

export default JahresabschlussSuggestionCard;
