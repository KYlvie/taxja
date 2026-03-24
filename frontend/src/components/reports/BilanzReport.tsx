import { Fragment, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import Select from '../common/Select';
import reportService, { BilanzReport as BilanzData } from '../../services/reportService';
import YearWarning from './YearWarning';
import { getLocaleForLanguage } from '../../utils/locale';
import exportElementToPdf from '../../utils/exportElementToPdf';
import './BilanzReport.css';

const BilanzReport = () => {
  const { t, i18n } = useTranslation();
  const currentYear = new Date().getFullYear();
  const [taxYear, setTaxYear] = useState(currentYear);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<BilanzData | null>(null);
  const reportRef = useRef<HTMLDivElement | null>(null);

  const lang = i18n.language.split('-')[0] || 'de';
  const priorYear = taxYear - 1;

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await reportService.generateBilanzReport(taxYear, lang);
      setReport(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('reports.generationError'));
    } finally {
      setLoading(false);
    }
  };

  const fmtNum = (value: number) =>
    new Intl.NumberFormat(getLocaleForLanguage(i18n.language), {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);

  const fmtCur = (value: number) =>
    new Intl.NumberFormat(getLocaleForLanguage(i18n.language), {
      style: 'currency',
      currency: 'EUR',
      minimumFractionDigits: 2,
    }).format(value);

  const handlePrint = () => window.print();

  const handleDownloadPDF = async () => {
    if (!reportRef.current) {
      return;
    }

    try {
      await exportElementToPdf({
        element: reportRef.current,
        filename: `Taxja-Bilanz-${taxYear}.pdf`,
        orientation: 'landscape',
      });
    } catch (err: any) {
      setError(err.response?.data?.detail || t('reports.generationError'));
    }
  };

  return (
    <div className="bilanz-report">
      <div className="bilanz-controls">
        <div className="form-group">
          <label htmlFor="bilanz-year">{t('reports.taxYear')}</label>
          <Select
            id="bilanz-year"
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
            {loading ? t('common.loading') : t('reports.bilanz.generate')}
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
        <div className="bilanz-content" id="bilanz-print-area" ref={reportRef}>
          <div className="guv-page">
            <div className="guv-page-header">
              <div className="guv-page-title">
                <span className="guv-title-underline">Gewinn- und Verlustrechnung</span>
              </div>
              <div className="guv-company">{report.user_name}</div>
              <div className="guv-period">
                1. Januar {report.tax_year} bis 31. Dezember {report.tax_year}
              </div>
            </div>

            <table className="guv-table">
              <thead>
                <tr>
                  <th className="guv-col-label"></th>
                  <th className="guv-col-amount">
                    {report.tax_year}
                    <br />
                    EUR
                  </th>
                  <th className="guv-col-amount">
                    {priorYear}
                    <br />
                    EUR
                  </th>
                </tr>
              </thead>
              <tbody>
                {report.guv.lines.map((line) => (
                  <Fragment key={line.key}>
                    {line.sub_items.map((subItem) => (
                      <tr key={subItem.key} className="guv-detail-row">
                        <td className="guv-detail-label">{subItem.label}</td>
                        <td className="guv-detail-amount">{fmtNum(subItem.amount)}</td>
                        <td className="guv-detail-amount prior">{fmtNum(subItem.amount_prior)}</td>
                      </tr>
                    ))}
                    <tr className="guv-section-row">
                      <td className="guv-section-label">
                        <span className="guv-nr">{line.nr}</span> {line.label}
                      </td>
                      <td className="guv-section-amount">{fmtNum(line.amount)}</td>
                      <td className="guv-section-amount prior">{fmtNum(line.amount_prior)}</td>
                    </tr>
                  </Fragment>
                ))}
              </tbody>
            </table>

            <table className="guv-summary-lines">
              <tbody>
                <tr className="guv-zwischensumme">
                  <td>{t('reports.bilanz.z6')}</td>
                  <td className="guv-col-amount">{fmtNum(report.guv.betriebsergebnis)}</td>
                  <td className="guv-col-amount prior">{fmtNum(report.guv.betriebsergebnis_prior)}</td>
                </tr>
                <tr className="guv-zwischensumme">
                  <td>{t('reports.bilanz.z9')}</td>
                  <td className="guv-col-amount">{fmtNum(report.guv.ergebnis_vor_steuern)}</td>
                  <td className="guv-col-amount prior">
                    {fmtNum(report.guv.ergebnis_vor_steuern_prior)}
                  </td>
                </tr>
                <tr>
                  <td className="guv-detail-label">{t('reports.bilanz.z10')}</td>
                  <td className="guv-col-amount">{fmtNum(report.guv.steuern)}</td>
                  <td className="guv-col-amount prior">{fmtNum(report.guv.steuern_prior)}</td>
                </tr>
                <tr className="guv-zwischensumme">
                  <td>{t('reports.bilanz.z11')}</td>
                  <td className="guv-col-amount">{fmtNum(report.guv.ergebnis_nach_steuern)}</td>
                  <td className="guv-col-amount prior">
                    {fmtNum(report.guv.ergebnis_nach_steuern_prior)}
                  </td>
                </tr>
                <tr className="guv-final">
                  <td>{t('reports.bilanz.z13')}</td>
                  <td className="guv-col-amount">{fmtNum(report.guv.net_profit)}</td>
                  <td className="guv-col-amount prior">
                    {fmtNum(report.guv.ergebnis_nach_steuern_prior)}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="bilanz-page">
            <div className="bilanz-page-header">
              <div className="bilanz-page-company">{report.user_name}</div>
              <div className="bilanz-page-title">
                <span className="bilanz-title-text">{t('reports.bilanz.balanceSheet')}</span>
              </div>
              <div className="bilanz-page-date">
                {t('reports.bilanz.asOf')} 31.12.{report.tax_year}
              </div>
            </div>

            <div className="balance-grid">
              <div className="balance-side">
                <div className="balance-side-header">
                  <span>{t('reports.bilanz.aktiva')}</span>
                  <span>
                    31.12.{report.tax_year}
                    <br />
                    EUR
                  </span>
                </div>
                {report.bilanz.aktiva.map((group) => (
                  <div key={group.key} className="balance-group">
                    <div className="balance-group-header">{group.label}</div>
                    {group.items.map((item) => (
                      <div key={item.key} className="balance-item">
                        <span>{item.label}</span>
                        <span className="text-right">{fmtNum(item.amount)}</span>
                      </div>
                    ))}
                    <div className="balance-group-total">
                      <span></span>
                      <span>{fmtNum(group.subtotal)}</span>
                    </div>
                  </div>
                ))}
                <div className="balance-grand-total">
                  <span>{t('reports.bilanz.summeAktiva')}</span>
                  <span>{fmtNum(report.bilanz.total_aktiva)}</span>
                </div>
              </div>

              <div className="balance-side">
                <div className="balance-side-header">
                  <span>{t('reports.bilanz.passiva')}</span>
                  <span>
                    31.12.{report.tax_year}
                    <br />
                    EUR
                  </span>
                </div>
                {report.bilanz.passiva.map((group) => (
                  <div key={group.key} className="balance-group">
                    <div className="balance-group-header">{group.label}</div>
                    {group.items.map((item) => (
                      <div key={item.key} className="balance-item">
                        <span>{item.label}</span>
                        <span className="text-right">{fmtNum(item.amount)}</span>
                      </div>
                    ))}
                    <div className="balance-group-total">
                      <span></span>
                      <span>{fmtNum(group.subtotal)}</span>
                    </div>
                  </div>
                ))}
                <div className="balance-grand-total">
                  <span>{t('reports.bilanz.summePassiva')}</span>
                  <span>{fmtNum(report.bilanz.total_passiva)}</span>
                </div>
              </div>
            </div>
          </div>

          {(report.vat_summary.vat_collected > 0 || report.vat_summary.vat_paid > 0) && (
            <div className="vat-summary-box">
              <h4>{t('reports.bilanz.vatSummary')}</h4>
              <div className="vat-row">
                <span>{t('reports.ea.vatCollected')}</span>
                <span>{fmtCur(report.vat_summary.vat_collected)}</span>
              </div>
              <div className="vat-row">
                <span>{t('reports.ea.vatPaid')}</span>
                <span>{fmtCur(report.vat_summary.vat_paid)}</span>
              </div>
              <div className="vat-row vat-balance">
                <span>{t('reports.ea.vatBalance')}</span>
                <span>{fmtCur(report.vat_summary.vat_balance)}</span>
              </div>
            </div>
          )}

          <div className="bilanz-disclaimer">{t('reports.bilanz.disclaimer')}</div>
        </div>
      )}
    </div>
  );
};

export default BilanzReport;
