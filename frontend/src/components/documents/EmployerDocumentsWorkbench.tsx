import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { aiToast } from '../../stores/aiToastStore';
import { useAuthStore } from '../../stores/authStore';
import { useRefreshStore } from '../../stores/refreshStore';
import {
  employerService,
  type EmployerAnnualArchive,
  type EmployerMonth,
  type EmployerOverview,
} from '../../services/employerService';
import {
  formatEmployerDate,
  formatEmployerMoney,
  formatEmployerMonthLabel,
  getEmployerAnnualArchiveStatusLabel,
  getEmployerMonthStatusLabel,
} from '../../utils/employerSupport';
import { normalizeLanguage } from '../../utils/locale';
import './EmployerDocumentsWorkbench.css';

const currentYear = new Date().getFullYear();

const getErrorMessage = (error: any, fallback: string) =>
  error?.response?.data?.detail || error?.message || fallback;

const buildMonthSummaryPayload = (month: EmployerMonth) => ({
  employee_count: month.employee_count ?? undefined,
  gross_wages: month.gross_wages ?? undefined,
  net_paid: month.net_paid ?? undefined,
  employer_social_cost: month.employer_social_cost ?? undefined,
  lohnsteuer: month.lohnsteuer ?? undefined,
  db_amount: month.db_amount ?? undefined,
  dz_amount: month.dz_amount ?? undefined,
  kommunalsteuer: month.kommunalsteuer ?? undefined,
  special_payments: month.special_payments ?? undefined,
  notes: month.notes ?? undefined,
});

