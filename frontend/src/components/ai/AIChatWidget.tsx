import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { MessageCircle, X, Minimize2 } from 'lucide-react';
import ChatInterface from './ChatInterface';
import './AIChatWidget.css';

interface AIChatWidgetProps {
  contextData?: {
    page?: string;
    documentId?: string;
    transactionId?: string;
    [key: string]: any;
  };
}

const AIChatWidget: React.FC<AIChatWidgetProps> = ({ contextData }) => {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth <= 768);
    };

    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  const handleToggle = () => {
    if (isOpen) {
      setIsOpen(false);
      setIsMinimized(false);
    } else {
      setIsOpen(true);
      setIsMinimized(false);
    }
  };

  const handleMinimize = () => {
    setIsMinimized(true);
  };

  const handleMaximize = () => {
    setIsMinimized(false);
  };

  return (
    <>
      {/* Floating chat button */}
      {!isOpen && (
        <button
          className="ai-chat-button"
          onClick={handleToggle}
          aria-label={t('ai.openChat')}
          title={t('ai.askTaxjaAI')}
        >
          <MessageCircle size={24} />
          <span className="ai-chat-button-text">{t('ai.askAI')}</span>
        </button>
      )}

      {/* Chat window */}
      {isOpen && (
        <div
          className={`ai-chat-window ${isMobile ? 'mobile' : ''} ${
            isMinimized ? 'minimized' : ''
          }`}
        >
          <div className="ai-chat-header">
            <div className="ai-chat-title">
              <MessageCircle size={20} />
              <span>{t('ai.taxjaAssistant')}</span>
            </div>
            <div className="ai-chat-controls">
              {!isMobile && !isMinimized && (
                <button
                  onClick={handleMinimize}
                  aria-label={t('ai.minimize')}
                  className="ai-chat-control-btn"
                >
                  <Minimize2 size={18} />
                </button>
              )}
              <button
                onClick={handleToggle}
                aria-label={t('ai.close')}
                className="ai-chat-control-btn"
              >
                <X size={18} />
              </button>
            </div>
          </div>

          {!isMinimized && (
            <div className="ai-chat-content">
              <ChatInterface contextData={contextData} />
            </div>
          )}

          {isMinimized && (
            <div className="ai-chat-minimized-content" onClick={handleMaximize}>
              <span>{t('ai.clickToExpand')}</span>
            </div>
          )}
        </div>
      )}
    </>
  );
};

export default AIChatWidget;
