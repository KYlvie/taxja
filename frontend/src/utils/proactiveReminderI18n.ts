type TranslationFn = (key: string, options?: Record<string, unknown>) => string;

const translateFromCandidates = (
  candidates: string[],
  t: TranslationFn
): string | undefined => {
  for (const candidate of candidates) {
    const translated = t(candidate);
    if (translated && translated !== candidate) {
      return translated;
    }
  }

  return undefined;
};

const translateReminderParamValue = (
  key: string,
  value: unknown,
  t: TranslationFn
): unknown => {
  if (Array.isArray(value)) {
    return value.map((entry) => translateReminderParamValue(key, entry, t));
  }

  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([nestedKey, nestedValue]) => [
        nestedKey,
        translateReminderParamValue(nestedKey, nestedValue, t),
      ])
    );
  }

  if (typeof value !== 'string') {
    return value;
  }

  const candidates: string[] = [];

  if (value.includes('.')) {
    candidates.push(value);
  }

  if (key === 'document_type') {
    candidates.push(`healthCheck.documentTypes.${value}`);
    candidates.push(`documents.types.${value}`);
  }

  const translated = translateFromCandidates(candidates, t);
  return translated ?? value;
};

export const translateReminderParams = (
  params: Record<string, unknown> | undefined,
  t: TranslationFn
): Record<string, unknown> => {
  if (!params) {
    return {};
  }

  return Object.fromEntries(
    Object.entries(params).map(([key, value]) => [
      key,
      translateReminderParamValue(key, value, t),
    ])
  );
};

export const translateReminderContent = (
  bodyKey: string,
  params: Record<string, unknown> | undefined,
  t: TranslationFn
): string => t(bodyKey, translateReminderParams(params, t));
