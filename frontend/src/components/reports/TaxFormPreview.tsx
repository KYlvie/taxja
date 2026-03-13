import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import reportService, { TaxFormData, TaxFormField } from '../../services/reportService';
import YearWarning from './YearWarning';
import './TaxFormPreview.css';

/** Section definitions matching official BMF form layout */
const SECTION_CONFIG: Record<string, {
  punkt: string;
  labels: Record<string, string>;
}> = {
  einkuenfte_nichtselbstaendig: {
    punkt: '1',
    labels: { de: 'Eink\u00fcnfte aus nichtselbst\u00e4ndiger Arbeit', en: 'Employment Income', zh: '\u5de5\u8d44\u6536\u5165' },
  },
  einkuenfte_gewerbebetrieb: {
    punkt: '2',
    labels: { de: 'Eink\u00fcnfte aus Gewerbebetrieb', en: 'Business Income', zh: '\u7ecf\u8425\u6240\u5f97' },
  },
  einkuenfte_selbstaendig: {
    punkt: '3',
    labels: { de: 'Eink\u00fcnfte aus selbst\u00e4ndiger Arbeit', en: 'Self-Employment Income', zh: '\u81ea\u7531\u804c\u4e1a\u6536\u5165' },
  },
  einkuenfte_vermietung: {
    punkt: '4',
    labels: { de: 'Eink\u00fcnfte aus Vermietung und Verpachtung', en: 'Rental Income', zh: '\u79df\u8d41\u6536\u5165' },
  },
  einkuenfte_kapital: {
    punkt: '5',
    labels: { de: 'Eink\u00fcnfte aus Kapitalverm\u00f6gen', en: 'Capital Income', zh: '\u8d44\u672c\u6536\u76ca' },
  },
  sonderausgaben: {
    punkt: '6',
    labels: { de: 'Sonderausgaben (\u00a7 18 EStG)', en: 'Special Deductions (\u00a7 18 EStG)', zh: '\u7279\u6b8a\u6263\u9664' },
  },
  werbungskosten: {
    punkt: '7',
    labels: { de: 'Werbungskosten (\u00a7 16 EStG)', en: 'Work-Related Expenses (\u00a7 16 EStG)', zh: '\u5de5\u4f5c\u76f8\u5173\u8d39\u7528' },
  },
  absetzbetraege: {
    punkt: '8',
    labels: { de: 'Absetzbetr\u00e4ge', en: 'Tax Credits', zh: '\u7a0e\u6536\u62b5\u514d' },
  },
  pendler: {
    punkt: '9',
    labels: { de: 'Pendlerpauschale (\u00a7 16 Abs. 1 Z 6 EStG)', en: 'Commuter Allowance', zh: '\u901a\u52e4\u8865\u8d34' },
  },
  ertraege: {
    punkt: '1',
    labels: { de: 'Ertr\u00e4ge (Betriebseinnahmen)', en: 'Revenue (Operating Income)', zh: '\u8425\u4e1a\u6536\u5165' },
  },
  aufwendungen: {
    punkt: '2',
    labels: { de: 'Aufwendungen (Betriebsausgaben)', en: 'Expenses (Operating Costs)', zh: '\u7ecf\u8425\u8d39\u7528' },
  },
  ergebnis: {
    punkt: '3',
    labels: { de: 'Ergebnis und K\u00f6rperschaftsteuer', en: 'Result and Corporate Tax', zh: '\u7ecf\u8425\u6210\u679c\u53ca\u516c\u53f8\u6240\u5f97\u7a0e' },
  },
  ausschuettung: {
    punkt: '4',
    labels: { de: 'Gewinnaussch\u00fcttung (KESt)', en: 'Dividend Distribution (WHT)', zh: '\u5229\u6da6\u5206\u914d' },
  },
};

const TOTAL_KEYS = new Set([
  'total_income', 'gesamtbetrag_einkuenfte', 'corporate_profit',
  'profit_after_koest', 'net_dividend',
]);

