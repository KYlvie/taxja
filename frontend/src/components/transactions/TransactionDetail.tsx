import { useTranslation } from 'react-i18next';
import { useConfirm } from '../../hooks/useConfirm';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { FileText } from 'lucide-react';
import { translateDeductionReason } from '../../utils/translateDeductionReason';
import { getLocaleForLanguage } from '../../utils/locale';
import { formatTransactionCategoryLabel } from '../../utils/formatTransactionCategoryLabel';
import {
  getTransactionAmountPrefix,
  getTransactionAmountTone,
  isExpenseTransactionType,
  Transaction,
} from '../../types/transaction';
import './TransactionDetail.css';

interface TransactionDetailProps {
  transaction: Transaction;
  onEdit: () => void;
  onDelete: () => void;
  onClose: () => void;
  onMarkReviewed?: (id: number) => void;
  hideLinkedDocumentSection?: boolean;
}

const TransactionDetail = ({
  transaction,
  onEdit,
  onDelete,
  onClose,
  onMarkReviewed,
  hideLinkedDocumentSection = false,
}: TransactionDetailProps) => {
  const { t, i18n } = useTranslation();
  const { confirm: showConfirm } = useConfirm();
  const navigate = useNavigate();
  const amountTone = getTransactionAmountTone(transaction.type);
  const isExpenseType = isExpenseTransactionType(transaction.type);
  const hasLineItems = Boolean(transaction.line_items && transaction.line_items.length > 0);
  const deductibleLineItemCount = transaction.line_items?.filter((item) => item.is_deductible).length ?? 0;
  const totalLineItemCount = transaction.line_items?.length ?? 0;
  const isPartiallyDeductible = hasLineItems
    && deductibleLineItemCount > 0
    && deductibleLineItemCount < totalLineItemCount;

  const formatAmount = (amount: number) => {
    return new Intl.NumberFormat(getLocaleForLanguage(i18n.language), {
      style: 'currency',
      currency: 'EUR',
    }).format(amount);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString(getLocaleForLanguage(i18n.language), {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  const formatDateTime = (dateString: string) => {
    return new Date(dateString).toLocaleString(getLocaleForLanguage(i18n.language), {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const renderDeductibleBadge = () => {
    if (isPartiallyDeductible) {
      return (
        <span className="badge badge-warning">
          ◐ {t('transactions.partiallyDeductible', 'Partial')}
        </span>
      );
    }

    if (hasLineItems) {
      return deductibleLineItemCount > 0 ? (
        <span className="badge badge-success">
          ✓ {t('transactions.deductibleYes')}
        </span>
      ) : (
        <span className="badge badge-secondary">
          ✗ {t('transactions.notDeductible')}
        </span>
      );
    }

    return transaction.is_deductible ? (
      <span className="badge badge-success">
        ✓ {t('transactions.deductibleYes')}
      </span>
    ) : (
      <span className="badge badge-secondary">
        ✗ {t('transactions.notDeductible')}
      </span>
    );
  };

  return createPortal(
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
              <span className={`amount ${amountTone}`}>
                {getTransactionAmountPrefix(transaction.type)}
                {formatAmount(transaction.amount)}
              </span>
            </div>

            <div className="detail-row">
              <span className="detail-label">{t('transactions.date')}:</span>
              <span>{formatDate(transaction.date)}</span>
            </div>

            {transaction.category ? (
              <div className="detail-row">
                <span className="detail-label">{t('transactions.category')}:</span>
                <span className="category-badge">
                  {formatTransactionCategoryLabel(transaction.category, t)}
                </span>
              </div>
            ) : null}

            <div className="detail-row">
              <span className="detail-label">{t('transactions.description')}:</span>
              <span>{transaction.description}</span>
            </div>
          </div>

          {isExpenseType && (
          <div className="detail-section">
            <h3>{t('transactions.taxInformation')}</h3>

            <div className="detail-row">
              <span className="detail-label">{t('transactions.deductible')}:</span>
              {renderDeductibleBadge()}
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
                          {translateDeductionReason(part, i18n.language)}
                          {i === 0 && <br />}
                        </span>
                      ))
                    : translateDeductionReason(transaction.deduction_reason, i18n.language)}
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

            {transaction.classification_method && (
              <div className="detail-row">
                <span className="detail-label">
                  {t('transactions.classificationPipeline', 'Classification Pipeline')}:
                </span>
                <div className="classification-pipeline">
                  {(() => {
                    const method = transaction.classification_method;
                    const stages: Array<{ key: string; active: boolean }> = [];
                    if (method === 'user_rule' || method === 'user_rule_soft') {
                      stages.push({ key: method, active: true });
                    } else {
                      stages.push({ key: 'user_rule', active: false });
                    }
                    if (method === 'rule_based' || method === 'rule') {
                      stages.push({ key: 'rule_based', active: true });
                    } else if (method !== 'user_rule' && method !== 'user_rule_soft' && method !== 'manual' && method !== 'csv') {
                      stages.push({ key: 'rule_based', active: false });
                    }
                    if (method === 'ml') {
                      stages.push({ key: 'ml', active: true });
                    } else if (method === 'llm' || method === 'llm_verified' || method === 'llm_consensus') {
                      stages.push({ key: 'ml', active: false });
                      stages.push({ key: method, active: true });
                    }
                    if (method === 'manual') {
                      stages.push({ key: 'manual', active: true });
                    }
                    if (method === 'csv') {
                      stages.push({ key: 'csv', active: true });
                    }
                    return stages.map((stage, idx) => (
                      <span key={stage.key} className="pipeline-stage-wrap">
                        {idx > 0 && <span className="pipeline-arrow">→</span>}
                        <span className={`method-badge method-${stage.key} ${stage.active ? 'pipeline-active' : 'pipeline-skipped'}`}>
                          {t(`transactions.methods.${stage.key}`, stage.key)}
                        </span>
                      </span>
                    ));
                  })()}
                </div>
              </div>
            )}
          </div>
          )}

          {transaction.line_items && transaction.line_items.length > 0 && (
            <div className="detail-section">
              <h3>{t('transactions.lineItems.title')}</h3>
              <div className="line-items-list">
                {transaction.line_items.map((item, idx) => (
                  <div key={item.id || idx} className="line-item-row">
                    <div className="line-item-main">
                      <span className="line-item-desc">{item.description}</span>
                      <span className="line-item-amount">{formatAmount(item.amount)}</span>
                    </div>
                    <div className="line-item-meta">
                      {item.quantity > 1 && (
                        <span className="line-item-qty">×{item.quantity}</span>
                      )}
                      {item.category && (
                        <span className="category-badge">
                          {formatTransactionCategoryLabel(item.category, t)}
                        </span>
                      )}
                      {item.is_deductible ? (
                        <span className="badge badge-success">✓ {t('transactions.deductibleYes')}</span>
                      ) : (
                        <span className="badge badge-secondary">✗ {t('transactions.notDeductible')}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
              {(transaction.deductible_amount != null || transaction.non_deductible_amount != null) && (
                <div className="line-items-summary">
                  {transaction.deductible_amount != null && transaction.deductible_amount > 0 && (
                    <div className="summary-row">
                      <span>{t('transactions.lineItems.deductibleTotal')}</span>
                      <span className="amount-success">{formatAmount(transaction.deductible_amount)}</span>
                    </div>
                  )}
                  {transaction.non_deductible_amount != null && transaction.non_deductible_amount > 0 && (
                    <div className="summary-row">
                      <span>{t('transactions.lineItems.nonDeductibleTotal')}</span>
                      <span className="amount-muted">{formatAmount(transaction.non_deductible_amount)}</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {transaction.needs_review && !transaction.reviewed && (
            <div className="detail-section review-section">
              <h3>{t('transactions.needsReview')}</h3>
              {transaction.ai_review_notes && (
                <div className="detail-row review-notes-row">
                  <span className="detail-label">{t('transactions.aiReviewNotes')}:</span>
                  <span className="review-notes-text">{transaction.ai_review_notes}</span>
                </div>
              )}
              {onMarkReviewed && (
                <button
                  className="btn btn-primary review-confirm-btn"
                  onClick={() => onMarkReviewed(transaction.id)}
                >
                  {t('transactions.markReviewed')}
                </button>
              )}
            </div>
          )}

          {transaction.document_id && !hideLinkedDocumentSection && (
            <div className="detail-section">
              <h3>{t('transactions.linkedDocument')}</h3>
              <div className="document-info">
                <button
                  className="document-link"
                  onClick={() => navigate(`/documents/${transaction.document_id}`)}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-primary)', padding: 0, font: 'inherit' }}
                >
                  <FileText size={16} />
                  {t('transactions.viewDocument')}
                </button>
              </div>
            </div>
          )}

          {transaction.is_system_generated && transaction.source_recurring_id && (
            <div className="detail-section">
              <div className="recurring-generated-hint">
                <span>🔄</span>
                <span>{t('recurring.edit.generatedHint')}</span>
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
              onClick={async () => {
                const ok = await showConfirm(t('transactions.confirmDelete'), { variant: 'danger', confirmText: t('common.delete') });
                if (ok) {
                  onDelete();
                }
              }}
            >
              {t('common.delete')}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
};

export default TransactionDetail;
