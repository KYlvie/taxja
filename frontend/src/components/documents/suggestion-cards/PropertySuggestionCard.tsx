import React from 'react';
import { useTranslation } from 'react-i18next';
import { SuggestionCardShell, Row, fmtEur, fmtDate, SuggestionCardProps } from './SuggestionCardBase';

const PropertySuggestionCard: React.FC<SuggestionCardProps> = (props) => {
  const { t } = useTranslation();
  const d = props.suggestion.data;
  return (
    <SuggestionCardShell
      icon="🏠" title={t('documents.suggestion.createProperty')}
      {...props} confirmActionKey={props.confirmActionKey || 'property'}
    >
      <div className="suggestion-details">
        <Row label={t('documents.ocr.propertyAddress')} value={d.address} />
        <Row label={t('documents.ocr.purchasePrice')} value={fmtEur(d.purchase_price)} />
        <Row label={t('documents.ocr.purchaseDate')} value={fmtDate(d.purchase_date)} />
        <Row label={t('documents.ocr.buildingValue')} value={fmtEur(d.building_value)} />
        {d.grunderwerbsteuer && <Row label={t('documents.ocr.transferTax')} value={fmtEur(d.grunderwerbsteuer)} />}
      </div>
      {d.address_mismatch_warning === true && (
        <div className="suggestion-address-mismatch" style={{
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

export default PropertySuggestionCard;
