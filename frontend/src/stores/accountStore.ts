import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import {
  accountService,
  CancellationImpact,
  DataExportStatus,
  DeactivateAccountRequest,
} from '../services/accountService';

interface AccountState {
  cancellationImpact: CancellationImpact | null;
  exportStatus: DataExportStatus | null;
  isLoading: boolean;
  error: string | null;

  fetchCancellationImpact: () => Promise<void>;
  deactivateAccount: (data: DeactivateAccountRequest) => Promise<void>;
  reactivateAccount: (token: string) => Promise<void>;
  requestDataExport: (password: string) => Promise<string>;
  pollExportStatus: (taskId: string) => Promise<void>;
  clearError: () => void;
  reset: () => void;
}

export const useAccountStore = create<AccountState>()(
  devtools(
    (set) => ({
      cancellationImpact: null,
      exportStatus: null,
      isLoading: false,
      error: null,

      fetchCancellationImpact: async () => {
        set({ isLoading: true, error: null });
        try {
          const impact = await accountService.getCancellationImpact();
          set({ cancellationImpact: impact, isLoading: false });
        } catch (error) {
          const message = error instanceof Error ? error.message : 'Failed to fetch cancellation impact';
          set({ error: message, isLoading: false });
        }
      },

      deactivateAccount: async (data: DeactivateAccountRequest) => {
        set({ isLoading: true, error: null });
        try {
          await accountService.deactivateAccount(data);
          set({ isLoading: false });
        } catch (error) {
          const message = error instanceof Error ? error.message : 'Failed to deactivate account';
          set({ error: message, isLoading: false });
          throw error;
        }
      },

      reactivateAccount: async (token: string) => {
        set({ isLoading: true, error: null });
        try {
          await accountService.reactivateAccount(token);
          set({ isLoading: false });
        } catch (error) {
          const message = error instanceof Error ? error.message : 'Failed to reactivate account';
          set({ error: message, isLoading: false });
          throw error;
        }
      },

      requestDataExport: async (password: string) => {
        set({ isLoading: true, error: null });
        try {
          const result = await accountService.requestDataExport(password);
          // If sync export returned ready immediately, set exportStatus directly
          if (result.status === 'ready' && result.download_url) {
            set({
              isLoading: false,
              exportStatus: { status: 'ready', download_url: result.download_url, expires_at: null },
            });
          } else {
            set({ isLoading: false });
          }
          return result.task_id;
        } catch (error) {
          const message = error instanceof Error ? error.message : 'Failed to request data export';
          set({ error: message, isLoading: false });
          throw error;
        }
      },

      pollExportStatus: async (taskId: string) => {
        try {
          const status = await accountService.getExportStatus(taskId);
          set({ exportStatus: status });
        } catch (error) {
          const message = error instanceof Error ? error.message : 'Failed to check export status';
          set({ error: message });
        }
      },

      clearError: () => set({ error: null }),

      reset: () =>
        set({
          cancellationImpact: null,
          exportStatus: null,
          isLoading: false,
          error: null,
        }),
    }),
    { name: 'AccountStore' }
  )
);
