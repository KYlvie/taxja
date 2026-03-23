type TranslateFn = (...args: any[]) => any;

export function normalizeTransactionCategoryKey(category?: string | null): string {
  const normalized = String(category || '').trim();
  if (!normalized) {
    return '';
  }

  const enumValue = normalized.includes('.')
    ? normalized.split('.').slice(-1)[0] || normalized
    : normalized;

  return enumValue
    .trim()
    .replace(/[\s/-]+/g, '_')
    .replace(/_+/g, '_')
    .toLowerCase();
}

export function humanizeTransactionCategoryKey(category?: string | null): string {
  const normalized = normalizeTransactionCategoryKey(category);
  if (!normalized) {
    return '';
  }

  return normalized
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

export function formatTransactionCategoryLabel(
  category: string | null | undefined,
  t: TranslateFn,
): string {
  const normalized = normalizeTransactionCategoryKey(category);
  if (!normalized) {
    return '';
  }

  const fallbackLabel = humanizeTransactionCategoryKey(normalized);
  const translated = t(`transactions.categories.${normalized}`, { defaultValue: fallbackLabel });

  if (translated && translated !== `transactions.categories.${normalized}`) {
    return translated;
  }

  return fallbackLabel;
}
