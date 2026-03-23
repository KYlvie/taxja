// Transaction types and interfaces

export enum TransactionType {
  INCOME = 'income',
  EXPENSE = 'expense',
  ASSET_ACQUISITION = 'asset_acquisition',
  LIABILITY_DRAWDOWN = 'liability_drawdown',
  LIABILITY_REPAYMENT = 'liability_repayment',
  TAX_PAYMENT = 'tax_payment',
  TRANSFER = 'transfer',
}

export const CATEGORIZED_TRANSACTION_TYPES = [
  TransactionType.INCOME,
  TransactionType.EXPENSE,
] as const;

export function transactionTypeRequiresCategory(type: TransactionType): boolean {
  return CATEGORIZED_TRANSACTION_TYPES.includes(type as (typeof CATEGORIZED_TRANSACTION_TYPES)[number]);
}

export function isExpenseTransactionType(type: TransactionType): boolean {
  return type === TransactionType.EXPENSE;
}

export function getTransactionAmountTone(type: TransactionType): 'positive' | 'negative' | 'neutral' {
  switch (type) {
    case TransactionType.INCOME:
    case TransactionType.LIABILITY_DRAWDOWN:
      return 'positive';
    case TransactionType.EXPENSE:
    case TransactionType.ASSET_ACQUISITION:
    case TransactionType.LIABILITY_REPAYMENT:
    case TransactionType.TAX_PAYMENT:
      return 'negative';
    case TransactionType.TRANSFER:
    default:
      return 'neutral';
  }
}

export function getTransactionAmountPrefix(type: TransactionType): string {
  const tone = getTransactionAmountTone(type);
  if (tone === 'positive') return '+';
  if (tone === 'negative') return '-';
  return '';
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
  VEHICLE = 'vehicle',
  TELECOM = 'telecom',
  RENT = 'rent',
  BANK_FEES = 'bank_fees',
  SVS_CONTRIBUTIONS = 'svs_contributions',
  CLEANING = 'cleaning',
  CLOTHING = 'clothing',
  SOFTWARE = 'software',
  SHIPPING = 'shipping',
  FUEL = 'fuel',
  EDUCATION = 'education',
  PROPERTY_MANAGEMENT_FEES = 'property_management_fees',
  PROPERTY_INSURANCE = 'property_insurance',
  DEPRECIATION_AFA = 'depreciation_afa',
  OTHER = 'other',
}

export enum LineItemPostingType {
  INCOME = 'income',
  EXPENSE = 'expense',
  PRIVATE_USE = 'private_use',
  ASSET_ACQUISITION = 'asset_acquisition',
  LIABILITY_DRAWDOWN = 'liability_drawdown',
  LIABILITY_REPAYMENT = 'liability_repayment',
  TAX_PAYMENT = 'tax_payment',
  TRANSFER = 'transfer',
}

export enum LineItemAllocationSource {
  MANUAL = 'manual',
  OCR_SPLIT = 'ocr_split',
  PERCENTAGE_RULE = 'percentage_rule',
  CAP_RULE = 'cap_rule',
  LOAN_INSTALLMENT = 'loan_installment',
  MIXED_USE_RULE = 'mixed_use_rule',
  VAT_POLICY = 'vat_policy',
  LEGACY_BACKFILL = 'legacy_backfill',
}

export interface LineItem {
  id?: number;
  description: string;
  amount: number;
  quantity: number;
  posting_type?: LineItemPostingType;
  allocation_source?: LineItemAllocationSource;
  category?: string;
  is_deductible: boolean;
  deduction_reason?: string;
  vat_rate?: number | null;
  vat_amount?: number | null;
  vat_recoverable_amount?: number | null;
  rule_bucket?: string;
  classification_method?: string;
  classification_confidence?: number;
  sort_order: number;
}

export interface Transaction {
  id: number;
  type: TransactionType;
  amount: number;
  date: string;
  description: string;
  category?: IncomeCategory | ExpenseCategory | string | null;
  is_deductible: boolean;
  deduction_reason?: string;
  is_system_generated?: boolean;
  needs_review?: boolean;
  ai_review_notes?: string;
  reviewed?: boolean;
  locked?: boolean;
  property_id?: string;
  vat_rate?: number;
  vat_amount?: number;
  document_id?: number;
  classification_confidence?: number;
  classification_method?: string;
  // Line items
  line_items?: LineItem[];
  deductible_amount?: number;
  non_deductible_amount?: number;
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
  source_recurring_id?: number;
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
  needs_review?: boolean;
}

export interface TransactionFormData {
  type: TransactionType;
  amount: number | string;
  date: string;
  description: string;
  category?: string;
  document_id?: number;
  property_id?: string | null;
  // Deductibility override
  is_deductible?: boolean;
  deduction_reason?: string;
  // Recurring fields
  is_recurring?: boolean;
  recurring_frequency?: string;
  recurring_start_date?: string;
  recurring_end_date?: string;
  recurring_day_of_month?: number;
  line_items?: LineItem[];
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
  available_years?: number[];
}
