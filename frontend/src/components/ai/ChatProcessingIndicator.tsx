/**
 * ChatProcessingIndicator — Task 11 + Task 23
 *
 * Shows document processing progress as a chat message.
 * When multiple docs are processing simultaneously, shows a collective batch indicator.
 *
 * Requirements: FR-13, FR-14
 */
import { useTranslation } from 'react-i18next';
import AIAvatar from './AIAvatar';
import { useAIAdvisorStore } from '../../stores/aiAdvisorStore';
import type { ProcessingUpdateMessage } from '../../stores/aiAdvisorStore';

interface ChatProcessingIndicatorProps {
  message: ProcessingUpdateMessage;
}

const phaseIcons: Record<string, string> = {
  uploading: '📤',
  ocr: '🔍',
  classifying: '📂',
  extracting: '📋',
  analyzing: '🧠',
  complete: '✅',
};

export default function ChatProcessingIndicator({ message }: ChatProcessingIndicatorProps) {
  const { t } = useTranslation();
  const icon = phaseIcons[message.phase] || '🔍';
  const isActive = message.uiState === 'processing';
  const batchSummary = useAIAdvisorStore((s) => s.getBatchProcessingSummary());

  return (
    <div className="chat-msg assistant">
      <AIAvatar status="thinking" />
      <div className="chat-msg-bubble">
        {/* Task 23: Batch indicator when multiple docs processing */}
        {batchSummary && (
          <div style={{ fontSize: '0.72rem', opacity: 0.6, marginBottom: 4 }}>
            📦 {t('ai.processing.batch', 'Processing {{count}} documents...', { count: batchSummary.count })}
          </div>
        )}
        <div className="chat-processing-indicator" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span className="chat-processing-icon">{icon}</span>
          <span className="chat-processing-text">{message.message}</span>
          {isActive && (
            <span className="chat-processing-dots">
              <span className="chat-typing-dot" />
              <span className="chat-typing-dot" />
              <span className="chat-typing-dot" />
            </span>
          )}
        </div>
        {message.documentType && (
          <div className="chat-processing-meta" style={{ fontSize: '0.75rem', opacity: 0.6, marginTop: 4 }}>
            {message.documentType}
          </div>
        )}
      </div>
    </div>
  );
}
