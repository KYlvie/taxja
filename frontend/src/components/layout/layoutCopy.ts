import { normalizeLanguage, type SupportedLanguage } from '../../utils/locale';

interface LayoutCopy {
  appCaption: string;
  contextKicker: string;
  sidebarSubtitle: string;
  sidebarStatus: string;
  openNavigation: string;
  advancedLabel: string;
}

const layoutCopyByLanguage: Partial<Record<SupportedLanguage, LayoutCopy>> = {
  de: {
    appCaption: 'Oesterreichische Steuerzentrale',
    contextKicker: 'Aktive Flaeche',
    sidebarSubtitle: 'Steuer-Operationsnetz',
    sidebarStatus: 'Live-Sync',
    openNavigation: 'Navigation oeffnen',
    advancedLabel: 'Erweiterte Verwaltung',
  },
  en: {
    appCaption: 'Austrian Tax Operations',
    contextKicker: 'Active Surface',
    sidebarSubtitle: 'Tax Operations Grid',
    sidebarStatus: 'Live Sync',
    openNavigation: 'Open navigation',
    advancedLabel: 'Advanced Management',
  },
  zh: {
    appCaption: '奥地利税务作业中台',
    contextKicker: '当前界面',
    sidebarSubtitle: '税务运营控制台',
    sidebarStatus: '实时同步',
    openNavigation: '打开导航',
    advancedLabel: '高级管理',
  },
  fr: {
    appCaption: 'Centre fiscal autrichien',
    contextKicker: 'Surface active',
    sidebarSubtitle: 'Grille des opérations fiscales',
    sidebarStatus: 'Sync en direct',
    openNavigation: 'Ouvrir la navigation',
    advancedLabel: 'Gestion avancée',
  },
  ru: {
    appCaption: 'Австрийский налоговый центр',
    contextKicker: 'Активная область',
    sidebarSubtitle: 'Панель налоговых операций',
    sidebarStatus: 'Синхронизация',
    openNavigation: 'Открыть навигацию',
    advancedLabel: 'Расширенное управление',
  },
};

export const getLayoutCopy = (language?: string | null): LayoutCopy =>
  layoutCopyByLanguage[normalizeLanguage(language)] ?? layoutCopyByLanguage.en!;
