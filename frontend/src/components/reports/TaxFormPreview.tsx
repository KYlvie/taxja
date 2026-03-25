import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import Select from '../common/Select';
import reportService, {
  TaxFormData,
  TaxFormField,
  EligibleForm,
  TaxPackageExportPreview,
  TaxPackageExportStatus,
} from '../../services/reportService';
import YearWarning from './YearWarning';
import { getApiErrorMessage, getFeatureGatePlan } from '../../utils/apiError';
import { getLocaleForLanguage } from '../../utils/locale';
import exportElementToPdf from '../../utils/exportElementToPdf';
import { useFeatureAccess, useUpgradePrompt } from '../subscription/withFeatureGate';
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

type TaxPackageWarningKey =
  | 'pending_tx_count'
  | 'pending_docs'
  | 'uncertain_year_docs'
  | 'skipped_files';

const TAX_PACKAGE_WARNING_HELP: Record<string, Record<TaxPackageWarningKey, string>> = {
  en: {
    pending_tx_count: 'Transactions from the selected tax year still require review before filing.',
    pending_docs: 'Tax-package documents for this year still have open review or OCR confirmation work.',
    uncertain_year_docs: 'These documents were assigned to this tax year only by upload date because no reliable document date or year was found.',
    skipped_files: 'These files matched the package scope but could not be included because the stored file is missing or unreadable.',
  },
  de: {
    pending_tx_count: 'Transaktionen des ausgewaehlten Steuerjahres muessen vor der Abgabe noch geprueft werden.',
    pending_docs: 'Steuerrelevante Dokumente dieses Jahres haben noch offene Pruef- oder OCR-Bestaetigungen.',
    uncertain_year_docs: 'Diese Dokumente wurden diesem Steuerjahr nur ueber das Upload-Datum zugeordnet, weil kein verlaessliches Dokumentdatum erkannt wurde.',
    skipped_files: 'Diese Dateien gehoeren inhaltlich zum Paket, konnten aber nicht aufgenommen werden, weil die gespeicherte Datei fehlt oder nicht lesbar ist.',
  },
  zh: {
    pending_tx_count: '指当前所选税务年度内，仍带待审核标记、建议先人工确认的交易。',
    pending_docs: '指会进入本税务包的文档里，仍未完成审核或 OCR 确认的文件。',
    uncertain_year_docs: '这些文档没有可靠的文档日期或归年，只是按上传日期临时归入本年度。',
    skipped_files: '这些文件本来属于导出范围，但因存储文件缺失或无法读取而未被纳入。',
  },
  fr: {
    pending_tx_count: 'Transactions de l annee fiscale selectionnee qui necessitent encore une verification avant le depot.',
    pending_docs: 'Documents fiscaux de cette annee dont la verification ou la confirmation OCR reste ouverte.',
    uncertain_year_docs: 'Ces documents ont ete rattaches a cette annee uniquement via leur date d envoi, faute de date documentaire fiable.',
    skipped_files: 'Ces fichiers entraient dans le perimetre du pack, mais n ont pas pu etre inclus car le fichier stocke est manquant ou illisible.',
  },
  ru: {
    pending_tx_count: 'Операции выбранного налогового года, которые всё ещё требуют проверки перед подачей.',
    pending_docs: 'Документы этого года, входящие в пакет, по которым ещё не завершена проверка или OCR-подтверждение.',
    uncertain_year_docs: 'Эти документы были отнесены к этому году только по дате загрузки, потому что надёжная дата документа не определена.',
    skipped_files: 'Эти файлы подходили под пакет, но не были включены, потому что файл в хранилище отсутствует или не читается.',
  },
  hu: {
    pending_tx_count: 'A kivalasztott adoev tranzakcioi, amelyek a bevallas elott meg ellenorzesre varnak.',
    pending_docs: 'Az idei adocsomagba tartozo dokumentumok, amelyeknel meg nyitott az ellenorzes vagy az OCR-jovahagyas.',
    uncertain_year_docs: 'Ezeket a dokumentumokat csak a feltoltes datuma alapjan soroltuk ehhez az adoevhez, mert nincs megbizhato dokumentumdatum.',
    skipped_files: 'Ezek a fajlok a csomag reszei lennenek, de a tarolt fajl hianyzik vagy nem olvashato, ezert kimaradtak.',
  },
  pl: {
    pending_tx_count: 'Transakcje z wybranego roku podatkowego, ktore nadal wymagaja weryfikacji przed zlozeniem.',
    pending_docs: 'Dokumenty podatkowe z tego roku, dla ktorych wciaz nie zakonczono przegladu lub potwierdzenia OCR.',
    uncertain_year_docs: 'Te dokumenty przypisano do tego roku tylko na podstawie daty przeslania, poniewaz brak wiarygodnej daty dokumentu.',
    skipped_files: 'Te pliki miescily sie w zakresie pakietu, ale nie zostaly dolaczone, bo brak pliku w magazynie lub nie da sie go odczytac.',
  },
  tr: {
    pending_tx_count: 'Secilen vergi yilindaki ve beyan oncesinde halen incelenmesi gereken islemler.',
    pending_docs: 'Bu yila ait vergi paketi belgeleri icinde incelemesi veya OCR onayi halen acik olan dosyalar.',
    uncertain_year_docs: 'Bu belgeler guvenilir bir belge tarihi bulunamadigi icin sadece yukleme tarihine gore bu yila atanmistir.',
    skipped_files: 'Bu dosyalar paket kapsamindaydi ancak depolanan dosya eksik veya okunamaz oldugu icin dahil edilemedi.',
  },
  bs: {
    pending_tx_count: 'Transakcije iz odabrane poreske godine koje jos trebaju pregled prije prijave.',
    pending_docs: 'Dokumenti za ovu godinu koji ulaze u poreski paket, ali im pregled ili OCR potvrda jos nisu zavrseni.',
    uncertain_year_docs: 'Ovi dokumenti su svrstani u ovu godinu samo po datumu otpremanja jer nije pronaden pouzdan datum dokumenta.',
    skipped_files: 'Ove datoteke pripadaju paketu, ali nisu ukljucene jer pohranjena datoteka nedostaje ili se ne moze procitati.',
  },
};

