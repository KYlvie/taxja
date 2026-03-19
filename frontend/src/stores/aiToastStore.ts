import { create } from 'zustand';

export interface AIToast {
  id: string;
  message: string;
  variant: 'success' | 'error' | 'info' | 'warning';
  /** Auto-dismiss after this many ms (default 6000) */
  duration?: number;
}

interface AIToastState {
  toasts: AIToast[];
  push: (toast: Omit<AIToast, 'id'>) => void;
  dismiss: (id: string) => void;
}

export const useAIToastStore = create<AIToastState>((set) => ({
  toasts: [],

  push: (toast) =>
    set((state) => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      const newToast: AIToast = { ...toast, id };
      // Keep max 5 toasts visible
      return { toasts: [...state.toasts, newToast].slice(-5) };
    }),

  dismiss: (id) =>
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    })),
}));

/** Convenience hook — call outside React components too */
export function aiToast(message: string, variant: AIToast['variant'] = 'info', duration?: number) {
  useAIToastStore.getState().push({ message, variant, duration });
}
