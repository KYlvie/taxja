import { normalizeLanguage, type SupportedLanguage } from '../../utils/locale';

interface LayoutCopy {
  appCaption: string;
  contextKicker: string;
  sidebarSubtitle: string;
  sidebarStatus: string;
  openNavigation: string;
  advancedLabel: string;
}

const layoutCopyByLanguage: Record<SupportedLanguage, LayoutCopy> = {
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
};

export const getLayoutCopy = (language?: string | null): LayoutCopy =>
  layoutCopyByLanguage[normalizeLanguage(language)];
