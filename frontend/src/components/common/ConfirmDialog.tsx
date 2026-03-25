import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { useThemeStore } from '../../stores/themeStore';
import RobotMascot from './RobotMascot';
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

const ROBOT_SIZE = 420;

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
  const theme = useThemeStore((s) => s.theme);
  const isCyber = theme === 'cyber';

  const [visible, setVisible] = useState(false);
  const [showBubble, setShowBubble] = useState(false);
  const [typedText, setTypedText] = useState('');
  const [showButtons, setShowButtons] = useState(false);
  const [exiting, setExiting] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setVisible(true);
      setExiting(false);
      setTypedText('');
      setShowBubble(false);
      setShowButtons(false);

      if (isCyber) {
        // Cyber mode: typing animation with robot
        const bubbleTimer = setTimeout(() => {
          setShowBubble(true);
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
        }, 500);
        return () => clearTimeout(bubbleTimer);
      } else {
        // Classic mode: show immediately, no typing animation
        setShowBubble(true);
        setTypedText(message);
        setShowButtons(true);
      }
    } else {
      if (visible) {
        setExiting(true);
        const exitTimer = setTimeout(() => {
          setVisible(false);
          setExiting(false);
        }, isCyber ? 400 : 200);
        return () => clearTimeout(exitTimer);
      }
    }
  }, [isOpen, message, isCyber]);

  if (!visible) return null;

  const variantColors: Record<string, string> = {
    info: '#7c3aed',
    warning: '#d97706',
    danger: '#dc2626',
    success: '#16a34a',
  };

  const handleConfirm = () => {
    setExiting(true);
    setTimeout(() => {
      onConfirm();
    }, isCyber ? 300 : 150);
  };

  const handleCancel = () => {
    setExiting(true);
    setTimeout(() => {
      onCancel?.();
    }, isCyber ? 300 : 150);
  };

  /* ── Cyber mode: full-screen robot ── */
  if (isCyber) {
    return createPortal(
      <div
        className={`cfd-robot-overlay ${exiting ? 'cfd-robot-overlay--exit' : ''}`}
        onClick={handleCancel}
        role="dialog"
        aria-modal="true"
      >
        <div className="cfd-robot-scene" onClick={(e) => e.stopPropagation()}>
          <div className="cfd-robot-container">
            <RobotMascot size={ROBOT_SIZE} />
          </div>
          {showBubble && (
            <div className={`cfd-robot-bubble cfd-robot-bubble--${variant}`}>
              {title && <div className="cfd-robot-bubble-title">{title}</div>}
              <div className="cfd-robot-bubble-text">
                {typedText}
                {typedText.length >= message.length && messageNode && (
                  <div className="cfd-robot-bubble-extra">{messageNode}</div>
                )}
              </div>
              <div className={`cfd-robot-actions ${showButtons ? 'cfd-robot-actions--visible' : ''}`}>
                {showCancel && (
                  <button className="cfd-robot-btn cfd-robot-btn--cancel" onClick={handleCancel}>
                    {cancelText || t('common.cancel')}
                  </button>
                )}
                <button
                  className="cfd-robot-btn cfd-robot-btn--confirm"
                  style={{ '--btn-color': variantColors[variant] } as React.CSSProperties}
                  onClick={handleConfirm}
                  disabled={!showButtons}
                >
                  {confirmText || t('common.confirm')}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>,
      document.body
    );
  }

  /* ── Classic mode: standard modal ── */
  return createPortal(
    <div
      className={`cfd-overlay ${exiting ? 'cfd-overlay--exit' : ''}`}
      onClick={handleCancel}
      role="dialog"
      aria-modal="true"
    >
      <div className={`cfd-modal cfd-modal--${variant}`} onClick={(e) => e.stopPropagation()}>
        {title && <div className="cfd-modal-title">{title}</div>}
        <div className="cfd-modal-body">
          {message}
          {messageNode && <div className="cfd-modal-extra">{messageNode}</div>}
        </div>
        <div className="cfd-modal-actions">
          {showCancel && (
            <button className="cfd-modal-btn cfd-modal-btn--cancel" onClick={handleCancel}>
              {cancelText || t('common.cancel')}
            </button>
          )}
          <button
            className={`cfd-modal-btn cfd-modal-btn--confirm cfd-modal-btn--${variant}`}
            onClick={handleConfirm}
          >
            {confirmText || t('common.confirm')}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
};

export default ConfirmDialog;
