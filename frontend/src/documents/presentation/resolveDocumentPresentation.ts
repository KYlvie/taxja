import {
  getMatchedAlias,
  normalizeDocumentType,
} from './normalizeDocumentType';
import isTaxImportDocument from './isTaxImportDocument';
import resolveBadges from './resolveBadges';
import resolveControlPolicy from './resolveControlPolicy';
import resolveTemplate from './resolveTemplate';
import type {
  DocumentLike,
  DocumentPresentationDecision,
  DocumentPresentationDraft,
  DocumentPresentationMode,
} from './types';

const buildReason = (decision: DocumentPresentationDecision): string => {
  if (decision.template === 'tax_import') {
    return 'Matched the existing tax import flow.';
  }

  if (decision.template === 'receipt_workbench' && !decision.controlPolicy.isPostable) {
    return 'Receipt/invoice family with a non-postable commercial semantic.';
  }

  if (decision.template === 'receipt_workbench') {
    return 'Receipt/invoice family always uses the receipt workbench.';
  }

  if (decision.template === 'contract_review') {
    return 'Contract and proof documents use the contract review template.';
  }

  if (decision.template === 'bank_statement_review') {
    return 'Bank statements use the dedicated bank statement review template.';
  }

  return 'Fell back to the generic review template.';
};

export const resolveDocumentPresentation = (
  doc: DocumentLike,
  draft?: DocumentPresentationDraft
): DocumentPresentationDecision => {
  const normalizedType = normalizeDocumentType(draft?.documentType ?? doc.document_type, doc);
  const template = resolveTemplate({ doc, normalizedType });
  const initialMode: DocumentPresentationMode = doc.needs_review ? 'edit' : 'readonly';
  const controlPolicy = resolveControlPolicy(doc, draft);
  const { badges, helpers } = resolveBadges({
    doc,
    normalizedType,
    controlPolicy,
    draft,
  });

  const decision: DocumentPresentationDecision = {
    normalizedType,
    template,
    initialMode,
    controlPolicy,
    badges,
    helpers,
    source: {
      rawDocumentType: doc.document_type ?? null,
      matchedAlias: getMatchedAlias(draft?.documentType ?? doc.document_type),
      taxImportMatched: isTaxImportDocument(doc),
    },
  };

  return {
    ...decision,
    reason: buildReason(decision),
  };
};

export default resolveDocumentPresentation;
