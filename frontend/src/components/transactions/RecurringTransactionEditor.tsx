import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import {
  recurringTransactionService,
  RecurringTransactionItem,
  UpdateAndRegenerateData,
} from '../../services/recurringTransactionService';
import Select from '../common/Select';
import './RecurringTransactionEditor.css';

interface RecurringTransactionEditorProps {
  recurringId: number;
  onClose: () => void;
  onSaved: () => void;
}

interface FormData {
  description: string;
  amount: string;
  frequency: string;
  day_of_month: number;
  end_date: string;
  notes: string;
  apply_from: string;
}

const RecurringTransactionEditor = ({
  recurringId,
  onClose,
  onSaved,
}: RecurringTransactionEditorProps) => {
  const { t } = useTranslation();
  const [recurring, setRecurring] = useState<RecurringTransactionItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { register, handleSubmit, watch, reset } = useForm<FormData>();

  useEffect(() => {
    const load = async () => {
      try {
        const data = await recurringTransactionService.getById(recurringId);
        setRecurring(data);
        reset({
          description: data.description,
          amount: String(data.amount),
          frequency: data.frequency,
          day_of_month: data.day_of_month || 1,
          end_date: data.end_date || '',
          notes: data.notes || '',
          apply_from: new Date().toISOString().split('T')[0],
        });
      } catch {
        setError(t('recurring.edit.loadError'));
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [recurringId, reset, t]);

  const onSubmit = async (formData: FormData) => {
    setSaving(true);
    setError(null);
    try {
      const payload: UpdateAndRegenerateData = {};
      if (recurring) {
        if (formData.description !== recurring.description) payload.description = formData.description;
        if (Number(formData.amount) !== recurring.amount) payload.amount = Number(formData.amount);
        if (formData.frequency !== recurring.frequency) payload.frequency = formData.frequency;
        if (formData.day_of_month !== (recurring.day_of_month || 1)) payload.day_of_month = formData.day_of_month;
        if (formData.end_date !== (recurring.end_date || '')) payload.end_date = formData.end_date || undefined;
        if (formData.notes !== (recurring.notes || '')) payload.notes = formData.notes;
      }
      if (formData.apply_from) payload.apply_from = formData.apply_from;

      await recurringTransactionService.updateAndRegenerate(recurringId, payload);
      onSaved();
    } catch {
      setError(t('recurring.edit.saveError'));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="recurring-editor-overlay" onClick={onClose}>
        <div className="recurring-editor" onClick={(e) => e.stopPropagation()}>
          <p>{t('common.loading')}</p>
        </div>
      </div>
    );
  }

  if (!recurring) {
    return (
      <div className="recurring-editor-overlay" onClick={onClose}>
        <div className="recurring-editor" onClick={(e) => e.stopPropagation()}>
          <p>{error || t('recurring.edit.notFound')}</p>
          <button className="btn btn-secondary" onClick={onClose}>{t('common.close')}</button>
        </div>
      </div>
    );
  }

  return (
    <div className="recurring-editor-overlay" onClick={onClose}>
      <div className="recurring-editor" onClick={(e) => e.stopPropagation()}>
        <div className="recurring-editor-header">
          <h2>🔄 {t('recurring.edit.title')}</h2>
          <button className="btn-close" onClick={onClose}>✕</button>
        </div>

        <div className="recurring-editor-info">
          <span className={`type-badge ${recurring.transaction_type}`}>
            {recurring.transaction_type === 'income' ? t('transactions.types.income') : t('transactions.types.expense')}
          </span>
          <span className="recurring-editor-meta">
            {t('recurring.edit.templateId')}: #{recurring.id}
          </span>
        </div>

        {error && <div className="error-banner">{error}</div>}

        <form onSubmit={handleSubmit(onSubmit)} className="recurring-editor-form">
          <div className="form-group">
            <label>{t('transactions.description')}</label>
            <input type="text" {...register('description')} />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>{t('transactions.amount')} (€)</label>
              <input type="number" step="0.01" min="0.01" {...register('amount')} />
            </div>
            <div className="form-group">
              <label>{t('recurring.frequency.label')}</label>
              <Select {...register('frequency')} value={watch('frequency') || ''}
                options={[
                  { value: 'monthly', label: t('recurring.frequency.monthly') },
                  { value: 'quarterly', label: t('recurring.frequency.quarterly') },
                  { value: 'semi_annual', label: t('recurring.frequency.semi_annual') },
                  { value: 'annually', label: t('recurring.frequency.annually') },
                  { value: 'weekly', label: t('recurring.frequency.weekly') },
                ]} />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>{t('recurring.form.dayOfMonth')}</label>
              <input type="number" min="1" max="31" {...register('day_of_month', { valueAsNumber: true })} />
            </div>
            <div className="form-group">
              <label>{t('recurring.form.endDate')}</label>
              <input type="date" {...register('end_date')} />
            </div>
          </div>

          <div className="form-group">
            <label>{t('recurring.form.notes')}</label>
            <textarea rows={2} {...register('notes')} />
          </div>

          <div className="form-group apply-from-group">
            <label>{t('recurring.edit.applyFrom')}</label>
            <input type="date" {...register('apply_from')} />
            <span className="field-hint">{t('recurring.edit.applyFromHint')}</span>
          </div>

          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={saving}>
              {t('common.cancel')}
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? t('common.saving') : t('recurring.edit.saveAndRegenerate')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default RecurringTransactionEditor;
