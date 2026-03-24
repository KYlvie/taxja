import type { Document } from '../types/document';

type ReprocessableDocument = Pick<
  Document,
  'id' | 'mime_type' | 'transaction_id' | 'ocr_result' | 'ocr_status' | 'linked_transaction_count' | 'linked_transactions'
>;

export const isOcrCapableMimeType = (mimeType?: string | null): boolean =>
  mimeType === 'application/pdf' || Boolean(mimeType && mimeType.startsWith('image/'));

const hasConfirmedWorkflowOutcome = (document?: ReprocessableDocument | null): boolean => {
  if (!document?.ocr_result || typeof document.ocr_result !== 'object') {
    return false;
  }

  const ocr = document.ocr_result as Record<string, any>;
  if (ocr.confirmed === true) {
    return true;
  }

  const suggestionStatus = ocr.import_suggestion?.status;
  if (suggestionStatus === 'confirmed' || suggestionStatus === 'auto_created') {
    return true;
  }

  const assetOutcomeStatus = ocr.asset_outcome?.status;
  return assetOutcomeStatus === 'confirmed' || assetOutcomeStatus === 'auto_created';
};

const hasAnyLinkedTransactions = (document?: ReprocessableDocument | null): boolean => {
  if (!document) return false;
  if (document.transaction_id != null) return true;
  if ((document.linked_transaction_count || 0) > 0) return true;
  if (Array.isArray(document.linked_transactions) && document.linked_transactions.length > 0) {
    return true;
  }

  if (!document.ocr_result || typeof document.ocr_result !== 'object') {
    return false;
  }

  const ocr = document.ocr_result as Record<string, any>;
  const importSuggestion = ocr.import_suggestion;
  if (importSuggestion && typeof importSuggestion === 'object') {
    if ((Number(importSuggestion.imported_count) || 0) > 0) {
      return true;
    }

    const createdTransactionIds = importSuggestion.created_transaction_ids;
    if (Array.isArray(createdTransactionIds) && createdTransactionIds.length > 0) {
      return true;
    }
  }

  return false;
};

const isProcessingDocument = (document?: ReprocessableDocument | null): boolean => {
  if (!document) return false;
  if (document.ocr_status === 'processing') return true;
  const pipelineState =
    document.ocr_result &&
    typeof document.ocr_result === 'object' &&
    '_pipeline' in document.ocr_result
      ? (document.ocr_result as Record<string, any>)._pipeline?.current_state
      : null;

  return typeof pipelineState === 'string' && pipelineState.startsWith('processing_');
};

export const canReprocessDocument = (
  document?: ReprocessableDocument | null
): document is ReprocessableDocument =>
  Boolean(document?.id) &&
  isOcrCapableMimeType(document?.mime_type) &&
  !hasAnyLinkedTransactions(document) &&
  !hasConfirmedWorkflowOutcome(document) &&
  !isProcessingDocument(document);
