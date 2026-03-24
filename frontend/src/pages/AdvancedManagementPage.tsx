import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { BarChart3, House, Repeat2, type LucideIcon } from 'lucide-react';
import FuturisticIcon, { type FuturisticIconTone } from '../components/common/FuturisticIcon';
import { normalizeLanguage } from '../utils/locale';
import './AdvancedManagementPage.css';

type AdvancedCardId = 'assets' | 'automation' | 'tax-tools';

type AdvancedCard = {
  id: AdvancedCardId;
  icon: LucideIcon;
  tone: FuturisticIconTone;
  title: string;
  subtitle: string;
  primaryLabel: string;
  primaryTo: string;
  secondaryLabel?: string;
  secondaryTo?: string;
};

type LangCopy = {
  title: string;
  subtitle: string;
  cards: AdvancedCard[];
};

const copy: Record<string, LangCopy> = {
  de: {
    title: 'Erweiterte Verwaltung',
    subtitle: 'Vermoegen, Schulden, Automatisierung und Steuer-Workspace',
    cards: [
      {
        id: 'assets',
        icon: House,
        tone: 'cyan',
        title: 'Asset- und Schuldenverwaltung',
        subtitle: 'Assets, Darlehen, Verbindlichkeiten und klare Modulgrenzen',
        primaryLabel: 'Assets verwalten',
        primaryTo: '/properties',
        secondaryLabel: 'Schulden verwalten',
        secondaryTo: '/liabilities',
      },
      {
        id: 'automation',
        icon: Repeat2,
        tone: 'violet',
        title: 'Regeln & Automatisierung',
        subtitle: 'Wiederkehrende Buchungen und gelernte Klassifizierungen verwalten',
        primaryLabel: 'Dauerbuchungen',
        primaryTo: '/recurring',
        secondaryLabel: 'Klassifizierungsspeicher',
        secondaryTo: '/classification-rules',
      },
      {
        id: 'tax-tools',
        icon: BarChart3,
        tone: 'emerald',
        title: 'Steuer-Workspace',
        subtitle: 'Meldungen, Unterlagen, KI-Hinweise und Berichte an einem Ort',
        primaryLabel: 'Workspace oeffnen',
        primaryTo: '/tax-tools',
      },
    ],
  },
  en: {
    title: 'Advanced Management',
    subtitle: 'Assets, liabilities, automation, and your tax workspace',
    cards: [
      {
        id: 'assets',
        icon: House,
        tone: 'cyan',
        title: 'Asset & Liability Management',
        subtitle: 'Assets, loans, borrowings, and clear module boundaries',
        primaryLabel: 'Manage Assets',
        primaryTo: '/properties',
        secondaryLabel: 'Manage Liabilities',
        secondaryTo: '/liabilities',
      },
      {
        id: 'automation',
        icon: Repeat2,
        tone: 'violet',
        title: 'Rules & Automation',
        subtitle: 'Manage recurring transactions and learned classification memory',
        primaryLabel: 'Recurring',
        primaryTo: '/recurring',
        secondaryLabel: 'Classification Memory',
        secondaryTo: '/classification-rules',
      },
      {
        id: 'tax-tools',
        icon: BarChart3,
        tone: 'emerald',
        title: 'Tax Workspace',
        subtitle: 'Filings, document prep, AI guidance and reports in one place',
        primaryLabel: 'Open Workspace',
        primaryTo: '/tax-tools',
      },
    ],
  },
  zh: {
    title: '\u9ad8\u7ea7\u7ba1\u7406',
    subtitle: '\u8d44\u4ea7\u3001\u8d1f\u503a\u3001\u81ea\u52a8\u5316\u4e0e\u7a0e\u52a1\u5de5\u4f5c\u53f0',
    cards: [
      {
        id: 'assets',
        icon: House,
        tone: 'cyan',
        title: '\u8d44\u4ea7\u8d1f\u503a\u7ba1\u7406',
        subtitle: '\u8d44\u4ea7\u3001\u8d37\u6b3e\u3001\u501f\u6b3e\u4e0e\u6e05\u6670\u7684\u6a21\u5757\u8fb9\u754c',
        primaryLabel: '\u7ba1\u7406\u8d44\u4ea7',
        primaryTo: '/properties',
        secondaryLabel: '\u7ba1\u7406\u8d1f\u503a',
        secondaryTo: '/liabilities',
      },
      {
        id: 'automation',
        icon: Repeat2,
        tone: 'violet',
        title: '\u89c4\u5219\u4e0e\u81ea\u52a8\u5316',
        subtitle: '\u7ba1\u7406\u5b9a\u671f\u4ea4\u6613\u4e0e AI \u5b66\u4e60\u7684\u5206\u7c7b\u8bb0\u5fc6',
        primaryLabel: '\u5b9a\u671f\u4ea4\u6613',
        primaryTo: '/recurring',
        secondaryLabel: '\u5206\u7c7b\u8bb0\u5fc6',
        secondaryTo: '/classification-rules',
      },
      {
        id: 'tax-tools',
        icon: BarChart3,
        tone: 'emerald',
        title: '\u7a0e\u52a1\u5de5\u4f5c\u53f0',
        subtitle: '\u7533\u62a5\u3001\u8d44\u6599\u51c6\u5907\u3001AI \u6d1e\u5bdf\u4e0e\u62a5\u544a\u96c6\u4e2d\u5728\u8fd9\u91cc',
        primaryLabel: '\u6253\u5f00\u5de5\u4f5c\u53f0',
        primaryTo: '/tax-tools',
      },
    ],
  },
  fr: {
    title: 'Gestion avancee',
    subtitle: 'Actifs, dettes, automatisation et espace fiscal',
    cards: [
      {
        id: 'assets',
        icon: House,
        tone: 'cyan',
        title: 'Gestion actif-passif',
        subtitle: 'Actifs, prets, dettes et frontieres de module claires',
        primaryLabel: 'Gerer les actifs',
        primaryTo: '/properties',
        secondaryLabel: 'Gerer les dettes',
        secondaryTo: '/liabilities',
      },
      {
        id: 'automation',
        icon: Repeat2,
        tone: 'violet',
        title: 'Regles et automatisation',
        subtitle: 'Gerer les transactions recurrentes et la memoire de classification',
        primaryLabel: 'Recurrentes',
        primaryTo: '/recurring',
        secondaryLabel: 'Memoire de classification',
        secondaryTo: '/classification-rules',
      },
      {
        id: 'tax-tools',
        icon: BarChart3,
        tone: 'emerald',
        title: 'Espace fiscal',
        subtitle: 'Declarations, preparation, IA et rapports au meme endroit',
        primaryLabel: 'Ouvrir',
        primaryTo: '/tax-tools',
      },
    ],
  },
  ru: {
    title: 'Расширенное управление',
    subtitle: 'Активы, обязательства, автоматизация и налоговое пространство',
    cards: [
      {
        id: 'assets',
        icon: House,
        tone: 'cyan',
        title: 'Управление активами и обязательствами',
        subtitle: 'Активы, кредиты, займы и чёткие границы модулей',
        primaryLabel: 'Управлять активами',
        primaryTo: '/properties',
        secondaryLabel: 'Управлять обязательствами',
        secondaryTo: '/liabilities',
      },
      {
        id: 'automation',
        icon: Repeat2,
        tone: 'violet',
        title: 'Правила и автоматизация',
        subtitle: 'Повторяющиеся транзакции и память классификации',
        primaryLabel: 'Повторяющиеся',
        primaryTo: '/recurring',
        secondaryLabel: 'Память классификации',
        secondaryTo: '/classification-rules',
      },
      {
        id: 'tax-tools',
        icon: BarChart3,
        tone: 'emerald',
        title: 'Налоговое пространство',
        subtitle: 'Отчётность, подготовка документов, ИИ-подсказки и отчёты',
        primaryLabel: 'Открыть',
        primaryTo: '/tax-tools',
      },
    ],
  },
  hu: {
    title: 'Speciális kezelés',
    subtitle: 'Eszközök, kötelezettségek, automatizálás és adó munkaterület',
    cards: [
      {
        id: 'assets',
        icon: House,
        tone: 'cyan',
        title: 'Eszköz- és kötelezettségkezelés',
        subtitle: 'Eszközök, hitelek, kölcsönök és egyértelmű modulhatárok',
        primaryLabel: 'Eszközök kezelése',
        primaryTo: '/properties',
        secondaryLabel: 'Kötelezettségek kezelése',
        secondaryTo: '/liabilities',
      },
      {
        id: 'automation',
        icon: Repeat2,
        tone: 'violet',
        title: 'Szabályok és automatizálás',
        subtitle: 'Ismétlődő tranzakciók és osztályozási memória kezelése',
        primaryLabel: 'Ismétlődő',
        primaryTo: '/recurring',
        secondaryLabel: 'Osztályozási memória',
        secondaryTo: '/classification-rules',
      },
      {
        id: 'tax-tools',
        icon: BarChart3,
        tone: 'emerald',
        title: 'Adó munkaterület',
        subtitle: 'Bevallások, dokumentum-előkészítés, AI tanácsok és jelentések',
        primaryLabel: 'Megnyitás',
        primaryTo: '/tax-tools',
      },
    ],
  },
  pl: {
    title: 'Zarządzanie zaawansowane',
    subtitle: 'Aktywa, zobowiązania, automatyzacja i przestrzeń podatkowa',
    cards: [
      {
        id: 'assets',
        icon: House,
        tone: 'cyan',
        title: 'Zarządzanie aktywami i zobowiązaniami',
        subtitle: 'Aktywa, kredyty, pożyczki i jasne granice modułów',
        primaryLabel: 'Zarządzaj aktywami',
        primaryTo: '/properties',
        secondaryLabel: 'Zarządzaj zobowiązaniami',
        secondaryTo: '/liabilities',
      },
      {
        id: 'automation',
        icon: Repeat2,
        tone: 'violet',
        title: 'Reguły i automatyzacja',
        subtitle: 'Transakcje cykliczne i pamięć klasyfikacji',
        primaryLabel: 'Cykliczne',
        primaryTo: '/recurring',
        secondaryLabel: 'Pamięć klasyfikacji',
        secondaryTo: '/classification-rules',
      },
      {
        id: 'tax-tools',
        icon: BarChart3,
        tone: 'emerald',
        title: 'Przestrzeń podatkowa',
        subtitle: 'Deklaracje, przygotowanie dokumentów, wskazówki AI i raporty',
        primaryLabel: 'Otwórz',
        primaryTo: '/tax-tools',
      },
    ],
  },
  tr: {
    title: 'Gelişmiş Yönetim',
    subtitle: 'Varlıklar, yükümlülükler, otomasyon ve vergi çalışma alanı',
    cards: [
      {
        id: 'assets',
        icon: House,
        tone: 'cyan',
        title: 'Varlık ve Yükümlülük Yönetimi',
        subtitle: 'Varlıklar, krediler, borçlar ve net modül sınırları',
        primaryLabel: 'Varlıkları Yönet',
        primaryTo: '/properties',
        secondaryLabel: 'Yükümlülükleri Yönet',
        secondaryTo: '/liabilities',
      },
      {
        id: 'automation',
        icon: Repeat2,
        tone: 'violet',
        title: 'Kurallar ve Otomasyon',
        subtitle: 'Yinelenen işlemler ve sınıflandırma hafızası yönetimi',
        primaryLabel: 'Yinelenen',
        primaryTo: '/recurring',
        secondaryLabel: 'Sınıflandırma Hafızası',
        secondaryTo: '/classification-rules',
      },
      {
        id: 'tax-tools',
        icon: BarChart3,
        tone: 'emerald',
        title: 'Vergi Çalışma Alanı',
        subtitle: 'Beyannameler, belge hazırlığı, AI önerileri ve raporlar',
        primaryLabel: 'Aç',
        primaryTo: '/tax-tools',
      },
    ],
  },
  bs: {
    title: 'Napredno upravljanje',
    subtitle: 'Imovina, obaveze, automatizacija i porezni prostor',
    cards: [
      {
        id: 'assets',
        icon: House,
        tone: 'cyan',
        title: 'Upravljanje imovinom i obavezama',
        subtitle: 'Imovina, krediti, zajmovi i jasne granice modula',
        primaryLabel: 'Upravljaj imovinom',
        primaryTo: '/properties',
        secondaryLabel: 'Upravljaj obavezama',
        secondaryTo: '/liabilities',
      },
      {
        id: 'automation',
        icon: Repeat2,
        tone: 'violet',
        title: 'Pravila i automatizacija',
        subtitle: 'Ponavljajuće transakcije i memorija klasifikacije',
        primaryLabel: 'Ponavljajuće',
        primaryTo: '/recurring',
        secondaryLabel: 'Memorija klasifikacije',
        secondaryTo: '/classification-rules',
      },
      {
        id: 'tax-tools',
        icon: BarChart3,
        tone: 'emerald',
        title: 'Porezni prostor',
        subtitle: 'Prijave, priprema dokumenata, AI savjeti i izvještaji',
        primaryLabel: 'Otvori',
        primaryTo: '/tax-tools',
      },
    ],
  },
};

const AdvancedManagementPage = () => {
  const { i18n } = useTranslation();
  const language = normalizeLanguage(i18n.resolvedLanguage || i18n.language);
  const c = copy[language] || copy.en;

  return (
    <div className="advanced-page">
      <div className="advanced-header-simple">
        <h1>{c.title}</h1>
        <p>{c.subtitle}</p>
      </div>

      <div className="advanced-grid">
        {c.cards.map((card) => (
          <article key={card.id} className="advanced-card card">
            <div className="advanced-card-icon">
              <FuturisticIcon icon={card.icon} tone={card.tone} size="lg" />
            </div>
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
            </div>
          </article>
        ))}
      </div>
    </div>
  );
};

export default AdvancedManagementPage;
