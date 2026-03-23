import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import Select from '../common/Select';
import reportService, { SaldenlisteReport as SaldenlisteData } from '../../services/reportService';
import YearWarning from './YearWarning';
import { getLocaleForLanguage } from '../../utils/locale';
import './SaldenlisteReport.css';

const SaldenlisteReport = () => {
  const { t, i18n } = useTranslation();
  const currentYear = new Date().getFullYear();
  const [taxYear, setTaxYear] = useState(currentYear);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<SaldenlisteData | null>(null);
  const [collapsedGroups, setCollapsedGroups] = useState<Set<number>>(new Set());

  const lang = i18n.language.split('-')[0] || 'de';

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await reportService.generateSaldenliste(taxYear, lang);
      setReport(data);
      setCollapsedGroups(new Set());
    } catch (err: any) {
      setError(err.response?.data?.detail || t('reports.generationError'));
    } finally {
      setLoading(false);
    }
  };

  const fmt = (n: number) =>
    new Intl.NumberFormat(getLocaleForLanguage(i18n.language), {
      style: 'currency', currency: 'EUR', minimumFractionDigits: 2,
    }).format(n);

  const fmtPct = (pct: number | null) => {
    if (pct === null || pct === undefined) return '—';
    return `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%`;
  };

  const pctClass = (pct: number | null) => {
    if (pct === null || pct === undefined) return '';
    return pct >= 0 ? 'positive' : 'negative';
  };

  const toggleGroup = (kk: number) => {
    setCollapsedGroups(prev => {
      const next = new Set(prev);
      if (next.has(kk)) next.delete(kk);
      else next.add(kk);
      return next;
    });
  };

  const handlePrint = () => window.print();

  return (
    <div className="saldenliste-report">
      <div className="saldenliste-controls">
        <div className="form-group">
          <label htmlFor="saldenliste-year">{t('reports.taxYear')}</label>
          <Select id="saldenliste-year" value={String(taxYear)} onChange={v => setTaxYear(Number(v))}
            options={Array.from({ length: 5 }, (_, i) => ({ value: String(currentYear - i), label: String(currentYear - i) }))} size="sm" />
        </div>
        <button className="btn btn-primary" onClick={handleGenerate} disabled={loading}>
          {loading ? t('common.loading') : t('reports.saldenliste.generate')}
        </button>
        {report && (
          <button className="btn btn-secondary" onClick={handlePrint}>
            🖨️ {t('reports.ea.print')}
          </button>
        )}
      </div>

      <YearWarning taxYear={taxYear} />
      {error && <div className="alert alert-error">⚠️ {error}</div>}

      {report && (
        <div className="saldenliste-content" id="saldenliste-print-area">
          <div className="saldenliste-header">
            <h2>{t('reports.saldenliste.title')} {report.tax_year}</h2>
            <div className="saldenliste-meta">
              <span>{report.user_name}</span>
              <span>{t('reports.ea.generated')}: {report.generated_at}</span>
            </div>
          </div>

          {report.groups.map(group => {
            const isCollapsed = collapsedGroups.has(group.kontenklasse);
            return (
              <div key={group.kontenklasse} className="saldenliste-group">
                <div
                  className="saldenliste-group-header"
                  onClick={() => toggleGroup(group.kontenklasse)}
                >
                  <span>
                    <span className={`toggle-icon${isCollapsed ? ' collapsed' : ''}`}>▼</span>
                    {' '}{group.kontenklasse} – {group.label}
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
                      {group.accounts.map(acc => (
                        <tr key={acc.konto}>
                          <td className="konto-nr">{acc.konto}</td>
                          <td>{acc.label}</td>
                          <td className="text-right">{fmt(acc.current_saldo)}</td>
                          <td className="text-right">{fmt(acc.prior_saldo)}</td>
                          <td className="text-right">{fmt(acc.deviation_abs)}</td>
                          <td className={`text-right ${pctClass(acc.deviation_pct)}`}>
                            {fmtPct(acc.deviation_pct)}
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
                    {t('reports.saldenliste.saldoVorjahr')}: {fmt((report.summary as any)[`${key}_prior`])}
                  </span>
                </div>
              </div>
            ))}
            <div className="summary-row total">
              <span>{t('reports.saldenliste.gewinnVerlust')}</span>
              <div className="summary-values">
                <span className={report.summary.gewinn_verlust_current >= 0 ? 'positive' : 'negative'}>
                  {fmt(report.summary.gewinn_verlust_current)}
                </span>
                <span className="summary-label-sub">
                  {t('reports.saldenliste.saldoVorjahr')}: {fmt(report.summary.gewinn_verlust_prior)}
                </span>
              </div>
            </div>
          </div>

          <div className="saldenliste-disclaimer">
            ⚠️ {t('reports.saldenliste.disclaimer')}
          </div>
        </div>
      )}
    </div>
  );
};

export default SaldenlisteReport;
