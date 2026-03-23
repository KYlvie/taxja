import { FormEvent, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import Select from '../common/Select';
import DateInput from '../common/DateInput';
import { getLocaleForLanguage } from '../../utils/locale';
import {
  LiabilityCreatePayload,
  LiabilityRecord,
  LiabilityReportCategory,
  LiabilityType,
  LiabilityUpdatePayload,
} from '../../types/liability';

type PropertyOption = {
  value: string;
  label: string;
};

type LiabilityFormProps = {
  initialValue?: LiabilityRecord | null;
  propertyOptions: PropertyOption[];
  submitting?: boolean;
  onCancel: () => void;
  onSubmit: (payload: LiabilityCreatePayload | LiabilityUpdatePayload) => Promise<void> | void;
};

type FormState = {
  liability_type: LiabilityType;
  display_name: string;
  currency: string;
  lender_name: string;
  principal_amount: string;
  outstanding_balance: string;
  interest_rate: string;
  start_date: string;
  end_date: string;
  monthly_payment: string;
  tax_relevant: boolean;
  tax_relevance_reason: string;
  report_category: LiabilityReportCategory;
  linked_property_id: string;
  notes: string;
  create_recurring_plan: boolean;
  recurring_day_of_month: string;
};

const LIABILITY_TYPE_OPTIONS: { value: LiabilityType; label: string }[] = [
  { value: 'property_loan', label: 'Property loan' },
  { value: 'business_loan', label: 'Business loan' },
  { value: 'owner_loan', label: 'Owner loan' },
  { value: 'family_loan', label: 'Family loan' },
  { value: 'other_liability', label: 'Other liability' },
];

const REPORT_CATEGORY_OPTIONS: { value: LiabilityReportCategory; label: string }[] = [
  { value: 'darlehen_und_kredite', label: 'Loans and credit' },
  { value: 'sonstige_verbindlichkeiten', label: 'Other liabilities' },
];

const toInputValue = (value: number | null | undefined) => (value == null ? '' : String(value));

const buildInitialState = (value?: LiabilityRecord | null): FormState => ({
  liability_type: value?.liability_type || 'business_loan',
  display_name: value?.display_name || '',
  currency: value?.currency || 'EUR',
  lender_name: value?.lender_name || '',
  principal_amount: toInputValue(value?.principal_amount),
  outstanding_balance: toInputValue(value?.outstanding_balance),
  interest_rate: toInputValue(value?.interest_rate ?? undefined),
  start_date: value?.start_date || new Date().toISOString().slice(0, 10),
  end_date: value?.end_date || '',
  monthly_payment: toInputValue(value?.monthly_payment ?? undefined),
  tax_relevant: Boolean(value?.tax_relevant),
  tax_relevance_reason: value?.tax_relevance_reason || '',
  report_category: value?.report_category || 'darlehen_und_kredite',
  linked_property_id: value?.linked_property_id || '',
  notes: value?.notes || '',
  create_recurring_plan: false,
  recurring_day_of_month: '',
});

const LiabilityForm = ({
  initialValue,
  propertyOptions,
  submitting = false,
  onCancel,
  onSubmit,
}: LiabilityFormProps) => {
  const { t, i18n } = useTranslation();
  const [state, setState] = useState<FormState>(() => buildInitialState(initialValue));

  useEffect(() => {
    setState(buildInitialState(initialValue));
  }, [initialValue]);

  const typeOptions = useMemo(
    () =>
      LIABILITY_TYPE_OPTIONS.map((option) => ({
        value: option.value,
        label: t(`liabilities.type.${option.value}`, option.label),
      })),
    [t],
  );

  const reportOptions = useMemo(
    () =>
      REPORT_CATEGORY_OPTIONS.map((option) => ({
        value: option.value,
        label: t(`liabilities.reportCategory.${option.value}`, option.label),
      })),
    [t],
  );

  const propertySelectOptions = useMemo(
    () => [
      { value: '', label: t('liabilities.fields.noPropertyLink') },
      ...propertyOptions,
    ],
    [propertyOptions, t],
  );

  const supportingDocumentLink = useMemo(() => {
    const params = new URLSearchParams();
    params.set('type', state.liability_type === 'other_liability' ? 'other' : 'loan_contract');
    if (state.linked_property_id) {
      params.set('property_id', state.linked_property_id);
    }
    return `/documents?${params.toString()}`;
  }, [state.liability_type, state.linked_property_id]);

  const updateField = <K extends keyof FormState>(field: K, value: FormState[K]) => {
    setState((current) => ({ ...current, [field]: value }));
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();

    const payload: LiabilityCreatePayload | LiabilityUpdatePayload = {
      liability_type: state.liability_type,
      display_name: state.display_name.trim(),
      currency: state.currency.trim().toUpperCase(),
      lender_name: state.lender_name.trim(),
      principal_amount: Number(state.principal_amount),
      outstanding_balance: Number(state.outstanding_balance),
      start_date: state.start_date,
      tax_relevant: state.tax_relevant,
      report_category: state.report_category,
    };

    if (state.interest_rate !== '') {
      payload.interest_rate = Number(state.interest_rate);
    }
    if (state.end_date) {
      payload.end_date = state.end_date;
    }
    if (state.monthly_payment !== '') {
      payload.monthly_payment = Number(state.monthly_payment);
    }
    if (state.tax_relevance_reason.trim()) {
      payload.tax_relevance_reason = state.tax_relevance_reason.trim();
    }
    if (state.linked_property_id) {
      payload.linked_property_id = state.linked_property_id;
    }
    if (state.notes.trim()) {
      payload.notes = state.notes.trim();
    }

    if (!initialValue) {
      payload.create_recurring_plan = state.create_recurring_plan;
      if (state.create_recurring_plan && state.recurring_day_of_month) {
        payload.recurring_day_of_month = Number(state.recurring_day_of_month);
      }
    }

    await onSubmit(payload);
  };

  return (
    <section className="liability-form">
      <h2>
        {initialValue
          ? t('liabilities.form.editTitle')
          : t('liabilities.form.createTitle')}
      </h2>

      {(!initialValue || initialValue.requires_supporting_document) && (
        <div className="liability-doc-callout">
          <div>
            <strong>{t('liabilities.documents.manualUploadTitle', 'Add the contract or proof file for this liability')}</strong>
            <p>
              {t('liabilities.documents.manualUploadHint', 'Manual liabilities can be created first, but uploading the linked contract or proof keeps the document trail complete and lets Taxja manage it like property-backed records.')}
            </p>
          </div>
          <Link className="btn btn-secondary btn-sm" to={supportingDocumentLink}>
            {t('liabilities.documents.uploadSupportingDocument', 'Upload contract / proof')}
          </Link>
        </div>
      )}

      <form className="liability-form-content" onSubmit={handleSubmit}>
        <div className="liability-form-section">
          <div className="liability-form-row">
            <div className="liability-form-field">
              <label htmlFor="liability-type">{t('liabilities.fields.liabilityType')} <span className="required">*</span></label>
              <Select
                id="liability-type"
                value={state.liability_type}
                onChange={(value) => updateField('liability_type', value as LiabilityType)}
                options={typeOptions}
              />
            </div>

            <div className="liability-form-field">
              <label htmlFor="liability-report-category">{t('liabilities.fields.reportCategory')}</label>
              <Select
                id="liability-report-category"
                value={state.report_category}
                onChange={(value) => updateField('report_category', value as LiabilityReportCategory)}
                options={reportOptions}
              />
            </div>
          </div>

          <div className="liability-form-field liability-form-field--full">
            <label htmlFor="liability-display-name">{t('liabilities.fields.displayName')} <span className="required">*</span></label>
            <input
              id="liability-display-name"
              type="text"
              value={state.display_name}
              onChange={(event) => updateField('display_name', event.target.value)}
              required
            />
          </div>

          <div className="liability-form-row">
            <div className="liability-form-field">
              <label htmlFor="liability-lender">{t('liabilities.fields.lenderName')}</label>
              <input
                id="liability-lender"
                type="text"
                value={state.lender_name}
                onChange={(event) => updateField('lender_name', event.target.value)}
                required
              />
            </div>

            <div className="liability-form-field">
              <label htmlFor="liability-currency">{t('liabilities.fields.currency')}</label>
              <input
                id="liability-currency"
                type="text"
                maxLength={3}
                value={state.currency}
                onChange={(event) => updateField('currency', event.target.value.toUpperCase())}
                required
              />
            </div>
          </div>
        </div>

        <div className="liability-form-section">
          <div className="liability-form-row">
            <div className="liability-form-field">
              <label htmlFor="liability-principal">{t('liabilities.fields.principalAmount')} <span className="required">*</span></label>
              <input
                id="liability-principal"
                type="number"
                step="0.01"
                min="0.01"
                value={state.principal_amount}
                onChange={(event) => updateField('principal_amount', event.target.value)}
                required
              />
            </div>

            <div className="liability-form-field">
              <label htmlFor="liability-outstanding">{t('liabilities.fields.outstandingBalance')}</label>
              <input
                id="liability-outstanding"
                type="number"
                step="0.01"
                min="0"
                value={state.outstanding_balance}
                onChange={(event) => updateField('outstanding_balance', event.target.value)}
                required
              />
            </div>
          </div>

          <div className="liability-form-row">
            <div className="liability-form-field">
              <label htmlFor="liability-interest">{t('liabilities.fields.interestRate')}</label>
              <input
                id="liability-interest"
                type="number"
                step="0.001"
                min="0"
                value={state.interest_rate}
                onChange={(event) => updateField('interest_rate', event.target.value)}
              />
            </div>

            <div className="liability-form-field">
              <label htmlFor="liability-monthly-payment">{t('liabilities.fields.monthlyPayment')}</label>
              <input
                id="liability-monthly-payment"
                type="number"
                step="0.01"
                min="0"
                value={state.monthly_payment}
                onChange={(event) => updateField('monthly_payment', event.target.value)}
              />
            </div>
          </div>

          <div className="liability-form-row">
            <div className="liability-form-field">
              <label htmlFor="liability-start-date">{t('liabilities.fields.startDate')} <span className="required">*</span></label>
              <DateInput
                id="liability-start-date"
                value={state.start_date}
                onChange={(val) => updateField('start_date', val)}
                locale={getLocaleForLanguage(i18n.language)}
                todayLabel={String(t('common.today'))}
              />
            </div>

            <div className="liability-form-field">
              <label htmlFor="liability-end-date">{t('liabilities.fields.endDate')}</label>
              <DateInput
                id="liability-end-date"
                value={state.end_date}
                onChange={(val) => updateField('end_date', val)}
                locale={getLocaleForLanguage(i18n.language)}
                todayLabel={String(t('common.today'))}
              />
            </div>
          </div>
        </div>

        <div className="liability-form-section">
          <div className="liability-form-field liability-form-field--full">
            <label htmlFor="liability-property">{t('liabilities.fields.linkedProperty')}</label>
            <Select
              id="liability-property"
              value={state.linked_property_id}
              onChange={(value) => updateField('linked_property_id', value)}
              options={propertySelectOptions}
            />
          </div>

          <div className="liability-form-field liability-form-field--full">
            <label className="liability-inline-checkbox">
              <input
                type="checkbox"
                checked={state.tax_relevant}
                onChange={(event) => updateField('tax_relevant', event.target.checked)}
              />
              <span>{t('liabilities.fields.taxRelevant')}</span>
            </label>
          </div>

          {state.tax_relevant && (
            <div className="liability-form-field liability-form-field--full">
              <label htmlFor="liability-tax-reason">{t('liabilities.fields.taxRelevanceReason')}</label>
              <textarea
                id="liability-tax-reason"
                value={state.tax_relevance_reason}
                onChange={(event) => updateField('tax_relevance_reason', event.target.value)}
              />
            </div>
          )}

          {!initialValue && (
            <>
              <div className="liability-form-field liability-form-field--full">
                <label className="liability-inline-checkbox">
                  <input
                    type="checkbox"
                    checked={state.create_recurring_plan}
                    onChange={(event) => updateField('create_recurring_plan', event.target.checked)}
                  />
                  <span>{t('liabilities.fields.createRecurringPlan')}</span>
                </label>
                <p className="liability-hint">
                  {t('liabilities.fields.createRecurringPlanHint')}
                </p>
              </div>

              {state.create_recurring_plan && (
                <div className="liability-form-row">
                  <div className="liability-form-field">
                    <label htmlFor="liability-recurring-day">{t('liabilities.fields.recurringDay')}</label>
                    <input
                      id="liability-recurring-day"
                      type="number"
                      min="1"
                      max="31"
                      value={state.recurring_day_of_month}
                      onChange={(event) => updateField('recurring_day_of_month', event.target.value)}
                    />
                  </div>
                </div>
              )}
            </>
          )}

          <div className="liability-form-field liability-form-field--full">
            <label htmlFor="liability-notes">{t('liabilities.fields.notes')}</label>
            <textarea
              id="liability-notes"
              value={state.notes}
              onChange={(event) => updateField('notes', event.target.value)}
            />
          </div>
        </div>

        <div className="liability-panel-actions">
          <button type="button" className="btn btn-secondary" onClick={onCancel} disabled={submitting}>
            {t('common.cancel')}
          </button>
          <button type="submit" className="btn btn-primary" disabled={submitting}>
            {submitting
              ? t('common.saving')
              : initialValue
                ? t('common.save')
                : t('common.create')}
          </button>
        </div>
      </form>
    </section>
  );
};

export default LiabilityForm;
