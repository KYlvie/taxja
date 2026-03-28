import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Property } from '../../types/property';
import api from '../../services/api';
import { getErrorMessage } from '../../services/propertyService';
import Select from '../common/Select';
import DateInput from '../common/DateInput';
import { getLocaleForLanguage } from '../../utils/locale';
import './PropertyReports.css';

interface PropertyReportsProps {
  property: Property;
}

interface IncomeStatementData {
  property: {
    id: string;
    address: string;
    purchase_date: string;
    building_value: number;
  };
  period: {
    start_date: string;
    end_date: string;
  };
  income: {
    rental_income: number;
    total_income: number;
  };
  expenses: {
    by_category: { [key: string]: number };
    total_expenses: number;
  };
  net_income: number;
}

interface DepreciationScheduleData {
  property: {
    id: string;
    address: string;
    purchase_date: string;
    building_value: number;
    depreciation_rate: number;
  };
  schedule: Array<{
    year: number;
    annual_depreciation: number;
    accumulated_depreciation: number;
    remaining_value: number;
  }>;
  summary: {
    total_years: number;
    total_depreciation: number;
    remaining_value: number;
  };
}

const PropertyReports = ({ property }: PropertyReportsProps) => {
  const { t, i18n } = useTranslation();
  const [activeReport, setActiveReport] = useState<'income' | 'depreciation' | null>(null);
  const [incomeStatementData, setIncomeStatementData] = useState<IncomeStatementData | null>(null);
  const [depreciationScheduleData, setDepreciationScheduleData] = useState<DepreciationScheduleData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exportFormat, setExportFormat] = useState<'csv' | 'pdf'>('csv');

  // Date range for income statement
  const currentYear = new Date().getFullYear();
  const [startDate, setStartDate] = useState(`${currentYear}-01-01`);
  const [endDate, setEndDate] = useState(new Date().toISOString().split('T')[0]);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat(getLocaleForLanguage(i18n.language), {
      style: 'currency',
      currency: 'EUR',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString(getLocaleForLanguage(i18n.language), {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    });
  };

  const formatPercentage = (rate: number) => {
    return `${(rate * 100).toFixed(2)}%`;
  };

  const handleGenerateIncomeStatement = async () => {
    setIsLoading(true);
    setError(null);
    setActiveReport('income');

    try {
      const response = await api.get(
        `/properties/${property.id}/reports/income-statement`,
        { params: { start_date: startDate, end_date: endDate } }
      );
      setIncomeStatementData(response.data);
    } catch (err: unknown) {
      const detail = getErrorMessage(err, 'Unknown error');
      console.error('Error generating income statement:', detail, err);
      setError(`${t('properties.reports.errorGenerating')}: ${detail}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleGenerateDepreciationSchedule = async () => {
    setIsLoading(true);
    setError(null);
    setActiveReport('depreciation');

    try {
      const response = await api.get(
        `/properties/${property.id}/reports/depreciation-schedule`
      );
      setDepreciationScheduleData(response.data);
    } catch (err: unknown) {
      const detail = getErrorMessage(err, 'Unknown error');
      console.error('Error generating depreciation schedule:', detail, err);
      setError(`${t('properties.reports.errorGenerating')}: ${detail}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDownload = () => {
    if (exportFormat === 'csv') {
      if (activeReport === 'income' && incomeStatementData) {
        downloadIncomeStatementCSV(incomeStatementData);
      } else if (activeReport === 'depreciation' && depreciationScheduleData) {
        downloadDepreciationScheduleCSV(depreciationScheduleData);
      }
    } else if (exportFormat === 'pdf') {
      if (activeReport === 'income' && incomeStatementData) {
        downloadIncomeStatementPDF(incomeStatementData);
      } else if (activeReport === 'depreciation' && depreciationScheduleData) {
        downloadDepreciationSchedulePDF(depreciationScheduleData);
      }
    }
  };

  const downloadIncomeStatementCSV = (data: IncomeStatementData) => {
    const rows = [
      [t('properties.reports.incomeStatement'), data.property.address],
      [t('properties.reports.period'), `${formatDate(data.period.start_date)} - ${formatDate(data.period.end_date)}`],
      [],
      [t('properties.reports.income')],
      [t('properties.rentalIncome'), data.income.rental_income.toFixed(2)],
      [t('properties.reports.totalIncome', 'Total Income'), data.income.total_income.toFixed(2)],
      [],
      [t('properties.reports.expensesByCategory', 'Expenses by Category')],
      ...Object.entries(data.expenses.by_category).map(([category, amount]) => [
        t(`transactions.categories.${category}`, category),
        amount.toFixed(2),
      ]),
      [t('properties.reports.totalExpenses'), data.expenses.total_expenses.toFixed(2)],
      [],
      [t('properties.netIncome'), data.net_income.toFixed(2)],
    ];

    const csvContent = rows.map((row) => row.join(',')).join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `income-statement-${property.id}-${startDate}-${endDate}.csv`;
    link.click();
  };

  const downloadDepreciationScheduleCSV = (data: DepreciationScheduleData) => {
    const rows = [
      [t('properties.reports.depreciationSchedule'), data.property.address],
      [t('properties.buildingValue'), data.property.building_value.toFixed(2)],
      [t('properties.depreciationRate'), (data.property.depreciation_rate * 100).toFixed(2) + '%'],
      [],
      [t('properties.reports.year'), t('properties.reports.annualDepreciation'), t('properties.accumulatedDepreciation'), t('properties.remainingValue')],
      ...data.schedule.map((item) => [
        item.year.toString(),
        item.annual_depreciation.toFixed(2),
        item.accumulated_depreciation.toFixed(2),
        item.remaining_value.toFixed(2),
      ]),
      [],
      [t('properties.reports.summary')],
      [t('properties.reports.totalYears'), data.summary.total_years.toString()],
      [t('properties.reports.totalDepreciation'), data.summary.total_depreciation.toFixed(2)],
      [t('properties.remainingValue'), data.summary.remaining_value.toFixed(2)],
    ];

    const csvContent = rows.map((row) => row.join(',')).join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `depreciation-schedule-${property.id}.csv`;
    link.click();
  };

  const downloadIncomeStatementPDF = (data: IncomeStatementData) => {
    // Generate simple HTML for PDF printing
    const htmlContent = `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="utf-8">
        <title>${t('properties.reports.incomeStatement')} - ${data.property.address}</title>
        <style>
          body { font-family: Arial, sans-serif; margin: 40px; }
          h1 { color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }
          h2 { color: #666; margin-top: 30px; }
          table { width: 100%; border-collapse: collapse; margin: 20px 0; }
          th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
          th { background-color: #f5f5f5; font-weight: bold; }
          .amount { text-align: right; }
          .positive { color: #4CAF50; }
          .negative { color: #f44336; }
          .total { font-weight: bold; background-color: #f9f9f9; }
          .info { margin: 20px 0; }
          .info-row { display: flex; justify-content: space-between; padding: 8px 0; }
        </style>
      </head>
      <body>
        <h1>${t('properties.reports.incomeStatement')}</h1>
        <div class="info">
          <div class="info-row"><strong>${t('properties.address')}:</strong> ${data.property.address}</div>
          <div class="info-row"><strong>${t('properties.reports.period')}:</strong> ${formatDate(data.period.start_date)} - ${formatDate(data.period.end_date)}</div>
        </div>

        <h2>${t('properties.reports.income')}</h2>
        <table>
          <tr>
            <td>${t('properties.rentalIncome')}</td>
            <td class="amount positive">${formatCurrency(data.income.rental_income)}</td>
          </tr>
          <tr class="total">
            <td>${t('properties.reports.totalIncome', 'Total Income')}</td>
            <td class="amount">${formatCurrency(data.income.total_income)}</td>
          </tr>
        </table>

        <h2>${t('properties.reports.expenses')}</h2>
        <table>
          ${Object.entries(data.expenses.by_category).map(([category, amount]) => `
            <tr>
              <td>${t(`transactions.categories.${category}`, category)}</td>
              <td class="amount">${formatCurrency(amount)}</td>
            </tr>
          `).join('')}
          <tr class="total">
            <td>${t('properties.reports.totalExpenses')}</td>
            <td class="amount negative">${formatCurrency(data.expenses.total_expenses)}</td>
          </tr>
        </table>

        <h2>${t('properties.reports.summary')}</h2>
        <table>
          <tr class="total">
            <td><strong>${t('properties.netIncome')}</strong></td>
            <td class="amount ${data.net_income >= 0 ? 'positive' : 'negative'}">
              <strong>${formatCurrency(data.net_income)}</strong>
            </td>
          </tr>
        </table>
      </body>
      </html>
    `;

    // Open in new window for printing
    const printWindow = window.open('', '_blank');
    if (printWindow) {
      printWindow.document.write(htmlContent);
      printWindow.document.close();
      printWindow.focus();
      setTimeout(() => {
        printWindow.print();
      }, 250);
    }
  };

  const downloadDepreciationSchedulePDF = (data: DepreciationScheduleData) => {
    // Generate simple HTML for PDF printing
    const htmlContent = `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="utf-8">
        <title>${t('properties.reports.depreciationSchedule')} - ${data.property.address}</title>
        <style>
          body { font-family: Arial, sans-serif; margin: 40px; }
          h1 { color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }
          h2 { color: #666; margin-top: 30px; }
          table { width: 100%; border-collapse: collapse; margin: 20px 0; }
          th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
          th { background-color: #f5f5f5; font-weight: bold; }
          .amount { text-align: right; }
          .total { font-weight: bold; background-color: #f9f9f9; }
          .info { margin: 20px 0; }
          .info-row { display: flex; justify-content: space-between; padding: 8px 0; }
        </style>
      </head>
      <body>
        <h1>${t('properties.reports.depreciationSchedule')}</h1>
        <div class="info">
          <div class="info-row"><strong>${t('properties.address')}:</strong> ${data.property.address}</div>
          <div class="info-row"><strong>${t('properties.buildingValue')}:</strong> ${formatCurrency(data.property.building_value)}</div>
          <div class="info-row"><strong>${t('properties.depreciationRate')}:</strong> ${formatPercentage(data.property.depreciation_rate)}</div>
        </div>

        <h2>${t('properties.reports.annualSchedule', 'Annual Schedule')}</h2>
        <table>
          <thead>
            <tr>
              <th>${t('properties.reports.year')}</th>
              <th class="amount">${t('properties.reports.annualDepreciation')}</th>
              <th class="amount">${t('properties.accumulatedDepreciation')}</th>
              <th class="amount">${t('properties.remainingValue')}</th>
            </tr>
          </thead>
          <tbody>
            ${data.schedule.map((item) => `
              <tr>
                <td>${item.year}</td>
                <td class="amount">${formatCurrency(item.annual_depreciation)}</td>
                <td class="amount">${formatCurrency(item.accumulated_depreciation)}</td>
                <td class="amount">${formatCurrency(item.remaining_value)}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>

        <h2>${t('properties.reports.summary')}</h2>
        <table>
          <tr>
            <td>${t('properties.reports.totalYears')}</td>
            <td class="amount">${data.summary.total_years}</td>
          </tr>
          <tr>
            <td>${t('properties.reports.totalDepreciation')}</td>
            <td class="amount">${formatCurrency(data.summary.total_depreciation)}</td>
          </tr>
          <tr class="total">
            <td><strong>${t('properties.remainingValue')}</strong></td>
            <td class="amount"><strong>${formatCurrency(data.summary.remaining_value)}</strong></td>
          </tr>
        </table>
      </body>
      </html>
    `;

    // Open in new window for printing
    const printWindow = window.open('', '_blank');
    if (printWindow) {
      printWindow.document.write(htmlContent);
      printWindow.document.close();
      printWindow.focus();
      setTimeout(() => {
        printWindow.print();
      }, 250);
    }
  };

  const isRealEstate = !property.asset_type || property.asset_type === 'real_estate';

  return (
    <div className="property-reports">
      <div className="reports-header">
        <h2>{isRealEstate ? t('properties.reports.title') : t('properties.reports.assetTitle', 'Asset Report')}</h2>
        <p className="reports-description">
          {isRealEstate
            ? t('properties.reports.description')
            : t('properties.reports.assetDescription', 'Generate depreciation schedule and asset value reports.')}
        </p>
      </div>

      {/* Report Generation Buttons */}
      <div className="report-controls">
        {isRealEstate && <div className="report-option">
          <div className="report-option-header">
            <h3>{t('properties.reports.incomeStatement')}</h3>
            <p>{t('properties.reports.incomeStatementDescription')}</p>
          </div>

          <div className="date-range-selector">
            <div className="date-input-group">
              <label htmlFor="start-date">{t('properties.reports.startDate')}</label>
              <DateInput
                id="start-date"
                value={startDate}
                onChange={(val) => setStartDate(val)}
                max={endDate}
                locale={getLocaleForLanguage(i18n.language)}
                todayLabel={String(t('common.today', 'Today'))}
              />
            </div>
            <div className="date-input-group">
              <label htmlFor="end-date">{t('properties.reports.endDate')}</label>
              <DateInput
                id="end-date"
                value={endDate}
                onChange={(val) => setEndDate(val)}
                min={startDate}
                max={new Date().toISOString().split('T')[0]}
                locale={getLocaleForLanguage(i18n.language)}
                todayLabel={String(t('common.today', 'Today'))}
              />
            </div>
          </div>

          <button
            className="btn btn-primary"
            onClick={handleGenerateIncomeStatement}
            disabled={isLoading}
          >
            {isLoading && activeReport === 'income' ? (
              <>
                <span className="spinner"></span>
                {t('properties.reports.generating')}
              </>
            ) : (
              <>📊 {t('properties.reports.generateIncomeStatement')}</>
            )}
          </button>
        </div>}

        <div className="report-option">
          <div className="report-option-header">
            <h3>{t('properties.reports.depreciationSchedule')}</h3>
            <p>{t('properties.reports.depreciationScheduleDescription')}</p>
          </div>

          <button
            className="btn btn-primary"
            onClick={handleGenerateDepreciationSchedule}
            disabled={isLoading}
          >
            {isLoading && activeReport === 'depreciation' ? (
              <>
                <span className="spinner"></span>
                {t('properties.reports.generating')}
              </>
            ) : (
              <>📈 {t('properties.reports.generateDepreciationSchedule')}</>
            )}
          </button>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="error-message">
          <span className="error-icon">⚠️</span>
          {error}
        </div>
      )}

      {/* Income Statement Preview (real estate only) */}
      {isRealEstate && incomeStatementData && activeReport === 'income' && (
        <div className="report-preview">
          <div className="report-preview-header">
            <h3>{t('properties.reports.incomeStatement')}</h3>
            <div className="download-controls">
              <div className="format-selector">
                <label htmlFor="export-format">{t('properties.reports.format')}</label>
                <Select id="export-format" value={exportFormat}
                  onChange={v => setExportFormat(v as 'csv' | 'pdf')} size="sm"
                  options={[{ value: 'csv', label: 'CSV' }, { value: 'pdf', label: 'PDF' }]} />
              </div>
              <button className="btn btn-secondary" onClick={handleDownload}>
                💾 {t('properties.reports.download')} {exportFormat.toUpperCase()}
              </button>
            </div>
          </div>

          <div className="report-content">
            <div className="report-section">
              <h4>{t('properties.reports.propertyInfo')}</h4>
              <div className="info-row">
                <span className="label">{t('properties.address')}</span>
                <span className="value">{incomeStatementData.property.address}</span>
              </div>
              <div className="info-row">
                <span className="label">{t('properties.reports.period')}</span>
                <span className="value">
                  {formatDate(incomeStatementData.period.start_date)} -{' '}
                  {formatDate(incomeStatementData.period.end_date)}
                </span>
              </div>
            </div>

            <div className="report-section">
              <h4>{t('properties.reports.income')}</h4>
              <div className="info-row highlight">
                <span className="label">{t('properties.rentalIncome')}</span>
                <span className="value positive">
                  {formatCurrency(incomeStatementData.income.rental_income)}
                </span>
              </div>
            </div>

            <div className="report-section">
              <h4>{t('properties.reports.expenses')}</h4>
              {Object.entries(incomeStatementData.expenses.by_category).map(
                ([category, amount]) => (
                  <div key={category} className="info-row">
                    <span className="label">{t(`transactions.categories.${category}`)}</span>
                    <span className="value">{formatCurrency(amount)}</span>
                  </div>
                )
              )}
              <div className="info-row highlight">
                <span className="label">{t('properties.reports.totalExpenses')}</span>
                <span className="value negative">
                  {formatCurrency(incomeStatementData.expenses.total_expenses)}
                </span>
              </div>
            </div>

            <div className="report-section summary">
              <div className="info-row highlight-strong">
                <span className="label">{t('properties.netIncome')}</span>
                <span
                  className={`value ${
                    incomeStatementData.net_income >= 0 ? 'positive' : 'negative'
                  }`}
                >
                  {formatCurrency(incomeStatementData.net_income)}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Depreciation Schedule Preview */}
      {depreciationScheduleData && activeReport === 'depreciation' && (
        <div className="report-preview">
          <div className="report-preview-header">
            <h3>{t('properties.reports.depreciationSchedule')}</h3>
            <div className="download-controls">
              <div className="format-selector">
                <label htmlFor="export-format-dep">{t('properties.reports.format')}</label>
                <Select id="export-format-dep" value={exportFormat}
                  onChange={v => setExportFormat(v as 'csv' | 'pdf')} size="sm"
                  options={[{ value: 'csv', label: 'CSV' }, { value: 'pdf', label: 'PDF' }]} />
              </div>
              <button className="btn btn-secondary" onClick={handleDownload}>
                💾 {t('properties.reports.download')} {exportFormat.toUpperCase()}
              </button>
            </div>
          </div>

          <div className="report-content">
            <div className="report-section">
              <h4>{isRealEstate ? t('properties.reports.propertyInfo') : t('properties.reports.assetInfo', 'Asset Information')}</h4>
              <div className="info-row">
                <span className="label">{isRealEstate ? t('properties.address') : t('common.name', 'Name')}</span>
                <span className="value">{depreciationScheduleData.property.address}</span>
              </div>
              <div className="info-row">
                <span className="label">{isRealEstate ? t('properties.buildingValue') : t('properties.purchasePrice', 'Purchase price')}</span>
                <span className="value">
                  {formatCurrency(depreciationScheduleData.property.building_value)}
                </span>
              </div>
              <div className="info-row">
                <span className="label">{t('properties.depreciationRate')}</span>
                <span className="value">
                  {formatPercentage(depreciationScheduleData.property.depreciation_rate)}
                </span>
              </div>
            </div>

            <div className="report-section">
              <h4>{t('properties.reports.schedule')}</h4>
              <div className="schedule-table">
                <table>
                  <thead>
                    <tr>
                      <th>{t('properties.reports.year')}</th>
                      <th>{t('properties.reports.annualDepreciation')}</th>
                      <th>{t('properties.accumulatedDepreciation')}</th>
                      <th>{t('properties.remainingValue')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {depreciationScheduleData.schedule.map((item) => (
                      <tr key={item.year}>
                        <td>{item.year}</td>
                        <td>{formatCurrency(item.annual_depreciation)}</td>
                        <td>{formatCurrency(item.accumulated_depreciation)}</td>
                        <td>{formatCurrency(item.remaining_value)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="report-section summary">
              <h4>{t('properties.reports.summary')}</h4>
              <div className="info-row">
                <span className="label">{t('properties.reports.totalYears')}</span>
                <span className="value">{depreciationScheduleData.summary.total_years}</span>
              </div>
              <div className="info-row highlight">
                <span className="label">{t('properties.reports.totalDepreciation')}</span>
                <span className="value">
                  {formatCurrency(depreciationScheduleData.summary.total_depreciation)}
                </span>
              </div>
              <div className="info-row highlight">
                <span className="label">{t('properties.remainingValue')}</span>
                <span className="value">
                  {formatCurrency(depreciationScheduleData.summary.remaining_value)}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PropertyReports;
