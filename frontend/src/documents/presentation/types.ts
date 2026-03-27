export type PresentationDocumentKind =
  | 'receipt'
  | 'invoice'
  | 'rental_contract'
  | 'purchase_contract'
  | 'loan_contract'
  | 'insurance_confirmation'
  | 'tax_form'
  | 'bank_statement'
  | 'generic';

export type DocumentPresentationTemplate =
  | 'receipt_workbench'
  | 'contract_review'
  | 'bank_statement_review'
  | 'tax_import'
  | 'generic_review';

export type DocumentPresentationMode = 'edit' | 'readonly';

export type ActionGateDisplayMode = 'enabled' | 'disabled' | 'hidden';

export type DocumentPresentationAction =
  | 'create_transaction'
  | 'sync_transaction'
  | 'confirm_and_create'
  | 'suggestion_create'
  | 'bulk_expense_quick_actions'
  | 'deductibility_controls';

export type DocumentTransactionType = 'expense' | 'income' | 'unknown';

export type CommercialSemantic =
  | 'standard_invoice'
  | 'receipt'
  | 'credit_note'
  | 'settlement_credit'
  | 'proforma'
  | 'delivery_note'
  | 'unknown';

export interface DocumentLike {
  id?: number | string;
  document_type?: string | null;
  needs_review?: boolean | null;
  ocr_result?: Record<string, unknown> | string | null;
  raw_text?: string | null;
}

export interface DocumentPresentationDraft {
  documentType?: string | null;
  transactionType?: DocumentTransactionType | string | null;
  documentTransactionDirection?: string | null;
  commercialDocumentSemantics?: string | null;
  isReversal?: boolean | null;
}

export interface DocumentControlPolicy {
  transactionType: DocumentTransactionType;
  isPostable: boolean;
  isExpenseLike: boolean;
  isReversalLike: boolean;
  hideDeductibility: boolean;
  hideCreateActions: boolean;
  allowCreateActions: boolean;
  allowSyncActions: boolean;
  allowSuggestionCreateActions: boolean;
}

export interface DocumentPresentationDecision {
  normalizedType: PresentationDocumentKind;
  template: DocumentPresentationTemplate;
  initialMode: DocumentPresentationMode;
  controlPolicy: DocumentControlPolicy;
  badges: string[];
  helpers: string[];
  reason?: string;
  source?: {
    rawDocumentType?: string | null;
    matchedAlias?: string | null;
    taxImportMatched?: boolean;
  };
}
