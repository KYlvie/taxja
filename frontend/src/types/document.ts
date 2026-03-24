export enum DocumentType {
  PAYSLIP = 'payslip',
  RECEIPT = 'receipt',
  INVOICE = 'invoice',
  PURCHASE_CONTRACT = 'purchase_contract',
  RENTAL_CONTRACT = 'rental_contract',
  LOAN_CONTRACT = 'loan_contract',
  BANK_STATEMENT = 'bank_statement',
  PROPERTY_TAX = 'property_tax',
  SVS_NOTICE = 'svs_notice',
  LOHNZETTEL = 'lohnzettel',
  EINKOMMENSTEUERBESCHEID = 'einkommensteuerbescheid',
  E1_FORM = 'e1_form',
  L1_FORM = 'l1_form',
  L1K_BEILAGE = 'l1k_beilage',
  L1AB_BEILAGE = 'l1ab_beilage',
  E1A_BEILAGE = 'e1a_beilage',
  E1B_BEILAGE = 'e1b_beilage',
  E1KV_BEILAGE = 'e1kv_beilage',
  U1_FORM = 'u1_form',
  U30_FORM = 'u30_form',
  JAHRESABSCHLUSS = 'jahresabschluss',
  SPENDENBESTAETIGUNG = 'spendenbestaetigung',
  VERSICHERUNGSBESTAETIGUNG = 'versicherungsbestaetigung',
  KINDERBETREUUNGSKOSTEN = 'kinderbetreuungskosten',
  FORTBILDUNGSKOSTEN = 'fortbildungskosten',
  PENDLERPAUSCHALE = 'pendlerpauschale',
  KIRCHENBEITRAG = 'kirchenbeitrag',
  GRUNDBUCHAUSZUG = 'grundbuchauszug',
  BETRIEBSKOSTENABRECHNUNG = 'betriebskostenabrechnung',
  GEWERBESCHEIN = 'gewerbeschein',
  KONTOAUSZUG = 'kontoauszug',
  OTHER = 'other',
  UNKNOWN = 'unknown',
}

export interface ExtractedData {
  date?: string;
  amount?: number;
  merchant?: string;
  items?: LineItem[];
  vat_amounts?: Record<string, number>;
  gross_income?: number;
  net_income?: number;
  withheld_tax?: number;
  employer?: string;
  invoice_number?: string;
  supplier?: string;
  confidence?: Record<string, number>;
  // Mietvertrag (rental contract) fields
  property_address?: string;
  monthly_rent?: number;
  start_date?: string;
  end_date?: string;
  tenant_name?: string;
  landlord_name?: string;
  user_contract_role?: string;
  user_contract_role_source?: string;
  user_contract_role_confidence?: number;
  contract_role_resolution?: Record<string, any>;
  document_transaction_direction?: string;
  document_transaction_direction_source?: string;
  document_transaction_direction_confidence?: number;
  transaction_direction_resolution?: Record<string, any>;
  commercial_document_semantics?: string;
  is_reversal?: boolean;
  contract_type?: string;
  betriebskosten?: number;
  heating_costs?: number;
  deposit_amount?: number;
  // Kaufvertrag (purchase contract) fields
  purchase_price?: number;
  purchase_date?: string;
  buyer_name?: string;
  seller_name?: string;
  purchase_contract_kind?: 'property' | 'asset' | string;
  asset_name?: string;
  asset_type?: string;
  first_registration_date?: string;
  vehicle_identification_number?: string;
  license_plate?: string;
  mileage_km?: number;
  is_used_asset?: boolean;
  previous_owners?: number;
  building_value?: number;
  land_value?: number;
  grunderwerbsteuer?: number;
  notary_name?: string;
  notary_fees?: number;
  registry_fees?: number;
  // Allow additional dynamic fields
  [key: string]: any;
}

export interface LineItem {
  description: string;
  amount: number;
  quantity?: number;
  category?: string;
  is_deductible?: boolean;
  deduction_reason?: string;
  vat_rate?: number | null;
  sort_order?: number;
}

export interface Document {
  id: number;
  user_id: number;
  document_type: DocumentType;
  file_path: string;
  file_name: string;
  file_size: number;
  mime_type: string;
  ocr_result?: ExtractedData;
  ocr_status?: string;
  raw_text?: string;
  confidence_score: number;
  needs_review: boolean;
  transaction_id?: number;
  created_at: string;
  updated_at: string;
  uploaded_at?: string;
  processed_at?: string;
  message?: string;
  deduplicated?: boolean;
  duplicate_of_document_id?: number | null;
}

export interface UploadProgress {
  file: File;
  source_files?: File[];
  upload_mode?: 'single' | 'image_group';
  page_count?: number;
  progress: number;
  status: 'pending' | 'uploading' | 'processing' | 'completed' | 'error';
  error?: string;
  document?: Document;
}

export interface OCRReviewData {
  document: Document;
  extracted_data: ExtractedData;
  suggestions?: string[];
}

export interface DocumentFilter {
  document_type?: DocumentType;
  start_date?: string;
  end_date?: string;
  search?: string;
  needs_review?: boolean;
}
