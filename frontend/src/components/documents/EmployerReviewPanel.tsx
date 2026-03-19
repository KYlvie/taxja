import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { aiToast } from '../../stores/aiToastStore';
import { useAuthStore } from '../../stores/authStore';
import { useRefreshStore } from '../../stores/refreshStore';
import type { Document } from '../../types/document';
import {
  employerService,
  type EmployerAnnualArchive,
  type EmployerDocumentReviewContext,
  type EmployerMonth,
  type EmployerMonthSummaryUpdate,
} from '../../services/employerService';
import {
  formatEmployerDateTime,
  formatEmployerMoney,
  formatEmployerMonthLabel,
  getEmployerAnnualArchiveStatusLabel,
  getEmployerMonthStatusLabel,
} from '../../utils/employerSupport';
import './EmployerReviewPanel.css';

interface EmployerReviewPanelProps {
  document: Document;
}

interface EmployerMonthFormState {
  employee_count: string;
  gross_wages: string;
  net_paid: string;
  employer_social_cost: string;
  lohnsteuer: string;
  db_amount: string;
  dz_amount: string;
  kommunalsteuer: string;
  special_payments: string;
  notes: string;
}

interface EmployerAnnualFormState {
  employer_name: string;
  gross_income: string;
  withheld_tax: string;
  notes: string;
}

const MONTHLY_DOC_TYPES = new Set(['payslip']);
const ANNUAL_DOC_TYPES = new Set(['lohnzettel']);

const EMPTY_MONTH_FORM: EmployerMonthFormState = {
  employee_count: '',
  gross_wages: '',
  net_paid: '',
  employer_social_cost: '',
  lohnsteuer: '',
  db_amount: '',
  dz_amount: '',
  kommunalsteuer: '',
  special_payments: '',
  notes: '',
};

const EMPTY_ANNUAL_FORM: EmployerAnnualFormState = {
  employer_name: '',
  gross_income: '',
  withheld_tax: '',
  notes: '',
};

const parseOcrObject = (ocrResult: unknown): Record<string, any> => {
  if (!ocrResult) {
    return {};
  }

  if (typeof ocrResult === 'string') {
    try {
      return JSON.parse(ocrResult);
    } catch {
      return {};
    }
  }

  if (typeof ocrResult === 'object') {
    return ocrResult as Record<string, any>;
  }

  return {};
};

const toInputValue = (value: unknown): string => {
  if (value === null || value === undefined) {
    return '';
  }

  return String(value);
};

const parseIntegerInput = (value: string): number | undefined => {
  const trimmed = value.trim();
  if (!trimmed) {
    return undefined;
  }

  const parsed = Number.parseInt(trimmed, 10);
  return Number.isFinite(parsed) ? parsed : undefined;
};

const parseDecimalInput = (value: string): number | undefined => {
  const trimmed = value.trim();
  if (!trimmed) {
    return undefined;
  }

  const parsed = Number(trimmed.replace(',', '.'));
  return Number.isFinite(parsed) ? parsed : undefined;
};

const getErrorMessage = (error: any, fallback: string) =>
  error?.response?.data?.detail || error?.message || fallback;

const buildMonthForm = (
  month: EmployerMonth | null | undefined,
  document: Document
): EmployerMonthFormState => {
  const ocr = parseOcrObject(document.ocr_result);

  return {
    employee_count: toInputValue(month?.employee_count ?? ocr.employee_count),
    gross_wages: toInputValue(month?.gross_wages ?? ocr.gross_income),
    net_paid: toInputValue(month?.net_paid ?? ocr.net_income),
    employer_social_cost: toInputValue(month?.employer_social_cost ?? ocr.employer_social_cost),
    lohnsteuer: toInputValue(month?.lohnsteuer ?? ocr.withheld_tax),
    db_amount: toInputValue(month?.db_amount ?? ocr.db_amount),
    dz_amount: toInputValue(month?.dz_amount ?? ocr.dz_amount),
    kommunalsteuer: toInputValue(month?.kommunalsteuer ?? ocr.kommunalsteuer),
    special_payments: toInputValue(month?.special_payments ?? ocr.special_payments),
    notes: month?.notes || '',
  };
};

const buildAnnualForm = (
  archive: EmployerAnnualArchive | null | undefined,
  document: Document
): EmployerAnnualFormState => {
  const ocr = parseOcrObject(document.ocr_result);

  return {
    employer_name: String(archive?.employer_name ?? ocr.employer_name ?? ocr.employer ?? ''),
    gross_income: toInputValue(archive?.gross_income ?? ocr.gross_income ?? ocr.kz_210),
    withheld_tax: toInputValue(archive?.withheld_tax ?? ocr.withheld_tax ?? ocr.kz_260),
    notes: archive?.notes || '',
  };
};

