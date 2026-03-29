import React from 'react';
import { useTranslation } from 'react-i18next';
import { SuggestionCardShell, Row, fmtEur, fmtDate, SuggestionCardProps } from './SuggestionCardBase';

const RentAdjustmentSuggestionCard: React.FC<SuggestionCardProps> = (props) => {
  const { t } = useTranslation();
  const d = props.suggestion.data;

  const pctDisplay = d.adjustment_percentage != null
    ? `${Number(d.adjustment_percentage).toFixed(1)}%`
    : null;

  return (
    <SuggestionCardShell
      icon="📈" title={t('documents.suggestion.updateRecurringRent')}
      {...props} confirmActionKey={props.confirmActionKey || 'rent_adjustment'}
    >
      <div className="suggestion-details">
        {/* Rent change: old → new */}
        {d.current_monthly_rent != null && d.new_monthly_rent != null && (
          <Row
            label={t('documents.suggestion.rentChange')}
            value={
              <span>
                {fmtEur(d.current_monthly_rent)}
                <span style={{ margin: '0 6px', opacity: 0.6 }}>→</span>
                <strong>{fmtEur(d.new_monthly_rent)}</strong>
                {pctDisplay && (
                  <span style={{ marginLeft: 6, color: '#dc2626', fontSize: '0.85em' }}>
                    (+{pctDisplay})
                  </span>
                )}
              </span>
            }
          />
        )}
        {d.current_monthly_rent == null && d.new_monthly_rent != null && (
          <Row label={t('documents.suggestion.newRent')} value={<strong>{fmtEur(d.new_monthly_rent)}</strong>} />
        )}
        {d.effective_date && (
          <Row label={t('documents.suggestion.effectiveDate')} value={fmtDate(d.effective_date)} />
        )}
        {d.adjustment_reason && (
          <Row label={t('documents.suggestion.adjustmentReason')} value={d.adjustment_reason} />
        )}
        {d.address && (
          <Row label={t('documents.ocr.propertyAddress')} value={d.address} />
        )}
        {d.matched_property_name && (
          <Row className="suggestion-match" label={t('documents.suggestion.matchedProperty')} value={d.matched_property_name} />
        )}
        {d.matched_recurring_amount != null && (
          <Row
            className="suggestion-match"
            label={t('documents.suggestion.currentRecurringAmount')}
            value={fmtEur(d.matched_recurring_amount)}
          />
        )}

        {/* BK adjustments */}
        {d.current_betriebskosten != null && d.new_betriebskosten != null && (
          <Row
            label={t('documents.suggestion.bkChange')}
            value={
              <span>
                {fmtEur(d.current_betriebskosten)}
                <span style={{ margin: '0 6px', opacity: 0.6 }}>→</span>
                {fmtEur(d.new_betriebskosten)}
              </span>
            }
          />
        )}
      </div>

      {/* Warnings */}
      {d.no_property_match && (
        <div className="suggestion-warning">{t('documents.suggestion.noPropertyMatch')}</div>
      )}
      {d.no_recurring_match && !d.no_property_match && (
        <div className="suggestion-warning">{t('documents.suggestion.noRecurringMatch')}</div>
      )}
    </SuggestionCardShell>
  );
};

export default RentAdjustmentSuggestionCard;
