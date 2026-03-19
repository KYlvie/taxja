import React from 'react';
import { useTranslation } from 'react-i18next';
import { SuggestionCardShell, Row, fmtEur, fmtDate, SuggestionCardProps } from './SuggestionCardBase';

const LoanSuggestionCard: React.FC<SuggestionCardProps> = (props) => {
  const { t } = useTranslation();
  const d = props.suggestion.data;
  const missingFields = Array.isArray(d.missing_fields) && d.missing_fields.length > 0 ? d.missing_fields : null;
  return (
    <SuggestionCardShell
      icon="🏦" title={t('documents.suggestion.createLoan')}
      {...props} confirmActionKey={props.confirmActionKey || 'loan'}
    >
      <div className="suggestion-details">
        {d.loan_amount != null && <Row label={t('documents.suggestion.loanAmount')} value={fmtEur(d.loan_amount)} />}
        {d.interest_rate != null && <Row label={t('documents.suggestion.interestRate')} value={`${Number(d.interest_rate).toFixed(2)}%`} />}
        {d.monthly_payment != null && <Row label={t('documents.suggestion.monthlyPayment')} value={fmtEur(d.monthly_payment)} />}
        {d.lender_name && <Row label={t('documents.suggestion.lenderName')} value={d.lender_name} />}
        {d.start_date && <Row label={t('documents.suggestion.loanStartDate')} value={fmtDate(d.start_date)} />}
        {d.end_date && <Row label={t('documents.suggestion.loanEndDate')} value={fmtDate(d.end_date)} />}
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
      {missingFields && (
        <div className="suggestion-warning">
          {t('documents.suggestion.missingFields', { fields: missingFields.join(', ') })}
        </div>
      )}
    </SuggestionCardShell>
  );
};

export default LoanSuggestionCard;
