import { describe, expect, it } from 'vitest';
import i18n from '../i18n';
import { getDocumentTypeLabel, getDocumentTypeShortLabel } from '../utils/documentTypeLabels';
import { DocumentType } from '../types/document';

describe('documentTypeLabels', () => {
  it('returns a localized short label when available', () => {
    const shortLabel = getDocumentTypeShortLabel(i18n.t.bind(i18n), DocumentType.VERSICHERUNGSBESTAETIGUNG);
    const fullLabel = getDocumentTypeLabel(i18n.t.bind(i18n), DocumentType.VERSICHERUNGSBESTAETIGUNG);

    expect(shortLabel).toBeTruthy();
    expect(fullLabel).toBeTruthy();
    expect(shortLabel).not.toContain('documents.typesShort.');
  });

  it('falls back to the full label when no short translation exists', () => {
    const shortLabel = getDocumentTypeShortLabel(i18n.t.bind(i18n), 'unknown_custom_type');
    const fullLabel = getDocumentTypeLabel(i18n.t.bind(i18n), 'unknown_custom_type');

    expect(shortLabel).toBe(fullLabel);
  });
});
