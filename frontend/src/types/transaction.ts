// Transaction types and interfaces

export enum TransactionType {
  INCOME = 'income',
  EXPENSE = 'expense',
}

export enum IncomeCategory {
  AGRICULTURE = 'agriculture',
  SELF_EMPLOYMENT = 'self_employment',
  BUSINESS = 'business',
  EMPLOYMENT = 'employment',
  CAPITAL_GAINS = 'capital_gains',
  RENTAL = 'rental',
  OTHER_INCOME = 'other_income',
}

export enum ExpenseCategory {
  OFFICE_SUPPLIES = 'office_supplies',
  EQUIPMENT = 'equipment',
  TRAVEL = 'travel',
  MARKETING = 'marketing',
  PROFESSIONAL_SERVICES = 'professional_services',
  INSURANCE = 'insurance',
  MAINTENANCE = 'maintenance',
  PROPERTY_TAX = 'property_tax',
  LOAN_INTEREST = 'loan_interest',
  DEPRECIATION = 'depreciation',
  GROCERIES = 'groceries',
  UTILITIES = 'utilities',
  COMMUTING = 'commuting',
  HOME_OFFICE = 'home_office',
  OTHER = 'other',
}

export interface Transaction {
  id: number;
  type: TransactionType;
  amount: number;
  date: string;
  description: string;
  category: IncomeCategory | ExpenseCategory;
  is_deductible: boolean;
  deduction_reason?: string;
  is_system_generated?: boolean;
  property_id?: string;
  vat_rate?: number;
  vat_amount?: number;
  document_id?: number;
  classification_confidence?: number;
  // Recurring fields
  is_recurring?: boolean;
  recurring_frequency?: string;
  recurring_start_date?: string;
  recurring_end_date?: string;
  recurring_day_of_month?: number;
  recurring_is_active?: boolean;
  recurring_next_date?: string;
  recurring_last_generated?: string;
  parent_recurring_id?: number;
  created_at?: string;
  updated_at?: string;
}

export interface TransactionFilters {
  start_date?: string;
  end_date?: string;
  type?: TransactionType;
  category?: string;
  search?: string;
  is_deductible?: boolean;
  is_recurring?: boolean;
}

export interface TransactionFormData {
  type: TransactionType;
  amount: number | string;
  date: string;
  description: string;
  category: string;
  document_id?: number;
  property_id?: string | null;
  // Recurring fields
  is_recurring?: boolean;
  recurring_frequency?: string;
  recurring_start_date?: string;
  recurring_end_date?: string;
  recurring_day_of_month?: number;
}

export interface ImportResult {
  success: number;
  failed: number;
  duplicates: number;
  transactions: Transaction[];
  errors?: Array<{
    row: number;
    error: string;
  }>;
}

export interface PaginationParams {
  page: number;
  page_size: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
