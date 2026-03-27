import {
  getMatchedAlias,
  normalizeRawType,
} from './normalizeDocumentType';
import type {
  CommercialSemantic,
  DocumentControlPolicy,
  DocumentLike,
  DocumentPresentationDraft,
  DocumentTransactionType,
} from './types';

const readOcrValue = (doc?: DocumentLike | null, key?: string): unknown => {
  if (!doc || !key) return undefined;
  if (!doc.ocr_result || typeof doc.ocr_result !== 'object') return undefined;
  return (doc.ocr_result as Record<string, unknown>)[key];
};

const normalizeTransactionType = (value: unknown): DocumentTransactionType => {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized === 'income' || normalized === 'expense') {
    return normalized;
  }
  return 'unknown';
};

export const normalizeSemantic = (value: unknown): CommercialSemantic => {
  const normalized = normalizeRawType(String(value || ''));
  switch (normalized) {
    case 'receipt':
      return 'receipt';
    case 'standard_invoice':
    case 'invoice':
      return 'standard_invoice';
    case 'credit_note':
    case 'gutschrift':
      return 'credit_note';
    case 'settlement_credit':
      return 'settlement_credit';
    case 'proforma':
    case 'proforma_invoice':
      return 'proforma';
    case 'delivery_note':
    case 'lieferschein':
      return 'delivery_note';
    default:
      return 'unknown';
  }
};

const semanticFromRawType = (rawType?: string | null): CommercialSemantic => {
  switch (normalizeRawType(rawType)) {
    case 'receipt':
      return 'receipt';
    case 'credit_note':
    case 'gutschrift':
      return 'credit_note';
    case 'proforma_invoice':
      return 'proforma';
    case 'delivery_note':
      return 'delivery_note';
    case 'invoice':
      return 'standard_invoice';
    default:
      return 'unknown';
  }
};

export const resolveEffectiveTransactionType = (
  doc: DocumentLike,
  draft?: DocumentPresentationDraft
): DocumentTransactionType => {
  const transactionType = normalizeTransactionType(
    draft?.transactionType
      ?? readOcrValue(doc, 'final_transaction_type')
      ?? readOcrValue(doc, '_transaction_type')
      ?? readOcrValue(doc, 'transaction_type')
      ?? draft?.documentTransactionDirection
      ?? readOcrValue(doc, 'document_transaction_direction')
      ?? readOcrValue(doc, 'transaction_direction')
  );

  return transactionType;
};

export const resolveEffectiveSemantic = (
  doc: DocumentLike,
  draft?: DocumentPresentationDraft
): CommercialSemantic => {
  const explicitSemantic = normalizeSemantic(
    draft?.commercialDocumentSemantics
      ?? readOcrValue(doc, 'commercial_document_semantics')
  );

  if (explicitSemantic !== 'unknown') {
    return explicitSemantic;
  }

  const matchedAlias = getMatchedAlias(draft?.documentType ?? doc.document_type);
  if (matchedAlias) {
    return semanticFromRawType(draft?.documentType ?? doc.document_type);
  }

  return semanticFromRawType(draft?.documentType ?? doc.document_type);
};

export const resolveEffectiveIsReversal = (
  doc: DocumentLike,
  draft?: DocumentPresentationDraft
): boolean => Boolean(
  draft?.isReversal
    ?? readOcrValue(doc, 'is_reversal')
);

export const resolveControlPolicy = (
  doc: DocumentLike,
  draft?: DocumentPresentationDraft
): DocumentControlPolicy => {
  const transactionType = resolveEffectiveTransactionType(doc, draft);
  const semantic = resolveEffectiveSemantic(doc, draft);
  const isReversalLike = semantic === 'credit_note' || resolveEffectiveIsReversal(doc, draft);
  const isPostable = !(semantic === 'proforma' || semantic === 'delivery_note');
  const isExpenseLike = transactionType === 'expense';
  const hideDeductibility = !isPostable || !isExpenseLike;
  const hideCreateActions = !isPostable;

  return {
    transactionType,
    isPostable,
    isExpenseLike,
    isReversalLike,
    hideDeductibility,
    hideCreateActions,
    allowCreateActions: isPostable,
    allowSyncActions: isPostable,
    allowSuggestionCreateActions: isPostable,
  };
};

export default resolveControlPolicy;
