import React, { useState, useMemo, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { SuggestionCardProps, fmtEur, fmtDate } from './SuggestionCardBase';

interface BankTx {
  date?: string;
  amount?: number;
  counterparty?: string;
  purpose?: string;
  is_duplicate?: boolean;
}

const KontoauszugSuggestionCard: React.FC<SuggestionCardProps & {
  onConfirmBankTransactions?: (indices: number[]) => void;
}> = (props) => {
  const { t } = useTranslation();
  const d = props.suggestion.data || {};
  const transactions: BankTx[] = Array.isArray(d.transactions) ? d.transactions : [];

  const nonDuplicateIndices = useMemo(
    () => transactions.map((tx, i) => ({ tx, i })).filter(({ tx }) => !tx.is_duplicate).map(({ i }) => i),
    [transactions]
  );

  const [selected, setSelected] = useState<Set<number>>(() => new Set(nonDuplicateIndices));

  const toggleOne = useCallback((idx: number) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx); else next.add(idx);
      return next;
    });
  }, []);

  const toggleAll = useCallback(() => {
    setSelected(prev =>
      prev.size === nonDuplicateIndices.length ? new Set() : new Set(nonDuplicateIndices)
    );
  }, [nonDuplicateIndices]);

  const handleConfirm = useCallback(() => {
    if (props.onConfirmBankTransactions) {
      props.onConfirmBankTransactions(Array.from(selected));
    }
  }, [selected, props.onConfirmBankTransactions]);

  return (
    <div className="import-suggestion-card">
      <div className="suggestion-header">
        <span className="suggestion-icon">🏦</span>
        <h3>{t('documents.suggestion.importBankStatement')}</h3>
      </div>
      {d.bank_name && (
        <div className="suggestion-row" style={{ marginBottom: 4 }}>
          <span>{t('documents.suggestion.fields.bank_name')}</span>
          <span>{d.bank_name}</span>
        </div>
      )}
      {d.iban && (
        <div className="suggestion-row" style={{ marginBottom: 4 }}>
          <span>{t('documents.suggestion.fields.iban')}</span>
          <span>{d.iban}</span>
        </div>
      )}
      {d.statement_period && (
        <div className="suggestion-row" style={{ marginBottom: 8 }}>
          <span>{t('documents.suggestion.fields.statement_period')}</span>
          <span>{d.statement_period}</span>
        </div>
      )}

      {transactions.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table className="bank-tx-table">
            <thead>
              <tr>
                <th style={{ width: 32 }}></th>
                <th>{t('documents.suggestion.fields.date')}</th>
                <th>{t('documents.suggestion.fields.amount')}</th>
                <th>{t('documents.suggestion.fields.counterparty')}</th>
                <th>{t('documents.suggestion.fields.purpose')}</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((tx, idx) => (
                <tr key={idx} className={tx.is_duplicate ? 'duplicate-tx' : ''}>
                  <td>
                    <input
                      type="checkbox"
                      checked={selected.has(idx)}
                      disabled={!!tx.is_duplicate}
                      onChange={() => toggleOne(idx)}
                      aria-label={`Select transaction ${idx + 1}`}
                    />
                  </td>
                  <td>{fmtDate(tx.date)}</td>
                  <td style={{ color: (tx.amount ?? 0) < 0 ? '#dc2626' : '#16a34a', fontWeight: 500 }}>
                    {fmtEur(tx.amount)}
                  </td>
                  <td>{tx.counterparty || '—'}</td>
                  <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {tx.purpose || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="bank-tx-import-footer">
        <label className="bank-tx-select-all">
          <input
            type="checkbox"
            checked={selected.size === nonDuplicateIndices.length && nonDuplicateIndices.length > 0}
            onChange={toggleAll}
            aria-label="Select all transactions"
          />
          {t('documents.suggestion.selectAll')}
        </label>
        <span style={{ fontSize: '0.85rem', color: '#6b7280' }}>
          {t('documents.suggestion.selectedCount', { count: selected.size, total: transactions.length })}
        </span>
      </div>

      {props.confirmResult && (
        <div className={`suggestion-result ${props.confirmResult.type}`}>{props.confirmResult.message}</div>
      )}
      <div className="suggestion-actions">
        <button className="btn btn-primary" onClick={handleConfirm} disabled={props.confirmingAction !== null || selected.size === 0}>
          {props.confirmingAction === 'bank_import' ? '⏳' : '✅'} {t('documents.suggestion.importSelected', { count: selected.size })}
        </button>
        <button className="btn btn-secondary" onClick={props.onDismiss} disabled={props.confirmingAction !== null}>
          {t('documents.suggestion.dismiss')}
        </button>
      </div>
    </div>
  );
};

export default KontoauszugSuggestionCard;
