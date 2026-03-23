import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
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

      // Show bubble after robot entrance animation
      const bubbleTimer = setTimeout(() => {
        setShowBubble(true);
        // Type out the message
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
      if (visible) {
        setExiting(true);
        const exitTimer = setTimeout(() => {
          setVisible(false);
          setExiting(false);
        }, 400);
        return () => clearTimeout(exitTimer);
      }
    }
  }, [isOpen, message]);

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
    }, 300);
  };

  const handleCancel = () => {
    setExiting(true);
    setTimeout(() => {
      onCancel?.();
    }, 300);
  };

  return createPortal(
    <div
      className={`cfd-robot-overlay ${exiting ? 'cfd-robot-overlay--exit' : ''}`}
      onClick={handleCancel}
      role="dialog"
      aria-modal="true"
    >
      <div className="cfd-robot-scene" onClick={(e) => e.stopPropagation()}>
        {/* 3D Robot */}
        <div className="cfd-robot-container">
          <RobotMascot size={ROBOT_SIZE} />
        </div>

        {/* Floating text bubble */}
        {showBubble && (
          <div className={`cfd-robot-bubble cfd-robot-bubble--${variant}`}>
            {title && (
              <div className="cfd-robot-bubble-title">
                {title}
              </div>
            )}
            <div className="cfd-robot-bubble-text">
              {typedText}
              {typedText.length >= message.length && messageNode && (
                <div className="cfd-robot-bubble-extra">{messageNode}</div>
              )}
            </div>

            {/* Action buttons inside bubble */}
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
};

export default ConfirmDialog;
