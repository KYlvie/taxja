import type { DocumentLike } from './types';

const SPECIAL_TAX_IMPORT_TYPES = new Set([
  'einkommensteuerbescheid',
  'e1_form',
  'l1_form',
  'l1k_beilage',
  'l1ab_beilage',
  'e1a_beilage',
  'e1b_beilage',
  'e1kv_beilage',
  'u1_form',
  'u30_form',
  'jahresabschluss',
  'lohnzettel',
  'svs_notice',
  'property_tax',
]);

const hasTaxImportText = (doc?: DocumentLike | null): boolean => {
  if (!doc) return false;
  return Boolean(
    doc.raw_text
      || (typeof doc.ocr_result === 'string' && doc.ocr_result.trim())
  );
};

export const isTaxImportDocument = (doc?: DocumentLike | null): boolean => {
  if (!doc?.document_type) return false;
  const normalizedType = String(doc.document_type)
    .trim()
    .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
    .replace(/[\s-]+/g, '_')
    .replace(/_+/g, '_')
    .toLowerCase();
  return SPECIAL_TAX_IMPORT_TYPES.has(normalizedType) && hasTaxImportText(doc);
};

export default isTaxImportDocument;
