import { create } from 'zustand';
import { Document, DocumentFilter } from '../types/document';

interface DocumentState {
  documents: Document[];
  currentDocument: Document | null;
  total: number;
  loading: boolean;
  error: string | null;
  filters: DocumentFilter;
  setDocuments: (documents: Document[], total: number) => void;
  setCurrentDocument: (document: Document | null) => void;
  addDocument: (document: Document) => void;
  updateDocument: (id: number, updates: Partial<Document>) => void;
  removeDocument: (id: number) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setFilters: (filters: DocumentFilter) => void;
  clearFilters: () => void;
}

export const useDocumentStore = create<DocumentState>((set) => ({
  documents: [],
  currentDocument: null,
  total: 0,
  loading: false,
  error: null,
  filters: {},
  setDocuments: (documents, total) => set({ documents, total }),
  setCurrentDocument: (document) => set({ currentDocument: document }),
  addDocument: (document) =>
    set((state) => ({
      documents: [document, ...state.documents],
      total: state.total + 1,
    })),
  updateDocument: (id, updates) =>
    set((state) => ({
      documents: state.documents.map((doc) =>
        doc.id === id ? { ...doc, ...updates } : doc
      ),
      currentDocument:
        state.currentDocument?.id === id
          ? { ...state.currentDocument, ...updates }
          : state.currentDocument,
    })),
  removeDocument: (id) =>
    set((state) => ({
      documents: state.documents.filter((doc) => doc.id !== id),
      total: state.total - 1,
    })),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
  setFilters: (filters) => set({ filters }),
  clearFilters: () => set({ filters: {} }),
}));
