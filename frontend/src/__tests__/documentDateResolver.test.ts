import { describe, it, expect } from 'vitest';
import {
  compareDocumentsByDocumentDate,
  resolveDocumentDate,
  resolveDocumentYear,
} from '../utils/documentDateResolver';

describe('resolveDocumentDate', () => {
  const BASE_DOC = { created_at: '2024-01-15T10:00:00Z' };

  it('uses the earliest valid OCR date when multiple fields exist', () => {
    const doc = {
      ...BASE_DOC,
      ocr_result: {
        document_date: '2023-06-01',
        date: '2023-05-01',
        invoice_date: '2023-04-01',
      },
    };
    expect(resolveDocumentDate(doc)).toEqual(new Date('2023-04-01'));
  });

  it('uses the earliest date across different OCR fields', () => {
    const doc = {
      ...BASE_DOC,
      ocr_result: { invoice_date: '2023-03-15', purchase_date: '2023-02-01' },
    };
    expect(resolveDocumentDate(doc)).toEqual(new Date('2023-02-01'));
  });

  it('uses purchase_date when higher priority fields are missing', () => {
    const doc = {
      ...BASE_DOC,
      ocr_result: { purchase_date: '2022-11-20' },
    };
    expect(resolveDocumentDate(doc)).toEqual(new Date('2022-11-20'));
  });

  it('uses start_date as last resort OCR field', () => {
    const doc = {
      ...BASE_DOC,
      ocr_result: { start_date: '2022-08-01' },
    };
    expect(resolveDocumentDate(doc)).toEqual(new Date('2022-08-01'));
  });

  it('falls back to created_at when no valid OCR date fields exist', () => {
    const doc = {
      ...BASE_DOC,
      ocr_result: { some_other_field: 'hello' },
    };
    expect(resolveDocumentDate(doc)).toEqual(new Date('2024-01-15T10:00:00Z'));
  });

  it('falls back to created_at when ocr_result is null', () => {
    const doc = { ...BASE_DOC, ocr_result: null };
    expect(resolveDocumentDate(doc)).toEqual(new Date('2024-01-15T10:00:00Z'));
  });

  it('falls back to created_at when ocr_result is undefined', () => {
    expect(resolveDocumentDate(BASE_DOC)).toEqual(new Date('2024-01-15T10:00:00Z'));
  });

  it('skips invalid date strings and falls through', () => {
    const doc = {
      ...BASE_DOC,
      ocr_result: {
        document_date: 'not-a-date',
        date: '',
        invoice_date: '2023-09-10',
      },
    };
    expect(resolveDocumentDate(doc)).toEqual(new Date('2023-09-10'));
  });

  it('skips non-string values in OCR fields', () => {
    const doc = {
      ...BASE_DOC,
      ocr_result: {
        document_date: 12345,
        date: null,
        invoice_date: '2023-07-04',
      },
    };
    expect(resolveDocumentDate(doc)).toEqual(new Date('2023-07-04'));
  });

  it('uses the earliest date from statement_period objects', () => {
    const doc = {
      ...BASE_DOC,
      ocr_result: {
        statement_period: {
          start: '2024-06-26',
          end: '2024-12-19',
        },
      },
    };
    expect(resolveDocumentDate(doc)).toEqual(new Date('2024-06-26'));
  });

  it('uses the earliest date from statement period strings', () => {
    const doc = {
      ...BASE_DOC,
      ocr_result: {
        statement_period: '2024/6/26 - 2024/12/19',
      },
    };
    expect(resolveDocumentDate(doc)).toEqual(new Date('2024-06-26T00:00:00.000Z'));
  });

  it('uses the earliest date from explicit period bounds', () => {
    const doc = {
      ...BASE_DOC,
      ocr_result: {
        period_start: '2024-06-26',
        period_end: '2024-12-19',
      },
    };
    expect(resolveDocumentDate(doc)).toEqual(new Date('2024-06-26'));
  });

  it('falls back to created_at when all OCR date fields are invalid', () => {
    const doc = {
      ...BASE_DOC,
      ocr_result: {
        document_date: 'bad',
        date: '',
        invoice_date: 'nope',
        receipt_date: null,
        purchase_date: 42,
        start_date: false,
        statement_period: 'not-a-date range',
      },
    };
    expect(resolveDocumentDate(doc)).toEqual(new Date('2024-01-15T10:00:00Z'));
  });

  it('prefers the top-level authoritative document year when present', () => {
    const doc = {
      ...BASE_DOC,
      document_year: 2024,
      ocr_result: {
        statement_period: {
          start: '2025-01-01',
          end: '2025-12-31',
        },
      },
    };

    expect(resolveDocumentYear(doc)).toBe(2024);
  });

  it('falls back to resolved OCR date year when authoritative year is missing', () => {
    const doc = {
      ...BASE_DOC,
      ocr_result: {
        invoice_date: '2023-04-01',
      },
    };

    expect(resolveDocumentYear(doc)).toBe(2023);
  });

  it('sorts exact document_date entries before year-only entries in document-date mode', () => {
    const exactDateDoc = {
      ...BASE_DOC,
      created_at: '2026-03-24T10:00:00Z',
      document_date: '2024-06-26',
      document_year: 2024,
      ocr_result: {},
    };
    const yearOnlyDoc = {
      ...BASE_DOC,
      created_at: '2026-03-25T10:00:00Z',
      document_year: 2024,
      ocr_result: {},
    };

    expect(compareDocumentsByDocumentDate(exactDateDoc, yearOnlyDoc)).toBeLessThan(0);
  });
});
