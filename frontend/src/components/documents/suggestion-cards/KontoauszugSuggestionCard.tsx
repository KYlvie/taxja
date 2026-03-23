import React from 'react';
import { useTranslation } from 'react-i18next';
import SuggestionCardShell, { Row } from './SuggestionCardBase';
import type { SuggestionCardProps } from './SuggestionCardBase';

type StatementTransaction = {
  date?: string;
  amount?: number;
  counterparty?: string;
  purpose?: string;
  is_duplicate?: boolean;
};

const KontoauszugSuggestionCard: React.FC<SuggestionCardProps> = (props) => {
  const { t } = useTranslation();
  const data = props.suggestion.data || {};
  const transactions: StatementTransaction[] = Array.isArray(data.transactions) ? data.transactions : [];
  const nonDuplicateCount = transactions.filter((tx) => !tx.is_duplicate).length;
  const duplicateCount = transactions.length - nonDuplicateCount;

  return (
    <SuggestionCardShell
      icon="🏦"
      title={t('documents.suggestion.importBankStatement', 'Import bank statement')}
      confirmResult={props.confirmResult}
      confirmingAction={props.confirmingAction}
      confirmActionKey={props.confirmActionKey || 'bank_workbench'}
      onConfirm={props.onConfirm}
      onDismiss={props.onDismiss}
      disableConfirm={props.confirmDisabled}
      disableConfirmReason={props.confirmDisabledReason}
      confirmLabel={props.confirmLabel || t('documents.suggestion.openBankWorkbench', 'Open bank statement workbench')}
      documentId={props.documentId}
      suggestionType={props.suggestion.type}
      suggestionData={props.suggestion.data}
    >
      {data.bank_name && (
        <Row
          label={t('documents.suggestion.fields.bank_name', 'Bank')}
          value={String(data.bank_name)}
        />
      )}
      {data.iban && (
        <Row
          label={t('documents.suggestion.fields.iban', 'IBAN')}
          value={String(data.iban)}
        />
      )}
      {data.statement_period && (
        <Row
          label={t('documents.suggestion.fields.statement_period', 'Statement period')}
          value={String(data.statement_period)}
        />
      )}
      <Row
        label={t('documents.bankWorkbench.totalCount', 'Total lines')}
        value={transactions.length}
      />
      <Row
        label={t('documents.bankWorkbench.pendingReview', 'Pending review')}
        value={nonDuplicateCount}
      />
      {duplicateCount > 0 && (
        <Row
          label={t('documents.bankWorkbench.ignoredCount', 'Ignored')}
          value={duplicateCount}
        />
      )}
      <p className="suggestion-help-text">
        {t(
          'documents.suggestion.bankWorkbenchHint',
          'Open the bank statement workbench to review low-confidence items, match existing transactions, and confirm any new transactions before importing them.'
        )}
      </p>
    </SuggestionCardShell>
  );
};

export default KontoauszugSuggestionCard;
