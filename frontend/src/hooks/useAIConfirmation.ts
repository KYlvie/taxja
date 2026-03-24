import React from 'react';
import { useCallback } from 'react';
import { useConfirmStore } from './useConfirm';

interface ConfirmOptions {
  variant?: 'info' | 'warning' | 'danger' | 'success';
  confirmText?: string;
  cancelText?: string;
  messageNode?: React.ReactNode;
}

/**
 * Hook for requesting user confirmation via a floating modal dialog.
 * Delegates to the GlobalConfirmDialog (useConfirmStore) which is
 * already rendered in App.tsx.
 *
 * Usage:
 *   const { confirm, alert } = useAIConfirmation();
 *   const ok = await confirm('Are you sure?');
 *   if (!ok) return;
 */
export function useAIConfirmation() {
  const show = useConfirmStore((s) => s.show);

  const confirm = useCallback(
    (message: string, opts?: ConfirmOptions): Promise<boolean> =>
      show({
        message,
        messageNode: opts?.messageNode,
        variant: opts?.variant ?? 'warning',
        showCancel: true,
        confirmText: opts?.confirmText,
        cancelText: opts?.cancelText,
      }),
    [show]
  );

  const alert = useCallback(
    (message: string, opts?: ConfirmOptions): Promise<boolean> =>
      show({
        message,
        variant: opts?.variant ?? 'info',
        showCancel: false,
        confirmText: opts?.confirmText,
      }),
    [show]
  );

  return { confirm, alert };
}
