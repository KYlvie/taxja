import { describe, expect, it } from 'vitest';

import de from '../i18n/locales/de.json';
import deSubscription from '../i18n/locales/de/subscription.json';
import en from '../i18n/locales/en.json';
import enSubscription from '../i18n/locales/en/subscription.json';
import zh from '../i18n/locales/zh.json';
import zhSubscription from '../i18n/locales/zh/subscription.json';
import fr from '../i18n/locales/fr.json';
import frSubscription from '../i18n/locales/fr/subscription.json';
import ru from '../i18n/locales/ru.json';
import ruSubscription from '../i18n/locales/ru/subscription.json';
import hu from '../i18n/locales/hu.json';
import huSubscription from '../i18n/locales/hu/subscription.json';
import pl from '../i18n/locales/pl.json';
import plSubscription from '../i18n/locales/pl/subscription.json';
import tr from '../i18n/locales/tr.json';
import trSubscription from '../i18n/locales/tr/subscription.json';
import bs from '../i18n/locales/bs.json';
import bsSubscription from '../i18n/locales/bs/subscription.json';
import { repairMojibakeText, sanitizeLocaleResource } from '../i18n/localeSanitizer';
import { supportedLanguages } from '../utils/locale';

const mergeLocaleResources = (
  base: Record<string, unknown>,
  extra: Record<string, unknown>
): Record<string, unknown> => {
  const merged: Record<string, unknown> = { ...base };

  Object.entries(extra).forEach(([key, value]) => {
    const existing = merged[key];
    if (
      existing &&
      value &&
      typeof existing === 'object' &&
      typeof value === 'object' &&
      !Array.isArray(existing) &&
      !Array.isArray(value)
    ) {
      merged[key] = mergeLocaleResources(
        existing as Record<string, unknown>,
        value as Record<string, unknown>
      );
      return;
    }

    merged[key] = value;
  });

  return merged;
};

const localeInputs = {
  de: mergeLocaleResources(de, deSubscription),
  en: mergeLocaleResources(en, enSubscription),
  zh: mergeLocaleResources(zh, zhSubscription),
  fr: mergeLocaleResources(fr, frSubscription),
  ru: mergeLocaleResources(ru, ruSubscription),
  hu: mergeLocaleResources(hu, huSubscription),
  pl: mergeLocaleResources(pl, plSubscription),
  tr: mergeLocaleResources(tr, trSubscription),
  bs: mergeLocaleResources(bs, bsSubscription),
};

const locales = {
  de: sanitizeLocaleResource('de', localeInputs.de),
  en: sanitizeLocaleResource('en', localeInputs.en),
  zh: sanitizeLocaleResource('zh', localeInputs.zh),
  fr: sanitizeLocaleResource('fr', localeInputs.fr),
  ru: sanitizeLocaleResource('ru', localeInputs.ru),
  hu: sanitizeLocaleResource('hu', localeInputs.hu),
  pl: sanitizeLocaleResource('pl', localeInputs.pl),
  tr: sanitizeLocaleResource('tr', localeInputs.tr),
  bs: sanitizeLocaleResource('bs', localeInputs.bs),
};

const getValue = (value: Record<string, unknown>, key: string): unknown =>
  key.split('.').reduce<unknown>((current, segment) => {
    if (!current || typeof current !== 'object') {
      return undefined;
    }

    return (current as Record<string, unknown>)[segment];
  }, value);

const collectStringValues = (value: unknown): string[] => {
  if (typeof value === 'string') {
    return [value];
  }

  if (Array.isArray(value)) {
    return value.flatMap(collectStringValues);
  }

  if (value && typeof value === 'object') {
    return Object.values(value).flatMap(collectStringValues);
  }

  return [];
};

const collectLeafKeys = (value: unknown, prefix = ''): string[] => {
  if (Array.isArray(value) || typeof value !== 'object' || value === null) {
    return prefix ? [prefix] : [];
  }

  return Object.entries(value).flatMap(([key, nestedValue]) =>
    collectLeafKeys(nestedValue, prefix ? `${prefix}.${key}` : key)
  );
};

