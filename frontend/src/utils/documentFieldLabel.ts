import type { TFunction } from 'i18next';

const STRIP_EDGE_PUNCTUATION = /^[\s"'`\[\](){}<>]+|[\s"'`\[\](){}<>]+$/g;
const SURROUNDED_FIELD_PATTERN =
  /(["'“”‘’「」『』【】\[\](){}<>])([A-Za-z][A-Za-z0-9_ ]{1,80})(["'“”‘’「」『』【】\[\](){}<>])/g;
const MISSING_FIELDS_PATTERN =
  /\b(Missing:\s*)([A-Za-z][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z][A-Za-z0-9_]*)+)/g;

const DOCUMENT_FIELD_LABEL_ALIASES: Record<string, string[]> = {
  transaction_type: ['documents.review.transactionType'],
  document_type: ['documents.documentType'],
  user_contract_role: ['documents.review.fields.myRole'],
};

export const normalizeDocumentFieldKey = (fieldName: string): string => {
  const stripped = fieldName.trim().replace(STRIP_EDGE_PUNCTUATION, '');

  if (!stripped) {
    return '';
  }

  const normalized = stripped
    .replace(/([a-z\d])([A-Z])/g, '$1_$2')
    .replace(/[^A-Za-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .toLowerCase();

  const kzMatch = normalized.match(/^[fk]z_(\d+)$/i);
  if (kzMatch) {
    return `kz_${kzMatch[1]}`;
  }

  return normalized;
};

const humanizeDocumentFieldName = (fieldName: string): string => {
  const stripped = fieldName.trim().replace(STRIP_EDGE_PUNCTUATION, '');
  const source = stripped || fieldName;

  return source
    .replace(/([a-z\d])([A-Z])/g, '$1 $2')
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase());
};

export const formatDocumentFieldLabel = (fieldName: string, t: TFunction): string => {
  const normalized = normalizeDocumentFieldKey(fieldName);

  if (normalized) {
    const candidates = [
      ...(DOCUMENT_FIELD_LABEL_ALIASES[normalized] ?? []),
      `documents.review.taxFieldLabels.${normalized}`,
      `documents.suggestion.fields.${normalized}`,
    ];

    for (const key of candidates) {
      const translated = t(key, '');
      if (typeof translated === 'string' && translated && translated !== key) {
        return translated;
      }
    }

    if (/^kz_\d+$/i.test(normalized)) {
      return normalized.toUpperCase().replace('_', ' ');
    }
  }

  return humanizeDocumentFieldName(fieldName);
};

export const formatDocumentFieldList = (fields: string[], t: TFunction): string =>
  fields.map((field) => formatDocumentFieldLabel(field, t)).join(', ');

export const translateDocumentSuggestionText = (text: string, t: TFunction): string =>
  text
    .replace(
      SURROUNDED_FIELD_PATTERN,
      (_match: string, opening: string, fieldName: string, closing: string) =>
        `${opening}${formatDocumentFieldLabel(fieldName, t)}${closing}`,
    )
    .replace(
      MISSING_FIELDS_PATTERN,
      (_match: string, prefix: string, fields: string) =>
        `${prefix}${formatDocumentFieldList(
          fields.split(',').map((field) => field.trim()).filter(Boolean),
          t,
        )}`,
    );
