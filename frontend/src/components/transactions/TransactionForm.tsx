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
  LineItem,
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
  is_deductible: z.boolean().optional(),
  deduction_reason: z.string().optional(),
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
          is_deductible: transaction.is_deductible ?? false,
          deduction_reason: transaction.deduction_reason || '',
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
          is_deductible: false,
          deduction_reason: '',
          is_recurring: false,
          recurring_frequency: 'monthly',
          recurring_day_of_month: 1,
        },
  });

  const transactionType = watch('type');
  const category = watch('category');
  const isRecurring = watch('is_recurring');
  const isDeductible = watch('is_deductible');

  // Track whether user is overriding AI decision
  const [isOverriding, setIsOverriding] = useState(false);
  const aiDecision = transaction?.is_deductible;
  const hasAiDecision = transaction?.is_deductible !== undefined;

  // Line items state
  const [lineItems, setLineItems] = useState<LineItem[]>(
    transaction?.line_items && transaction.line_items.length > 0
      ? transaction.line_items
      : []
  );
  const hasLineItems = lineItems.length > 0;

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

  // ── Line item helpers ─────────────────────────────────────────────
  const updateLineItem = (index: number, field: keyof LineItem, value: any) => {
    setLineItems(prev => prev.map((item, i) =>
      i === index ? { ...item, [field]: value } : item
    ));
  };

  const removeLineItem = (index: number) => {
    setLineItems(prev => prev.filter((_, i) => i !== index));
  };

  const addLineItem = () => {
    setLineItems(prev => [
      ...prev,
      {
        description: '',
        amount: 0,
        quantity: 1,
        is_deductible: false,
        sort_order: prev.length,
      },
    ]);
  };

  // All expense categories for line item dropdown
  const lineItemCategoryOptions = Object.values(ExpenseCategory).map(cat => ({
    value: cat,
    label: t(`transactions.categories.${cat}`),
  }));

  // Wrap onSubmit to inject reviewed/locked when user overrides AI decision
  const handleFormSubmit = (data: TransactionFormData) => {
    const submitData: any = { ...data };
    if (isOverriding && isDeductible !== aiDecision) {
      submitData.reviewed = true;
      submitData.locked = true;
      // Prefix reason with [User Override] marker
      if (submitData.deduction_reason && !submitData.deduction_reason.startsWith('[')) {
        submitData.deduction_reason = `[Benutzer-Korrektur] ${submitData.deduction_reason}`;
      }
    }
    // Include line items if present
    if (hasLineItems) {
      submitData.line_items = lineItems
        .filter(li => li.description.trim() !== '' && li.amount > 0)
        .map((li, idx) => ({
          ...li,
          sort_order: idx,
        }));
    }
    onSubmit(submitData);
  };

  return (
    <form className="transaction-form" onSubmit={handleSubmit(handleFormSubmit)}>
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

      {/* Deductibility Override Section — only for expenses */}
      {transaction && hasAiDecision && transactionType !== TransactionType.INCOME && (
        <div className="deductibility-override-section">
          <div className="deductibility-current">
            <span className="deductibility-label">{t('transactions.deductible')}:</span>
            {!isOverriding ? (
              <>
                {transaction.is_deductible ? (
                  <span className="badge badge-success">✓ {t('transactions.deductibleYes')}</span>
                ) : (
                  <span className="badge badge-secondary">✗ {t('transactions.notDeductible')}</span>
                )}
                <span className="ai-badge">🤖 AI</span>
                <button
                  type="button"
                  className="btn-override"
                  onClick={() => setIsOverriding(true)}
                >
                  ✏️ {t('transactions.overrideDeductibility')}
                </button>
              </>
            ) : (
              <div className="override-controls">
                <label className="override-toggle">
                  <input
                    type="checkbox"
                    {...register('is_deductible')}
                  />
                  <span className={`override-status ${isDeductible ? 'deductible' : 'not-deductible'}`}>
                    {isDeductible ? t('transactions.deductibleYes') : t('transactions.notDeductible')}
                  </span>
                </label>
                {isDeductible !== aiDecision && (
                  <div className="override-reason-group">
                    <label htmlFor="deduction_reason">{t('transactions.overrideReason')}</label>
                    <textarea
                      id="deduction_reason"
                      rows={2}
                      placeholder={t('transactions.overrideReasonPlaceholder')}
                      {...register('deduction_reason')}
                    />
                    <span className="override-hint">⚠️ {t('transactions.overrideWarning')}</span>
                  </div>
                )}
                <button
                  type="button"
                  className="btn-cancel-override"
                  onClick={() => {
                    setIsOverriding(false);
                    setValue('is_deductible', aiDecision ?? false);
                    setValue('deduction_reason', transaction.deduction_reason || '');
                  }}
                >
                  {t('transactions.cancelOverride')}
                </button>
              </div>
            )}
          </div>
          {transaction.deduction_reason && !isOverriding && (
            <div className="ai-reason-display">
              <span className="ai-reason-text">
                {transaction.deduction_reason.includes(' | ')
                  ? transaction.deduction_reason.split(' | ').map((part, i) => (
                      <span key={i}>
                        {i === 1 && <span>💡 </span>}
                        {part}
                        {i === 0 && <br />}
                      </span>
                    ))
                  : transaction.deduction_reason}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Line Items Section — only when editing a transaction that has them, or user adds them */}
      {transaction && transactionType === TransactionType.EXPENSE && (
        <div className="line-items-section">
          <div className="line-items-header">
            <span className="line-items-title">📋 {t('transactions.lineItems.title')}</span>
            {!hasLineItems && (
              <button type="button" className="btn-add-line-item" onClick={addLineItem}>
                + {t('transactions.lineItems.addItem')}
              </button>
            )}
          </div>

          {hasLineItems && (
            <div className="line-items-edit-list">
              {lineItems.map((item, idx) => (
                <div key={idx} className="line-item-edit-row">
                  <div className="line-item-edit-main">
                    <input
                      type="text"
                      className="line-item-input line-item-desc-input"
                      placeholder={t('transactions.lineItems.descriptionPlaceholder')}
                      value={item.description}
                      onChange={e => updateLineItem(idx, 'description', e.target.value)}
                    />
                    <input
                      type="number"
                      className="line-item-input line-item-amount-input"
                      step="0.01"
                      min="0"
                      placeholder="0.00"
                      value={item.amount || ''}
                      onChange={e => updateLineItem(idx, 'amount', parseFloat(e.target.value) || 0)}
                    />
                    <button
                      type="button"
                      className="btn-remove-line-item"
                      onClick={() => removeLineItem(idx)}
                      title={t('transactions.lineItems.removeItem')}
                    >
                      ✕
                    </button>
                  </div>
                  <div className="line-item-edit-meta">
                    <select
                      className="line-item-select"
                      value={item.category || ''}
                      onChange={e => updateLineItem(idx, 'category', e.target.value || undefined)}
                    >
                      <option value="">{t('transactions.lineItems.selectCategory')}</option>
                      {lineItemCategoryOptions.map(opt => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                    <label className="line-item-deductible-toggle">
                      <input
                        type="checkbox"
                        checked={item.is_deductible}
                        onChange={e => updateLineItem(idx, 'is_deductible', e.target.checked)}
                      />
                      <span className={item.is_deductible ? 'deductible-yes' : 'deductible-no'}>
                        {item.is_deductible ? t('transactions.deductibleYes') : t('transactions.notDeductible')}
                      </span>
                    </label>
                  </div>
                </div>
              ))}
              <button type="button" className="btn-add-line-item" onClick={addLineItem}>
                + {t('transactions.lineItems.addItem')}
              </button>
            </div>
          )}
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
