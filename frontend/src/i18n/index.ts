import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import de from './locales/de.json'
import deSubscription from './locales/de/subscription.json'
import en from './locales/en.json'
import enSubscription from './locales/en/subscription.json'
import zh from './locales/zh.json'
import zhSubscription from './locales/zh/subscription.json'
import { normalizeLanguage } from '../utils/locale'

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
      de: { translation: mergeLocaleResources(de, deSubscription) },
      en: { translation: mergeLocaleResources(en, enSubscription) },
      zh: { translation: mergeLocaleResources(zh, zhSubscription) }
    },
    lng: initialLanguage,
    fallbackLng: 'de',
    supportedLngs: ['de', 'en', 'zh'],
    nonExplicitSupportedLngs: true,
    load: 'languageOnly',
    interpolation: {
      escapeValue: false
    }
  })

syncLanguageState(initialLanguage)
i18n.on('languageChanged', syncLanguageState)

export default i18n
