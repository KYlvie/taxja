import { describe, expect, it } from 'vitest';

import normalizeDocumentType from '../normalizeDocumentType';
import presentationFixtures from './fixtures';

describe('normalizeDocumentType', () => {
  it('normalizes commercial aliases into the invoice family', () => {
    expect(normalizeDocumentType('credit_note')).toBe('invoice');
    expect(normalizeDocumentType('gutschrift')).toBe('invoice');
    expect(normalizeDocumentType('proforma_invoice')).toBe('invoice');
    expect(normalizeDocumentType('delivery_note')).toBe('invoice');
  });

  it('normalizes historical contract and statement aliases', () => {
    expect(normalizeDocumentType('mietvertrag')).toBe('rental_contract');
    expect(normalizeDocumentType('kreditvertrag')).toBe('loan_contract');
    expect(normalizeDocumentType('kontoauszug')).toBe('bank_statement');
  });

  it('recognizes tax import documents through the existing tax flow detection', () => {
    expect(normalizeDocumentType('e1_form', presentationFixtures.taxForm)).toBe('tax_form');
  });

  it('falls back to generic for unknown document types', () => {
    expect(normalizeDocumentType('totally_unknown_type')).toBe('generic');
  });
});
