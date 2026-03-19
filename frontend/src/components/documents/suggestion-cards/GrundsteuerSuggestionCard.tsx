import React from 'react';
import { useTranslation } from 'react-i18next';
import { SuggestionCardShell, Row, fmtEur, SuggestionCardProps } from './SuggestionCardBase';

const GrundsteuerSuggestionCard: React.FC<SuggestionCardProps> = (props) => {
  const { t } = useTranslation();
  const d = props.suggestion.data || {};
  const f = (key: string) => t(`documents.suggestion.fields.${key}`, key.replace(/_/g, ' '));
  return (
    <SuggestionCardShell
      icon="🏡" title={t('documents.suggestion.importGrundsteuer')}
      {...props} confirmActionKey="tax_data"
      confirmLabel={t('documents.suggestion.confirmTaxData')}
    >
      {d.tax_year && (
        <div className="suggestion-row" style={{ fontWeight: 600, marginBottom: 8 }}>
          <span>{t('documents.suggestion.taxYear')}</span><span>{d.tax_year}</span>
        </div>
      )}
      <div className="suggestion-details">
        {d.address && <Row label={f('address')} value={d.address} />}
        {d.einheitswert != null && <Row label={f('einheitswert')} value={fmtEur(d.einheitswert)} />}
        {d.grundsteuer_betrag != null && <Row label={f('grundsteuer_betrag')} value={fmtEur(d.grundsteuer_betrag)} />}
        {d.steuermessbetrag != null && <Row label={f('steuermessbetrag')} value={fmtEur(d.steuermessbetrag)} />}
        {d.hebesatz != null && <Row label={f('hebesatz')} value={`${d.hebesatz}%`} />}
        {d.matched_property_name && (
          <Row className="suggestion-match" label={f('matched_property')} value={d.matched_property_name} />
        )}
      </div>
      {d.confidence != null && (
        <div className="suggestion-confidence">
          {t('documents.suggestion.confidence')}: {(Number(d.confidence) * 100).toFixed(0)}%
        </div>
      )}
    </SuggestionCardShell>
  );
};

export default GrundsteuerSuggestionCard;
