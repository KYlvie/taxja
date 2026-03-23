export type LiabilityType =
  | 'property_loan'
  | 'business_loan'
  | 'owner_loan'
  | 'family_loan'
  | 'other_liability';

export type LiabilitySourceType =
  | 'manual'
  | 'document_confirmed'
  | 'document_auto_created'
  | 'system_migrated';

export type LiabilityReportCategory =
  | 'darlehen_und_kredite'
  | 'sonstige_verbindlichkeiten';

export interface LiabilityRelatedTransaction {
  id: number;
  type: string;
  amount: number;
  transaction_date: string;
  description?: string;
}

export interface LiabilityRelatedRecurring {
  id: number;
  recurring_type: string;
  description: string;
  amount: number;
  frequency: string;
  is_active: boolean;
  next_generation_date?: string | null;
}

export interface LiabilityRecord {
  id: number;
  user_id: number;
  liability_type: LiabilityType;
  source_type: LiabilitySourceType;
  display_name: string;
  currency: string;
  lender_name: string;
  principal_amount: number;
  outstanding_balance: number;
  interest_rate?: number | null;
  start_date: string;
  end_date?: string | null;
  monthly_payment?: number | null;
  tax_relevant: boolean;
  tax_relevance_reason?: string | null;
  report_category: LiabilityReportCategory;
  linked_property_id?: string | null;
  linked_loan_id?: number | null;
  source_document_id?: number | null;
  is_active: boolean;
  can_edit_directly: boolean;
  can_deactivate_directly: boolean;
  edit_via_document: boolean;
  requires_supporting_document: boolean;
  recommended_document_type: string;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface LiabilityDetail extends LiabilityRecord {
  related_transactions: LiabilityRelatedTransaction[];
  related_recurring_transactions: LiabilityRelatedRecurring[];
}

export interface LiabilityListResponse {
  items: LiabilityRecord[];
  total: number;
  active_count: number;
}

export interface LiabilitySummary {
  total_assets: number;
  total_liabilities: number;
  net_worth: number;
  active_liability_count: number;
  monthly_debt_service: number;
  annual_deductible_interest: number;
}

export interface LiabilityCreatePayload {
  liability_type: LiabilityType;
  display_name: string;
  currency?: string;
  lender_name: string;
  principal_amount: number;
  outstanding_balance: number;
  interest_rate?: number;
  start_date: string;
  end_date?: string;
  monthly_payment?: number;
  tax_relevant?: boolean;
  tax_relevance_reason?: string;
  report_category?: LiabilityReportCategory;
  linked_property_id?: string;
  source_document_id?: number;
  notes?: string;
  create_recurring_plan?: boolean;
  recurring_day_of_month?: number;
}

export interface LiabilityUpdatePayload extends Partial<LiabilityCreatePayload> {
  is_active?: boolean;
}
