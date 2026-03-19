import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
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
  const { t } = useTranslation();
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
        return t('documents.suggestion.assetDecision.gwg', '建议按低值资产处理');
      case 'create_asset_auto':
        return t('documents.suggestion.assetDecision.auto', '系统可自动建资产');
      case 'create_asset_suggestion':
      default:
        return t('documents.suggestion.assetDecision.asset', '建议建立固定资产');
    }
  })();

  const vatRecoverableLabel = (() => {
    switch (d.vat_recoverable_status) {
      case 'likely_yes':
        return t('documents.suggestion.assetVat.likelyYes', '大概率可抵扣进项税');
      case 'likely_no':
        return t('documents.suggestion.assetVat.likelyNo', '大概率不可抵扣进项税');
      case 'partial':
        return t('documents.suggestion.assetVat.partial', '可能部分可抵扣');
      default:
        return t('documents.suggestion.assetVat.unclear', '进项税资格待确认');
    }
  })();

  const handleSubmit = () => {
    setLocalError(null);

    if (showPutIntoUseDate && !putIntoUseDate) {
      setLocalError(t('documents.suggestion.assetErrors.putIntoUseRequired', '请先确认投入使用日期。'));
      return;
    }

    const businessUse = toNumber(businessUsePercentage);
    if (businessUse === null || businessUse < 0 || businessUse > 100) {
      setLocalError(t('documents.suggestion.assetErrors.businessUse', '业务使用比例需要在 0 到 100 之间。'));
      return;
    }

    if (showVehicleHistoryFields && !firstRegistrationDate && !priorOwnerUsageYears.trim()) {
      setLocalError(
        t(
          'documents.suggestion.assetErrors.vehicleHistory',
          '二手车辆需要首次登记日期或前任使用年限，才能正确计算折旧。'
        )
      );
      return;
    }

    const usefulLife = usefulLifeYears.trim() ? toNumber(usefulLifeYears) : null;
    if (usefulLife !== null && (!Number.isInteger(usefulLife) || usefulLife < 1 || usefulLife > 50)) {
      setLocalError(t('documents.suggestion.assetErrors.usefulLife', '使用年限需要是 1 到 50 之间的整数。'));
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
            '递减折旧比例超出了当前允许范围。'
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
      title={t('documents.suggestion.createAsset', '创建资产')}
      confirmResult={props.confirmResult}
      confirmingAction={props.confirmingAction}
      confirmActionKey={props.confirmActionKey || 'asset'}
      onConfirm={handleSubmit}
      onDismiss={props.onDismiss}
      confirmLabel={t('documents.suggestion.assetConfirm', '确认并创建资产')}
    >
      <div className="suggestion-details">
        {d.name && <Row label={String(t('documents.suggestion.assetName', '资产名称'))} value={d.name} />}
        {d.asset_type && (
          <Row
            label={String(t('documents.suggestion.assetType', '资产类型'))}
            value={String(t(`documents.suggestion.assetTypes.${d.asset_type}`, d.asset_type))}
          />
        )}
        <Row label={String(t('documents.ocr.purchasePrice', '购置金额'))} value={fmtEur(d.purchase_price)} />
        {d.purchase_date && <Row label={String(t('documents.ocr.purchaseDate', '购置日期'))} value={fmtDate(d.purchase_date)} />}
        {d.supplier && <Row label={String(t('documents.suggestion.supplier', '供应商'))} value={d.supplier} />}
        <Row label={String(t('documents.suggestion.assetDecisionLabel', '系统建议'))} value={decisionLabel} />
        <Row
          label={String(t('documents.suggestion.assetVatLabel', '进项税预判'))}
          value={vatRecoverableLabel}
        />
        {d.ifb_candidate !== undefined && (
          <Row
            label={String(t('documents.suggestion.assetIfbLabel', 'IFB 候选'))}
            value={
              d.ifb_candidate
                ? t('documents.suggestion.assetIfbYes', '是')
                : t('documents.suggestion.assetIfbNo', '否')
            }
          />
        )}
        {d.useful_life_years && (
          <Row
            label={String(t('documents.suggestion.usefulLife', '建议使用年限'))}
            value={`${d.useful_life_years} ${String(t('documents.suggestion.years', '年'))}`}
          />
        )}
      </div>

      <div className="asset-suggestion-badges">
        <span className="asset-suggestion-badge">
          {t('documents.suggestion.assetBasis', '比较基数')} {String(d.comparison_basis || '—')}
        </span>
        {d.policy_confidence != null && (
          <span className="asset-suggestion-badge">
            {t('documents.suggestion.assetConfidence', '规则置信度')} {formatPercent(Math.round(Number(d.policy_confidence) * 100))}
          </span>
        )}
        {d.duplicate?.duplicate_status && d.duplicate.duplicate_status !== 'none' && (
          <span className="asset-suggestion-badge warning">
            {t('documents.suggestion.assetDuplicateWarning', '检测到疑似重复资产')}
          </span>
        )}
      </div>

      <div className="asset-confirmation-hint">
        {t(
          'documents.suggestion.assetHint',
          '系统已经先做了税务预判。这里只补真正会影响折旧和税务结论的关键信息。'
        )}
      </div>

      <div className="asset-confirmation-grid">
        {showPutIntoUseDate && (
          <label className="asset-confirmation-field">
            <span>{t('documents.suggestion.assetFields.putIntoUseDate', '投入使用日期')}</span>
            <input
              type="date"
              value={putIntoUseDate}
              onChange={(event) => setPutIntoUseDate(event.target.value)}
              disabled={props.confirmingAction !== null}
            />
          </label>
        )}

        <label className="asset-confirmation-field">
          <span>{t('documents.suggestion.assetFields.businessUse', '业务使用比例')}</span>
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
            <span>{t('documents.suggestion.assetFields.condition', '资产状态')}</span>
            <select
              value={isUsedAsset ? 'used' : 'new'}
              onChange={(event) => setIsUsedAsset(event.target.value === 'used')}
              disabled={props.confirmingAction !== null}
            >
              <option value="new">{t('documents.suggestion.assetCondition.new', '全新')}</option>
              <option value="used">{t('documents.suggestion.assetCondition.used', '二手')}</option>
            </select>
          </label>
        )}

        {showVehicleHistoryFields && (
          <>
            <label className="asset-confirmation-field">
              <span>{t('documents.suggestion.assetFields.firstRegistrationDate', '首次登记日期')}</span>
              <input
                type="date"
                value={firstRegistrationDate}
                onChange={(event) => setFirstRegistrationDate(event.target.value)}
                disabled={props.confirmingAction !== null}
              />
            </label>
            <label className="asset-confirmation-field">
              <span>{t('documents.suggestion.assetFields.priorUsageYears', '前任使用年限')}</span>
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
            <span>{t('documents.suggestion.assetFields.gwgElection', '税务处理方式')}</span>
            <select
              value={gwgTreatment}
              onChange={(event) => setGwgTreatment(event.target.value as 'gwg' | 'asset')}
              disabled={props.confirmingAction !== null}
            >
              <option value="gwg">{t('documents.suggestion.assetGwg', '按低值资产一次性费用化')}</option>
              <option value="asset">{t('documents.suggestion.assetCapitalize', '作为固定资产折旧')}</option>
            </select>
          </label>
        )}

        {allowedDepreciationMethods.length > 0 && (
          <label className="asset-confirmation-field">
            <span>{t('documents.suggestion.assetFields.depreciationMethod', '折旧方法')}</span>
            <select
              value={depreciationMethod}
              onChange={(event) => setDepreciationMethod(event.target.value)}
              disabled={props.confirmingAction !== null || (gwgElectionRequired && gwgTreatment === 'gwg')}
            >
              {allowedDepreciationMethods.map((method) => (
                <option key={method} value={method}>
                  {method === 'degressive'
                    ? t('documents.suggestion.assetDepreciation.degressive', '递减折旧')
                    : t('documents.suggestion.assetDepreciation.linear', '线性折旧')}
                </option>
              ))}
            </select>
          </label>
        )}

        {depreciationMethod === 'degressive' && (
          <label className="asset-confirmation-field">
            <span>{t('documents.suggestion.assetFields.degressiveRate', '递减折旧比例')}</span>
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
            <span>{t('documents.suggestion.assetFields.usefulLifeYears', '使用年限')}</span>
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
