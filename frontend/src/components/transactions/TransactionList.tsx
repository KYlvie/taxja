import { useTranslation } from 'react-i18next';
import { Transaction, TransactionType } from '../../types/transaction';
import './TransactionList.css';

interface TransactionListProps {
  transactions: Transaction[];
  onEdit: (transaction: Transaction) => void;
  onDelete: (id: number) => void;
  onView: (transaction: Transaction) => void;
  onPause?: (id: number) => void;
  onResume?: (id: number) => void;
}

const TransactionList = ({
  transactions,
  onEdit,
  onDelete,
  onView,
  onPause,
  onResume,
}: TransactionListProps) => {
  const { t } = useTranslation();

  const formatAmount = (amount: number, type: TransactionType) => {
    const formatted = new Intl.NumberFormat('de-AT', {
      style: 'currency',
      currency: 'EUR',
    }).format(amount);
    return type === TransactionType.INCOME ? `+${formatted}` : `-${formatted}`;
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('de-AT', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    });
  };

  if (transactions.length === 0) {
    return (
      <div className="transaction-list-empty">
        <p>{t('transactions.noTransactions')}</p>
      </div>
    );
  }

  return (
    <div className="transaction-list">
      <table className="transaction-table">
        <thead>
          <tr>
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
              className={`transaction-row ${transaction.type}`}
              onClick={() => onView(transaction)}
            >
              <td>{formatDate(transaction.date)}</td>
              <td className="description">
                {transaction.description}
                {transaction.is_recurring && (
                  <span
                    className={`recurring-badge ${transaction.recurring_is_active === false ? 'paused' : ''}`}
                    title={
                      transaction.recurring_is_active === false
                        ? t('recurring.status.paused')
                        : t('recurring.frequency.' + (transaction.recurring_frequency || 'monthly'))
                    }
                  >
                    🔄
                  </span>
                )}
                {transaction.is_system_generated && (
                  <span className="system-generated-badge" title={t('transactions.systemGenerated')}>
                    🤖
                  </span>
                )}
                {transaction.document_id && (
                  <span className="has-document" title={t('transactions.hasDocument')}>
                    📎
                  </span>
                )}
              </td>
              <td>
                <span className="category-badge">
                  {t(`transactions.categories.${transaction.category}`)}
                </span>
              </td>
              <td className={`amount ${transaction.type}`}>
                {formatAmount(transaction.amount, transaction.type)}
              </td>
              <td>
                <span className={`type-badge ${transaction.type}`}>
                  {t(`transactions.types.${transaction.type}`)}
                </span>
              </td>
              <td>
                {transaction.is_deductible ? (
                  <span className="deductible-yes">✓</span>
                ) : (
                  <span className="deductible-no">✗</span>
                )}
              </td>
              <td className="actions">
                {transaction.is_recurring && transaction.recurring_is_active && onPause && (
                  <button
                    className="btn-icon"
                    onClick={(e) => {
                      e.stopPropagation();
                      onPause(transaction.id);
                    }}
                    title={t('recurring.actions.pause')}
                  >
                    ⏸️
                  </button>
                )}
                {transaction.is_recurring && !transaction.recurring_is_active && onResume && (
                  <button
                    className="btn-icon"
                    onClick={(e) => {
                      e.stopPropagation();
                      onResume(transaction.id);
                    }}
                    title={t('recurring.actions.resume')}
                  >
                    ▶️
                  </button>
                )}
                <button
                  className="btn-icon"
                  onClick={(e) => {
                    e.stopPropagation();
                    onEdit(transaction);
                  }}
                  title={t('common.edit')}
                >
                  ✏️
                </button>
                <button
                  className="btn-icon btn-danger"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (window.confirm(t('transactions.confirmDelete'))) {
                      onDelete(transaction.id);
                    }
                  }}
                  title={t('common.delete')}
                >
                  🗑️
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default TransactionList;
