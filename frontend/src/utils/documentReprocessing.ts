import type { Document } from '../types/document';

type ReprocessableDocument = Pick<Document, 'id' | 'mime_type'>;

export const isOcrCapableMimeType = (mimeType?: string | null): boolean =>
  mimeType === 'application/pdf' || Boolean(mimeType && mimeType.startsWith('image/'));

export const canReprocessDocument = (
  document?: ReprocessableDocument | null
): document is ReprocessableDocument =>
  Boolean(document?.id) && isOcrCapableMimeType(document?.mime_type);
