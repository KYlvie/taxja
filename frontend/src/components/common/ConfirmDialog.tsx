import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import './ConfirmDialog.css';

export interface ConfirmDialogProps {
  isOpen: boolean;
  title?: string;
  message: string;
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

  const variantEmoji: Record<string, string> = {
    info: '💡',
    warning: '⚠️',
    danger: '🗑️',
    success: '✅',
  };

  const btnClass = 'cfd-btn cfd-btn--' + variant;

  return (
    <div className="cfd-overlay" onClick={onCancel} role="dialog" aria-modal="true">
      <div className="cfd-dialog" onClick={(e) => e.stopPropagation()}>
        {/* AI Assistant header */}
        <div className="cfd-header">
          <div className="cfd-avatar">
            <span className="cfd-avatar-icon">🤖</span>
            <span className="cfd-avatar-pulse" />
          </div>
          <div className="cfd-header-info">
            <span className="cfd-assistant-name">Taxja AI</span>
            <span className="cfd-status">{isTyping ? t('ai.typing', '正在输入...') : t('ai.online', '在线')}</span>
          </div>
        </div>

        {/* Chat area */}
        <div className="cfd-chat">
          {showMessage && (
            <div className="cfd-bubble-row">
              <div className="cfd-bubble-avatar">🤖</div>
              <div className={'cfd-bubble cfd-bubble--' + variant}>
                {isTyping ? (
                  <div className="cfd-typing-dots">
                    <span /><span /><span />
                  </div>
                ) : (
                  <>
                    {title && (
                      <div className="cfd-bubble-title">
                        {variantEmoji[variant]} {title}
                      </div>
                    )}
                    <div className="cfd-bubble-text">{typedText}</div>
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
