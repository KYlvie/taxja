export enum RecurrenceFrequency {
  MONTHLY = 'monthly',
  QUARTERLY = 'quarterly',
  ANNUALLY = 'annually',
  WEEKLY = 'weekly',
  BIWEEKLY = 'biweekly',
}

export enum RecurringTransactionType {
  RENTAL_INCOME = 'rental_income',
  LOAN_INTEREST = 'loan_interest',
  DEPRECIATION = 'depreciation',
  MANUAL = 'manual',
}

export interface RecurringTransaction {
  id: number;
  user_id: number;
  recurring_type: RecurringTransactionType;
  property_id?: string;
  loan_id?: number;
  description: string;
  amount: number;
  transaction_type: 'income' | 'expense';
  category: string;
  frequency: RecurrenceFrequency;
  start_date: string;
  end_date?: string;
  day_of_month?: number;
  is_active: boolean;
  paused_at?: string;
  last_generated_date?: string;
  next_generation_date?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface RecurringTransactionListResponse {
  items: RecurringTransaction[];
  total: number;
  active_count: number;
  paused_count: number;
}

export interface RentalIncomeRecurringCreate {
  property_id: string;
  monthly_rent: number;
  start_date: string;
  end_date?: string;
  day_of_month?: number;
}

export interface LoanInterestRecurringCreate {
  loan_id: number;
  monthly_interest: number;
  start_date: string;
  end_date?: string;
  day_of_month?: number;
}

export interface RecurringTransactionUpdate {
  description?: string;
  amount?: number;
  frequency?: RecurrenceFrequency;
  end_date?: string;
  day_of_month?: number;
  notes?: string;
  is_active?: boolean;
}
