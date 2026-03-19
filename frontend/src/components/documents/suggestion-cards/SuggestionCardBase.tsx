import React from 'react';
import { useTranslation } from 'react-i18next';
import { MessageCircle } from 'lucide-react';
import { useAIAdvisorStore } from '../../../stores/aiAdvisorStore';
import './SuggestionCardBase.css';

export interface SuggestionCardProps {
  suggestion: { type: string; data: Record<string, any>; status?: string };
  confirmResult: { type: 'success' | 'error'; message: string } | null;
  confirmingAction: string | null;
  onConfirm: (payload?: any) => void;
  onDismiss: () => void;
  confirmActionKey?: string; // which confirmingAction value to check for spinner
  confirmLabel?: string;
  /** Document ID — used for "Ask AI about this" link */
  documentId?: number;
}

/** Format EUR amount */
export const fmtEur = (v: number | null | undefined) =>
  v != null ? `€ ${v.toLocaleString('de-AT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—';

/** Format date string */
export const fmtDate = (d: string | null | undefined) => {
  if (!d) return '—';
  try { return new Date(d).toLocaleDateString('de-AT'); } catch { return d; }
};

/** Shared card shell: icon + title + details + actions */
export const SuggestionCardShell: React.FC<{
  icon: string;
  title: string;
  confirmResult: SuggestionCardProps['confirmResult'];
  confirmingAction: string | null;
  confirmActionKey: string;
  onConfirm: (payload?: any) => void;
  onDismiss: () => void;
  confirmLabel?: string;
  documentId?: number;
  suggestionType?: string;
  suggestionData?: Record<string, any>;
  children: React.ReactNode;
}> = ({ icon, title, confirmResult, confirmingAction, confirmActionKey, onConfirm, onDismiss, confirmLabel, documentId, suggestionType, suggestionData, children }) => {
  const { t } = useTranslation();
  const pushSuggestionMessage = useAIAdvisorStore((s) => s.pushSuggestionMessage);

  /** Task 25: Open AI chat with suggestion context pre-loaded */
  const handleAskAI = () => {
    if (!documentId || !suggestionType) return;
    // Push suggestion into chat panel so the user can ask questions about it
    pushSuggestionMessage({
      idempotencyKey: `${documentId}:${suggestionType}:completed`,
      type: 'suggestion',
      suggestionType,
      documentId,
      extractedData: suggestionData || {},
      status: 'pending',
    });
    // Scroll chat into view by triggering a small state change
    // The FloatingAIChat panel will auto-show via unread badge
  };

  return (
    <div className="import-suggestion-card">
      <div className="suggestion-header">
        <span className="suggestion-icon">{icon}</span>
        <h3>{title}</h3>
      </div>
      {children}
      {confirmResult && (
        <div className={`suggestion-result ${confirmResult.type}`}>{confirmResult.message}</div>
      )}
      <div className="suggestion-actions">
        <button className="btn btn-primary" onClick={onConfirm} disabled={confirmingAction !== null}>
          {confirmingAction === confirmActionKey ? '⏳' : '✅'} {confirmLabel || t('documents.suggestion.confirm')}
        </button>
        <button className="btn btn-secondary" onClick={onDismiss} disabled={confirmingAction !== null}>
          {t('documents.suggestion.dismiss')}
        </button>
      </div>
      {/* Task 25: "Ask AI about this" link — bridges Documents page to Chat */}
      {documentId && suggestionType && (
        <button
          type="button"
          className="suggestion-ask-ai-link"
          onClick={handleAskAI}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            marginTop: 8,
            padding: 0,
            background: 'none',
            border: 'none',
            color: 'var(--color-primary, #6366f1)',
            fontSize: '0.78rem',
            cursor: 'pointer',
            opacity: 0.8,
          }}
        >
          <MessageCircle size={13} />
          {t('ai.askAboutDocument', 'Ask AI about this')}
        </button>
      )}
    </div>
  );
};

/** Row helper */
export const Row: React.FC<{ label: string; value: React.ReactNode; className?: string }> = ({ label, value, className }) => (
  <div className={`suggestion-row ${className || ''}`}>
    <span>{label}</span>
    <span>{value}</span>
  </div>
);

export default SuggestionCardShell;
