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
  svsNotice: baseDoc({
    id: 13,
    document_type: 'svs_notice',
    raw_text: 'SVS Beitragsvorschreibung 2024',
  }),
  propertyTax: baseDoc({
    id: 14,
    document_type: 'property_tax',
    raw_text: 'Grundsteuer Bescheid 2024',
  }),
  lohnzettel: baseDoc({
    id: 15,
    document_type: 'lohnzettel',
    raw_text: 'Lohnzettel 2024',
  }),
  u1Form: baseDoc({
    id: 16,
    document_type: 'u1_form',
    raw_text: 'U1 Umsatzsteuererklaerung',
  }),
  otherDocument: baseDoc({
    id: 17,
    document_type: 'other',
    needs_review: true,
    raw_text: 'Unclassified OCR text',
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
  ruleCorrectedIncome: baseDoc({
    id: 12,
    document_type: 'invoice',
    needs_review: false,
    ocr_result: {
      final_transaction_type: 'income',
      final_transaction_type_source: 'transaction_suggestion',
      _transaction_type: 'expense',
      commercial_document_semantics: 'standard_invoice',
      document_transaction_direction: 'expense',
    },
  }),
};

export default presentationFixtures;
