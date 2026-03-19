import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { normalizeLanguage } from '../utils/locale';
import { useAuthStore } from '../stores/authStore';
import { propertyService } from '../services/propertyService';
import { Property } from '../types/property';
import { taxFilingService, TaxFilingSummary } from '../services/taxFilingService';
import { dashboardService } from '../services/dashboardService';
import WhatIfSimulator from '../components/dashboard/WhatIfSimulator';
import FlatRateComparison from '../components/dashboard/FlatRateComparison';
import RefundEstimate from '../components/dashboard/RefundEstimate';
import AITaxAdvisor from '../components/dashboard/AITaxAdvisor';
import EmployerDocumentsWorkbench from '../components/documents/EmployerDocumentsWorkbench';
import PropertyReports from '../components/properties/PropertyReports';
import SubpageBackLink from '../components/common/SubpageBackLink';
import './TaxToolsPage.css';

const pageCopy = {
  de: {
    title: 'Steuer-Tools',
    subtitle: 'Steuerstand, KI-Hinweise, Lohn-Dateien und Vermoegensberichte',
    back: 'Zurueck',
    taxPosition: 'Steuerstand',
    assetOverview: 'Vermoegensueberblick',
    assetOverviewDescription: 'Hier laufen Steuerstatus, Vermoegen und lohnbezogene Dateien zusammen.',
    trackedAssets: 'Erfasste Assets',
    activeProperties: 'Aktive Immobilien',
    rentalIncome: 'Mieteinnahmen',
    propertyExpenses: 'Objektkosten',
    netRentalIncome: 'Netto-Mietergebnis',
    assetReport: 'Vermoegensbericht',
    noAssets: 'Keine Vermoegenswerte',
    filingSummary: 'Jahresuebersicht Steuerdaten',
    selectYear: 'Steuerjahr waehlen',
    noData: 'Keine bestaetigten Daten fuer dieses Jahr',
    income: 'Einkuenfte',
    deductions: 'Absetzbetraege',
    vatSummary: 'Umsatzsteuer',
    taxableIncome: 'Zu versteuerndes Einkommen',
    estimatedTax: 'Geschaetzte Steuer',
    withheldTax: 'Einbehaltene Steuer',
    estimatedRefund: 'Geschaetzte Rueckerstattung',
    vatPayable: 'USt-Zahllast',
    records: 'Datensaetze',
    source: 'Quelle',
    noYears: 'Noch keine bestaetigten Steuerdaten vorhanden',
    conflictsWarning: 'Datenkonflikte erkannt',
    conflictSource: 'Dokument',
  },
  en: {
    title: 'Tax Tools',
    subtitle: 'Tax position, AI guidance, payroll files and asset reports',
    back: 'Back',
    taxPosition: 'Tax position',
    assetOverview: 'Asset overview',
    assetOverviewDescription: 'Tax status, tracked assets, and payroll file support live together here.',
    trackedAssets: 'Tracked assets',
    activeProperties: 'Active properties',
    rentalIncome: 'Rental income',
    propertyExpenses: 'Property expenses',
    netRentalIncome: 'Net rental income',
    assetReport: 'Asset Report',
    noAssets: 'No assets found',
    filingSummary: 'Annual Tax Data Summary',
    selectYear: 'Select tax year',
    noData: 'No confirmed data for this year',
    income: 'Income',
    deductions: 'Deductions',
    vatSummary: 'VAT',
    taxableIncome: 'Taxable Income',
    estimatedTax: 'Estimated Tax',
    withheldTax: 'Withheld Tax',
    estimatedRefund: 'Estimated Refund',
    vatPayable: 'VAT Payable',
    records: 'records',
    source: 'Source',
    noYears: 'No confirmed tax data yet',
    conflictsWarning: 'Data conflicts detected',
    conflictSource: 'Document',
  },
  zh: {
    title: '税务工具',
    subtitle: '税款状态、AI 建议、工资文件与资产报告',
    back: '返回',
    taxPosition: '税务结算',
    assetOverview: '资产概览',
    assetOverviewDescription: '税款状态、已跟踪资产和工资文件支持都集中在这里。',
    trackedAssets: '已跟踪资产',
    activeProperties: '活跃房产',
    rentalIncome: '租金收入',
    propertyExpenses: '房产支出',
    netRentalIncome: '净租金收入',
    assetReport: '资产报告',
    noAssets: '暂无资产',
    filingSummary: '年度税务数据汇总',
    selectYear: '选择税务年度',
    noData: '该年度暂无已确认数据',
    income: '收入',
    deductions: '扣除项',
    vatSummary: '增值税',
    taxableIncome: '应税收入',
    estimatedTax: '预估税额',
    withheldTax: '已扣税额',
    estimatedRefund: '预估退税',
    vatPayable: '增值税应缴',
    records: '条记录',
    source: '来源',
    noYears: '暂无已确认的税务数据',
    conflictsWarning: '检测到数据冲突',
    conflictSource: '文档',
  },
} as const;

