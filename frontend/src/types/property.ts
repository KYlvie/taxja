// Property types and interfaces for rental property and depreciable asset management

export enum PropertyType {
  RENTAL = 'rental',
  OWNER_OCCUPIED = 'owner_occupied',
  MIXED_USE = 'mixed_use',
}

export enum AssetCategory {
  REAL_ESTATE = 'real_estate',
  VEHICLE = 'vehicle',
  ELECTRIC_VEHICLE = 'electric_vehicle',
  COMPUTER = 'computer',
  PHONE = 'phone',
  OFFICE_FURNITURE = 'office_furniture',
  MACHINERY = 'machinery',
  TOOLS = 'tools',
  SOFTWARE = 'software',
  OTHER_EQUIPMENT = 'other_equipment',
}

/** Default useful life in years per Austrian tax law */
export const ASSET_USEFUL_LIFE: Record<string, number> = {
  vehicle: 8,
  electric_vehicle: 8,
  computer: 3,
  phone: 3,
  office_furniture: 10,
  machinery: 10,
  tools: 5,
  software: 3,
  other_equipment: 5,
  real_estate: 50,
};

export enum PropertyStatus {
  ACTIVE = 'active',
  SOLD = 'sold',
  ARCHIVED = 'archived',
  SCRAPPED = 'scrapped',
  WITHDRAWN = 'withdrawn',
}

export type DisposalReason = 'sold' | 'scrapped' | 'fully_depreciated' | 'private_withdrawal';

export interface DisposalRequest {
  disposal_reason: DisposalReason;
  disposal_date: string;
  sale_price?: number;
}

export type ComparisonBasis = 'net' | 'gross';
export type DepreciationMethod = 'linear' | 'degressive';
export type UsefulLifeSource = 'law' | 'tax_practice' | 'system_default' | 'user_override';
export type VatRecoverableStatus = 'likely_yes' | 'likely_no' | 'partial' | 'unclear';
export type IfbRateSource = 'statutory_window' | 'fallback_default' | 'not_applicable';
export type AssetRecognitionDecision =
  | 'expense_only'
  | 'gwg_suggestion'
  | 'create_asset_suggestion'
  | 'create_asset_auto'
  | 'duplicate_warning'
  | 'manual_review';

export interface Property {
  id: string; // UUID
  user_id: number;
  asset_type?: string;
  sub_category?: string;
  name?: string;
  property_type: PropertyType;
  rental_percentage: number;
  address: string;
  street: string;
  city: string;
  postal_code: string;
  purchase_date: string; // ISO date string
  purchase_price: number;
  building_value: number;
  land_value?: number;
  grunderwerbsteuer?: number; // Property transfer tax
  notary_fees?: number;
  registry_fees?: number;
  construction_year?: number;
  depreciation_rate: number;
  useful_life_years?: number;
  acquisition_kind?: string;
  put_into_use_date?: string;
  is_used_asset?: boolean;
  first_registration_date?: string;
  prior_owner_usage_years?: number;
  business_use_percentage?: number;
  comparison_basis?: ComparisonBasis;
  comparison_amount?: number;
  gwg_eligible?: boolean;
  gwg_elected?: boolean;
  depreciation_method?: DepreciationMethod;
  degressive_afa_rate?: number;
  useful_life_source?: UsefulLifeSource;
  income_tax_cost_cap?: number;
  income_tax_depreciable_base?: number;
  vat_recoverable_status?: VatRecoverableStatus;
  ifb_candidate?: boolean;
  ifb_rate?: number;
  ifb_rate_source?: IfbRateSource;
  recognition_decision?: AssetRecognitionDecision;
  policy_confidence?: number;
  supplier?: string;
  accumulated_depreciation?: number;
  disposal_reason?: string;
  status: PropertyStatus;
  sale_date?: string; // ISO date string
  sale_price?: number;
  kaufvertrag_document_id?: number; // Purchase contract document
  mietvertrag_document_id?: number; // Rental contract document
  annual_depreciation?: number;
  remaining_value?: number;
  created_at: string;
  updated_at: string;
}

export interface PropertyCreate {
  property_type?: PropertyType;
  rental_percentage?: number;
  street: string;
  city: string;
  postal_code: string;
  purchase_date: string; // ISO date string
  purchase_price: number;
  building_value?: number; // Auto-calculated as 80% if not provided
  construction_year?: number;
  depreciation_rate?: number; // Auto-determined based on construction year if not provided
  grunderwerbsteuer?: number;
  notary_fees?: number;
  registry_fees?: number;
}

export interface PropertyUpdate {
  property_type?: PropertyType;
  rental_percentage?: number;
  street?: string;
  city?: string;
  postal_code?: string;
  purchase_date?: string;
  purchase_price?: number;
  building_value?: number;
  construction_year?: number;
  depreciation_rate?: number;
  grunderwerbsteuer?: number;
  notary_fees?: number;
  registry_fees?: number;
  status?: PropertyStatus;
  sale_date?: string; // ISO date string
}

export interface PropertyMetrics {
  property_id: string; // UUID
  accumulated_depreciation: number;
  remaining_depreciable_value: number;
  annual_depreciation: number;
  total_rental_income: number;
  total_expenses: number;
  net_rental_income: number;
  years_remaining?: number;
  warnings?: unknown[]; // Tax validation warnings
}

export interface PropertyListItem {
  id: string; // UUID
  property_type: PropertyType;
  address: string;
  purchase_date: string;
  building_value: number;
  depreciation_rate: number;
  status: PropertyStatus;
  created_at: string;
}

export interface PropertyDetailResponse extends Property {
  metrics?: PropertyMetrics;
}

export interface PropertyListResponse {
  total: number;
  properties: PropertyListItem[];
  include_archived: boolean;
}

export interface PropertyFilters {
  status?: PropertyStatus;
  property_type?: PropertyType;
  search?: string;
  include_archived?: boolean;
}

export interface RentalContract {
  id: number;
  description: string;
  amount: number;
  unit_percentage: number | null;
  start_date: string | null;
  end_date: string | null;
  is_active: boolean;
  frequency: string | null;
  source_document_id: number | null;
}

export interface PropertyFormData {
  asset_category: 'real_estate' | 'other';
  // Real estate fields
  property_type: PropertyType;
  rental_percentage: number | string;
  street: string;
  city: string;
  postal_code: string;
  purchase_date: string;
  purchase_price: number | string;
  building_value?: number | string;
  construction_year?: number | string;
  depreciation_rate?: number | string;
  grunderwerbsteuer?: number | string;
  notary_fees?: number | string;
  registry_fees?: number | string;
  monthly_rent?: number | string;
  // Non-real-estate asset fields
  asset_type?: string;
  asset_name?: string;
  sub_category?: string;
  supplier?: string;
  business_use_percentage?: number | string;
  useful_life_years?: number | string;
  put_into_use_date?: string;
}
