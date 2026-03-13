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
  contract_type?: string;
  betriebskosten?: number;
  heating_costs?: number;
  deposit_amount?: number;
  // Kaufvertrag (purchase contract) fields
  purchase_price?: number;
  purchase_date?: string;
  buyer_name?: string;
  seller_name?: string;
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
  is_deductible?: boolean;
  deduction_reason?: string;
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
}

export interface UploadProgress {
  file: File;
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
