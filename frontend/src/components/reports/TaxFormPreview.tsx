import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import reportService, { TaxFormData, TaxFormField, EligibleForm } from '../../services/reportService';
import YearWarning from './YearWarning';
import './TaxFormPreview.css';

/** Section definitions matching official BMF form layout */
const SECTION_PUNKT: Record<string, string> = {
  einkuenfte_nichtselbstaendig: '1',
  einkuenfte_gewerbebetrieb: '2',
  einkuenfte_selbstaendig: '3',
  einkuenfte_vermietung: '4',
  einkuenfte_kapital: '5',
  sonderausgaben: '6',
  werbungskosten: '7',
  absetzbetraege: '8',
  pendler: '9',
  ertraege: '1',
  aufwendungen: '2',
  ergebnis: '3',
  ausschuettung: '4',
  // E1a sections
  betriebseinnahmen: '1',
  betriebsausgaben: '2',
  gewinn: '3',
  gewinnfreibetrag: '4',
  pauschalierung: '5',
  // E1b sections
  mieteinnahmen: '1',
  werbungskosten_vv: '2',
  afa: '3',
  zinsen: '4',
  ergebnis_vv: '5',
  // L1k sections
  familienbonus: '1',
  kindermehrbetrag: '2',
  unterhaltsabsetzbetrag: '3',
  // U1 sections
  lieferungen: '1',
  sonstige_leistungen: '2',
  vorsteuer: '3',
  zahllast: '4',
  // UVA sections
  umsaetze: '1',
  steuerbetraege: '2',
  // vorsteuer already defined above
  // zahllast already defined above
};

const TOTAL_KEYS = new Set([
  'total_income', 'gesamtbetrag_einkuenfte', 'corporate_profit',
  'profit_after_koest', 'net_dividend',
  // E1a totals
  'betriebsergebnis', 'gewinn_nach_freibetrag',
  // E1b totals
  'total_vv_einkuenfte', 'aggregate_vv_einkuenfte',
  // U1 totals
  'zahllast', 'umsatzsteuer_zahllast',
]);

/** Form type category icons */
const FORM_ICONS: Record<string, string> = {
  E1: '\uD83D\uDCCB',    // clipboard
  E1a: '\uD83D\uDCBC',   // briefcase
  E1b: '\uD83C\uDFE0',   // house
  L1: '\uD83D\uDC64',    // person
  L1k: '\uD83D\uDC68\u200D\uD83D\uDC67\u200D\uD83D\uDC66', // family
  K1: '\uD83C\uDFE2',    // office
  U1: '\uD83D\uDCB0',    // money
  UVA: '\uD83D\uDCB0',   // money
};

/** Map form_type to the API call */
const generateFormByType = async (formType: string, taxYear: number): Promise<TaxFormData> => {
  switch (formType.toUpperCase()) {
    case 'E1A':
      return reportService.generateE1aForm(taxYear);
    case 'E1B':
      return reportService.generateE1bForm(taxYear);
    case 'L1K':
      return reportService.generateL1kForm(taxYear);
    case 'U1':
      return reportService.generateU1Form(taxYear);
    case 'UVA':
      return reportService.generateUvaForm(taxYear);
    default:
      // E1, L1, K1 — main form
      return reportService.generateTaxForm(taxYear);
  }
};