const buildMonthPayload = (form: EmployerMonthFormState): EmployerMonthSummaryUpdate => {
  const payload: EmployerMonthSummaryUpdate = {};

  const employeeCount = parseIntegerInput(form.employee_count);
  if (employeeCount !== undefined) {
    payload.employee_count = employeeCount;
  }

  const decimalFields: Array<
    | 'gross_wages'
    | 'net_paid'
    | 'employer_social_cost'
    | 'lohnsteuer'
    | 'db_amount'
    | 'dz_amount'
    | 'kommunalsteuer'
    | 'special_payments'
  > = [
    'gross_wages',
    'net_paid',
    'employer_social_cost',
    'lohnsteuer',
    'db_amount',
    'dz_amount',
    'kommunalsteuer',
    'special_payments',
  ];
  const sourceMap: Record<string, string> = {
    gross_wages: form.gross_wages,
    net_paid: form.net_paid,
    employer_social_cost: form.employer_social_cost,
    lohnsteuer: form.lohnsteuer,
    db_amount: form.db_amount,
    dz_amount: form.dz_amount,
    kommunalsteuer: form.kommunalsteuer,
    special_payments: form.special_payments,
  };

  decimalFields.forEach((field) => {
    const parsed = parseDecimalInput(sourceMap[field]);
    if (parsed !== undefined) {
      payload[field] = parsed;
    }
  });

  if (form.notes.trim()) {
    payload.notes = form.notes.trim();
  }

  return payload;
};

