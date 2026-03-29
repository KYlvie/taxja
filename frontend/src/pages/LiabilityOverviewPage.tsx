import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import SubpageBackLink from '../components/common/SubpageBackLink';
import AssetLiabilityOverview from '../components/liabilities/AssetLiabilityOverview';
import LiabilityDetailPanel from '../components/liabilities/LiabilityDetail';
import LiabilityList from '../components/liabilities/LiabilityList';
import { liabilityService } from '../services/liabilityService';
import { LiabilityDetail, LiabilityRecord, LiabilitySummary } from '../types/liability';
import './TaxToolsPage.css';
import './LiabilitiesPage.css';

const formatCurrency = (value: number) =>
  new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value || 0);

const LIABILITY_TYPE_ORDER = [
  'property_loan',
  'business_loan',
  'owner_loan',
  'family_loan',
  'other_liability',
] as const;

const LiabilityOverviewPage = () => {
  const { t } = useTranslation();
  const [summary, setSummary] = useState<LiabilitySummary | null>(null);
  const [liabilities, setLiabilities] = useState<LiabilityRecord[]>([]);
  const [selectedLiabilityId, setSelectedLiabilityId] = useState<number | null>(null);
  const [selectedLiability, setSelectedLiability] = useState<LiabilityDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const activeLiabilities = useMemo(
    () => liabilities.filter((liability) => liability.is_active),
    [liabilities],
  );
  const taxRelevantLiabilities = useMemo(
    () => activeLiabilities.filter((liability) => liability.tax_relevant),
    [activeLiabilities],
  );
  const taxRelevantOutstandingBalance = useMemo(
    () =>
      taxRelevantLiabilities.reduce(
        (sum, liability) => sum + (liability.outstanding_balance || 0),
        0,
      ),
    [taxRelevantLiabilities],
  );
  const taxNeutralLiabilities = useMemo(
    () => activeLiabilities.filter((liability) => !liability.tax_relevant),
    [activeLiabilities],
  );
  const topLiabilities = useMemo(
    () =>
      [...activeLiabilities]
        .sort((a, b) => b.outstanding_balance - a.outstanding_balance)
        .slice(0, 3),
    [activeLiabilities],
  );
  const liabilityTypeBreakdown = useMemo(
    () =>
      LIABILITY_TYPE_ORDER.map((liabilityType) => {
        const matching = activeLiabilities.filter(
          (liability) => liability.liability_type === liabilityType,
        );
        return {
          liabilityType,
          count: matching.length,
          balance: matching.reduce(
            (sum, liability) => sum + (liability.outstanding_balance || 0),
            0,
          ),
        };
      }),
    [activeLiabilities],
  );
  const lenderBreakdown = useMemo(() => {
    const grouped = new Map<
      string,
      { lenderName: string; count: number; balance: number; monthlyPayment: number }
    >();

    activeLiabilities.forEach((liability) => {
      const lenderName =
        liability.lender_name?.trim() ||
        t('liabilities.overview.unknownLender', 'Unknown lender');
      const current = grouped.get(lenderName) ?? {
        lenderName,
        count: 0,
        balance: 0,
        monthlyPayment: 0,
      };
      current.count += 1;
      current.balance += liability.outstanding_balance || 0;
      current.monthlyPayment += liability.monthly_payment || 0;
      grouped.set(lenderName, current);
    });

    return [...grouped.values()]
      .sort((a, b) => b.balance - a.balance)
      .slice(0, 5);
  }, [activeLiabilities, t]);

  const refreshSelectedLiability = useCallback(async (id: number) => {
    setLoadingDetail(true);
    try {
      const detail = await liabilityService.get(id);
      setSelectedLiability(detail);
    } catch {
      setSelectedLiability(null);
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const [summaryData, listData] = await Promise.all([
          liabilityService.getSummary(),
          liabilityService.list(true),
        ]);
        setSummary(summaryData);
        setLiabilities(listData.items);
        const nextSelectedId = listData.items.find((item) => item.is_active)?.id ?? listData.items[0]?.id ?? null;
        setSelectedLiabilityId(nextSelectedId);
        if (nextSelectedId) {
          await refreshSelectedLiability(nextSelectedId);
        } else {
          setSelectedLiability(null);
        }
      } catch {
        setSummary(null);
        setLiabilities([]);
        setSelectedLiability(null);
        setSelectedLiabilityId(null);
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [refreshSelectedLiability]);

  const handleSelectLiability = useCallback(
    (id: number) => {
      setSelectedLiabilityId(id);
      void refreshSelectedLiability(id);
    },
    [refreshSelectedLiability],
  );

  return (
    <div className="tax-tools-page">
      <div className="tax-tools-header">
        <SubpageBackLink to="/liabilities" label={t('common.back', 'Back')} />
        <h1>{t('liabilities.overview.pageTitle', 'Liability Overview')}</h1>
        <p>
          {t(
            'liabilities.overview.pageSubtitle',
            'Track balances, repayment progress, and the liabilities currently attached to your tax reporting.',
          )}
        </p>
      </div>

      <div className="tax-tools-content">
        <AssetLiabilityOverview summary={summary} loading={loading} />

        <div className="liability-panel">
          <div className="liability-group-header">
            <div>
              <h2>{t('liabilities.manage.listTitle', 'Liabilities')}</h2>
              <p className="liability-hint">
                {t(
                  'liabilities.overview.portfolioSubtitle',
                  'All tracked loans, financing arrangements, and other liabilities in one place.',
                )}
              </p>
            </div>
            <span className="liability-count-badge">
              {activeLiabilities.length || liabilities.length}
            </span>
          </div>
          <LiabilityList
            liabilities={liabilities}
            selectedId={selectedLiabilityId}
            onSelect={handleSelectLiability}
          />
        </div>

        <div className="liability-panel">
          <div className="liability-group-header">
            <div>
              <h2>{t('liabilities.overview.mixTitle', 'Liability Mix')}</h2>
              <p className="liability-hint">
                {t(
                  'liabilities.overview.mixSubtitle',
                  'Break down balances by financing type so you can quickly see how debt is distributed across the portfolio.',
                )}
              </p>
            </div>
          </div>

          <div className="liability-overview-grid">
            {liabilityTypeBreakdown.map((item) => (
              <article key={item.liabilityType} className="liability-metric-card">
                <span className="liability-metric-label">
                  {t(`liabilities.type.${item.liabilityType}`, item.liabilityType)}
                </span>
                <strong className="liability-metric-value">{item.count}</strong>
                <span className="liability-metric-note">
                  {formatCurrency(item.balance)}
                </span>
              </article>
            ))}
          </div>

          {lenderBreakdown.length ? (
            <div className="liability-table-view liability-table-view--always">
              <table className="liability-table">
                <thead>
                  <tr>
                    <th>{t('liabilities.fields.lenderName', 'Lender')}</th>
                    <th>{t('liabilities.overview.exposureCount', 'Open facilities')}</th>
                    <th>{t('liabilities.fields.outstandingBalance', 'Outstanding balance')}</th>
                    <th>{t('liabilities.fields.monthlyPayment', 'Monthly payment')}</th>
                  </tr>
                </thead>
                <tbody>
                  {lenderBreakdown.map((lender) => (
                    <tr key={lender.lenderName}>
                      <td>{lender.lenderName}</td>
                      <td>{lender.count}</td>
                      <td className="amount">{formatCurrency(lender.balance)}</td>
                      <td className="amount">{formatCurrency(lender.monthlyPayment)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="liability-empty">
              {t(
                'liabilities.overview.mixEmpty',
                'No liability mix is available yet. Add your first loan or borrowing to populate this section.',
              )}
            </div>
          )}
        </div>

        <div className="liability-panel">
          <div className="liability-group-header">
            <div>
              <h2>{t('liabilities.overview.taxFocusTitle', 'Tax-Relevant Liabilities')}</h2>
              <p className="liability-hint">
                {t(
                  'liabilities.overview.taxFocusSubtitle',
                  'Separate liabilities that feed tax reporting from financing that stays outside deductible workflows.',
                )}
              </p>
            </div>
          </div>

          <div className="liability-overview-grid">
            <article className="liability-metric-card">
              <span className="liability-metric-label">
                {t('liabilities.overview.taxRelevantCount', 'Tax-relevant liabilities')}
              </span>
              <strong className="liability-metric-value">{taxRelevantLiabilities.length}</strong>
              <span className="liability-metric-note">
                {t(
                  'liabilities.overview.taxRelevantCountNote',
                  'Liabilities currently feeding interest deduction and reporting workflows.',
                )}
              </span>
            </article>
            <article className="liability-metric-card">
              <span className="liability-metric-label">
                {t('liabilities.overview.taxRelevantBalance', 'Tax-relevant balance')}
              </span>
              <strong className="liability-metric-value">
                {formatCurrency(taxRelevantOutstandingBalance)}
              </strong>
              <span className="liability-metric-note">
                {t(
                  'liabilities.overview.taxRelevantBalanceNote',
                  'Outstanding balance across liabilities that are currently tax relevant.',
                )}
              </span>
            </article>
            <article className="liability-metric-card">
              <span className="liability-metric-label">
                {t('liabilities.overview.taxNeutralCount', 'Non-tax liabilities')}
              </span>
              <strong className="liability-metric-value">{taxNeutralLiabilities.length}</strong>
              <span className="liability-metric-note">
                {t(
                  'liabilities.overview.taxNeutralCountNote',
                  'Financing that remains visible in net worth but stays outside deductible flows.',
                )}
              </span>
            </article>
          </div>

          {topLiabilities.length ? (
            <div className="liability-table-view liability-table-view--always">
              <table className="liability-table">
                <thead>
                  <tr>
                    <th>{t('liabilities.fields.displayName', 'Display name')}</th>
                    <th>{t('liabilities.fields.liabilityType', 'Liability type')}</th>
                    <th>{t('liabilities.fields.outstandingBalance', 'Outstanding balance')}</th>
                    <th>{t('liabilities.fields.monthlyPayment', 'Monthly payment')}</th>
                    <th>{t('liabilities.fields.taxRelevant', 'Tax relevant')}</th>
                  </tr>
                </thead>
                <tbody>
                  {topLiabilities.map((liability) => (
                    <tr key={liability.id}>
                      <td className="liability-name-cell">
                        <div className="liability-name-content">
                          <strong>{liability.display_name}</strong>
                          <span>{liability.lender_name}</span>
                        </div>
                      </td>
                      <td>
                        <span className="liability-type-badge">
                          {t(
                            `liabilities.type.${liability.liability_type}`,
                            liability.liability_type,
                          )}
                        </span>
                      </td>
                      <td className="amount">{formatCurrency(liability.outstanding_balance)}</td>
                      <td className="amount">
                        {liability.monthly_payment == null
                          ? t('common.notAvailable', 'N/A')
                          : formatCurrency(liability.monthly_payment)}
                      </td>
                      <td>
                        <span
                          className={`liability-tax-chip ${
                            liability.tax_relevant ? 'is-tax-relevant' : 'is-tax-neutral'
                          }`}
                        >
                          {liability.tax_relevant
                            ? t('common.yes', 'Yes')
                            : t('common.no', 'No')}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="liability-empty">
              {t(
                'liabilities.overview.taxFocusEmpty',
                'No liabilities on file yet. Add financing or upload contract-backed debt to populate this section.',
              )}
            </div>
          )}
        </div>

        <div className="liability-panel">
          <div className="liability-group-header">
            <div>
              <h2>{t('liabilities.overview.reportTitle', 'Individual Liability Report')}</h2>
              <p className="liability-hint">
                {t(
                  'liabilities.overview.reportSubtitle',
                  'Inspect repayment progress, interest exposure, and linked tax records for each liability.',
                )}
              </p>
            </div>
          </div>
          <LiabilityDetailPanel
            liability={selectedLiability}
            loading={loadingDetail}
            onEdit={() => {}}
            onDeactivate={() => {}}
            showActions={false}
          />
        </div>
      </div>
    </div>
  );
};

export default LiabilityOverviewPage;
