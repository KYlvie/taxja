import isTaxImportDocument from './isTaxImportDocument';
import type { DocumentLike, PresentationDocumentKind } from './types';

export const TYPE_ALIAS_MAP: Record<string, PresentationDocumentKind> = {
  receipt: 'receipt',
  payslip: 'receipt',
  invoice: 'invoice',
  credit_note: 'invoice',
  gutschrift: 'invoice',
  proforma_invoice: 'invoice',
  delivery_note: 'invoice',
  rental_contract: 'rental_contract',
  mietvertrag: 'rental_contract',
  purchase_contract: 'purchase_contract',
  loan_contract: 'loan_contract',
  kreditvertrag: 'loan_contract',
  versicherungsbestaetigung: 'insurance_confirmation',
  insurance_confirmation: 'insurance_confirmation',
  bank_statement: 'bank_statement',
  kontoauszug: 'bank_statement',
  einkommensteuerbescheid: 'tax_form',
  e1_form: 'tax_form',
  l1_form: 'tax_form',
  l1k_beilage: 'tax_form',
  l1ab_beilage: 'tax_form',
  e1a_beilage: 'tax_form',
  e1b_beilage: 'tax_form',
  e1kv_beilage: 'tax_form',
  u1_form: 'tax_form',
  u30_form: 'tax_form',
  jahresabschluss: 'tax_form',
  lohnzettel: 'tax_form',
  svs_notice: 'tax_form',
  property_tax: 'tax_form',
};

export const normalizeRawType = (rawType?: string | null): string => {
  if (!rawType) return '';

  return rawType
    .trim()
    .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
    .replace(/[\s-]+/g, '_')
    .replace(/_+/g, '_')
    .toLowerCase();
};

export const getMatchedAlias = (rawType?: string | null): string | null => {
  const normalizedType = normalizeRawType(rawType);
  return normalizedType && TYPE_ALIAS_MAP[normalizedType] ? normalizedType : null;
};

export const normalizeDocumentType = (
  rawType?: string | null,
  doc?: DocumentLike | null
): PresentationDocumentKind => {
  const normalizedType = normalizeRawType(rawType);

  if (normalizedType && TYPE_ALIAS_MAP[normalizedType]) {
    return TYPE_ALIAS_MAP[normalizedType];
  }

  if (doc && isTaxImportDocument(doc)) {
    return 'tax_form';
  }

  return 'generic';
};

export default normalizeDocumentType;
