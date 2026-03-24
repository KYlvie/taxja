import { useTranslation } from 'react-i18next';
import {
  AlertTriangle,
  Bot,
  Paperclip,
  Pause,
  Pencil,
  Play,
  RefreshCw,
  Trash2,
} from 'lucide-react';
import {
  getTransactionAmountPrefix,
  getTransactionAmountTone,
  isExpenseTransactionType,
  Transaction,
  TransactionType,
} from '../../types/transaction';
import { getLocaleForLanguage } from '../../utils/locale';
import './TransactionList.css';

interface TransactionListProps {
  transactions: Transaction[];
  onEdit: (transaction: Transaction) => void;
  onDelete: (id: number) => void;
  onView: (transaction: Transaction) => void;
  onPause?: (id: number) => void;
  onResume?: (id: number) => void;
  onEditRecurring?: (recurringId: number) => void;
  selectedIds?: Set<number>;
  onToggleSelect?: (id: number) => void;
  onToggleSelectAll?: () => void;
}

const TransactionList = ({
  transactions,
  onEdit,
  onDelete,
  onView,
  onPause,
  onResume,
  onEditRecurring,
  selectedIds,
  onToggleSelect,
  onToggleSelectAll,
}: TransactionListProps) => {
  const { t, i18n } = useTranslation();
  const locale = getLocaleForLanguage(i18n.resolvedLanguage || i18n.language);

  const formatAmount = (amount: number, type: TransactionType) => {
    const formatted = new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: 'EUR',
    }).format(amount);

    return `${getTransactionAmountPrefix(type)}${formatted}`;
  };

  const formatDate = (dateString: string) =>
    new Date(dateString).toLocaleDateString(locale, {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    });

  const recurringLabel = (transaction: Transaction) =>
    transaction.recurring_is_active === false
      ? t('recurring.status.paused')
      : t(`recurring.frequency.${transaction.recurring_frequency || 'monthly'}`);

  const renderActionButtons = (transaction: Transaction) => (
    <>
      {transaction.is_recurring && transaction.recurring_is_active && onPause ? (
        <button
          type="button"
          className="btn-icon"
          onClick={(event) => {
            event.stopPropagation();
            onPause(transaction.id);
          }}
          title={t('recurring.actions.pause')}
          aria-label={t('recurring.actions.pause')}
        >
          <Pause size={16} />
        </button>
      ) : null}

      {transaction.is_recurring && !transaction.recurring_is_active && onResume ? (
        <button
          type="button"
          className="btn-icon"
          onClick={(event) => {
            event.stopPropagation();
            onResume(transaction.id);
          }}
          title={t('recurring.actions.resume')}
          aria-label={t('recurring.actions.resume')}
        >
          <Play size={16} />
        </button>
      ) : null}

      {(transaction.source_recurring_id || transaction.parent_recurring_id) &&
      onEditRecurring ? (
        <button
          type="button"
          className="btn-icon"
          onClick={(event) => {
            event.stopPropagation();
            onEditRecurring((transaction.source_recurring_id || transaction.parent_recurring_id)!);
          }}
          title={t('recurring.edit.title')}
          aria-label={t('recurring.edit.title')}
        >
          <RefreshCw size={16} />
        </button>
      ) : (
        <button
          type="button"
          className="btn-icon"
          onClick={(event) => {
            event.stopPropagation();
            onEdit(transaction);
          }}
          title={t('common.edit')}
          aria-label={t('common.edit')}
        >
          <Pencil size={16} />
        </button>
      )}

      <button
        type="button"
        className="btn-icon btn-danger"
        onClick={(event) => {
          event.stopPropagation();
          onDelete(transaction.id);
        }}
        title={t('common.delete')}
        aria-label={t('common.delete')}
      >
        <Trash2 size={16} />
      </button>
    </>
  );

  if (transactions.length === 0) {
    return (
      <div className="transaction-list-empty">
        <p>{t('transactions.noTransactions')}</p>
      </div>
    );
  }

  return (
    <div className="transaction-list">
      <div className="transaction-table-shell">
        <table className="transaction-table">
          <thead>
            <tr>
              {onToggleSelect && (
                <th className="col-checkbox">
                  <input
                    type="checkbox"
                    checked={transactions.length > 0 && transactions.every((t) => selectedIds?.has(t.id))}
                    ref={(el) => {
                      if (el) {
                        const allSelected = transactions.length > 0 && transactions.every((t) => selectedIds?.has(t.id));
                        const someSelected = transactions.some((t) => selectedIds?.has(t.id));
                        el.indeterminate = someSelected && !allSelected;
                      }
                    }}
                    onChange={() => onToggleSelectAll?.()}
                    aria-label={t('transactions.selectAll', 'Select all')}
                  />
                </th>
              )}
              <th>{t('transactions.date')}</th>
              <th>{t('transactions.description')}</th>
              <th>{t('transactions.category')}</th>
              <th>{t('transactions.amount')}</th>
              <th>{t('transactions.type')}</th>
              <th>{t('transactions.deductible')}</th>
              <th>{t('common.actions')}</th>
            </tr>
          </thead>
          <tbody>
            {transactions.map((transaction) => (
              <tr
                key={transaction.id}
                className={`transaction-row ${transaction.type}${selectedIds?.has(transaction.id) ? ' selected' : ''}`}
                onClick={() => onView(transaction)}
              >
                {onToggleSelect && (
                  <td className="col-checkbox" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={selectedIds?.has(transaction.id) || false}
                      onChange={() => onToggleSelect(transaction.id)}
                      aria-label={t('transactions.selectTransaction', 'Select')}
                    />
                  </td>
                )}
                <td>{formatDate(transaction.date)}</td>
                <td className="description">
                  <span className="description-text">{transaction.description}</span>
                  <span className="transaction-inline-flags">
                    {transaction.needs_review && !transaction.reviewed ? (
                      <span
                        className="inline-flag needs-review-badge"
                        title={t('transactions.needsReview')}
                      >
                        <AlertTriangle size={13} />
                      </span>
                    ) : null}

                    {transaction.is_recurring ? (
                      <span
                        className={`inline-flag recurring-badge ${
                          transaction.recurring_is_active === false ? 'paused' : ''
                        }`}
                        title={recurringLabel(transaction)}
                      >
                        <RefreshCw size={13} />
                      </span>
                    ) : null}

                    {transaction.is_system_generated ? (
                      <span
                        className="inline-flag system-generated-badge"
                        title={t('transactions.systemGenerated')}
                      >
                        <Bot size={13} />
                      </span>
                    ) : null}

                    {transaction.document_id ? (
                      <span className="inline-flag has-document" title={t('transactions.hasDocument')}>
                        <Paperclip size={13} />
                      </span>
                    ) : null}
                  </span>
                </td>
                <td>
                  {transaction.category ? (
                    <span className="category-badge">
                      {t(`transactions.categories.${transaction.category}`)}
                    </span>
                  ) : (
                    <span className="category-empty">-</span>
                  )}
                </td>
                <td className={`amount ${getTransactionAmountTone(transaction.type)}`}>
                  {formatAmount(transaction.amount, transaction.type)}
                </td>
                <td>
                  <span className={`type-badge ${transaction.type}`}>
                    {t(`transactions.types.${transaction.type}`)}
                  </span>
                </td>
                <td>
                  {isExpenseTransactionType(transaction.type) ? (
                    transaction.is_deductible ? (
                      <span className="deductible-yes">✓</span>
                    ) : (
                      <span className="deductible-no">✕</span>
                    )
                  ) : (
                    <span className="deductible-na">-</span>
                  )}
                </td>
                <td className="actions">{renderActionButtons(transaction)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="transaction-mobile-list">
        {transactions.map((transaction) => (
          <article
            key={transaction.id}
            className={`transaction-card ${transaction.type}`}
            onClick={() => onView(transaction)}
          >
            <div className="transaction-card-top">
              <div className="transaction-card-date">{formatDate(transaction.date)}</div>
              <div className={`amount ${getTransactionAmountTone(transaction.type)}`}>
                {formatAmount(transaction.amount, transaction.type)}
              </div>
            </div>

            <div className="transaction-card-description">{transaction.description}</div>

            <div className="transaction-card-tags">
              {transaction.category ? (
                <span className="category-badge">
                  {t(`transactions.categories.${transaction.category}`)}
                </span>
              ) : null}
              <span className={`type-badge ${transaction.type}`}>
                {t(`transactions.types.${transaction.type}`)}
              </span>
              {isExpenseTransactionType(transaction.type) ? (
                <span
                  className={`transaction-chip ${transaction.is_deductible ? 'positive' : 'neutral'}`}
                >
                  {t('transactions.deductible')}: {transaction.is_deductible ? t('common.yes', 'Yes') : t('common.no', 'No')}
                </span>
              ) : null}

              {transaction.needs_review && !transaction.reviewed ? (
                <span className="transaction-chip needs-review">
                  <AlertTriangle size={12} />
                  <span>{t('transactions.needsReview')}</span>
                </span>
              ) : null}

              {transaction.is_recurring ? (
                <span
                  className={`transaction-chip recurring ${
                    transaction.recurring_is_active === false ? 'paused' : ''
                  }`}
                >
                  <RefreshCw size={12} />
                  <span>{recurringLabel(transaction)}</span>
                </span>
              ) : null}

              {transaction.is_system_generated ? (
                <span className="transaction-chip neutral">
                  <Bot size={12} />
                  <span>{t('transactions.systemGenerated')}</span>
                </span>
              ) : null}

              {transaction.document_id ? (
                <span className="transaction-chip neutral">
                  <Paperclip size={12} />
                  <span>{t('transactions.hasDocument')}</span>
                </span>
              ) : null}
            </div>

            <div className="transaction-card-actions">{renderActionButtons(transaction)}</div>
          </article>
        ))}
      </div>
    </div>
  );
};

export default TransactionList;
