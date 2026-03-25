import React from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import RobotMascot from '../common/RobotMascot';
import '../common/ConfirmDialog.css';
import './UpgradePrompt.css';

interface UpgradePromptProps {
  isOpen: boolean;
  onClose: () => void;
  feature: string;
  requiredPlan: 'free' | 'plus' | 'pro';
  featureBenefits?: string[];
}

type SupportedModalLanguage = 'de' | 'en' | 'zh' | 'fr' | 'ru' | 'hu' | 'pl' | 'tr' | 'bs';

interface ModalCopy {
  title: string;
  description: string;
  sectionTitle: string;
  benefits: string[];
  trialNote: string;
}

const TAX_TOOL_COPY: Record<SupportedModalLanguage, ModalCopy> = {
  de: {
    title: 'Auf Pro upgraden fuer Steuerwerkzeuge',
    description: 'Die Erstellung von Steuerformularen und der Export des Steuerpakets sind im Pro-Plan verfuegbar.',
    sectionTitle: 'Mit Pro verfuegbar:',
    benefits: [
      'Oesterreichische Steuerformulare erzeugen',
      'Erzeugte Formular-PDFs drucken oder herunterladen',
      'Jaehrliches Steuerpaket mit Transaktionen und Belegen exportieren',
      'Offene Pruefpunkte vor dem Export direkt kontrollieren',
    ],
    trialNote: 'Starte mit einer 14-taegigen Pro-Testphase.',
  },
  en: {
    title: 'Upgrade to Pro for tax tools',
    description: 'Tax-form generation and annual tax package export are available on the Pro plan.',
    sectionTitle: 'Available with Pro:',
    benefits: [
      'Generate Austrian tax forms',
      'Print or download generated form PDFs',
      'Export an annual tax package with transactions and source documents',
      'Review pending filing items before export',
    ],
    trialNote: 'Start with a 14-day Pro trial.',
  },
  zh: {
    title: '升级到 Pro 使用税务工具',
    description: '税务表格生成与年度税务包导出仅对 Pro 套餐开放。',
    sectionTitle: '升级后可用：',
    benefits: [
      '生成奥地利税务表格',
      '打印或下载已生成的税表 PDF',
      '导出包含交易与原始凭证的年度税务包',
      '导出前直接检查待处理项目',
    ],
    trialNote: '从 14 天 Pro 试用开始。',
  },
  fr: {
    title: 'Passez a Pro pour les outils fiscaux',
    description: 'La generation des formulaires fiscaux et l export du pack fiscal annuel sont disponibles avec le forfait Pro.',
    sectionTitle: 'Disponible avec Pro :',
    benefits: [
      'Generer les formulaires fiscaux autrichiens',
      'Imprimer ou telecharger les PDF generes',
      'Exporter un pack fiscal annuel avec transactions et justificatifs',
      'Verifier les elements en attente avant l export',
    ],
    trialNote: 'Commencez avec un essai Pro de 14 jours.',
  },
  ru: {
    title: 'Перейдите на Pro для налоговых инструментов',
    description: 'Генерация налоговых форм и экспорт годового налогового пакета доступны только в тарифе Pro.',
    sectionTitle: 'Будет доступно в Pro:',
    benefits: [
      'Генерация австрийских налоговых форм',
      'Печать и скачивание PDF с формами',
      'Экспорт годового налогового пакета с операциями и документами',
      'Проверка незавершенных пунктов перед экспортом',
    ],
    trialNote: 'Начните с 14-дневного пробного периода Pro.',
  },
  hu: {
    title: 'Valts Pro csomagra az adoeszkozoekhez',
    description: 'Az adoformak generalasa es az eves adocsomag exportja a Pro csomagban erheto el.',
    sectionTitle: 'Pro csomagban elerheto:',
    benefits: [
      'Osztrak adoformak generalasa',
      'A generalt PDF-ek nyomtatasa vagy letoltese',
      'Eves adocsomag exportalasa tranzakciokkal es forrasdokumentumokkal',
      'Nyitott elemek attekintese export elott',
    ],
    trialNote: 'Indits 14 napos Pro probaidot.',
  },
  pl: {
    title: 'Przejdz na Pro, aby korzystac z narzedzi podatkowych',
    description: 'Generowanie formularzy podatkowych i eksport rocznej paczki podatkowej sa dostepne w planie Pro.',
    sectionTitle: 'Dostepne w Pro:',
    benefits: [
      'Generowanie austriackich formularzy podatkowych',
      'Drukowanie lub pobieranie wygenerowanych PDF-ow',
      'Eksport rocznej paczki podatkowej z transakcjami i dokumentami',
      'Sprawdzenie otwartych pozycji przed eksportem',
    ],
    trialNote: 'Rozpocznij 14-dniowy okres probny Pro.',
  },
  tr: {
    title: 'Vergi araclari icin Pro planina gecin',
    description: 'Vergi formu olusturma ve yillik vergi paketi disa aktarma yalnizca Pro planinda sunulur.',
    sectionTitle: 'Pro ile acilanlar:',
    benefits: [
      'Avusturya vergi formlari olusturma',
      'Olusturulan PDF formlarini yazdirma veya indirme',
      'Islem ve belgelerle yillik vergi paketi disa aktarma',
      'Disa aktarmadan once bekleyen kalemleri inceleme',
    ],
    trialNote: '14 gunluk Pro denemesiyle baslayin.',
  },
  bs: {
    title: 'Predjite na Pro za poreske alate',
    description: 'Generisanje poreskih obrazaca i izvoz godisnjeg poreskog paketa dostupni su u Pro paketu.',
    sectionTitle: 'Dostupno uz Pro:',
    benefits: [
      'Generisanje austrijskih poreskih obrazaca',
      'Stampanje ili preuzimanje generisanih PDF obrazaca',
      'Izvoz godisnjeg poreskog paketa sa transakcijama i dokumentima',
      'Pregled stavki na cekanju prije izvoza',
    ],
    trialNote: 'Pocnite sa 14-dnevnim Pro probnim periodom.',
  },
};