const EmployerDocumentsWorkbench = () => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const language = normalizeLanguage(i18n.resolvedLanguage || i18n.language);
  const text = {
    zh: {
      loadError: '加载工资控制台失败。',
      eyebrow: '工资文件工作台',
      title: '集中处理工资月份和历史年包',
      subtitle: '在这里确认工资月份、补缺口、归档历史工资文件，不需要再单独开一个模块。',
      refresh: '刷新',
      payrollMonths: '工资月份',
      missingConfirmations: '待确认',
      historicalPacks: '历史年包',
      nextDeadline: '下一个截止日',
      pendingMonths: '待确认的工资月份',
      pendingMonthMeta: '{{count}} 份关联文件',
      viewDetails: '查看详情',
      confirming: '确认中...',
      confirmPayroll: '确认为工资月份',
      confirmNoPayroll: '确认为无工资',
      noPendingMonths: '当前没有待确认的工资月份。',
      pendingArchives: '待归档的历史工资年包',
      unknownEmployer: '未识别雇主',
      documentCount: '{{count}} 份文件',
      saving: '保存中...',
      archiveYear: '归档工资年包',
      noPendingArchives: '当前没有待归档的历史工资年包。',
    },
    en: {
      loadError: 'Failed to load employer workbench.',
      eyebrow: 'Employer inbox',
      title: 'Handle payroll months and historical packs in one place',
      subtitle: 'Review payroll-like files, clear missing confirmations, and archive older Lohnzettel without opening a separate module.',
      refresh: 'Refresh',
      payrollMonths: 'Payroll months',
      missingConfirmations: 'Waiting for confirmation',
      historicalPacks: 'Historical year packs',
      nextDeadline: 'Next employer deadline',
      pendingMonths: 'Payroll months waiting for confirmation',
      pendingMonthMeta: '{{count}} linked file(s)',
      viewDetails: 'View details',
      confirming: 'Confirming...',
      confirmPayroll: 'Mark as payroll month',
      confirmNoPayroll: 'Mark as no payroll',
      noPendingMonths: 'No payroll months are waiting for confirmation right now.',
      pendingArchives: 'Historical payroll packs waiting for archive',
      unknownEmployer: 'Employer not captured',
      documentCount: '{{count}} document(s)',
      saving: 'Saving...',
      archiveYear: 'Archive payroll year',
      noPendingArchives: 'No historical payroll packs are waiting for archive review.',
    },
    de: {
      loadError: 'Arbeitgeber-Arbeitsbereich konnte nicht geladen werden.',
      eyebrow: 'Arbeitgeber-Inbox',
      title: 'Lohnmonate und historische Pakete an einer Stelle bearbeiten',
      subtitle: 'Lohnbezogene Dateien pruefen, offene Bestaetigungen klaeren und aeltere Lohnzettel archivieren.',
      refresh: 'Aktualisieren',
      payrollMonths: 'Lohnmonate',
      missingConfirmations: 'Bestaetigung offen',
      historicalPacks: 'Historische Jahrespakete',
      nextDeadline: 'Naechste Frist',
      pendingMonths: 'Lohnmonate mit offener Bestaetigung',
      pendingMonthMeta: '{{count}} verknuepfte Datei(en)',
      viewDetails: 'Details anzeigen',
      confirming: 'Wird bestaetigt...',
      confirmPayroll: 'Als Lohnmonat bestaetigen',
      confirmNoPayroll: 'Als ohne Lohn bestaetigen',
      noPendingMonths: 'Aktuell warten keine Lohnmonate auf eine Bestaetigung.',
      pendingArchives: 'Historische Lohnpakete mit offener Archivierung',
      unknownEmployer: 'Arbeitgeber nicht erkannt',
      documentCount: '{{count}} Dokument(e)',
      saving: 'Wird gespeichert...',
      archiveYear: 'Lohnjahr archivieren',
      noPendingArchives: 'Aktuell warten keine historischen Lohnpakete auf die Archivierung.',
    },
  }[language];
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [overview, setOverview] = useState<EmployerOverview | null>(null);
  const [months, setMonths] = useState<EmployerMonth[]>([]);
  const [annualArchives, setAnnualArchives] = useState<EmployerAnnualArchive[]>([]);

  const employerSupportEnabled = Boolean(
    user
    && (user.employer_mode || 'none') !== 'none'
    && ['self_employed', 'mixed'].includes(user.user_type)
  );

  const pendingMonths = months.filter((month) => month.status === 'missing_confirmation');
  const pendingArchives = annualArchives.filter((archive) => archive.status === 'pending_confirmation');

  const loadWorkbench = async () => {
    if (!employerSupportEnabled) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const [nextOverview, nextMonths, nextArchives] = await Promise.all([
        employerService.getOverview(currentYear),
        employerService.getMonths(currentYear),
        employerService.getAnnualArchives(),
      ]);
      setOverview(nextOverview);
      setMonths(nextMonths);
      setAnnualArchives(nextArchives);
    } catch (loadError: any) {
      setError(getErrorMessage(loadError, text.loadError));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadWorkbench();
  }, [employerSupportEnabled]);

  const updateMonth = (updatedMonth: EmployerMonth) => {
    setMonths((current) => {
      const exists = current.some((month) => month.id === updatedMonth.id);
      if (exists) {
        return current.map((month) => (month.id === updatedMonth.id ? updatedMonth : month));
      }

      return [...current].sort((left, right) => left.year_month.localeCompare(right.year_month));
    });
    useRefreshStore.getState().refreshDashboard();
  };

  const updateArchive = (updatedArchive: EmployerAnnualArchive) => {
    setAnnualArchives((current) => {
      const exists = current.some((archive) => archive.id === updatedArchive.id);
      if (exists) {
        return current.map((archive) => (archive.id === updatedArchive.id ? updatedArchive : archive));
      }

      return [...current].sort((left, right) => right.tax_year - left.tax_year);
    });
    useRefreshStore.getState().refreshDashboard();
  };

  const openLinkedDocument = (documentId?: number) => {
    if (!documentId) {
      return;
    }

    navigate(`/documents/${documentId}`);
  };

  const handleConfirmPayroll = async (month: EmployerMonth) => {
    setBusyAction(`month-payroll-${month.id}`);

    try {
      const updatedMonth = await employerService.confirmPayroll({
        year_month: month.year_month,
        document_id: month.documents[0]?.document_id,
        payroll_signal: month.payroll_signal || 'payslip',
        source_type: 'advanced_management',
        confidence: month.confidence ?? undefined,
        ...buildMonthSummaryPayload(month),
      });
      updateMonth(updatedMonth);
      aiToast(t('documents.employer.payrollConfirmed', 'This month is now marked as a payroll month.'), 'success');
      await loadWorkbench();
    } catch (actionError: any) {
      aiToast(getErrorMessage(actionError, t('common.error', 'Something went wrong.')), 'error');
    } finally {
      setBusyAction(null);
    }
  };

  const handleConfirmNoPayroll = async (month: EmployerMonth) => {
    setBusyAction(`month-no-payroll-${month.id}`);

    try {
      const updatedMonth = await employerService.confirmNoPayroll(month.year_month, month.notes || undefined);
      updateMonth(updatedMonth);
      aiToast(t('documents.employer.noPayrollConfirmed', 'This month is marked as having no payroll.'), 'success');
      await loadWorkbench();
    } catch (actionError: any) {
      aiToast(getErrorMessage(actionError, t('common.error', 'Something went wrong.')), 'error');
    } finally {
      setBusyAction(null);
    }
  };

  const handleArchiveYear = async (archive: EmployerAnnualArchive) => {
    setBusyAction(`archive-${archive.id}`);

    try {
      const updatedArchive = await employerService.confirmAnnualArchive({
        tax_year: archive.tax_year,
        document_id: archive.documents[0]?.document_id,
        archive_signal: archive.archive_signal || 'lohnzettel',
        source_type: 'advanced_management',
        confidence: archive.confidence ?? undefined,
        employer_name: archive.employer_name || undefined,
        gross_income: archive.gross_income ?? undefined,
        withheld_tax: archive.withheld_tax ?? undefined,
        notes: archive.notes || undefined,
      });
      updateArchive(updatedArchive);
      aiToast(t('documents.employer.archiveSaved', 'Historical payroll pack saved.'), 'success');
      await loadWorkbench();
    } catch (actionError: any) {
      aiToast(getErrorMessage(actionError, t('common.error', 'Something went wrong.')), 'error');
    } finally {
      setBusyAction(null);
    }
  };

  if (!employerSupportEnabled) {
    return null;
  }

  return (
    <section className="employer-workbench-card">
      <div className="employer-workbench-header">
        <div>
          <span className="employer-workbench-eyebrow">
            {t('documents.employer.workbenchEyebrow', text.eyebrow)}
          </span>
          <h3>{t('documents.employer.workbenchTitle', text.title)}</h3>
          <p>{t('documents.employer.workbenchSubtitle', text.subtitle)}</p>
        </div>
        <button type="button" className="employer-workbench-refresh" onClick={loadWorkbench} disabled={loading}>
          {loading ? t('common.loading', 'Loading...') : t('common.refresh', text.refresh)}
        </button>
      </div>

      {error && <div className="employer-workbench-error">{error}</div>}

      <div className="employer-workbench-metrics">
        <div className="employer-workbench-metric">
          <span>{t('dashboard.employerPayrollMonths', text.payrollMonths)}</span>
          <strong>{overview?.payroll_months ?? 0}</strong>
        </div>
        <div className="employer-workbench-metric attention">
          <span>{t('dashboard.employerMissingConfirmations', text.missingConfirmations)}</span>
          <strong>{overview?.missing_confirmation_months ?? 0}</strong>
        </div>
        <div className="employer-workbench-metric">
          <span>{t('dashboard.employerHistoricalPacks', text.historicalPacks)}</span>
          <strong>{annualArchives.length}</strong>
        </div>
        <div className="employer-workbench-metric">
          <span>{t('dashboard.employerNextDeadline', text.nextDeadline)}</span>
          <strong>{formatEmployerDate(overview?.next_deadline)}</strong>
        </div>
      </div>

      <div className="employer-workbench-columns">
        <div className="employer-workbench-section">
          <div className="employer-workbench-section-header">
            <h4>{t('documents.employer.pendingMonths', text.pendingMonths)}</h4>
            <span className="employer-workbench-count">{pendingMonths.length}</span>
          </div>

          {pendingMonths.length > 0 ? (
            <div className="employer-workbench-list">
              {pendingMonths.map((month) => (
                <article key={month.id} className="employer-workbench-item">
                  <div className="employer-workbench-item-main">
                    <div className="employer-workbench-item-top">
                      <strong>{formatEmployerMonthLabel(month.year_month)}</strong>
                      <span className={`employer-workbench-pill status-${month.status}`}>
                        {getEmployerMonthStatusLabel(month.status, language)}
                      </span>
                    </div>
                    <p>
                      {t('documents.employer.pendingMonthMeta', text.pendingMonthMeta, {
                        count: month.documents.length,
                      })}
                      {month.gross_wages != null && (
                        <> · EUR {formatEmployerMoney(month.gross_wages)}</>
                      )}
                    </p>
                  </div>
                  <div className="employer-workbench-actions">
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => openLinkedDocument(month.documents[0]?.document_id)}
                      disabled={!month.documents[0]?.document_id}
                    >
                      {t('common.viewDetails', text.viewDetails)}
                    </button>
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={() => handleConfirmPayroll(month)}
                      disabled={busyAction !== null}
                    >
                      {busyAction === `month-payroll-${month.id}`
                        ? t('documents.employer.confirming', text.confirming)
                        : t('documents.employer.confirmPayroll', text.confirmPayroll)}
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => handleConfirmNoPayroll(month)}
                      disabled={busyAction !== null}
                    >
                      {busyAction === `month-no-payroll-${month.id}`
                        ? t('documents.employer.confirming', text.confirming)
                        : t('documents.employer.confirmNoPayroll', text.confirmNoPayroll)}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="employer-workbench-empty">
              {t('documents.employer.noPendingMonths', text.noPendingMonths)}
            </div>
          )}
        </div>

        <div className="employer-workbench-section">
          <div className="employer-workbench-section-header">
            <h4>{t('documents.employer.pendingArchives', text.pendingArchives)}</h4>
            <span className="employer-workbench-count">{pendingArchives.length}</span>
          </div>

          {pendingArchives.length > 0 ? (
            <div className="employer-workbench-list">
              {pendingArchives.map((archive) => (
                <article key={archive.id} className="employer-workbench-item">
                  <div className="employer-workbench-item-main">
                    <div className="employer-workbench-item-top">
                      <strong>{archive.tax_year}</strong>
                      <span className={`employer-workbench-pill status-${archive.status}`}>
                        {getEmployerAnnualArchiveStatusLabel(archive.status, language)}
                      </span>
                    </div>
                    <p>
                      {archive.employer_name || t('dashboard.employerUnknownEmployer', text.unknownEmployer)}
                      {' · '}
                      {t('dashboard.employerDocumentCount', text.documentCount, {
                        count: archive.documents.length,
                      })}
                      {archive.gross_income != null && (
                        <> · EUR {formatEmployerMoney(archive.gross_income)}</>
                      )}
                    </p>
                  </div>
                  <div className="employer-workbench-actions">
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => openLinkedDocument(archive.documents[0]?.document_id)}
                      disabled={!archive.documents[0]?.document_id}
                    >
                      {t('common.viewDetails', text.viewDetails)}
                    </button>
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={() => handleArchiveYear(archive)}
                      disabled={busyAction !== null}
                    >
                      {busyAction === `archive-${archive.id}`
                        ? t('documents.employer.saving', text.saving)
                        : t('documents.employer.archiveYear', text.archiveYear)}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="employer-workbench-empty">
              {t('documents.employer.noPendingArchives', text.noPendingArchives)}
            </div>
          )}
        </div>
      </div>
    </section>
  );
};

export default EmployerDocumentsWorkbench;
