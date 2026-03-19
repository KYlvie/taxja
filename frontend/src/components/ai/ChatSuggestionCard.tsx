/**
 * ChatSuggestionCard — Task 9
 *
 * Renders suggestion data as a structured card inside the chat panel.
 * RULE: No embedded forms. Complex suggestions show summary + buttons ONLY.
 * Multi-field data collection goes through ChatFollowUpQuestion as a separate message.
 *
 * Uses ActionDescriptor for confirm — dispatches generically, NOT per-type switch.
 *
 * Requirements: FR-1, FR-2, FR-3, FR-4, FR-22
 */
import { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, X, Loader2, Undo2 } from 'lucide-react';
import { documentService } from '../../services/documentService';
import { useAIAdvisorStore } from '../../stores/aiAdvisorStore';
import { useRefreshStore } from '../../stores/refreshStore';
import AIAvatar from './AIAvatar';
import type { SuggestionChatMessage } from '../../stores/aiAdvisorStore';

interface ChatSuggestionCardProps {
  message: SuggestionChatMessage;
}

/** Map suggestion types to display icons */
const typeIcons: Record<string, string> = {
  create_property: '🏠',
  create_asset: '🚗',
  create_recurring_income: '💰',
  create_recurring_expense: '💸',
  create_loan: '🏦',
  import_lohnzettel: '📄',
  import_l1: '📋',
  import_e1a: '📋',
  import_bank_statement: '🏧',
};

/** Extract key display fields from extracted data */
function getDisplayRows(data: Record<string, any>, _suggestionType: string): Array<{ label: string; value: string }> {
  const rows: Array<{ label: string; value: string }> = [];

  if (data.amount || data.purchase_price || data.monthly_rent) {
    const amount = data.amount || data.purchase_price || data.monthly_rent;
    rows.push({ label: 'Amount', value: `€ ${Number(amount).toLocaleString('de-AT', { minimumFractionDigits: 2 })}` });
  }

  if (data.vendor || data.seller || data.landlord || data.employer) {
    rows.push({ label: 'From', value: data.vendor || data.seller || data.landlord || data.employer });
  }

  if (data.date || data.purchase_date || data.contract_date) {
    rows.push({ label: 'Date', value: data.date || data.purchase_date || data.contract_date });
  }

  if (data.address || data.property_address) {
    rows.push({ label: 'Address', value: data.address || data.property_address });
  }

  if (data.asset_name || data.description || data.item) {
    rows.push({ label: 'Item', value: data.asset_name || data.description || data.item });
  }

  return rows.slice(0, 5); // Max 5 rows
}

/** Get human-readable suggestion type name */
function getTypeName(suggestionType: string, t: any): string {
  const typeMap: Record<string, string> = {
    create_property: t('ai.suggestion.property', 'Property'),
    create_asset: t('ai.suggestion.asset', 'Asset'),
    create_recurring_income: t('ai.suggestion.recurringIncome', 'Recurring Income'),
    create_recurring_expense: t('ai.suggestion.recurringExpense', 'Recurring Expense'),
    create_loan: t('ai.suggestion.loan', 'Loan'),
  };
  if (suggestionType.startsWith('import_')) {
    return t('ai.suggestion.taxData', 'Tax Data');
  }
  return typeMap[suggestionType] || t('ai.suggestion.document', 'Document');
}

// Task 24: Hoisted outside component — only entity creation, not tax data import
const UNDO_TYPES = new Set(['create_property', 'create_asset', 'create_recurring_income', 'create_recurring_expense', 'create_loan']);

