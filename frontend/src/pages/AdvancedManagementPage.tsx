import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { normalizeLanguage } from '../utils/locale';
import './AdvancedManagementPage.css';

type AdvancedCardId = 'assets' | 'rules' | 'classification' | 'tax-tools';

type AdvancedCard = {
  id: AdvancedCardId;
  icon: string;
  title: string;
  subtitle: string;
  primaryLabel: string;
  primaryTo: string;
  secondaryLabel?: string;
  secondaryTo?: string;
  tertiaryLabel?: string;
  tertiaryTo?: string;
};

type LangCopy = {
  title: string;
  subtitle: string;
  cards: AdvancedCard[];
};

const copy: Record<'de' | 'en' | 'zh', LangCopy> = {
  de: {
    title: 'Erweiterte Verwaltung',
    subtitle: 'Vermoegen, Regeln und Steuer-Tools',
    cards: [
      {
        id: 'assets',
        icon: '🏠',
        title: 'Vermoegensverwaltung',
        subtitle: 'Immobilien, Geraete, Abschreibung und Vergleiche',
        primaryLabel: 'Verwalten',
        primaryTo: '/properties',
        secondaryLabel: 'Portfolio',
        secondaryTo: '/properties/portfolio',
        tertiaryLabel: 'Vergleich',
        tertiaryTo: '/properties/comparison',
      },
      {
        id: 'rules',
        icon: '🔄',
        title: 'Automatische Regeln',
        subtitle: 'Wiederkehrende Buchungen steuern',
        primaryLabel: 'Regeln',
        primaryTo: '/recurring',
      },
      {
        id: 'classification',
        icon: '✨',
        title: 'AI-Klassifizierungsregeln',
        subtitle: 'Gelernte Zuordnungsregeln verwalten',
        primaryLabel: 'Regeln anzeigen',
        primaryTo: '/classification-rules',
      },
      {
        id: 'tax-tools',
        icon: '📊',
        title: 'Steuer-Tools',
        subtitle: 'Steuerstand, KI-Hinweise, Lohn-Dateien und Vermoegensberichte',
        primaryLabel: 'Oeffnen',
        primaryTo: '/tax-tools',
      },
    ],
  },
  en: {
    title: 'Advanced Management',
    subtitle: 'Assets, rules and tax tools',
    cards: [
      {
        id: 'assets',
        icon: '🏠',
        title: 'Asset Management',
        subtitle: 'Properties, equipment, depreciation and comparisons',
        primaryLabel: 'Manage',
        primaryTo: '/properties',
        secondaryLabel: 'Portfolio',
        secondaryTo: '/properties/portfolio',
        tertiaryLabel: 'Compare',
        tertiaryTo: '/properties/comparison',
      },
      {
        id: 'rules',
        icon: '🔄',
        title: 'Automatic Rules',
        subtitle: 'Manage recurring transactions',
        primaryLabel: 'Rules',
        primaryTo: '/recurring',
      },
      {
        id: 'classification',
        icon: '✨',
        title: 'AI Classification Rules',
        subtitle: 'Manage learned categorization rules',
        primaryLabel: 'View Rules',
        primaryTo: '/classification-rules',
      },
      {
        id: 'tax-tools',
        icon: '📊',
        title: 'Tax Tools',
        subtitle: 'Tax position, AI guidance, payroll files and asset reports',
        primaryLabel: 'Open',
        primaryTo: '/tax-tools',
      },
    ],
  },
  zh: {
    title: '高级管理',
    subtitle: '资产、规则与税务工具',
    cards: [
      {
        id: 'assets',
        icon: '🏠',
        title: '资产管理',
        subtitle: '房产、设备、折旧、总览与对比',
        primaryLabel: '管理资产',
        primaryTo: '/properties',
        secondaryLabel: '资产总览',
        secondaryTo: '/properties/portfolio',
        tertiaryLabel: '资产对比',
        tertiaryTo: '/properties/comparison',
      },
      {
        id: 'rules',
        icon: '🔄',
        title: '自动规则',
        subtitle: '管理每月自动记账',
        primaryLabel: '打开规则',
        primaryTo: '/recurring',
      },
      {
        id: 'classification',
        icon: '✨',
        title: 'AI分类规则',
        subtitle: '管理 AI 学习到的分类规则',
        primaryLabel: '查看规则',
        primaryTo: '/classification-rules',
      },
      {
        id: 'tax-tools',
        icon: '📊',
        title: '税务工具',
        subtitle: '税款状态、AI 建议、工资文件与资产报告',
        primaryLabel: '打开',
        primaryTo: '/tax-tools',
      },
    ],
  },
};

const AdvancedManagementPage = () => {
  const { i18n } = useTranslation();
  const language = normalizeLanguage(i18n.resolvedLanguage || i18n.language);
  const c = copy[language];

  return (
    <div className="advanced-page">
      <div className="advanced-header-simple">
        <h1>{c.title}</h1>
        <p>{c.subtitle}</p>
      </div>

      <div className="advanced-grid">
        {c.cards.map((card) => (
          <article key={card.id} className="advanced-card card">
            <div className="advanced-card-icon">{card.icon}</div>
            <h2>{card.title}</h2>
            <p className="advanced-card-subtitle">{card.subtitle}</p>
            <div className="advanced-card-actions">
              <Link to={card.primaryTo} className="btn btn-primary">
                {card.primaryLabel}
              </Link>
              {card.secondaryLabel && card.secondaryTo && (
                <Link to={card.secondaryTo} className="btn btn-secondary">
                  {card.secondaryLabel}
                </Link>
              )}
              {card.tertiaryLabel && card.tertiaryTo && (
                <Link to={card.tertiaryTo} className="btn btn-secondary">
                  {card.tertiaryLabel}
                </Link>
              )}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
};

export default AdvancedManagementPage;
