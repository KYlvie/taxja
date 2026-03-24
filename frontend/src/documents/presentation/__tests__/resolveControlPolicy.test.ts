import { describe, expect, it } from 'vitest';

import resolveControlPolicy from '../resolveControlPolicy';
import presentationFixtures from './fixtures';

describe('resolveControlPolicy', () => {
  it('keeps full actions for expense standard invoices', () => {
    const policy = resolveControlPolicy(presentationFixtures.oldInvoice);

    expect(policy.transactionType).toBe('expense');
    expect(policy.isPostable).toBe(true);
    expect(policy.hideDeductibility).toBe(false);
    expect(policy.allowCreateActions).toBe(true);
    expect(policy.allowSyncActions).toBe(true);
  });

  it('hides deductibility for income documents while staying postable', () => {
    const policy = resolveControlPolicy(presentationFixtures.oldReceipt, {
      transactionType: 'income',
      commercialDocumentSemantics: 'receipt',
    });

    expect(policy.transactionType).toBe('income');
    expect(policy.isPostable).toBe(true);
    expect(policy.hideDeductibility).toBe(true);
  });

  it('marks credit notes as reversal-like while staying postable', () => {
    const policy = resolveControlPolicy(presentationFixtures.gutschrift);

    expect(policy.isReversalLike).toBe(true);
    expect(policy.isPostable).toBe(true);
    expect(policy.allowSuggestionCreateActions).toBe(true);
  });

  it('blocks non-postable proforma invoices', () => {
    const policy = resolveControlPolicy(presentationFixtures.proformaInvoice);

    expect(policy.isPostable).toBe(false);
    expect(policy.hideCreateActions).toBe(true);
    expect(policy.allowCreateActions).toBe(false);
    expect(policy.allowSuggestionCreateActions).toBe(false);
  });

  it('blocks non-postable delivery notes', () => {
    const policy = resolveControlPolicy(presentationFixtures.deliveryNote);

    expect(policy.isPostable).toBe(false);
    expect(policy.hideDeductibility).toBe(true);
    expect(policy.allowSyncActions).toBe(false);
  });
});
