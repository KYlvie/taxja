import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Bot, CheckCircle2, Info, TriangleAlert, Trash2, type LucideIcon } from 'lucide-react';
import FuturisticIcon, { type FuturisticIconTone } from './FuturisticIcon';
import './ConfirmDialog.css';

export interface ConfirmDialogProps {
  isOpen: boolean;
  title?: string;
  message: string;
  messageNode?: React.ReactNode;
  confirmText?: string;
  cancelText?: string;
  variant?: 'info' | 'warning' | 'danger' | 'success';
  showCancel?: boolean;
  onConfirm: () => void;
  onCancel?: () => void;
}

const ConfirmDialog = ({
  isOpen,
  title,
  message,
  messageNode,
  confirmText,
  cancelText,
  variant = 'info',
  showCancel = true,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) => {
  const { t } = useTranslation();
  const [showMessage, setShowMessage] = useState(false);
  const [showButtons, setShowButtons] = useState(false);
  const [typedText, setTypedText] = useState('');
  const [isTyping, setIsTyping] = useState(false);

  useEffect(() => {
    if (!isOpen) {
      setShowMessage(false);
      setShowButtons(false);
      setTypedText('');
      setIsTyping(false);
      return;
    }

    // Show typing indicator first, then type out message
    setIsTyping(true);
    setShowMessage(true);

    const typingDelay = setTimeout(() => {
      setIsTyping(false);
      // Type out the message character by character
      let i = 0;
      const speed = Math.max(8, Math.min(25, 600 / message.length));
      const typeInterval = setInterval(() => {
        i++;
        setTypedText(message.slice(0, i));
        if (i >= message.length) {
          clearInterval(typeInterval);
          setTimeout(() => setShowButtons(true), 200);
        }
      }, speed);

      return () => clearInterval(typeInterval);
    }, 600);

    return () => clearTimeout(typingDelay);
  }, [isOpen, message]);

  if (!isOpen) return null;

  const variantIcon: Record<string, { icon: LucideIcon; tone: FuturisticIconTone }> = {
    info: { icon: Info, tone: 'violet' },
    warning: { icon: TriangleAlert, tone: 'amber' },
    danger: { icon: Trash2, tone: 'rose' },
    success: { icon: CheckCircle2, tone: 'emerald' },
  };

  const btnClass = 'cfd-btn cfd-btn--' + variant;

  return (
    <div className="cfd-overlay" onClick={onCancel} role="dialog" aria-modal="true">
      <div className="cfd-dialog" onClick={(e) => e.stopPropagation()}>
        {/* AI Assistant header */}
        <div className="cfd-header">
          <div className="cfd-avatar">
            <span className="cfd-avatar-icon">
              <FuturisticIcon icon={Bot} tone="violet" size="sm" />
            </span>
            <span className="cfd-avatar-pulse" />
          </div>
          <div className="cfd-header-info">
            <span className="cfd-assistant-name">Taxja AI</span>
            <span className="cfd-status">{isTyping ? t('ai.typing', 'Typing...') : t('ai.online', 'Online')}</span>
          </div>
        </div>

        {/* Chat area */}
        <div className="cfd-chat">
          {showMessage && (
            <div className="cfd-bubble-row">
              <div className="cfd-bubble-avatar">
                <FuturisticIcon icon={Bot} tone="violet" size="xs" />
              </div>
              <div className={'cfd-bubble cfd-bubble--' + variant}>
                {isTyping ? (
                  <div className="cfd-typing-dots">
                    <span /><span /><span />
                  </div>
                ) : (
                  <>
                    {title && (
                      <div className="cfd-bubble-title">
                        <FuturisticIcon icon={variantIcon[variant].icon} tone={variantIcon[variant].tone} size="xs" /> {title}
                      </div>
                    )}
                    <div className="cfd-bubble-text">
                      {typedText}
                      {messageNode && typedText.length >= message.length && (
                        <div className="cfd-bubble-extra" style={{ marginTop: '8px' }}>{messageNode}</div>
                      )}
                    </div>
                  </>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Action buttons */}
        <div className={'cfd-actions' + (showButtons ? ' cfd-actions--visible' : '')}>
          {showCancel && (
            <button className="cfd-btn cfd-btn--cancel" onClick={onCancel}>
              {cancelText || t('common.cancel')}
            </button>
          )}
          <button className={btnClass} onClick={onConfirm} disabled={!showButtons}>
            {confirmText || t('common.confirm')}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ConfirmDialog;
