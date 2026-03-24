import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { LiabilityDetail } from '../../types/liability';

type LiabilityDetailProps = {
  liability: LiabilityDetail | null;
  loading?: boolean;
  onEdit: () => void;
  onDeactivate: () => void;
};

const formatCurrency = (value: number) =>
  new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value || 0);

const formatDate = (value?: string | null) => {
  if (!value) {
    return '\u2014';
  }
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

    rows.push({
      month: i + 1,
      label,
      payment: actualPayment,
      principalPortion,
      interest,
      remaining,
    });
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

  // Show up to 12 months of projected interest
  const months = 12;
  // Start from the later of start_date or 12 months ago
  const baseDate = new Date(Math.max(start.getTime(), new Date(now.getFullYear(), now.getMonth() - 11, 1).getTime()));

  for (let i = 0; i < months; i++) {
    const monthDate = new Date(baseDate.getFullYear(), baseDate.getMonth() + i, 1);
    const interest = balance * monthlyRate;
    const label = monthDate.toLocaleDateString(undefined, { year: 'numeric', month: 'short' });
    data.push({ label, interest: Math.round(interest * 100) / 100 });

    // If monthly payment is available, reduce the balance for the projection
    if (monthlyPayment && monthlyPayment > 0) {
      const principalPortion = monthlyPayment - interest;
      balance = Math.max(0, balance - principalPortion);
    }
  }

  return data;
}

