import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import type { EmployerAnnualArchive, EmployerOverview } from '../../services/employerService';
import { formatEmployerDate, formatEmployerMoney } from '../../utils/employerSupport';
import { normalizeLanguage } from '../../utils/locale';
import './EmployerStatusCard.css';

interface EmployerStatusCardProps {
  selectedYear: number;
  overview: EmployerOverview | null;
  annualArchives: EmployerAnnualArchive[];
}

const EmployerStatusCard = ({
  selectedYear,
  overview,
  annualArchives,
}: EmployerStatusCardProps) => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const language = normalizeLanguage(i18n.resolvedLanguage || i18n.language);
  const text = {
    zh: {
      title: '雇主支持',
      subtitle: '集中查看工资月份、补确认缺口，并归档历史工资年包。',
      action: '查看详情',
      attentionTitle: '需要处理',
      attentionBody: '您有待确认或待归档的雇主相关项目。',
      selectedYear: '所选年份',
      payrollMonths: '工资月份',
      missingConfirmations: '待确认',
      noPayrollMonths: '已确认无工资月份',
      nextDeadline: '下一个截止日',
      historicalPacks: '历史年包',
      historyTitle: '历史工资年包',
      pendingArchives: '{{count}} 个待归档',
      unknownEmployer: '未识别雇主',
      documentCount: '{{count}} 份文件',
      archived: '已归档',
      pending: '待处理',
      noHistory: '归档历史 Lohnzettel 或年度工资文件后，这里会显示历史年包。',
    },
    en: {
      title: 'Employer Support',
      subtitle: 'Track payroll months, clear confirmation gaps, and archive historical payroll packs.',
      action: 'View details',
      attentionTitle: 'Action needed',
      attentionBody: 'You have employer-related items waiting for confirmation or archive review.',
      selectedYear: 'Selected year',
      payrollMonths: 'Payroll months',
      missingConfirmations: 'Waiting for confirmation',
      noPayrollMonths: 'No-payroll months confirmed',
      nextDeadline: 'Next employer deadline',
      historicalPacks: 'Historical year packs',
      historyTitle: 'Historical payroll packs',
      pendingArchives: '{{count}} pending',
      unknownEmployer: 'Employer not captured',
      documentCount: '{{count}} document(s)',
      archived: 'Archived',
      pending: 'Pending',
      noHistory: 'Historical payroll packs will appear here once you archive older Lohnzettel or annual payroll files.',
    },
    de: {
      title: 'Arbeitgeber-Hinweise',
      subtitle: 'Lohnmonate, offene Bestaetigungen und historische Jahrespakete an einer Stelle.',
      action: 'Details anzeigen',
      attentionTitle: 'Handlungsbedarf',
      attentionBody: 'Es gibt arbeitgeberbezogene Elemente mit offener Bestaetigung oder Archivpruefung.',
      selectedYear: 'Ausgewaehltes Jahr',
      payrollMonths: 'Lohnmonate',
      missingConfirmations: 'Bestaetigung offen',
      noPayrollMonths: 'Monate ohne Lohn bestaetigt',
      nextDeadline: 'Naechste Frist',
      historicalPacks: 'Historische Jahrespakete',
      historyTitle: 'Historische Lohnpakete',
      pendingArchives: '{{count}} offen',
      unknownEmployer: 'Arbeitgeber nicht erkannt',
      documentCount: '{{count}} Dokument(e)',
      archived: 'Archiviert',
      pending: 'Offen',
      noHistory: 'Historische Lohnpakete erscheinen hier, sobald aeltere Lohnzettel oder Jahresdateien archiviert sind.',
    },
  }[language];

  const pendingAnnualArchives = useMemo(
    () => annualArchives.filter((archive) => archive.status === 'pending_confirmation'),
    [annualArchives]
  );
  const recentAnnualArchives = useMemo(
    () => annualArchives.slice(0, 4),
    [annualArchives]
  );

  const summaryTone =
    (overview?.missing_confirmation_months || 0) > 0 || pendingAnnualArchives.length > 0
      ? 'attention'
      : (overview?.payroll_months || 0) > 0 || annualArchives.length > 0
        ? 'healthy'
        : 'idle';

  return (
    <section className={`dashboard-summary-card employer-status-card tone-${summaryTone}`}>
      <div className="dashboard-summary-header employer-status-header">
        <div>
          <h3 className="dashboard-summary-title">
            {t('dashboard.employerSupportTitle', text.title)}
          </h3>
          <p className="employer-status-subtitle">
            {t('dashboard.employerSupportSubtitle', text.subtitle)}
          </p>
        </div>
        <button
          type="button"
          className="employer-status-link"
          onClick={() => navigate('/advanced')}
        >
          {t('common.viewDetails', text.action)} {'->'}
        </button>
      </div>

      {((overview?.missing_confirmation_months || 0) > 0 || pendingAnnualArchives.length > 0) && (
        <div className="employer-status-alert">
          <strong>
            {t('dashboard.employerAttentionTitle', text.attentionTitle)}
          </strong>
          <p>
            {t('dashboard.employerAttentionBody', text.attentionBody)}
          </p>
        </div>
      )}

      <div className="dashboard-summary-grid employer-status-grid">
        <div>
          <div className="dashboard-summary-label">
            {t('dashboard.employerSelectedYear', text.selectedYear)}
          </div>
          <div className="dashboard-summary-value">{selectedYear}</div>
        </div>
        <div>
          <div className="dashboard-summary-label">
            {t('dashboard.employerPayrollMonths', text.payrollMonths)}
          </div>
          <div className="dashboard-summary-value">{overview?.payroll_months ?? 0}</div>
        </div>
        <div>
          <div className="dashboard-summary-label">
            {t('dashboard.employerMissingConfirmations', text.missingConfirmations)}
          </div>
          <div className="dashboard-summary-value text-warning">
            {overview?.missing_confirmation_months ?? 0}
          </div>
        </div>
        <div>
          <div className="dashboard-summary-label">
            {t('dashboard.employerNoPayrollMonths', text.noPayrollMonths)}
          </div>
          <div className="dashboard-summary-value">{overview?.no_payroll_months ?? 0}</div>
        </div>
        <div>
          <div className="dashboard-summary-label">
            {t('dashboard.employerNextDeadline', text.nextDeadline)}
          </div>
          <div className="dashboard-summary-value employer-status-deadline">
            {formatEmployerDate(overview?.next_deadline)}
          </div>
        </div>
        <div>
          <div className="dashboard-summary-label">
            {t('dashboard.employerHistoricalPacks', text.historicalPacks)}
          </div>
          <div className="dashboard-summary-value">{annualArchives.length}</div>
        </div>
      </div>

      <div className="employer-status-history">
        <div className="employer-status-history-header">
          <h4>{t('dashboard.employerHistoryTitle', text.historyTitle)}</h4>
          {pendingAnnualArchives.length > 0 && (
            <span className="employer-status-pill pending">
              {t('dashboard.employerPendingArchives', text.pendingArchives, {
                count: pendingAnnualArchives.length,
              })}
            </span>
          )}
        </div>

        {recentAnnualArchives.length > 0 ? (
          <div className="employer-status-history-list">
            {recentAnnualArchives.map((archive) => (
              <div key={archive.id} className="employer-status-history-item">
                <div className="employer-status-history-main">
                  <div className="employer-status-year">{archive.tax_year}</div>
                  <div className="employer-status-history-meta">
                    <div className="employer-status-employer">
                      {archive.employer_name || t('dashboard.employerUnknownEmployer', text.unknownEmployer)}
                    </div>
                    <div className="employer-status-doc-count">
                      {t('dashboard.employerDocumentCount', text.documentCount, {
                        count: archive.documents.length,
                      })}
                    </div>
                  </div>
                </div>
                <div className="employer-status-history-side">
                  <span
                    className={`employer-status-pill ${
                      archive.status === 'archived' ? 'archived' : 'pending'
                    }`}
                  >
                    {archive.status === 'archived'
                      ? t('dashboard.employerArchived', text.archived)
                      : t('dashboard.employerPending', text.pending)}
                  </span>
                  {formatEmployerMoney(archive.gross_income, null) && (
                    <div className="employer-status-amount">
                      EUR {formatEmployerMoney(archive.gross_income, null)}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="employer-status-empty">
            {t('dashboard.employerNoHistory', text.noHistory)}
          </div>
        )}
      </div>
    </section>
  );
};

export default EmployerStatusCard;
