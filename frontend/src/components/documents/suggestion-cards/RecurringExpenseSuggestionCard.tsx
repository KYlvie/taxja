import React from 'react';
import { useTranslation } from 'react-i18next';
import { SuggestionCardShell, Row, fmtEur, fmtDate, SuggestionCardProps } from './SuggestionCardBase';

const RecurringExpenseSuggestionCard: React.FC<SuggestionCardProps> = (props) => {
  const { t } = useTranslation();
  const d = props.suggestion.data;
  return (
    <SuggestionCardShell
      icon="💸" title={t('documents.suggestion.createRecurringExpense')}
      {...props} confirmActionKey={props.confirmActionKey || 'recurring_expense'}
    >
      <div className="suggestion-details">
        {d.description && <Row label={String(t('common.description'))} value={d.description} />}
        {d.amount && <Row label={String(t('common.amount'))} value={fmtEur(d.amount)} />}
        {d.frequency && <Row label={String(t('recurring.frequency.label'))} value={String(t(`recurring.frequency.${d.frequency}`, d.frequency))} />}
        {d.start_date && <Row label={String(t('documents.ocr.startDate'))} value={fmtDate(d.start_date)} />}
        {d.end_date && <Row label={String(t('documents.ocr.endDate'))} value={fmtDate(d.end_date)} />}
        {d.category && <Row label={String(t('documents.ocr.category'))} value={d.category} />}
      </div>
    </SuggestionCardShell>
  );
};

export default RecurringExpenseSuggestionCard;
