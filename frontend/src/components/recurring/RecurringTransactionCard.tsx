import React from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { RecurringTransaction } from '../../types/recurring';
import './RecurringTransactionCard.css';

interface RecurringTransactionCardProps {
  transaction: RecurringTransaction;
  onPause: (id: number) => void;
  onResume: (id: number) => void;
  onEdit: (transaction: RecurringTransaction) => void;
  onDelete: (id: number) => void;
}

export const RecurringTransactionCard: React.FC<RecurringTransactionCardProps> = ({
  transaction,
  onPause,
  onResume,
  onEdit,
  onDelete,
}) => {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const getTypeLabel = (type: string) =>
    t(`recurring.types.${type}`, type);

  const getFrequencyLabel = (frequency: string) =>
    t(`recurring.frequencies.${frequency}`, frequency);

  return (
    <div className="recurring-card">
      <div className="card-header">
        <div className="card-content">
          <div className="card-title-row">
            <h3 className="card-title">{transaction.description}</h3>
            <span className={`status-badge ${
              transaction.is_active ? 'status-active' :
              (transaction.end_date && new Date(transaction.end_date) < new Date()) ? 'status-stopped' : 'status-paused'
            }`}>
              {transaction.is_active ? t('recurring.statusActive', 'Active') :
               (transaction.end_date && new Date(transaction.end_date) < new Date()) ? t('recurring.statusStopped', 'Stopped') : t('recurring.statusPaused', 'Paused')}
            </span>
          </div>
          
          <div className="card-details">
            <div className="detail-item">
              <span className="detail-label">{t('recurring.typeLabel', 'Type')}:</span>
              <span className="detail-value">{getTypeLabel(transaction.recurring_type)}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">{t('recurring.amount', 'Amount')}:</span>
              <span className="amount-value">€{Number(transaction.amount).toFixed(2)}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">{t('recurring.frequencyLabel', 'Frequency')}:</span>
              <span className="detail-value">{getFrequencyLabel(transaction.frequency)}</span>
            </div>
            {transaction.next_generation_date && (
              <div className="detail-item">
                <span className="detail-label">{t('recurring.nextGeneration', 'Next')}:</span>
                <span className="detail-value">
                  {new Date(transaction.next_generation_date).toLocaleDateString()}
                </span>
              </div>
            )}
            {transaction.last_generated_date && (
              <div className="detail-item">
                <span className="detail-label">{t('recurring.lastGenerated', 'Last')}:</span>
                <span className="detail-value">
                  {new Date(transaction.last_generated_date).toLocaleDateString()}
                </span>
              </div>
            )}
          </div>
        </div>

        <div className="card-actions">
          {transaction.is_active ? (
            <button onClick={() => onPause(transaction.id)} className="action-btn btn-pause">
              {t('recurring.pause', 'Pause')}
            </button>
          ) : transaction.end_date && new Date(transaction.end_date) < new Date() ? null : (
            <button onClick={() => onResume(transaction.id)} className="action-btn btn-resume">
              {t('recurring.resume', 'Resume')}
            </button>
          )}

          {transaction.source_document_id && (
            <button
              onClick={() => navigate(`/documents/${transaction.source_document_id}`)}
              className="action-btn btn-view"
            >
              {t('recurring.viewContract', 'View Contract')}
            </button>
          )}
          <button onClick={() => onEdit(transaction)} className="action-btn btn-edit">
            {t('recurring.edit', 'Edit')}
          </button>

          <button onClick={() => onDelete(transaction.id)} className="action-btn btn-delete">
            {t('recurring.delete', 'Delete')}
          </button>
        </div>
      </div>
    </div>
  );
};
