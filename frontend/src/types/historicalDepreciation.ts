// Types for historical depreciation backfill feature

export interface HistoricalDepreciationYear {
  year: number;
  amount: number;
  transaction_date: string; // ISO date string (December 31 of year)
}

export interface HistoricalDepreciationPreview {
  property_id: string;
  years: HistoricalDepreciationYear[];
  total_amount: number;
  years_count: number;
}

export interface BackfillResult {
  property_id: string;
  years_backfilled: number;
  total_amount: number;
  transactions_created: HistoricalDepreciationYear[];
}
