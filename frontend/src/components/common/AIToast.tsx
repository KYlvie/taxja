import { useEffect, useRef, useState } from 'react';
import { useAIToastStore, type AIToast as AIToastType } from '../../stores/aiToastStore';
import './AIToast.css';

const variantEmoji: Record<string, string> = {
  success: '✅',
  error: '😅',
  warning: '⚠️',
  info: '💡',
};

/** Single toast item */
const ToastItem = ({ toast, onDismiss }: { toast: AIToastType; onDismiss: () => void }) => {
  const [exiting, setExiting] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout>>();
  const duration = toast.duration ?? 6000;

  const handleDismiss = () => {
    setExiting(true);
    setTimeout(onDismiss, 300); // match animation duration
  };

  useEffect(() => {
    timerRef.current = setTimeout(handleDismiss, duration);
    return () => clearTimeout(timerRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      className={`ai-toast ai-toast--${toast.variant} ${exiting ? 'ai-toast--exiting' : ''}`}
      onClick={handleDismiss}
      role="status"
      aria-live="polite"
      style={{ position: 'relative', overflow: 'hidden' }}
    >
      <div className="ai-toast-avatar">🤖</div>
      <div className="ai-toast-message">
        {variantEmoji[toast.variant]} {toast.message}
      </div>
      <div className="ai-toast-close">✕</div>
      <div
        className={`ai-toast-progress ai-toast-progress--${toast.variant}`}
        style={{ animationDuration: `${duration}ms` }}
      />
    </div>
  );
};

/** Global toast container — mount once in App */
const AIToastContainer = () => {
  const toasts = useAIToastStore((s) => s.toasts);
  const dismiss = useAIToastStore((s) => s.dismiss);

  if (toasts.length === 0) return null;

  return (
    <div className="ai-toast-container">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={() => dismiss(toast.id)} />
      ))}
    </div>
  );
};

export default AIToastContainer;
