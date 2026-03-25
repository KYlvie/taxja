import { useEffect, useRef, useState } from 'react';
import { Bot, CheckCircle2, CircleAlert, Info, TriangleAlert, type LucideIcon } from 'lucide-react';
import { useAIToastStore, type AIToast as AIToastType } from '../../stores/aiToastStore';
import { useThemeStore } from '../../stores/themeStore';
import FuturisticIcon, { type FuturisticIconTone } from './FuturisticIcon';
import './AIToast.css';

const variantIcons: Record<string, { icon: LucideIcon; tone: FuturisticIconTone }> = {
  success: { icon: CheckCircle2, tone: 'emerald' },
  error: { icon: CircleAlert, tone: 'rose' },
  warning: { icon: TriangleAlert, tone: 'amber' },
  info: { icon: Info, tone: 'violet' },
};

/** Single toast item */
const ToastItem = ({ toast, onDismiss, isCyber }: { toast: AIToastType; onDismiss: () => void; isCyber: boolean }) => {
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
      className={`ai-toast ai-toast--${toast.variant} ${exiting ? 'ai-toast--exiting' : ''} ${isCyber ? '' : 'ai-toast--standard'}`}
      onClick={handleDismiss}
      role="status"
      aria-live="polite"
      style={{ position: 'relative', overflow: 'hidden' }}
    >
      {isCyber && (
        <div className="ai-toast-avatar">
          <FuturisticIcon icon={Bot} tone="violet" size="sm" />
        </div>
      )}
      <div className="ai-toast-message">
        <FuturisticIcon icon={variantIcons[toast.variant].icon} tone={variantIcons[toast.variant].tone} size="xs" /> {toast.message}
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
  const theme = useThemeStore((s) => s.theme);
  const isCyber = theme === 'cyber';

  if (toasts.length === 0) return null;

  return (
    <div className="ai-toast-container">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={() => dismiss(toast.id)} isCyber={isCyber} />
      ))}
    </div>
  );
};

export default AIToastContainer;
