import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { SuggestionCardProps } from './SuggestionCardBase';
import { fmtDate, fmtEur, Row } from './SuggestionCardBase';

const InsuranceSuggestionCard: React.FC<SuggestionCardProps> = ({
  suggestion,
  confirmResult,
  confirmingAction,
  onConfirm,
  onDismiss,
}) => {
  const { t } = useTranslation();
  const data = suggestion.data || {};
  const isArchiveOnly = suggestion.type === 'archive_insurance_document';
  const inputFields = Array.isArray(data.input_fields) ? data.input_fields : [];
  const dedupConflicts = Array.isArray(data.dedup_conflicts) ? data.dedup_conflicts : [];
  const defaultArchiveReasonCode = (
    typeof data.archive_reason_code === 'string'
      ? data.archive_reason_code
      : dedupConflicts.length > 0
        ? 'already_covered'
        : data.document_subtype === 'bedingungen' || data.document_subtype === 'schadensmeldung'
          ? 'reference_only'
          : data.deductibility_status === 'not_deductible'
            ? 'not_relevant'
            : 'other'
  );

  const initialForm = useMemo(() => ({
    business_use_percentage:
      typeof data.business_use_percentage === 'number' ? String(data.business_use_percentage) : '',
    beruflicher_anteil_pct:
      typeof data.beruflicher_anteil_pct === 'number' ? String(data.beruflicher_anteil_pct) : '',
    property_rental_status: typeof data.property_rental_status === 'string' ? data.property_rental_status : '',
    dedup_resolution: dedupConflicts.length > 0 ? 'link_existing' : 'ignore_existing',
    override_payment_amount:
      typeof data.payment_amount === 'number' ? String(data.payment_amount) : '',
    override_payment_frequency:
      typeof data.payment_frequency === 'string' ? data.payment_frequency : '',
    archive_reason_code: defaultArchiveReasonCode,
    archive_reason_note: typeof data.archive_reason_note === 'string' ? data.archive_reason_note : '',
  }), [data, dedupConflicts.length, defaultArchiveReasonCode]);

  const [form, setForm] = useState(initialForm);

  const needsBusinessUse = inputFields.includes('business_use_percentage');
  const needsProfessionalShare = inputFields.includes('beruflicher_anteil_pct');
  const needsPropertyStatus = inputFields.includes('property_rental_status');

  const confirmDisabled = (
    (!isArchiveOnly && needsBusinessUse && form.business_use_percentage.trim() === '')
    || (!isArchiveOnly && needsProfessionalShare && form.beruflicher_anteil_pct.trim() === '')
    || (!isArchiveOnly && needsPropertyStatus && !form.property_rental_status)
  );
  const archiveDisabled = form.archive_reason_code === 'other' && form.archive_reason_note.trim() === '';

  const payload = {
    business_use_percentage:
      form.business_use_percentage.trim() !== '' ? Number(form.business_use_percentage) : undefined,
    beruflicher_anteil_pct:
      form.beruflicher_anteil_pct.trim() !== '' ? Number(form.beruflicher_anteil_pct) : undefined,
    property_rental_status: form.property_rental_status || undefined,
    dedup_resolution: form.dedup_resolution as 'link_existing' | 'ignore_existing' | 'cancel',
    override_payment_amount:
      form.override_payment_amount.trim() !== '' ? Number(form.override_payment_amount) : undefined,
    override_payment_frequency:
      form.override_payment_frequency || undefined,
    archive_reason_code: form.archive_reason_code || undefined,
    archive_reason_note: form.archive_reason_note.trim() !== '' ? form.archive_reason_note.trim() : undefined,
  };

  return (
    <div className="import-suggestion-card">
      <div className="suggestion-header">
        <span className="suggestion-icon">INS</span>
        <h3>
          {isArchiveOnly
            ? t('documents.suggestion.archiveInsurance', 'Archive insurance document')
            : t('documents.suggestion.createInsuranceRecurring', 'Create insurance recurring')}
        </h3>
      </div>

      <div style={{ display: 'grid', gap: 8 }}>
        <Row
          label={t('documents.suggestion.insurer', 'Insurer')}
          value={data.insurer_name || '-'}
        />
        <Row
          label={t('documents.suggestion.insuranceType', 'Insurance type')}
          value={data.insurance_type || '-'}
        />
        <Row
          label={t('documents.suggestion.paymentAmount', 'Payment amount')}
          value={
            <span title={data.payment_amount_source ? `source: ${data.payment_amount_source}` : undefined}>
              {fmtEur(data.payment_amount)}
            </span>
          }
        />
        <Row
          label={t('documents.suggestion.annualPremium', 'Annual premium')}
          value={
            <span title={data.premium_annual_brutto_source ? `source: ${data.premium_annual_brutto_source}` : undefined}>
              {fmtEur(data.premium_annual_brutto)}
            </span>
          }
        />
        <Row
          label={t('documents.suggestion.frequency', 'Frequency')}
          value={data.payment_frequency || '-'}
        />
        <Row
          label={t('documents.suggestion.taxTreatment', 'Tax treatment')}
          value={data.deductibility_hint || '-'}
        />
        <Row label="Polizze" value={data.polizze_nr || '-'} />
        <Row
          label={t('documents.suggestion.policyHolder', 'Policy holder')}
          value={data.versicherungsnehmer || '-'}
        />
        <Row
          label={t('documents.suggestion.startDate', 'Start date')}
          value={fmtDate(data.vertragsbeginn)}
        />
      </div>

      {!isArchiveOnly && (
        <div style={{ display: 'grid', gap: 10, marginTop: 16 }}>
          <div className="suggestion-row">
            <span>{t('documents.suggestion.overrideAmount', 'Override payment amount')}</span>
            <input
              type="number"
              step="0.01"
              value={form.override_payment_amount}
              onChange={(event) => setForm((current) => ({ ...current, override_payment_amount: event.target.value }))}
            />
          </div>
          <div className="suggestion-row">
            <span>{t('documents.suggestion.overrideFrequency', 'Override frequency')}</span>
            <select
              value={form.override_payment_frequency}
              onChange={(event) => setForm((current) => ({ ...current, override_payment_frequency: event.target.value }))}
            >
              <option value="">{t('common.select', 'Select')}</option>
              <option value="monthly">monthly</option>
              <option value="quarterly">quarterly</option>
              <option value="semi_annual">semi_annual</option>
              <option value="annually">annually</option>
            </select>
          </div>

          {needsBusinessUse && (
            <div className="suggestion-row">
              <span>{t('documents.suggestion.businessUsePct', 'Business-use %')}</span>
              <input
                type="number"
                min="0"
                max="100"
                value={form.business_use_percentage}
                onChange={(event) => setForm((current) => ({ ...current, business_use_percentage: event.target.value }))}
              />
            </div>
          )}

          {needsProfessionalShare && (
            <div className="suggestion-row">
              <span>{t('documents.suggestion.professionalSharePct', 'Professional share %')}</span>
              <input
                type="number"
                min="0"
                max="100"
                value={form.beruflicher_anteil_pct}
                onChange={(event) => setForm((current) => ({ ...current, beruflicher_anteil_pct: event.target.value }))}
              />
            </div>
          )}

          {needsPropertyStatus && (
            <div className="suggestion-row">
              <span>{t('documents.suggestion.propertyRentalStatus', 'Property status')}</span>
              <select
                value={form.property_rental_status}
                onChange={(event) => setForm((current) => ({ ...current, property_rental_status: event.target.value }))}
              >
                <option value="">{t('common.select', 'Select')}</option>
                <option value="rented">rented</option>
                <option value="owner_occupied">owner_occupied</option>
                <option value="mixed">mixed</option>
              </select>
            </div>
          )}

          {dedupConflicts.length > 0 && (
            <div style={{ display: 'grid', gap: 8 }}>
              <strong>{t('documents.suggestion.dedupConflicts', 'Potential overlaps')}</strong>
              {dedupConflicts.map((conflict: Record<string, unknown>, index: number) => (
                <div key={`${String(conflict.existing_transaction_id || conflict.existing_recurring_id || index)}`} className="suggestion-result info">
                  {String(conflict.date || '-')}: {fmtEur(Number(conflict.amount || 0))} - {String(conflict.description || '')}
                </div>
              ))}
              <div className="suggestion-row">
                <span>{t('documents.suggestion.dedupResolution', 'Conflict handling')}</span>
                <select
                  value={form.dedup_resolution}
                  onChange={(event) => setForm((current) => ({ ...current, dedup_resolution: event.target.value }))}
                >
                  <option value="link_existing">link_existing</option>
                  <option value="ignore_existing">ignore_existing</option>
                  <option value="cancel">cancel</option>
                </select>
              </div>
            </div>
          )}
        </div>
      )}

      <div style={{ display: 'grid', gap: 10, marginTop: 16 }}>
        <div className="suggestion-row">
          <span>{t('documents.suggestion.archiveReason', 'Archive reason')}</span>
          <select
            value={form.archive_reason_code}
            onChange={(event) => setForm((current) => ({ ...current, archive_reason_code: event.target.value }))}
          >
            <option value="already_covered">already_covered</option>
            <option value="not_relevant">not_relevant</option>
            <option value="duplicate">duplicate</option>
            <option value="reference_only">reference_only</option>
            <option value="other">other</option>
          </select>
        </div>
        {form.archive_reason_code === 'other' && (
          <div className="suggestion-row">
            <span>{t('documents.suggestion.archiveReasonNote', 'Archive note')}</span>
            <input
              type="text"
              value={form.archive_reason_note}
              onChange={(event) => setForm((current) => ({ ...current, archive_reason_note: event.target.value }))}
            />
          </div>
        )}
      </div>

      {confirmResult && (
        <div className={`suggestion-result ${confirmResult.type}`}>{confirmResult.message}</div>
      )}

      <div className="suggestion-actions">
        <button
          className="btn btn-primary"
          onClick={() => (isArchiveOnly ? onConfirm({ ...payload, archive_only: true }) : onConfirm(payload))}
          disabled={confirmingAction !== null || (isArchiveOnly ? archiveDisabled : confirmDisabled)}
        >
          {isArchiveOnly
            ? t('documents.suggestion.archiveOnly', 'Archive only')
            : t('documents.suggestion.confirm', 'Confirm')}
        </button>
        {!isArchiveOnly && (
          <button
            className="btn btn-secondary"
            onClick={() => onConfirm({ ...payload, archive_only: true })}
            disabled={confirmingAction !== null || archiveDisabled}
          >
            {t('documents.suggestion.archiveOnly', 'Archive only')}
          </button>
        )}
        <button
          className="btn btn-secondary"
          onClick={() => setForm(initialForm)}
          disabled={confirmingAction !== null}
        >
          {t('common.cancel', 'Cancel')}
        </button>
      </div>
    </div>
  );
};

export default InsuranceSuggestionCard;