export default function ChatSuggestionCard({ message }: ChatSuggestionCardProps) {
  const { t, i18n } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [showUndo, setShowUndo] = useState(false);
  const [undoCountdown, setUndoCountdown] = useState(10);
  const undoTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const updateSuggestionStatus = useAIAdvisorStore((s) => s.updateSuggestionStatus);
  const refreshAll = useRefreshStore((s) => s.refreshAll);

  const supportsUndo = UNDO_TYPES.has(message.suggestionType);

  // Cleanup undo timer on unmount
  useEffect(() => {
    return () => {
      if (undoTimerRef.current) clearInterval(undoTimerRef.current);
      undoTimerRef.current = null;
    };
  }, []);

  const icon = typeIcons[message.suggestionType] || '📋';
  const typeName = getTypeName(message.suggestionType, t);
  const rows = getDisplayRows(message.extractedData, message.suggestionType);
  const lang = i18n.language?.slice(0, 2) || 'en';

  // Get button labels from ActionDescriptor or fallback to generic
  const confirmLabel = message.action?.confirmLabel
    ? (typeof message.action.confirmLabel === 'object'
      ? (message.action.confirmLabel as any)[lang] || (message.action.confirmLabel as any).en
      : message.action.confirmLabel)
    : t('common.confirm', 'Confirm');
  const dismissLabel = message.action?.dismissLabel
    ? (typeof message.action.dismissLabel === 'object'
      ? (message.action.dismissLabel as any)[lang] || (message.action.dismissLabel as any).en
      : message.action.dismissLabel)
    : t('common.dismiss', 'Dismiss');

  const handleConfirm = async () => {
    if (!message.action) {
      setResult({ type: 'error', text: t('ai.suggestion.noAction', 'Action configuration missing. Please refresh.') });
      return;
    }
    setLoading(true);
    setResult(null);
    try {
      await documentService.executeAction(message.action.endpoint, message.action.method, message.action.payload);
      updateSuggestionStatus(message.documentId, 'confirmed');
      setResult({ type: 'success', text: t('ai.suggestion.confirmed', 'Created successfully!') });
      refreshAll();

      // Task 24: Start undo countdown for entity creation types
      if (supportsUndo) {
        setShowUndo(true);
        setUndoCountdown(10);
        undoTimerRef.current = setInterval(() => {
          setUndoCountdown((prev) => {
            if (prev <= 1) {
              if (undoTimerRef.current) clearInterval(undoTimerRef.current);
              setShowUndo(false);
              return 0;
            }
            return prev - 1;
          });
        }, 1000);
      }
    } catch (err: any) {
      setResult({ type: 'error', text: err?.response?.data?.detail || t('ai.suggestion.error', 'Action failed') });
    } finally {
      setLoading(false);
    }
  };

  /** Task 24: Undo — dismiss the suggestion to reverse the creation */
  const handleUndo = async () => {
    if (undoTimerRef.current) clearInterval(undoTimerRef.current);
    setShowUndo(false);
    try {
      await documentService.dismissSuggestion(message.documentId);
      updateSuggestionStatus(message.documentId, 'dismissed');
      setResult({ type: 'success', text: t('ai.suggestion.undone', 'Undone. The created item has been removed.') });
      refreshAll();
    } catch {
      setResult({ type: 'error', text: t('ai.suggestion.undoFailed', 'Undo failed. Please remove manually.') });
    }
  };

  const handleDismiss = async () => {
    try {
      await documentService.dismissSuggestion(message.documentId);
      updateSuggestionStatus(message.documentId, 'dismissed');
    } catch {
      // Silent dismiss failure
    }
  };

  const isActionable = message.status === 'pending' || message.status === 'needs_input';
  const isConfirmed = message.status === 'confirmed';
  const isDismissed = message.status === 'dismissed';

  return (
    <div className="chat-msg assistant">
      <AIAvatar />
      <div className="chat-msg-bubble">
        <p style={{ margin: '0 0 6px', fontSize: '0.84rem' }}>
          {icon} {t('ai.suggestion.found', 'I found something in your document:')}
        </p>

        <div className="chat-recurring-card">
          <div style={{ fontWeight: 600, fontSize: '0.82rem', marginBottom: 6 }}>
            {typeName}
          </div>

          <div className="chat-recurring-details">
            {rows.map((row, i) => (
              <div key={i} className="chat-recurring-row">
                <span>{row.label}</span>
                <span className="chat-recurring-value">{row.value}</span>
              </div>
            ))}
          </div>

          {/* Action buttons — only when actionable */}
          {isActionable && !result && (
            <div className="chat-recurring-actions" style={{ marginTop: 8 }}>
              <button
                className="chat-recurring-btn confirm"
                onClick={handleConfirm}
                disabled={loading || message.status === 'needs_input'}
              >
                {loading ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                {' '}{confirmLabel}
              </button>
              <button
                className="chat-recurring-btn dismiss"
                onClick={handleDismiss}
                disabled={loading}
              >
                <X size={14} /> {dismissLabel}
              </button>
            </div>
          )}

          {/* Needs input hint */}
          {message.status === 'needs_input' && !result && (
            <div style={{ fontSize: '0.75rem', opacity: 0.7, marginTop: 6, fontStyle: 'italic' }}>
              {t('ai.suggestion.needsInput', 'Please answer the follow-up questions below first.')}
            </div>
          )}

          {/* Result message */}
          {result && (
            <div className={`chat-recurring-result ${result.type === 'success' ? 'confirmed' : ''}`}
              style={{ marginTop: 8, fontSize: '0.8rem' }}>
              {result.type === 'success' ? <Check size={14} /> : '❌'} {result.text}
              {/* Task 24: Undo button — 10 second countdown after confirm */}
              {showUndo && (
                <button
                  type="button"
                  onClick={handleUndo}
                  style={{
                    marginLeft: 8,
                    padding: '2px 8px',
                    fontSize: '0.75rem',
                    background: 'none',
                    border: '1px solid var(--color-border, #e2e8f0)',
                    borderRadius: 6,
                    cursor: 'pointer',
                    color: 'var(--color-text-secondary, #64748b)',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 3,
                  }}
                >
                  <Undo2 size={11} />
                  {t('ai.suggestion.undo', 'Undo')} ({undoCountdown}s)
                </button>
              )}
            </div>
          )}

          {/* Already confirmed/dismissed state */}
          {isConfirmed && !result && (
            <div className="chat-recurring-result confirmed" style={{ marginTop: 8, fontSize: '0.8rem' }}>
              <Check size={14} /> {t('ai.suggestion.alreadyConfirmed', 'Confirmed')}
            </div>
          )}
          {isDismissed && !result && (
            <div style={{ marginTop: 8, fontSize: '0.8rem', opacity: 0.5 }}>
              {t('ai.suggestion.dismissed', 'Dismissed')}
            </div>
          )}
        </div>

        <span className="chat-msg-time">
          {message.timestamp instanceof Date
            ? message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            : new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>
    </div>
  );
}
