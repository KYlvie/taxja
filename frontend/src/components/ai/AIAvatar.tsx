/**
 * AIAvatar — Task 1
 *
 * Single source of truth for AI avatar rendering across all AI surfaces.
 * Replaces: emoji icons in ConfirmDialog, gradient circles in ChatInterface,
 * avatar spans in AIToast, emoji icons in FloatingAIChat proactive messages.
 *
 * Requirements: FR-16
 */
import './AIAvatar.css';

interface AIAvatarProps {
  /** sm = 20px, md = 26px, lg = 36px */
  size?: 'sm' | 'md' | 'lg';
  /** online = static, thinking = pulse animation, idle = dimmed */
  status?: 'online' | 'thinking' | 'idle';
  /** Additional class names */
  className?: string;
}

export default function AIAvatar({
  size = 'md',
  status = 'online',
  className = '',
}: AIAvatarProps) {
  return (
    <div
      className={`ai-avatar ai-avatar--${size} ai-avatar--${status} ${className}`.trim()}
      aria-hidden="true"
    >
      <span className="ai-avatar__letter">T</span>
      {status === 'thinking' && <div className="ai-avatar__pulse" />}
    </div>
  );
}
