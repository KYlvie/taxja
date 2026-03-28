import type { TFunction } from 'i18next';
import { DocumentType } from '../types/document';

type DocumentTypeLike = DocumentType | string | null | undefined;

const normalizeDocumentTypeValue = (type: DocumentTypeLike): string => {
  if (type == null) return DocumentType.OTHER;
  return String(type);
};

export const getDocumentTypeLabel = (
  t: TFunction,
  type: DocumentTypeLike,
): string => t(`documents.types.${normalizeDocumentTypeValue(type)}`);

export const getDocumentTypeShortLabel = (
  t: TFunction,
  type: DocumentTypeLike,
): string => {
  const normalized = normalizeDocumentTypeValue(type);
  return t(`documents.typesShort.${normalized}`, {
    defaultValue: getDocumentTypeLabel(t, normalized),
  });
};
