import React from 'react';
import { useTranslation } from 'react-i18next';
import { SuggestionCardShell, Row, fmtEur, SuggestionCardProps } from './SuggestionCardBase';

const L1abSuggestionCard: React.FC<SuggestionCardProps> = (props) => {
  const { t } = useTranslation();
  const d = props.suggestion.data || {};
  const f = (key: string) => t(`documents.suggestion.fields.${key}`, key.replace(/_/g, ' '));
  return (
    <SuggestionCardShell
      icon="💰" title={t('documents.suggestion.importL1ab')}
      {...props} confirmActionKey="tax_data"
      confirmLabel={t('documents.suggestion.confirmTaxData')}
    >
      {d.tax_year && (
        <div className="suggestion-row" style={{ fontWeight: 600, marginBottom: 8 }}>
          <span>{t('documents.suggestion.taxYear')}</span><span>{d.tax_year}</span>
        </div>
      )}
      <div className="suggestion-details">
        {d.alleinverdienerabsetzbetrag != null && <Row label={f('alleinverdienerabsetzbetrag')} value={fmtEur(d.alleinverdienerabsetzbetrag)} />}
        {d.alleinerzieherabsetzbetrag != null && <Row label={f('alleinerzieherabsetzbetrag')} value={fmtEur(d.alleinerzieherabsetzbetrag)} />}
        {d.pendlerpauschale != null && <Row label={f('pendlerpauschale')} value={fmtEur(d.pendlerpauschale)} />}
        {d.pendlereuro != null && <Row label={f('pendlereuro')} value={fmtEur(d.pendlereuro)} />}
        {d.distance_km != null && <Row label={f('distance_km')} value={`${d.distance_km} km`} />}
        {d.public_transport_available != null && <Row label={f('public_transport_available')} value={d.public_transport_available ? '✅' : '—'} />}
      </div>
      {d.confidence != null && (
        <div className="suggestion-confidence">
          {t('documents.suggestion.confidence')}: {(Number(d.confidence) * 100).toFixed(0)}%
        </div>
      )}
    </SuggestionCardShell>
  );
};

export default L1abSuggestionCard;
