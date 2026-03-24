export type FallbackTransactionDirection = 'credit' | 'debit' | 'unknown';

export interface FallbackBankStatementLine {
  id: string;
  line_date?: string | null;
  amount?: string | number | null;
  counterparty?: string | null;
  purpose?: string | null;
  raw_reference?: string | null;
  direction: FallbackTransactionDirection;
}

const MONTHS: Record<string, number> = {
  jaenner: 1,
  januar: 1,
  jan: 1,
  februar: 2,
  feb: 2,
  maerz: 3,
  mrz: 3,
  april: 4,
  apr: 4,
  mai: 5,
  juni: 6,
  jun: 6,
  juli: 7,
  jul: 7,
  august: 8,
  aug: 8,
  september: 9,
  sep: 9,
  oktober: 10,
  okt: 10,
  oct: 10,
  november: 11,
  nov: 11,
  dezember: 12,
  dez: 12,
  dec: 12,
};

const MONTH_HEADER_RE = /^([\p{L}]+)\s+(\d{4})$/u;
const TRANSACTION_START_RE = /^(\d{1,2})\.\s*([\p{L}]+)\.?(?:\s+(\d{4}))?$/u;
const AMOUNT_RE = /(-?\s*(?:EUR|€)?\s*\d{1,3}(?:[.\s]\d{3})*,\d{2})/i;
const PLACEHOLDER_COUNTERPARTIES = new Set(['', '-', '-euro', 'euro', '-eur', 'eur']);

const normalizeLine = (value: string) => value
  .replace(/[\u2212\u2013\u2014\u2011]/g, '-')
  .replace(/[\u00a0\u2009\u202f]/g, ' ')
  .trim();

const normalizeToken = (value: string) => normalizeLine(value)
  .toLowerCase()
  .replace(/ä/g, 'ae')
  .replace(/ö/g, 'oe')
  .replace(/ü/g, 'ue')
  .replace(/ß/g, 'ss')
  .normalize('NFKD')
  .replace(/[^\x00-\x7F]/g, '');

const normalizeCounterparty = (value: string | null | undefined) => (value || '')
  .toLowerCase()
  .replace(/[€$£]/g, 'euro')
  .replace(/\s+/g, '')
  .trim();

const parseAmount = (value: string | number | null | undefined): number | null => {
  if (value === null || value === undefined || value === '') return null;
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : null;
  }

  const normalized = normalizeLine(String(value))
    .replace(/EUR/gi, '')
    .replace(/€/g, '')
    .replace(/\s+/g, '')
    .replace(/\.(?=\d{3}(?:,|$))/g, '')
    .replace(',', '.');
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : null;
};

const getDirection = (
  rawType: unknown,
  amount: string | number | null | undefined,
): FallbackTransactionDirection => {
  const normalizedType = String(rawType || '').trim().toLowerCase();
  if (['credit', 'incoming', 'income', 'deposit'].includes(normalizedType)) {
    return 'credit';
  }
  if (['debit', 'outgoing', 'expense', 'withdrawal'].includes(normalizedType)) {
    return 'debit';
  }

  const numeric = parseAmount(amount);
  if (numeric === null) return 'unknown';
  if (numeric < 0) return 'debit';
  if (numeric > 0) return 'credit';
  return 'unknown';
};

const isMonthSummaryLine = (value: string) => normalizeToken(value).includes('kontoausgang');

const mapOcrTransactions = (rawTransactions: unknown[]): FallbackBankStatementLine[] => rawTransactions
  .filter((transaction): transaction is Record<string, unknown> => Boolean(transaction) && typeof transaction === 'object')
  .map((transaction, index) => {
    const amount = transaction.amount as string | number | null | undefined;
    const reference = String(
      transaction.raw_reference
      ?? transaction.reference
      ?? ''
    ).trim() || null;
    const purpose = String(
      transaction.purpose
      ?? transaction.description
      ?? reference
      ?? ''
    ).trim() || null;
    const counterparty = String(
      transaction.counterparty
      ?? transaction.payee
      ?? transaction.merchant
      ?? ''
    ).trim() || null;

    return {
      id: `fallback-ocr-${index}`,
      line_date: String(transaction.date ?? '').trim() || null,
      amount,
      counterparty,
      purpose,
      raw_reference: reference,
      direction: getDirection(transaction.transaction_type ?? transaction.direction, amount),
    };
  });

