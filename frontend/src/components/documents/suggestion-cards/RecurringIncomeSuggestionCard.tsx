import React from 'react';
import { useTranslation } from 'react-i18next';
import { SuggestionCardShell, Row, fmtEur, fmtDate, SuggestionCardProps } from './SuggestionCardBase';

const RecurringIncomeSuggestionCard: React.FC<SuggestionCardProps> = (props) => {
  const { t } = useTranslation();
  const d = props.suggestion.data;
  return (
    <SuggestionCardShell
      icon="🔄" title={t('documents.suggestion.createRecurring')}
      {...props} confirmActionKey={props.confirmActionKey || 'recurring'}
    >
      <div className="suggestion-details">
        <Row label={t('documents.ocr.monthlyRent')} value={fmtEur(d.monthly_rent)} />
        <Row label={t('documents.ocr.startDate')} value={fmtDate(d.start_date)} />
        {d.end_date && <Row label={t('documents.ocr.endDate')} value={fmtDate(d.end_date)} />}
        {d.address && <Row label={t('documents.ocr.propertyAddress')} value={d.address} />}
        {d.matched_property_address && (
          <Row className="suggestion-match" label={t('documents.suggestion.matchedProperty')} value={d.matched_property_address} />
        )}
        {!d.matched_property_id && (
          <div className="suggestion-warning">{t('documents.suggestion.noPropertyMatch')}</div>
        )}
      </div>
      {d.address_mismatch_warning === true && (
        <div style={{
          padding: '10px 14px', margin: '12px 0', background: '#fffbeb',
          border: '1px solid #fcd34d', borderRadius: '8px', color: '#92400e',
          fontSize: '0.85rem', display: 'flex', alignItems: 'flex-start', gap: '8px',
        }}>
          <span style={{ flexShrink: 0 }}>⚠️</span>
          <span>{t('documents.suggestion.addressMismatchWarning')}</span>
        </div>
      )}
    </SuggestionCardShell>
  );
};

export default RecurringIncomeSuggestionCard;
