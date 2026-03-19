/**
 * ChatProactiveAction — Task 12
 *
 * Renders proactive messages with inline Confirm/Dismiss/View Details buttons.
 * Confirm → direct API call (no navigation away).
 * Uses unified ActionDescriptor for generic dispatch when available.
 * Falls back to per-type handlers for legacy messages without action descriptor.
 *
 * Requirements: FR-10, FR-11, FR-12, FR-22
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, X, Loader2, ChevronDown, ChevronUp } from 'lucide-react';
import { documentService } from '../../services/documentService';
import { useAIAdvisorStore, type ProactiveMessage } from '../../stores/aiAdvisorStore';
import { useRefreshStore } from '../../stores/refreshStore';

interface ChatProactiveActionProps {
  message: ProactiveMessage;
}

/** Types that support inline action */
const ACTIONABLE_TYPES = new Set([
  'recurring_confirm',
  'asset_confirm',
  'tax_form_review',
  'employer_month_confirm',
]);

export function isActionableProactive(msg: ProactiveMessage): boolean {
  return ACTIONABLE_TYPES.has(msg.type) && msg.actionStatus === 'pending';
}

export default function ChatProactiveAction({ message }: ChatProactiveActionProps) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language?.slice(0, 2) || 'en';
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [result, setResult] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const updateMessageAction = useAIAdvisorStore((s) => s.updateMessageAction);
  const refreshAll = useRefreshStore((s) => s.refreshAll);

  const handleConfirm = async () => {
    setLoading(true);
    setResult(null);

    try {
      // Use unified ActionDescriptor if available
      if (message.action) {
        await documentService.executeAction(
          message.action.endpoint,
          message.action.method,
          message.action.payload
        );
      } else {
        // Fallback: per-type dispatch for legacy messages
        await handleLegacyConfirm();
      }

      updateMessageAction(message.id, 'confirmed');
      setResult({ type: 'success', text: t('ai.proactive.confirmed', 'Done!') });
      refreshAll();
    } catch (err: any) {
      setResult({
        type: 'error',
        text: err?.response?.data?.detail || t('ai.proactive.actionFailed', 'Action failed'),
      });
    } finally {
      setLoading(false);
    }
  };

  /** Legacy per-type confirm for messages without ActionDescriptor */
  const handleLegacyConfirm = async () => {
    const docId = message.documentId;
    if (!docId) throw new Error('No document ID');

    switch (message.type) {
      case 'recurring_confirm': {
        const suggType = message.actionData?.suggestion_type;
        if (suggType === 'create_recurring_expense') {
          await documentService.confirmRecurringExpense(docId);
        } else {
          await documentService.confirmRecurring(docId);
        }
        break;
      }
      case 'asset_confirm':
        await documentService.confirmAsset(docId, {});
        break;
      case 'tax_form_review':
        await documentService.confirmTaxData(docId);
        break;
      default:
        throw new Error(`Unsupported legacy action type: ${message.type}`);
    }
  };

  const handleDismiss = () => {
    if (message.documentId) {
      documentService.dismissSuggestion(message.documentId).catch(() => {});
    }
    updateMessageAction(message.id, 'dismissed');
  };

  // Get button labels from ActionDescriptor or fallback
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

  const isConfirmed = message.actionStatus === 'confirmed';
  const isDismissed = message.actionStatus === 'dismissed';
  const isPending = message.actionStatus === 'pending';

  return (
    <>
      {/* Action buttons — only for pending actionable messages */}
      {isPending && !result && (
        <div className="chat-recurring-card" style={{ marginTop: 8 }}>
          {/* Expandable details */}
          {message.actionData && (
            <button
              type="button"
              onClick={() => setExpanded(!expanded)}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                fontSize: '0.78rem',
                color: 'var(--color-primary)',
                padding: '2px 0',
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                marginBottom: expanded ? 6 : 0,
              }}
            >
              {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              {t('ai.proactive.viewDetails', 'View details')}
            </button>
          )}

          {expanded && message.actionData && (
            <div className="chat-recurring-details" style={{ marginBottom: 8 }}>
              {Object.entries(message.actionData)
                .filter(([key]) => !key.startsWith('suggestion_') && key !== 'decision' && key !== 'quality_gate_decision')
                .slice(0, 6)
                .map(([key, val]) => (
                  <div key={key} className="chat-recurring-row">
                    <span>{key.replace(/_/g, ' ')}</span>
                    <span className="chat-recurring-value">
                      {typeof val === 'number'
                        ? `€ ${val.toLocaleString('de-AT', { minimumFractionDigits: 2 })}`
                        : String(val)}
                    </span>
                  </div>
                ))}
            </div>
          )}

          <div className="chat-recurring-actions">
            <button
              className="chat-recurring-btn confirm"
              onClick={handleConfirm}
              disabled={loading}
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
        </div>
      )}

      {/* Result feedback */}
      {result && (
        <div
          className={`chat-recurring-result ${result.type === 'success' ? 'confirmed' : ''}`}
          style={{ marginTop: 8, fontSize: '0.8rem' }}
        >
          {result.type === 'success' ? <Check size={14} /> : '❌'} {result.text}
        </div>
      )}

      {/* Already confirmed */}
      {isConfirmed && !result && (
        <div className="chat-recurring-result confirmed" style={{ marginTop: 6, fontSize: '0.8rem' }}>
          <Check size={14} /> {t('ai.proactive.alreadyConfirmed', 'Confirmed')}
        </div>
      )}

      {/* Already dismissed */}
      {isDismissed && !result && (
        <div style={{ marginTop: 6, fontSize: '0.8rem', opacity: 0.5 }}>
          {t('ai.proactive.alreadyDismissed', 'Dismissed')}
        </div>
      )}
    </>
  );
}
