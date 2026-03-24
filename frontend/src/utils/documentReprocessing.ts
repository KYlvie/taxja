import type { Document } from '../types/document';

type ReprocessableDocument = Pick<
  Document,
  'id' | 'mime_type' | 'transaction_id' | 'ocr_result' | 'ocr_status'
>;

export const isOcrCapableMimeType = (mimeType?: string | null): boolean =>
  mimeType === 'application/pdf' || Boolean(mimeType && mimeType.startsWith('image/'));

const isConfirmedDocument = (document?: ReprocessableDocument | null): boolean =>
  Boolean(
    document?.ocr_result &&
      typeof document.ocr_result === 'object' &&
      (document.ocr_result as Record<string, unknown>).confirmed === true
  );

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
  !document?.transaction_id &&
  !isConfirmedDocument(document) &&
  !isProcessingDocument(document);