const TaxFormPreview = () => {
  const { t, i18n } = useTranslation();
  const currentYear = new Date().getFullYear();
  const [taxYear, setTaxYear] = useState(currentYear);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formData, setFormData] = useState<TaxFormData | null>(null);
  const [editedValues, setEditedValues] = useState<Record<string, number>>({});

  // Eligible forms state
  const [eligibleForms, setEligibleForms] = useState<EligibleForm[]>([]);
  const [selectedFormType, setSelectedFormType] = useState<string>('MAIN');
  const [loadingForms, setLoadingForms] = useState(false);

  const lang = (i18n.language.split('-')[0] || 'de') as 'de' | 'en' | 'zh';

  // Fetch eligible forms when year changes
  useEffect(() => {
    const fetchEligibleForms = async () => {
      setLoadingForms(true);
      try {
        const response = await reportService.getEligibleForms(taxYear);
        console.log('[TaxFormPreview] eligible-forms response:', response);
        setEligibleForms(response.forms);
      } catch (err: any) {
        console.warn('[TaxFormPreview] eligible-forms failed:', err?.response?.status, err?.message);
        setEligibleForms([]);
      } finally {
        setLoadingForms(false);
      }
    };
    fetchEligibleForms();
  }, [taxYear]);

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    setEditedValues({});
    try {
      const data = await generateFormByType(selectedFormType, taxYear);
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

  const getEligibleFormName = (form: EligibleForm) => {
    const key = `name_${lang}` as keyof EligibleForm;
    return (form[key] as string) || form.name_de;
  };

  const getEligibleFormDesc = (form: EligibleForm) => {
    const key = `description_${lang}` as keyof EligibleForm;
    return (form[key] as string) || form.description_de;
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

  const groupedFields = formData?.fields?.reduce((acc, field) => {
    if (!acc[field.section]) acc[field.section] = [];
    acc[field.section].push(field);
    return acc;
  }, {} as Record<string, TaxFormField[]>) || {};

  const getSectionOrder = (): string[] => {
    if (!formData) return [];
    const ft = formData.form_type;
    if (ft === 'L1') {
      return ['absetzbetraege', 'sonderausgaben', 'werbungskosten', 'pendler'];
    }
    if (ft === 'K1') {
      return ['ertraege', 'aufwendungen', 'ergebnis', 'ausschuettung'];
    }
    if (ft === 'E1a') {
      return ['betriebseinnahmen', 'betriebsausgaben', 'gewinn', 'gewinnfreibetrag', 'pauschalierung'];
    }
    if (ft === 'L1k') {
      return ['familienbonus', 'kindermehrbetrag', 'unterhaltsabsetzbetrag'];
    }
    if (ft === 'U1') {
      return ['lieferungen', 'sonstige_leistungen', 'vorsteuer', 'zahllast'];
    }
    if (ft === 'UVA') {
      return ['umsaetze', 'steuerbetraege', 'vorsteuer', 'zahllast'];
    }
    // Default: E1
    return [
      'einkuenfte_nichtselbstaendig', 'einkuenfte_gewerbebetrieb',
      'einkuenfte_selbstaendig', 'einkuenfte_vermietung',
      'einkuenfte_kapital', 'sonderausgaben', 'werbungskosten',
      'absetzbetraege', 'pendler',
    ];
  };

  const getSectionLabel = (section: string) => {
    if (!SECTION_PUNKT[section]) return section.replace(/_/g, ' ');
    return t(`taxFormPreview.sections.${section}`, section.replace(/_/g, ' '));
  };

  const getPunktNr = (section: string) => SECTION_PUNKT[section] || '?';

  const getSummaryLabel = (key: string) => {
    return t(`taxFormPreview.summaryLabels.${key}`, key.replace(/_/g, ' '));
  };

  const getSummaryKeys = (): string[] => {
    if (!formData) return [];
    const ft = formData.form_type;
    if (ft === 'L1') {
      return ['employment_income', 'werbungskosten', 'sonderausgaben',
              'pendlerpauschale', 'familienbonus', 'alleinerzieher'];
    }
    if (ft === 'K1') {
      return ['total_revenue', 'total_expenses', 'corporate_profit',
              'koest', 'profit_after_koest', 'kest_on_dividend',
              'net_dividend', 'vat_collected', 'vat_paid', 'vat_balance'];
    }
    if (ft === 'E1a') {
      return ['betriebseinnahmen', 'betriebsausgaben', 'betriebsergebnis',
              'gewinnfreibetrag', 'gewinn_nach_freibetrag'];
    }
    if (ft === 'L1k') {
      return ['familienbonus_total', 'kindermehrbetrag_total',
              'unterhaltsabsetzbetrag_total', 'total_absetzbetraege'];
    }
    if (ft === 'U1') {
      return ['umsatz_steuerpflichtig', 'umsatzsteuer', 'vorsteuer',
              'zahllast', 'bereits_entrichtet', 'nachzahlung_gutschrift'];
    }
    if (ft === 'UVA') {
      return ['total_revenue', 'revenue_20', 'revenue_10', 'revenue_13',
              'revenue_exempt', 'total_vat_collected', 'total_vorsteuer', 'zahllast'];
    }
    // Default: E1
    return ['employment_income', 'self_employment_income', 'gewerbebetrieb_gewinn',
            'rental_income', 'vermietung_einkuenfte', 'capital_gains',
            'total_income', 'total_deductible', 'gesamtbetrag_einkuenfte',
            'vat_collected', 'vat_paid', 'vat_balance'];
  };

  // Form types that have official BMF PDF templates in DB (E1, E1a, E1b, U1 for 2022-2025)
  const OFFICIAL_TEMPLATE_TYPES = new Set(['E1', 'E1a', 'E1b', 'U1']);

  // Check if the currently selected form has an official template
  const getSelectedFormHasTemplate = (): boolean => {
    const ft = formData?.form_type || selectedFormType;
    if (ft === 'MAIN') {
      const mainForm = eligibleForms.find(f => ['E1', 'L1', 'K1'].includes(f.form_type));
      return mainForm?.has_template ?? OFFICIAL_TEMPLATE_TYPES.has(mainForm?.form_type || 'E1');
    }
    const form = eligibleForms.find(f => f.form_type === ft);
    return form?.has_template ?? OFFICIAL_TEMPLATE_TYPES.has(ft);
  };

  const selectedFormHasTemplate = getSelectedFormHasTemplate();

  const handlePrint = () => window.print();

  const handleDownloadPDF = async () => {
    try {
      const formType = formData?.form_type || selectedFormType || 'E1';
      const blob = await reportService.downloadFilledFormPDF(formType, taxYear);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `Taxja-${formType}-${taxYear}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('taxFormPreview.pdfDownloadFailed'));
    }
  };

  // Determine which forms are "supplementary" (not the main form)
  const mainFormTypes = new Set(['E1', 'L1', 'K1']);
  const supplementaryForms = eligibleForms.filter(f => !mainFormTypes.has(f.form_type));
  const mainForms = eligibleForms.filter(f => mainFormTypes.has(f.form_type));

  const orderedSections = getSectionOrder().filter(s => groupedFields[s]?.length);

  // Render E1b per-property sections
  const renderE1bProperties = () => {
    if (!formData?.properties?.length) return null;
    return (
      <div className="tf-e1b-properties">
        {formData.properties.map((prop, idx) => {
          const propFields = prop.fields?.reduce((acc, field) => {
            if (!acc[field.section]) acc[field.section] = [];
            acc[field.section].push(field);
            return acc;
          }, {} as Record<string, TaxFormField[]>) || {};

          return (
            <div key={prop.property_id || idx} className="tf-property-section">
              <div className="tf-property-header">
                {'\uD83C\uDFE0'} {prop.address || `Objekt ${idx + 1}`}
              </div>
              {Object.entries(propFields).map(([section, fields]) => (
                <div key={section} className="tf-section">
                  <div className="tf-section-header">
                    <span className="tf-punkt-nr">{getPunktNr(section) !== '?' ? `${t('taxFormPreview.punkt')} ${getPunktNr(section)}` : section.replace(/_/g, ' ')}</span>
                    <span className="tf-section-title">{getSectionLabel(section)}</span>
                  </div>
                  <div className="tf-fields">
                    {fields.map((field, i) => (
                      <div key={`${field.kz}-${i}`} className="tf-field">
                        <div className="tf-kz">{t('taxFormPreview.kz')} {field.kz}</div>
                        <div className="tf-label">
                          {getLabel(field)}
                          {field.note_de && (
                            <span className="tf-field-note">{field.note_de}</span>
                          )}
                        </div>
                        <div className="tf-field-value">
                          <span className="tf-readonly">{fmt(field.value)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
              {/* Per-property summary */}
              {prop.summary && (
                <div className="tf-property-breakdown">
                  <h4>{t('taxFormPreview.summaryLabels.property_result', 'Ergebnis')}</h4>
                  <div className="tf-property-list">
                    {Object.entries(prop.summary).map(([key, amount]) => (
                      <div key={key} className="tf-property-item">
                        <span className="tf-property-category">{getSummaryLabel(key)}</span>
                        <span className="tf-property-amount">{fmt(amount as number)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="tax-form-preview">
      {/* ─── Form Type Selector ─── */}
      {eligibleForms.length > 0 && (
        <div className="tf-form-selector">
          <div className="tf-form-selector-label">
            {t('taxFormPreview.selectForm', 'Formular auswaehlen')}
          </div>
          <div className="tf-form-tabs">
            {/* Main form tab */}
            <button
              className={`tf-form-tab ${selectedFormType === 'MAIN' ? 'active' : ''}`}
              onClick={() => { setSelectedFormType('MAIN'); setFormData(null); }}
              title={mainForms[0] ? getEligibleFormDesc(mainForms[0]) : ''}
            >
              <span className="tf-tab-icon">{FORM_ICONS[mainForms[0]?.form_type || 'E1']}</span>
              <span className="tf-tab-info">
                <span className="tf-tab-name-primary">
                  {mainForms[0] ? getEligibleFormName(mainForms[0]) : t('taxFormPreview.mainForm', 'Hauptformular')}
                </span>
                <span className="tf-tab-meta">
                  <span className="tf-tab-code">{mainForms[0]?.form_type || 'E1'}</span>
                  {mainForms[0]?.has_template && <span className="tf-tab-official" title={t('taxFormPreview.officialPdfAvailable', 'Offizielles BMF-PDF verfügbar')}>{'\uD83C\uDDE6\uD83C\uDDF9'}</span>}
                </span>
              </span>
            </button>
            {/* Supplementary form tabs */}
            {supplementaryForms.map(form => (
              <button
                key={form.form_type}
                className={`tf-form-tab ${selectedFormType === form.form_type ? 'active' : ''}`}
                onClick={() => { setSelectedFormType(form.form_type); setFormData(null); }}
                title={getEligibleFormDesc(form)}
              >
                <span className="tf-tab-icon">{FORM_ICONS[form.form_type] || '\uD83D\uDCC4'}</span>
                <span className="tf-tab-info">
                  <span className="tf-tab-name-primary">{getEligibleFormName(form)}</span>
                  <span className="tf-tab-meta">
                    <span className="tf-tab-code">{form.form_type}</span>
                    {form.has_template && <span className="tf-tab-official" title={t('taxFormPreview.officialPdfAvailable', 'Offizielles BMF-PDF verfügbar')}>{'\uD83C\uDDE6\uD83C\uDDF9'}</span>}
                  </span>
                </span>
              </button>
            ))}
          </div>
          {loadingForms && (
            <div className="tf-loading-forms">{t('common.loading', 'Laden...')}</div>
          )}
        </div>
      )}

      {/* ─── Controls: Year + Generate ─── */}
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
        {formData && selectedFormHasTemplate && (
          <button className="btn btn-primary" onClick={handleDownloadPDF}>
            {'\uD83D\uDCE5'} {t('reports.taxForm.downloadPDF')}
          </button>
        )}
      </div>

      {/* Info message for forms without official BMF template */}
      {formData && !selectedFormHasTemplate && (
        <div className="alert alert-info" style={{ marginTop: '0.5rem', display: 'flex', alignItems: 'flex-start', gap: '0.5rem' }}>
          <span>{'\u2139\uFE0F'}</span>
          <span>{t('taxFormPreview.noOfficialTemplate', 'Für dieses Formular steht kein offizielles BMF-PDF zum Download bereit. Bitte verwenden Sie unsere vereinfachte Vorschau oben und reichen Sie über FinanzOnline ein oder bestellen Sie das Papierformular.')}</span>
        </div>
      )}

      <YearWarning taxYear={taxYear} />
      {error && <div className="alert alert-error">{'\u26A0\uFE0F'} {error}</div>}

      {formData && (
        <div className="tf-content" id="tf-print-area">
          <div className="tf-bmf-header">
            <div className="tf-bmf-header-left">
              <h2>{t('taxFormPreview.bmfHeader')}</h2>
              <div className="tf-bmf-subtitle">
                {t('taxFormPreview.republic')} {'\u2022'} {getFormName()} {formData.tax_year}
              </div>
            </div>
            <div className="tf-form-code">{formData.form_type}</div>
          </div>

          <div className="tf-personal-info">
            <div className="tf-info-cell">
              <div className="tf-info-label">{t('taxFormPreview.taxNumber')}</div>
              <div className="tf-info-value">{formData.tax_number || 'N/A'}</div>
            </div>
            <div className="tf-info-cell">
              <div className="tf-info-label">{t('taxFormPreview.nameOrCompany')}</div>
              <div className="tf-info-value">{formData.user_name}</div>
            </div>
            <div className="tf-info-cell">
              <div className="tf-info-label">{t('taxFormPreview.assessmentYear')}</div>
              <div className="tf-info-value">{formData.tax_year}</div>
            </div>
          </div>
          <div className="tf-generated-note">
            {t('taxFormPreview.generatedAt', { date: formData.generated_at })} {'\u2022'} {t('taxFormPreview.taxFilingAssistant')}
          </div>

          {/* E1b: render per-property sections */}
          {formData.form_type === 'E1b' && formData.properties?.length ? (
            renderE1bProperties()
          ) : (
            /* Standard sections for all other form types */
            orderedSections.map(section => (
              <div key={section} className="tf-section">
                <div className="tf-section-header">
                  <span className="tf-punkt-nr">{t('taxFormPreview.punkt')} {getPunktNr(section)}</span>
                  <span className="tf-section-title">{getSectionLabel(section)}</span>
                </div>
                <div className="tf-fields">
                  {groupedFields[section].map((field, i) => (
                    <div key={`${field.kz}-${i}`} className="tf-field">
                      <div className="tf-kz">{t('taxFormPreview.kz')} {field.kz}</div>
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
            ))
          )}

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

            {/* E1b aggregate summary */}
            {formData.form_type === 'E1b' && formData.aggregate_summary && (
              <div className="tf-property-breakdown">
                <h4>{t('taxFormPreview.summaryLabels.aggregate_total', 'Gesamtsumme alle Objekte')}</h4>
                <div className="tf-property-list">
                  {Object.entries(formData.aggregate_summary).map(([key, amount]) => (
                    <div key={key} className={`tf-property-item ${key.includes('total') || key.includes('ergebnis') ? 'is-depreciation' : ''}`}>
                      <span className="tf-property-category">{getSummaryLabel(key)}</span>
                      <span className="tf-property-amount">{fmt(amount as number)}</span>
                    </div>
                  ))}
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