const SUMMARY_LABELS: Record<string, Record<string, string>> = {
  employment_income: { de: 'Eink\u00fcnfte nichtselbst\u00e4ndige Arbeit', en: 'Employment income', zh: '\u5de5\u8d44\u6536\u5165' },
  self_employment_income: { de: 'Eink\u00fcnfte selbst\u00e4ndige Arbeit', en: 'Self-employment income', zh: '\u81ea\u7531\u804c\u4e1a\u6536\u5165' },
  gewerbebetrieb_gewinn: { de: 'Gewinn aus Gewerbebetrieb', en: 'Business profit', zh: '\u7ecf\u8425\u5229\u6da6' },
  rental_income: { de: 'Eink\u00fcnfte Vermietung (brutto)', en: 'Rental income (gross)', zh: '\u79df\u8d41\u6536\u5165' },
  vermietung_einkuenfte: { de: 'Eink\u00fcnfte Vermietung (netto)', en: 'Rental income (net)', zh: '\u79df\u8d41\u6536\u5165' },
  rental_by_property: { de: 'Nach Immobilie', en: 'By Property', zh: '\u6309\u7269\u4e1a' },
  property_expenses: { de: 'Immobilienausgaben', en: 'Property Expenses', zh: '\u7269\u4e1a\u652f\u51fa' },
  property_depreciation: { de: 'AfA (Abschreibung)', en: 'Depreciation (AfA)', zh: '\u6298\u65e7 (AfA)' },
  capital_gains: { de: 'Eink\u00fcnfte Kapitalverm\u00f6gen', en: 'Capital income', zh: '\u8d44\u672c\u6536\u76ca' },
  total_income: { de: 'GESAMTBETRAG DER EINK\u00dcNFTE', en: 'TOTAL INCOME', zh: '\u603b\u6536\u5165' },
  total_deductible: { de: 'Abzugsf\u00e4hige Aufwendungen', en: 'Deductible expenses', zh: '\u53ef\u6263\u9664\u652f\u51fa' },
  gesamtbetrag_einkuenfte: { de: 'ZU VERSTEUERNDES EINKOMMEN', en: 'TAXABLE INCOME', zh: '\u5e94\u7a0e\u6240\u5f97' },
  werbungskosten: { de: 'Werbungskosten', en: 'Work-related expenses', zh: '\u5de5\u4f5c\u76f8\u5173\u8d39\u7528' },
  sonderausgaben: { de: 'Sonderausgaben', en: 'Special deductions', zh: '\u7279\u6b8a\u6263\u9664' },
  pendlerpauschale: { de: 'Pendlerpauschale', en: 'Commuter allowance', zh: '\u901a\u52e4\u8865\u8d34' },
  familienbonus: { de: 'Familienbonus Plus', en: 'Family Bonus Plus', zh: '\u5bb6\u5ead\u5956\u91d1Plus' },
  alleinerzieher: { de: 'Alleinverdiener-/Alleinerzieherabsetzbetrag', en: 'Sole earner/single parent credit', zh: '\u5355\u4eb2\u7a0e\u6536\u62b5\u514d' },
  total_revenue: { de: 'Umsatzerl\u00f6se', en: 'Revenue', zh: '\u8425\u4e1a\u6536\u5165' },
  total_expenses: { de: 'Betriebsausgaben gesamt', en: 'Total expenses', zh: '\u603b\u652f\u51fa' },
  corporate_profit: { de: 'Gewinn / Verlust vor Steuern', en: 'Profit/Loss before tax', zh: '\u7a0e\u524d\u5229\u6da6' },
  koest: { de: 'K\u00f6rperschaftsteuer', en: 'Corporate tax', zh: '\u516c\u53f8\u6240\u5f97\u7a0e' },
  profit_after_koest: { de: 'Jahres\u00fcberschuss nach K\u00f6St', en: 'Net profit after corp. tax', zh: '\u7a0e\u540e\u51c0\u5229\u6da6' },
  kest_on_dividend: { de: 'KESt auf Gewinnaussch\u00fcttung', en: 'WHT on dividends', zh: '\u80a1\u606f\u9884\u6263\u7a0e' },
  net_dividend: { de: 'Netto-Aussch\u00fcttung', en: 'Net dividend', zh: '\u51c0\u5206\u7ea2' },
  vat_collected: { de: 'USt eingenommen', en: 'VAT collected', zh: 'VAT\u6536\u5165' },
  vat_paid: { de: 'VSt bezahlt', en: 'VAT paid', zh: 'VAT\u652f\u51fa' },
  vat_balance: { de: 'USt-Zahllast / -Guthaben', en: 'VAT balance', zh: 'VAT\u4f59\u989d' },
};