const extractFromRawText = (rawText: string | null | undefined): FallbackBankStatementLine[] => {
  if (!rawText) return [];

  let currentYear: number | null = null;
  let activeBlock: { date: string; lines: string[] } | null = null;
  const blocks: Array<{ date: string; lines: string[] }> = [];

  for (const rawLine of rawText.split(/\r?\n/)) {
    const line = normalizeLine(rawLine);
    if (!line || line.startsWith('--- PAGE')) {
      continue;
    }

    const monthHeader = line.match(MONTH_HEADER_RE);
    if (monthHeader) {
      const month = MONTHS[normalizeToken(monthHeader[1])];
      if (month) {
        currentYear = Number(monthHeader[2]);
        if (activeBlock) {
          blocks.push(activeBlock);
          activeBlock = null;
        }
        continue;
      }
    }

    if (isMonthSummaryLine(line) && !activeBlock) {
      continue;
    }

    const startMatch = line.match(TRANSACTION_START_RE);
    if (startMatch) {
      const month = MONTHS[normalizeToken(startMatch[2])];
      const year = startMatch[3] ? Number(startMatch[3]) : currentYear;
      if (month && year) {
        if (activeBlock) {
          blocks.push(activeBlock);
        }
        activeBlock = {
          date: `${startMatch[1].padStart(2, '0')}.${String(month).padStart(2, '0')}.${year}`,
          lines: [],
        };
        continue;
      }
    }

    if (activeBlock) {
      activeBlock.lines.push(line);
    }
  }

  if (activeBlock) {
    blocks.push(activeBlock);
  }

  const extracted: FallbackBankStatementLine[] = [];
  const seen = new Set<string>();

  for (const [index, block] of blocks.entries()) {
    const amountLineIndex = [...block.lines]
      .map((line, lineIndex) => ({ line, lineIndex }))
      .reverse()
      .find(({ line }) => AMOUNT_RE.test(line))?.lineIndex;

    if (amountLineIndex === undefined) {
      continue;
    }

    const amountMatch = block.lines[amountLineIndex].match(AMOUNT_RE);
    const amount = parseAmount(amountMatch?.[1]);
    if (amount === null) {
      continue;
    }

    const detailLines = block.lines.filter((line, lineIndex) => (
      lineIndex !== amountLineIndex
      && !isMonthSummaryLine(line)
      && !AMOUNT_RE.test(line)
    ));
    if (!detailLines.length) {
      continue;
    }

    const counterparty = detailLines[0] || null;
    const rawReference = detailLines.slice(1).join(' ').trim() || null;
    const purpose = rawReference || null;
    const fingerprint = [
      block.date,
      amount.toFixed(2),
      counterparty || '',
      rawReference || '',
    ].join('|');

    if (seen.has(fingerprint)) {
      continue;
    }
    seen.add(fingerprint);

    extracted.push({
      id: `fallback-raw-${index}`,
      line_date: block.date,
      amount,
      counterparty,
      purpose,
      raw_reference: rawReference,
      direction: getDirection(null, amount),
    });
  }

  return extracted;
};

const scoreLines = (lines: FallbackBankStatementLine[]) => lines.reduce((score, line) => {
  let nextScore = score;
  if (line.line_date && /\d{2}\.\d{2}\.\d{4}/.test(line.line_date)) nextScore += 2;
  if (parseAmount(line.amount) !== null) nextScore += 2;
  if (!PLACEHOLDER_COUNTERPARTIES.has(normalizeCounterparty(line.counterparty))) nextScore += 2;
  if (line.purpose || line.raw_reference) nextScore += 1;
  if (line.direction !== 'unknown') nextScore += 1;
  return nextScore;
}, 0);

export const buildFallbackBankStatementLines = (
  rawTransactions: unknown[],
  rawText?: string | null,
): FallbackBankStatementLine[] => {
  const ocrLines = mapOcrTransactions(rawTransactions);
  const rawTextLines = extractFromRawText(rawText);

  if (!rawTextLines.length) {
    return ocrLines;
  }
  if (!ocrLines.length) {
    return rawTextLines;
  }

  return scoreLines(rawTextLines) > scoreLines(ocrLines) ? rawTextLines : ocrLines;
};

export const __test__ = {
  extractFromRawText,
  parseAmount,
};
