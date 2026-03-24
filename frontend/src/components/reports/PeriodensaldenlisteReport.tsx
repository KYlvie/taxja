import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import Select from '../common/Select';
import reportService, {
  PeriodensaldenlisteReport as PeriodensaldenlisteData,
} from '../../services/reportService';
import YearWarning from './YearWarning';
import { getLocaleForLanguage } from '../../utils/locale';
import exportElementToPdf from '../../utils/exportElementToPdf';
import './PeriodensaldenlisteReport.css';

const MONTH_KEYS = Array.from({ length: 12 }, (_, index) => `reports.periodensaldenliste.month${index + 1}`);

const PeriodensaldenlisteReport = () => {
  const { t, i18n } = useTranslation();
  const currentYear = new Date().getFullYear();
  const [taxYear, setTaxYear] = useState(currentYear);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<PeriodensaldenlisteData | null>(null);
  const [collapsedGroups, setCollapsedGroups] = useState<Set<number>>(new Set());
  const reportRef = useRef<HTMLDivElement | null>(null);

  const lang = i18n.language.split('-')[0] || 'de';

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await reportService.generatePeriodensaldenliste(taxYear, lang);
      setReport(data);
      setCollapsedGroups(new Set());
    } catch (err: any) {
      (() => {
        const detail = err.response?.data?.detail;
        if (detail && typeof detail === 'object' && (detail.error === 'feature_not_available' || detail.error === 'insufficient_plan')) {
          setError(t('subscription.featureRequiresPlan', { plan: (detail.required_plan || 'Pro').toUpperCase() }));
        } else {
          setError(typeof detail === 'string' ? detail : t('reports.generationError'));
        }
      })();
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
        filename: `Taxja-Periodensaldenliste-${taxYear}.pdf`,
        orientation: 'landscape',
      });
    } catch (err: any) {
      (() => {
        const detail = err.response?.data?.detail;
        if (detail && typeof detail === 'object' && (detail.error === 'feature_not_available' || detail.error === 'insufficient_plan')) {
          setError(t('subscription.featureRequiresPlan', { plan: (detail.required_plan || 'Pro').toUpperCase() }));
        } else {
          setError(typeof detail === 'string' ? detail : t('reports.generationError'));
        }
      })();
    }
  };

  return (
    <div className="periodensaldenliste-report">
      <div className="periodensaldenliste-controls">
        <div className="form-group">
          <label htmlFor="periodensaldenliste-year">{t('reports.taxYear')}</label>
          <Select
            id="periodensaldenliste-year"
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
            {loading ? t('common.loading') : t('reports.periodensaldenliste.generate')}
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
        <div
          className="periodensaldenliste-content"
          id="periodensaldenliste-print-area"
          ref={reportRef}
        >
          <div className="periodensaldenliste-header">
            <h2>
              {t('reports.periodensaldenliste.title')} {report.tax_year}
            </h2>
            <div className="periodensaldenliste-meta">
              <span>{report.user_name}</span>
              <span>
                {t('reports.ea.generated')}: {report.generated_at}
              </span>
            </div>
          </div>

          {report.groups.map((group) => {
            const isCollapsed = collapsedGroups.has(group.kontenklasse);

            return (
              <div key={group.kontenklasse} className="periodensaldenliste-group">
                <div
                  className="periodensaldenliste-group-header"
                  onClick={() => toggleGroup(group.kontenklasse)}
                >
                  <span>
                    <span className={`toggle-icon${isCollapsed ? ' collapsed' : ''}`}>▼</span>{' '}
                    {group.kontenklasse} – {group.label}
                  </span>
                  <span>{fmt(group.subtotal_gesamt)}</span>
                </div>

                {!isCollapsed && (
                  <div className="table-scroll-wrapper">
                    <table className="periodensaldenliste-table">
                      <thead>
                        <tr>
                          <th className="col-konto">{t('reports.periodensaldenliste.konto')}</th>
                          <th className="col-bezeichnung">
                            {t('reports.periodensaldenliste.bezeichnung')}
                          </th>
                          {MONTH_KEYS.map((key, index) => (
                            <th key={index} className="col-month text-right">
                              {t(key)}
                            </th>
                          ))}
                          <th className="col-gesamt text-right">
                            {t('reports.periodensaldenliste.gesamt')}
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {group.accounts.map((account) => (
                          <tr key={account.konto}>
                            <td className="konto-nr">{account.konto}</td>
                            <td className="col-bezeichnung">{account.label}</td>
                            {account.months.map((monthValue, index) => (
                              <td key={index} className="col-month text-right">
                                {fmt(monthValue)}
                              </td>
                            ))}
                            <td className="col-gesamt text-right">{fmt(account.gesamt)}</td>
                          </tr>
                        ))}
                        <tr className="subtotal-row">
                          <td></td>
                          <td>{t('reports.periodensaldenliste.subtotal')}</td>
                          {group.subtotal_months.map((monthValue, index) => (
                            <td key={index} className="col-month text-right">
                              {fmt(monthValue)}
                            </td>
                          ))}
                          <td className="col-gesamt text-right">{fmt(group.subtotal_gesamt)}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            );
          })}

          <div className="summary-box">
            <h3>{t('reports.periodensaldenliste.title')}</h3>
            {([
              ['aktiva', t('reports.periodensaldenliste.aktiva')],
              ['passiva', t('reports.periodensaldenliste.passiva')],
              ['ertrag', t('reports.periodensaldenliste.ertrag')],
              ['aufwand', t('reports.periodensaldenliste.aufwand')],
            ] as const).map(([key, label]) => (
              <div key={key} className="summary-row">
                <span className="summary-label">{label}</span>
                <div className="summary-months">
                  {((report.summary as any)[`${key}_months`] as number[]).map(
                    (monthValue: number, index: number) => (
                      <span key={index} className="summary-month-val">
                        {fmt(monthValue)}
                      </span>
                    ),
                  )}
                  <span className="summary-gesamt-val">
                    {fmt((report.summary as any)[`${key}_gesamt`])}
                  </span>
                </div>
              </div>
            ))}
            <div className="summary-row total">
              <span className="summary-label">{t('reports.periodensaldenliste.gewinnVerlust')}</span>
              <div className="summary-months">
                {report.summary.gewinn_verlust_months.map((monthValue, index) => (
                  <span
                    key={index}
                    className={`summary-month-val ${monthValue >= 0 ? 'positive' : 'negative'}`}
                  >
                    {fmt(monthValue)}
                  </span>
                ))}
                <span
                  className={`summary-gesamt-val ${
                    report.summary.gewinn_verlust_gesamt >= 0 ? 'positive' : 'negative'
                  }`}
                >
                  {fmt(report.summary.gewinn_verlust_gesamt)}
                </span>
              </div>
            </div>
          </div>

          <div className="periodensaldenliste-disclaimer">
            {t('reports.periodensaldenliste.disclaimer')}
          </div>
        </div>
      )}
    </div>
  );
};

export default PeriodensaldenlisteReport;
