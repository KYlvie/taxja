import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Check, X, Loader2, ChevronDown, ChevronUp } from 'lucide-react';
import { documentService } from '../../services/documentService';
import { dashboardService } from '../../services/dashboardService';
import { useAIAdvisorStore, type ProactiveMessage } from '../../stores/aiAdvisorStore';
import { useRefreshStore } from '../../stores/refreshStore';
import { getLocaleForLanguage } from '../../utils/locale';

interface ChatProactiveActionProps {
  message: ProactiveMessage;
}

const ACTIONABLE_TYPES = new Set([
  'recurring_confirm',
  'asset_confirm',
  'tax_form_review',
  'employer_month_confirm',
]);

export function isActionableProactive(message: ProactiveMessage): boolean {
  if (message.bucket) {
    return true;
  }
  return ACTIONABLE_TYPES.has(message.type) && message.actionStatus === 'pending';
}

function getBucketLabels(message: ProactiveMessage, t: ReturnType<typeof useTranslation>['t']) {
  switch (message.bucket) {
    case 'terminal_action':
      return {
        primary: t('common.confirm', 'Confirm'),
        secondary: t('ai.proactive.dontRemindAgain', 'Do not remind again'),
      };
    case 'snoozeable_condition':
      return {
        primary: t('ai.proactive.viewDetails', 'View details'),
        secondary: t('ai.proactive.remindLater', 'Remind me later'),
      };
    case 'time_based_repeat':
      return {
        primary: t('ai.proactive.takeActionNow', 'Take action now'),
        secondary: t('ai.proactive.remindLater', 'Remind me later'),
      };
    default:
      return {
        primary: t('common.confirm', 'Confirm'),
        secondary: t('common.dismiss', 'Dismiss'),
      };
  }
}

