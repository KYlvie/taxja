import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import Select from '../components/common/Select';
import {
  BarChart3,
  Briefcase,
  Calculator,
  ClipboardCheck,
  ClipboardList,
  Landmark,
  NotebookTabs,
  ReceiptText,
  Scale,
  Sliders,
  TriangleAlert,
  Wallet,
  type LucideIcon,
} from 'lucide-react';
import { getLocaleForLanguage } from '../utils/locale';
import { useAuthStore } from '../stores/authStore';
import { taxFilingService, TaxFilingSummary } from '../services/taxFilingService';
import { dashboardService } from '../services/dashboardService';
import WhatIfSimulator from '../components/dashboard/WhatIfSimulator';
import FlatRateComparison from '../components/dashboard/FlatRateComparison';
import RefundEstimate from '../components/dashboard/RefundEstimate';
import AITaxAdvisor from '../components/dashboard/AITaxAdvisor';
import EmployerDocumentsWorkbench from '../components/documents/EmployerDocumentsWorkbench';
import AuditChecklist from '../components/reports/AuditChecklist';
import YearWarning from '../components/reports/YearWarning';
import FuturisticIcon from '../components/common/FuturisticIcon';
import SubpageBackLink from '../components/common/SubpageBackLink';
import './TaxToolsPage.css';

type TaxTool = 'refund' | 'whatIf' | 'flatRate' | 'filing' | 'employer' | 'audit';

interface ToolDef {
  id: TaxTool;
  icon: LucideIcon;
  label: string;
  desc: string;
}

const TaxToolsSectionHeading = ({
  icon,
  tone,
  title,
}: {
  icon: LucideIcon;
  tone: 'emerald' | 'amber' | 'violet' | 'rose';
  title: string;
}) => (
  <h3 className="tax-tools-heading">
    <FuturisticIcon icon={icon} tone={tone} size="sm" />
    <span>{title}</span>
  </h3>
);

