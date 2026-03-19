import React from 'react';
import { useTranslation } from 'react-i18next';
import { SuggestionCardShell, Row, fmtEur, SuggestionCardProps } from './SuggestionCardBase';

const LohnzettelSuggestionCard: React.FC<SuggestionCardProps> = (props) => {
  const { t } = useTranslation();
  const d = props.suggestion.data || {};
  const f = (key: string) => t(`documents.suggestion.fields.${key}`, key.replace(/_/g, ' '));
  return (
    <SuggestionCardShell
      icon="📋" title={t('documents.suggestion.importLohnzettel')}
      {...props} confirmActionKey="tax_data"
      confirmLabel={t('documents.suggestion.confirmTaxData')}
    >
      {d.tax_year && (
        <div className="suggestion-row" style={{ fontWeight: 600, marginBottom: 8 }}>
          <span>{t('documents.suggestion.taxYear')}</span><span>{d.tax_year}</span>
        </div>
      )}
      <div className="suggestion-details">
        {d.employer_name && <Row label={f('employer_name')} value={d.employer_name} />}
        {d.employee_name && <Row label={f('employee_name')} value={d.employee_name} />}
        {d.sv_nummer && <Row label={f('sv_nummer')} value={d.sv_nummer} />}
        {/* Income group */}
        {d.kz_210 != null && <Row label={f('kz_210')} value={fmtEur(d.kz_210)} />}
        {d.kz_215 != null && <Row label={f('kz_215')} value={fmtEur(d.kz_215)} />}
        {d.kz_220 != null && <Row label={f('kz_220')} value={fmtEur(d.kz_220)} />}
        {d.kz_245 != null && <Row label={f('kz_245')} value={fmtEur(d.kz_245)} />}
        {/* Deductions group */}
        {d.kz_230 != null && <Row label={f('kz_230')} value={fmtEur(d.kz_230)} />}
        {d.kz_260 != null && <Row label={f('kz_260')} value={fmtEur(d.kz_260)} />}
        {d.kz_718 != null && <Row label={f('kz_718')} value={fmtEur(d.kz_718)} />}
        {d.kz_719 != null && <Row label={f('kz_719')} value={fmtEur(d.kz_719)} />}
        {d.familienbonus != null && <Row label={f('familienbonus')} value={fmtEur(d.familienbonus)} />}
        {d.telearbeitspauschale != null && <Row label={f('telearbeitspauschale')} value={fmtEur(d.telearbeitspauschale)} />}
      </div>
      {d.confidence != null && (
        <div className="suggestion-confidence">
          {t('documents.suggestion.confidence')}: {(Number(d.confidence) * 100).toFixed(0)}%
        </div>
      )}
    </SuggestionCardShell>
  );
};

export default LohnzettelSuggestionCard;
