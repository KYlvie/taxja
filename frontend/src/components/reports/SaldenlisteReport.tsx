import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import Select from '../common/Select';
import reportService, { SaldenlisteReport as SaldenlisteData } from '../../services/reportService';
import YearWarning from './YearWarning';
import { getApiErrorMessage, getFeatureGatePlan } from '../../utils/apiError';
import { getLocaleForLanguage } from '../../utils/locale';
import exportElementToPdf from '../../utils/exportElementToPdf';
import './SaldenlisteReport.css';

const SaldenlisteReport = () => {
  const { t, i18n } = useTranslation();
  const currentYear = new Date().getFullYear();
  const [taxYear, setTaxYear] = useState(currentYear);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<SaldenlisteData | null>(null);
  const [collapsedGroups, setCollapsedGroups] = useState<Set<number>>(new Set());
  const reportRef = useRef<HTMLDivElement | null>(null);

  const lang = i18n.language.split('-')[0] || 'de';

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await reportService.generateSaldenliste(taxYear, lang);
      setReport(data);
      setCollapsedGroups(new Set());
    } catch (err: any) {
      const gatePlan = getFeatureGatePlan(err);
      if (gatePlan) {
        setError(t('subscription.featureRequiresPlan', { plan: gatePlan.toUpperCase() }));
      } else {
        setError(getApiErrorMessage(err, t('reports.generationError')));
      }
    } finally {
      setLoading(false);
    }
  };

  const fmt = (value: number) =>
    new Intl.NumberFormat(getLocaleForLanguage(i18n.language), {
      style: 'currency',
      currency: 'EUR',
      minimumFractionDigits: 2,
    }).format(value);

  const fmtPct = (value: number | null) => {
    if (value === null || value === undefined) {
      return '—';
    }
    return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`;
  };

  const pctClass = (value: number | null) => {
    if (value === null || value === undefined) {
      return '';
    }
    return value >= 0 ? 'positive' : 'negative';
  };

  const toggleGroup = (kontenklasse: number) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(kontenklasse)) {
        next.delete(kontenklasse);
      } else {
        next.add(kontenklasse);
      }
      return next;
    });
  };

  const handlePrint = () => window.print();

  const handleDownloadPDF = async () => {
    if (!reportRef.current) {
      return;
    }

    try {
      await exportElementToPdf({
        element: reportRef.current,
        filename: `Taxja-Saldenliste-${taxYear}.pdf`,
        orientation: 'landscape',
      });
    } catch (err: any) {
      const gatePlan = getFeatureGatePlan(err);
      if (gatePlan) {
        setError(t('subscription.featureRequiresPlan', { plan: gatePlan.toUpperCase() }));
      } else {
        setError(getApiErrorMessage(err, t('reports.generationError')));
      }
    }
  };

  return (
    <div className="saldenliste-report">
      <div className="saldenliste-controls">
        <div className="form-group">
          <label htmlFor="saldenliste-year">{t('reports.taxYear')}</label>
          <Select
            id="saldenliste-year"
            value={String(taxYear)}
            onChange={(value) => setTaxYear(Number(value))}
            options={Array.from({ length: 5 }, (_, index) => ({
              value: String(currentYear - index),
              label: String(currentYear - index),
            }))}
            size="sm"
          />
        </div>

        {!report ? (
          <button className="btn btn-primary" onClick={handleGenerate} disabled={loading}>
            {loading ? t('common.loading') : t('reports.saldenliste.generate')}
          </button>
        ) : (
          <>
            <button className="btn btn-secondary" onClick={handlePrint}>
              {t('reports.ea.print')}
            </button>
            <button className="btn btn-primary" onClick={handleDownloadPDF}>
              {t('reports.ea.downloadPDF')}
            </button>
          </>
        )}
      </div>

      <YearWarning taxYear={taxYear} />
      {error && <div className="alert alert-error">{error}</div>}

      {report && (
        <div className="saldenliste-content" id="saldenliste-print-area" ref={reportRef}>
          <div className="saldenliste-header">
            <h2>
              {t('reports.saldenliste.title')} {report.tax_year}
            </h2>
            <div className="saldenliste-meta">
              <span>{report.user_name}</span>
              <span>
                {t('reports.ea.generated')}: {report.generated_at}
              </span>
            </div>
          </div>

          {report.groups.map((group) => {
            const isCollapsed = collapsedGroups.has(group.kontenklasse);

            return (
              <div key={group.kontenklasse} className="saldenliste-group">
                <div
                  className="saldenliste-group-header"
                  onClick={() => toggleGroup(group.kontenklasse)}
                >
                  <span>
                    <span className={`toggle-icon${isCollapsed ? ' collapsed' : ''}`}>▼</span>{' '}
                    {group.kontenklasse} – {group.label}
                  </span>
                  <span>{fmt(group.subtotal_current)}</span>
                </div>

                {!isCollapsed && (
                  <table className="saldenliste-table">
                    <thead>
                      <tr>
                        <th>{t('reports.saldenliste.konto')}</th>
                        <th>{t('reports.saldenliste.bezeichnung')}</th>
                        <th className="text-right">{t('reports.saldenliste.saldoAktuell')}</th>
                        <th className="text-right">{t('reports.saldenliste.saldoVorjahr')}</th>
                        <th className="text-right">{t('reports.saldenliste.abweichung')}</th>
                        <th className="text-right">{t('reports.saldenliste.abweichungPct')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {group.accounts.map((account) => (
                        <tr key={account.konto}>
                          <td className="konto-nr">{account.konto}</td>
                          <td>{account.label}</td>
                          <td className="text-right">{fmt(account.current_saldo)}</td>
                          <td className="text-right">{fmt(account.prior_saldo)}</td>
                          <td className="text-right">{fmt(account.deviation_abs)}</td>
                          <td className={`text-right ${pctClass(account.deviation_pct)}`}>
                            {fmtPct(account.deviation_pct)}
                          </td>
                        </tr>
                      ))}
                      <tr className="subtotal-row">
                        <td></td>
                        <td>{t('reports.saldenliste.subtotal')}</td>
                        <td className="text-right">{fmt(group.subtotal_current)}</td>
                        <td className="text-right">{fmt(group.subtotal_prior)}</td>
                        <td className="text-right">{fmt(group.subtotal_deviation_abs)}</td>
                        <td className={`text-right ${pctClass(group.subtotal_deviation_pct)}`}>
                          {fmtPct(group.subtotal_deviation_pct)}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                )}
              </div>
            );
          })}

          <div className="summary-box">
            <h3>{t('reports.saldenliste.title')}</h3>
            {([
              ['aktiva', t('reports.saldenliste.aktiva')],
              ['passiva', t('reports.saldenliste.passiva')],
              ['ertrag', t('reports.saldenliste.ertrag')],
              ['aufwand', t('reports.saldenliste.aufwand')],
            ] as const).map(([key, label]) => (
              <div key={key} className="summary-row">
                <span>{label}</span>
                <div className="summary-values">
                  <span>{fmt((report.summary as any)[`${key}_current`])}</span>
                  <span className="summary-label-sub">
                    {t('reports.saldenliste.saldoVorjahr')}:{' '}
                    {fmt((report.summary as any)[`${key}_prior`])}
                  </span>
                </div>
              </div>
            ))}
            <div className="summary-row total">
              <span>{t('reports.saldenliste.gewinnVerlust')}</span>
              <div className="summary-values">
                <span
                  className={
                    report.summary.gewinn_verlust_current >= 0 ? 'positive' : 'negative'
                  }
                >
                  {fmt(report.summary.gewinn_verlust_current)}
                </span>
                <span className="summary-label-sub">
                  {t('reports.saldenliste.saldoVorjahr')}:{' '}
                  {fmt(report.summary.gewinn_verlust_prior)}
                </span>
              </div>
            </div>
          </div>

          <div className="saldenliste-disclaimer">{t('reports.saldenliste.disclaimer')}</div>
        </div>
      )}
    </div>
  );
};

export default SaldenlisteReport;
