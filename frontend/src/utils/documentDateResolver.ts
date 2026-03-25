/**
 * Resolve the effective document date from OCR result.
 *
 * If multiple valid dates exist in OCR output, use the earliest one so
 * ranged documents such as bank statements are grouped by their starting period.
 * Falls back to created_at when no valid OCR date is found.
 */

type DocumentDateLike = {
  ocr_result?: Record<string, unknown> | null;
  created_at: string;
  document_date?: string | null;
  document_year?: number | null;
};

const DATE_FIELDS = [
  'document_date',
  'date',
  'invoice_date',
  'receipt_date',
  'purchase_date',
  'start_date',
  'end_date',
  'period_start',
  'period_end',
  'statement_period',
] as const;

const ISO_DATE_RE = /\b(\d{4})[./-](\d{1,2})[./-](\d{1,2})\b/g;
const DMY_DATE_RE = /\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b/g;

const toValidDate = (year: number, month: number, day: number): Date | null => {
  const parsed = new Date(Date.UTC(year, month - 1, day));
  if (
    parsed.getUTCFullYear() !== year ||
    parsed.getUTCMonth() !== month - 1 ||
    parsed.getUTCDate() !== day
  ) {
    return null;
  }
  return parsed;
};

const extractDatesFromString = (value: string): Date[] => {
  const direct = new Date(value);
  const extracted: Date[] = [];

  for (const match of value.matchAll(ISO_DATE_RE)) {
    const parsed = toValidDate(Number(match[1]), Number(match[2]), Number(match[3]));
    if (parsed) extracted.push(parsed);
  }

  for (const match of value.matchAll(DMY_DATE_RE)) {
    const parsed = toValidDate(Number(match[3]), Number(match[2]), Number(match[1]));
    if (parsed) extracted.push(parsed);
  }

  if (extracted.length > 0) {
    return extracted;
  }

  return Number.isNaN(direct.getTime()) ? [] : [direct];
};

const extractDatesFromUnknown = (value: unknown): Date[] => {
  if (typeof value === 'string') {
    return extractDatesFromString(value);
  }

  if (value && typeof value === 'object') {
    const objectValue = value as Record<string, unknown>;
    const nestedDates: Date[] = [];
    for (const key of ['start', 'end']) {
      nestedDates.push(...extractDatesFromUnknown(objectValue[key]));
    }
    return nestedDates;
  }

  return [];
};

const resolveMaterializedDocumentDate = (doc: DocumentDateLike): Date | null => {
  if (typeof doc.document_date === 'string') {
    const topLevelDates = extractDatesFromString(doc.document_date);
    if (topLevelDates.length > 0) {
      return topLevelDates[0];
    }
  }

  const ocr = doc.ocr_result;
  const candidates: Date[] = [];

  if (ocr && typeof ocr === 'object') {
    for (const field of DATE_FIELDS) {
      candidates.push(...extractDatesFromUnknown(ocr[field]));
    }
  }

  if (candidates.length === 0) {
    return null;
  }

  return candidates.reduce((earliest, current) =>
    current.getTime() < earliest.getTime() ? current : earliest
  );
};

const resolveAuthorityDocumentYear = (doc: DocumentDateLike): number | null => {
  if (typeof doc.document_year === 'number' && Number.isFinite(doc.document_year)) {
    return doc.document_year;
  }

  const ocr = doc.ocr_result;
  const raw = ocr && typeof ocr === 'object' ? ocr.document_year : null;
  if (typeof raw === 'number' && Number.isFinite(raw)) {
    return raw;
  }
  if (typeof raw === 'string') {
    const parsed = Number.parseInt(raw, 10);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }

  return null;
};

export function resolveDocumentDate(doc: DocumentDateLike): Date {
  return resolveMaterializedDocumentDate(doc) ?? new Date(doc.created_at);
}

export function resolveDocumentYear(doc: DocumentDateLike): number {
  return resolveAuthorityDocumentYear(doc) ?? resolveDocumentDate(doc).getFullYear();
}

export function compareDocumentsByDocumentDate(
  left: DocumentDateLike,
  right: DocumentDateLike,
): number {
  const leftExact = resolveMaterializedDocumentDate(left);
  const rightExact = resolveMaterializedDocumentDate(right);

  if (leftExact && rightExact) {
    return rightExact.getTime() - leftExact.getTime();
  }
  if (leftExact) {
    return -1;
  }
  if (rightExact) {
    return 1;
  }

  const leftYear = resolveAuthorityDocumentYear(left);
  const rightYear = resolveAuthorityDocumentYear(right);

  if (leftYear !== null && rightYear !== null && leftYear !== rightYear) {
    return rightYear - leftYear;
  }
  if (leftYear !== null) {
    return -1;
  }
  if (rightYear !== null) {
    return 1;
  }

  return new Date(right.created_at).getTime() - new Date(left.created_at).getTime();
}
