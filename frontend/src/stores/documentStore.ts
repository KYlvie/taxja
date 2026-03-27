import { create } from 'zustand';
import { Document, DocumentFilter } from '../types/document';

export type SortMode = 'upload_date' | 'document_date' | 'file_name';

const SORT_MODE_STORAGE_KEY = 'taxja_doc_sort_mode';

function loadSortMode(): SortMode {
  try {
    const stored = localStorage.getItem(SORT_MODE_STORAGE_KEY);
    if (stored === 'document_date') return 'document_date';
    if (stored === 'file_name') return 'file_name';
  } catch {
    // localStorage unavailable
  }
  return 'upload_date';
}

interface DocumentState {
  documents: Document[];
  currentDocument: Document | null;
  total: number;
  loading: boolean;
  error: string | null;
  filters: DocumentFilter;
  sortMode: SortMode;
  setDocuments: (documents: Document[], total: number) => void;
  setCurrentDocument: (document: Document | null) => void;
  addDocument: (document: Document) => void;
  updateDocument: (id: number, updates: Partial<Document>) => void;
  removeDocument: (id: number) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setFilters: (filters: DocumentFilter) => void;
  clearFilters: () => void;
  setSortMode: (mode: SortMode) => void;
}

export const useDocumentStore = create<DocumentState>((set) => ({
  documents: [],
  currentDocument: null,
  total: 0,
  loading: false,
  error: null,
  filters: {},
  sortMode: loadSortMode(),
  setDocuments: (documents, total) => set({ documents, total }),
  setCurrentDocument: (document) => set({ currentDocument: document }),
  addDocument: (document) =>
    set((state) => {
      const existingIndex = state.documents.findIndex((doc) => doc.id === document.id);
      if (existingIndex >= 0) {
        const nextDocuments = [...state.documents];
        nextDocuments[existingIndex] = { ...nextDocuments[existingIndex], ...document };
        return { documents: nextDocuments };
      }

      return {
        documents: [document, ...state.documents],
        total: state.total + 1,
      };
    }),
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
  setSortMode: (mode) => {
    try {
      localStorage.setItem(SORT_MODE_STORAGE_KEY, mode);
    } catch {
      // localStorage unavailable
    }
    set({ sortMode: mode });
  },
}));
