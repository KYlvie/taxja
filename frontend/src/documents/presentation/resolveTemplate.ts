import isTaxImportDocument from './isTaxImportDocument';
import type {
  DocumentLike,
  DocumentPresentationTemplate,
  PresentationDocumentKind,
} from './types';

interface ResolveTemplateInput {
  doc: DocumentLike;
  normalizedType: PresentationDocumentKind;
}

export const resolveTemplate = ({
  doc,
  normalizedType,
}: ResolveTemplateInput): DocumentPresentationTemplate => {
  if (isTaxImportDocument(doc) || normalizedType === 'tax_form') {
    return 'tax_import';
  }

  if (normalizedType === 'receipt' || normalizedType === 'invoice') {
    return 'receipt_workbench';
  }

  if (
    normalizedType === 'rental_contract'
    || normalizedType === 'purchase_contract'
    || normalizedType === 'loan_contract'
    || normalizedType === 'insurance_confirmation'
  ) {
    return 'contract_review';
  }

  return 'generic_review';
};

export default resolveTemplate;
