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
import { sanitizeLocaleResource } from '../i18n/localeSanitizer';

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

const getValue = (value: Record<string, unknown>, key: string): unknown =>
  key.split('.').reduce<unknown>((current, segment) => {
    if (!current || typeof current !== 'object') {
      return undefined;
    }

    return (current as Record<string, unknown>)[segment];
  }, value);

describe('TransactionList reconciliation tooltip i18n', () => {
  it('provides the unreconciled tooltip for all nine supported languages', () => {
    for (const [language, resource] of Object.entries(localeInputs)) {
      const sanitized = sanitizeLocaleResource(language as keyof typeof localeInputs, resource);
      expect(getValue(sanitized, 'transactions.bankReconcileHint'), language).toBeTruthy();
    }
  });

  it('uses the expected copy for core locales', () => {
    expect(
      getValue(
        sanitizeLocaleResource('en', localeInputs.en),
        'transactions.bankReconcileHint'
      )
    ).toBe('Upload bank statements in Documents to reconcile.');

    expect(
      getValue(
        sanitizeLocaleResource('de', localeInputs.de),
        'transactions.bankReconcileHint'
      )
    ).toBe('Bitte laden Sie Bankauszuege unter Dokumente hoch, um abzugleichen.');

    expect(
      getValue(
        sanitizeLocaleResource('zh', localeInputs.zh),
        'transactions.bankReconcileHint'
      )
    ).toBe('请到文档上传银行流水完成对账');
  });
});
