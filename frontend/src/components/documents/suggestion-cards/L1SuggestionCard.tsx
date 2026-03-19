import React from 'react';
import { useTranslation } from 'react-i18next';
import { SuggestionCardShell, Row, fmtEur, SuggestionCardProps } from './SuggestionCardBase';

const L1SuggestionCard: React.FC<SuggestionCardProps> = (props) => {
  const { t } = useTranslation();
  const d = props.suggestion.data || {};
  const f = (key: string) => t(`documents.suggestion.fields.${key}`, key.replace(/_/g, ' '));
  return (
    <SuggestionCardShell
      icon="📝" title={t('documents.suggestion.importL1')}
      {...props} confirmActionKey="tax_data"
      confirmLabel={t('documents.suggestion.confirmTaxData')}
    >
      {d.tax_year && (
        <div className="suggestion-row" style={{ fontWeight: 600, marginBottom: 8 }}>
          <span>{t('documents.suggestion.taxYear')}</span><span>{d.tax_year}</span>
        </div>
      )}
      <div className="suggestion-details">
        {d.taxpayer_name && <Row label={f('taxpayer_name')} value={d.taxpayer_name} />}
        {d.steuernummer && <Row label={f('steuernummer')} value={d.steuernummer} />}
        {/* Werbungskosten */}
        {d.kz_717 != null && <Row label={f('kz_717')} value={fmtEur(d.kz_717)} />}
        {d.kz_718 != null && <Row label={f('kz_718')} value={fmtEur(d.kz_718)} />}
        {d.kz_719 != null && <Row label={f('kz_719')} value={fmtEur(d.kz_719)} />}
        {d.kz_720 != null && <Row label={f('kz_720')} value={fmtEur(d.kz_720)} />}
        {d.kz_721 != null && <Row label={f('kz_721')} value={fmtEur(d.kz_721)} />}
        {d.kz_722 != null && <Row label={f('kz_722')} value={fmtEur(d.kz_722)} />}
        {d.kz_724 != null && <Row label={f('kz_724')} value={fmtEur(d.kz_724)} />}
        {/* Sonderausgaben */}
        {d.kz_450 != null && <Row label={f('kz_450')} value={fmtEur(d.kz_450)} />}
        {d.kz_458 != null && <Row label={f('kz_458')} value={fmtEur(d.kz_458)} />}
        {d.kz_459 != null && <Row label={f('kz_459')} value={fmtEur(d.kz_459)} />}
        {/* Außergewöhnliche Belastungen */}
        {d.kz_730 != null && <Row label={f('kz_730')} value={fmtEur(d.kz_730)} />}
        {d.kz_740 != null && <Row label={f('kz_740')} value={fmtEur(d.kz_740)} />}
      </div>
      {d.confidence != null && (
        <div className="suggestion-confidence">
          {t('documents.suggestion.confidence')}: {(Number(d.confidence) * 100).toFixed(0)}%
        </div>
      )}
    </SuggestionCardShell>
  );
};

export default L1SuggestionCard;