const TaxFormPreview = () => {
  const { t, i18n } = useTranslation();
  const currentYear = new Date().getFullYear();
  const [taxYear, setTaxYear] = useState(currentYear);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formData, setFormData] = useState<TaxFormData | null>(null);
  const [editedValues, setEditedValues] = useState<Record<string, number>>({});

  const lang = (i18n.language.split('-')[0] || 'de') as 'de' | 'en' | 'zh';

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    setEditedValues({});
    try {
      const data = await reportService.generateTaxForm(taxYear);
      setFormData(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('reports.generationError'));
    } finally {
      setLoading(false);
    }
  };

  const getLabel = (field: TaxFormField) => {
    const key = `label_${lang}` as keyof TaxFormField;
    return (field[key] as string) || field.label_de;
  };

  const getDisclaimer = () => {
    if (!formData) return '';
    const key = `disclaimer_${lang}` as keyof TaxFormData;
    return (formData[key] as string) || formData.disclaimer_de;
  };

  const getFormName = () => {
    if (!formData) return '';
    const key = `form_name_${lang}` as keyof TaxFormData;
    return (formData[key] as string) || formData.form_name_de;
  };

  const handleValueChange = (kz: string, section: string, value: string) => {
    const key = `${kz}_${section}`;
    setEditedValues(prev => ({ ...prev, [key]: parseFloat(value) || 0 }));
  };

  const getFieldValue = (field: TaxFormField) => {
    const key = `${field.kz}_${field.section}`;
    return editedValues[key] !== undefined ? editedValues[key] : field.value;
  };

  const fmt = (n: number) => new Intl.NumberFormat('de-AT', {
    style: 'currency', currency: 'EUR', minimumFractionDigits: 2,
  }).format(n);

  const groupedFields = formData?.fields.reduce((acc, field) => {
    if (!acc[field.section]) acc[field.section] = [];
    acc[field.section].push(field);
    return acc;
  }, {} as Record<string, TaxFormField[]>) || {};

  const getSectionOrder = (): string[] => {
    if (!formData) return [];
    if (formData.form_type === 'L1') {
      return ['absetzbetraege', 'sonderausgaben', 'werbungskosten', 'pendler'];
    }
    if (formData.form_type === 'K1') {
      return ['ertraege', 'aufwendungen', 'ergebnis', 'ausschuettung'];
    }
    return [
      'einkuenfte_nichtselbstaendig', 'einkuenfte_gewerbebetrieb',
      'einkuenfte_selbstaendig', 'einkuenfte_vermietung',
      'einkuenfte_kapital', 'sonderausgaben', 'werbungskosten',
      'absetzbetraege', 'pendler',
    ];
  };

  const getSectionLabel = (section: string) => {
    const cfg = SECTION_CONFIG[section];
    if (!cfg) return section.replace(/_/g, ' ');
    return cfg.labels[lang] || cfg.labels.de;
  };

  const getPunktNr = (section: string) => SECTION_CONFIG[section]?.punkt || '?';

  const getSummaryLabel = (key: string) => {
    const labels = SUMMARY_LABELS[key];
    if (!labels) return key.replace(/_/g, ' ');
    return labels[lang] || labels.de;
  };

  const getSummaryKeys = (): string[] => {
    if (!formData) return [];
    if (formData.form_type === 'L1') {
      return ['employment_income', 'werbungskosten', 'sonderausgaben',
              'pendlerpauschale', 'familienbonus', 'alleinerzieher'];
    }
    if (formData.form_type === 'K1') {
      return ['total_revenue', 'total_expenses', 'corporate_profit',
              'koest', 'profit_after_koest', 'kest_on_dividend',
              'net_dividend', 'vat_collected', 'vat_paid', 'vat_balance'];
    }
    return ['employment_income', 'self_employment_income', 'gewerbebetrieb_gewinn',
            'rental_income', 'vermietung_einkuenfte', 'capital_gains',
            'total_income', 'total_deductible', 'gesamtbetrag_einkuenfte',
            'vat_collected', 'vat_paid', 'vat_balance'];
  };

  const handlePrint = () => window.print();

  const handleDownloadPDF = async () => {
    try {
      const blob = await reportService.downloadTaxFormPDF(taxYear);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `Taxja-${formData?.form_type || 'E1'}-${taxYear}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'PDF download failed');
    }
  };

  const orderedSections = getSectionOrder().filter(s => groupedFields[s]?.length);

  return (
    <div className="tax-form-preview">
      <div className="tf-controls">
        <div className="form-group">
          <label htmlFor="tf-year">{t('reports.taxYear')}</label>
          <select id="tf-year" value={taxYear} onChange={e => setTaxYear(+e.target.value)}>
            {Array.from({ length: 5 }, (_, i) => currentYear - i).map(y => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </div>
        <button className="btn btn-primary" onClick={handleGenerate} disabled={loading}>
          {loading ? t('common.loading') : t('reports.taxForm.generate')}
        </button>
        {formData && (
          <button className="btn btn-secondary" onClick={handlePrint}>
            {'\uD83D\uDDA8\uFE0F'} {t('reports.ea.print')}
          </button>
        )}
        {formData && (
          <button className="btn btn-primary" onClick={handleDownloadPDF}>
            {'\uD83D\uDCE5'} {t('reports.taxForm.downloadPDF')}
          </button>
        )}
      </div>

      <YearWarning taxYear={taxYear} />
      {error && <div className="alert alert-error">{'\u26A0\uFE0F'} {error}</div>}

      {formData && (
        <div className="tf-content" id="tf-print-area">
          <div className="tf-bmf-header">
            <div className="tf-bmf-header-left">
              <h2>Bundesministerium f{'\u00fc'}r Finanzen</h2>
              <div className="tf-bmf-subtitle">
                Republik {'\u00d6'}sterreich {'\u2022'} {getFormName()} {formData.tax_year}
              </div>
            </div>
            <div className="tf-form-code">{formData.form_type}</div>
          </div>

          <div className="tf-personal-info">
            <div className="tf-info-cell">
              <div className="tf-info-label">Steuernummer</div>
              <div className="tf-info-value">{formData.tax_number || 'N/A'}</div>
            </div>
            <div className="tf-info-cell">
              <div className="tf-info-label">Familienname / Firmenname</div>
              <div className="tf-info-value">{formData.user_name}</div>
            </div>
            <div className="tf-info-cell">
              <div className="tf-info-label">Veranlagungsjahr</div>
              <div className="tf-info-value">{formData.tax_year}</div>
            </div>
          </div>
          <div className="tf-generated-note">
            Erstellt am {formData.generated_at} {'\u2022'} Taxja Steuer-Ausf{'\u00fc'}llhilfe
          </div>

          {orderedSections.map(section => (
            <div key={section} className="tf-section">
              <div className="tf-section-header">
                <span className="tf-punkt-nr">Punkt {getPunktNr(section)}</span>
                <span className="tf-section-title">{getSectionLabel(section)}</span>
              </div>
              <div className="tf-fields">
                {groupedFields[section].map((field, i) => (
                  <div key={`${field.kz}-${i}`} className="tf-field">
                    <div className="tf-kz">KZ {field.kz}</div>
                    <div className="tf-label">
                      {getLabel(field)}
                      {field.note_de && (
                        <span className="tf-field-note">{field.note_de}</span>
                      )}
                    </div>
                    <div className="tf-field-value">
                      {field.editable ? (
                        <input
                          type="number"
                          step="0.01"
                          value={getFieldValue(field)}
                          onChange={e => handleValueChange(field.kz, field.section, e.target.value)}
                          className="tf-input"
                          aria-label={`KZ ${field.kz} ${getLabel(field)}`}
                        />
                      ) : (
                        <span className="tf-readonly">{fmt(field.value)}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}

          <div className="tf-summary">
            <h3>{'\u03A3'} {t('reports.taxForm.summary')}</h3>
            <div className="tf-summary-grid">
              {getSummaryKeys()
                .filter(key => {
                  const val = formData.summary[key];
                  return val !== undefined && (val !== 0 || TOTAL_KEYS.has(key));
                })
                .map(key => (
                  <div
                    key={key}
                    className={`tf-summary-item ${TOTAL_KEYS.has(key) ? 'is-total' : ''}`}
                  >
                    <span className="tf-summary-label">{getSummaryLabel(key)}</span>
                    <span className="tf-summary-value">{fmt(formData.summary[key] as number)}</span>
                  </div>
                ))}
            </div>
            
            {/* Property breakdown section */}
            {formData.summary.rental_by_property && Object.keys(formData.summary.rental_by_property).length > 0 && (
              <div className="tf-property-breakdown">
                <h4>{getSummaryLabel('rental_by_property')}</h4>
                <div className="tf-property-list">
                  {Object.entries(formData.summary.rental_by_property).map(([address, amount]) => (
                    <div key={address} className="tf-property-item">
                      <span className="tf-property-address">{address}</span>
                      <span className="tf-property-amount">{fmt(amount as number)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* Property expenses breakdown */}
            {formData.summary.property_expenses && Object.keys(formData.summary.property_expenses).length > 0 && (
              <div className="tf-property-breakdown">
                <h4>{getSummaryLabel('property_expenses')}</h4>
                <div className="tf-property-list">
                  {Object.entries(formData.summary.property_expenses).map(([category, amount]) => (
                    <div key={category} className="tf-property-item">
                      <span className="tf-property-category">{category.replace(/_/g, ' ')}</span>
                      <span className="tf-property-amount">{fmt(amount as number)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* Property depreciation */}
            {formData.summary.property_depreciation && formData.summary.property_depreciation > 0 && (
              <div className="tf-property-breakdown">
                <div className="tf-property-item is-depreciation">
                  <span className="tf-property-label">{getSummaryLabel('property_depreciation')}</span>
                  <span className="tf-property-amount">{fmt(formData.summary.property_depreciation)}</span>
                </div>
              </div>
            )}
          </div>

          <div className="tf-actions">
            <a
              href={formData.finanzonline_url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-primary"
            >
              {'\uD83C\uDFDB\uFE0F'} {t('reports.taxForm.openFinanzOnline')}
            </a>
            <a
              href={formData.form_download_url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-secondary"
            >
              {'\uD83D\uDCC4'} {t('reports.taxForm.downloadForm')}
            </a>
          </div>

          <div className="tf-disclaimer">
            {'\u26A0\uFE0F'} {getDisclaimer()}
          </div>
        </div>
      )}
    </div>
  );
};

export default TaxFormPreview;