const EmployerReviewPanel = ({ document }: EmployerReviewPanelProps) => {
  const { t } = useTranslation();
  const user = useAuthStore((state) => state.user);
  const [context, setContext] = useState<EmployerDocumentReviewContext | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [monthForm, setMonthForm] = useState<EmployerMonthFormState>(EMPTY_MONTH_FORM);
  const [annualForm, setAnnualForm] = useState<EmployerAnnualFormState>(EMPTY_ANNUAL_FORM);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [result, setResult] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const employerSupportEnabled = useMemo(() => {
    if (!user) {
      return false;
    }

    return (
      (user.employer_mode || 'none') !== 'none'
      && ['self_employed', 'mixed'].includes(user.user_type)
      && (MONTHLY_DOC_TYPES.has(document.document_type) || ANNUAL_DOC_TYPES.has(document.document_type))
    );
  }, [document.document_type, user]);

  useEffect(() => {
    let active = true;

    if (!employerSupportEnabled) {
      setContext(null);
      setLoadError(null);
      setMonthForm(EMPTY_MONTH_FORM);
      setAnnualForm(EMPTY_ANNUAL_FORM);
      return () => {
        active = false;
      };
    }

    setLoading(true);
    setLoadError(null);
    setResult(null);

    employerService.getDocumentReviewContext(document.id)
      .then((nextContext) => {
        if (!active) {
          return;
        }

        setContext(nextContext);
        setMonthForm(buildMonthForm(nextContext.month, document));
        setAnnualForm(buildAnnualForm(nextContext.annual_archive, document));
      })
      .catch((error) => {
        if (!active) {
          return;
        }

        setLoadError(getErrorMessage(error, 'Failed to load employer review context.'));
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [document, employerSupportEnabled]);

  const applyMonthUpdate = (month: EmployerMonth, message: string) => {
    setContext((current) => (
      current
        ? {
            ...current,
            supported: true,
            reason: null,
            month,
            candidate_year_month: current.candidate_year_month || month.year_month,
          }
        : current
    ));
    setMonthForm(buildMonthForm(month, document));
    setResult({ type: 'success', message });
    aiToast(message, 'success');
    useRefreshStore.getState().refreshDashboard();
  };

  const applyArchiveUpdate = (archive: EmployerAnnualArchive, message: string) => {
    setContext((current) => (
      current
        ? {
            ...current,
            supported: true,
            reason: null,
            annual_archive: archive,
            candidate_tax_year: current.candidate_tax_year || archive.tax_year,
          }
        : current
    ));
    setAnnualForm(buildAnnualForm(archive, document));
    setResult({ type: 'success', message });
    aiToast(message, 'success');
    useRefreshStore.getState().refreshDashboard();
  };

  const handleSaveMonthSummary = async () => {
    if (!context?.candidate_year_month) {
      return;
    }

    setBusyAction('save-month');
    setResult(null);

    try {
      const month = await employerService.updateMonth(
        context.candidate_year_month,
        buildMonthPayload(monthForm)
      );
      applyMonthUpdate(month, t('documents.employer.summarySaved', 'Employer month summary updated.'));
    } catch (error: any) {
      setResult({
        type: 'error',
        message: getErrorMessage(error, t('common.error', 'Something went wrong.')),
      });
    } finally {
      setBusyAction(null);
    }
  };

  const handleConfirmPayroll = async () => {
    if (!context?.candidate_year_month) {
      return;
    }

    setBusyAction('confirm-payroll');
    setResult(null);

    try {
      const month = await employerService.confirmPayroll({
        year_month: context.candidate_year_month,
        document_id: document.id,
        payroll_signal: context.month?.payroll_signal || context.document_type,
        source_type: 'document_review',
        ...buildMonthPayload(monthForm),
      });
      applyMonthUpdate(month, t('documents.employer.payrollConfirmed', 'This month is now marked as a payroll month.'));
    } catch (error: any) {
      setResult({
        type: 'error',
        message: getErrorMessage(error, t('common.error', 'Something went wrong.')),
      });
    } finally {
      setBusyAction(null);
    }
  };

  const handleConfirmNoPayroll = async () => {
    if (!context?.candidate_year_month) {
      return;
    }

    setBusyAction('confirm-no-payroll');
    setResult(null);

    try {
      const month = await employerService.confirmNoPayroll(
        context.candidate_year_month,
        monthForm.notes.trim() || undefined
      );
      applyMonthUpdate(month, t('documents.employer.noPayrollConfirmed', 'This month is marked as having no payroll.'));
    } catch (error: any) {
      setResult({
        type: 'error',
        message: getErrorMessage(error, t('common.error', 'Something went wrong.')),
      });
    } finally {
      setBusyAction(null);
    }
  };

  const handleArchiveYear = async () => {
    if (!context?.candidate_tax_year) {
      return;
    }

    const alreadyArchived = context.annual_archive?.status === 'archived';
    setBusyAction('archive-year');
    setResult(null);

    try {
      const archive = await employerService.confirmAnnualArchive({
        tax_year: context.candidate_tax_year,
        document_id: document.id,
        archive_signal: context.annual_archive?.archive_signal || context.document_type,
        source_type: 'document_review',
        employer_name: annualForm.employer_name.trim() || undefined,
        gross_income: parseDecimalInput(annualForm.gross_income),
        withheld_tax: parseDecimalInput(annualForm.withheld_tax),
        notes: annualForm.notes.trim() || undefined,
      });
      applyArchiveUpdate(
        archive,
        alreadyArchived
          ? t('documents.employer.archiveUpdated', 'Historical payroll archive updated.')
          : t('documents.employer.archiveSaved', 'Historical payroll pack saved.')
      );
    } catch (error: any) {
      setResult({
        type: 'error',
        message: getErrorMessage(error, t('common.error', 'Something went wrong.')),
      });
    } finally {
      setBusyAction(null);
    }
  };

  if (!employerSupportEnabled) {
    return null;
  }

  if (loading) {
    return (
      <section className="employer-review-card">
        <div className="employer-review-header">
          <div>
            <h3>{t('documents.employer.title', 'Employer review')}</h3>
            <p>{t('documents.employer.loading', 'Loading payroll review context for this document...')}</p>
          </div>
        </div>
      </section>
    );
  }

  if (loadError) {
    return (
      <section className="employer-review-card">
        <div className="employer-review-header">
          <div>
            <h3>{t('documents.employer.title', 'Employer review')}</h3>
            <p>{loadError}</p>
          </div>
        </div>
      </section>
    );
  }

  if (!context) {
    return null;
  }

  const showReasonCard = ['current_year_not_archivable', 'tax_year_not_found'].includes(context.reason || '');
  if (!context.supported && !showReasonCard) {
    return null;
  }

  const isMonthlyReview = MONTHLY_DOC_TYPES.has(context.document_type);
  const isAnnualReview = ANNUAL_DOC_TYPES.has(context.document_type);
  const monthGrossDisplay = formatEmployerMoney(context.month?.gross_wages);
  const annualGrossDisplay = formatEmployerMoney(context.annual_archive?.gross_income);

  return (
    <section className="employer-review-card">
      <div className="employer-review-header">
        <div>
          <h3>{t('documents.employer.title', 'Employer review')}</h3>
          <p>
            {isMonthlyReview
              ? t(
                  'documents.employer.monthSubtitle',
                  'Confirm whether this file belongs to a payroll month and keep the monthly summary accurate.'
                )
              : t(
                  'documents.employer.annualSubtitle',
                  'Archive this historical payroll pack without rebuilding a full payroll year.'
                )}
          </p>
        </div>
        {isMonthlyReview && (
          <span className={`employer-review-pill status-${context.month?.status || 'unknown'}`}>
            {getEmployerMonthStatusLabel(context.month?.status)}
          </span>
        )}
        {isAnnualReview && context.supported && (
          <span className={`employer-review-pill status-${context.annual_archive?.status || 'pending_confirmation'}`}>
            {getEmployerAnnualArchiveStatusLabel(context.annual_archive?.status)}
          </span>
        )}
      </div>

      {result && (
        <div className={`employer-review-result ${result.type}`}>
          {result.message}
        </div>
      )}

      {isMonthlyReview && context.supported && (
        <>
          <div className="employer-review-meta">
            <div>
              <span className="employer-review-label">
                {t('documents.employer.monthLabel', 'Payroll month')}
              </span>
              <strong>{formatEmployerMonthLabel(context.candidate_year_month)}</strong>
            </div>
            <div>
              <span className="employer-review-label">
                {t('documents.employer.signalLabel', 'Detected from')}
              </span>
              <strong>{context.month?.payroll_signal || context.document_type}</strong>
            </div>
            <div>
              <span className="employer-review-label">
                {t('documents.employer.lastUpdate', 'Last signal')}
              </span>
              <strong>{formatEmployerDateTime(context.month?.last_signal_at)}</strong>
            </div>
            <div>
              <span className="employer-review-label">
                {t('documents.employer.summaryAmount', 'Gross wages')}
              </span>
              <strong>{monthGrossDisplay === '--' ? '--' : `EUR ${monthGrossDisplay}`}</strong>
            </div>
          </div>

          <div className="employer-review-form-grid">
            <label>
              <span>{t('documents.employer.employeeCount', 'Employee count')}</span>
              <input
                type="number"
                min="0"
                value={monthForm.employee_count}
                onChange={(event) => setMonthForm((current) => ({ ...current, employee_count: event.target.value }))}
              />
            </label>
            <label>
              <span>{t('documents.employer.grossWages', 'Gross wages')}</span>
              <input
                type="number"
                step="0.01"
                min="0"
                value={monthForm.gross_wages}
                onChange={(event) => setMonthForm((current) => ({ ...current, gross_wages: event.target.value }))}
              />
            </label>
            <label>
              <span>{t('documents.employer.netPaid', 'Net paid')}</span>
              <input
                type="number"
                step="0.01"
                min="0"
                value={monthForm.net_paid}
                onChange={(event) => setMonthForm((current) => ({ ...current, net_paid: event.target.value }))}
              />
            </label>
            <label>
              <span>{t('documents.employer.socialCost', 'Employer social cost')}</span>
              <input
                type="number"
                step="0.01"
                min="0"
                value={monthForm.employer_social_cost}
                onChange={(event) => setMonthForm((current) => ({ ...current, employer_social_cost: event.target.value }))}
              />
            </label>
            <label>
              <span>{t('documents.employer.lohnsteuer', 'Lohnsteuer')}</span>
              <input
                type="number"
                step="0.01"
                min="0"
                value={monthForm.lohnsteuer}
                onChange={(event) => setMonthForm((current) => ({ ...current, lohnsteuer: event.target.value }))}
              />
            </label>
            <label>
              <span>{t('documents.employer.db', 'DB')}</span>
              <input
                type="number"
                step="0.01"
                min="0"
                value={monthForm.db_amount}
                onChange={(event) => setMonthForm((current) => ({ ...current, db_amount: event.target.value }))}
              />
            </label>
            <label>
              <span>{t('documents.employer.dz', 'DZ')}</span>
              <input
                type="number"
                step="0.01"
                min="0"
                value={monthForm.dz_amount}
                onChange={(event) => setMonthForm((current) => ({ ...current, dz_amount: event.target.value }))}
              />
            </label>
            <label>
              <span>{t('documents.employer.kommunalsteuer', 'Kommunalsteuer')}</span>
              <input
                type="number"
                step="0.01"
                min="0"
                value={monthForm.kommunalsteuer}
                onChange={(event) => setMonthForm((current) => ({ ...current, kommunalsteuer: event.target.value }))}
              />
            </label>
            <label>
              <span>{t('documents.employer.specialPayments', 'Special payments')}</span>
              <input
                type="number"
                step="0.01"
                min="0"
                value={monthForm.special_payments}
                onChange={(event) => setMonthForm((current) => ({ ...current, special_payments: event.target.value }))}
              />
            </label>
            <label className="employer-review-full-width">
              <span>{t('documents.employer.notes', 'Notes')}</span>
              <textarea
                rows={3}
                value={monthForm.notes}
                onChange={(event) => setMonthForm((current) => ({ ...current, notes: event.target.value }))}
              />
            </label>
          </div>

          <div className="employer-review-actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleSaveMonthSummary}
              disabled={busyAction !== null}
            >
              {busyAction === 'save-month'
                ? t('documents.employer.saving', 'Saving...')
                : t('documents.employer.saveSummary', 'Save summary')}
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleConfirmPayroll}
              disabled={busyAction !== null}
            >
              {busyAction === 'confirm-payroll'
                ? t('documents.employer.confirming', 'Confirming...')
                : t('documents.employer.confirmPayroll', 'Mark as payroll month')}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleConfirmNoPayroll}
              disabled={busyAction !== null}
            >
              {busyAction === 'confirm-no-payroll'
                ? t('documents.employer.confirming', 'Confirming...')
                : t('documents.employer.confirmNoPayroll', 'Mark as no payroll')}
            </button>
          </div>
        </>
      )}

      {isAnnualReview && context.supported && (
        <>
          <div className="employer-review-meta">
            <div>
              <span className="employer-review-label">
                {t('documents.employer.taxYear', 'Tax year')}
              </span>
              <strong>{context.candidate_tax_year || '--'}</strong>
            </div>
            <div>
              <span className="employer-review-label">
                {t('documents.employer.archiveSignal', 'Detected from')}
              </span>
              <strong>{context.annual_archive?.archive_signal || context.document_type}</strong>
            </div>
            <div>
              <span className="employer-review-label">
                {t('documents.employer.lastUpdate', 'Last signal')}
              </span>
              <strong>{formatEmployerDateTime(context.annual_archive?.last_signal_at)}</strong>
            </div>
            <div>
              <span className="employer-review-label">
                {t('documents.employer.summaryAmount', 'Gross wages')}
              </span>
              <strong>{annualGrossDisplay === '--' ? '--' : `EUR ${annualGrossDisplay}`}</strong>
            </div>
          </div>

          <div className="employer-review-form-grid">
            <label>
              <span>{t('documents.employer.employerName', 'Employer name')}</span>
              <input
                type="text"
                value={annualForm.employer_name}
                onChange={(event) => setAnnualForm((current) => ({ ...current, employer_name: event.target.value }))}
              />
            </label>
            <label>
              <span>{t('documents.employer.grossIncome', 'Gross income')}</span>
              <input
                type="number"
                step="0.01"
                min="0"
                value={annualForm.gross_income}
                onChange={(event) => setAnnualForm((current) => ({ ...current, gross_income: event.target.value }))}
              />
            </label>
            <label>
              <span>{t('documents.employer.withheldTax', 'Withheld tax')}</span>
              <input
                type="number"
                step="0.01"
                min="0"
                value={annualForm.withheld_tax}
                onChange={(event) => setAnnualForm((current) => ({ ...current, withheld_tax: event.target.value }))}
              />
            </label>
            <label className="employer-review-full-width">
              <span>{t('documents.employer.notes', 'Notes')}</span>
              <textarea
                rows={3}
                value={annualForm.notes}
                onChange={(event) => setAnnualForm((current) => ({ ...current, notes: event.target.value }))}
              />
            </label>
          </div>

          <div className="employer-review-actions">
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleArchiveYear}
              disabled={busyAction !== null}
            >
              {busyAction === 'archive-year'
                ? t('documents.employer.saving', 'Saving...')
                : context.annual_archive?.status === 'archived'
                  ? t('documents.employer.updateArchive', 'Update archived year')
                  : t('documents.employer.archiveYear', 'Archive payroll year')}
            </button>
          </div>
        </>
      )}

      {showReasonCard && (
        <div className="employer-review-info">
          {context.reason === 'current_year_not_archivable'
            ? t(
                'documents.employer.currentYearInfo',
                'This Lohnzettel belongs to the current year, so it is not treated as a historical payroll archive yet.'
              )
            : t(
                'documents.employer.taxYearMissing',
                'We could not read a historical payroll year from this file yet. You can still keep the document, but it is not ready for annual archive review.'
              )}
        </div>
      )}
    </section>
  );
};

export default EmployerReviewPanel;
