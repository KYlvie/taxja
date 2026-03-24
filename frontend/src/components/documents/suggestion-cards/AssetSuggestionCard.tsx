import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import Select from '../../common/Select';
import DateInput from '../../common/DateInput';
import { getLocaleForLanguage } from '../../../utils/locale';
import type { AssetSuggestionConfirmationPayload } from '../../../services/documentService';
import { SuggestionCardShell, Row, fmtEur, fmtDate, SuggestionCardProps } from './SuggestionCardBase';

const ASSET_ICONS: Record<string, string> = {
  vehicle: 'Car',
  electric_vehicle: 'EV',
  computer: 'PC',
  phone: 'PH',
  office_furniture: 'OF',
  machinery: 'MC',
  tools: 'TL',
  software: 'SW',
  other_equipment: 'EQ',
};

const VEHICLE_SUBTYPES = new Set([
  'pkw',
  'electric_pkw',
  'truck_van',
  'fiscal_truck',
  'motorcycle',
  'special_vehicle',
]);

const toNumber = (value: unknown): number | null => {
  if (value === null || value === undefined || value === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

const toStringArray = (value: unknown): string[] => (
  Array.isArray(value)
    ? value
        .map((item) => String(item || '').trim())
        .filter(Boolean)
    : []
);

const formatPercent = (value: number | null | undefined) => (
  value != null ? `${value}%` : '—'
);

const AssetSuggestionCard: React.FC<SuggestionCardProps> = (props) => {
  const { t, i18n } = useTranslation();
  const d = props.suggestion.data || {};
  const icon = ASSET_ICONS[d.asset_type] || 'EQ';

  const reviewReasons = useMemo(() => toStringArray(d.review_reasons), [d.review_reasons]);
  const missingFields = useMemo(() => new Set(toStringArray(d.missing_fields)), [d.missing_fields]);
  const allowedDepreciationMethods = useMemo(() => {
    const methods = toStringArray(d.allowed_depreciation_methods);
    if (methods.length > 0) return methods;
    if (d.suggested_depreciation_method) return [String(d.suggested_depreciation_method)];
    return ['linear'];
  }, [d.allowed_depreciation_methods, d.suggested_depreciation_method]);

  const isVehicleAsset = Boolean(
    d.asset_type === 'vehicle'
    || d.asset_type === 'electric_vehicle'
    || VEHICLE_SUBTYPES.has(String(d.sub_category || ''))
  );
  const gwgEligible = Boolean(d.gwg_eligible ?? d.decision === 'gwg_suggestion');
  const gwgDefaultSelected = Boolean(d.gwg_default_selected ?? d.decision === 'gwg_suggestion');
  const gwgElectionRequired = Boolean(d.gwg_election_required ?? gwgEligible);
  const initialUsedAsset = Boolean(
    d.is_used_asset
    || reviewReasons.includes('used_vehicle_history_missing')
  );

  const [putIntoUseDate, setPutIntoUseDate] = useState<string>(d.put_into_use_date || '');
  const [businessUsePercentage, setBusinessUsePercentage] = useState<string>(
    d.business_use_percentage != null ? String(d.business_use_percentage) : '100'
  );
  const [isUsedAsset, setIsUsedAsset] = useState<boolean>(initialUsedAsset);
  const [firstRegistrationDate, setFirstRegistrationDate] = useState<string>(d.first_registration_date || '');
  const [priorOwnerUsageYears, setPriorOwnerUsageYears] = useState<string>(
    d.prior_owner_usage_years != null ? String(d.prior_owner_usage_years) : ''
  );
  const [gwgTreatment, setGwgTreatment] = useState<'gwg' | 'asset'>(
    gwgEligible && gwgDefaultSelected ? 'gwg' : 'asset'
  );
  const [depreciationMethod, setDepreciationMethod] = useState<string>(
    String(d.depreciation_method || d.suggested_depreciation_method || allowedDepreciationMethods[0] || 'linear')
  );
  const [degressiveRate, setDegressiveRate] = useState<string>(
    d.degressive_afa_rate != null
      ? String(d.degressive_afa_rate)
      : d.degressive_max_rate != null
        ? String(d.degressive_max_rate)
        : ''
  );
  const [usefulLifeYears, setUsefulLifeYears] = useState<string>(
    d.useful_life_years != null ? String(d.useful_life_years) : ''
  );
  const [localError, setLocalError] = useState<string | null>(null);

  useEffect(() => {
    setPutIntoUseDate(d.put_into_use_date || '');
    setBusinessUsePercentage(d.business_use_percentage != null ? String(d.business_use_percentage) : '100');
    setIsUsedAsset(initialUsedAsset);
    setFirstRegistrationDate(d.first_registration_date || '');
    setPriorOwnerUsageYears(d.prior_owner_usage_years != null ? String(d.prior_owner_usage_years) : '');
    setGwgTreatment(gwgEligible && gwgDefaultSelected ? 'gwg' : 'asset');
    setDepreciationMethod(
      String(d.depreciation_method || d.suggested_depreciation_method || allowedDepreciationMethods[0] || 'linear')
    );
    setDegressiveRate(
      d.degressive_afa_rate != null
        ? String(d.degressive_afa_rate)
        : d.degressive_max_rate != null
          ? String(d.degressive_max_rate)
          : ''
    );
    setUsefulLifeYears(d.useful_life_years != null ? String(d.useful_life_years) : '');
    setLocalError(null);
  }, [
    allowedDepreciationMethods,
    d.business_use_percentage,
    d.degressive_afa_rate,
    d.degressive_max_rate,
    d.depreciation_method,
    d.first_registration_date,
    d.prior_owner_usage_years,
    d.put_into_use_date,
    d.suggested_depreciation_method,
    d.useful_life_years,
    gwgDefaultSelected,
    gwgEligible,
    initialUsedAsset,
  ]);

  const showPutIntoUseDate = missingFields.has('put_into_use_date') || !d.put_into_use_date;
  const showUsedAssetQuestion = isVehicleAsset || d.is_used_asset !== undefined || reviewReasons.includes('used_vehicle_history_missing');
  const showVehicleHistoryFields = isVehicleAsset && isUsedAsset;
  const showUsefulLifeInput = d.useful_life_years != null;

  const decisionLabel = (() => {
    switch (d.decision) {
      case 'gwg_suggestion':
        return t('documents.suggestion.assetDecision.gwg', 'Recommended as low-value asset');
      case 'create_asset_auto':
        return t('documents.suggestion.assetDecision.auto', 'System can create asset automatically');
      case 'create_asset_suggestion':
      default:
        return t('documents.suggestion.assetDecision.asset', 'Recommended as fixed asset');
    }
  })();

  const vatRecoverableLabel = (() => {
    switch (d.vat_recoverable_status) {
      case 'likely_yes':
        return t('documents.suggestion.assetVat.likelyYes', 'Input VAT likely deductible');
      case 'likely_no':
        return t('documents.suggestion.assetVat.likelyNo', 'Input VAT likely not deductible');
      case 'partial':
        return t('documents.suggestion.assetVat.partial', 'Possibly partially deductible');
      default:
        return t('documents.suggestion.assetVat.unclear', 'Input VAT eligibility to be confirmed');
    }
  })();

  const handleSubmit = () => {
    setLocalError(null);

    if (showPutIntoUseDate && !putIntoUseDate) {
      setLocalError(t('documents.suggestion.assetErrors.putIntoUseRequired', 'Please confirm the date put into use first.'));
      return;
    }

    const businessUse = toNumber(businessUsePercentage);
    if (businessUse === null || businessUse < 0 || businessUse > 100) {
      setLocalError(t('documents.suggestion.assetErrors.businessUse', 'Business use percentage must be between 0 and 100.'));
      return;
    }

    if (showVehicleHistoryFields && !firstRegistrationDate && !priorOwnerUsageYears.trim()) {
      setLocalError(
        t(
          'documents.suggestion.assetErrors.vehicleHistory',
          'Used vehicles require the first registration date or prior usage years to correctly calculate depreciation.'
        )
      );
      return;
    }

    const usefulLife = usefulLifeYears.trim() ? toNumber(usefulLifeYears) : null;
    if (usefulLife !== null && (!Number.isInteger(usefulLife) || usefulLife < 1 || usefulLife > 50)) {
      setLocalError(t('documents.suggestion.assetErrors.usefulLife', 'Useful life must be a whole number between 1 and 50.'));
      return;
    }

    const payload: AssetSuggestionConfirmationPayload = {
      business_use_percentage: businessUse,
      depreciation_method: depreciationMethod as 'linear' | 'degressive',
    };

    if (putIntoUseDate) {
      payload.put_into_use_date = putIntoUseDate;
    }

    if (showUsedAssetQuestion) {
      payload.is_used_asset = isUsedAsset;
    }

    if (firstRegistrationDate) {
      payload.first_registration_date = firstRegistrationDate;
    }

    const priorUsage = priorOwnerUsageYears.trim() ? toNumber(priorOwnerUsageYears) : null;
    if (priorUsage !== null) {
      payload.prior_owner_usage_years = priorUsage;
    }

    if (gwgElectionRequired) {
      payload.gwg_elected = gwgTreatment === 'gwg';
    }

    if (depreciationMethod === 'degressive') {
      const maxRate = toNumber(d.degressive_max_rate) ?? 0.3;
      const selectedRate = toNumber(degressiveRate) ?? maxRate;
      if (selectedRate <= 0 || selectedRate > maxRate) {
        setLocalError(
          t(
            'documents.suggestion.assetErrors.degressiveRate',
            'Declining-balance rate is outside the allowed range.'
          )
        );
        return;
      }
      payload.degressive_afa_rate = selectedRate;
    }

    if (usefulLife !== null) {
      payload.useful_life_years = usefulLife;
    }

    props.onConfirm(payload);
  };

  return (
    <SuggestionCardShell
      icon={icon}
      title={t('documents.suggestion.createAsset', 'Create depreciable asset from purchase contract?')}
      confirmResult={props.confirmResult}
      confirmingAction={props.confirmingAction}
      confirmActionKey={props.confirmActionKey || 'asset'}
      onConfirm={handleSubmit}
      onDismiss={props.onDismiss}
      confirmLabel={t('documents.suggestion.assetConfirm', 'Confirm and create asset')}
    >
      <div className="suggestion-details">
        {d.name && <Row label={String(t('documents.suggestion.assetName', 'Asset name'))} value={d.name} />}
        {d.asset_type && (
          <Row
            label={String(t('documents.suggestion.assetType', 'Asset type'))}
            value={String(t(`documents.suggestion.assetTypes.${d.asset_type}`, d.asset_type))}
          />
        )}
        <Row label={String(t('documents.ocr.purchasePrice', 'Purchase Price'))} value={fmtEur(d.purchase_price)} />
        {d.purchase_date && <Row label={String(t('documents.ocr.purchaseDate', 'Purchase Date'))} value={fmtDate(d.purchase_date)} />}
        {d.supplier && <Row label={String(t('documents.suggestion.supplier', 'Supplier'))} value={d.supplier} />}
        <Row label={String(t('documents.suggestion.assetDecisionLabel', 'System recommendation'))} value={decisionLabel} />
        <Row
          label={String(t('documents.suggestion.assetVatLabel', 'Input VAT assessment'))}
          value={vatRecoverableLabel}
        />
        {d.ifb_candidate !== undefined && (
          <Row
            label={String(t('documents.suggestion.assetIfbLabel', 'IFB candidate'))}
            value={
              d.ifb_candidate
                ? t('documents.suggestion.assetIfbYes', 'Yes')
                : t('documents.suggestion.assetIfbNo', 'No')
            }
          />
        )}
        {d.useful_life_years && (
          <Row
            label={String(t('documents.suggestion.usefulLife', 'Useful life'))}
            value={`${d.useful_life_years} ${String(t('documents.suggestion.years', 'years'))}`}
          />
        )}
      </div>

      <div className="asset-suggestion-badges">
        <span className="asset-suggestion-badge">
          {t('documents.suggestion.assetBasis', 'Comparison basis')} {String(d.comparison_basis || '—')}
        </span>
        {d.policy_confidence != null && (
          <span className="asset-suggestion-badge">
            {t('documents.suggestion.assetConfidence', 'Rule confidence')} {formatPercent(Math.round(Number(d.policy_confidence) * 100))}
          </span>
        )}
        {d.duplicate?.duplicate_status && d.duplicate.duplicate_status !== 'none' && (
          <span className="asset-suggestion-badge warning">
            {t('documents.suggestion.assetDuplicateWarning', 'Possible duplicate asset detected')}
          </span>
        )}
      </div>

      <div className="asset-confirmation-hint">
        {t(
          'documents.suggestion.assetHint',
          'The system has pre-assessed the tax treatment. Only provide key information that affects depreciation and tax conclusions.'
        )}
      </div>

      <div className="asset-confirmation-grid">
        {showPutIntoUseDate && (
          <label className="asset-confirmation-field">
            <span>{t('documents.suggestion.assetFields.putIntoUseDate', 'Date put into use')}</span>
            <DateInput
              value={putIntoUseDate}
              onChange={(val) => setPutIntoUseDate(val)}
              disabled={props.confirmingAction !== null}
              locale={getLocaleForLanguage(i18n.language)}
              todayLabel={String(t('common.today', 'Today'))}
            />
          </label>
        )}

        <label className="asset-confirmation-field">
          <span>{t('documents.suggestion.assetFields.businessUse', 'Business use percentage')}</span>
          <input
            type="number"
            min="0"
            max="100"
            step="1"
            value={businessUsePercentage}
            onChange={(event) => setBusinessUsePercentage(event.target.value)}
            disabled={props.confirmingAction !== null}
          />
        </label>

        {showUsedAssetQuestion && (
          <label className="asset-confirmation-field">
            <span>{t('documents.suggestion.assetFields.condition', 'Asset condition')}</span>
            <Select value={isUsedAsset ? 'used' : 'new'} onChange={v => setIsUsedAsset(v === 'used')}
              disabled={props.confirmingAction !== null} size="sm"
              options={[
                { value: 'new', label: t('documents.suggestion.assetCondition.new', 'New') },
                { value: 'used', label: t('documents.suggestion.assetCondition.used', 'Used') },
              ]} />
          </label>
        )}

        {showVehicleHistoryFields && (
          <>
            <label className="asset-confirmation-field">
              <span>{t('documents.suggestion.assetFields.firstRegistrationDate', 'First registration date')}</span>
              <DateInput
                value={firstRegistrationDate}
                onChange={(val) => setFirstRegistrationDate(val)}
                disabled={props.confirmingAction !== null}
                locale={getLocaleForLanguage(i18n.language)}
                todayLabel={String(t('common.today', 'Today'))}
              />
            </label>
            <label className="asset-confirmation-field">
              <span>{t('documents.suggestion.assetFields.priorUsageYears', 'Prior usage years')}</span>
              <input
                type="number"
                min="0"
                step="0.1"
                value={priorOwnerUsageYears}
                onChange={(event) => setPriorOwnerUsageYears(event.target.value)}
                disabled={props.confirmingAction !== null}
              />
            </label>
          </>
        )}

        {gwgElectionRequired && (
          <label className="asset-confirmation-field">
            <span>{t('documents.suggestion.assetFields.gwgElection', 'Tax treatment method')}</span>
            <Select value={gwgTreatment} onChange={v => setGwgTreatment(v as 'gwg' | 'asset')}
              disabled={props.confirmingAction !== null} size="sm"
              options={[
                { value: 'gwg', label: t('documents.suggestion.assetGwg', 'Expense as low-value asset (one-off)') },
                { value: 'asset', label: t('documents.suggestion.assetCapitalize', 'Capitalize as fixed asset (depreciate)') },
              ]} />
          </label>
        )}

        {allowedDepreciationMethods.length > 0 && (
          <label className="asset-confirmation-field">
            <span>{t('documents.suggestion.assetFields.depreciationMethod', 'Depreciation method')}</span>
            <Select value={depreciationMethod} onChange={setDepreciationMethod}
              disabled={props.confirmingAction !== null || (gwgElectionRequired && gwgTreatment === 'gwg')} size="sm"
              options={allowedDepreciationMethods.map(method => ({
                value: method,
                label: method === 'degressive'
                  ? t('documents.suggestion.assetDepreciation.degressive', 'Declining-balance depreciation')
                  : t('documents.suggestion.assetDepreciation.linear', 'Straight-line depreciation'),
              }))} />
          </label>
        )}

        {depreciationMethod === 'degressive' && (
          <label className="asset-confirmation-field">
            <span>{t('documents.suggestion.assetFields.degressiveRate', 'Declining-balance rate')}</span>
            <input
              type="number"
              min="0.01"
              max={String(d.degressive_max_rate ?? 0.3)}
              step="0.01"
              value={degressiveRate}
              onChange={(event) => setDegressiveRate(event.target.value)}
              disabled={props.confirmingAction !== null || (gwgElectionRequired && gwgTreatment === 'gwg')}
            />
          </label>
        )}

        {showUsefulLifeInput && (
          <label className="asset-confirmation-field">
            <span>{t('documents.suggestion.assetFields.usefulLifeYears', 'Useful life (years)')}</span>
            <input
              type="number"
              min="1"
              max="50"
              step="1"
              value={usefulLifeYears}
              onChange={(event) => setUsefulLifeYears(event.target.value)}
              disabled={props.confirmingAction !== null || (gwgElectionRequired && gwgTreatment === 'gwg')}
            />
          </label>
        )}
      </div>

      {localError && <div className="suggestion-result error">{localError}</div>}
    </SuggestionCardShell>
  );
};

export default AssetSuggestionCard;