export default function ChatProactiveAction({ message }: ChatProactiveActionProps) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const lang = i18n.language?.slice(0, 2) || 'en';
  const [loadingAction, setLoadingAction] = useState<'primary' | 'secondary' | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [result, setResult] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const updateMessageAction = useAIAdvisorStore((s) => s.updateMessageAction);
  const dismissMessage = useAIAdvisorStore((s) => s.dismissMessage);
  const refreshAll = useRefreshStore((s) => s.refreshAll);

  const handleLegacyConfirm = async () => {
    const docId = message.documentId;
    if (!docId) {
      throw new Error('No document ID');
    }

    switch (message.type) {
      case 'recurring_confirm': {
        const suggestionType = message.actionData?.suggestion_type;
        if (suggestionType === 'create_recurring_expense') {
          await documentService.confirmRecurringExpense(docId);
        } else {
          await documentService.confirmRecurring(docId);
        }
        break;
      }
      case 'asset_confirm': {
        const suggestionType = message.actionData?.suggestion_type;
        if (suggestionType === 'create_property') {
          await documentService.confirmProperty(docId);
        } else {
          await documentService.confirmAsset(docId, {});
        }
        break;
      }
      case 'tax_form_review':
        await documentService.confirmTaxData(docId);
        break;
      default:
        throw new Error(`Unsupported legacy action type: ${message.type}`);
    }
  };

  const handleTerminalConfirm = async () => {
    if (message.action) {
      await documentService.executeAction(
        message.action.endpoint,
        message.action.method,
        message.action.payload
      );
    } else {
      await handleLegacyConfirm();
    }

    updateMessageAction(message.id, 'confirmed');
    setResult({ type: 'success', text: t('ai.proactive.confirmed', 'Done!') });
    refreshAll();
  };

  const handleTerminalDismiss = async () => {
    if (!message.documentId) {
      throw new Error('No document ID');
    }

    await documentService.dismissSuggestion(message.documentId);
    updateMessageAction(message.id, 'dismissed');
    setResult({
      type: 'success',
      text: t('ai.proactive.dismissed', 'No longer reminding you about this item.'),
    });
    refreshAll();
  };

  const handlePrimary = async () => {
    setLoadingAction('primary');
    setResult(null);
    try {
      if (message.bucket === 'terminal_action') {
        await handleTerminalConfirm();
      } else if (message.link) {
        navigate(message.link);
      } else if (message.serverId) {
        await dashboardService.acknowledgeProactiveReminder(message.serverId);
        dismissMessage(message.id);
        setResult({ type: 'success', text: t('ai.proactive.acknowledged', 'Marked as handled.') });
      }
    } catch (err: any) {
      setResult({
        type: 'error',
        text: err?.response?.data?.detail || err?.message || t('ai.proactive.actionFailed', 'Action failed'),
      });
    } finally {
      setLoadingAction(null);
    }
  };

  const handleSecondary = async () => {
    setLoadingAction('secondary');
    setResult(null);
    try {
      if (message.bucket === 'terminal_action') {
        await handleTerminalDismiss();
      } else if (message.serverId) {
        await dashboardService.snoozeProactiveReminder(message.serverId);
        dismissMessage(message.id);
        setResult({
          type: 'success',
          text: t('ai.proactive.snoozed', 'Okay - I will remind you again later.'),
        });
      }
    } catch (err: any) {
      setResult({
        type: 'error',
        text: err?.response?.data?.detail || err?.message || t('ai.proactive.actionFailed', 'Action failed'),
      });
    } finally {
      setLoadingAction(null);
    }
  };

  const labels = getBucketLabels(message, t);
  const confirmLabel =
    message.bucket === 'terminal_action' && message.action?.confirmLabel
      ? typeof message.action.confirmLabel === 'object'
        ? (message.action.confirmLabel as any)[lang] || (message.action.confirmLabel as any).en
        : message.action.confirmLabel
      : labels.primary;
  const dismissLabel =
    message.bucket === 'terminal_action' && message.action?.dismissLabel
      ? typeof message.action.dismissLabel === 'object'
        ? (message.action.dismissLabel as any)[lang] || (message.action.dismissLabel as any).en
        : message.action.dismissLabel
      : labels.secondary;

  const isConfirmed = message.actionStatus === 'confirmed';
  const isDismissed = message.actionStatus === 'dismissed';
  const isPending = message.bucket ? true : message.actionStatus === 'pending';
  const canExpand = Boolean(message.actionData && Object.keys(message.actionData).length > 0);
  const linkActions = [
    message.link
      ? {
          href: message.link,
          label:
            message.linkLabel ||
            (message.link.startsWith('/documents/')
              ? t('ai.proactive.viewDocument', 'View document')
              : t('ai.proactive.viewDetails', 'View details')),
        }
      : null,
    message.secondaryLink
      ? {
          href: message.secondaryLink,
          label: message.secondaryLinkLabel || t('ai.proactive.viewDocument', 'View document'),
        }
      : null,
  ].filter((action): action is { href: string; label: string } => Boolean(action));

  return (
    <>
      {isPending && !result && (
        <div className="chat-recurring-card">
          {canExpand && (
            <button
              type="button"
              onClick={() => setExpanded((value) => !value)}
              className="chat-proactive-toggle"
            >
              {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              {t('ai.proactive.viewDetails', 'View details')}
            </button>
          )}

          {expanded && canExpand && (
            <div className="chat-recurring-details">
              {Object.entries(message.actionData || {})
                .filter(([key, value]) => {
                  if (value === null || value === undefined || value === '') {
                    return false;
                  }
                  return !key.startsWith('suggestion_') && key !== 'decision' && key !== 'quality_gate_decision';
                })
                .slice(0, 6)
                .map(([key, value]) => (
                  <div key={key} className="chat-recurring-row">
                    <span>{key.replace(/_/g, ' ')}</span>
                    <span className="chat-recurring-value">
                      {typeof value === 'number'
                        ? `€ ${value.toLocaleString(getLocaleForLanguage(i18n.language), {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                          })}`
                        : String(value)}
                    </span>
                  </div>
                ))}
            </div>
          )}

          <div className="chat-recurring-actions">
            <button
              className="chat-recurring-btn confirm"
              onClick={handlePrimary}
              disabled={loadingAction !== null}
            >
              {loadingAction === 'primary' ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}{' '}
              {confirmLabel}
            </button>
            <button
              className="chat-recurring-btn dismiss"
              onClick={handleSecondary}
              disabled={loadingAction !== null}
            >
              {loadingAction === 'secondary' ? <Loader2 size={14} className="animate-spin" /> : <X size={14} />}{' '}
              {dismissLabel}
            </button>
          </div>

          {linkActions.length > 0 && (
            <div className="chat-inline-link-actions">
              {linkActions.map((action) => (
                <button
                  key={`${message.id}-${action.href}`}
                  type="button"
                  className="chat-recurring-btn dismiss chat-inline-link-btn"
                  onClick={() => navigate(action.href)}
                >
                  <ArrowRight size={14} />
                  <span>{action.label}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {result && (
        <div className={`chat-recurring-result ${result.type === 'success' ? 'confirmed' : ''}`}>
          {result.type === 'success' ? <Check size={14} /> : '✕'} {result.text}
        </div>
      )}

      {isConfirmed && !result && (
        <div className="chat-recurring-result confirmed">
          <Check size={14} /> {t('ai.proactive.alreadyConfirmed', 'Confirmed')}
        </div>
      )}

      {isDismissed && !result && (
        <div className="chat-dismissed-note">{t('ai.proactive.alreadyDismissed', 'Dismissed')}</div>
      )}
    </>
  );
}
