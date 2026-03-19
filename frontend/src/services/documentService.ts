import api from './api';
import { Document, DocumentFilter, OCRReviewData } from '../types/document';

export interface AssetSuggestionConfirmationPayload {
  put_into_use_date?: string;
  business_use_percentage?: number;
  is_used_asset?: boolean;
  first_registration_date?: string;
  prior_owner_usage_years?: number;
  gwg_elected?: boolean;
  depreciation_method?: 'linear' | 'degressive';
  degressive_afa_rate?: number;
  useful_life_years?: number;
}

export const documentService = {
  // Upload single document
  uploadDocument: async (
    file: File,
    onProgress?: (progress: number) => void,
    propertyId?: string
  ): Promise<Document> => {
    const formData = new FormData();
    formData.append('file', file);

    const url = propertyId
      ? `/documents/upload?property_id=${encodeURIComponent(propertyId)}`
      : '/documents/upload';

    const response = await api.post<Document>(url, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 120000, // 2min — OCR processing runs synchronously
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total && onProgress) {
          const percentCompleted = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          onProgress(percentCompleted);
        }
      },
    });

    return response.data;
  },

  uploadImageGroup: async (
    files: File[],
    onProgress?: (progress: number) => void,
    propertyId?: string
  ): Promise<Document> => {
    const formData = new FormData();
    files.forEach((file) => {
      formData.append('files', file);
    });

    const url = propertyId
      ? `/documents/upload-image-group?property_id=${encodeURIComponent(propertyId)}`
      : '/documents/upload-image-group';

    const response = await api.post<Document>(url, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 120000,
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total && onProgress) {
          const percentCompleted = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          onProgress(percentCompleted);
        }
      },
    });

    return response.data;
  },

  // Batch upload documents
  batchUpload: async (
    files: File[],
    _onProgress?: (fileIndex: number, progress: number) => void
  ): Promise<Document[]> => {
    const formData = new FormData();
    files.forEach((file) => {
      formData.append('files', file);
    });

    const response = await api.post(
      '/documents/batch-upload',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 300000, // 5min for batch
      }
    );

    // Backend returns {successful: [...], failed: [...], ...}
    return response.data.successful || response.data.documents || [];
  },

  // Get document list with filters
  getDocuments: async (
    filters?: DocumentFilter,
    page: number = 1,
    pageSize: number = 20
  ): Promise<{ documents: Document[]; total: number }> => {
    const params = new URLSearchParams();
    params.append('page', page.toString());
    params.append('page_size', pageSize.toString());

    if (filters?.document_type) {
      params.append('document_type', filters.document_type);
    }
    if (filters?.start_date) {
      params.append('start_date', filters.start_date);
    }
    if (filters?.end_date) {
      params.append('end_date', filters.end_date);
    }
    if (filters?.search) {
      params.append('search_text', filters.search);
    }

    const response = await api.get(`/documents?${params.toString()}`);
    const data = response.data;
    // Map backend field names to frontend Document type
    let documents = (data.documents || []).map((doc: any) => ({
      ...doc,
      created_at: doc.created_at || doc.uploaded_at,
      updated_at: doc.updated_at || doc.processed_at || doc.uploaded_at,
      needs_review: doc.needs_review ?? (doc.confidence_score != null && doc.confidence_score < 0.7),
    }));
    // Client-side filter for needs_review (not supported by backend)
    if (filters?.needs_review) {
      documents = documents.filter((doc: any) => doc.needs_review);
    }
    return { documents, total: filters?.needs_review ? documents.length : (data.total || 0) };
  },

  // Get single document
  getDocument: async (id: number): Promise<Document> => {
    const response = await api.get(`/documents/${id}`);
    const doc = response.data;
    return {
      ...doc,
      created_at: doc.created_at || doc.uploaded_at,
      updated_at: doc.updated_at || doc.processed_at || doc.uploaded_at,
      needs_review: doc.needs_review ?? (doc.confidence_score != null && doc.confidence_score < 0.7),
    };
  },

  // Get document for OCR review
  getDocumentForReview: async (id: number): Promise<OCRReviewData> => {
    // First get the document details
    const docResponse = await api.get(`/documents/${id}`);
    const doc = docResponse.data;
    const mappedDoc = {
      ...doc,
      created_at: doc.created_at || doc.uploaded_at,
      updated_at: doc.updated_at || doc.processed_at || doc.uploaded_at,
      needs_review: doc.needs_review ?? (doc.confidence_score != null && doc.confidence_score < 0.7),
    };

    // Try to get OCR review data
    let extractedData: any = {};
    let suggestions: string[] = [];
    try {
      const reviewResponse = await api.get(`/documents/${id}/review`);
      const review = reviewResponse.data;
      // Map extracted_fields array to ExtractedData object
      if (review.extracted_fields) {
        for (const field of review.extracted_fields) {
          extractedData[field.field_name] = field.value;
          if (!extractedData.confidence) extractedData.confidence = {};
          extractedData.confidence[field.field_name] = field.confidence;
        }
      }
      suggestions = review.suggestions || [];
      // Override confidence from review
      if (review.overall_confidence != null) {
        mappedDoc.confidence_score = review.overall_confidence;
      }
    } catch {
      // If review endpoint fails, use ocr_result from document
      extractedData = doc.ocr_result || {};
    }

    return { document: mappedDoc, extracted_data: extractedData, suggestions };
  },

  // Confirm OCR results
  confirmOCR: async (id: number): Promise<void> => {
    await api.post(`/documents/${id}/confirm`, { confirmed: true });
  },

  // Correct OCR results
  correctOCR: async (
    id: number,
    correctedData: Record<string, any>
  ): Promise<Document> => {
    const response = await api.post(
      `/documents/${id}/correct`,
      { corrected_data: correctedData }
    );
    return response.data;
  },

  // Download document
  downloadDocument: async (id: number): Promise<Blob> => {
    const response = await api.get(`/documents/${id}/download`, {
      responseType: 'blob',
    });
    return response.data;
  },

  // Delete document
  deleteDocument: async (id: number, deleteMode: 'document_only' | 'with_data' = 'document_only'): Promise<void> => {
    await api.delete(`/documents/${id}?delete_mode=${deleteMode}`);
  },

  // Get related data for a document (before deletion)
  getDocumentRelatedData: async (id: number): Promise<any> => {
    const response = await api.get(`/documents/${id}/related-data`);
    return response.data;
  },

  // Get document URL for preview
  getDocumentUrl: (id: number): string => {
    const baseURL = api.defaults.baseURL || '/api/v1';
    return `${baseURL}/documents/${id}/download`;
  },

  // Confirm property creation from Kaufvertrag OCR suggestion
  confirmProperty: async (id: number): Promise<any> => {
    const response = await api.post(`/documents/${id}/confirm-property`);
    return response.data;
  },

  // Confirm recurring income creation from Mietvertrag OCR suggestion
  confirmRecurring: async (id: number): Promise<any> => {
    const response = await api.post(`/documents/${id}/confirm-recurring`);
    return response.data;
  },

  // Confirm recurring expense creation from invoice/insurance OCR suggestion
  confirmRecurringExpense: async (id: number): Promise<any> => {
    const response = await api.post(`/documents/${id}/confirm-recurring-expense`);
    return response.data;
  },

  // Confirm loan creation from Kreditvertrag OCR suggestion
  confirmLoan: async (id: number): Promise<any> => {
    const response = await api.post(`/documents/${id}/confirm-loan`);
    return response.data;
  },

  // Confirm asset creation from vehicle/equipment Kaufvertrag OCR suggestion
  confirmAsset: async (id: number, confirmation?: AssetSuggestionConfirmationPayload): Promise<any> => {
    const response = await api.post(`/documents/${id}/confirm-asset`, confirmation || {});
    return response.data;
  },

  // Dismiss an import suggestion
  dismissSuggestion: async (id: number): Promise<any> => {
    const response = await api.post(`/documents/${id}/dismiss-suggestion`);
    return response.data;
  },

  // Confirm tax filing data from OCR suggestion (L16, L1, E1a, E1b, etc.)
  confirmTaxData: async (id: number): Promise<any> => {
    const response = await api.post(`/documents/${id}/confirm-tax-data`);
    return response.data;
  },

  // Retry OCR processing (re-process document)
  retryOcr: async (id: number): Promise<any> => {
    const response = await api.post(`/documents/${id}/retry-ocr`, null, { timeout: 120000 });
    return response.data;
  },

  // Batch import selected bank transactions from Kontoauszug OCR
  confirmBankTransactions: async (id: number, transactionIndices: number[]): Promise<any> => {
    const response = await api.post(`/documents/${id}/confirm-bank-transactions`, {
      transaction_indices: transactionIndices,
    });
    return response.data;
  },

  // =========================================================================
  // AI Unified Interaction — Process Status & Follow-Up
  // =========================================================================

  /**
   * Get current processing phase for a document.
   * Frontend polls this to show real-time progress in the chat panel.
   * Returns ui_state, idempotency_key (backend-generated), phase timestamps, etc.
   */
  getProcessStatus: async (id: number, lang: string = 'en'): Promise<ProcessStatusResponse> => {
    const response = await api.get<ProcessStatusResponse>(
      `/documents/${id}/process-status`,
      { params: { lang } }
    );
    return response.data;
  },

  /**
   * Submit user answers to follow-up questions for a document suggestion.
   * Supports: full answers, partial answers, use_defaults mode.
   * Enforces optimistic concurrency via suggestion_version (409 on mismatch).
   */
  submitFollowUp: async (
    id: number,
    answers: Record<string, any>,
    options?: {
      useDefaults?: boolean;
      suggestionVersion?: number;
    }
  ): Promise<FollowUpAnswerResponse> => {
    const response = await api.post<FollowUpAnswerResponse>(
      `/documents/${id}/follow-up`,
      {
        answers,
        use_defaults: options?.useDefaults ?? false,
        suggestion_version: options?.suggestionVersion ?? null,
      }
    );
    return response.data;
  },

  /**
   * Generic action confirm — dispatches based on ActionDescriptor from backend.
   * No per-type switch needed; the action contract is self-describing.
   */
  executeAction: async (
    endpoint: string,
    method: string = 'POST',
    payload?: Record<string, any>
  ): Promise<any> => {
    const config = { timeout: 30000 };
    let response;
    if (method === 'POST') {
      response = await api.post(endpoint, payload || {}, config);
    } else if (method === 'PUT') {
      response = await api.put(endpoint, payload || {}, config);
    } else if (method === 'DELETE') {
      response = await api.delete(endpoint, config);
    } else {
      throw new Error(`Unsupported method: ${method}`);
    }
    return response.data;
  },
};