const LiabilityDetailPanel = ({
  liability,
  loading = false,
  onEdit,
  onDeactivate,
}: LiabilityDetailProps) => {
  const { t } = useTranslation();
  const [showAllRows, setShowAllRows] = useState(false);

  const progressData = useMemo(() => {
    if (!liability) return null;
    const principal = liability.principal_amount || 0;
    const repaid = principal > 0
      ? Math.max(0, Math.min(principal, principal - liability.outstanding_balance))
      : 0;
    const pct = principal > 0 ? Math.round((repaid / principal) * 100) : 0;
    const remaining = principal > 0 ? Math.max(0, liability.outstanding_balance) : 0;
    return { principal, repaid, pct, remaining };
  }, [liability]);

  const amortization = useMemo(() => {
    if (
      !liability ||
      liability.monthly_payment == null ||
      liability.monthly_payment <= 0 ||
      liability.interest_rate == null
    ) {
      return null;
    }
    return computeAmortization(
      liability.outstanding_balance,
      liability.interest_rate,
      liability.monthly_payment,
      liability.start_date,
    );
  }, [liability]);

  const amortizationSummary = useMemo(() => {
    if (!amortization || amortization.length === 0) return null;
    const totalPayments = amortization.reduce((s, r) => s + r.payment, 0);
    const totalInterest = amortization.reduce((s, r) => s + r.interest, 0);
    const lastRow = amortization[amortization.length - 1];
    return { totalPayments, totalInterest, payoffLabel: lastRow.label };
  }, [amortization]);

  const interestTrend = useMemo(() => {
    if (!liability || liability.interest_rate == null || liability.interest_rate <= 0) {
      return null;
    }
    return computeInterestTrend(
      liability.outstanding_balance,
      liability.interest_rate,
      liability.start_date,
      liability.monthly_payment,
    );
  }, [liability]);

  const sourceDocumentLink = useMemo(() => {
    if (!liability) {
      return '/documents?type=loan_contract';
    }
    if (liability.source_document_id) {
      return `/documents/${liability.source_document_id}`;
    }

    const params = new URLSearchParams();
    params.set('type', liability.recommended_document_type || 'loan_contract');
    if (liability.linked_property_id) {
      params.set('property_id', liability.linked_property_id);
    }
    return `/documents?${params.toString()}`;
  }, [liability]);

  const sourceManagedMessage = useMemo(() => {
    if (!liability || liability.can_edit_directly) {
      return null;
    }
    if (liability.edit_via_document) {
      return t('liabilities.documents.sourceManagedMessage');
    }
    return t('liabilities.documents.sourceManagedPropertyLoanMessage');
  }, [liability, t]);

  if (loading) {
    return (
      <section className="liability-panel card">
        <h2>{t('liabilities.detail.title')}</h2>
        <p className="liability-hint">{t('common.loading')}</p>
      </section>
    );
  }

  if (!liability) {
    return (
      <section className="liability-panel card">
        <h2>{t('liabilities.detail.title')}</h2>
        <div className="liability-empty">
          {t('liabilities.detail.empty')}
        </div>
      </section>
    );
  }

  const visibleRows = amortization
    ? showAllRows
      ? amortization
      : amortization.slice(0, 12)
    : [];

  return (
    <section className="liability-panel card">
      <div className="liability-group-header">
        <div>
          <h2>{liability.display_name}</h2>
          <p className="liability-hint">{liability.lender_name}</p>
        </div>
        <span className={`liability-status-badge ${liability.is_active ? 'is-active' : 'is-inactive'}`}>
          {liability.is_active ? t('common.active') : t('common.inactive')}
        </span>
      </div>

      {sourceManagedMessage && (
        <div className="liability-doc-callout">
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
        <div className="liability-doc-callout">
          <div>
            <strong>{t('liabilities.documents.missingTitle')}</strong>
            <p>{t('liabilities.documents.missingHint')}</p>
          </div>
          <Link className="btn btn-secondary btn-sm" to={sourceDocumentLink}>
            {t('liabilities.documents.uploadSupportingDocument')}
          </Link>
        </div>
      )}

      {/* Repayment Progress */}
      {progressData && progressData.principal > 0 && (
        <div className="liability-progress-section">
          <h3>{t('liabilities.progress.title')}</h3>
          <div className="liability-progress-bar liability-progress-bar--large">
            <div
              className="liability-progress-bar-fill"
              style={{ width: `${progressData.pct}%` }}
            />
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

      <div className="liability-detail-grid">
        <div className="liability-detail-field">
          <small>{t('liabilities.fields.liabilityType')}</small>
          <strong>{t(`liabilities.type.${liability.liability_type}`)}</strong>
        </div>
        <div className="liability-detail-field">
          <small>{t('liabilities.fields.sourceType')}</small>
          <strong>{t(`liabilities.sourceType.${liability.source_type}`)}</strong>
        </div>
        <div className="liability-detail-field">
          <small>{t('liabilities.fields.reportCategory')}</small>
          <strong>{t(`liabilities.reportCategory.${liability.report_category}`)}</strong>
        </div>
        <div className="liability-detail-field">
          <small>{t('liabilities.fields.sourceDocument')}</small>
          <strong>
            {liability.source_document_id
              ? t('liabilities.documents.linkedDocumentId', { id: liability.source_document_id })
              : '-'}
          </strong>
        </div>
        <div className="liability-detail-field">
          <small>{t('liabilities.fields.principalAmount')}</small>
          <strong>{formatCurrency(liability.principal_amount)}</strong>
        </div>
        <div className="liability-detail-field">
          <small>{t('liabilities.fields.outstandingBalance')}</small>
          <strong>{formatCurrency(liability.outstanding_balance)}</strong>
        </div>
        <div className="liability-detail-field">
          <small>{t('liabilities.fields.monthlyPayment')}</small>
          <strong>
            {liability.monthly_payment == null
              ? t('common.notAvailable')
              : formatCurrency(liability.monthly_payment)}
          </strong>
        </div>
        <div className="liability-detail-field">
          <small>{t('liabilities.fields.interestRate')}</small>
          <strong>
            {liability.interest_rate == null
              ? t('common.notAvailable')
              : `${Number(liability.interest_rate).toFixed(3)}%`}
          </strong>
        </div>
        <div className="liability-detail-field">
          <small>{t('liabilities.fields.startDate')}</small>
          <strong>{formatDate(liability.start_date)}</strong>
        </div>
        <div className="liability-detail-field">
          <small>{t('liabilities.fields.endDate')}</small>
          <strong>{formatDate(liability.end_date)}</strong>
        </div>
        <div className="liability-detail-field">
          <small>{t('liabilities.fields.taxRelevant')}</small>
          <strong>{liability.tax_relevant ? t('common.yes') : t('common.no')}</strong>
        </div>
        <div className="liability-detail-field">
          <small>{t('liabilities.fields.currency')}</small>
          <strong>{liability.currency}</strong>
        </div>
        <div className="liability-detail-field liability-detail-field--full">
          <small>{t('liabilities.fields.taxRelevanceReason')}</small>
          <strong>{liability.tax_relevance_reason || '-'}</strong>
        </div>
        <div className="liability-detail-field liability-detail-field--full">
          <small>{t('liabilities.fields.notes')}</small>
          <strong>{liability.notes || '-'}</strong>
        </div>
      </div>

      <div className="liability-inline-actions">
        {liability.can_edit_directly && (
          <button type="button" className="btn btn-primary" onClick={onEdit}>
            {t('common.edit')}
          </button>
        )}
        {liability.is_active && liability.can_deactivate_directly && (
          <button type="button" className="btn btn-secondary" onClick={onDeactivate}>
            {t('liabilities.actions.deactivate')}
          </button>
        )}
      </div>

      {/* Amortization Schedule */}
      <div>
        <h3>{t('liabilities.schedule.title')}</h3>
        {!amortization ? (
          <p className="liability-hint">
            {t('liabilities.schedule.noData')}
          </p>
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
                {showAllRows
                  ? t('liabilities.schedule.showLess')
                  : t('liabilities.schedule.showAll')}
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

      {/* Interest Expense Trend Chart */}
      {interestTrend && interestTrend.length > 0 && (
        <div>
          <h3>{t('liabilities.interestTrend.title')}</h3>
          <p className="liability-hint">
            {t('liabilities.interestTrend.projected')}
          </p>
          <div className="liability-interest-chart">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={interestTrend} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 11, fill: 'var(--color-text-secondary)' }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: 'var(--color-text-secondary)' }}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(v: number) => `\u20AC${v}`}
                />
                <Tooltip
                  formatter={(value: number) => [formatCurrency(value), t('liabilities.interestTrend.monthly')]}
                  contentStyle={{
                    borderRadius: '12px',
                    border: '1px solid var(--color-border)',
                    background: 'rgba(255,255,255,0.96)',
                  }}
                />
                <Bar
                  dataKey="interest"
                  name={t('liabilities.interestTrend.monthly')}
                  fill="rgba(99,102,241,0.7)"
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      <div>
        <h3>{t('liabilities.detail.relatedTransactions')}</h3>
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

      <div>
        <h3>{t('liabilities.detail.relatedRecurring')}</h3>
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
    </section>
  );
};

export default LiabilityDetailPanel;
