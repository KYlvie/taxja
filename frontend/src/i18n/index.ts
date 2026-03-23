import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import de from './locales/de.json'
import deSubscription from './locales/de/subscription.json'
import en from './locales/en.json'
import enSubscription from './locales/en/subscription.json'
import zh from './locales/zh.json'
import zhSubscription from './locales/zh/subscription.json'
import fr from './locales/fr.json'
import frSubscription from './locales/fr/subscription.json'
import ru from './locales/ru.json'
import ruSubscription from './locales/ru/subscription.json'
import hu from './locales/hu.json'
import huSubscription from './locales/hu/subscription.json'
import pl from './locales/pl.json'
import plSubscription from './locales/pl/subscription.json'
import tr from './locales/tr.json'
import trSubscription from './locales/tr/subscription.json'
import bs from './locales/bs.json'
import bsSubscription from './locales/bs/subscription.json'
import { normalizeLanguage } from '../utils/locale'
import { sanitizeLocaleResource } from './localeSanitizer'

const mergeLocaleResources = (
  base: Record<string, unknown>,
  extra: Record<string, unknown>
): Record<string, unknown> => {
  const merged: Record<string, unknown> = { ...base }

  Object.entries(extra).forEach(([key, value]) => {
    const existing = merged[key]
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
      )
      return
    }

    merged[key] = value
  })

  return merged
}

const getInitialLanguage = (): string =>
  normalizeLanguage(localStorage.getItem('language') || navigator.language)

const syncLanguageState = (language: string) => {
  const normalizedLanguage = normalizeLanguage(language)
  localStorage.setItem('language', normalizedLanguage)
  document.documentElement.lang = normalizedLanguage
}

const initialLanguage = getInitialLanguage()

i18n
  .use(initReactI18next)
  .init({
    resources: {
      de: { translation: sanitizeLocaleResource('de', mergeLocaleResources(de, deSubscription)) },
      en: { translation: sanitizeLocaleResource('en', mergeLocaleResources(en, enSubscription)) },
      zh: { translation: sanitizeLocaleResource('zh', mergeLocaleResources(zh, zhSubscription)) },
      fr: { translation: sanitizeLocaleResource('fr', mergeLocaleResources(fr, frSubscription)) },
      ru: { translation: sanitizeLocaleResource('ru', mergeLocaleResources(ru, ruSubscription)) },
      hu: { translation: sanitizeLocaleResource('hu', mergeLocaleResources(hu, huSubscription)) },
      pl: { translation: sanitizeLocaleResource('pl', mergeLocaleResources(pl, plSubscription)) },
      tr: { translation: sanitizeLocaleResource('tr', mergeLocaleResources(tr, trSubscription)) },
      bs: { translation: sanitizeLocaleResource('bs', mergeLocaleResources(bs, bsSubscription)) }
    },
    lng: initialLanguage,
    fallbackLng: 'de',
    supportedLngs: ['de', 'en', 'zh', 'fr', 'ru', 'hu', 'pl', 'tr', 'bs'],
    nonExplicitSupportedLngs: true,
    load: 'languageOnly',
    interpolation: {
      escapeValue: false
    }
  })

syncLanguageState(initialLanguage)
i18n.on('languageChanged', syncLanguageState)

export default i18n
