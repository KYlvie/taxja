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
import { useNavigate } from 'react-router-dom';
import {
  Banknote,
  Building2,
  Check,
  ClipboardList,
  Eye,
  FileText,
  House,
  Landmark,
  Loader2,
  ReceiptText,
  Undo2,
  Wallet,
  X,
  XCircle,
  type LucideIcon,
} from 'lucide-react';
import { documentService } from '../../services/documentService';
import { useAIAdvisorStore } from '../../stores/aiAdvisorStore';
import { useRefreshStore } from '../../stores/refreshStore';
import { getLocaleForLanguage } from '../../utils/locale';
import i18nInstance from '../../i18n';
import AIAvatar from './AIAvatar';
import FuturisticIcon, { type FuturisticIconTone } from '../common/FuturisticIcon';
import type { SuggestionChatMessage } from '../../stores/aiAdvisorStore';

interface ChatSuggestionCardProps {
  message: SuggestionChatMessage;
}

/** Map suggestion types to display icons */
const typeIcons: Record<string, { icon: LucideIcon; tone: FuturisticIconTone }> = {
  create_property: { icon: House, tone: 'cyan' },
  create_asset: { icon: Building2, tone: 'emerald' },
  create_recurring_income: { icon: Wallet, tone: 'emerald' },
  create_recurring_expense: { icon: Banknote, tone: 'rose' },
  create_loan: { icon: Landmark, tone: 'amber' },
  create_loan_repayment: { icon: Landmark, tone: 'amber' },
  import_lohnzettel: { icon: FileText, tone: 'cyan' },
  import_l1: { icon: ClipboardList, tone: 'amber' },
  import_e1a: { icon: ClipboardList, tone: 'amber' },
  import_bank_statement: { icon: ReceiptText, tone: 'violet' },
  link_to_existing: { icon: Banknote, tone: 'amber' },
};

/** Extract key display fields from extracted data */
function getDisplayRows(data: Record<string, any>, _suggestionType: string): Array<{ label: string; value: string }> {
  const rows: Array<{ label: string; value: string }> = [];

  if (data.amount || data.purchase_price || data.monthly_rent) {
    const amount = data.amount || data.purchase_price || data.monthly_rent;
    rows.push({ label: 'Amount', value: `€ ${Number(amount).toLocaleString(getLocaleForLanguage(i18nInstance.language), { minimumFractionDigits: 2 })}` });
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

  // For link_to_existing: show match reason
  if (data.matched_type) {
    rows.push({ label: 'Match Type', value: data.matched_type });
  }
  if (data.reason) {
    rows.push({ label: 'Reason', value: data.reason });
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
    create_loan_repayment: t('ai.suggestion.loanRepayment', 'Loan Repayment'),
    link_to_existing: t('ai.suggestion.linkExisting', 'Duplicate Detected'),
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

  const navigate = useNavigate();
  const iconMeta = typeIcons[message.suggestionType] || { icon: ClipboardList, tone: 'slate' as FuturisticIconTone };
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
    setLoading(true);
    setResult(null);
    try {
      // Special handling for link_to_existing (AI dedup match)
      if (message.suggestionType === 'link_to_existing') {
        await documentService.executeAction(
          `/documents/${message.documentId}/link-existing`,
          'POST',
          { action: 'confirm' }
        );
        updateSuggestionStatus(message.documentId, 'confirmed');
        setResult({ type: 'success', text: t('ai.suggestion.linked', 'Document linked to existing record. No duplicate created.') });
        refreshAll();
        setLoading(false);
        return;
      }

      if (!message.action) {
        setResult({ type: 'error', text: t('ai.suggestion.noAction', 'Action configuration missing. Please refresh.') });
        setLoading(false);
        return;
      }
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
      if (message.suggestionType === 'link_to_existing') {
        // Reject AI dedup match — allow normal processing
        await documentService.executeAction(
          `/documents/${message.documentId}/link-existing`,
          'POST',
          { action: 'reject' }
        );
      } else {
        await documentService.dismissSuggestion(message.documentId);
      }
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
        <p className="chat-suggestion-intro">
          <span className="chat-suggestion-intro-icon">
            <FuturisticIcon icon={iconMeta.icon} tone={iconMeta.tone} size="xs" />
          </span>
          <span>
            {message.extractedData?.file_name
              ? t('ai.suggestion.foundInFile', 'I found something in "{{fileName}}":', { fileName: message.extractedData.file_name })
              : t('ai.suggestion.found', 'I found something in your document:')}
          </span>
        </p>

        <div className="chat-recurring-card">
          <div className="chat-suggestion-title">
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

          {/* View document link */}
          {message.documentId && (
            <button
              className="chat-suggestion-view-doc"
              onClick={() => navigate(`/documents/${message.documentId}`)}
              type="button"
            >
              <Eye size={13} /> {t('ai.suggestion.viewDocument', 'View document')}
            </button>
          )}

          {/* Action buttons — only when actionable */}
          {isActionable && !result && (
            <div className="chat-recurring-actions">
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
            <div className="chat-suggestion-note">
              {t('ai.suggestion.needsInput', 'Please answer the follow-up questions below first.')}
            </div>
          )}

          {/* Result message */}
          {result && (
            <div className={`chat-recurring-result ${result.type === 'success' ? 'confirmed' : ''}`}>
              {result.type === 'success' ? <Check size={14} /> : <XCircle size={14} />} {result.text}
              {/* Task 24: Undo button — 10 second countdown after confirm */}
              {showUndo && (
                <button
                  type="button"
                  onClick={handleUndo}
                  className="chat-suggestion-undo"
                >
                  <Undo2 size={11} />
                  {t('ai.suggestion.undo', 'Undo')} ({undoCountdown}s)
                </button>
              )}
            </div>
          )}

          {/* Already confirmed/dismissed state */}
          {isConfirmed && !result && (
            <div className="chat-recurring-result confirmed">
              <Check size={14} /> {t('ai.suggestion.alreadyConfirmed', 'Confirmed')}
            </div>
          )}
          {isDismissed && !result && (
            <div className="chat-dismissed-note">
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
