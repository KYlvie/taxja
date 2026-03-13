import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import reportService, { EAReport as EAReportData } from '../../services/reportService';
import YearWarning from './YearWarning';
import './EAReport.css';

const EAReport = () => {
  const { t, i18n } = useTranslation();
  const currentYear = new Date().getFullYear();
  const [taxYear, setTaxYear] = useState(currentYear);
  const [loading, setLoading] = useState(false);
  const [reclassifying, setReclassifying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<EAReportData | null>(null);

  const lang = i18n.language.split('-')[0] || 'de';

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await reportService.generateEAReport(taxYear, lang);
      setReport(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('reports.generationError'));
    } finally {
      setLoading(false);
    }
  };

  const handleReclassify = async () => {
    setReclassifying(true);
    setError(null);
    try {
      await reportService.reclassifyTransactions(taxYear);
      // Re-generate report after reclassification
      const data = await reportService.generateEAReport(taxYear, lang);
      setReport(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Reclassification failed');
    } finally {
      setReclassifying(false);
    }
  };

  const fmt = (n: number) => new Intl.NumberFormat('de-AT', {
    style: 'currency', currency: 'EUR', minimumFractionDigits: 2,
  }).format(n);

  const handlePrint = () => window.print();

  const handleDownloadPDF = async () => {
    try {
      const blob = await reportService.downloadEAReportPDF(taxYear, lang);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `Taxja-EA-Rechnung-${taxYear}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'PDF download failed');
    }
  };

  return (
    <div className="ea-report">
      <div className="ea-controls">
        <div className="form-group">
          <label htmlFor="ea-year">{t('reports.taxYear')}</label>
          <select id="ea-year" value={taxYear} onChange={e => setTaxYear(+e.target.value)}>
            {Array.from({ length: 5 }, (_, i) => currentYear - i).map(y => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </div>
        <button className="btn btn-primary" onClick={handleGenerate} disabled={loading}>
          {loading ? t('common.loading') : t('reports.ea.generate')}
        </button>
        {report && (
          <button className="btn btn-secondary" onClick={handlePrint}>
            🖨️ {t('reports.ea.print')}
          </button>
        )}
        {report && (
          <button className="btn btn-primary" onClick={handleDownloadPDF}>
            📥 {t('reports.ea.downloadPDF')}
          </button>
        )}
        <button
          className="btn btn-secondary"
          onClick={handleReclassify}
          disabled={reclassifying}
          title={t('reports.ea.reclassifyHint', 'Re-run classification and deductibility checks on all transactions')}
        >
          {reclassifying ? '⏳...' : '🔄'} {t('reports.ea.reclassify', 'Reclassify')}
        </button>
      </div>

      <YearWarning taxYear={taxYear} />
      {error && <div className="alert alert-error">⚠️ {error}</div>}

      {report && (
        <div className="ea-report-content" id="ea-print-area">
          <div className="ea-header">
            <h2>Einnahmen-Ausgaben-Rechnung {report.tax_year}</h2>
            <div className="ea-meta">
              <span>{report.user_name}</span>
              {report.tax_number && <span>StNr: {report.tax_number}</span>}
              <span>{t('reports.ea.generated')}: {report.generated_at}</span>
            </div>
          </div>

          {/* Income sections */}
          <div className="ea-section">
            <h3 className="ea-section-title income-title">
              {t('reports.ea.income')}
            </h3>
            {report.income_sections.length === 0 ? (
              <p className="ea-empty">{t('reports.ea.noIncome')}</p>
            ) : (
              report.income_sections.map(section => (
                <div key={section.key} className="ea-group">
                  <div className="ea-group-header">
                    <span className="ea-group-label">{t(`reports.ea.sections.${section.key}`, section.label)}</span>
                    <span className="ea-group-subtotal">{fmt(section.subtotal)}</span>
                  </div>
                  <table className="ea-table">
                    <thead>
                      <tr>
                        <th>{t('reports.ea.date')}</th>
                        <th>{t('reports.ea.description')}</th>
                        <th className="text-right">{t('reports.ea.amount')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {section.items.map((item, i) => (
                        <tr key={i}>
                          <td className="ea-date">{item.date}</td>
                          <td className="ea-desc">{item.description}</td>
                          <td className="text-right">{fmt(item.amount)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))
            )}
            <div className="ea-total income-total">
              <span>{t('reports.ea.totalIncome')}</span>
              <span>{fmt(report.summary.total_income)}</span>
            </div>
          </div>

          {/* Expense sections */}
          <div className="ea-section">
            <h3 className="ea-section-title expense-title">
              {t('reports.ea.expenses')}
            </h3>
            {report.expense_sections.length === 0 ? (
              <p className="ea-empty">{t('reports.ea.noExpenses')}</p>
            ) : (
              report.expense_sections.map(section => (
                <div key={section.key} className="ea-group">
                  <div className="ea-group-header">
                    <span className="ea-group-label">{t(`reports.ea.sections.${section.key}`, section.label)}</span>
                    <span className="ea-group-subtotal">{fmt(section.subtotal)}</span>
                  </div>
                  <table className="ea-table">
                    <thead>
                      <tr>
                        <th>{t('reports.ea.date')}</th>
                        <th>{t('reports.ea.description')}</th>
                        <th className="text-right">{t('reports.ea.amount')}</th>
                        <th className="text-center">{t('reports.ea.deductible')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {section.items.map((item, i) => (
                        <tr key={i} className={item.is_deductible ? '' : 'non-deductible'}>
                          <td className="ea-date">{item.date}</td>
                          <td className="ea-desc">{item.description}</td>
                          <td className="text-right">{fmt(item.amount)}</td>
                          <td className="text-center">{item.is_deductible ? '✓' : '✗'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))
            )}
            <div className="ea-total expense-total">
              <span>{t('reports.ea.totalExpenses')}</span>
              <span>{fmt(report.summary.total_expenses)}</span>
            </div>
            <div className="ea-total deductible-total">
              <span>{t('reports.ea.totalDeductible')}</span>
              <span>{fmt(report.summary.total_deductible)}</span>
            </div>
          </div>

          {/* Summary / Betriebsergebnis */}
          <div className="ea-summary-box">
            <div className="ea-summary-row">
              <span>{t('reports.ea.totalIncome')}</span>
              <span className="positive">{fmt(report.summary.total_income)}</span>
            </div>
            <div className="ea-summary-row">
              <span>{t('reports.ea.totalExpenses')}</span>
              <span className="negative">- {fmt(report.summary.total_expenses)}</span>
            </div>
            <div className="ea-summary-row ea-result">
              <span>{t('reports.ea.betriebsergebnis')}</span>
              <span className={report.summary.betriebsergebnis >= 0 ? 'positive' : 'negative'}>
                {fmt(report.summary.betriebsergebnis)}
              </span>
            </div>
            {(report.summary.total_vat_collected > 0 || report.summary.total_vat_paid > 0) && (
              <>
                <div className="ea-summary-divider" />
                <div className="ea-summary-row">
                  <span>{t('reports.ea.vatCollected')}</span>
                  <span>{fmt(report.summary.total_vat_collected)}</span>
                </div>
                <div className="ea-summary-row">
                  <span>{t('reports.ea.vatPaid')}</span>
                  <span>{fmt(report.summary.total_vat_paid)}</span>
                </div>
                <div className="ea-summary-row">
                  <span>{t('reports.ea.vatBalance')}</span>
                  <span>{fmt(report.summary.vat_balance)}</span>
                </div>
              </>
            )}
          </div>

          <div className="ea-disclaimer">
            ⚠️ {t('reports.ea.disclaimer')}
          </div>
        </div>
      )}
    </div>
  );
};

export default EAReport;
