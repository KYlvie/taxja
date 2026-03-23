import { describe, expect, it } from 'vitest';

import {
  formatDocumentFieldLabel,
  translateDocumentSuggestionText,
} from '../utils/documentFieldLabel';

const dictionary: Record<string, string> = {
  'documents.review.transactionType': 'Transaction type (Translated)',
  'documents.documentType': 'Document type (Translated)',
  'documents.review.fields.myRole': 'My role (Translated)',
  'documents.review.taxFieldLabels.employer_name': 'Employer (Translated)',
  'documents.review.taxFieldLabels.employee_name': 'Employee (Translated)',
  'documents.review.taxFieldLabels.loan_amount': 'Loan amount (Translated)',
  'documents.review.taxFieldLabels.interest_rate': 'Interest rate (Translated)',
  'documents.review.taxFieldLabels.utilities_included': 'Utilities included (Translated)',
  'documents.review.taxFieldLabels.social_insurance': 'Social insurance (Translated)',
  'documents.review.taxFieldLabels.document_transaction_direction':
    'Document transaction direction (Translated)',
  'documents.review.taxFieldLabels.commercial_document_semantics':
    'Commercial document semantics (Translated)',
  'documents.review.taxFieldLabels.is_reversal': 'Is reversal (Translated)',
};

const t = ((key: string, fallbackOrOptions?: unknown) => {
  if (typeof fallbackOrOptions === 'string') {
    return dictionary[key] ?? fallbackOrOptions;
  }

  return dictionary[key] ?? key;
}) as any;

describe('document field label helpers', () => {
  it('formats normalized field labels through i18n keys', () => {
    expect(formatDocumentFieldLabel('Employer Name', t)).toBe('Employer (Translated)');
    expect(formatDocumentFieldLabel('loan_amount', t)).toBe('Loan amount (Translated)');
    expect(formatDocumentFieldLabel('Transaction Type', t)).toBe('Transaction type (Translated)');
    expect(formatDocumentFieldLabel('Document Type', t)).toBe('Document type (Translated)');
  });

  it('translates quoted field names inside OCR suggestions', () => {
    const translated = translateDocumentSuggestionText('Please verify "Employer Name".', t);
    expect(translated).toContain('"Employer (Translated)"');
  });

  it('translates comma-separated missing field lists', () => {
    const translated = translateDocumentSuggestionText('Missing: loan_amount, interest_rate', t);
    expect(translated).toContain('Loan amount (Translated)');
    expect(translated).toContain('Interest rate (Translated)');
  });

  it('supports internal field names with spaces and underscores', () => {
    const translated = translateDocumentSuggestionText('Please verify "Utilities Included".', t);
    expect(translated).toContain('Utilities included (Translated)');
  });

  it('translates review helper fields that previously leaked in English', () => {
    const translated = translateDocumentSuggestionText(
      'Please verify "Social Insurance", "Document Transaction Direction", "Commercial Document Semantics", and "Is Reversal".',
      t,
    );
    expect(translated).toContain('Social insurance (Translated)');
    expect(translated).toContain('Document transaction direction (Translated)');
    expect(translated).toContain('Commercial document semantics (Translated)');
    expect(translated).toContain('Is reversal (Translated)');
  });
});