type AssetOption = {
  id: string;
  label: string;
};

const TaxToolsPage = () => {
  const { i18n } = useTranslation();
  const lang = normalizeLanguage(i18n.resolvedLanguage || i18n.language);
  const c = pageCopy[lang];
  const { user } = useAuthStore();
  const currentYear = new Date().getFullYear();
  const showFlatRate = user?.user_type === 'self_employed' || user?.user_type === 'mixed';
  const showEmployerWorkbench = Boolean(
    user &&
    (user.employer_mode || 'none') !== 'none' &&
    ['self_employed', 'mixed'].includes(user.user_type)
  );

  const [allAssets, setAllAssets] = useState<AssetOption[]>([]);
  const [selectedAsset, setSelectedAsset] = useState<Property | null>(null);
  const [loading, setLoading] = useState(false);
  const [assetCounts, setAssetCounts] = useState({ properties: 0, assets: 0 });
  const [propertyMetrics, setPropertyMetrics] = useState<any>(null);
  const [dashboardData, setDashboardData] = useState<any>(null);

  const [filingYears, setFilingYears] = useState<number[]>([]);
  const [selectedYear, setSelectedYear] = useState<number | null>(null);
  const [filingSummary, setFilingSummary] = useState<TaxFilingSummary | null>(null);
  const [filingLoading, setFilingLoading] = useState(false);

  const hasTransactions = Boolean(
    dashboardData && (dashboardData.yearToDateIncome > 0 || dashboardData.yearToDateExpenses > 0)
  );
  const showRefundEstimate = !user || user.user_type !== 'gmbh';
  const showAssetOverview = assetCounts.assets > 0 || assetCounts.properties > 0 || propertyMetrics?.has_properties;

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
    const loadContext = async () => {
      let propertiesCount = 0;
      let assetsCount = 0;
      const nextAssets: AssetOption[] = [];

      const [propertyResult, assetResult, metricsResult, dashboardResult] = await Promise.all([
        propertyService.getProperties(true).catch(() => null),
        propertyService.getAssets(true).catch(() => null),
        dashboardService.getPropertyMetrics(currentYear).catch(() => null),
        dashboardService.getDashboardData(currentYear).catch(() => null),
      ]);

      if (propertyResult?.properties) {
        propertiesCount = propertyResult.properties.length;
        for (const property of propertyResult.properties) {
          nextAssets.push({ id: property.id, label: `🏠 ${property.address}` });
        }
      }

      if (assetResult?.assets) {
        assetsCount = assetResult.assets.length;
        for (const asset of assetResult.assets) {
          const icon = asset.asset_type === 'vehicle' || asset.asset_type === 'electric_vehicle'
            ? '🚗'
            : asset.asset_type === 'computer' || asset.asset_type === 'phone'
              ? '💻'
              : asset.asset_type === 'machinery' || asset.asset_type === 'tools'
                ? '⚙️'
                : '📦';
          nextAssets.push({ id: asset.id, label: `${icon} ${asset.name || asset.asset_type}` });
        }
      }

      setAllAssets(nextAssets);
      setAssetCounts({ properties: propertiesCount, assets: assetsCount + propertiesCount });
      setPropertyMetrics(metricsResult);
      setDashboardData(dashboardResult);

      if (nextAssets.length > 0) {
        void fetchFull(nextAssets[0].id);
      } else {
        setSelectedAsset(null);
      }
    };

    void loadContext();
  }, [currentYear]);

  useEffect(() => {
    taxFilingService.getAvailableYears().then((years) => {
      setFilingYears(years);
      if (years.length > 0) {
        setSelectedYear(years[0]);
      }
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedYear) {
      return;
    }

    setFilingLoading(true);
    taxFilingService.getSummary(selectedYear)
      .then(setFilingSummary)
      .catch(() => setFilingSummary(null))
      .finally(() => setFilingLoading(false));
  }, [selectedYear]);

  return (
    <div className="tax-tools-page">
      <div className="tax-tools-header">
        <SubpageBackLink to="/advanced" label={c.back} />
        <h1>{c.title}</h1>
        <p>{c.subtitle}</p>
      </div>

      <div className="tax-tools-content">
        {showRefundEstimate && hasTransactions && (
          <section className="asset-report-section">
            <h3>💶 {c.taxPosition}</h3>
            <RefundEstimate
              estimatedRefund={dashboardData?.estimatedRefund}
              withheldTax={dashboardData?.withheldTax}
              calculatedTax={dashboardData?.calculatedTax}
              hasLohnzettel={dashboardData?.hasLohnzettel}
            />
          </section>
        )}

        {showAssetOverview && (
          <section className="asset-report-section">
            <h3>📦 {c.assetOverview}</h3>
            <p className="tax-tools-section-subtitle">{c.assetOverviewDescription}</p>
            <div className="tax-tools-summary-grid">
              <div className="tax-tools-summary-card">
                <span className="tax-tools-summary-label">{c.trackedAssets}</span>
                <strong>{assetCounts.assets}</strong>
              </div>
              <div className="tax-tools-summary-card">
                <span className="tax-tools-summary-label">{c.activeProperties}</span>
                <strong>{propertyMetrics?.active_properties_count ?? 0}</strong>
              </div>
              <div className="tax-tools-summary-card positive">
                <span className="tax-tools-summary-label">{c.rentalIncome}</span>
                <strong>€ {(propertyMetrics?.total_rental_income ?? 0).toLocaleString('de-AT', { minimumFractionDigits: 2 })}</strong>
              </div>
              <div className="tax-tools-summary-card warning">
                <span className="tax-tools-summary-label">{c.propertyExpenses}</span>
                <strong>€ {(propertyMetrics?.total_property_expenses ?? 0).toLocaleString('de-AT', { minimumFractionDigits: 2 })}</strong>
              </div>
              <div className="tax-tools-summary-card">
                <span className="tax-tools-summary-label">{c.netRentalIncome}</span>
                <strong>€ {(propertyMetrics?.net_rental_income ?? 0).toLocaleString('de-AT', { minimumFractionDigits: 2 })}</strong>
              </div>
            </div>
          </section>
        )}

        {hasTransactions && <AITaxAdvisor />}

        {showEmployerWorkbench && <EmployerDocumentsWorkbench />}

        <WhatIfSimulator />
        {showFlatRate && <FlatRateComparison />}

        <section className="asset-report-section">
          <h3>📊 {c.filingSummary}</h3>
          {filingYears.length === 0 ? (
            <p className="text-muted">{c.noYears}</p>
          ) : (
            <>
              <label className="tax-tools-select-label" htmlFor="tax-tools-year-select">
                {c.selectYear}
              </label>
              <select
                id="tax-tools-year-select"
                className="asset-select"
                value={selectedYear ?? ''}
                onChange={(e) => setSelectedYear(Number(e.target.value))}
              >
                {filingYears.map((year) => (
                  <option key={year} value={year}>
                    {year}
                  </option>
                ))}
              </select>

              {filingLoading && <p>...</p>}
              {!filingLoading && filingSummary && filingSummary.record_count === 0 && (
                <p className="text-muted">{c.noData}</p>
              )}
              {!filingLoading && filingSummary && filingSummary.record_count > 0 && (
                <div className="filing-summary">
                  <div className="filing-totals-grid">
                    <div className="filing-total-card">
                      <span className="filing-label">{c.taxableIncome}</span>
                      <span className="filing-value">€ {filingSummary.totals.taxable_income.toLocaleString('de-AT', { minimumFractionDigits: 2 })}</span>
                    </div>
                    <div className="filing-total-card">
                      <span className="filing-label">{c.estimatedTax}</span>
                      <span className="filing-value">€ {filingSummary.totals.estimated_tax.toLocaleString('de-AT', { minimumFractionDigits: 2 })}</span>
                    </div>
                    <div className="filing-total-card">
                      <span className="filing-label">{c.withheldTax}</span>
                      <span className="filing-value">€ {filingSummary.totals.withheld_tax.toLocaleString('de-AT', { minimumFractionDigits: 2 })}</span>
                    </div>
                    <div className={`filing-total-card ${filingSummary.totals.estimated_refund >= 0 ? 'positive' : 'negative'}`}>
                      <span className="filing-label">{c.estimatedRefund}</span>
                      <span className="filing-value">€ {filingSummary.totals.estimated_refund.toLocaleString('de-AT', { minimumFractionDigits: 2 })}</span>
                    </div>
                  </div>

                  {filingSummary.conflicts && filingSummary.conflicts.length > 0 && (
                    <div className="tax-tools-conflict-bar">
                      <div className="tax-tools-conflict-title">
                        <span>⚠️</span> {c.conflictsWarning}
                      </div>
                      {filingSummary.conflicts.map((conflict: any, idx: number) => (
                        <div
                          key={`${conflict.description || conflict.message || idx}-${idx}`}
                          className="tax-tools-conflict-item"
                        >
                          {conflict.description || conflict.message || JSON.stringify(conflict)}
                          {conflict.source_document_ids && (
                            <span className="tax-tools-conflict-source">
                              ({c.conflictSource}: {conflict.source_document_ids.join(', ')})
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {filingSummary.income.length > 0 && (
                    <div className="filing-section">
                      <h4>💰 {c.income} (€ {filingSummary.totals.total_income.toLocaleString('de-AT', { minimumFractionDigits: 2 })})</h4>
                      {filingSummary.income.map((item) => (
                        <div key={item.id} className="filing-item">
                          <span className="filing-item-type">{item.data_type}</span>
                          <span className="filing-item-doc">{c.source}: #{item.source_document_id}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {filingSummary.deductions.length > 0 && (
                    <div className="filing-section">
                      <h4>📝 {c.deductions} (€ {filingSummary.totals.total_deductions.toLocaleString('de-AT', { minimumFractionDigits: 2 })})</h4>
                      {filingSummary.deductions.map((item) => (
                        <div key={item.id} className="filing-item">
                          <span className="filing-item-type">{item.data_type}</span>
                          <span className="filing-item-doc">{c.source}: #{item.source_document_id}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {filingSummary.vat.length > 0 && (
                    <div className="filing-section">
                      <h4>🧾 {c.vatSummary} ({c.vatPayable}: € {filingSummary.totals.total_vat_payable.toLocaleString('de-AT', { minimumFractionDigits: 2 })})</h4>
                      {filingSummary.vat.map((item) => (
                        <div key={item.id} className="filing-item">
                          <span className="filing-item-type">{item.data_type}</span>
                          <span className="filing-item-doc">{c.source}: #{item.source_document_id}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  <p className="text-muted tax-tools-record-count">
                    {filingSummary.record_count} {c.records}
                  </p>
                </div>
              )}
            </>
          )}
        </section>

        <section className="asset-report-section">
          <h3>📋 {c.assetReport}</h3>
          {allAssets.length === 0 ? (
            <p className="text-muted">{c.noAssets}</p>
          ) : (
            <>
              <select
                className="asset-select"
                value={selectedAsset?.id ?? ''}
                onChange={(e) => fetchFull(e.target.value)}
              >
                {allAssets.map((asset) => (
                  <option key={asset.id} value={asset.id}>
                    {asset.label}
                  </option>
                ))}
              </select>
              {loading && <p>...</p>}
              {!loading && selectedAsset && <PropertyReports property={selectedAsset} />}
            </>
          )}
        </section>
      </div>
    </div>
  );
};

export default TaxToolsPage;
