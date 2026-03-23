import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  FileSearch,
  PencilLine,
  Power,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import FuturisticIcon from '../components/common/FuturisticIcon';
import LiabilityForm from '../components/liabilities/LiabilityForm';
import LiabilityList from '../components/liabilities/LiabilityList';
import { useConfirm } from '../hooks/useConfirm';
import { documentService } from '../services/documentService';
import { liabilityService } from '../services/liabilityService';
import { propertyService } from '../services/propertyService';
import { Document, DocumentType } from '../types/document';
import { getApiErrorMessage } from '../utils/apiError';
import { formatDocumentFieldList } from '../utils/documentFieldLabel';
import {
  LiabilityCreatePayload,
  LiabilityDetail,
  LiabilityRecord,
  LiabilityUpdatePayload,
} from '../types/liability';
import './LiabilitiesPage.css';

type PropertyOption = {
  value: string;
  label: string;
};

/* ── helpers ── */

const formatCurrency = (value: number) =>
  new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value || 0);

const formatDate = (value?: string | null) => {
  if (!value) return '\u2014';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString();
};

type AmortizationRow = {
  month: number;
  label: string;
  payment: number;
  principalPortion: number;
  interest: number;
  remaining: number;
};

function computeAmortization(
  startingBalance: number,
  annualRate: number,
  monthlyPayment: number,
  startDate: string,
): AmortizationRow[] {
  const rows: AmortizationRow[] = [];
  let remaining = startingBalance;
  const monthlyRate = annualRate / 100 / 12;
  const start = new Date(startDate);

  for (let i = 0; remaining > 0.01 && i < 600; i++) {
    const interest = remaining * monthlyRate;
    const actualPayment = Math.min(monthlyPayment, remaining + interest);
    const principalPortion = actualPayment - interest;
    remaining = Math.max(0, remaining - principalPortion);

    const monthDate = new Date(start.getFullYear(), start.getMonth() + i, 1);
    const label = monthDate.toLocaleDateString(undefined, { year: 'numeric', month: 'short' });

    rows.push({ month: i + 1, label, payment: actualPayment, principalPortion, interest, remaining });
  }
  return rows;
}

function computeInterestTrend(
  outstanding: number,
  annualRate: number,
  startDate: string,
  monthlyPayment?: number | null,
): { label: string; interest: number }[] {
  const data: { label: string; interest: number }[] = [];
  const now = new Date();
  const start = new Date(startDate);
  const monthlyRate = annualRate / 100 / 12;
  let balance = outstanding;
  const months = 12;
  const baseDate = new Date(Math.max(start.getTime(), new Date(now.getFullYear(), now.getMonth() - 11, 1).getTime()));

  for (let i = 0; i < months; i++) {
    const monthDate = new Date(baseDate.getFullYear(), baseDate.getMonth() + i, 1);
    const interest = balance * monthlyRate;
    const label = monthDate.toLocaleDateString(undefined, { year: 'numeric', month: 'short' });
    data.push({ label, interest: Math.round(interest * 100) / 100 });
    if (monthlyPayment && monthlyPayment > 0) {
      const principalPortion = monthlyPayment - interest;
      balance = Math.max(0, balance - principalPortion);
    }
  }
  return data;
}

/* ── Full-page liability detail (matches PropertyDetail layout) ── */

