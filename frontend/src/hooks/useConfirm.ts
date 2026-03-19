import { create } from 'zustand';
import { useCallback } from 'react';

interface ConfirmState {
  isOpen: boolean;
  title?: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  variant: 'info' | 'warning' | 'danger' | 'success';
  showCancel: boolean;
  resolve: ((value: boolean) => void) | null;
}

interface ConfirmStore extends ConfirmState {
  show: (opts: Partial<Omit<ConfirmState, 'isOpen' | 'resolve'>>) => Promise<boolean>;
  close: (result: boolean) => void;
}

export const useConfirmStore = create<ConfirmStore>((set, get) => ({
  isOpen: false,
  message: '',
  variant: 'info',
  showCancel: true,
  resolve: null,

  show: (opts) => {
    return new Promise<boolean>((resolve) => {
      set({
        isOpen: true,
        title: opts.title,
        message: opts.message || '',
        confirmText: opts.confirmText,
        cancelText: opts.cancelText,
        variant: opts.variant || 'info',
        showCancel: opts.showCancel !== undefined ? opts.showCancel : true,
        resolve,
      });
    });
  },

  close: (result) => {
    const { resolve } = get();
    if (resolve) resolve(result);
    set({
      isOpen: false,
      title: undefined,
      message: '',
      confirmText: undefined,
      cancelText: undefined,
      variant: 'info',
      showCancel: true,
      resolve: null,
    });
  },
}));

/** Convenience hook for confirm/alert dialogs */
export function useConfirm() {
  const show = useConfirmStore((s) => s.show);

  const confirm = useCallback(
    (message: string, opts?: {
      title?: string;
      variant?: 'info' | 'warning' | 'danger' | 'success';
      confirmText?: string;
      cancelText?: string;
    }) => show({ message, showCancel: true, ...opts }),
    [show]
  );

  const alert = useCallback(
    (message: string, opts?: {
      title?: string;
      variant?: 'info' | 'warning' | 'danger' | 'success';
      confirmText?: string;
    }) => show({ message, showCancel: false, ...opts }),
    [show]
  );

  return { confirm, alert };
}
