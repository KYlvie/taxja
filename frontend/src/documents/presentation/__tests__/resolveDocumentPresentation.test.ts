import { describe, expect, it } from 'vitest';

import resolveDocumentPresentation from '../resolveDocumentPresentation';
import presentationFixtures from './fixtures';

describe('resolveDocumentPresentation', () => {
  it('keeps receipt/invoice family documents in the receipt workbench regardless of needs_review', () => {
    const editableDecision = resolveDocumentPresentation(presentationFixtures.needsReviewTrue);
    const readonlyDecision = resolveDocumentPresentation(presentationFixtures.needsReviewFalse);

    expect(editableDecision.template).toBe('receipt_workbench');
    expect(readonlyDecision.template).toBe('receipt_workbench');
    expect(editableDecision.initialMode).toBe('edit');
    expect(readonlyDecision.initialMode).toBe('readonly');
  });

  it('routes historical contract aliases into contract review', () => {
    const decision = resolveDocumentPresentation(presentationFixtures.kreditvertrag);

    expect(decision.normalizedType).toBe('loan_contract');
    expect(decision.template).toBe('contract_review');
  });

  it('routes tax forms into the tax import flow', () => {
    const decision = resolveDocumentPresentation(presentationFixtures.taxForm);

    expect(decision.normalizedType).toBe('tax_form');
    expect(decision.template).toBe('tax_import');
    expect(decision.source?.taxImportMatched).toBe(true);
  });

  it('emits non-postable badges and helpers for proforma invoices', () => {
    const decision = resolveDocumentPresentation(presentationFixtures.proformaInvoice);

    expect(decision.template).toBe('receipt_workbench');
    expect(decision.badges).toContain('Non-postable');
    expect(decision.helpers.some((helper) => helper.includes('proforma invoice'))).toBe(true);
  });

  it('recomputes live policy from local draft values without changing the template', () => {
    const decision = resolveDocumentPresentation(presentationFixtures.proformaInvoice, {
      documentType: 'invoice',
      transactionType: 'expense',
      commercialDocumentSemantics: 'standard_invoice',
      isReversal: false,
    });

    expect(decision.template).toBe('receipt_workbench');
    expect(decision.controlPolicy.isPostable).toBe(true);
    expect(decision.badges).not.toContain('Non-postable');
  });
});
