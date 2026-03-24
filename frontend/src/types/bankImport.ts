export type BankStatementImportSourceType = 'csv' | 'mt940' | 'document';

export type BankStatementLineStatus =
  | 'pending_review'
  | 'auto_created'
  | 'matched_existing'
  | 'ignored_duplicate';

export type BankStatementSuggestedAction =
  | 'create_new'
  | 'match_existing'
  | 'ignore';

export interface BankStatementImportSummary {
  id: number;
  source_type: BankStatementImportSourceType;
  source_document_id?: number | null;
  bank_name?: string | null;
  iban?: string | null;
  statement_period?: string | null;
  tax_year?: number | null;
  created_at?: string | null;
  updated_at?: string | null;
  total_count: number;
  auto_created_count: number;
  matched_existing_count: number;
  pending_review_count: number;
  ignored_count: number;
}

export interface BankStatementTransactionSummary {
  id: number;
  type?: string | null;
  amount: string;
  transaction_date?: string | null;
  description?: string | null;
  income_category?: string | null;
  expense_category?: string | null;
  classification_confidence?: string | null;
  bank_reconciled?: boolean;
  bank_reconciled_at?: string | null;
}

export interface BankStatementLine {
  id: number;
  line_date?: string | null;
  amount: string;
  counterparty?: string | null;
  purpose?: string | null;
  raw_reference?: string | null;
  normalized_fingerprint?: string | null;
  review_status?: BankStatementLineStatus | null;
  suggested_action?: BankStatementSuggestedAction | null;
  confidence_score?: string | null;
  linked_transaction_id?: number | null;
  created_transaction_id?: number | null;
  reviewed_at?: string | null;
  reviewed_by?: number | null;
  linked_transaction?: BankStatementTransactionSummary | null;
  created_transaction?: BankStatementTransactionSummary | null;
}