const getTaxPackageWarningHelp = (language: string, key: TaxPackageWarningKey): string => {
  const normalized = (language || 'en').split('-')[0].toLowerCase();
  return TAX_PACKAGE_WARNING_HELP[normalized]?.[key] ?? TAX_PACKAGE_WARNING_HELP.en[key];
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
  const [showTaxPackagePanel, setShowTaxPackagePanel] = useState(false);
  const [includeFoundationMaterials, setIncludeFoundationMaterials] = useState(false);
  const [taxPackagePreview, setTaxPackagePreview] = useState<TaxPackageExportPreview | null>(null);
  const [loadingTaxPackagePreview, setLoadingTaxPackagePreview] = useState(false);
  const [taxPackagePreviewError, setTaxPackagePreviewError] = useState<string | null>(null);
  const [acknowledgedTaxPackageWarnings, setAcknowledgedTaxPackageWarnings] = useState(false);
  const [taxPackageExport, setTaxPackageExport] = useState<TaxPackageExportStatus | null>(null);
  const [creatingTaxPackage, setCreatingTaxPackage] = useState(false);

  // Eligible forms state
  const [eligibleForms, setEligibleForms] = useState<EligibleForm[]>([]);
  const [selectedFormType, setSelectedFormType] = useState<string>('MAIN');
  const [loadingForms, setLoadingForms] = useState(false);
  const previewExportRef = useRef<HTMLDivElement | null>(null);
  const hasTaxFormAccess = useFeatureAccess('e1_generation');
  const { showUpgrade, UpgradePromptComponent } = useUpgradePrompt();

  const uiLanguage = i18n.language.split('-')[0] || 'de';
  const lang = uiLanguage as 'de' | 'en' | 'zh' | 'fr' | 'ru';

  const buildScopedLink = (
    page: 'documents' | 'transactions',
    options?: {
      needsReview?: boolean;
      yearScoped?: boolean;
    },
  ) => {
    const params = new URLSearchParams();
    if (options?.needsReview) params.set('needs_review', 'true');
    if (options?.yearScoped) params.set('year', String(taxYear));
    return `/${page}${params.toString() ? `?${params.toString()}` : ''}`;
  };

  // Clear generated preview when tax year changes so each year must be generated explicitly
  useEffect(() => {
    setFormData(null);
    setError(null);
    setEditedValues({});
    setTaxPackagePreview(null);
    setTaxPackagePreviewError(null);
    setAcknowledgedTaxPackageWarnings(false);
    setTaxPackageExport(null);
    setShowTaxPackagePanel(false);
    setIncludeFoundationMaterials(false);
  }, [taxYear]);

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
    if (!hasTaxFormAccess) {
      showUpgrade('e1_generation', 'pro');
      return;
    }
    setLoading(true);
    setError(null);
    setEditedValues({});
    try {
      const data = await generateFormByType(selectedFormType, taxYear);
      setFormData(data);
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

  const fmt = (n: number) => new Intl.NumberFormat(getLocaleForLanguage(i18n.language), {
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
      if (!selectedFormHasTemplate) {
        if (!previewExportRef.current || !formData) {
          throw new Error('preview_export_unavailable');
        }

        await exportElementToPdf({
          element: previewExportRef.current,
          filename: `Taxja-${formType}-${taxYear}.pdf`,
          title: getFormName(),
          subtitle: `${t('reports.taxYear')}: ${taxYear}`,
          brandLabel: 'Taxja',
        });
        return;
      }

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
      const gatePlan = getFeatureGatePlan(err);
      if (gatePlan) {
        setError(t('subscription.featureRequiresPlan', { plan: gatePlan.toUpperCase() }));
      } else {
        setError(getApiErrorMessage(err, t('taxFormPreview.pdfDownloadFailed')));
      }
    }
  };

  const handleCreateTaxPackage = async () => {
    if (taxPackagePreview?.has_warnings && !acknowledgedTaxPackageWarnings) {
      setAcknowledgedTaxPackageWarnings(true);
      return;
    }

    setCreatingTaxPackage(true);
    setError(null);
    try {
      const result = await reportService.createTaxPackageExport(
        taxYear,
        uiLanguage,
        includeFoundationMaterials,
      );
      setTaxPackageExport(result);
    } catch (err: any) {
      const gatePlan = getFeatureGatePlan(err);
      if (gatePlan) {
        setError(t('subscription.featureRequiresPlan', { plan: gatePlan.toUpperCase() }));
      } else {
        setError(getApiErrorMessage(err, t('reports.taxForm.exportPackageFailed', 'Failed to export tax package')));
      }
    } finally {
      setCreatingTaxPackage(false);
    }
  };

  const handleToggleTaxPackagePanel = () => {
    if (!hasTaxFormAccess) {
      showUpgrade('e1_generation', 'pro');
      return;
    }
    setShowTaxPackagePanel((open) => !open);
  };

  useEffect(() => {
    if (!taxPackageExport || !['pending', 'processing'].includes(taxPackageExport.status)) {
      return undefined;
    }

    const intervalId = window.setInterval(async () => {
      try {
        const next = await reportService.getTaxPackageExportStatus(taxPackageExport.export_id);
        setTaxPackageExport(next);
      } catch (err: any) {
        setError(getApiErrorMessage(err, t('reports.taxForm.exportPackageFailed', 'Failed to export tax package')));
      }
    }, 2000);

    return () => window.clearInterval(intervalId);
  }, [taxPackageExport, t]);

  useEffect(() => {
    if (!showTaxPackagePanel || !hasTaxFormAccess) {
      return undefined;
    }

    let cancelled = false;
    const loadPreview = async () => {
      setLoadingTaxPackagePreview(true);
      setTaxPackagePreviewError(null);
      setAcknowledgedTaxPackageWarnings(false);
      try {
        const preview = await reportService.previewTaxPackageExport(
          taxYear,
          uiLanguage,
          includeFoundationMaterials,
        );
        if (!cancelled) {
          setTaxPackagePreview(preview);
        }
      } catch (err: any) {
        if (!cancelled) {
          setTaxPackagePreview(null);
          setTaxPackagePreviewError(
            getApiErrorMessage(err, t('reports.taxForm.exportPackagePreviewFailed', 'Failed to check export package warnings')),
          );
        }
      } finally {
        if (!cancelled) {
          setLoadingTaxPackagePreview(false);
        }
      }
    };

    loadPreview();
    return () => {
      cancelled = true;
    };
  }, [showTaxPackagePanel, hasTaxFormAccess, taxYear, uiLanguage, includeFoundationMaterials, t]);

  // Determine which forms are "supplementary" (not the main form)
  const mainFormTypes = new Set(['E1', 'L1', 'K1']);
  const supplementaryForms = eligibleForms.filter(f => !mainFormTypes.has(f.form_type));
  const mainForms = eligibleForms.filter(f => mainFormTypes.has(f.form_type));

  const orderedSections = getSectionOrder().filter(s => groupedFields[s]?.length);
  const taxPackageWarnings = taxPackagePreview?.warnings || [];
  const hasTaxPackageWarnings = taxPackageWarnings.length > 0;
  const taxPackageSummary = taxPackagePreview?.summary;
  const taxPackageWarningItems = [
    {
      key: 'pending_tx_count' as const,
      count: typeof taxPackageSummary?.pending_tx_count === 'number' ? taxPackageSummary.pending_tx_count : 0,
      label: t('reports.taxForm.exportPackageWarningPendingTransactions', 'Pending review transactions'),
      help: getTaxPackageWarningHelp(uiLanguage, 'pending_tx_count'),
      href: buildScopedLink('transactions', { needsReview: true, yearScoped: true }),
      actionLabel: t('reports.taxForm.reviewTransactionsBeforeExport', 'Review pending transactions'),
    },
    {
      key: 'pending_docs' as const,
      count: typeof taxPackageSummary?.pending_document_count === 'number' ? taxPackageSummary.pending_document_count : 0,
      label: t('reports.taxForm.exportPackageWarningPendingDocuments', 'Pending review documents included in this package'),
      help: getTaxPackageWarningHelp(uiLanguage, 'pending_docs'),
      href: buildScopedLink('documents', { needsReview: true, yearScoped: true }),
      actionLabel: t('reports.taxForm.reviewDocumentsBeforeExport', 'Review pending documents'),
    },
    {
      key: 'uncertain_year_docs' as const,
      count: typeof taxPackageSummary?.uncertain_year_docs === 'number' ? taxPackageSummary.uncertain_year_docs : 0,
      label: t('reports.taxForm.exportPackageWarningFallbackYears', 'Documents assigned to this tax year by uploaded date fallback'),
      help: getTaxPackageWarningHelp(uiLanguage, 'uncertain_year_docs'),
      href: buildScopedLink('documents', { yearScoped: true }),
      actionLabel: t('reports.taxForm.reviewDocumentsByYear', 'Review documents from this year'),
    },
    {
      key: 'skipped_files' as const,
      count: Array.isArray(taxPackageSummary?.skipped_files) ? taxPackageSummary.skipped_files.length : 0,
      label: t('reports.taxForm.exportPackageWarningSkippedFiles', 'Files excluded from export'),
      help: getTaxPackageWarningHelp(uiLanguage, 'skipped_files'),
      href: buildScopedLink('documents', { yearScoped: true }),
      actionLabel: t('reports.taxForm.reviewDocumentsByYear', 'Review documents from this year'),
    },
  ].filter((item) => item.count > 0);

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
      {UpgradePromptComponent}
      {/* ─── Form Type Selector ─── */}
      <div className="tf-form-selector">
        <div className="tf-form-selector-header">
          <div className="tf-form-selector-copy">
            <div className="tf-form-selector-label">
              {t('taxFormPreview.selectForm', 'Formular auswaehlen')}
            </div>
          </div>
          <button
            className={`btn btn-secondary tf-tax-package-btn ${hasTaxFormAccess ? '' : 'tf-tax-package-btn--locked'}`.trim()}
            onClick={handleToggleTaxPackagePanel}
            type="button"
          >
            {'\uD83D\uDCE6'} {t('reports.taxForm.exportPackage', 'Export tax package')}
            {!hasTaxFormAccess && (
              <span className="tf-tax-package-btn-badge">PRO</span>
            )}
          </button>
        </div>
        {eligibleForms.length > 0 && (
          <div className="tf-form-tabs">
            {/* Main form tabs — render ALL main forms (E1, L1, K1) */}
            {mainForms.map((mf, idx) => (
              <button
                key={mf.form_type}
                className={`tf-form-tab ${(idx === 0 && selectedFormType === 'MAIN') || selectedFormType === mf.form_type ? 'active' : ''}`}
                onClick={() => { setSelectedFormType(idx === 0 ? 'MAIN' : mf.form_type); setFormData(null); }}
                title={getEligibleFormDesc(mf)}
              >
                <span className="tf-tab-icon">{FORM_ICONS[mf.form_type] || '\uD83D\uDCC4'}</span>
                <span className="tf-tab-info">
                  <span className="tf-tab-name-primary">
                    {getEligibleFormName(mf)}
                  </span>
                  <span className="tf-tab-meta">
                    <span className="tf-tab-code">{mf.form_type}</span>
                    {mf.has_template && <span className="tf-tab-official" title={t('taxFormPreview.officialPdfAvailable', 'Offizielles BMF-PDF verfügbar')}>{'\uD83C\uDDE6\uD83C\uDDF9'}</span>}
                  </span>
                </span>
              </button>
            ))}
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
        )}
        {loadingForms && (
          <div className="tf-loading-forms">{t('common.loading', 'Laden...')}</div>
        )}
      </div>

      {/* ─── Controls: Year + Generate ─── */}
      {hasTaxFormAccess && showTaxPackagePanel && createPortal(
        <div className="tf-tax-package-overlay" onClick={() => setShowTaxPackagePanel(false)}>
          <div className="tf-tax-package-modal" onClick={(e) => e.stopPropagation()}>
            <div className="tf-tax-package-modal-header">
              <div className="tf-tax-package-title">
                {t('reports.taxForm.exportPackagePanelTitle', 'Export tax package')}
              </div>
              <button
                type="button"
                className="tf-tax-package-modal-close"
                onClick={() => setShowTaxPackagePanel(false)}
                aria-label={t('common.close', 'Close')}
              >
                ✕
              </button>
            </div>
          <p className="tf-tax-package-description">
            {t(
              'reports.taxForm.exportPackagePanelDescription',
              'Prepare a downloadable package for the selected tax year with transaction exports and tax-related source documents.',
            )}
          </p>
          <ul className="tf-tax-package-scope">
            <li>{t('reports.taxForm.packageScopeTransactionsCsv', 'Transaction CSV')}</li>
            <li>{t('reports.taxForm.packageScopeTransactionsPdf', 'Transaction PDF')}</li>
            <li>{t('reports.taxForm.packageScopeSummaryPdf', 'Summary PDF')}</li>
            <li>{t('reports.taxForm.packageScopeDocuments', 'Tax-related source documents')}</li>
            <li>{t('reports.taxForm.packageScopeFoundationOptional', 'Optional: foundation materials')}</li>
          </ul>
          <label className="tf-tax-package-checkbox">
            <input
              type="checkbox"
              checked={includeFoundationMaterials}
              onChange={(event) => setIncludeFoundationMaterials(event.target.checked)}
            />
            <span>{t('reports.taxForm.includeFoundationMaterials', 'Include foundation materials')}</span>
          </label>
          <div className="tf-tax-package-hint">
            {t(
              'reports.taxForm.includeFoundationMaterialsHint',
              'Adds long-lived base materials such as rental, loan, purchase, registry, and trade-license documents.',
            )}
          </div>
          {loadingTaxPackagePreview && (
            <div className="tf-tax-package-preview-loading">
              {t('reports.taxForm.exportPackagePreviewLoading', 'Checking export package warnings...')}
            </div>
          )}
          {taxPackagePreviewError && (
            <div className="tf-tax-package-failure">
              {taxPackagePreviewError}
            </div>
          )}
          {!loadingTaxPackagePreview && taxPackagePreview && hasTaxPackageWarnings && (
            <div className={`tf-tax-package-warning ${acknowledgedTaxPackageWarnings ? 'tf-tax-package-warning--confirmed' : ''}`}>
              <div className="tf-tax-package-warning-title">
                {t('reports.taxForm.exportPackageWarningTitle', 'Review these items before exporting')}
              </div>
              <div className="tf-tax-package-warning-description">
                {t(
                  'reports.taxForm.exportPackageWarningDescription',
                  'The package can still be exported, but these open items may reduce filing quality. Please review and resolve them first if possible.',
                )}
              </div>
              <div className="tf-tax-package-warning-list">
                {taxPackageWarningItems.map((warning) => (
                  <div className="tf-tax-package-warning-item" key={warning.key}>
                    <div className="tf-tax-package-warning-item-header">
                      <span className="tf-tax-package-warning-item-label">
                        {warning.label}: {warning.count}
                      </span>
                      <Link className="btn btn-secondary" to={warning.href}>
                        {warning.actionLabel}
                      </Link>
                    </div>
                    <div className="tf-tax-package-warning-item-help">{warning.help}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
          <div className="tf-tax-package-actions">
            <button
              className="btn btn-primary"
              onClick={handleCreateTaxPackage}
              disabled={creatingTaxPackage || loadingTaxPackagePreview}
            >
              {creatingTaxPackage
                ? t('reports.taxForm.exportPackageLoading', 'Preparing tax package...')
                : hasTaxPackageWarnings
                  ? acknowledgedTaxPackageWarnings
                    ? t('reports.taxForm.continueExportPackage', 'Continue export anyway')
                    : t('reports.taxForm.reviewWarningsFirst', 'Review warnings first')
                  : t('reports.taxForm.preparePackage', 'Prepare package')}
            </button>
          </div>

          {taxPackageExport && (
            <div className="tf-tax-package-status">
              <div className="tf-tax-package-status-label">
                {taxPackageExport.status === 'pending' &&
                  t('reports.taxForm.packageStatusPending', 'Preparing')}
                {taxPackageExport.status === 'processing' &&
                  t('reports.taxForm.packageStatusProcessing', 'Packaging')}
                {taxPackageExport.status === 'ready' &&
                  t('reports.taxForm.packageStatusReady', 'Ready to download')}
                {taxPackageExport.status === 'failed' &&
                  t('reports.taxForm.packageFailureTitle', 'Package could not be prepared')}
              </div>

              {taxPackageExport.status === 'ready' && (taxPackageExport.parts?.length ?? 0) > 0 && (
                <div className="tf-tax-package-downloads">
                  {(taxPackageExport.parts || []).map((part) => (
                    <a
                      key={part.part_number}
                      className="btn btn-secondary"
                      href={part.download_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {'\u2B07\uFE0F'} {(taxPackageExport.parts?.length || 0) === 1
                        ? t('reports.taxForm.packageDownloadSingle', 'Download package')
                        : t('reports.taxForm.packageDownloadPart', 'Download part {{part}}', { part: part.part_number })}
                    </a>
                  ))}
                </div>
              )}

              {taxPackageExport.status === 'failed' && taxPackageExport.failure && (
                <div className="tf-tax-package-failure">
                  <div>{taxPackageExport.failure.reason || t('reports.taxForm.exportPackageFailed', 'Failed to export tax package')}</div>
                  {typeof taxPackageExport.failure.document_count === 'number' && (
                    <div>
                      {t('reports.taxForm.packageFailureDocumentCount', 'Document count')}: {taxPackageExport.failure.document_count}
                    </div>
                  )}
                  {typeof taxPackageExport.failure.estimated_total_size_bytes === 'number' && (
                    <div>
                      {t('reports.taxForm.packageFailureEstimatedSize', 'Estimated size')}: {Math.round(taxPackageExport.failure.estimated_total_size_bytes / (1024 * 1024))} MB
                    </div>
                  )}
                  {taxPackageExport.failure.largest_family && (
                    <div>
                      {t('reports.taxForm.packageFailureLargestFamily', 'Largest family')}: {taxPackageExport.failure.largest_family.label}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
          </div>
        </div>,
        document.body
      )}

      <div className="tf-controls">
        <div className="tf-generate-row">
          <div className="tf-year-inline">
            <label htmlFor="tf-year">{t('reports.taxYear')}</label>
            <Select
              id="tf-year"
              value={String(taxYear)}
              onChange={v => setTaxYear(Number(v))}
              options={Array.from({ length: 5 }, (_, i) => ({
                value: String(currentYear - i),
                label: String(currentYear - i),
              }))}
              size="sm"
            />
          </div>
          <div className="tf-action-group">
            {!formData ? (
              <button
                className={`btn btn-primary tf-generate-btn ${hasTaxFormAccess ? '' : 'tf-generate-btn--locked'}`.trim()}
                onClick={handleGenerate}
                disabled={loading}
                type="button"
              >
                {loading ? t('common.loading') : t('reports.taxForm.generate')}
                {!hasTaxFormAccess && <span className="tf-generate-btn-badge">PRO</span>}
              </button>
            ) : (
              <>
                <button className="btn btn-secondary" onClick={handlePrint}>
                  {'\uD83D\uDDA8\uFE0F'} {t('reports.ea.print')}
                </button>
                {selectedFormHasTemplate ? (
                  <button className="btn btn-primary" onClick={handleDownloadPDF}>
                    {'\uD83D\uDCE5'} {t('reports.taxForm.downloadPDF')}
                  </button>
                ) : (
                  <button className="btn btn-primary" onClick={handleDownloadPDF}>
                    {'\uD83D\uDCE5'} {t('reports.ea.downloadPDF', 'Download PDF')}
                  </button>
                )}
              </>
            )}
          </div>
        </div>
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
        <div className="tf-content" id="tf-print-area" ref={previewExportRef}>
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
              {formData.summary && getSummaryKeys()
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
            {formData.summary?.rental_by_property && Object.keys(formData.summary.rental_by_property).length > 0 && (
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
            {formData.summary?.property_expenses && Object.keys(formData.summary.property_expenses).length > 0 && (
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
            {formData.summary?.property_depreciation && formData.summary.property_depreciation > 0 && (
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