const LiabilityFullDetail = ({
  liability,
  loading,
  onBack,
  onEdit,
  onDeactivate,
}: {
  liability: LiabilityDetail;
  loading: boolean;
  onBack: () => void;
  onEdit: () => void;
  onDeactivate: () => Promise<void>;
}) => {
  const { t } = useTranslation();
  const [showAllRows, setShowAllRows] = useState(false);

  const progressData = useMemo(() => {
    const principal = liability.principal_amount || 0;
    const repaid = principal > 0 ? Math.max(0, Math.min(principal, principal - liability.outstanding_balance)) : 0;
    const pct = principal > 0 ? Math.round((repaid / principal) * 100) : 0;
    const remaining = principal > 0 ? Math.max(0, liability.outstanding_balance) : 0;
    return { principal, repaid, pct, remaining };
  }, [liability]);

  const amortization = useMemo(() => {
    if (!liability.monthly_payment || liability.monthly_payment <= 0 || liability.interest_rate == null) return null;
    return computeAmortization(liability.outstanding_balance, liability.interest_rate, liability.monthly_payment, liability.start_date);
  }, [liability]);

  const amortizationSummary = useMemo(() => {
    if (!amortization || amortization.length === 0) return null;
    const totalPayments = amortization.reduce((s, r) => s + r.payment, 0);
    const totalInterest = amortization.reduce((s, r) => s + r.interest, 0);
    const lastRow = amortization[amortization.length - 1];
    return { totalPayments, totalInterest, payoffLabel: lastRow.label };
  }, [amortization]);

  const interestTrend = useMemo(() => {
    if (liability.interest_rate == null || liability.interest_rate <= 0) return null;
    return computeInterestTrend(liability.outstanding_balance, liability.interest_rate, liability.start_date, liability.monthly_payment);
  }, [liability]);

  const sourceDocumentLink = useMemo(() => {
    if (liability.source_document_id) return `/documents/${liability.source_document_id}`;
    const params = new URLSearchParams();
    params.set('type', liability.recommended_document_type || 'loan_contract');
    if (liability.linked_property_id) params.set('property_id', liability.linked_property_id);
    return `/documents?${params.toString()}`;
  }, [liability]);

  const sourceManagedMessage = useMemo(() => {
    if (liability.can_edit_directly) return null;
    if (liability.edit_via_document) return t('liabilities.documents.sourceManagedMessage');
    return t('liabilities.documents.sourceManagedPropertyLoanMessage');
  }, [liability, t]);

  if (loading) {
    return (
      <div className="property-detail">
        <div className="breadcrumb">
          <button className="breadcrumb-link" onClick={onBack}>
            <FuturisticIcon icon={ArrowLeft} tone="slate" size="xs" />
            <span>{t('liabilities.page.title')}</span>
          </button>
        </div>
        <p className="liability-hint">{t('common.loading')}</p>
      </div>
    );
  }

  const visibleRows = amortization ? (showAllRows ? amortization : amortization.slice(0, 12)) : [];

  return (
    <div className="property-detail">
      {/* Breadcrumb */}
      <div className="breadcrumb">
        <button className="breadcrumb-link" onClick={onBack}>
          <FuturisticIcon icon={ArrowLeft} tone="slate" size="xs" />
          <span>{t('liabilities.page.title')}</span>
        </button>
        <span className="breadcrumb-separator">/</span>
        <span className="breadcrumb-current">{liability.display_name}</span>
      </div>

      {/* Header */}
      <div className="property-detail-header">
        <div className="header-content">
          <h1>{liability.display_name}</h1>
          <div className="property-badges">
            <span className={`status-badge ${liability.is_active ? 'active' : 'archived'}`}>
              {liability.is_active ? t('common.active') : t('common.inactive')}
            </span>
            <span className="type-badge asset">
              {t(`liabilities.type.${liability.liability_type}`)}
            </span>
          </div>
        </div>
        <div className="header-actions">
          {liability.source_document_id && (
            <Link className="btn btn-secondary btn-icon" to={sourceDocumentLink}>
              <FuturisticIcon icon={FileSearch} tone="cyan" size="xs" />
              <span>{t('liabilities.documents.openSourceDocument')}</span>
            </Link>
          )}
          {liability.can_edit_directly && (
            <button className="btn btn-secondary btn-icon" onClick={onEdit}>
              <FuturisticIcon icon={PencilLine} tone="slate" size="xs" />
              <span>{t('common.edit')}</span>
            </button>
          )}
          {liability.is_active && liability.can_deactivate_directly && (
            <button className="btn btn-secondary btn-icon" onClick={onDeactivate}>
              <FuturisticIcon icon={Power} tone="slate" size="xs" />
              <span>{t('liabilities.actions.deactivate')}</span>
            </button>
          )}
        </div>
      </div>

      {/* Source-managed callout */}
      {sourceManagedMessage && (
        <div className="liability-doc-callout" style={{ marginBottom: '1.5rem' }}>
          <div>
            <strong>{t('liabilities.documents.sourceManagedTitle')}</strong>
            <p>{sourceManagedMessage}</p>
          </div>
          <Link className="btn btn-secondary btn-sm" to={sourceDocumentLink}>
            {liability.edit_via_document
              ? t('liabilities.documents.openSourceDocument')
              : t('liabilities.documents.openLinkedLoanFlow')}
          </Link>
        </div>
      )}

      {liability.requires_supporting_document && (
        <div className="liability-doc-callout" style={{ marginBottom: '1.5rem' }}>
          <div>
            <strong>{t('liabilities.documents.missingTitle')}</strong>
            <p>{t('liabilities.documents.missingHint')}</p>
          </div>
          <Link className="btn btn-secondary btn-sm" to={sourceDocumentLink}>
            {t('liabilities.documents.uploadSupportingDocument')}
          </Link>
        </div>
      )}

      {/* Info Grid */}
      <div className="property-info-section">
        <h2>{t('liabilities.detail.title')}</h2>
        <div className="info-grid">
          {/* Loan Details Card */}
          <div className="info-card">
            <h3>{t('liabilities.fields.principalAmount')}</h3>
            <div className="info-rows">
              <div className="info-row">
                <span className="label">{t('liabilities.fields.principalAmount')}</span>
                <span className="value">{formatCurrency(liability.principal_amount)}</span>
              </div>
              <div className="info-row highlight">
                <span className="label">{t('liabilities.fields.outstandingBalance')}</span>
                <span className="value">{formatCurrency(liability.outstanding_balance)}</span>
              </div>
              <div className="info-row">
                <span className="label">{t('liabilities.fields.monthlyPayment')}</span>
                <span className="value">
                  {liability.monthly_payment == null ? t('common.notAvailable') : formatCurrency(liability.monthly_payment)}
                </span>
              </div>
              <div className="info-row">
                <span className="label">{t('liabilities.fields.interestRate')}</span>
                <span className="value">
                  {liability.interest_rate == null ? t('common.notAvailable') : `${Number(liability.interest_rate).toFixed(3)}%`}
                </span>
              </div>
              <div className="info-row">
                <span className="label">{t('liabilities.fields.currency')}</span>
                <span className="value">{liability.currency}</span>
              </div>
            </div>
          </div>

          {/* Dates & Source Card */}
          <div className="info-card">
            <h3>{t('liabilities.fields.startDate')}</h3>
            <div className="info-rows">
              <div className="info-row">
                <span className="label">{t('liabilities.fields.startDate')}</span>
                <span className="value">{formatDate(liability.start_date)}</span>
              </div>
              <div className="info-row">
                <span className="label">{t('liabilities.fields.endDate')}</span>
                <span className="value">{formatDate(liability.end_date)}</span>
              </div>
              <div className="info-row">
                <span className="label">{t('liabilities.fields.liabilityType')}</span>
                <span className="value">{t(`liabilities.type.${liability.liability_type}`)}</span>
              </div>
              <div className="info-row">
                <span className="label">{t('liabilities.fields.sourceType')}</span>
                <span className="value">{t(`liabilities.sourceType.${liability.source_type}`)}</span>
              </div>
              <div className="info-row">
                <span className="label">{t('liabilities.fields.sourceDocument')}</span>
                <span className="value">
                  {liability.source_document_id
                    ? t('liabilities.documents.linkedDocumentId', { id: liability.source_document_id })
                    : '-'}
                </span>
              </div>
            </div>
          </div>

          {/* Tax Info Card */}
          <div className="info-card">
            <h3>{t('liabilities.fields.taxRelevant')}</h3>
            <div className="info-rows">
              <div className="info-row">
                <span className="label">{t('liabilities.fields.taxRelevant')}</span>
                <span className="value">{liability.tax_relevant ? t('common.yes') : t('common.no')}</span>
              </div>
              <div className="info-row">
                <span className="label">{t('liabilities.fields.reportCategory')}</span>
                <span className="value">{t(`liabilities.reportCategory.${liability.report_category}`)}</span>
              </div>
              <div className="info-row">
                <span className="label">{t('liabilities.fields.taxRelevanceReason')}</span>
                <span className="value">{liability.tax_relevance_reason || '-'}</span>
              </div>
              {liability.notes && (
                <div className="info-row">
                  <span className="label">{t('liabilities.fields.notes')}</span>
                  <span className="value">{liability.notes}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Repayment Progress */}
      {progressData.principal > 0 && (
        <div className="liability-progress-section" style={{ marginBottom: '2rem' }}>
          <h3>{t('liabilities.progress.title')}</h3>
          <div className="liability-progress-bar liability-progress-bar--large">
            <div className="liability-progress-bar-fill" style={{ width: `${progressData.pct}%` }} />
          </div>
          <div className="liability-progress-details">
            <span>
              {t('liabilities.progress.repaid')}: {formatCurrency(progressData.repaid)}{' '}
              {t('liabilities.progress.ofTotal', { total: formatCurrency(progressData.principal) })}
            </span>
            <span>
              {t('liabilities.progress.remaining')}: {formatCurrency(progressData.remaining)}
            </span>
          </div>
          <span className="liability-progress-pct">{progressData.pct}%</span>
        </div>
      )}

      {/* Amortization Schedule */}
      <div className="property-info-section">
        <h2>{t('liabilities.schedule.title')}</h2>
        {!amortization ? (
          <p className="liability-hint">{t('liabilities.schedule.noData')}</p>
        ) : (
          <>
            <table className="liability-section-table">
              <thead>
                <tr>
                  <th>{t('liabilities.schedule.month')}</th>
                  <th>{t('liabilities.schedule.payment')}</th>
                  <th>{t('liabilities.schedule.principal')}</th>
                  <th>{t('liabilities.schedule.interest')}</th>
                  <th>{t('liabilities.schedule.remaining')}</th>
                </tr>
              </thead>
              <tbody>
                {visibleRows.map((row) => (
                  <tr key={row.month}>
                    <td>{row.label}</td>
                    <td>{formatCurrency(row.payment)}</td>
                    <td>{formatCurrency(row.principalPortion)}</td>
                    <td>{formatCurrency(row.interest)}</td>
                    <td>{formatCurrency(row.remaining)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {amortization.length > 12 && (
              <button
                type="button"
                className="btn btn-secondary liability-schedule-toggle"
                onClick={() => setShowAllRows((prev) => !prev)}
              >
                {showAllRows ? t('liabilities.schedule.showLess') : t('liabilities.schedule.showAll')}
              </button>
            )}
            {amortizationSummary && (
              <div className="liability-schedule-summary">
                <div className="liability-schedule-summary-item">
                  <small>{t('liabilities.schedule.totalPayments')}</small>
                  <strong>{formatCurrency(amortizationSummary.totalPayments)}</strong>
                </div>
                <div className="liability-schedule-summary-item">
                  <small>{t('liabilities.schedule.totalInterest')}</small>
                  <strong>{formatCurrency(amortizationSummary.totalInterest)}</strong>
                </div>
                <div className="liability-schedule-summary-item">
                  <small>{t('liabilities.schedule.payoffDate')}</small>
                  <strong>{amortizationSummary.payoffLabel}</strong>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Interest Trend Chart */}
      {interestTrend && interestTrend.length > 0 && (
        <div className="property-info-section">
          <h2>{t('liabilities.interestTrend.title')}</h2>
          <p className="liability-hint">{t('liabilities.interestTrend.projected')}</p>
          <div className="liability-interest-chart">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={interestTrend} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
                <XAxis dataKey="label" tick={{ fontSize: 11, fill: 'var(--color-text-secondary)' }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 11, fill: 'var(--color-text-secondary)' }} tickLine={false} axisLine={false} tickFormatter={(v: number) => `\u20AC${v}`} />
                <Tooltip
                  formatter={(value: number) => [formatCurrency(value), t('liabilities.interestTrend.monthly')]}
                  contentStyle={{ borderRadius: '12px', border: '1px solid var(--color-border)', background: 'rgba(255,255,255,0.96)' }}
                />
                <Bar dataKey="interest" name={t('liabilities.interestTrend.monthly')} fill="rgba(99,102,241,0.7)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Related Transactions */}
      <div className="property-info-section">
        <h2>{t('liabilities.detail.relatedTransactions')}</h2>
        {liability.related_transactions.length ? (
          <table className="liability-section-table">
            <thead>
              <tr>
                <th>{t('transactions.date')}</th>
                <th>{t('transactions.type')}</th>
                <th>{t('transactions.amount')}</th>
                <th>{t('transactions.description')}</th>
              </tr>
            </thead>
            <tbody>
              {liability.related_transactions.map((tx) => (
                <tr key={tx.id}>
                  <td>{formatDate(tx.transaction_date)}</td>
                  <td>{tx.type}</td>
                  <td>{formatCurrency(tx.amount)}</td>
                  <td>{tx.description || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="liability-hint">{t('liabilities.detail.noTransactions')}</p>
        )}
      </div>

      {/* Related Recurring Transactions */}
      <div className="property-info-section">
        <h2>{t('liabilities.detail.relatedRecurring')}</h2>
        {liability.related_recurring_transactions.length ? (
          <table className="liability-section-table">
            <thead>
              <tr>
                <th>{t('common.type')}</th>
                <th>{t('common.description')}</th>
                <th>{t('transactions.amount')}</th>
                <th>{t('recurring.frequency')}</th>
                <th>{t('common.next')}</th>
              </tr>
            </thead>
            <tbody>
              {liability.related_recurring_transactions.map((recurring) => (
                <tr key={recurring.id}>
                  <td>{recurring.recurring_type}</td>
                  <td>{recurring.description}</td>
                  <td>{formatCurrency(recurring.amount)}</td>
                  <td>{recurring.frequency}</td>
                  <td>{formatDate(recurring.next_generation_date)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="liability-hint">{t('liabilities.detail.noRecurring')}</p>
        )}
      </div>
    </div>
  );
};


/* ── Main page component ── */

const LiabilitiesPage = () => {
  const { t } = useTranslation();
  const { confirm, alert } = useConfirm();
  const navigate = useNavigate();
  const location = useLocation();
  const { id } = useParams<{ id: string }>();

  const [includeInactive, setIncludeInactive] = useState(false);
  const [liabilities, setLiabilities] = useState<LiabilityRecord[]>([]);
  const [loanDocuments, setLoanDocuments] = useState<Document[]>([]);
  const [selectedLiability, setSelectedLiability] = useState<LiabilityDetail | null>(null);
  const [propertyOptions, setPropertyOptions] = useState<PropertyOption[]>([]);
  const [loadingList, setLoadingList] = useState(false);
  const [loadingLoanDocuments, setLoadingLoanDocuments] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [editing, setEditing] = useState(false);

  const isCreateMode = location.pathname.endsWith('/new');

  const pendingLoanDocuments = useMemo(() => {
    const linkedDocumentIds = new Set(
      liabilities
        .map((liability) => liability.source_document_id)
        .filter((value): value is number => typeof value === 'number'),
    );
    return loanDocuments.filter((document) => {
      if (linkedDocumentIds.has(document.id)) return false;
      const suggestion = document.ocr_result?.import_suggestion;
      const status = suggestion?.status;
      return status === 'pending' || status === 'needs_input';
    });
  }, [liabilities, loanDocuments]);

  const activeLiabilityCount = useMemo(
    () => liabilities.filter((liability) => liability.is_active).length,
    [liabilities],
  );
  const inactiveLiabilityCount = liabilities.length - activeLiabilityCount;

  const refreshList = async () => {
    setLoadingList(true);
    try {
      const data = await liabilityService.list(includeInactive);
      setLiabilities(data.items);
    } catch (error) {
      console.error('Failed to load liabilities', error);
      await alert(t('liabilities.errors.loadList'), { variant: 'danger' });
    } finally {
      setLoadingList(false);
    }
  };

  const refreshProperties = async () => {
    try {
      const data = await propertyService.getProperties(true);
      const options = (data.properties || []).map((property) => ({
        value: String(property.id),
        label: property.address,
      }));
      setPropertyOptions(options);
    } catch (error) {
      console.error('Failed to load properties for liabilities', error);
    }
  };

  const refreshLoanDocuments = async () => {
    setLoadingLoanDocuments(true);
    try {
      const data = await documentService.getDocuments(
        { document_type: DocumentType.LOAN_CONTRACT },
        1,
        50,
      );
      setLoanDocuments(data.documents);
    } catch (error) {
      console.error('Failed to load loan documents for liabilities', error);
    } finally {
      setLoadingLoanDocuments(false);
    }
  };

  const refreshDetail = async (liabilityId: number) => {
    setLoadingDetail(true);
    try {
      const detail = await liabilityService.get(liabilityId);
      setSelectedLiability(detail);
    } catch (error) {
      console.error('Failed to load liability detail', error);
      setSelectedLiability(null);
      await alert(t('liabilities.errors.loadDetail'), { variant: 'danger' });
    } finally {
      setLoadingDetail(false);
    }
  };

  useEffect(() => {
    void refreshProperties();
    void refreshLoanDocuments();
  }, []);

  useEffect(() => {
    void refreshList();
  }, [includeInactive]);

  useEffect(() => {
    if (!id) {
      setSelectedLiability(null);
      setEditing(false);
      return;
    }
    const liabilityId = Number(id);
    if (!Number.isFinite(liabilityId)) return;
    void refreshDetail(liabilityId);
  }, [id]);

  const handleCreate = async (payload: LiabilityCreatePayload | LiabilityUpdatePayload) => {
    setSubmitting(true);
    try {
      const created = await liabilityService.create(payload as LiabilityCreatePayload);
      await refreshList();
      setEditing(false);
      navigate(`/liabilities/${created.id}`);
      await refreshDetail(created.id);
    } catch (error) {
      console.error('Failed to create liability', error);
      await alert(getApiErrorMessage(error, t('liabilities.errors.create')), { variant: 'danger' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleUpdate = async (payload: LiabilityCreatePayload | LiabilityUpdatePayload) => {
    if (!selectedLiability) return;
    setSubmitting(true);
    try {
      await liabilityService.update(selectedLiability.id, payload as LiabilityUpdatePayload);
      await Promise.all([refreshList(), refreshDetail(selectedLiability.id)]);
      setEditing(false);
    } catch (error) {
      console.error('Failed to update liability', error);
      await alert(getApiErrorMessage(error, t('liabilities.errors.update')), { variant: 'danger' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeactivate = async () => {
    if (!selectedLiability) return;
    const accepted = await confirm(t('liabilities.confirm.deactivate'), {
      title: t('liabilities.actions.deactivate'),
      confirmText: t('common.continue'),
      cancelText: t('common.cancel'),
      variant: 'warning',
    });
    if (!accepted) return;
    setSubmitting(true);
    try {
      await liabilityService.remove(selectedLiability.id);
      await refreshList();
      navigate('/liabilities');
      setSelectedLiability(null);
      setEditing(false);
    } catch (error) {
      console.error('Failed to deactivate liability', error);
      await alert(getApiErrorMessage(error, t('liabilities.errors.delete')), { variant: 'danger' });
    } finally {
      setSubmitting(false);
    }
  };

  const openCreate = () => {
    setEditing(false);
    navigate('/liabilities/new');
  };

  const openSelect = (liabilityId: number) => {
    setEditing(false);
    navigate(`/liabilities/${liabilityId}`);
  };

  const closeManagePane = () => {
    setEditing(false);
    navigate('/liabilities');
  };

  const getPendingLoanDocumentStatus = (document: Document) => {
    const suggestion = document.ocr_result?.import_suggestion;
    if (suggestion?.status === 'needs_input') {
      return t('liabilities.documents.pendingNeedsInput', 'Needs input');
    }
    const missingFields = suggestion?.data?.missing_fields;
    if (Array.isArray(missingFields) && missingFields.length > 0) {
      return t('liabilities.documents.pendingMissingFields', {
        defaultValue: 'Missing: {{fields}}',
        fields: formatDocumentFieldList(missingFields, t),
      });
    }
    return t('liabilities.documents.pendingReview', 'Awaiting confirmation');
  };

  /* ── Full-page create form ── */
  if (isCreateMode) {
    return (
      <div className="liabilities-page liabilities-page--form-mode">
        <div className="liabilities-header">
          <div className="liabilities-title">
            <h1>{t('liabilities.page.title')}</h1>
            <p>{t('liabilities.page.manageSub')}</p>
          </div>
        </div>
        <div className="liabilities-form-shell card">
          <button type="button" className="liabilities-back-strip" onClick={closeManagePane}>
            {t('common.back')}
          </button>
          <div className="liabilities-form-stage">
            <LiabilityForm
              propertyOptions={propertyOptions}
              submitting={submitting}
              onCancel={closeManagePane}
              onSubmit={handleCreate}
            />
          </div>
        </div>
      </div>
    );
  }

  /* ── Full-page edit form ── */
  if (selectedLiability && editing) {
    return (
      <div className="liabilities-page liabilities-page--form-mode">
        <div className="liabilities-header">
          <div className="liabilities-title">
            <h1>{t('liabilities.page.title')}</h1>
            <p>{t('liabilities.page.manageSub')}</p>
          </div>
        </div>
        <div className="liabilities-form-shell card">
          <button type="button" className="liabilities-back-strip" onClick={() => setEditing(false)}>
            {t('common.back')}
          </button>
          <div className="liabilities-form-stage">
            <LiabilityForm
              initialValue={selectedLiability}
              propertyOptions={propertyOptions}
              submitting={submitting}
              onCancel={() => setEditing(false)}
              onSubmit={handleUpdate}
            />
          </div>
        </div>
      </div>
    );
  }

  /* ── Full-page detail view (like PropertyDetail) ── */
  if (id && selectedLiability) {
    return (
      <LiabilityFullDetail
        liability={selectedLiability}
        loading={loadingDetail}
        onBack={closeManagePane}
        onEdit={() => setEditing(true)}
        onDeactivate={handleDeactivate}
      />
    );
  }

  /* ── Loading detail ── */
  if (id && !selectedLiability && loadingDetail) {
    return (
      <div className="property-detail">
        <div className="breadcrumb">
          <button className="breadcrumb-link" onClick={closeManagePane}>
            <FuturisticIcon icon={ArrowLeft} tone="slate" size="xs" />
            <span>{t('liabilities.page.title')}</span>
          </button>
        </div>
        <p className="liability-hint">{t('common.loading')}</p>
      </div>
    );
  }

  /* ── List view ── */
  return (
    <div className="liabilities-page">
      <div className="properties-header">
        <div className="properties-title">
          <h1>{t('liabilities.page.title')}</h1>
          <p className="properties-subtitle">{t('liabilities.page.manageSub')}</p>
        </div>
        <div className="properties-actions">
          <button type="button" className="btn btn-primary" onClick={openCreate}>
            {t('liabilities.actions.new')}
          </button>
        </div>
      </div>

      <div className="properties-overview-link" style={{ marginBottom: '16px' }}>
        <Link to="/liabilities/overview" className="btn btn-secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', width: '100%', justifyContent: 'center', textDecoration: 'none' }}>
          {t('liabilities.overview.pageTitle', 'Liability Overview')}
        </Link>
      </div>

      <div className="list-header">
        <div className="list-stats">
          <span className="stat-item">
            <strong>{activeLiabilityCount}</strong> {t('liabilities.manage.countLabel')}
          </span>
          {pendingLoanDocuments.length > 0 && (
            <span className="stat-item" style={{ marginLeft: '8px' }}>
              <strong>{pendingLoanDocuments.length}</strong>{' '}
              {t('liabilities.documents.pendingTitle')}
            </span>
          )}
          {includeInactive && inactiveLiabilityCount > 0 && (
            <span className="stat-item muted">
              ({inactiveLiabilityCount} {t('common.inactive')})
            </span>
          )}
        </div>
        <div className="toggle-archived">
          <label>
            <input
              type="checkbox"
              checked={includeInactive}
              onChange={(event) => setIncludeInactive(event.target.checked)}
            />
            {t('liabilities.filters.includeInactive')}
          </label>
        </div>
      </div>

      {(loadingLoanDocuments || pendingLoanDocuments.length > 0) && (
        <section className="liability-panel card">
          <div className="liability-group-header">
            <div>
              <h2>{t('liabilities.documents.pendingTitle', 'Pending loan contracts')}</h2>
              <p className="liability-hint">
                {t('liabilities.documents.pendingHint', 'Confirmed contracts become liabilities automatically. Contracts still waiting for review or missing fields stay here until you finish them in Documents.')}
              </p>
            </div>
            <span className="liability-count-badge">
              {loadingLoanDocuments ? '...' : pendingLoanDocuments.length}
            </span>
          </div>
          {loadingLoanDocuments ? (
            <p className="liability-hint">{t('common.loading')}</p>
          ) : (
            <div className="liability-list-items">
              {pendingLoanDocuments.map((document) => (
                <article key={document.id} className="liability-pending-doc-card">
                  <div>
                    <strong>{document.file_name || `${t('documents.document')} #${document.id}`}</strong>
                    <p>{getPendingLoanDocumentStatus(document)}</p>
                  </div>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => navigate(`/documents/${document.id}`)}
                  >
                    {t('liabilities.documents.openSourceDocument', 'Open source document')}
                  </button>
                </article>
              ))}
            </div>
          )}
        </section>
      )}

      <div className="liabilities-content">
        {loadingList ? (
          <section className="liability-panel card">
            <h2>{t('liabilities.manage.listTitle')}</h2>
            <p className="liability-hint">{t('common.loading')}</p>
          </section>
        ) : (
          <LiabilityList liabilities={liabilities} selectedId={null} onSelect={openSelect} />
        )}
      </div>
    </div>
  );
};

export default LiabilitiesPage;
