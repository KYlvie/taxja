import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Building2, Package, LibraryBig, type LucideIcon, ChevronDown, ChevronUp } from 'lucide-react';
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
import './LiabilitiesPage.css';

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
  collapsed,
  onToggle,
}: {
  icon: LucideIcon;
  tone: 'cyan' | 'amber' | 'violet';
  title: string;
  collapsed?: boolean;
  onToggle?: () => void;
}) => (
  <h3
    className={`tax-tools-heading ${onToggle ? 'collapsible' : ''}`}
    onClick={onToggle}
    style={onToggle ? { cursor: 'pointer', userSelect: 'none' } : undefined}
  >
    <FuturisticIcon icon={icon} tone={tone} size="sm" />
    <span>{title}</span>
    {onToggle && (collapsed ? <ChevronDown size={18} /> : <ChevronUp size={18} />)}
  </h3>
);

const AssetInsightsPage = () => {
  const { t, i18n } = useTranslation();
  const locale = getLocaleForLanguage(i18n.language);

  const [allAssets, setAllAssets] = useState<AssetOption[]>([]);
  const [rawAssets, setRawAssets] = useState<any[]>([]);
  const [selectedAsset, setSelectedAsset] = useState<Property | null>(null);

  // All sections start collapsed
  const [collapsedSections, setCollapsedSections] = useState<Set<string>>(
    new Set(['portfolio', 'otherAssets', 'assetReport'])
  );
  const toggleSection = (key: string) => {
    setCollapsedSections((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };
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
        <h1>{t('assetOverview.pageTitle', 'Asset Overview')}</h1>
        <p>{t('assetOverview.pageSubtitle', 'Assets, depreciation, net worth, and individual reports in one place.')}</p>
      </div>

      <div className="tax-tools-content">
        {/* ── Asset Overview Summary (always visible) ── */}
        <section className="liability-panel card">
          <h2>{t('assetOverview.summaryTitle', 'Asset Overview')}</h2>

          {loadingLiabilities ? (
            <p className="text-muted">{t('common.loading', 'Loading...')}</p>
          ) : liabilitySummary ? (
            <>
              <div className="liability-overview-balance" style={{ marginBottom: '16px' }}>
                <article className="liability-highlight-card">
                  <span>{t('assetOverview.balanceSnapshot', 'Balance snapshot')}</span>
                  <strong>{fmtCurrency(liabilitySummary.net_worth)}</strong>
                  <p>{t('assetOverview.balanceSnapshotHint', 'Current asset carrying values combined with all tracked liabilities.')}</p>
                </article>
                <article className="liability-highlight-card">
                  <span>{t('assetOverview.annualDepreciation', 'Annual depreciation')}</span>
                  <strong>{fmtCurrency(
                    (propertyMetrics?.total_property_expenses ?? 0) + nonReAssetTotalDepreciation
                  )}</strong>
                  <p>{t('assetOverview.annualDepreciationHint', 'Total depreciation across all properties and other assets for the current year.')}</p>
                </article>
              </div>

              <div className="liability-overview-grid">
                <article className="liability-metric-card">
                  <span className="liability-metric-label">{t('assetOverview.totalAssets', 'Total Assets')}</span>
                  <strong className="liability-metric-value">{fmtCurrency(liabilitySummary.total_assets)}</strong>
                  <span className="liability-metric-note">{t('assetOverview.totalAssetsNote', 'Carrying value of all registered assets')}</span>
                </article>
                <article className="liability-metric-card">
                  <span className="liability-metric-label">{t('assetOverview.totalLiabilities', 'Total Liabilities')}</span>
                  <strong className="liability-metric-value">{fmtCurrency(liabilitySummary.total_liabilities)}</strong>
                  <span className="liability-metric-note">{t('assetOverview.totalLiabilitiesNote', 'Open balances across all active liabilities')}</span>
                </article>
                <article className="liability-metric-card">
                  <span className="liability-metric-label">{t('assetOverview.netWorth', 'Net Worth')}</span>
                  <strong className="liability-metric-value">{fmtCurrency(liabilitySummary.net_worth)}</strong>
                  <span className="liability-metric-note">{t('assetOverview.netWorthNote', 'Assets minus liabilities')}</span>
                </article>
                <article className="liability-metric-card">
                  <span className="liability-metric-label">{t('assetOverview.propertyCount', 'Properties')}</span>
                  <strong className="liability-metric-value">{propertyMetrics?.active_properties_count ?? propertiesCount}</strong>
                  <span className="liability-metric-note">{t('assetOverview.propertyCountNote', 'Active real estate properties')}</span>
                </article>
                <article className="liability-metric-card">
                  <span className="liability-metric-label">{t('assetOverview.otherAssetCount', 'Other Assets')}</span>
                  <strong className="liability-metric-value">{nonReAssetsCount}</strong>
                  <span className="liability-metric-note">{t('assetOverview.otherAssetCountNote', 'Devices, vehicles, and equipment')}</span>
                </article>
                <article className="liability-metric-card">
                  <span className="liability-metric-label">{t('assetOverview.monthlyDebtService', 'Monthly Debt Service')}</span>
                  <strong className="liability-metric-value">{fmtCurrency(liabilitySummary.monthly_debt_service)}</strong>
                  <span className="liability-metric-note">{t('assetOverview.monthlyDebtServiceNote', 'Scheduled repayments currently on file')}</span>
                </article>
              </div>
            </>
          ) : (
            <p className="text-muted">{t('assetOverview.noSummary', 'No summary available yet. Add assets or liabilities to populate the overview.')}</p>
          )}
        </section>

        {/* ── Section A: Property Portfolio ── */}
        <section className={`asset-report-section ${collapsedSections.has('portfolio') ? 'collapsed' : ''}`}>
          <SectionHeading icon={Building2} tone="cyan" title={t('properties.portfolio.title', 'Property Portfolio')} collapsed={collapsedSections.has('portfolio')} onToggle={() => toggleSection('portfolio')} />
          {!collapsedSections.has('portfolio') && (<>
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
                </>)}
</section>

        {/* ── Section B: Other Assets (Devices, Vehicles, etc.) ── */}
        <section className={`asset-report-section ${collapsedSections.has('otherAssets') ? 'collapsed' : ''}`}>
          <SectionHeading icon={Package} tone="amber" title={t('properties.assetOverview.title', 'Other Assets')} collapsed={collapsedSections.has('otherAssets')} onToggle={() => toggleSection('otherAssets')} />
          {!collapsedSections.has('otherAssets') && (<>
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
                </>)}
</section>

        {/* ── Section C: Individual Asset Report ── */}
        <section className={`asset-report-section ${collapsedSections.has('assetReport') ? 'collapsed' : ''}`}>
          <SectionHeading icon={LibraryBig} tone="violet" title={t('properties.assetReport.title', 'Individual Asset Report')} collapsed={collapsedSections.has('assetReport')} onToggle={() => toggleSection('assetReport')} />
          {!collapsedSections.has('assetReport') && (<>
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
                </>)}
</section>
      </div>
    </div>
  );
};

export default AssetInsightsPage;