const getNormalizedLanguage = (language?: string): SupportedModalLanguage => {
  const normalized = (language || 'en').split('-')[0].toLowerCase();
  if (normalized in TAX_TOOL_COPY) {
    return normalized as SupportedModalLanguage;
  }
  return 'en';
};

const UpgradePrompt: React.FC<UpgradePromptProps> = ({
  isOpen,
  onClose,
  feature,
  requiredPlan,
  featureBenefits = [],
}) => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();

  if (!isOpen) return null;

  const lang = getNormalizedLanguage(i18n.language);

  const handleUpgrade = () => {
    navigate('/pricing');
    onClose();
  };

  const getPlanName = () => {
    return requiredPlan === 'pro'
      ? t('upgrade.plans.pro', 'Pro')
      : t('upgrade.plans.plus', 'Plus');
  };

  const getFeatureName = () => {
    const featureNames: Record<string, string> = {
      ocr_scanning: t('upgrade.features.ocr_scanning', 'Document scanning'),
      unlimited_ocr: t('upgrade.features.unlimited_ocr', 'Unlimited document scanning'),
      ai_assistant: t('upgrade.features.ai_assistant', 'AI tax assistant'),
      e1_generation: t('upgrade.features.e1_generation', 'Tax tools'),
      advanced_reports: t('upgrade.features.advanced_reports', 'Advanced reports'),
      api_access: t('upgrade.features.api_access', 'API access'),
      unlimited_transactions: t('upgrade.features.unlimited_transactions', 'Unlimited transactions'),
    };

    return featureNames[feature] || feature;
  };

  const fallbackBenefits = requiredPlan === 'pro'
    ? [
      t('upgrade.benefits.pro.1', 'Unlimited document scanning'),
      t('upgrade.benefits.pro.2', 'AI-powered tax assistance'),
      t('upgrade.benefits.pro.3', 'Automatic tax-form generation'),
      t('upgrade.benefits.pro.4', 'Advanced analytics and reports'),
      t('upgrade.benefits.pro.5', 'Priority customer support'),
    ]
    : [
      t('upgrade.benefits.plus.1', 'Unlimited transactions'),
      t('upgrade.benefits.plus.2', '20 document scans per month'),
      t('upgrade.benefits.plus.3', 'Full tax calculations'),
      t('upgrade.benefits.plus.4', 'Multi-language support'),
      t('upgrade.benefits.plus.5', 'VAT & SVS calculations'),
    ];

  const featureCopy = feature === 'e1_generation'
    ? TAX_TOOL_COPY[lang]
    : {
        title: t('upgrade.title', 'Upgrade to {{plan}}', { plan: getPlanName() }),
        description: t(
          'upgrade.description',
          '{{feature}} is available on the {{plan}} plan. Upgrade now to unlock this feature and more!',
          { feature: getFeatureName(), plan: getPlanName() },
        ),
        sectionTitle: t('upgrade.benefits_title', "What you'll get:"),
        benefits: featureBenefits.length > 0 ? featureBenefits : fallbackBenefits,
        trialNote: t('upgrade.trial_note', 'Start with a 14-day free trial of Pro plan'),
      };

  const benefits = featureBenefits.length > 0 ? featureBenefits : featureCopy.benefits;

  return createPortal(
    <div
      className="cfd-robot-overlay upgrade-robot-overlay"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="upgrade-prompt-title"
    >
      <div className="cfd-robot-scene upgrade-robot-scene" onClick={(event) => event.stopPropagation()}>
        <div className="cfd-robot-container upgrade-robot-container">
          <RobotMascot size={360} />
        </div>
        <div className="cfd-robot-bubble cfd-robot-bubble--info upgrade-robot-bubble">
          <div className="upgrade-robot-plan-badge">
            {getPlanName().toUpperCase()}
          </div>
          <button
            className="upgrade-robot-close"
            onClick={onClose}
            type="button"
            aria-label={t('common.close', 'Close')}
          >
            ×
          </button>

          <div className="cfd-robot-bubble-title upgrade-robot-title" id="upgrade-prompt-title">
            {featureCopy.title}
          </div>
          <div className="cfd-robot-bubble-text upgrade-robot-description">
            {featureCopy.description}
          </div>

          <div className="upgrade-robot-benefits">
            <div className="upgrade-robot-benefits-title">{featureCopy.sectionTitle}</div>
            <ul className="upgrade-robot-benefits-list">
              {benefits.map((benefit) => (
                <li key={benefit} className="upgrade-robot-benefit">
                  <span className="upgrade-robot-benefit-icon">✓</span>
                  <span>{benefit}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="cfd-robot-actions cfd-robot-actions--visible">
            <button className="cfd-robot-btn cfd-robot-btn--cancel" onClick={onClose} type="button">
              {t('upgrade.cancel', 'Maybe later')}
            </button>
            <button className="cfd-robot-btn cfd-robot-btn--confirm" onClick={handleUpgrade} type="button">
              {t('upgrade.button', 'Upgrade now')}
            </button>
          </div>

          <div className="upgrade-robot-footnote">{featureCopy.trialNote}</div>
        </div>
      </div>
    </div>,
    document.body,
  );
};

export default UpgradePrompt;