describe('localeSanitizer', () => {
  it('repairs common cp1252 control-character corruption', () => {
    expect(repairMojibakeText('Valeur du b\u00e2timent (\u0080)')).toBe('Valeur du b\u00e2timent (\u20ac)');
    expect(repairMojibakeText('Symulator \u0084Co je\u015bli\u0094')).toBe('Symulator \u201eCo je\u015bli\u201d');
    expect(repairMojibakeText('Fran\u00c3\u00a7ais')).toBe('Fran\u00e7ais');
  });

  it('provides required keys for all supported locales on localized asset/liability pages', () => {
    const requiredKeys = [
      'properties.pendingDocuments.title',
      'properties.pendingDocuments.hint',
      'properties.pendingDocuments.needsInput',
      'properties.pendingDocuments.missingFields',
      'properties.pendingDocuments.awaitingConfirmation',
      'properties.pendingDocuments.openSourceDocument',
      'liabilities.overview.pageTitle',
      'taxTools.page.transactionsSummary',
      'taxTools.page.txnIncome',
      'taxTools.page.txnExpense',
      'taxTools.page.txnDeductible',
      'tour.taxTools.employer.title',
      'tour.taxTools.employer.message',
      'tour.taxTools.audit.title',
      'tour.taxTools.audit.message',
      'tour.taxTools.assetReport.title',
      'tour.taxTools.assetReport.message',
      'documents.reviewAction',
      'documents.reviewActionHint',
      'documents.confirmReview',
      'documents.exportZipYearHint',
      'documents.exportZipNoYears',
      'documents.fileYearLabel',
      'documents.filesLabel',
      'documents.estimatedSizeLabel',
      'documents.exportZipLargeHint',
      'documents.exportZipDirectDownloadHint',
      'documents.receiptReview.editing',
      'documents.receiptReview.expandDetails',
      'documents.receiptReview.hideDetails',
      'documents.receiptReview.linkedTransactionShort',
      'documents.bankWorkbench.mode.import',
      'documents.bankWorkbench.mode.extracted',
      'documents.bankWorkbench.fallbackSummaryTitle',
      'documents.bankWorkbench.localFallbackNotice',
      'documents.bankWorkbench.fallbackTransactionsTitle',
      'documents.bankWorkbench.fallbackTransactionsDescription',
      'documents.bankWorkbench.noExtractedTransactions',
      'documents.bankWorkbench.accountHolder',
      'documents.bankWorkbench.taxYear',
      'documents.bankWorkbench.openingBalance',
      'documents.bankWorkbench.closingBalance',
      'documents.bankWorkbench.creditCount',
      'documents.bankWorkbench.debitCount',
      'documents.bankWorkbench.direction.label',
      'documents.bankWorkbench.direction.credit',
      'documents.bankWorkbench.direction.debit',
      'documents.bankWorkbench.direction.unknown',
      'documents.bankWorkbench.actions.undoCreate',
      'documents.bankWorkbench.actions.unmatch',
      'documents.bankWorkbench.fallback.createdOne',
      'documents.bankWorkbench.fallback.createdMany',
      'documents.bankWorkbench.fallback.alreadyImportedOne',
      'documents.bankWorkbench.fallback.alreadyImportedMany',
      'documents.bankWorkbench.fallback.noTransactionsCreated',
      'documents.review.taxFieldLabels.issuer',
      'documents.review.taxFieldLabels.recipient',
      'documents.review.taxFieldLabels.document_date',
      'documents.review.taxFieldLabels.document_year',
      'documents.review.taxFieldLabels.year_basis',
      'documents.review.taxFieldLabels.year_confidence',
      'documents.review.taxFieldLabels.bescheid_datum',
      'documents.review.taxFieldLabels.faellig_am',
      'common.oneClickConfirm',
      'common.bulkConfirmSuccess',
      'reports.taxForm.exportPackage',
      'reports.taxForm.exportPackageLoading',
      'reports.taxForm.exportPackageFailed',
      'transactions.exportCsv',
      'transactions.exportPdf',
      'classificationRules.searchPlaceholder',
      'classificationRules.searchDeductPlaceholder',
      'classificationRules.pageTitle',
      'classificationRules.title',
      'classificationRules.categorySectionDescription',
      'classificationRules.automationSectionTitle',
      'classificationRules.searchAutomationPlaceholder',
      'classificationRules.automationActionAutoCreate',
      'ai.proactive.healthSummaryReminder',
    ];

    for (const locale of Object.values(locales)) {
      for (const key of requiredKeys) {
        expect(getValue(locale, key), `${key} should exist`).toBeTruthy();
      }
    }
  });

  it('does not leave common mojibake markers in sanitized locales', () => {
    const mojibakePattern = /(Ã|Â|â€|â€“|â€”|â€¦|�)/;

    for (const [language, locale] of Object.entries(locales)) {
      for (const text of collectStringValues(locale)) {
        expect(text, `${language} locale still contains mojibake: ${text}`).not.toMatch(mojibakePattern);
      }
    }
  });

  it('returns repaired and patched values after sanitization', () => {
    expect(getValue(locales.de, 'properties.purchasePrice')).toBe('Kaufpreis (\u20ac)');
    expect(getValue(locales.fr, 'properties.purchasePrice')).toBe("Prix d'achat (\u20ac)");
    expect(getValue(locales.fr, 'liabilities.documents.pendingHint')).toBe(
      'Les contrats confirm\u00e9s deviennent automatiquement des dettes. Les contrats encore en r\u00e9vision ou avec des champs manquants restent ici jusqu\u2019\u00e0 ce que vous les terminiez dans Documents.'
    );
    expect(getValue(locales.zh, 'tour.taxTools.employer.title')).toBe('\u96c7\u4e3b\u7a0e\u52a1\u8bc1\u660e');
    expect(getValue(locales.zh, 'documents.bankWorkbench.mode.import')).toBe(
      '\u5bfc\u5165\u5de5\u4f5c\u53f0'
    );
    expect(getValue(locales.zh, 'common.oneClickConfirm')).toBe('\u4e00\u952e\u786e\u8ba4');
    expect(getValue(locales.zh, 'documents.filters.needsReview')).toBe('\u5f85\u5ba1\u6838');
    expect(getValue(locales.zh, 'transactions.filters.needsReviewOnly')).toBe('\u4ec5\u770b\u5f85\u5ba1\u6838');
    expect(getValue(locales.zh, 'documents.bankWorkbench.creditCount')).toBe(
      '\u6536\u5165\u7b14\u6570'
    );
    expect(getValue(locales.zh, 'documents.review.taxFieldLabels.issuer')).toBe('\u5f00\u7968\u65b9');
    expect(getValue(locales.zh, 'documents.review.taxFieldLabels.recipient')).toBe('\u6536\u7968\u65b9');
    expect(getValue(locales.zh, 'documents.review.taxFieldLabels.document_date')).toBe('\u6587\u4ef6\u65e5\u671f');
    expect(getValue(locales.zh, 'documents.review.taxFieldLabels.document_year')).toBe('\u5f52\u5c5e\u5e74\u4efd');
    expect(getValue(locales.zh, 'documents.review.taxFieldLabels.year_basis')).toBe('\u5e74\u4efd\u4f9d\u636e');
    expect(getValue(locales.zh, 'documents.review.taxFieldLabels.year_confidence')).toBe('\u5e74\u4efd\u7f6e\u4fe1\u5ea6');
    expect(getValue(locales.zh, 'documents.review.taxFieldLabels.bescheid_datum')).toBe('\u7a0e\u5355\u65e5\u671f');
    expect(getValue(locales.zh, 'documents.review.taxFieldLabels.aktenzahl')).toBe('\u6848\u53f7');
    expect(getValue(locales.zh, 'documents.review.taxFieldLabels.faellig_am')).toBe('\u5230\u671f\u65e5');
    expect(getValue(locales.zh, 'documents.exportZipYearHint')).toBe(
      '\u8bf7\u9009\u62e9\u8981\u5bfc\u51fa\u7684\u6587\u4ef6\u5e74\u5ea6\u3002\u8fd9\u91cc\u4f7f\u7528\u6587\u6863\u5f52\u5c5e\u5e74\u4efd\uff0c\u800c\u4e0d\u662f\u4e0a\u4f20\u5e74\u4efd\u3002'
    );
    expect(getValue(locales.de, 'documents.reviewAction')).toBe('Weiter pruefen');
    expect(getValue(locales.de, 'documents.reviewActionHint')).toBe('Klicken, um die Bestaetigung abzuschliessen');
    expect(getValue(locales.de, 'classificationRules.automationSectionTitle')).toBe('Regeln zur automatischen Verarbeitung');
    expect(getValue(locales.en, 'documents.reviewAction')).toBe('Continue review');
    expect(getValue(locales.en, 'documents.reviewActionHint')).toBe('Click to complete confirmation');
    expect(getValue(locales.en, 'documents.review.taxFieldLabels.document_year')).toBe('Document year');
    expect(getValue(locales.en, 'documents.review.taxFieldLabels.bescheid_datum')).toBe('Assessment date');
    expect(getValue(locales.en, 'documents.review.taxFieldLabels.aktenzahl')).toBe('Reference number');
    expect(getValue(locales.en, 'documents.review.taxFieldLabels.faellig_am')).toBe('Due date');
    expect(getValue(locales.en, 'classificationRules.automationActionAutoCreate')).toBe('Auto-create');
    expect(getValue(locales.en, 'reports.taxForm.exportPackage')).toBe('Export tax package');
    expect(getValue(locales.zh, 'documents.confirmReview')).toBe('\u786e\u8ba4\u5b8c\u6210\u5ba1\u6838\uff1f');
    expect(getValue(locales.zh, 'documents.reviewActionHint')).toBe('\u70b9\u51fb\u5b8c\u6210\u786e\u8ba4');
    expect(getValue(locales.zh, 'classificationRules.automationSectionTitle')).toBe('\u81ea\u52a8\u5904\u7406\u89c4\u5219');
    expect(getValue(locales.zh, 'reports.taxForm.exportPackage')).toBe('\u5bfc\u51fa\u7a0e\u52a1\u5305');
    expect(getValue(locales.fr, 'documents.reviewAction')).toBe('Poursuivre la verification');
    expect(getValue(locales.fr, 'documents.reviewActionHint')).toBe('Cliquer pour terminer la confirmation');
    expect(getValue(locales.ru, 'documents.confirmReview')).toBe(
      '\u0417\u0430\u0432\u0435\u0440\u0448\u0438\u0442\u044c \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0443?'
    );
    expect(getValue(locales.ru, 'documents.reviewActionHint')).toBe(
      '\u041d\u0430\u0436\u043c\u0438\u0442\u0435, \u0447\u0442\u043e\u0431\u044b \u0437\u0430\u0432\u0435\u0440\u0448\u0438\u0442\u044c \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u0435'
    );
    expect(getValue(locales.hu, 'documents.reviewAction')).toBe('Ellenorzes folytatasa');
    expect(getValue(locales.hu, 'documents.reviewActionHint')).toBe('Kattintson a jovahagyas befejezesehez');
    expect(getValue(locales.pl, 'tour.taxTools.audit.title')).toBe('Lista kontrolna audytu');
    expect(getValue(locales.pl, 'documents.confirmReview')).toBe('Zakonczyc przeglad?');
    expect(getValue(locales.pl, 'documents.reviewActionHint')).toBe('Kliknij, aby zakonczyc potwierdzenie');
    expect(getValue(locales.tr, 'transactions.exportCsv')).toBe('CSV olarak disa aktar');
    expect(getValue(locales.tr, 'documents.reviewAction')).toBe('Incelemeye devam et');
    expect(getValue(locales.tr, 'documents.reviewActionHint')).toBe('Onayi tamamlamak icin tiklayin');
    expect(getValue(locales.bs, 'documents.confirmReview')).toBe('Zavrsiti pregled?');
    expect(getValue(locales.bs, 'documents.reviewActionHint')).toBe('Kliknite da dovrsite potvrdu');
    expect(getValue(locales.de, 'reports.taxForm.exportPackage')).toBe('Steuerpaket exportieren');
    expect(getValue(locales.zh, 'ai.proactive.healthSummaryReminder')).toBe(
      '\u60a8\u6709 {{count}} \u9879\u7a0e\u52a1\u5065\u5eb7\u63d0\u9192\u5f85\u5904\u7406\uff0c\u5f53\u524d\u5065\u5eb7\u5206\u4e3a {{score}} \u5206\u3002'
    );
  });

  it('keeps the full merged locale tree aligned across all nine supported languages', () => {
    expect(supportedLanguages).toEqual(['de', 'en', 'zh', 'fr', 'ru', 'hu', 'pl', 'tr', 'bs']);

    const localeEntries = Object.entries(locales);
    expect(localeEntries).toHaveLength(supportedLanguages.length);

    const [baselineLanguage, baselineLocale] = localeEntries[0];
    const baselineKeys = new Set(collectLeafKeys(baselineLocale));

    for (const [language, locale] of localeEntries) {
      const localeKeys = new Set(collectLeafKeys(locale));
      expect(localeKeys.size, `${language} key count should match ${baselineLanguage}`).toBe(baselineKeys.size);
      expect([...localeKeys].sort(), `${language} keys should match ${baselineLanguage}`).toEqual(
        [...baselineKeys].sort()
      );
    }
  });
});
