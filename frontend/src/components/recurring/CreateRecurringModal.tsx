import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useConfirm } from '../../hooks/useConfirm';
import { useForm } from 'react-hook-form';
import { recurringService } from '../../services/recurringService';
import { propertyService } from '../../services/propertyService';
import { loanService } from '../../services/loanService';
import { IncomeCategory, ExpenseCategory } from '../../types/transaction';
import { RecurrenceFrequency } from '../../types/recurring';
import Select from '../common/Select';
import '../transactions/RecurringTransactionEditor.css';

interface Property {
  id: string;
  address: string;
  status: string;
}

interface FormData {
  transaction_type: 'income' | 'expense';
  category: string;
  description: string;
  amount: number;
  frequency: string;
  start_date: string;
  day_of_month: number;
  end_date?: string;
  notes?: string;
  property_id?: string;
  loan_id?: number;
}

interface CreateRecurringModalProps {
  onClose: () => void;
  onSuccess: () => void;
}

const PROPERTY_INCOME_CATEGORIES = [IncomeCategory.RENTAL];
const PROPERTY_EXPENSE_CATEGORIES = [
  ExpenseCategory.LOAN_INTEREST,
  ExpenseCategory.PROPERTY_TAX,
  ExpenseCategory.DEPRECIATION,
  ExpenseCategory.MAINTENANCE,
  ExpenseCategory.UTILITIES,
];

