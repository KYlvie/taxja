// Property types and interfaces for rental property asset management

export enum PropertyType {
  RENTAL = 'rental',
  OWNER_OCCUPIED = 'owner_occupied',
  MIXED_USE = 'mixed_use',
}

export enum PropertyStatus {
  ACTIVE = 'active',
  SOLD = 'sold',
  ARCHIVED = 'archived',
}

export interface Property {
  id: string; // UUID
  user_id: number;
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
  registry_fees?: number; // Eintragungsgebühr
  construction_year?: number;
  depreciation_rate: number;
  status: PropertyStatus;
  sale_date?: string; // ISO date string
  kaufvertrag_document_id?: number; // Purchase contract document
  mietvertrag_document_id?: number; // Rental contract document
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
  warnings?: any[]; // Tax validation warnings
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

export interface PropertyFormData {
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
}
