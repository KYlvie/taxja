import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import Select from '../components/common/Select';
import {
  BarChart3,
  Briefcase,
  ChevronDown,
  ChevronUp,
  ClipboardList,
  Landmark,
  NotebookTabs,
  ReceiptText,
  Scale,
  Sliders,
  Sparkles,
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
import { useFeatureAccess, FeatureLockedBanner } from '../components/subscription/withFeatureGate';
import './TaxToolsPage.css';

const SectionHeading = ({
  icon,
  tone,
  title,
  collapsed,
  onToggle,
}: {
  icon: LucideIcon;
  tone: 'emerald' | 'amber' | 'violet' | 'rose' | 'cyan';
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

  // Feature access checks
  const hasAIAccess = useFeatureAccess('ai_assistant');
  const hasAdvancedReports = useFeatureAccess('advanced_reports');

  const [dashboardData, setDashboardData] = useState<any>(null);
  const [filingYears, setFilingYears] = useState<number[]>([]);
  const [selectedYear, setSelectedYear] = useState<number | null>(null);
  const [filingSummary, setFilingSummary] = useState<TaxFilingSummary | null>(null);
  const [filingLoading, setFilingLoading] = useState(false);
  const [auditYear, setAuditYear] = useState(currentYear);

  // All sections start collapsed except refund
  const [collapsedSections, setCollapsedSections] = useState<Set<string>>(
    new Set(['whatIf', 'flatRate', 'filing', 'employer', 'audit', 'aiAdvisor']),
  );
  const toggleSection = (key: string) => {
    setCollapsedSections((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

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
    if (!selectedYear) return;
    setFilingLoading(true);
    taxFilingService
      .getSummary(selectedYear)
      .then(setFilingSummary)
      .catch(() => setFilingSummary(null))
      .finally(() => setFilingLoading(false));
  }, [selectedYear]);

  return (
    <div className="tax-tools-page">
      <div className="tax-tools-header">
        <SubpageBackLink to="/advanced" label={t('taxTools.page.back', 'Back')} />
        <h1>{t('taxTools.page.title', 'Tax Tools')}</h1>
        <p>{t('taxTools.page.subtitle', 'Tax position, AI guidance, payroll files and filings in one place')}</p>
      </div>

      <div className="tax-tools-content">
        {/* ── Section 1: Tax Position / Refund Estimate ── */}
        {showRefundEstimate && hasTransactions && (
          <section className={`asset-report-section ${collapsedSections.has('refund') ? 'collapsed' : ''}`}>
            <SectionHeading
              icon={Landmark}
              tone="emerald"
              title={t('taxTools.page.taxPosition', 'Tax position')}
              collapsed={collapsedSections.has('refund')}
              onToggle={() => toggleSection('refund')}
            />
            {!collapsedSections.has('refund') && (
              <RefundEstimate
                estimatedRefund={dashboardData?.estimatedRefund}
                withheldTax={dashboardData?.withheldTax}
                calculatedTax={dashboardData?.calculatedTax}
                hasLohnzettel={dashboardData?.hasLohnzettel}
              />
            )}
          </section>
        )}

        {/* ── Section 2: AI Tax Advisor ── */}
        <section className={`asset-report-section ${collapsedSections.has('aiAdvisor') ? 'collapsed' : ''}`}>
          <SectionHeading
            icon={Sparkles}
            tone="violet"
            title={t('taxTools.page.aiAdvisor', 'AI Tax Optimization')}
            collapsed={collapsedSections.has('aiAdvisor')}
            onToggle={() => toggleSection('aiAdvisor')}
          />
          {!collapsedSections.has('aiAdvisor') && (
            hasAIAccess ? (
              <AITaxAdvisor />
            ) : (
              <FeatureLockedBanner feature="ai_assistant" requiredPlan="pro" />
            )
          )}
        </section>

        {/* ── Section 3: What-If Simulator ── */}
        <section className={`asset-report-section ${collapsedSections.has('whatIf') ? 'collapsed' : ''}`}>
          <SectionHeading
            icon={Sliders}
            tone="amber"
            title={t('taxTools.whatIf.title', 'What-If Simulator')}
            collapsed={collapsedSections.has('whatIf')}
            onToggle={() => toggleSection('whatIf')}
          />
          {!collapsedSections.has('whatIf') && <WhatIfSimulator />}
        </section>

        {/* ── Section 4: Flat Rate Comparison ── */}
        {showFlatRate && (
          <section className={`asset-report-section ${collapsedSections.has('flatRate') ? 'collapsed' : ''}`}>
            <SectionHeading
              icon={Scale}
              tone="cyan"
              title={t('taxTools.flatRate.title', 'Flat Rate Comparison')}
              collapsed={collapsedSections.has('flatRate')}
              onToggle={() => toggleSection('flatRate')}
            />
            {!collapsedSections.has('flatRate') && <FlatRateComparison />}
          </section>
        )}

        {/* ── Section 5: Filing Summary ── */}
        <section className={`asset-report-section ${collapsedSections.has('filing') ? 'collapsed' : ''}`}>
          <SectionHeading
            icon={BarChart3}
            tone="violet"
            title={t('taxTools.page.filingSummary', 'Annual Tax Data Summary')}
            collapsed={collapsedSections.has('filing')}
            onToggle={() => toggleSection('filing')}
          />
          {!collapsedSections.has('filing') && (
            hasAdvancedReports ? (
            <>
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
                  {!filingLoading && filingSummary && ((filingSummary.record_count ?? 0) > 0 || (filingSummary.transactions && filingSummary.transactions.transaction_count > 0)) && (
                    <div className="filing-summary">
                      {(filingSummary.record_count ?? 0) > 0 && (
                        <>
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
                        </>
                      )}

                      {(filingSummary.record_count ?? 0) > 0 && (
                        <p className="text-muted tax-tools-record-count">
                          {filingSummary.record_count} {t('taxTools.page.records', 'confirmed records')}
                        </p>
                      )}

                      {filingSummary.transactions && filingSummary.transactions.transaction_count > 0 && (
                        <div className="filing-section filing-transactions-section">
                          <h4 className="tax-tools-subheading">
                            <FuturisticIcon icon={ClipboardList} tone="cyan" size="xs" />
                            <span>
                              {t('taxTools.page.transactionsSummary', 'Transactions')} ({filingSummary.transactions.transaction_count})
                            </span>
                          </h4>
                          <div className="filing-totals-grid" style={{ marginBottom: '0.75rem' }}>
                            <div className="filing-total-card">
                              <span className="filing-label">{t('taxTools.page.txnIncome', 'Income')}</span>
                              <span className="filing-value">
                                € {filingSummary.transactions.income_total.toLocaleString(getLocaleForLanguage(i18n.language), { minimumFractionDigits: 2 })}
                              </span>
                            </div>
                            <div className="filing-total-card">
                              <span className="filing-label">{t('taxTools.page.txnExpense', 'Expenses')}</span>
                              <span className="filing-value">
                                € {filingSummary.transactions.expense_total.toLocaleString(getLocaleForLanguage(i18n.language), { minimumFractionDigits: 2 })}
                              </span>
                            </div>
                            <div className="filing-total-card">
                              <span className="filing-label">{t('taxTools.page.txnDeductible', 'Deductible')}</span>
                              <span className="filing-value">
                                € {filingSummary.transactions.deductible_total.toLocaleString(getLocaleForLanguage(i18n.language), { minimumFractionDigits: 2 })}
                              </span>
                            </div>
                          </div>
                          <div className="filing-txn-categories">
                            {filingSummary.transactions.by_category.map((cat) => (
                              <div key={`${cat.type}-${cat.category}`} className="filing-item">
                                <span className="filing-item-type">
                                  {t(`transactions.types.${cat.type}`, cat.type)}
                                </span>
                                <span className="filing-item-category">
                                  {t(`transactions.categories.${cat.category}`, cat.category)}
                                </span>
                                <span className="filing-item-count">{cat.count}×</span>
                                <span className="filing-item-amount">
                                  € {cat.total.toLocaleString(getLocaleForLanguage(i18n.language), { minimumFractionDigits: 2 })}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                  {!filingLoading && filingSummary && (filingSummary.record_count ?? 0) === 0 && (!filingSummary.transactions || filingSummary.transactions.transaction_count === 0) && (
                    <p className="text-muted">{t('taxTools.page.noData', 'No confirmed data for this year')}</p>
                  )}
                </>
              )}
            </>
          ) : (
            <FeatureLockedBanner feature="advanced_reports" requiredPlan="plus" />
          )
          )}
        </section>

        {/* ── Section 6: Employer Documents Workbench ── */}
        {showEmployerWorkbench && (
          <section className={`asset-report-section ${collapsedSections.has('employer') ? 'collapsed' : ''}`}>
            <SectionHeading
              icon={Briefcase}
              tone="cyan"
              title={t('taxTools.employer.title', 'Employer Workbench')}
              collapsed={collapsedSections.has('employer')}
              onToggle={() => toggleSection('employer')}
            />
            {!collapsedSections.has('employer') && <EmployerDocumentsWorkbench />}
          </section>
        )}

        {/* ── Section 7: Audit Checklist ── */}
        <section className={`asset-report-section ${collapsedSections.has('audit') ? 'collapsed' : ''}`}>
          <SectionHeading
            icon={NotebookTabs}
            tone="rose"
            title={t('taxTools.page.auditChecklist', 'Audit Checklist')}
            collapsed={collapsedSections.has('audit')}
            onToggle={() => toggleSection('audit')}
          />
          {!collapsedSections.has('audit') && (
            <>
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
            </>
          )}
        </section>

        {/* ── No data fallback ── */}
        {!showRefundEstimate && !hasTransactions && (
          <p className="text-muted">{t('taxTools.page.noData', 'No data available yet. Upload documents to see your tax estimate.')}</p>
        )}
      </div>
    </div>
  );
};

export default TaxToolsPage;
