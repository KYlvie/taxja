import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Transaction, TransactionType } from '../../types/transaction';
import './TransactionDetail.css';

interface TransactionDetailProps {
  transaction: Transaction;
  onEdit: () => void;
  onDelete: () => void;
  onClose: () => void;
}

const TransactionDetail = ({
  transaction,
  onEdit,
  onDelete,
  onClose,
}: TransactionDetailProps) => {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const formatAmount = (amount: number) => {
    return new Intl.NumberFormat('de-AT', {
      style: 'currency',
      currency: 'EUR',
    }).format(amount);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('de-AT', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  const formatDateTime = (dateString: string) => {
    return new Date(dateString).toLocaleString('de-AT', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="transaction-detail-overlay" onClick={onClose}>
      <div className="transaction-detail" onClick={(e) => e.stopPropagation()}>
        <div className="detail-header">
          <h2>{t('transactions.transactionDetails')}</h2>
          <button className="btn-close" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="detail-body">
          <div className="detail-section">
            <div className="detail-row">
              <span className="detail-label">{t('transactions.type')}:</span>
              <span className={`type-badge ${transaction.type}`}>
                {t(`transactions.types.${transaction.type}`)}
              </span>
            </div>

            <div className="detail-row">
              <span className="detail-label">{t('transactions.amount')}:</span>
              <span className={`amount ${transaction.type}`}>
                {transaction.type === TransactionType.INCOME ? '+' : '-'}
                {formatAmount(transaction.amount)}
              </span>
            </div>

            <div className="detail-row">
              <span className="detail-label">{t('transactions.date')}:</span>
              <span>{formatDate(transaction.date)}</span>
            </div>

            <div className="detail-row">
              <span className="detail-label">{t('transactions.category')}:</span>
              <span className="category-badge">
                {t(`transactions.categories.${transaction.category}`)}
              </span>
            </div>

            <div className="detail-row">
              <span className="detail-label">{t('transactions.description')}:</span>
              <span>{transaction.description}</span>
            </div>
          </div>

          <div className="detail-section">
            <h3>{t('transactions.taxInformation')}</h3>

            <div className="detail-row">
              <span className="detail-label">{t('transactions.deductible')}:</span>
              {transaction.is_deductible ? (
                <span className="badge badge-success">
                  ✓ {t('transactions.deductibleYes')}
                </span>
              ) : (
                <span className="badge badge-secondary">
                  ✗ {t('transactions.notDeductible')}
                </span>
              )}
              {transaction.locked ? (
                <span className="badge badge-user-override">🔒 {t('transactions.userOverride')}</span>
              ) : (
                <span className="badge badge-ai">🤖 AI</span>
              )}
            </div>

            {transaction.deduction_reason && (
              <div className="detail-row deduction-info">
                <span className="detail-label">{t('transactions.taxAdvice')}:</span>
                <span className="deduction-reason-text">
                  {transaction.deduction_reason.includes(' | ')
                    ? transaction.deduction_reason.split(' | ').map((part, i) => (
                        <span key={i} className={i === 0 ? 'reason-main' : 'reason-tip'}>
                          {i === 1 && <span className="tip-icon">💡 </span>}
                          {part}
                          {i === 0 && <br />}
                        </span>
                      ))
                    : transaction.deduction_reason}
                </span>
              </div>
            )}

            {transaction.vat_rate && (
              <>
                <div className="detail-row">
                  <span className="detail-label">{t('transactions.vatRate')}:</span>
                  <span>{(transaction.vat_rate * 100).toFixed(0)}%</span>
                </div>

                {transaction.vat_amount && (
                  <div className="detail-row">
                    <span className="detail-label">{t('transactions.vatAmount')}:</span>
                    <span>{formatAmount(transaction.vat_amount)}</span>
                  </div>
                )}
              </>
            )}

            {transaction.classification_confidence !== undefined && (
              <div className="detail-row">
                <span className="detail-label">
                  {t('transactions.classificationConfidence')}:
                </span>
                <div className="confidence-bar">
                  <div
                    className="confidence-fill"
                    style={{
                      width: `${transaction.classification_confidence * 100}%`,
                      backgroundColor:
                        transaction.classification_confidence > 0.7
                          ? '#28a745'
                          : transaction.classification_confidence > 0.5
                          ? '#ffc107'
                          : '#dc3545',
                    }}
                  />
                  <span className="confidence-text">
                    {(transaction.classification_confidence * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            )}
          </div>

          {transaction.document_id && (
            <div className="detail-section">
              <h3>{t('transactions.linkedDocument')}</h3>
              <div className="document-info">
                <span className="document-icon">📎</span>
                <button
                  className="document-link"
                  onClick={() => navigate(`/documents/${transaction.document_id}`)}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-primary)', textDecoration: 'underline', padding: 0, font: 'inherit' }}
                >
                  {t('transactions.viewDocument')}
                </button>
              </div>
            </div>
          )}

          {(transaction.created_at || transaction.updated_at) && (
            <div className="detail-section metadata">
              {transaction.created_at && (
                <div className="detail-row">
                  <span className="detail-label">{t('transactions.createdAt')}:</span>
                  <span className="metadata-text">
                    {formatDateTime(transaction.created_at)}
                  </span>
                </div>
              )}
              {transaction.updated_at && (
                <div className="detail-row">
                  <span className="detail-label">{t('transactions.updatedAt')}:</span>
                  <span className="metadata-text">
                    {formatDateTime(transaction.updated_at)}
                  </span>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="detail-footer">
          <button className="btn btn-secondary" onClick={onClose}>
            {t('common.close')}
          </button>
          <div className="action-buttons">
            <button className="btn btn-primary" onClick={onEdit}>
              {t('common.edit')}
            </button>
            <button
              className="btn btn-danger"
              onClick={() => {
                if (window.confirm(t('transactions.confirmDelete'))) {
                  onDelete();
                }
              }}
            >
              {t('common.delete')}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TransactionDetail;
