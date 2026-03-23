import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Building2, Package, LibraryBig, Scale, type LucideIcon } from 'lucide-react';
import Select from '../components/common/Select';
import FuturisticIcon from '../components/common/FuturisticIcon';
import SubpageBackLink from '../components/common/SubpageBackLink';
import { PropertyComparison } from '../components/properties/PropertyComparison';
import PropertyReports from '../components/properties/PropertyReports';
import { propertyService } from '../services/propertyService';
import { dashboardService } from '../services/dashboardService';
import { liabilityService } from '../services/liabilityService';
import { Property } from '../types/property';
import { LiabilitySummary } from '../types/liability';
import { getLocaleForLanguage } from '../utils/locale';
import './TaxToolsPage.css';

type AssetOption = {
  id: string;
  label: string;
  group: string;
};

const assetLabelPrefix = (assetType: string | undefined, t: (key: string, defaultValue: string) => string) => {
  if (!assetType || assetType === 'real_estate') {
    return t('properties.assetCategory.property', 'Property');
  }
  if (assetType === 'vehicle' || assetType === 'electric_vehicle') {
    return t('properties.assetCategory.vehicle', 'Vehicle');
  }
  if (assetType === 'computer' || assetType === 'phone') {
    return t('properties.assetCategory.device', 'Device');
  }
  if (assetType === 'machinery' || assetType === 'tools') {
    return t('properties.assetCategory.tools', 'Tools');
  }
  return t('properties.assetCategory.asset', 'Asset');
};

const SectionHeading = ({
  icon,
  tone,
  title,
}: {
  icon: LucideIcon;
  tone: 'cyan' | 'amber' | 'violet';
  title: string;
}) => (
  <h3 className="tax-tools-heading">
    <FuturisticIcon icon={icon} tone={tone} size="sm" />
    <span>{title}</span>
  </h3>
);