// =============================================================================
// Response Types for AI Unified Interaction
// =============================================================================

export interface ProcessStatusResponse {
  phase: string;
  document_type: string | null;
  message: string;
  ui_state: 'processing' | 'needs_input' | 'ready_to_confirm' | 'confirmed' | 'dismissed' | 'error';
  suggestion: Record<string, any> | null;
  phase_started_at: string | null;
  phase_updated_at: string | null;
  current_phase_attempt: number;
  suggestion_version: number | null;
  idempotency_key: string;
  action: ActionDescriptorResponse | null;
  follow_up_questions: FollowUpQuestionResponse[] | null;
}

export interface ActionDescriptorResponse {
  kind: string;
  target_id: string;
  endpoint: string;
  method: string;
  payload?: Record<string, any>;
  confirm_label?: Record<string, string>;
  dismiss_label?: Record<string, string>;
  detail_label?: Record<string, string>;
}

export interface FollowUpQuestionResponse {
  id: string;
  question: Record<string, string>;
  input_type: string;
  options?: any[];
  default_value?: any;
  required: boolean;
  field_key: string;
  help_text?: Record<string, string>;
  validation?: Record<string, any>;
}

export interface FollowUpAnswerResponse {
  status: string;
  ui_state: string;
  suggestion_version: number;
  remaining_questions: number;
  remaining_question_list: any[];
  applied_defaults: Record<string, any>;
}
