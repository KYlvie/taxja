import { useEffect, useState, useCallback } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';
import { FileText } from 'lucide-react';
import { translateDeductionReason } from '../../utils/translateDeductionReason';
import Select from '../common/Select';
import {
  isExpenseTransactionType,
  transactionTypeRequiresCategory,
  Transaction,
  TransactionType,
  IncomeCategory,
  ExpenseCategory,
  LineItem,
} from '../../types/transaction';
import { usePropertyStore } from '../../stores/propertyStore';
import { suggestCategory } from '../../utils/categoryMatcher';
import { formatTransactionCategoryLabel } from '../../utils/formatTransactionCategoryLabel';
import { formatCurrency } from '../../utils/locale';
import './TransactionForm.css';

const transactionSchema = z.object({
  type: z.nativeEnum(TransactionType),
  amount: z.string().min(1, 'Amount is required'),
  date: z.string().min(1, 'Date is required'),
  description: z.string().min(3, 'Description must be at least 3 characters'),
  category: z.string().optional(),
  document_id: z.number().optional(),
  property_id: z.string().optional().nullable(),
  is_deductible: z.boolean().optional(),
  deduction_reason: z.string().optional(),
  is_recurring: z.boolean().optional().default(false),
  recurring_frequency: z.string().optional(),
  recurring_start_date: z.string().optional(),
  recurring_end_date: z.string().optional(),
  recurring_day_of_month: z.number().optional(),
}).superRefine((data, ctx) => {
  if (transactionTypeRequiresCategory(data.type) && !data.category) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['category'],
      message: 'Category is required',
    });
  }
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
  const { t, i18n } = useTranslation();
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
          category: transaction.category || '',
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
  const amountValue = watch('amount');
  const requiresCategory = transactionTypeRequiresCategory(transactionType);
  const isExpenseType = isExpenseTransactionType(transactionType);

  // Track whether user is overriding AI decision
  const [isOverriding, setIsOverriding] = useState(false);
  const aiDecision = transaction?.is_deductible;
  const hasAiDecision = transaction?.is_deductible !== undefined;
  const [lineItemSaveError, setLineItemSaveError] = useState<string | null>(null);

  // Line items state
  const [lineItems, setLineItems] = useState<LineItem[]>(
    transaction?.line_items && transaction.line_items.length > 0
      ? transaction.line_items
      : []
  );
  const hasLineItems = lineItems.length > 0;
  const parsedTransactionAmount = Number.parseFloat(String(amountValue || '0'));
  const normalizedTransactionAmount = Number.isFinite(parsedTransactionAmount)
    ? parsedTransactionAmount
    : 0;
  const validLineItems = lineItems.filter(
    (lineItem) => lineItem.description.trim() !== '' && Number(lineItem.amount) > 0
  );
  const lineItemsTotal = Number(
    validLineItems
      .reduce(
        (sum, lineItem) => sum + (Number(lineItem.amount) || 0) * (Number(lineItem.quantity ?? 1) || 1),
        0
      )
      .toFixed(2)
  );
  const lineItemsDelta = Number((normalizedTransactionAmount - lineItemsTotal).toFixed(2));
  const hasLineItemMismatch = (
    isExpenseType
    && hasLineItems
    && validLineItems.length > 0
    && Math.abs(lineItemsDelta) > 0.01
  );
  const lineItemsParentAmountLabel = formatCurrency(normalizedTransactionAmount, i18n.language);
  const lineItemsTotalLabel = formatCurrency(lineItemsTotal, i18n.language);
  const lineItemsDeltaLabel = formatCurrency(Math.abs(lineItemsDelta), i18n.language);

  useEffect(() => {
    if (lineItemSaveError) {
      setLineItemSaveError(null);
    }
  }, [amountValue, lineItems, lineItemSaveError]);

  // Fetch properties on mount
  useEffect(() => {
    fetchProperties();
  }, [fetchProperties]);

  // ── Auto-suggest category from description ────────────────────────────
  const [autoSuggested, setAutoSuggested] = useState(false);
  const description = watch('description');

  const tryAutoSuggest = useCallback(
    (desc: string) => {
      if (!transactionTypeRequiresCategory(transactionType)) return;
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
    if (
      !transaction ||
      transaction.type !== transactionType ||
      !transactionTypeRequiresCategory(transactionType)
    ) {
      setValue('category', '');
      setAutoSuggested(false);
    }
  }, [transactionType, transaction, setValue]);

  const getCategoryOptions = () => {
    if (!transactionTypeRequiresCategory(transactionType)) {
      return [];
    }
    if (transactionType === TransactionType.INCOME) {
      return Object.values(IncomeCategory).map((cat) => ({
        value: cat,
        label: formatTransactionCategoryLabel(cat, t),
      }));
    } else {
      return Object.values(ExpenseCategory).map((cat) => ({
        value: cat,
        label: formatTransactionCategoryLabel(cat, t),
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
    label: formatTransactionCategoryLabel(cat, t),
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
    if (isExpenseType && hasLineItems) {
      submitData.line_items = lineItems
        .filter(li => li.description.trim() !== '' && li.amount > 0)
        .map((li, idx) => ({
          ...li,
          sort_order: idx,
        }));
      const reconciledTotal = Number(
        submitData.line_items
          .reduce(
            (sum: number, lineItem: any) =>
              sum + (Number(lineItem.amount) || 0) * (Number(lineItem.quantity ?? 1) || 1),
            0
          )
          .toFixed(2)
      );
      const expectedTotal = Number(Number(data.amount || 0).toFixed(2));
      if (submitData.line_items.length > 0 && Math.abs(expectedTotal - reconciledTotal) > 0.01) {
        setLineItemSaveError(
          t('receiptReview.syncAmountMismatch', {
            expected: formatCurrency(expectedTotal, i18n.language),
            reconstructed: formatCurrency(reconciledTotal, i18n.language),
            defaultValue:
              'The invoice total {{expected}} does not match the reconstructed line-item total {{reconstructed}}. Check the line-item amounts or VAT on this invoice, then save again.',
          })
        );
        return;
      }
      // Derive transaction-level is_deductible from line items
      const validItems = submitData.line_items;
      const anyDeductible = validItems.some((li: any) => li.is_deductible);
      submitData.is_deductible = anyDeductible;
    } else if (!isExpenseType && transaction?.line_items?.length) {
      submitData.line_items = [];
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
        <Select id="type" {...register('type')}
          value={watch('type')}
          options={[
            { value: TransactionType.INCOME, label: t('transactions.types.income') },
            { value: TransactionType.EXPENSE, label: t('transactions.types.expense') },
            { value: TransactionType.ASSET_ACQUISITION, label: t('transactions.types.asset_acquisition') },
            { value: TransactionType.LIABILITY_DRAWDOWN, label: t('transactions.types.liability_drawdown') },
            { value: TransactionType.LIABILITY_REPAYMENT, label: t('transactions.types.liability_repayment') },
            { value: TransactionType.TAX_PAYMENT, label: t('transactions.types.tax_payment') },
            { value: TransactionType.TRANSFER, label: t('transactions.types.transfer') },
          ]} />
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

      {requiresCategory && (
      <div className="form-group">
        <label htmlFor="category">
          {t('transactions.category')} <span className="required">*</span>
        </label>
        <Select id="category"
          {...register('category', { onChange: () => setAutoSuggested(false) })}
          value={watch('category') || ''}
          placeholder={t('transactions.selectCategory')}
          options={getCategoryOptions()} />
        {autoSuggested && (
          <span className="auto-suggest-hint">
            🤖 {t('transactions.autoSuggestHint')}
          </span>
        )}
        {errors.category && <span className="error">{errors.category.message}</span>}
      </div>
      )}

      {requiresCategory && isPropertyRelatedCategory() && (
        <div className="form-group">
          <label htmlFor="property_id">
            {t('transactions.property')}
            {category === IncomeCategory.RENTAL && (
              <span className="field-hint"> ({t('transactions.propertyRecommended')})</span>
            )}
          </label>
          <Select id="property_id" {...register('property_id')}
            value={watch('property_id') || ''}
            placeholder={t('transactions.selectProperty')}
            options={activeProperties.map(p => ({ value: String(p.id), label: p.address }))} />
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
              <Select id="recurring_frequency" {...register('recurring_frequency')}
                value={watch('recurring_frequency') || 'monthly'}
                options={[
                  { value: 'monthly', label: t('recurring.frequency.monthly') },
                  { value: 'quarterly', label: t('recurring.frequency.quarterly') },
                  { value: 'yearly', label: t('recurring.frequency.annually') },
                  { value: 'weekly', label: t('recurring.frequency.weekly') },
                ]} />
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
      {transaction && hasAiDecision && isExpenseType && !hasLineItems && (
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
                        {translateDeductionReason(part, i18n.language)}
                        {i === 0 && <br />}
                      </span>
                    ))
                  : translateDeductionReason(transaction.deduction_reason, i18n.language)}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Deductibility summary derived from line items — read-only */}
      {transaction && isExpenseType && hasLineItems && (
        <div className="deductibility-override-section">
          <div className="deductibility-current">
            <span className="deductibility-label">{t('transactions.deductible')}:</span>
            {(() => {
              const deductCount = lineItems.filter(li => li.is_deductible).length;
              const total = lineItems.length;
              if (deductCount === total) return <span className="badge badge-success">✓ {t('transactions.deductibleYes')}</span>;
              if (deductCount === 0) return <span className="badge badge-secondary">✗ {t('transactions.notDeductible')}</span>;
              return <span className="badge badge-warning">◐ {t('transactions.partiallyDeductible', 'Partial')} ({deductCount}/{total})</span>;
            })()}
            <span className="ai-hint-text" style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
              {t('transactions.deductibilityDerivedFromItems', '由明细条目决定')}
            </span>
          </div>
        </div>
      )}

      {/* Line Items Section — only when editing a transaction that has them, or user adds them */}
      {transaction && isExpenseType && (
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
              <div
                className={`line-items-balance-summary${hasLineItemMismatch ? ' line-items-balance-summary-error' : ''}`}
              >
                <span>
                  {t('transactions.amount')}:
                  <strong>{lineItemsParentAmountLabel}</strong>
                </span>
                <span>
                  {t('transactions.lineItems.title')} {t('common.total')}:
                  <strong>{lineItemsTotalLabel}</strong>
                </span>
                <span>
                  {t('dashboard.remaining')}:
                  <strong>{lineItemsDeltaLabel}</strong>
                </span>
              </div>
              {hasLineItemMismatch ? (
                <span className="error line-items-balance-error">
                  {lineItemSaveError || t('receiptReview.syncAmountMismatch', {
                    expected: lineItemsParentAmountLabel,
                    reconstructed: lineItemsTotalLabel,
                    defaultValue:
                      'The invoice total {{expected}} does not match the reconstructed line-item total {{reconstructed}}. Check the line-item amounts or VAT on this invoice, then save again.',
                  })}
                </span>
              ) : null}
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
                    <Select value={item.category || ''}
                      onChange={v => updateLineItem(idx, 'category', v || undefined)}
                      placeholder={t('transactions.lineItems.selectCategory')}
                      options={lineItemCategoryOptions} size="sm" />
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
            <FileText size={16} />
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
        <button type="submit" className="btn btn-primary" disabled={isSubmitting || hasLineItemMismatch}>
          {isSubmitting ? t('common.saving') : t('common.save')}
        </button>
      </div>
    </form>
  );
};

export default TransactionForm;
