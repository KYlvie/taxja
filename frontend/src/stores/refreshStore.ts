import { create } from 'zustand';

/**
 * Lightweight refresh signal store.
 * Components subscribe to specific counters and re-fetch when they change.
 * Triggered by DocumentUpload after OCR auto-creates properties/recurring/transactions.
 */
interface RefreshState {
  propertiesVersion: number;
  recurringVersion: number;
  transactionsVersion: number;
  dashboardVersion: number;

  refreshProperties: () => void;
  refreshRecurring: () => void;
  refreshTransactions: () => void;
  refreshDashboard: () => void;
  refreshAll: () => void;
}

export const useRefreshStore = create<RefreshState>((set) => ({
  propertiesVersion: 0,
  recurringVersion: 0,
  transactionsVersion: 0,
  dashboardVersion: 0,

  refreshProperties: () => set((s) => ({ propertiesVersion: s.propertiesVersion + 1 })),
  refreshRecurring: () => set((s) => ({ recurringVersion: s.recurringVersion + 1 })),
  refreshTransactions: () => set((s) => ({ transactionsVersion: s.transactionsVersion + 1 })),
  refreshDashboard: () => set((s) => ({ dashboardVersion: s.dashboardVersion + 1 })),
  refreshAll: () =>
    set((s) => ({
      propertiesVersion: s.propertiesVersion + 1,
      recurringVersion: s.recurringVersion + 1,
      transactionsVersion: s.transactionsVersion + 1,
      dashboardVersion: s.dashboardVersion + 1,
    })),
}));
