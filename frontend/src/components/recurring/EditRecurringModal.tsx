import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useConfirm } from '../../hooks/useConfirm';
import { useForm } from 'react-hook-form';
import { useNavigate } from 'react-router-dom';
import { RecurringTransaction } from '../../types/recurring';
import { recurringService } from '../../services/recurringService';
import '../transactions/RecurringTransactionEditor.css';

interface FormData {
  amount: number;
  end_date?: string;
  notes?: string;
}

interface EditRecurringModalProps {
  transaction: RecurringTransaction;
  onClose: () => void;
  onSuccess: () => void;
}

export const EditRecurringModal: React.FC<EditRecurringModalProps> = ({
  transaction,
  onClose,
  onSuccess,
}) => {
  const { t } = useTranslation();
  const { confirm: showConfirm, alert: showAlert } = useConfirm();
  const navigate = useNavigate();
  const isStopped = !transaction.is_active;
  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({
    defaultValues: {
      amount: transaction.amount,
      end_date: transaction.end_date || '',
      notes: transaction.notes || '',
    },
  });
  const [loading, setLoading] = useState(false);

  const onSubmit = async (data: FormData) => {
    try {
      setLoading(true);
      await recurringService.update(transaction.id, {
        amount: data.amount,
        end_date: data.end_date || undefined,
        notes: data.notes || undefined,
      });
      onSuccess();
    } catch (error: any) {
      console.error('Failed to update recurring transaction:', error);
      const detail = error?.response?.data?.detail;
      await showAlert(detail || t('recurring.errors.updateFailed'), { variant: 'danger' });
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    const ok = await showConfirm(t('recurring.confirmStop'), { variant: 'warning' });
    if (ok) {
      try {
        setLoading(true);
        await recurringService.stop(transaction.id);
        onSuccess();
      } catch (error) {
        console.error('Failed to stop recurring transaction:', error);
        await showAlert(t('recurring.errors.stopFailed'), { variant: 'danger' });
      } finally {
        setLoading(false);
      }
    }
  };

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString('zh-CN');
  };

  return (
    <div className="recurring-editor-overlay" onClick={onClose}>
      <div className="recurring-editor" onClick={(e) => e.stopPropagation()}>
        <div className="recurring-editor-header">
          <h2>{isStopped ? '📋' : '🔄'} {isStopped ? t('recurring.view.title') : t('recurring.edit.title')}</h2>
          <button className="btn-close" onClick={onClose}>✕</button>
        </div>

        <div className="recurring-editor-info">
          <span className={`type-badge ${transaction.transaction_type}`}>
            {transaction.transaction_type === 'income'
              ? t('transactions.types.income')
              : t('transactions.types.expense')}
          </span>
          <span className="recurring-editor-meta">{transaction.description}</span>
        </div>

        <div className="recurring-editor-info">
          <span className="recurring-editor-meta">
            {t('recurring.frequency.label')}: {t(`recurring.frequency.${transaction.frequency}`)}
          </span>
        </div>

        {isStopped ? (
          /* Stopped: read-only view */
          <div className="recurring-editor-form">
            <div className="recurring-editor-info">
              <span className="recurring-editor-meta">
                {t('recurring.form.amount')}: €{Number(transaction.amount).toFixed(2)}
              </span>
            </div>
            <div className="recurring-editor-info">
              <span className="recurring-editor-meta">
                {t('recurring.startDate')}: {formatDate(transaction.start_date)}
              </span>
            </div>
            <div className="recurring-editor-info">
              <span className="recurring-editor-meta">
                {t('recurring.endDate')}: {formatDate(transaction.end_date)}
              </span>
            </div>
            {transaction.notes && (
              <div className="recurring-editor-info">
                <span className="recurring-editor-meta">
                  {t('recurring.form.notes')}: {transaction.notes}
                </span>
              </div>
            )}
            {/* Document link */}
            <div className="recurring-document-section">
              {transaction.source_document_id ? (
                <button
                  type="button"
                  className="btn-document-link"
                  onClick={() => navigate(`/documents/${transaction.source_document_id}`)}
                >
                  📎 {t('recurring.viewDocument')}
                </button>
              ) : (
                <button
                  type="button"
                  className="btn-document-link btn-upload-hint"
                  onClick={() => navigate('/documents')}
                >
                  📤 {t('recurring.uploadDocument')}
                </button>
              )}
            </div>
            <div className="recurring-generated-hint">
              ℹ️ {t('recurring.view.stoppedHint')}
            </div>
            <div className="form-actions">
              <div style={{ flex: 1 }} />
              <button
                type="button"
                className="btn btn-secondary"
                onClick={onClose}
              >
                {t('common.close')}
              </button>
            </div>
          </div>
        ) : (
          /* Active: editable form */
          <form onSubmit={handleSubmit(onSubmit)} className="recurring-editor-form">
            <div className="form-group">
              <label>{t('recurring.form.amount')} (€)</label>
              <input
                type="number"
                step="0.01"
                {...register('amount', { required: true, min: 0 })}
              />
              {errors.amount && (
                <span className="field-error">{t('recurring.errors.amountRequired')}</span>
              )}
            </div>

            <div className="form-group">
              <label>{t('recurring.form.endDate')} ({t('common.optional')})</label>
              <input type="date" {...register('end_date')} />
              <span className="field-hint">{t('recurring.form.endDateHelp')}</span>
            </div>

            <div className="form-group">
              <label>{t('recurring.form.notes')} ({t('common.optional')})</label>
              <textarea rows={3} {...register('notes')} />
            </div>

            {/* Document link */}
            <div className="recurring-document-section">
              {transaction.source_document_id ? (
                <button
                  type="button"
                  className="btn-document-link"
                  onClick={() => navigate(`/documents/${transaction.source_document_id}`)}
                >
                  📎 {t('recurring.viewDocument')}
                </button>
              ) : (
                <button
                  type="button"
                  className="btn-document-link btn-upload-hint"
                  onClick={() => navigate('/documents')}
                >
                  📤 {t('recurring.uploadDocument')}
                </button>
              )}
            </div>

            <div className="form-actions">
              <button
                type="button"
                className="btn btn-danger"
                onClick={handleStop}
                disabled={loading}
              >
                {t('recurring.actions.stop')}
              </button>
              <div style={{ flex: 1 }} />
              <button
                type="button"
                className="btn btn-secondary"
                onClick={onClose}
                disabled={loading}
              >
                {t('common.cancel')}
              </button>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={loading}
              >
                {loading ? t('common.saving') : t('common.save')}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
