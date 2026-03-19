import type {
  EmployerAnnualArchive,
  EmployerMonth,
} from '../services/employerService';
import { normalizeLanguage } from './locale';

type EmployerUiLanguage = 'de' | 'en' | 'zh';

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

  return numeric.toLocaleString('de-AT', {
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
    return new Date(value).toLocaleDateString('de-AT');
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
    return new Date(value).toLocaleString('de-AT');
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
    return new Date(Number(year), Number(month) - 1, 1).toLocaleDateString('de-AT', {
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

  switch (status) {
    case 'payroll_detected':
      return locale === 'zh'
        ? '已确认工资月份'
        : locale === 'de'
          ? 'Lohnmonat bestaetigt'
          : 'Payroll confirmed';
    case 'missing_confirmation':
      return locale === 'zh'
        ? '待确认'
        : locale === 'de'
          ? 'Bestaetigung offen'
          : 'Needs confirmation';
    case 'no_payroll_confirmed':
      return locale === 'zh'
        ? '已确认无工资'
        : locale === 'de'
          ? 'Ohne Lohn bestaetigt'
          : 'No payroll confirmed';
    case 'archived_year_only':
      return locale === 'zh'
        ? '仅年度归档'
        : locale === 'de'
          ? 'Nur Jahresarchiv'
          : 'Archive only';
    default:
      return locale === 'zh'
        ? '尚未确认'
        : locale === 'de'
          ? 'Noch nicht bestaetigt'
          : 'Not confirmed yet';
  }
};

export const getEmployerAnnualArchiveStatusLabel = (
  status?: EmployerAnnualArchive['status'],
  language?: string
) => {
  const locale = resolveLanguage(language);

  if (status === 'archived') {
    return locale === 'zh'
      ? '已归档'
      : locale === 'de'
        ? 'Archiviert'
        : 'Archived';
  }

  return locale === 'zh'
    ? '待归档'
    : locale === 'de'
      ? 'Archiv ausstehend'
      : 'Pending archive';
};