const AssetInsightsPage = () => {
  const { t, i18n } = useTranslation();
  const locale = getLocaleForLanguage(i18n.language);

  const [allAssets, setAllAssets] = useState<AssetOption[]>([]);
  const [rawAssets, setRawAssets] = useState<any[]>([]);
  const [selectedAsset, setSelectedAsset] = useState<Property | null>(null);
  const [loading, setLoading] = useState(false);
  const [propertiesCount, setPropertiesCount] = useState(0);
  const [nonReAssetsCount, setNonReAssetsCount] = useState(0);
  const [propertyMetrics, setPropertyMetrics] = useState<any>(null);
  const [liabilitySummary, setLiabilitySummary] = useState<LiabilitySummary | null>(null);
  const [loadingLiabilities, setLoadingLiabilities] = useState(false);

  const fmtCurrency = (v: number) =>
    `€ ${v.toLocaleString(locale, { minimumFractionDigits: 2 })}`;

  const fetchFull = async (id: string) => {
    setLoading(true);
    try {
      const full = await propertyService.getProperty(id);
      setSelectedAsset(full);
    } catch {
      setSelectedAsset(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const loadLiabilities = async () => {
      setLoadingLiabilities(true);
      try {
        const data = await liabilityService.getSummary();
        setLiabilitySummary(data);
      } catch {
        setLiabilitySummary(null);
      } finally {
        setLoadingLiabilities(false);
      }
    };

    void loadLiabilities();
  }, []);

  useEffect(() => {
    const loadContext = async () => {
      const nextAssets: AssetOption[] = [];
      let pCount = 0;
      let aCount = 0;
      let assets: any[] = [];

      const [propertyResult, assetResult, metricsResult] = await Promise.all([
        propertyService.getProperties(true).catch(() => null),
        propertyService.getAssets(true).catch(() => null),
        dashboardService.getPropertyMetrics(new Date().getFullYear()).catch(() => null),
      ]);

      const propertyGroupLabel = t('properties.assetCategory.property', 'Property');
      if (propertyResult?.properties) {
        pCount = propertyResult.properties.length;
        for (const property of propertyResult.properties) {
          nextAssets.push({
            id: property.id,
            label: property.address,
            group: propertyGroupLabel,
          });
        }
      }

      if (assetResult?.assets) {
        aCount = assetResult.assets.length;
        assets = assetResult.assets;
        for (const asset of assetResult.assets) {
          const prefix = assetLabelPrefix(asset.asset_type, t);
          nextAssets.push({
            id: asset.id,
            label: `${asset.name || asset.asset_type}`,
            group: prefix,
          });
        }
      }

      setAllAssets(nextAssets);
      setRawAssets(assets);
      setPropertiesCount(pCount);
      setNonReAssetsCount(aCount);
      setPropertyMetrics(metricsResult);

      if (nextAssets.length > 0) {
        void fetchFull(nextAssets[0].id);
      } else {
        setSelectedAsset(null);
      }
    };

    void loadContext();
  }, []);

  // Compute non-RE asset metrics from raw data
  const nonReAssetTotalValue = rawAssets.reduce(
    (sum, a) => sum + (Number(a.purchase_price) || 0),
    0,
  );
  const nonReAssetTotalDepreciation = rawAssets.reduce(
    (sum, a) => sum + (Number(a.annual_depreciation) || Number(a.depreciation_rate) * Number(a.purchase_price) / 100 || 0),
    0,
  );

  // Build grouped options for the report selector
  const groupedOptions = (() => {
    const groups: Record<string, AssetOption[]> = {};
    for (const asset of allAssets) {
      if (!groups[asset.group]) groups[asset.group] = [];
      groups[asset.group].push(asset);
    }
    return Object.entries(groups).flatMap(([group, items]) => [
      { value: `__group__${group}`, label: `── ${group} ──`, disabled: true },
      ...items.map((item) => ({ value: String(item.id), label: `  ${item.label}` })),
    ]);
  })();

  return (
    <div className="tax-tools-page">
      <div className="tax-tools-header">
        <SubpageBackLink to="/advanced" label={t('common.back', 'Back')} />
        <h1>{t('assetOverview.pageTitle', 'Asset-Liability Overview')}</h1>
        <p>{t('assetOverview.pageSubtitle', 'Assets, liabilities, net worth, and individual reports in one place.')}</p>
      </div>

      <div className="tax-tools-content">
        {/* ── Section 0: Asset-Liability Summary ── */}
        <section className="asset-report-section">
          <SectionHeading icon={Scale} tone="cyan" title={t('assetOverview.liabilitySummary', 'Asset-Liability Summary')} />
          <p className="tax-tools-section-subtitle">
            {t('assetOverview.liabilitySummarySubtitle', 'High-level snapshot of your total assets, liabilities, and net worth.')}
          </p>

          {loadingLiabilities ? (
            <p className="text-muted">{t('common.loading', 'Loading...')}</p>
          ) : liabilitySummary ? (
            <div className="tax-tools-summary-grid">
              <div className="tax-tools-summary-card positive">
                <span className="tax-tools-summary-label">{t('assetOverview.totalAssets', 'Total Assets')}</span>
                <strong>{fmtCurrency(liabilitySummary.total_assets)}</strong>
              </div>
              <div className="tax-tools-summary-card warning">
                <span className="tax-tools-summary-label">{t('assetOverview.totalLiabilities', 'Total Liabilities')}</span>
                <strong>{fmtCurrency(liabilitySummary.total_liabilities)}</strong>
              </div>
              <div className="tax-tools-summary-card">
                <span className="tax-tools-summary-label">{t('assetOverview.netWorth', 'Net Worth')}</span>
                <strong>{fmtCurrency(liabilitySummary.net_worth)}</strong>
              </div>
              <div className="tax-tools-summary-card">
                <span className="tax-tools-summary-label">{t('assetOverview.monthlyDebtService', 'Monthly Debt Service')}</span>
                <strong>{fmtCurrency(liabilitySummary.monthly_debt_service)}</strong>
              </div>
            </div>
          ) : (
            <p className="text-muted">{t('assetOverview.noSummary', 'No summary available yet. Add assets or liabilities to populate the overview.')}</p>
          )}
        </section>

        {/* ── Section A: Property Portfolio ── */}
        <section className="asset-report-section">
          <SectionHeading icon={Building2} tone="cyan" title={t('properties.portfolio.title', 'Property Portfolio')} />
          <p className="tax-tools-section-subtitle">
            {t('properties.portfolio.subtitle', 'Overview and comparison of your real estate properties.')}
          </p>

          {propertiesCount > 0 || propertyMetrics?.has_properties ? (
            <>
              <div className="tax-tools-summary-grid">
                <div className="tax-tools-summary-card">
                  <span className="tax-tools-summary-label">{t('properties.portfolio.activeCount', 'Active properties')}</span>
                  <strong>{propertyMetrics?.active_properties_count ?? propertiesCount}</strong>
                </div>
                <div className="tax-tools-summary-card positive">
                  <span className="tax-tools-summary-label">{t('properties.portfolio.rentalIncome', 'Rental income')}</span>
                  <strong>{fmtCurrency(propertyMetrics?.total_rental_income ?? 0)}</strong>
                </div>
                <div className="tax-tools-summary-card warning">
                  <span className="tax-tools-summary-label">{t('properties.portfolio.expenses', 'Property expenses')}</span>
                  <strong>{fmtCurrency(propertyMetrics?.total_property_expenses ?? 0)}</strong>
                </div>
                <div className="tax-tools-summary-card">
                  <span className="tax-tools-summary-label">{t('properties.portfolio.netRental', 'Net rental income')}</span>
                  <strong>{fmtCurrency(propertyMetrics?.net_rental_income ?? 0)}</strong>
                </div>
              </div>
              <div className="tax-tools-comparison-panel">
                <PropertyComparison embedded />
              </div>
            </>
          ) : (
            <p className="text-muted">{t('properties.portfolio.noProperties', 'No properties yet. Upload a purchase contract to get started.')}</p>
          )}
        </section>

        {/* ── Section B: Other Assets (Devices, Vehicles, etc.) ── */}
        <section className="asset-report-section">
          <SectionHeading icon={Package} tone="amber" title={t('properties.assetOverview.title', 'Other Assets')} />
          <p className="tax-tools-section-subtitle">
            {t('properties.assetOverview.subtitle', 'Devices, vehicles, and other depreciable assets.')}
          </p>

          {nonReAssetsCount > 0 ? (
            <>
              <div className="tax-tools-summary-grid">
                <div className="tax-tools-summary-card">
                  <span className="tax-tools-summary-label">{t('properties.assetOverview.totalCount', 'Asset count')}</span>
                  <strong>{nonReAssetsCount}</strong>
                </div>
                <div className="tax-tools-summary-card">
                  <span className="tax-tools-summary-label">{t('properties.assetOverview.totalValue', 'Total purchase value')}</span>
                  <strong>{fmtCurrency(nonReAssetTotalValue)}</strong>
                </div>
                <div className="tax-tools-summary-card">
                  <span className="tax-tools-summary-label">{t('properties.assetOverview.totalDepreciation', 'Annual depreciation')}</span>
                  <strong>{fmtCurrency(nonReAssetTotalDepreciation)}</strong>
                </div>
              </div>

              <div className="tax-tools-comparison-panel">
                <div className="table-container">
                  <table className="comparison-table">
                    <thead>
                      <tr>
                        <th>{t('properties.assetName', 'Asset name')}</th>
                        <th>{t('properties.assetType', 'Type')}</th>
                        <th style={{ textAlign: 'right' }}>{t('properties.purchasePrice', 'Purchase price')}</th>
                        <th style={{ textAlign: 'right' }}>{t('properties.depreciationRate', 'Depreciation rate')}</th>
                        <th style={{ textAlign: 'right' }}>{t('properties.accumulatedDepreciation', 'Accumulated depreciation')}</th>
                        <th style={{ textAlign: 'right' }}>{t('properties.remainingValue', 'Remaining value')}</th>
                        <th>{t('properties.statusLabel', 'Status')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rawAssets.map((asset) => {
                        const price = Number(asset.purchase_price) || 0;
                        const accDep = Number(asset.accumulated_depreciation) || 0;
                        const remaining = Math.max(0, price - accDep);
                        const depRate = asset.depreciation_rate != null
                          ? `${(Number(asset.depreciation_rate) * 100).toFixed(2)}%`
                          : '—';
                        return (
                          <tr key={asset.id}>
                            <td className="address-cell">{asset.name || asset.address || '—'}</td>
                            <td>{String(t(`properties.assetTypes.${asset.asset_type}`, asset.asset_type))}</td>
                            <td style={{ textAlign: 'right' }}>{fmtCurrency(price)}</td>
                            <td style={{ textAlign: 'right' }}>{depRate}</td>
                            <td style={{ textAlign: 'right', color: accDep > 0 ? '#ef4444' : undefined }}>{accDep > 0 ? fmtCurrency(accDep) : '—'}</td>
                            <td style={{ textAlign: 'right', color: remaining > 0 ? '#22c55e' : undefined }}>{fmtCurrency(remaining)}</td>
                            <td>
                              <span className={`status-badge ${asset.status}`}>
                                {String(t(`properties.status.${asset.status}`, asset.status))}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                    <tfoot>
                      <tr className="total-row">
                        <td colSpan={2}><strong>{t('common.total', 'Total')}</strong></td>
                        <td style={{ textAlign: 'right' }}><strong>{fmtCurrency(nonReAssetTotalValue)}</strong></td>
                        <td style={{ textAlign: 'right' }}>—</td>
                        <td style={{ textAlign: 'right' }}><strong>{fmtCurrency(nonReAssetTotalDepreciation)}</strong></td>
                        <td style={{ textAlign: 'right' }}><strong>{fmtCurrency(Math.max(0, nonReAssetTotalValue - nonReAssetTotalDepreciation))}</strong></td>
                        <td>—</td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              </div>
            </>
          ) : (
            <p className="text-muted">{t('properties.assetOverview.noAssets', 'No other assets yet. Upload a purchase contract for equipment, vehicles, or devices.')}</p>
          )}
        </section>

        {/* ── Section C: Individual Asset Report ── */}
        <section className="asset-report-section">
          <SectionHeading icon={LibraryBig} tone="violet" title={t('properties.assetReport.title', 'Individual Asset Report')} />
          {allAssets.length === 0 ? (
            <p className="text-muted">{t('properties.assetReport.noAssets', 'No assets available for reporting.')}</p>
          ) : (
            <>
              <Select
                value={selectedAsset?.id ?? ''}
                onChange={(value) => {
                  if (!value.startsWith('__group__')) fetchFull(value);
                }}
                options={groupedOptions}
                size="sm"
              />
              {loading && <p>...</p>}
              {!loading && selectedAsset && <PropertyReports property={selectedAsset} />}
            </>
          )}
        </section>
      </div>
    </div>
  );
};

export default AssetInsightsPage;
