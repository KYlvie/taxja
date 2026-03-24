import { describe, expect, it } from 'vitest';

import resolveTemplate from '../resolveTemplate';
import presentationFixtures from './fixtures';

describe('resolveTemplate', () => {
  it('prioritizes the tax import flow above all other templates', () => {
    expect(
      resolveTemplate({
        doc: presentationFixtures.taxForm,
        normalizedType: 'tax_form',
      })
    ).toBe('tax_import');
  });

  it('always routes invoice family documents into the receipt workbench', () => {
    expect(
      resolveTemplate({
        doc: presentationFixtures.oldInvoice,
        normalizedType: 'invoice',
      })
    ).toBe('receipt_workbench');
  });

  it('routes contract families into contract review', () => {
    expect(
      resolveTemplate({
        doc: presentationFixtures.kreditvertrag,
        normalizedType: 'loan_contract',
      })
    ).toBe('contract_review');
  });

  it('keeps bank statements in generic review', () => {
    expect(
      resolveTemplate({
        doc: presentationFixtures.kontoauszug,
        normalizedType: 'bank_statement',
      })
    ).toBe('generic_review');
  });

  it('does not let needs_review affect the selected template', () => {
    expect(
      resolveTemplate({
        doc: presentationFixtures.needsReviewTrue,
        normalizedType: 'invoice',
      })
    ).toBe(
      resolveTemplate({
        doc: presentationFixtures.needsReviewFalse,
        normalizedType: 'invoice',
      })
    );
  });
});
