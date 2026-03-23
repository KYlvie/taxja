import React from 'react';
import { useTranslation } from 'react-i18next';
import { SuggestionCardShell, Row, fmtEur, fmtDate, SuggestionCardProps } from './SuggestionCardBase';
import { formatDocumentFieldList } from '../../../utils/documentFieldLabel';

const warningStyle: React.CSSProperties = {
  padding: '10px 14px',
  margin: '12px 0',
  background: '#fffbeb',
  border: '1px solid #fcd34d',
  borderRadius: '8px',
  color: '#92400e',
  fontSize: '0.85rem',
  display: 'flex',
  alignItems: 'flex-start',
  gap: '8px',
};

const LoanSuggestionCard: React.FC<SuggestionCardProps> = (props) => {
  const { t } = useTranslation();
  const d = props.suggestion.data;
  const isStandaloneRepayment = props.suggestion.type === 'create_loan_repayment';
  const missingFields = Array.isArray(d.missing_fields) && d.missing_fields.length > 0 ? d.missing_fields : null;
  const formattedMissingFields = missingFields ? formatDocumentFieldList(missingFields, t) : '';
  const disableConfirm = !isStandaloneRepayment && (Boolean(missingFields) || props.suggestion.status === 'needs_input');
  const confirmLabel = isStandaloneRepayment
    ? t('documents.suggestion.keepLoanContract', 'Keep Contract')
    : undefined;

  return (
    <SuggestionCardShell
      icon="LO"
      title={
        isStandaloneRepayment
          ? t('documents.suggestion.createLoanRepayment', 'Unlinked Loan Contract')
          : t('documents.suggestion.createLoan')
      }
      {...props}
      confirmActionKey={props.confirmActionKey || 'loan'}
      disableConfirm={disableConfirm}
      confirmLabel={confirmLabel}
    >
      <div className="suggestion-details">
        {d.loan_amount != null && <Row label={t('documents.suggestion.loanAmount')} value={fmtEur(d.loan_amount)} />}
        {d.interest_rate != null && (
          <Row label={t('documents.suggestion.interestRate')} value={`${Number(d.interest_rate).toFixed(2)}%`} />
        )}
        {d.monthly_payment != null && (
          <Row label={t('documents.suggestion.monthlyPayment')} value={fmtEur(d.monthly_payment)} />
        )}
        {d.lender_name && <Row label={t('documents.suggestion.lenderName')} value={d.lender_name} />}
        {d.start_date && <Row label={t('documents.suggestion.loanStartDate')} value={fmtDate(d.start_date)} />}
        {d.end_date && <Row label={t('documents.suggestion.loanEndDate')} value={fmtDate(d.end_date)} />}
        {d.matched_property_address && (
          <Row
            className="suggestion-match"
            label={t('documents.suggestion.matchedProperty', 'Matched property')}
            value={d.matched_property_address}
          />
        )}
      </div>

      {!isStandaloneRepayment && (
        <div className="suggestion-deductible-hint">
          <span>i</span>
          <span>
            {t(
              'documents.suggestion.loanInterestHint',
              'This creates a linked property loan and schedules monthly deductible interest, not the full installment.'
            )}
          </span>
        </div>
      )}

      {isStandaloneRepayment && (
        <div className="suggestion-warning">
          {t(
            'documents.suggestion.loanRepaymentStandaloneHint',
            'No property is linked yet. Confirming keeps this loan contract on file without creating an expense or recurring schedule. Link it to a property later to activate the deductible interest flow.'
          )}
        </div>
      )}

      {d.address_mismatch_warning === true && (
        <div style={warningStyle}>
          <span style={{ flexShrink: 0 }}>!</span>
          <span>{t('documents.suggestion.addressMismatchWarning')}</span>
        </div>
      )}

      {missingFields && (
        <div className="suggestion-warning">
          {isStandaloneRepayment
            ? t(
                'documents.suggestion.loanMissingFieldsStandalone',
                `Some OCR fields are still missing (${formattedMissingFields}). That's okay for now because we won't create bookkeeping entries until a property is linked.`
              )
            : t('documents.suggestion.missingFields', { fields: formattedMissingFields })}
        </div>
      )}

      {disableConfirm && (
        <div className="suggestion-warning">
          {t(
            'documents.suggestion.reviewLoanFieldsFirst',
            'Review the extracted loan fields first. We can only create the recurring schedule after the missing OCR values are filled in.'
          )}
        </div>
      )}
    </SuggestionCardShell>
  );
};

export default LoanSuggestionCard;
