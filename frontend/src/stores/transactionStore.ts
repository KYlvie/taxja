import { create } from 'zustand';
import { Transaction, TransactionFilters } from '../types/transaction';

interface TransactionState {
  transactions: Transaction[];
  filters: TransactionFilters;
  selectedTransaction: Transaction | null;
  isLoading: boolean;
  error: string | null;
  pagination: {
    page: number;
    pageSize: number;
    total: number;
  };
  setTransactions: (transactions: Transaction[]) => void;
  addTransaction: (transaction: Transaction) => void;
  updateTransaction: (id: number, transaction: Partial<Transaction>) => void;
  deleteTransaction: (id: number) => void;
  setFilters: (filters: TransactionFilters) => void;
  setSelectedTransaction: (transaction: Transaction | null) => void;
  setLoading: (isLoading: boolean) => void;
  setError: (error: string | null) => void;
  setPagination: (pagination: Partial<TransactionState['pagination']>) => void;
  clearFilters: () => void;
}

export const useTransactionStore = create<TransactionState>((set) => ({
  transactions: [],
  filters: {},
  selectedTransaction: null,
  isLoading: false,
  error: null,
  pagination: {
    page: 1,
    pageSize: 20,
    total: 0,
  },
  setTransactions: (transactions) => set({ transactions }),
  addTransaction: (transaction) =>
    set((state) => ({
      transactions: [transaction, ...state.transactions],
    })),
  updateTransaction: (id, updatedTransaction) =>
    set((state) => ({
      transactions: state.transactions.map((t) =>
        t.id === id ? { ...t, ...updatedTransaction } : t
      ),
    })),
  deleteTransaction: (id) =>
    set((state) => ({
      transactions: state.transactions.filter((t) => t.id !== id),
    })),
  setFilters: (filters) => set({ filters }),
  setSelectedTransaction: (transaction) =>
    set({ selectedTransaction: transaction }),
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
  setPagination: (pagination) =>
    set((state) => ({
      pagination: { ...state.pagination, ...pagination },
    })),
  clearFilters: () => set({ filters: {} }),
}));