const TaxToolsPage = () => {
  const { t, i18n } = useTranslation();
  const { user } = useAuthStore();
  const currentYear = new Date().getFullYear();
  const showFlatRate = user?.user_type === 'self_employed' || user?.user_type === 'mixed';
  const showEmployerWorkbench = Boolean(
    user &&
      (user.employer_mode || 'none') !== 'none' &&
      ['self_employed', 'mixed'].includes(user.user_type),
  );

  const [selectedTool, setSelectedTool] = useState<TaxTool>('refund');
  const [dashboardData, setDashboardData] = useState<any>(null);
  const [filingYears, setFilingYears] = useState<number[]>([]);
  const [selectedYear, setSelectedYear] = useState<number | null>(null);
  const [filingSummary, setFilingSummary] = useState<TaxFilingSummary | null>(null);
  const [filingLoading, setFilingLoading] = useState(false);
  const [auditYear, setAuditYear] = useState(currentYear);

  const hasTransactions = Boolean(
    dashboardData && (dashboardData.yearToDateIncome > 0 || dashboardData.yearToDateExpenses > 0),
  );
  const showRefundEstimate = !user || user.user_type !== 'gmbh';

  useEffect(() => {
    dashboardService
      .getDashboardData(currentYear)
      .then(setDashboardData)
      .catch(() => setDashboardData(null));
  }, [currentYear]);

  useEffect(() => {
    taxFilingService
      .getAvailableYears()
      .then((years) => {
        setFilingYears(years);
        if (years.length > 0) {
          setSelectedYear(years[0]);
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedYear) {
      return;
    }

    setFilingLoading(true);
    taxFilingService
      .getSummary(selectedYear)
      .then(setFilingSummary)
      .catch(() => setFilingSummary(null))
      .finally(() => setFilingLoading(false));
  }, [selectedYear]);

  /* ── Tool definitions ─────────────────────────────────── */
  const tools: ToolDef[] = [
    {
      id: 'refund',
      icon: Calculator,
      label: t('taxTools.refund.title', 'Tax Estimate'),
      desc: t('taxTools.refund.desc', 'View estimated refund'),
    },
    {
      id: 'whatIf',
      icon: Sliders,
      label: t('taxTools.whatIf.title', 'What-If Simulator'),
      desc: t('taxTools.whatIf.desc', 'Test tax scenarios'),
    },
    {
      id: 'flatRate',
      icon: Scale,
      label: t('taxTools.flatRate.title', 'Flat Rate Comparison'),
      desc: t('taxTools.flatRate.desc', 'Compare tax methods'),
    },
    {
      id: 'filing',
      icon: BarChart3,
      label: t('taxTools.filing.title', 'Filing Summary'),
      desc: t('taxTools.filing.desc', 'Annual tax data'),
    },
    ...(showEmployerWorkbench
      ? [
          {
            id: 'employer' as TaxTool,
            icon: Briefcase,
            label: t('taxTools.employer.title', 'Employer Workbench'),
            desc: t('taxTools.employer.desc', 'Payroll documents'),
          },
        ]
      : []),
    {
      id: 'audit',
      icon: ClipboardCheck,
      label: t('taxTools.audit.title', 'Audit Checklist'),
      desc: t('taxTools.audit.desc', 'Filing readiness check'),
    },
  ];

  /* ── Section renderers ────────────────────────────────── */

  const renderRefund = () => (
    <>
      {showRefundEstimate && hasTransactions && (
        <section className="asset-report-section">
          <TaxToolsSectionHeading
            icon={Landmark}
            tone="emerald"
            title={t('taxTools.page.taxPosition', 'Tax position')}
          />
          <RefundEstimate
            estimatedRefund={dashboardData?.estimatedRefund}
            withheldTax={dashboardData?.withheldTax}
            calculatedTax={dashboardData?.calculatedTax}
            hasLohnzettel={dashboardData?.hasLohnzettel}
          />
        </section>
      )}
      {hasTransactions && <AITaxAdvisor />}
      {!showRefundEstimate && !hasTransactions && (
        <p className="text-muted">{t('taxTools.page.noData', 'No data available yet. Upload documents to see your tax estimate.')}</p>
      )}
    </>
  );

  const renderWhatIf = () => <WhatIfSimulator />;

  const renderFlatRate = () =>
    showFlatRate ? <FlatRateComparison /> : (
      <p className="text-muted">{t('taxTools.page.flatRateNotApplicable', 'Flat rate comparison is only available for self-employed users.')}</p>
    );

  const renderFiling = () => (
    <section className="asset-report-section">
      <TaxToolsSectionHeading
        icon={BarChart3}
        tone="violet"
        title={t('taxTools.page.filingSummary', 'Annual Tax Data Summary')}
      />
      {filingYears.length === 0 ? (
        <p className="text-muted">{t('taxTools.page.noYears', 'No confirmed tax data yet')}</p>
      ) : (
        <>
          <label className="tax-tools-select-label" htmlFor="tax-tools-year-select">
            {t('taxTools.page.selectYear', 'Select tax year')}
          </label>
          <Select
            id="tax-tools-year-select"
            value={selectedYear != null ? String(selectedYear) : ''}
            onChange={(value) => setSelectedYear(Number(value))}
            options={filingYears.map((year) => ({ value: String(year), label: String(year) }))}
            size="sm"
          />

          {filingLoading && <p>...</p>}
          {!filingLoading && !filingSummary && selectedYear && (
            <p className="text-muted">{t('taxTools.page.noData', 'No confirmed data for this year')}</p>
          )}
          {!filingLoading && filingSummary && filingSummary.record_count === 0 && (
            <p className="text-muted">{t('taxTools.page.noData', 'No confirmed data for this year')}</p>
          )}
          {!filingLoading && filingSummary && filingSummary.record_count > 0 && (
            <div className="filing-summary">
              <div className="filing-totals-grid">
                <div className="filing-total-card">
                  <span className="filing-label">{t('taxTools.page.taxableIncome', 'Taxable Income')}</span>
                  <span className="filing-value">
                    €{' '}
                    {filingSummary.totals.taxable_income.toLocaleString(
                      getLocaleForLanguage(i18n.language),
                      { minimumFractionDigits: 2 },
                    )}
                  </span>
                </div>
                <div className="filing-total-card">
                  <span className="filing-label">{t('taxTools.page.estimatedTax', 'Estimated Tax')}</span>
                  <span className="filing-value">
                    €{' '}
                    {filingSummary.totals.estimated_tax.toLocaleString(
                      getLocaleForLanguage(i18n.language),
                      { minimumFractionDigits: 2 },
                    )}
                  </span>
                </div>
                <div className="filing-total-card">
                  <span className="filing-label">{t('taxTools.page.withheldTax', 'Withheld Tax')}</span>
                  <span className="filing-value">
                    €{' '}
                    {filingSummary.totals.withheld_tax.toLocaleString(
                      getLocaleForLanguage(i18n.language),
                      { minimumFractionDigits: 2 },
                    )}
                  </span>
                </div>
                <div
                  className={`filing-total-card ${
                    filingSummary.totals.estimated_refund >= 0 ? 'positive' : 'negative'
                  }`}
                >
                  <span className="filing-label">{t('taxTools.page.estimatedRefund', 'Estimated Refund')}</span>
                  <span className="filing-value">
                    €{' '}
                    {filingSummary.totals.estimated_refund.toLocaleString(
                      getLocaleForLanguage(i18n.language),
                      { minimumFractionDigits: 2 },
                    )}
                  </span>
                </div>
              </div>

              {filingSummary.conflicts && filingSummary.conflicts.length > 0 && (
                <div className="tax-tools-conflict-bar">
                  <div className="tax-tools-conflict-title">
                    <FuturisticIcon icon={TriangleAlert} tone="amber" size="xs" />{' '}
                    {t('taxTools.page.conflictsWarning', 'Data conflicts detected')}
                  </div>
                  {filingSummary.conflicts.map((conflict: any, idx: number) => (
                    <div
                      key={`${conflict.description || conflict.message || idx}-${idx}`}
                      className="tax-tools-conflict-item"
                    >
                      {conflict.description || conflict.message || JSON.stringify(conflict)}
                      {conflict.source_document_ids && (
                        <span className="tax-tools-conflict-source">
                          ({t('taxTools.page.conflictSource', 'Document')}: {conflict.source_document_ids.join(', ')})
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {filingSummary.income.length > 0 && (
                <div className="filing-section">
                  <h4 className="tax-tools-subheading">
                    <FuturisticIcon icon={Wallet} tone="emerald" size="xs" />
                    <span>
                      {t('taxTools.page.income', 'Income')} (
                      €{' '}
                      {filingSummary.totals.total_income.toLocaleString(
                        getLocaleForLanguage(i18n.language),
                        { minimumFractionDigits: 2 },
                      )}
                      )
                    </span>
                  </h4>
                  {filingSummary.income.map((item) => (
                    <div key={item.id} className="filing-item">
                      <span className="filing-item-type">{item.data_type}</span>
                      <span className="filing-item-doc">
                        {t('taxTools.page.source', 'Source')}: #{item.source_document_id}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {filingSummary.deductions.length > 0 && (
                <div className="filing-section">
                  <h4 className="tax-tools-subheading">
                    <FuturisticIcon icon={ClipboardList} tone="amber" size="xs" />
                    <span>
                      {t('taxTools.page.deductions', 'Deductions')} (
                      €{' '}
                      {filingSummary.totals.total_deductions.toLocaleString(
                        getLocaleForLanguage(i18n.language),
                        { minimumFractionDigits: 2 },
                      )}
                      )
                    </span>
                  </h4>
                  {filingSummary.deductions.map((item) => (
                    <div key={item.id} className="filing-item">
                      <span className="filing-item-type">{item.data_type}</span>
                      <span className="filing-item-doc">
                        {t('taxTools.page.source', 'Source')}: #{item.source_document_id}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {filingSummary.vat.length > 0 && (
                <div className="filing-section">
                  <h4 className="tax-tools-subheading">
                    <FuturisticIcon icon={ReceiptText} tone="violet" size="xs" />
                    <span>
                      {t('taxTools.page.vatSummary', 'VAT')} ({t('taxTools.page.vatPayable', 'VAT Payable')}: €{' '}
                      {filingSummary.totals.total_vat_payable.toLocaleString(
                        getLocaleForLanguage(i18n.language),
                        { minimumFractionDigits: 2 },
                      )}
                      )
                    </span>
                  </h4>
                  {filingSummary.vat.map((item) => (
                    <div key={item.id} className="filing-item">
                      <span className="filing-item-type">{item.data_type}</span>
                      <span className="filing-item-doc">
                        {t('taxTools.page.source', 'Source')}: #{item.source_document_id}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              <p className="text-muted tax-tools-record-count">
                {filingSummary.record_count} {t('taxTools.page.records', 'records')}
              </p>
            </div>
          )}
        </>
      )}
    </section>
  );

  const renderEmployer = () => <EmployerDocumentsWorkbench />;

  const renderAudit = () => (
    <section className="asset-report-section audit-checklist-section">
      <TaxToolsSectionHeading
        icon={NotebookTabs}
        tone="rose"
        title={t('taxTools.page.auditChecklist', 'Audit Checklist')}
      />
      <div className="year-selector">
        <label htmlFor="audit-year">{t('taxTools.page.auditSelectYear', 'Select tax year')}</label>
        <Select
          id="audit-year"
          value={String(auditYear)}
          onChange={(v) => setAuditYear(Number(v))}
          options={Array.from({ length: 5 }, (_, i) => ({
            value: String(currentYear - i),
            label: String(currentYear - i),
          }))}
          size="sm"
        />
      </div>
      <YearWarning taxYear={auditYear} />
      <AuditChecklist taxYear={auditYear} />
    </section>
  );

  const renderContent = () => {
    switch (selectedTool) {
      case 'refund':
        return renderRefund();
      case 'whatIf':
        return renderWhatIf();
      case 'flatRate':
        return renderFlatRate();
      case 'filing':
        return renderFiling();
      case 'employer':
        return renderEmployer();
      case 'audit':
        return renderAudit();
      default:
        return null;
    }
  };

  return (
    <div className="tax-tools-page">
      <div className="tax-tools-header">
        <SubpageBackLink to="/advanced" label={t('taxTools.page.back', 'Back')} />
        <h1>{t('taxTools.page.title', 'Tax Tools')}</h1>
        <p>{t('taxTools.page.subtitle', 'Tax position, AI guidance, payroll files and filings in one place')}</p>
      </div>

      <div className="tax-tools-layout">
        <nav className="tax-tools-sidebar">
          {tools.map((tool) => (
            <button
              key={tool.id}
              className={`tax-tools-nav-item ${selectedTool === tool.id ? 'active' : ''}`}
              onClick={() => setSelectedTool(tool.id)}
            >
              <tool.icon size={20} />
              <div>
                <div className="nav-item-label">{tool.label}</div>
                <div className="nav-item-desc">{tool.desc}</div>
              </div>
            </button>
          ))}
        </nav>
        <main className="tax-tools-content">
          {renderContent()}
        </main>
      </div>
    </div>
  );
};

export default TaxToolsPage;
