import { describe, expect, it } from 'vitest';

import de from '../i18n/locales/de.json';
import en from '../i18n/locales/en.json';
import zh from '../i18n/locales/zh.json';
import fr from '../i18n/locales/fr.json';
import ru from '../i18n/locales/ru.json';
import hu from '../i18n/locales/hu.json';
import pl from '../i18n/locales/pl.json';
import tr from '../i18n/locales/tr.json';
import bs from '../i18n/locales/bs.json';
import { repairMojibakeText, sanitizeLocaleResource } from '../i18n/localeSanitizer';

const locales = {
  de: sanitizeLocaleResource('de', de),
  en: sanitizeLocaleResource('en', en),
  zh: sanitizeLocaleResource('zh', zh),
  fr: sanitizeLocaleResource('fr', fr),
  ru: sanitizeLocaleResource('ru', ru),
  hu: sanitizeLocaleResource('hu', hu),
  pl: sanitizeLocaleResource('pl', pl),
  tr: sanitizeLocaleResource('tr', tr),
  bs: sanitizeLocaleResource('bs', bs),
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
      'transactions.exportCsv',
      'transactions.exportPdf',
      'classificationRules.searchPlaceholder',
      'classificationRules.searchDeductPlaceholder',
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
    expect(getValue(locales.pl, 'tour.taxTools.audit.title')).toBe('Lista kontrolna audytu');
    expect(getValue(locales.tr, 'transactions.exportCsv')).toBe('CSV olarak disa aktar');
    expect(getValue(locales.zh, 'ai.proactive.healthSummaryReminder')).toBe(
      '\u60a8\u6709 {{count}} \u9879\u7a0e\u52a1\u5065\u5eb7\u63d0\u9192\u5f85\u5904\u7406\uff0c\u5f53\u524d\u5065\u5eb7\u5206\u4e3a {{score}} \u5206\u3002'
    );
  });
});
