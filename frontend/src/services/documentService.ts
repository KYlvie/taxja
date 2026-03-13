import api from './api';
import { Document, DocumentFilter, OCRReviewData } from '../types/document';

export const documentService = {
  // Upload single document
  uploadDocument: async (
    file: File,
    onProgress?: (progress: number) => void
  ): Promise<Document> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await api.post<Document>('/documents/upload', formData, {
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

  // Dismiss an import suggestion
  dismissSuggestion: async (id: number): Promise<any> => {
    const response = await api.post(`/documents/${id}/dismiss-suggestion`);
    return response.data;
  },
};
