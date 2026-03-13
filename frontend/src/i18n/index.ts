import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import de from './locales/de.json'
import en from './locales/en.json'
import zh from './locales/zh.json'

// Detect browser language on first visit
const getBrowserLanguage = (): string => {
  const browserLang = navigator.language.split('-')[0]
  const supportedLanguages = ['de', 'en', 'zh']
  return supportedLanguages.includes(browserLang) ? browserLang : 'de'
}

i18n
  .use(initReactI18next)
  .init({
    resources: {
      de: { translation: de },
      en: { translation: en },
      zh: { translation: zh }
    },
    lng: localStorage.getItem('language') || getBrowserLanguage(),
    fallbackLng: 'de',
    interpolation: {
      escapeValue: false
    }
  })

export default i18n
