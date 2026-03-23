import type { DocumentLike } from '../types';

const baseDoc = (overrides: Partial<DocumentLike> = {}): DocumentLike => ({
  id: 101,
  document_type: 'receipt',
  needs_review: false,
  raw_text: null,
  ocr_result: {},
  ...overrides,
});

export const presentationFixtures = {
  oldReceipt: baseDoc({
    id: 1,
    document_type: 'receipt',
    ocr_result: {
      _transaction_type: 'expense',
      commercial_document_semantics: 'receipt',
      document_transaction_direction: 'expense',
    },
  }),
  oldInvoice: baseDoc({
    id: 2,
    document_type: 'invoice',
    ocr_result: {
      _transaction_type: 'expense',
      commercial_document_semantics: 'standard_invoice',
      document_transaction_direction: 'expense',
    },
  }),
  gutschrift: baseDoc({
    id: 3,
    document_type: 'gutschrift',
    ocr_result: {
      _transaction_type: 'expense',
      commercial_document_semantics: 'credit_note',
      is_reversal: true,
    },
  }),
  proformaInvoice: baseDoc({
    id: 4,
    document_type: 'proforma_invoice',
    ocr_result: {
      _transaction_type: 'expense',
      commercial_document_semantics: 'proforma',
    },
  }),
  deliveryNote: baseDoc({
    id: 5,
    document_type: 'delivery_note',
    ocr_result: {
      _transaction_type: 'expense',
      commercial_document_semantics: 'delivery_note',
    },
  }),
  mietvertrag: baseDoc({
    id: 6,
    document_type: 'mietvertrag',
    ocr_result: {
      landlord_name: 'Erika Muster',
      tenant_name: 'Max Mustermann',
    },
  }),
  kreditvertrag: baseDoc({
    id: 7,
    document_type: 'kreditvertrag',
    needs_review: true,
    ocr_result: {
      borrower_name: 'Ing. Klaus Bauer',
      loan_amount: 290000,
    },
  }),
  kontoauszug: baseDoc({
    id: 8,
    document_type: 'kontoauszug',
    ocr_result: {
      account_holder: 'Test User',
    },
  }),
  taxForm: baseDoc({
    id: 9,
    document_type: 'e1_form',
    raw_text: 'E1 Einkommensteuererklaerung 2025',
  }),
  needsReviewTrue: baseDoc({
    id: 10,
    document_type: 'invoice',
    needs_review: true,
    ocr_result: {
      _transaction_type: 'expense',
      commercial_document_semantics: 'standard_invoice',
    },
  }),
  needsReviewFalse: baseDoc({
    id: 11,
    document_type: 'invoice',
    needs_review: false,
    ocr_result: {
      _transaction_type: 'expense',
      commercial_document_semantics: 'standard_invoice',
    },
  }),
};

export default presentationFixtures;
