import { useEffect, useState, useCallback } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';
import {
  Transaction,
  TransactionType,
  IncomeCategory,
  ExpenseCategory,
} from '../../types/transaction';
import { usePropertyStore } from '../../stores/propertyStore';
import { suggestCategory } from '../../utils/categoryMatcher';
import './TransactionForm.css';

const transactionSchema = z.object({
  type: z.nativeEnum(TransactionType),
  amount: z.string().min(1, 'Amount is required'),
  date: z.string().min(1, 'Date is required'),
  description: z.string().min(3, 'Description must be at least 3 characters'),
  category: z.string().min(1, 'Category is required'),
  document_id: z.number().optional(),
  property_id: z.string().optional().nullable(),
  is_recurring: z.boolean().optional().default(false),
  recurring_frequency: z.string().optional(),
  recurring_start_date: z.string().optional(),
  recurring_end_date: z.string().optional(),
  recurring_day_of_month: z.number().optional(),
});

type TransactionFormData = z.infer<typeof transactionSchema>;

interface TransactionFormProps {
  transaction?: Transaction;
  onSubmit: (data: TransactionFormData) => void;
  onCancel: () => void;
}

const TransactionForm = ({
  transaction,
  onSubmit,
  onCancel,
}: TransactionFormProps) => {
  const { t } = useTranslation();
  const { properties, fetchProperties } = usePropertyStore();
  
  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<TransactionFormData>({
    resolver: zodResolver(transactionSchema),
    defaultValues: transaction
      ? {
          type: transaction.type,
          amount: transaction.amount.toString(),
          date: transaction.date.split('T')[0],
          description: transaction.description,
          category: transaction.category,
          document_id: transaction.document_id,
          property_id: transaction.property_id || null,
          is_recurring: transaction.is_recurring || false,
          recurring_frequency: transaction.recurring_frequency || 'monthly',
          recurring_start_date: transaction.recurring_start_date || '',
          recurring_end_date: transaction.recurring_end_date || '',
          recurring_day_of_month: transaction.recurring_day_of_month || 1,
        }
      : {
          type: TransactionType.EXPENSE,
          date: new Date().toISOString().split('T')[0],
          property_id: null,
          is_recurring: false,
          recurring_frequency: 'monthly',
          recurring_day_of_month: 1,
        },
  });

  const transactionType = watch('type');
  const category = watch('category');
  const isRecurring = watch('is_recurring');

  // Fetch properties on mount
  useEffect(() => {
    fetchProperties();
  }, [fetchProperties]);

  // ── Auto-suggest category from description ────────────────────────────
  const [autoSuggested, setAutoSuggested] = useState(false);
  const description = watch('description');

  const tryAutoSuggest = useCallback(
    (desc: string) => {
      if (!desc || desc.length < 3) return;
      // Don't overwrite if user already picked a category manually
      const currentCat = watch('category');
      if (currentCat && !autoSuggested) return;

      const typeValue = transactionType === TransactionType.INCOME ? 'income' : 'expense';
      const result = suggestCategory(desc, typeValue);
      if (result) {
        setValue('category', result.category);
        setAutoSuggested(true);
      }
    },
    [transactionType, setValue, watch, autoSuggested]
  );

  // Re-suggest when description changes (debounced via useEffect)
  useEffect(() => {
    if (!transaction && description && description.length >= 3) {
      const timer = setTimeout(() => tryAutoSuggest(description), 400);
      return () => clearTimeout(timer);
    }
  }, [description, transaction, tryAutoSuggest]);

  // Reset category when type changes
  useEffect(() => {
    if (!transaction) {
      setValue('category', '');
      setAutoSuggested(false);
    }
  }, [transactionType, transaction, setValue]);

  const getCategoryOptions = () => {
    if (transactionType === TransactionType.INCOME) {
      return Object.values(IncomeCategory).map((cat) => ({
        value: cat,
        label: t(`transactions.categories.${cat}`),
      }));
    } else {
      return Object.values(ExpenseCategory).map((cat) => ({
        value: cat,
        label: t(`transactions.categories.${cat}`),
      }));
    }
  };

  // Check if category is property-related
  const isPropertyRelatedCategory = () => {
    if (transactionType === TransactionType.INCOME) {
      return category === IncomeCategory.RENTAL;
    } else {
      const propertyExpenseCategories = [
        ExpenseCategory.LOAN_INTEREST,
        ExpenseCategory.PROPERTY_TAX,
        ExpenseCategory.DEPRECIATION,
        ExpenseCategory.MAINTENANCE,
        ExpenseCategory.UTILITIES,
      ];
      return propertyExpenseCategories.includes(category as ExpenseCategory);
    }
  };

  // Get active properties for dropdown
  const activeProperties = properties.filter(p => p.status === 'active');

  return (
    <form className="transaction-form" onSubmit={handleSubmit(onSubmit)}>
      <h2>
        {transaction
          ? t('transactions.editTransaction')
          : t('transactions.addTransaction')}
      </h2>

      <div className="form-group">
        <label htmlFor="type">
          {t('transactions.type')} <span className="required">*</span>
        </label>
        <select id="type" {...register('type')} disabled={!!transaction}>
          <option value={TransactionType.INCOME}>
            {t('transactions.types.income')}
          </option>
          <option value={TransactionType.EXPENSE}>
            {t('transactions.types.expense')}
          </option>
        </select>
        {errors.type && <span className="error">{errors.type.message}</span>}
      </div>

      <div className="form-row">
        <div className="form-group">
          <label htmlFor="amount">
            {t('transactions.amount')} <span className="required">*</span>
          </label>
          <input
            id="amount"
            type="number"
            step="0.01"
            min="0"
            placeholder="0.00"
            {...register('amount')}
          />
          {errors.amount && <span className="error">{errors.amount.message}</span>}
        </div>

        <div className="form-group">
          <label htmlFor="date">
            {t('transactions.date')} <span className="required">*</span>
          </label>
          <input id="date" type="date" {...register('date')} />
          {errors.date && <span className="error">{errors.date.message}</span>}
        </div>
      </div>

      <div className="form-group">
        <label htmlFor="description">
          {t('transactions.description')} <span className="required">*</span>
        </label>
        <input
          id="description"
          type="text"
          placeholder={t('transactions.descriptionPlaceholder')}
          {...register('description')}
        />
        {errors.description && (
          <span className="error">{errors.description.message}</span>
        )}
      </div>

      <div className="form-group">
        <label htmlFor="category">
          {t('transactions.category')} <span className="required">*</span>
        </label>
        <select
          id="category"
          {...register('category', {
            onChange: () => {
              // User manually picked — clear auto-suggest flag
              setAutoSuggested(false);
            },
          })}
        >
          <option value="">{t('transactions.selectCategory')}</option>
          {getCategoryOptions().map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        {autoSuggested && (
          <span className="auto-suggest-hint">
            🤖 {t('transactions.autoSuggestHint')}
          </span>
        )}
        {errors.category && <span className="error">{errors.category.message}</span>}
      </div>

      {isPropertyRelatedCategory() && (
        <div className="form-group">
          <label htmlFor="property_id">
            {t('transactions.property')}
            {category === IncomeCategory.RENTAL && (
              <span className="field-hint"> ({t('transactions.propertyRecommended')})</span>
            )}
          </label>
          <select id="property_id" {...register('property_id')}>
            <option value="">{t('transactions.selectProperty')}</option>
            {activeProperties.map((property) => (
              <option key={property.id} value={property.id}>
                {property.address}
              </option>
            ))}
          </select>
          {activeProperties.length === 0 && (
            <span className="field-hint">
              {t('transactions.noPropertiesAvailable')}{' '}
              <a href="/properties">{t('transactions.addPropertyFirst')}</a>
            </span>
          )}
        </div>
      )}

      {/* Recurring Transaction Toggle */}
      <div className="form-group recurring-toggle">
        <label className="toggle-label">
          <input
            type="checkbox"
            {...register('is_recurring')}
          />
          <span className="toggle-text">🔄 {t('recurring.title')}</span>
          <span className="toggle-hint">（{t('transactions.recurringHint')}）</span>
        </label>
      </div>

      {isRecurring && (
        <div className="recurring-settings">
          <div className="recurring-settings-header">{t('recurring.settingsTitle')}</div>
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="recurring_frequency">{t('recurring.frequency.label')} <span className="required">*</span></label>
              <select id="recurring_frequency" {...register('recurring_frequency')}>
                <option value="monthly">{t('recurring.frequency.monthly')}</option>
                <option value="quarterly">{t('recurring.frequency.quarterly')}</option>
                <option value="yearly">{t('recurring.frequency.annually')}</option>
                <option value="weekly">{t('recurring.frequency.weekly')}</option>
              </select>
            </div>
            <div className="form-group">
              <label htmlFor="recurring_day_of_month">{t('recurring.form.dayOfMonth')}</label>
              <input
                id="recurring_day_of_month"
                type="number"
                min="1"
                max="31"
                {...register('recurring_day_of_month', { valueAsNumber: true })}
              />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="recurring_start_date">{t('recurring.form.startDate')} <span className="required">*</span></label>
              <input
                id="recurring_start_date"
                type="date"
                {...register('recurring_start_date')}
              />
            </div>
            <div className="form-group">
              <label htmlFor="recurring_end_date">{t('recurring.form.endDate')}（{t('recurring.form.endDateHelp')}）</label>
              <input
                id="recurring_end_date"
                type="date"
                {...register('recurring_end_date')}
              />
            </div>
          </div>
        </div>
      )}

      {transaction?.is_deductible !== undefined && (
        <div className="form-info">
          <div className="deductibility-info">
            <strong>{t('transactions.deductible')}:</strong>{' '}
            {transaction.is_deductible ? (
              <span className="badge badge-success">{t('common.yes')}</span>
            ) : (
              <span className="badge badge-secondary">{t('common.no')}</span>
            )}
          </div>
        </div>
      )}

      {transaction?.document_id && (
        <div className="form-info">
          <div className="document-link">
            <span>📎 {t('transactions.linkedDocument')}</span>
            <a href={`/documents/${transaction.document_id}`}>
              {t('transactions.viewDocument')}
            </a>
          </div>
        </div>
      )}

      <div className="form-actions">
        <button
          type="button"
          className="btn btn-secondary"
          onClick={onCancel}
          disabled={isSubmitting}
        >
          {t('common.cancel')}
        </button>
        <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
          {isSubmitting ? t('common.saving') : t('common.save')}
        </button>
      </div>
    </form>
  );
};

export default TransactionForm;
