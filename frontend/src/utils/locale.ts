export const supportedLanguages = ['de', 'en', 'zh', 'fr', 'ru', 'hu', 'pl', 'tr', 'bs'] as const;

export type SupportedLanguage = (typeof supportedLanguages)[number];

export const normalizeLanguage = (language?: string | null): SupportedLanguage => {
  const baseLanguage = language?.split('-')[0]?.toLowerCase();

  return supportedLanguages.includes(baseLanguage as SupportedLanguage)
    ? (baseLanguage as SupportedLanguage)
    : 'de';
};

export const getLocaleForLanguage = (language?: string | null): string => {
  switch (normalizeLanguage(language)) {
    case 'en':
      return 'en-GB';
    case 'zh':
      return 'zh-CN';
    case 'fr':
      return 'fr-FR';
    case 'ru':
      return 'ru-RU';
    case 'hu':
      return 'hu-HU';
    case 'pl':
      return 'pl-PL';
    case 'tr':
      return 'tr-TR';
    case 'bs':
      return 'bs-BA';
    case 'de':
    default:
      return 'de-AT';
  }
};

export const formatCurrency = (amount: number, language?: string | null): string =>
  new Intl.NumberFormat(getLocaleForLanguage(language), {
    style: 'currency',
    currency: 'EUR',
  }).format(amount);

export const formatDate = (
  value: string | Date,
  language?: string | null,
  options: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  }
): string => {
  const date = value instanceof Date ? value : new Date(value);
  return new Intl.DateTimeFormat(getLocaleForLanguage(language), options).format(date);
};

export const formatNumber = (
  value: number,
  language?: string | null,
  options?: Intl.NumberFormatOptions
): string =>
  new Intl.NumberFormat(getLocaleForLanguage(language), options).format(value);

export const getShortMonthLabels = (language?: string | null): string[] =>
  Array.from({ length: 12 }, (_, month) =>
    new Intl.DateTimeFormat(getLocaleForLanguage(language), {
      month: 'short',
    }).format(new Date(2026, month, 1))
  );
