import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { LiabilitySummary } from '../../types/liability';

type AssetLiabilityOverviewProps = {
  summary: LiabilitySummary | null;
  loading?: boolean;
};

const formatCurrency = (value: number) =>
  new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value || 0);

const AssetLiabilityOverview = ({ summary, loading = false }: AssetLiabilityOverviewProps) => {
  const { t } = useTranslation();

  const metrics = useMemo(() => {
    if (!summary) {
      return [];
    }

    return [
      {
        label: t('liabilities.summary.totalAssets', 'Total assets'),
        value: formatCurrency(summary.total_assets),
        note: t('liabilities.summary.totalAssetsNote', 'Pure asset-side carrying value'),
      },
      {
        label: t('liabilities.summary.totalLiabilities', 'Total liabilities'),
        value: formatCurrency(summary.total_liabilities),
        note: t('liabilities.summary.totalLiabilitiesNote', 'Open balances across all active liabilities'),
      },
      {
        label: t('liabilities.summary.netWorth', 'Net worth'),
        value: formatCurrency(summary.net_worth),
        note: t('liabilities.summary.netWorthNote', 'Assets minus liabilities'),
      },
      {
        label: t('liabilities.summary.activeLiabilities', 'Active liabilities'),
        value: String(summary.active_liability_count || 0),
        note: t('liabilities.summary.activeLiabilitiesNote', 'Loans and borrowings currently tracked'),
      },
      {
        label: t('liabilities.summary.monthlyDebtService', 'Monthly debt service'),
        value: formatCurrency(summary.monthly_debt_service),
        note: t('liabilities.summary.monthlyDebtServiceNote', 'Scheduled repayments currently on file'),
      },
      {
        label: t('liabilities.summary.annualDeductibleInterest', 'Annual deductible interest'),
        value: formatCurrency(summary.annual_deductible_interest),
        note: t('liabilities.summary.annualDeductibleInterestNote', 'Tax-relevant interest recorded in transactions'),
      },
    ];
  }, [summary, t]);

  if (loading) {
    return (
      <section className="liability-panel card">
        <h2>{t('liabilities.overview.title', 'Asset-liability overview')}</h2>
        <p className="liability-hint">{t('common.loading', 'Loading...')}</p>
      </section>
    );
  }

  if (!summary) {
    return (
      <section className="liability-panel card">
        <h2>{t('liabilities.overview.title', 'Asset-liability overview')}</h2>
        <div className="liability-empty">
          {t(
            'liabilities.overview.empty',
            'No summary is available yet. Add liabilities or properties to populate the overview.',
          )}
        </div>
      </section>
    );
  }

  return (
    <section className="liability-panel card">
      <h2>{t('liabilities.overview.title', 'Asset-liability overview')}</h2>
      <div className="liability-overview-balance">
        <article className="liability-highlight-card">
          <span>{t('liabilities.overview.assetsVsLiabilities', 'Balance snapshot')}</span>
          <strong>{formatCurrency(summary.net_worth)}</strong>
          <p>
            {t(
              'liabilities.overview.assetsVsLiabilitiesHint',
              'This view combines your current asset carrying values with all tracked liabilities.',
            )}
          </p>
        </article>
        <article className="liability-highlight-card">
          <span>{t('liabilities.overview.taxFilter', 'Tax filter')}</span>
          <strong>{formatCurrency(summary.annual_deductible_interest)}</strong>
          <p>
            {t(
              'liabilities.overview.taxFilterHint',
              'Only tax-relevant liabilities flow into tax deduction workflows. Everything still remains available for full reporting.',
            )}
          </p>
        </article>
      </div>

      <div className="liability-overview-grid">
        {metrics.map((metric) => (
          <article key={metric.label} className="liability-metric-card">
            <span className="liability-metric-label">{metric.label}</span>
            <strong className="liability-metric-value">{metric.value}</strong>
            <span className="liability-metric-note">{metric.note}</span>
          </article>
        ))}
      </div>
    </section>
  );
};

export default AssetLiabilityOverview;
