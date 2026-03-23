import { useForm } from 'react-hook-form';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Transaction } from '../../types/transaction';
import { recurringTransactionService } from '../../services/recurringTransactionService';
import Select from '../common/Select';
import './RecurringTransactionEditor.css';

interface ConvertToRecurringModalProps {
  transaction: Transaction;
  onClose: () => void;
  onConverted: () => void;
}

interface FormData {
  frequency: string;
  start_date: string;
  end_date: string;
  day_of_month: number;
  notes: string;
}

const ConvertToRecurringModal = ({
  transaction,
  onClose,
  onConverted,
}: ConvertToRecurringModalProps) => {
  const { t } = useTranslation();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { register, handleSubmit, watch } = useForm<FormData>({
    defaultValues: {
      frequency: 'monthly',
      start_date: transaction.date?.split('T')[0] || new Date().toISOString().split('T')[0],
      end_date: '',
      day_of_month: new Date(transaction.date).getDate() || 1,
      notes: '',
    },
  });

  const onSubmit = async (data: FormData) => {
    setSaving(true);
    setError(null);
    try {
      await recurringTransactionService.convertFromTransaction(transaction.id, {
        frequency: data.frequency,
        start_date: data.start_date,
        end_date: data.end_date || undefined,
        day_of_month: data.day_of_month,
        notes: data.notes || undefined,
      });
      onConverted();
    } catch {
      setError(t('recurring.convert.error'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="recurring-editor-overlay" onClick={onClose}>
      <div className="recurring-editor" onClick={(e) => e.stopPropagation()}>
        <div className="recurring-editor-header">
          <h2>🔄 {t('recurring.convert.title')}</h2>
          <button className="btn-close" onClick={onClose}>✕</button>
        </div>

        <div className="recurring-editor-info">
          <span>{transaction.description}</span>
          <span className="recurring-editor-meta">
            €{Number(transaction.amount).toFixed(2)}
          </span>
        </div>

        <div className="convert-upload-hint">
          <span className="hint-icon">📎</span>
          <span>{t('recurring.convert.uploadHint')}</span>
        </div>

        {error && <div className="error-banner">{error}</div>}

        <form onSubmit={handleSubmit(onSubmit)} className="recurring-editor-form">
          <div className="form-row">
            <div className="form-group">
              <label>{t('recurring.frequency.label')}</label>
              <Select {...register('frequency')} value={watch('frequency') || ''}
                options={[
                  { value: 'monthly', label: t('recurring.frequency.monthly') },
                  { value: 'quarterly', label: t('recurring.frequency.quarterly') },
                  { value: 'annually', label: t('recurring.frequency.annually') },
                  { value: 'weekly', label: t('recurring.frequency.weekly') },
                ]} />
            </div>
            <div className="form-group">
              <label>{t('recurring.form.dayOfMonth')}</label>
              <input type="number" min="1" max="31" {...register('day_of_month', { valueAsNumber: true })} />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>{t('recurring.form.startDate')}</label>
              <input type="date" {...register('start_date')} />
            </div>
            <div className="form-group">
              <label>{t('recurring.form.endDate')}（{t('recurring.form.endDateHelp')}）</label>
              <input type="date" {...register('end_date')} />
            </div>
          </div>

          <div className="form-group">
            <label>{t('recurring.form.notes')}</label>
            <textarea rows={2} {...register('notes')} placeholder={t('recurring.convert.notesPlaceholder')} />
          </div>

          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={saving}>
              {t('common.cancel')}
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? t('common.saving') : t('recurring.convert.confirm')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ConvertToRecurringModal;
