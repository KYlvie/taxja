import type {
  EmployerAnnualArchive,
  EmployerMonth,
} from '../services/employerService';
import { normalizeLanguage, getLocaleForLanguage } from './locale';
import i18n from '../i18n';

type EmployerUiLanguage = 'de' | 'en' | 'zh' | 'fr' | 'ru';

const resolveLanguage = (language?: string): EmployerUiLanguage =>
  normalizeLanguage(language) as EmployerUiLanguage;

export const formatEmployerMoney = (
  value?: number | string | null,
  emptyValue: string | null = '--'
) => {
  if (value === null || value === undefined || value === '') {
    return emptyValue;
  }

  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return emptyValue;
  }

  return numeric.toLocaleString(getLocaleForLanguage(i18n.language), {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
};

export const formatEmployerDate = (
  value?: string | null,
  emptyValue = '--'
) => {
  if (!value) {
    return emptyValue;
  }

  try {
    return new Date(value).toLocaleDateString(getLocaleForLanguage(i18n.language));
  } catch {
    return value;
  }
};

export const formatEmployerDateTime = (
  value?: string | null,
  emptyValue = '--'
) => {
  if (!value) {
    return emptyValue;
  }

  try {
    return new Date(value).toLocaleString(getLocaleForLanguage(i18n.language));
  } catch {
    return value;
  }
};

export const formatEmployerMonthLabel = (
  yearMonth?: string | null,
  emptyValue = '--'
) => {
  if (!yearMonth) {
    return emptyValue;
  }

  const [year, month] = yearMonth.split('-');
  if (!year || !month) {
    return yearMonth;
  }

  try {
    return new Date(Number(year), Number(month) - 1, 1).toLocaleDateString(getLocaleForLanguage(i18n.language), {
      year: 'numeric',
      month: 'long',
    });
  } catch {
    return yearMonth;
  }
};

export const getEmployerMonthStatusLabel = (
  status?: EmployerMonth['status'],
  language?: string
) => {
  const locale = resolveLanguage(language);

  const labels: Record<string, Record<EmployerUiLanguage, string>> = {
    payroll_detected: { de: 'Lohnmonat bestaetigt', en: 'Payroll confirmed', zh: '已确认工资月份', fr: 'Paie confirmée', ru: 'Зарплата подтверждена' },
    missing_confirmation: { de: 'Bestaetigung offen', en: 'Needs confirmation', zh: '待确认', fr: 'Confirmation requise', ru: 'Требуется подтверждение' },
    no_payroll_confirmed: { de: 'Ohne Lohn bestaetigt', en: 'No payroll confirmed', zh: '已确认无工资', fr: 'Sans paie confirmé', ru: 'Без зарплаты подтверждено' },
    archived_year_only: { de: 'Nur Jahresarchiv', en: 'Archive only', zh: '仅年度归档', fr: 'Archive uniquement', ru: 'Только архив' },
  };
  const fallback: Record<EmployerUiLanguage, string> = { de: 'Noch nicht bestaetigt', en: 'Not confirmed yet', zh: '尚未确认', fr: 'Pas encore confirmé', ru: 'Ещё не подтверждено' };
  const entry = (status && labels[status]) || fallback;
  return entry[locale] || entry.en;
};

export const getEmployerAnnualArchiveStatusLabel = (
  status?: EmployerAnnualArchive['status'],
  language?: string
) => {
  const locale = resolveLanguage(language);

  const labels: Record<string, Record<EmployerUiLanguage, string>> = {
    archived: { de: 'Archiviert', en: 'Archived', zh: '已归档', fr: 'Archivé', ru: 'Архивировано' },
  };
  const fallback: Record<EmployerUiLanguage, string> = { de: 'Archiv ausstehend', en: 'Pending archive', zh: '待归档', fr: 'Archivage en attente', ru: 'Ожидает архивации' };
  const entry = (status && labels[status]) || fallback;
  return entry[locale] || entry.en;
};
