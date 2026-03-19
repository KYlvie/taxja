import React from 'react';
import { useTranslation } from 'react-i18next';
import { SuggestionCardShell, Row, fmtEur, SuggestionCardProps } from './SuggestionCardBase';

const SvsSuggestionCard: React.FC<SuggestionCardProps> = (props) => {
  const { t } = useTranslation();
  const d = props.suggestion.data || {};
  const f = (key: string) => t(`documents.suggestion.fields.${key}`, key.replace(/_/g, ' '));
  return (
    <SuggestionCardShell
      icon="🏥" title={t('documents.suggestion.importSvs')}
      {...props} confirmActionKey="tax_data"
      confirmLabel={t('documents.suggestion.confirmTaxData')}
    >
      {d.tax_year && (
        <div className="suggestion-row" style={{ fontWeight: 600, marginBottom: 8 }}>
          <span>{t('documents.suggestion.taxYear')}</span><span>{d.tax_year}</span>
        </div>
      )}
      <div className="suggestion-details">
        {d.beitragsgrundlage != null && <Row label={f('beitragsgrundlage')} value={fmtEur(d.beitragsgrundlage)} />}
        {d.krankenversicherung != null && <Row label={f('krankenversicherung')} value={fmtEur(d.krankenversicherung)} />}
        {d.pensionsversicherung != null && <Row label={f('pensionsversicherung')} value={fmtEur(d.pensionsversicherung)} />}
        {d.unfallversicherung != null && <Row label={f('unfallversicherung')} value={fmtEur(d.unfallversicherung)} />}
        {d.selbstaendigenvorsorge != null && <Row label={f('selbstaendigenvorsorge')} value={fmtEur(d.selbstaendigenvorsorge)} />}
        {d.gesamtbeitrag != null && <Row label={f('gesamtbeitrag')} value={fmtEur(d.gesamtbeitrag)} />}
      </div>
      <div className="suggestion-deductible-hint">
        <span>💡</span>
        <span>{t('documents.suggestion.svsDeductibleHint')}</span>
      </div>
      {d.confidence != null && (
        <div className="suggestion-confidence">
          {t('documents.suggestion.confidence')}: {(Number(d.confidence) * 100).toFixed(0)}%
        </div>
      )}
    </SuggestionCardShell>
  );
};

export default SvsSuggestionCard;
