import { FileUp, Building2, RefreshCw,
  CalendarRange, LayoutGrid, TrendingUp, Upload as UploadIcon,
  Filter, List, ChevronsLeftRight, Sparkles, Download, PlusCircle,
  Upload, Tags, LayoutList, FileText, Crown, Globe, Palette, Pencil, Archive,
  Plus, House, Repeat2, BarChart3, FileBarChart, Printer, Landmark, FileDown,
  FileSignature, Info, ScrollText, Receipt, Eye, ScanLine, Link2, Package, Home,
  Calculator, Sliders, Scale, ClipboardList, MessageSquare, Bot, Lightbulb,
  User, ShieldCheck, BriefcaseBusiness, CreditCard, History, NotebookTabs } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

/* Tour configuration types */
export interface TourStep {
  icon: LucideIcon;
  titleKey: string;
  messageKey: string;
  target: string | null;
  fallbackTarget?: string | null;
  placement: 'center' | 'right' | 'top' | 'bottom' | 'left';
}

/* Per-page tour configurations */
const PAGE_TOURS: Record<string, TourStep[]> = {
  '/dashboard': [
    { icon: CalendarRange,   titleKey: 'tour.dashboard.year.title',     messageKey: 'tour.dashboard.year.message',     target: '.year-selector',       placement: 'bottom' },
    { icon: UploadIcon,      titleKey: 'tour.dashboard.upload.title',   messageKey: 'tour.dashboard.upload.message',   target: '.upload-zone',         fallbackTarget: '.document-upload', placement: 'bottom' },
    { icon: LayoutGrid,      titleKey: 'tour.dashboard.overview.title', messageKey: 'tour.dashboard.overview.message', target: '.overview-grid',       fallbackTarget: '.dashboard-overview', placement: 'top' },
    { icon: TrendingUp,      titleKey: 'tour.dashboard.trends.title',   messageKey: 'tour.dashboard.trends.message',   target: '.trend-charts',        placement: 'top' },
    { icon: Crown,           titleKey: 'tour.dashboard.plan.title',     messageKey: 'tour.dashboard.plan.message',     target: '.header-status',       placement: 'bottom' },
    { icon: Globe,           titleKey: 'tour.dashboard.language.title', messageKey: 'tour.dashboard.language.message', target: '.language-switcher',    placement: 'bottom' },
    { icon: Palette,         titleKey: 'tour.dashboard.theme.title',    messageKey: 'tour.dashboard.theme.message',    target: '.theme-toggle',        fallbackTarget: '.header-right', placement: 'bottom' },
  ],
  '/transactions': [
    { icon: Sparkles,          titleKey: 'tour.transactions.classRules.title', messageKey: 'tour.transactions.classRules.message', target: '.header-actions a',           placement: 'bottom' },
    { icon: Download,          titleKey: 'tour.transactions.export.title',     messageKey: 'tour.transactions.export.message',     target: '.header-actions button:nth-child(2)', placement: 'bottom' },
    { icon: PlusCircle,        titleKey: 'tour.transactions.addNew.title',     messageKey: 'tour.transactions.addNew.message',     target: '.header-actions button:nth-child(3)', fallbackTarget: '.header-actions .btn-primary', placement: 'bottom' },
    { icon: Filter,            titleKey: 'tour.transactions.filters.title',    messageKey: 'tour.transactions.filters.message',    target: '.transaction-filters', placement: 'bottom' },
    { icon: List,              titleKey: 'tour.transactions.list.title',       messageKey: 'tour.transactions.list.message',       target: '.transactions-page table', fallbackTarget: '.transactions-page', placement: 'top' },
    { icon: ChevronsLeftRight, titleKey: 'tour.transactions.paging.title',     messageKey: 'tour.transactions.paging.message',     target: '.pagination',          placement: 'top' },
  ],
  '/transactions/new': [],
  '/documents': [
    { icon: Upload,        titleKey: 'tour.documents.upload.title', messageKey: 'tour.documents.upload.message', target: '.upload-zone',        placement: 'bottom' },
    { icon: Tags,          titleKey: 'tour.documents.tabs.title',   messageKey: 'tour.documents.tabs.message',   target: '.document-group-tabs', placement: 'bottom' },
    { icon: FileUp,        titleKey: 'tour.documents.list.title',   messageKey: 'tour.documents.list.message',   target: '.document-list',      placement: 'top' },
  ],
  '/documents/:id': [
    { icon: FileSignature, titleKey: 'tour.documentDetail.header.title',      messageKey: 'tour.documentDetail.header.message',      target: '.viewer-header',              fallbackTarget: '.review-header', placement: 'bottom' },
    { icon: Eye,           titleKey: 'tour.documentDetail.preview.title',     messageKey: 'tour.documentDetail.preview.message',     target: '.viewer-content',             fallbackTarget: '.review-content', placement: 'top' },
    { icon: ScanLine,      titleKey: 'tour.documentDetail.ocrData.title',     messageKey: 'tour.documentDetail.ocrData.message',     target: '.viewer-ocr-result',          fallbackTarget: '.review-form-fieldset', placement: 'top' },
    { icon: Link2,         titleKey: 'tour.documentDetail.linked.title',      messageKey: 'tour.documentDetail.linked.message',      target: '.viewer-linked-transaction',  fallbackTarget: '.viewer-linked-asset', placement: 'top' },
    { icon: Pencil,        titleKey: 'tour.documentDetail.editMode.title',    messageKey: 'tour.documentDetail.editMode.message',    target: '.review-form-fieldset',       fallbackTarget: '.ocr-fields-grid', placement: 'top' },
  ],
  '/reports': [
    { icon: LayoutList,    titleKey: 'tour.reports.tabs.title',       messageKey: 'tour.reports.tabs.message',       target: '.tabs',        placement: 'bottom' },
    { icon: FileBarChart,  titleKey: 'tour.reports.generate.title',   messageKey: 'tour.reports.generate.message',   target: '.tab-content .btn-primary', fallbackTarget: '.tab-content', placement: 'bottom' },
    { icon: Printer,       titleKey: 'tour.reports.print.title',      messageKey: 'tour.reports.print.message',      target: '.tab-content .btn-secondary', fallbackTarget: '.tab-content', placement: 'bottom' },
    { icon: FileText,      titleKey: 'tour.reports.content.title',    messageKey: 'tour.reports.content.message',    target: '.tab-content', placement: 'top' },
    { icon: Landmark,      titleKey: 'tour.reports.finanzOnline.title', messageKey: 'tour.reports.finanzOnline.message', target: '.tf-actions .btn-primary', fallbackTarget: '.tf-actions', placement: 'top' },
    { icon: FileDown,      titleKey: 'tour.reports.downloadForm.title', messageKey: 'tour.reports.downloadForm.message', target: '.tf-actions .btn-secondary', fallbackTarget: '.tf-actions', placement: 'top' },
  ],
  '/properties': [
    { icon: BarChart3,  titleKey: 'tour.properties.overview.title', messageKey: 'tour.properties.overview.message', target: '.properties-overview-link', fallbackTarget: '.properties-header', placement: 'bottom' },
    { icon: PlusCircle, titleKey: 'tour.properties.add.title',     messageKey: 'tour.properties.add.message',     target: '.properties-actions .btn-primary', fallbackTarget: '.properties-actions', placement: 'bottom' },
    { icon: Building2,  titleKey: 'tour.properties.cards.title',   messageKey: 'tour.properties.cards.message',   target: '.property-cards', fallbackTarget: '.property-list', placement: 'top' },
    { icon: Pencil,     titleKey: 'tour.properties.edit.title',    messageKey: 'tour.properties.edit.message',    target: '.property-actions .btn-icon:first-child', fallbackTarget: '.property-actions', placement: 'bottom' },
    { icon: Archive,    titleKey: 'tour.properties.archive.title', messageKey: 'tour.properties.archive.message', target: '.toggle-archived', fallbackTarget: '.property-list', placement: 'bottom' },
  ],
  '/properties/portfolio': [
    { icon: BarChart3, titleKey: 'tour.assetInsights.summary.title',      messageKey: 'tour.assetInsights.summary.message',      target: '.tax-tools-summary-grid',    fallbackTarget: '.asset-report-section', placement: 'top' },
    { icon: Home,      titleKey: 'tour.assetInsights.portfolio.title',    messageKey: 'tour.assetInsights.portfolio.message',    target: '.tax-tools-comparison-panel', fallbackTarget: '.asset-report-section', placement: 'top' },
    { icon: Package,   titleKey: 'tour.assetInsights.otherAssets.title',  messageKey: 'tour.assetInsights.otherAssets.message',  target: '.tax-tools-asset-list',      fallbackTarget: '.asset-report-section', placement: 'top' },
    { icon: FileText,  titleKey: 'tour.assetInsights.reports.title',      messageKey: 'tour.assetInsights.reports.message',      target: '.tax-tools-select-label',    fallbackTarget: '.asset-report-section', placement: 'top' },
  ],
  '/properties/:id': [
    { icon: FileSignature, titleKey: 'tour.propertyDetail.actions.title',     messageKey: 'tour.propertyDetail.actions.message',     target: '.header-actions',            placement: 'bottom' },
    { icon: Info,          titleKey: 'tour.propertyDetail.info.title',        messageKey: 'tour.propertyDetail.info.message',        target: '.property-info-section',     placement: 'top' },
    { icon: ScrollText,    titleKey: 'tour.propertyDetail.contracts.title',   messageKey: 'tour.propertyDetail.contracts.message',   target: '.rental-contracts-section',  placement: 'top' },
    { icon: Receipt,       titleKey: 'tour.propertyDetail.transactions.title', messageKey: 'tour.propertyDetail.transactions.message', target: '.transactions-section',    placement: 'top' },
  ],
  '/liabilities': [
    { icon: BarChart3, titleKey: 'tour.liabilities.overview.title', messageKey: 'tour.liabilities.overview.message', target: '.properties-overview-link',        fallbackTarget: '.properties-header', placement: 'bottom' },
    { icon: Plus,      titleKey: 'tour.liabilities.add.title',     messageKey: 'tour.liabilities.add.message',     target: '.properties-actions .btn-primary', fallbackTarget: '.properties-header', placement: 'bottom' },
    { icon: List,      titleKey: 'tour.liabilities.list.title',    messageKey: 'tour.liabilities.list.message',    target: '.liabilities-content',            fallbackTarget: '.liabilities-page', placement: 'top' },
    { icon: Eye,       titleKey: 'tour.liabilities.detail.title',  messageKey: 'tour.liabilities.detail.message',  target: '.liability-panel',                fallbackTarget: '.liabilities-page', placement: 'top' },
  ],
  '/liabilities/overview': [],
  '/liabilities/new': [],
  '/recurring': [
    { icon: Plus,       titleKey: 'tour.recurring.create.title',  messageKey: 'tour.recurring.create.message',  target: '.recurring-actions', placement: 'bottom' },
    { icon: Filter,     titleKey: 'tour.recurring.filters.title', messageKey: 'tour.recurring.filters.message', target: '.recurring-filters', placement: 'bottom' },
    { icon: RefreshCw,  titleKey: 'tour.recurring.list.title',    messageKey: 'tour.recurring.list.message',    target: '.recurring-list',   placement: 'top' },
  ],
  '/advanced': [
    { icon: House,     titleKey: 'tour.advanced.assets.title',     messageKey: 'tour.advanced.assets.message',     target: '.advanced-card:nth-child(1)', fallbackTarget: '.advanced-grid', placement: 'bottom' },
    { icon: Repeat2,   titleKey: 'tour.advanced.automation.title', messageKey: 'tour.advanced.automation.message', target: '.advanced-card:nth-child(2)', fallbackTarget: '.advanced-grid', placement: 'bottom' },
    { icon: BarChart3, titleKey: 'tour.advanced.taxtools.title',   messageKey: 'tour.advanced.taxtools.message',   target: '.advanced-card:nth-child(3)', fallbackTarget: '.advanced-grid', placement: 'top' },
  ],
  '/tax-tools': [
    { icon: Calculator,    titleKey: 'tour.taxTools.refund.title',     messageKey: 'tour.taxTools.refund.message',     target: '.tax-tools-nav-item:nth-child(1)', fallbackTarget: '.tax-tools-sidebar', placement: 'right' },
    { icon: Sliders,       titleKey: 'tour.taxTools.whatIf.title',     messageKey: 'tour.taxTools.whatIf.message',     target: '.tax-tools-nav-item:nth-child(2)', fallbackTarget: '.tax-tools-sidebar', placement: 'right' },
    { icon: Scale,         titleKey: 'tour.taxTools.flatRate.title',   messageKey: 'tour.taxTools.flatRate.message',   target: '.tax-tools-nav-item:nth-child(3)', fallbackTarget: '.tax-tools-sidebar', placement: 'right' },
    { icon: ClipboardList, titleKey: 'tour.taxTools.filing.title',     messageKey: 'tour.taxTools.filing.message',     target: '.tax-tools-nav-item:nth-child(4)', fallbackTarget: '.tax-tools-sidebar', placement: 'right' },
    { icon: BriefcaseBusiness, titleKey: 'tour.taxTools.employer.title', messageKey: 'tour.taxTools.employer.message', target: '.tax-tools-nav-item:nth-child(5)', fallbackTarget: '.tax-tools-sidebar', placement: 'right' },
    { icon: NotebookTabs,  titleKey: 'tour.taxTools.audit.title',       messageKey: 'tour.taxTools.audit.message',       target: '.tax-tools-nav-item:nth-child(6)',  fallbackTarget: '.tax-tools-sidebar', placement: 'right' },
  ],
  '/profile': [
    { icon: User,              titleKey: 'tour.profile.basicInfo.title',   messageKey: 'tour.profile.basicInfo.message',   target: '.profile-section:nth-child(1)',  fallbackTarget: '.profile-form', placement: 'top' },
    { icon: BriefcaseBusiness, titleKey: 'tour.profile.taxInfo.title',     messageKey: 'tour.profile.taxInfo.message',     target: '.profile-section:nth-child(2)',  fallbackTarget: '.profile-form', placement: 'top' },
    { icon: Building2,         titleKey: 'tour.profile.commuting.title',   messageKey: 'tour.profile.commuting.message',   target: '.profile-section:nth-child(3)',  fallbackTarget: '.profile-form', placement: 'top' },
    { icon: ShieldCheck,       titleKey: 'tour.profile.security.title',    messageKey: 'tour.profile.security.message',    target: '.security-info',                 fallbackTarget: '.profile-form', placement: 'top' },
    { icon: Download,          titleKey: 'tour.profile.dataExport.title',  messageKey: 'tour.profile.dataExport.message',  target: '.privacy-section',               fallbackTarget: '.profile-page', placement: 'top' },
  ],
  '/classification-rules': [
    { icon: Sparkles,      titleKey: 'tour.classificationRules.intro.title',   messageKey: 'tour.classificationRules.intro.message',   target: null,                     fallbackTarget: null, placement: 'center' },
    { icon: List,          titleKey: 'tour.classificationRules.list.title',    messageKey: 'tour.classificationRules.list.message',    target: '.classification-rules',  fallbackTarget: null, placement: 'top' },
    { icon: Bot,           titleKey: 'tour.classificationRules.autoLearn.title', messageKey: 'tour.classificationRules.autoLearn.message', target: '.cr-count',          fallbackTarget: '.classification-rules', placement: 'bottom' },
  ],
  '/ai-assistant': [
    { icon: MessageSquare, titleKey: 'tour.aiAssistant.welcome.title',    messageKey: 'tour.aiAssistant.welcome.message',    target: '.chat-welcome',      fallbackTarget: '.ai-assistant-page', placement: 'top' },
    { icon: Pencil,        titleKey: 'tour.aiAssistant.input.title',      messageKey: 'tour.aiAssistant.input.message',      target: '.chat-input-area',   fallbackTarget: '.ai-assistant-page', placement: 'top' },
    { icon: Lightbulb,     titleKey: 'tour.aiAssistant.proactive.title',  messageKey: 'tour.aiAssistant.proactive.message',  target: '.chat-proactive-section', fallbackTarget: '.chat-messages', placement: 'top' },
  ],
  '/subscription/manage': [
    { icon: Crown,      titleKey: 'tour.subscription.plan.title',    messageKey: 'tour.subscription.plan.message',    target: '.plan-card',          fallbackTarget: '.subscription-management', placement: 'top' },
    { icon: CreditCard, titleKey: 'tour.subscription.billing.title', messageKey: 'tour.subscription.billing.message', target: '.billing-history',    fallbackTarget: '.subscription-management', placement: 'top' },
  ],
  '/credits/history': [
    { icon: Filter,  titleKey: 'tour.creditHistory.filter.title', messageKey: 'tour.creditHistory.filter.message', target: '.credit-history-filter', fallbackTarget: '.credit-history-page', placement: 'bottom' },
    { icon: History, titleKey: 'tour.creditHistory.list.title',   messageKey: 'tour.creditHistory.list.message',   target: '.credit-history-list',   fallbackTarget: '.credit-history-page', placement: 'top' },
  ],
};

/* Route matcher (prefix match for parametric routes) */
export function getPageTourSteps(pathname: string): TourStep[] | null {
  // Exact match first (empty arrays mean "no tour for this route")
  if (pathname in PAGE_TOURS) {
    const steps = PAGE_TOURS[pathname];
    return steps.length > 0 ? steps : null;
  }

  // Parametric detail pages: /properties/123 -> /properties/:id
  const segments = pathname.split('/').filter(Boolean);
  if (segments.length >= 2) {
    const paramRoute = '/' + segments[0] + '/:id';
    if (PAGE_TOURS[paramRoute]) return PAGE_TOURS[paramRoute];
  }

  // Prefix match fallback: /properties/123 -> /properties
  for (const route of Object.keys(PAGE_TOURS)) {
    if (!route.includes(':') && pathname.startsWith(route + '/')) return PAGE_TOURS[route];
  }
  return null;
}
