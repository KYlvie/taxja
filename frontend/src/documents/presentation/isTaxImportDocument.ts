import type { DocumentLike } from './types';

const SPECIAL_TAX_IMPORT_TYPES = new Set([
  'einkommensteuerbescheid',
  'e1_form',
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
  const normalizedType = String(doc.document_type).trim().toLowerCase();
  return SPECIAL_TAX_IMPORT_TYPES.has(normalizedType) && hasTaxImportText(doc);
};

export default isTaxImportDocument;
