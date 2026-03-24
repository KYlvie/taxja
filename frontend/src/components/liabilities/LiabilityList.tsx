import { Eye } from 'lucide-react';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { LiabilityRecord, LiabilityType } from '../../types/liability';
import { getLocaleForLanguage } from '../../utils/locale';

type LiabilityListProps = {
  liabilities: LiabilityRecord[];
  selectedId?: number | null;
  onSelect: (id: number) => void;
};

const formatCurrency = (value: number, language: string) =>
  new Intl.NumberFormat(getLocaleForLanguage(language), {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value || 0);

const formatDate = (value: string, language: string) => {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleDateString(getLocaleForLanguage(language), {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
};

const LIABILITY_TYPE_ORDER: LiabilityType[] = [
  'property_loan',
  'business_loan',
  'owner_loan',
  'family_loan',
  'other_liability',
];

const LiabilityList = ({ liabilities, selectedId, onSelect }: LiabilityListProps) => {
  const { t, i18n } = useTranslation();
  const language = i18n?.language || 'en';

  const sortedLiabilities = useMemo(() => {
    const order = new Map<LiabilityType, number>(LIABILITY_TYPE_ORDER.map((type, index) => [type, index]));
    return [...liabilities].sort((a, b) => {
      if (a.is_active !== b.is_active) {
        return a.is_active ? -1 : 1;
      }
      const typeDelta = (order.get(a.liability_type) ?? 99) - (order.get(b.liability_type) ?? 99);
      if (typeDelta !== 0) {
        return typeDelta;
      }
      return a.display_name.localeCompare(b.display_name);
    });
  }, [liabilities]);

  if (!liabilities.length) {
    return (
      <section className="liability-panel card">
        <h2>{t('liabilities.manage.listTitle', 'Liabilities')}</h2>
        <div className="liability-empty">
          {t(
            'liabilities.manage.empty',
            'No liabilities tracked yet. Add your first loan or other liability to complete the debt side of your reporting.',
          )}
        </div>
      </section>
    );
  }

  return (
    <section className="liability-panel card">
      <h2>{t('liabilities.manage.listTitle', 'Liabilities')}</h2>
      <div className="liability-cards">
        {sortedLiabilities.map((liability) => {
          const principal = liability.principal_amount || 0;
          const repaid = principal > 0
            ? Math.max(0, Math.min(principal, principal - liability.outstanding_balance))
            : 0;
          const pct = principal > 0 ? Math.round((repaid / principal) * 100) : 0;

          return (
            <button
              key={liability.id}
              type="button"
              className={`liability-list-card ${selectedId === liability.id ? 'is-selected' : ''}`}
              onClick={() => onSelect(liability.id)}
            >
              <div className="liability-list-card-header">
                <div>
                  <strong>{liability.display_name}</strong>
                  <span>{liability.lender_name}</span>
                </div>
                <span className={`liability-status-badge ${liability.is_active ? 'is-active' : 'is-inactive'}`}>
                  {liability.is_active
                    ? t('common.active', 'Active')
                    : t('common.inactive', 'Inactive')}
                </span>
              </div>

              <div className="liability-list-card-body">
                <div className="liability-list-card-metric">
                  <small>{t('liabilities.fields.liabilityType', 'Liability type')}</small>
                  <strong>{t(`liabilities.type.${liability.liability_type}`, liability.liability_type)}</strong>
                </div>
                <div className="liability-list-card-metric">
                  <small>{t('liabilities.fields.startDate', 'Start date')}</small>
                  <strong>{formatDate(liability.start_date, language)}</strong>
                </div>
                <div className="liability-list-card-metric">
                  <small>{t('liabilities.fields.outstandingBalance', 'Outstanding balance')}</small>
                  <strong>{formatCurrency(liability.outstanding_balance, language)}</strong>
                </div>
                <div className="liability-list-card-metric">
                  <small>{t('liabilities.fields.monthlyPayment', 'Monthly payment')}</small>
                  <strong>
                    {liability.monthly_payment == null
                      ? t('common.notAvailable', 'N/A')
                      : formatCurrency(liability.monthly_payment, language)}
                  </strong>
                </div>
              </div>

              <div className="liability-list-card-progress">
                <div className="liability-progress-bar">
                  <div
                    className="liability-progress-bar-fill"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className="liability-progress-label">{pct}% {t('liabilities.progress.repaid', 'Repaid')}</span>
              </div>

              <div className="liability-list-card-footer">
                <span className={`liability-tax-chip ${liability.tax_relevant ? 'is-tax-relevant' : 'is-tax-neutral'}`}>
                  {liability.tax_relevant
                    ? t('common.yes', 'Yes')
                    : t('common.no', 'No')}
                </span>
                <span>{t(`liabilities.reportCategory.${liability.report_category}`, liability.report_category)}</span>
              </div>
            </button>
          );
        })}
      </div>

      <div className="liability-table-view">
        <table className="liability-table">
          <thead>
            <tr>
              <th>{t('liabilities.fields.displayName', 'Display name')}</th>
              <th>{t('liabilities.fields.liabilityType', 'Liability type')}</th>
              <th>{t('liabilities.fields.startDate', 'Start date')}</th>
              <th>{t('liabilities.fields.outstandingBalance', 'Outstanding balance')}</th>
              <th>{t('liabilities.fields.monthlyPayment', 'Monthly payment')}</th>
              <th>{t('liabilities.fields.taxRelevant', 'Tax relevant')}</th>
              <th>{t('common.status', 'Status')}</th>
              <th>{t('common.actions', 'Actions')}</th>
            </tr>
          </thead>
          <tbody>
            {sortedLiabilities.map((liability) => (
              <tr
                key={liability.id}
                className={`liability-row ${selectedId === liability.id ? 'is-selected' : ''}`}
                onClick={() => onSelect(liability.id)}
              >
                <td className="liability-name-cell">
                  <div className="liability-name-content">
                    <strong>{liability.display_name}</strong>
                    <span>{liability.lender_name}</span>
                  </div>
                </td>
                <td>
                  <span className="liability-type-badge">
                    {t(`liabilities.type.${liability.liability_type}`, liability.liability_type)}
                  </span>
                </td>
                <td>{formatDate(liability.start_date, language)}</td>
                <td className="amount">{formatCurrency(liability.outstanding_balance, language)}</td>
                <td className="amount">
                  {liability.monthly_payment == null
                    ? t('common.notAvailable', 'N/A')
                    : formatCurrency(liability.monthly_payment, language)}
                </td>
                <td>
                  <span className={`liability-tax-chip ${liability.tax_relevant ? 'is-tax-relevant' : 'is-tax-neutral'}`}>
                    {liability.tax_relevant ? t('common.yes', 'Yes') : t('common.no', 'No')}
                  </span>
                </td>
                <td>
                  <span className={`liability-status-badge ${liability.is_active ? 'is-active' : 'is-inactive'}`}>
                    {liability.is_active
                      ? t('common.active', 'Active')
                      : t('common.inactive', 'Inactive')}
                  </span>
                </td>
                <td className="actions">
                  <button
                    type="button"
                    className="btn-icon"
                    onClick={(event) => {
                      event.stopPropagation();
                      onSelect(liability.id);
                    }}
                    title={t('common.view', 'View')}
                  >
                    <Eye size={15} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
};

export default LiabilityList;