export const CreateRecurringModal: React.FC<CreateRecurringModalProps> = ({
  onClose,
  onSuccess,
}) => {
  const { t } = useTranslation();
  const { alert: showAlert } = useConfirm();
  const { register, handleSubmit, watch, formState: { errors } } = useForm<FormData>({
    defaultValues: {
      transaction_type: 'income',
      frequency: 'monthly',
      day_of_month: 1,
    },
  });
  const [properties, setProperties] = useState<Property[]>([]);
  const [loans, setLoans] = useState<{ id: number; label: string }[]>([]);
  const [loading, setLoading] = useState(false);

  const txType = watch('transaction_type');
  const category = watch('category');

  const needsProperty =
    (txType === 'income' && PROPERTY_INCOME_CATEGORIES.includes(category as IncomeCategory)) ||
    (txType === 'expense' && PROPERTY_EXPENSE_CATEGORIES.includes(category as ExpenseCategory));
  const needsLoan = category === ExpenseCategory.LOAN_INTEREST;

  useEffect(() => {
    const load = async () => {
      try {
        const res = await propertyService.getProperties(false);
        setProperties(
          res.properties
            .filter((p: any) => p.status === 'active')
            .map((p: any) => ({ id: p.id, address: p.address, status: p.status }))
        );
      } catch (e) { console.error(e); }
      try {
        const loansData = await loanService.list();
        setLoans(
          loansData
            .filter((l: any) => l.is_active)
            .map((l: any) => ({ id: l.id, label: `${l.lender_name} (${l.property_id})` }))
        );
      } catch (e) { console.error(e); }
    };
    load();
  }, []);

  const getCategoryOptions = () => {
    if (txType === 'income') {
      return Object.values(IncomeCategory).map(c => ({
        value: c,
        label: t(`transactions.categories.${c}`),
      }));
    }
    return Object.values(ExpenseCategory).map(c => ({
      value: c,
      label: t(`transactions.categories.${c}`),
    }));
  };

  const onSubmit = async (data: FormData) => {
    try {
      setLoading(true);
      await recurringService.create({
        recurring_type: 'manual',
        description: data.description,
        amount: data.amount,
        transaction_type: data.transaction_type,
        category: data.category,
        frequency: data.frequency as RecurrenceFrequency,
        start_date: data.start_date,
        end_date: data.end_date || undefined,
        day_of_month: data.day_of_month,
        notes: data.notes || undefined,
        property_id: needsProperty ? data.property_id || undefined : undefined,
        loan_id: needsLoan ? data.loan_id || undefined : undefined,
      });
      onSuccess();
    } catch (error) {
      console.error('Failed to create recurring transaction:', error);
      await showAlert(t('recurring.errors.createFailed'), { variant: 'danger' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="recurring-editor-overlay" onClick={onClose}>
      <div className="recurring-editor" onClick={(e) => e.stopPropagation()}>
        <div className="recurring-editor-header">
          <h2>➕ {t('recurring.create.title')}</h2>
          <button className="btn-close" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="recurring-editor-form">
          {/* Type: income / expense */}
          <div className="form-group">
            <label>{t('transactions.type')} <span className="required">*</span></label>
            <Select {...register('transaction_type')} value={watch('transaction_type') || ''}
              options={[
                { value: 'income', label: t('transactions.types.income') },
                { value: 'expense', label: t('transactions.types.expense') },
              ]} />
          </div>

          {/* Category */}
          <div className="form-group">
            <label>{t('transactions.category')} <span className="required">*</span></label>
            <Select {...register('category', { required: true })} value={watch('category') || ''}
              placeholder={t('transactions.selectCategory')}
              options={getCategoryOptions()} />
            {errors.category && (
              <span className="field-error">{t('recurring.errors.categoryRequired')}</span>
            )}
          </div>

          {/* Description */}
          <div className="form-group">
            <label>{t('transactions.description')} <span className="required">*</span></label>
            <input
              type="text"
              placeholder={t('transactions.descriptionPlaceholder')}
              {...register('description', { required: true, minLength: 3 })}
            />
            {errors.description && (
              <span className="field-error">{t('recurring.errors.descriptionRequired')}</span>
            )}
          </div>

          {/* Amount */}
          <div className="form-group">
            <label>{t('recurring.form.amount')} (€) <span className="required">*</span></label>
            <input
              type="number"
              step="0.01"
              {...register('amount', { required: true, min: 0.01, valueAsNumber: true })}
            />
            {errors.amount && (
              <span className="field-error">{t('recurring.errors.amountRequired')}</span>
            )}
          </div>

          {/* Property selector (conditional) */}
          {needsProperty && (
            <div className="form-group">
              <label>{t('recurring.form.property')}</label>
              <Select {...register('property_id')} value={watch('property_id') || ''}
                placeholder={t('recurring.form.selectProperty')}
                options={properties.map(p => ({
                  value: p.id,
                  label: p.address,
                }))} />
            </div>
          )}

          {/* Loan selector (conditional) */}
          {needsLoan && (
            <div className="form-group">
              <label>{t('recurring.form.loan')}</label>
              <Select {...register('loan_id', { valueAsNumber: true })} value={watch('loan_id')?.toString() || ''}
                placeholder={t('recurring.form.selectLoan')}
                options={loans.map(l => ({
                  value: String(l.id),
                  label: l.label,
                }))} />
            </div>
          )}

          {/* Frequency */}
          <div className="form-group">
            <label>{t('recurring.frequency.label')} <span className="required">*</span></label>
            <Select {...register('frequency')} value={watch('frequency') || ''}
              options={[
                { value: 'monthly', label: t('recurring.frequency.monthly') },
                { value: 'quarterly', label: t('recurring.frequency.quarterly') },
                { value: 'yearly', label: t('recurring.frequency.annually') },
                { value: 'weekly', label: t('recurring.frequency.weekly') },
              ]} />
          </div>

          {/* Start date + day of month */}
          <div className="form-row">
            <div className="form-group">
              <label>{t('recurring.form.startDate')} <span className="required">*</span></label>
              <input type="date" {...register('start_date', { required: true })} />
              {errors.start_date && (
                <span className="field-error">{t('recurring.errors.dateRequired')}</span>
              )}
            </div>
            <div className="form-group">
              <label>{t('recurring.form.dayOfMonth')} <span className="required">*</span></label>
              <input
                type="number"
                min="1"
                max="31"
                {...register('day_of_month', { required: true, min: 1, max: 31, valueAsNumber: true })}
              />
            </div>
          </div>

          {/* End date */}
          <div className="form-group">
            <label>{t('recurring.form.endDate')} ({t('common.optional')})</label>
            <input type="date" {...register('end_date')} />
          </div>

          {/* Notes */}
          <div className="form-group">
            <label>{t('recurring.form.notes')} ({t('common.optional')})</label>
            <textarea
              rows={2}
              placeholder={t('recurring.create.notesPlaceholder')}
              {...register('notes')}
            />
          </div>

          {/* Upload hint */}
          <div className="recurring-upload-hint">
            <span>📎</span>
            <span>
              {t('recurring.create.uploadHint')}{' '}
              <a href="/documents" target="_blank" rel="noopener noreferrer">
                {t('recurring.create.goToDocuments')}
              </a>
            </span>
          </div>

          <div className="form-actions">
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
              {loading ? t('common.saving') : t('common.create')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
