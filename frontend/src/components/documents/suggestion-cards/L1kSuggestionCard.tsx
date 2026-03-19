import React from 'react';
import { useTranslation } from 'react-i18next';
import { SuggestionCardShell, Row, fmtEur, SuggestionCardProps } from './SuggestionCardBase';

const L1kSuggestionCard: React.FC<SuggestionCardProps> = (props) => {
  const { t } = useTranslation();
  const d = props.suggestion.data || {};
  const f = (key: string) => t(`documents.suggestion.fields.${key}`, key.replace(/_/g, ' '));
  return (
    <SuggestionCardShell
      icon="👶" title={t('documents.suggestion.importL1k')}
      {...props} confirmActionKey="tax_data"
      confirmLabel={t('documents.suggestion.confirmTaxData')}
    >
      {d.tax_year && (
        <div className="suggestion-row" style={{ fontWeight: 600, marginBottom: 8 }}>
          <span>{t('documents.suggestion.taxYear')}</span><span>{d.tax_year}</span>
        </div>
      )}
      <div className="suggestion-details">
        {d.familienbonus_total != null && <Row label={f('familienbonus_total')} value={fmtEur(d.familienbonus_total)} />}
        {d.kindermehrbetrag != null && <Row label={f('kindermehrbetrag')} value={fmtEur(d.kindermehrbetrag)} />}
        {d.unterhaltsabsetzbetrag != null && <Row label={f('unterhaltsabsetzbetrag')} value={fmtEur(d.unterhaltsabsetzbetrag)} />}
      </div>
      {/* Children list */}
      {Array.isArray(d.children) && d.children.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <div className="suggestion-nested-title">{f('children')} ({d.children.length})</div>
          {d.children.map((child: any, idx: number) => (
            <div key={idx} className="suggestion-array-item">
              {child.name && <Row label={f('child_name')} value={child.name} />}
              {child.birthdate && <Row label={f('birthdate')} value={child.birthdate} />}
              {child.familienbonus != null && <Row label={f('familienbonus')} value={fmtEur(child.familienbonus)} />}
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

export default L1kSuggestionCard;
