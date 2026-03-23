import i18n from '../../i18n';
import {
  resolveEffectiveIsReversal,
  resolveEffectiveSemantic,
  resolveEffectiveTransactionType,
} from './resolveControlPolicy';
import type {
  DocumentControlPolicy,
  DocumentLike,
  DocumentPresentationDraft,
  PresentationDocumentKind,
} from './types';

interface ResolveBadgesInput {
  doc: DocumentLike;
  normalizedType: PresentationDocumentKind;
  controlPolicy: DocumentControlPolicy;
  draft?: DocumentPresentationDraft;
}

export const resolveBadges = ({
  doc,
  controlPolicy,
  draft,
}: ResolveBadgesInput): { badges: string[]; helpers: string[] } => {
  const t = i18n.t.bind(i18n);
  const badges: string[] = [];
  const helpers: string[] = [];
  const semantic = resolveEffectiveSemantic(doc, draft);
  const transactionType = resolveEffectiveTransactionType(doc, draft);
  const isReversal = resolveEffectiveIsReversal(doc, draft);

  if (transactionType === 'income') {
    badges.push(t('documents.review.direction.income', 'Income'));
  }

  if (transactionType === 'expense') {
    badges.push(t('documents.review.direction.expense', 'Expense'));
  }

  if (semantic === 'credit_note') {
    badges.push(t('documents.review.semantics.credit_note', 'Credit Note'));
  }

  if (isReversal || controlPolicy.isReversalLike) {
    badges.push(t('documents.review.reversal', 'Reversal'));
    helpers.push(t('documents.review.reversalHelper', 'This document is treated as a reversal or credit note.'));
  }

  if (!controlPolicy.isPostable && semantic === 'proforma') {
    badges.push(t('documents.review.nonPostable', 'Non-postable'));
    helpers.push(t('documents.review.proformaHelper', 'This document is a proforma invoice and will not create a transaction record.'));
  }

  if (!controlPolicy.isPostable && semantic === 'delivery_note') {
    badges.push(t('documents.review.nonPostable', 'Non-postable'));
    helpers.push(t('documents.review.deliveryNoteHelper', 'This document is a delivery note and will not create a transaction record.'));
  }

  return {
    badges: Array.from(new Set(badges)),
    helpers: Array.from(new Set(helpers)),
  };
};

export default resolveBadges;
