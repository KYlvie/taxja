import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Check, X, Loader2 } from 'lucide-react';
import { documentService } from '../../services/documentService';
import { dashboardService } from '../../services/dashboardService';
import { useAIAdvisorStore, type ProactiveMessage } from '../../stores/aiAdvisorStore';
import { useRefreshStore } from '../../stores/refreshStore';
import { getLocaleForLanguage } from '../../utils/locale';

interface ChatProactiveActionProps {
  message: ProactiveMessage;
}

interface ReminderDetailItem {
  kind: 'asset' | 'document';
  href: string;
  label: string;
  asset_id?: string;
  document_id?: number;
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

function getDetailItems(message: ProactiveMessage): ReminderDetailItem[] {
  const rawItems = message.actionData?.detail_items;
  if (!Array.isArray(rawItems)) {
    return [];
  }

  return rawItems
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object')
    .map((item): ReminderDetailItem => ({
      kind: item.kind === 'document' ? 'document' : 'asset',
      href: typeof item.href === 'string' ? item.href : '',
      label: typeof item.label === 'string' ? item.label : '',
      asset_id: typeof item.asset_id === 'string' ? item.asset_id : undefined,
      document_id: typeof item.document_id === 'number' ? item.document_id : undefined,
    }))
    .filter((item) => item.href && item.label);
}

export default function ChatProactiveAction({ message }: ChatProactiveActionProps) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const lang = i18n.language?.slice(0, 2) || 'en';
  const [loadingAction, setLoadingAction] = useState<'primary' | 'secondary' | 'dismiss' | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [result, setResult] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const updateMessageAction = useAIAdvisorStore((s) => s.updateMessageAction);
  const dismissMessage = useAIAdvisorStore((s) => s.dismissMessage);
  const refreshAll = useRefreshStore((s) => s.refreshAll);
  const detailItems = getDetailItems(message);
  const hasMultipleDetailItems = detailItems.length > 1;
  const singleDetailItem = detailItems.length === 1 ? detailItems[0] : null;

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
    if (message.bucket !== 'terminal_action' && hasMultipleDetailItems) {
      setExpanded((value) => !value);
      return;
    }

    if (message.bucket !== 'terminal_action' && !message.link && singleDetailItem?.href) {
      navigate(singleDetailItem.href);
      return;
    }

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

  const handlePermanentDismiss = async () => {
    setLoadingAction('dismiss');
    setResult(null);
    try {
      if (message.serverId) {
        await dashboardService.acknowledgeProactiveReminder(message.serverId);
        dismissMessage(message.id);
        setResult({
          type: 'success',
          text: t('ai.proactive.dismissed', 'No longer reminding you about this item.'),
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
    message.bucket !== 'terminal_action' && hasMultipleDetailItems
      ? expanded
        ? t('ai.proactive.hideDetails', 'Hide details')
        : t('ai.proactive.expandDetails', 'Expand details')
      : message.bucket === 'terminal_action' && message.action?.confirmLabel
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
  // Only show expand button if there are user-visible fields (not just internal metadata)
  const internalKeys = new Set([
    'suggestion_type', 'suggestion_id', 'suggestion_status',
    'decision', 'quality_gate_decision',
    'category', 'action_label_key', 'action label key',
    'bucket', 'priority', 'source', 'trigger',
  ]);
  const visibleDataEntries = Object.entries(message.actionData || {}).filter(([key, value]) => {
    if (value === null || value === undefined || value === '') return false;
    if (internalKeys.has(key)) return false;
    if (key.startsWith('suggestion_') || key.startsWith('_')) return false;
    if (typeof value === 'string' && value.includes('.') && !value.includes(' ') && value.length > 15) return false;
    return true;
  });
  const canExpand = hasMultipleDetailItems || visibleDataEntries.length > 0;
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
  // Hide link actions when primary button already navigates to the same destination
  const hasNavigatingPrimary = message.bucket !== 'terminal_action' && (!!message.link || !!singleDetailItem || hasMultipleDetailItems);
  const visibleLinkActions = hasNavigatingPrimary ? [] : linkActions;

  return (
    <>
      {isPending && !result && (
        <div className="chat-recurring-card">
          {expanded && canExpand && (
            <div className="chat-recurring-details">
              {detailItems.length > 0 && (
                <div className="chat-proactive-detail-list">
                  {detailItems.map((item) => (
                    <div key={`${item.kind}:${item.href}`} className="chat-proactive-detail-item">
                      <div className="chat-proactive-detail-copy">
                        <span className="chat-proactive-detail-label">{item.label}</span>
                      </div>
                      <button
                        type="button"
                        className="chat-recurring-btn view-doc"
                        onClick={() => navigate(item.href)}
                      >
                        <ArrowRight size={14} />
                        <span>{t('common.viewDetails', 'View details')}</span>
                      </button>
                    </div>
                  ))}
                </div>
              )}
              {Object.entries(message.actionData || {})
                .filter(([key, value]) => {
                  if (value === null || value === undefined || value === '') {
                    return false;
                  }
                  // Hide internal metadata fields
                  const internalKeys = new Set([
                    'suggestion_type', 'suggestion_id', 'suggestion_status',
                    'decision', 'quality_gate_decision',
                    'category', 'action_label_key', 'action label key',
                    'bucket', 'priority', 'source', 'trigger',
                    'file_name',
                    'detail_items',
                  ]);
                  if (internalKeys.has(key)) return false;
                  if (key.startsWith('suggestion_') || key.startsWith('_')) return false;
                  // Hide complex array/object values (e.g. transactions, line_items)
                  if (Array.isArray(value)) return false;
                  if (typeof value === 'object' && value !== null) return false;
                  // Hide values that look like i18n keys
                  if (typeof value === 'string' && value.includes('.') && !value.includes(' ') && value.length > 15) return false;
                  return true;
                })
                .slice(0, 6)
                .map(([key, value]) => {
                  // Translate known field names
                  const labelMap: Record<string, string> = {
                    monthly_rent: t('documents.review.fields.monthlyRent', 'Monthly rent'),
                    amount: t('documents.review.fields.amount', 'Amount'),
                    property_address: t('documents.review.fields.propertyAddress', 'Address'),
                    description: t('common.description', 'Description'),
                    merchant: t('documents.review.fields.merchant', 'Merchant'),
                    date: t('documents.review.fields.date', 'Date'),
                    loan_amount: t('documents.review.fields.loanAmount', 'Loan amount'),
                    interest_rate: t('documents.review.fields.interestRate', 'Interest rate'),
                    lender_name: t('documents.review.fields.lenderName', 'Lender'),
                    potential_savings: t('ai.proactive.potentialSavings', 'Potential savings'),
                    'potential savings': t('ai.proactive.potentialSavings', 'Potential savings'),
                    estimated_refund: t('ai.proactive.estimatedRefund', 'Estimated refund'),
                    tax_saving: t('ai.proactive.taxSaving', 'Tax saving'),
                    iban: 'IBAN',
                    bank_name: t('documents.suggestion.fields.bank_name', 'Bank'),
                    tax_year: t('documents.suggestion.taxYear', 'Tax year'),
                    taxpayer_name: t('ai.suggestion.taxpayerName', 'Taxpayer'),
                  };
                  const label = labelMap[key] || key.replace(/_/g, ' ');
                  // Don't format year-like numbers as currency
                  const yearKeys = new Set(['tax_year', 'year', 'fiscal_year']);
                  const displayValue = typeof value === 'number'
                    ? (yearKeys.has(key) ? String(value) : `€ ${value.toLocaleString(getLocaleForLanguage(i18n.language), {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                          })}`)
                    : String(value);
                  return (
                  <div key={key} className="chat-recurring-row">
                    <span>{label}</span>
                    <span className="chat-recurring-value">
                      {displayValue}
                    </span>
                  </div>
                  );
                })}
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
            {message.bucket && message.bucket !== 'terminal_action' && message.serverId
              && !(message.kind === 'deadline_reminder'
                || (message.severity === 'high' && message.actionData?.category === 'threshold_warning')) && (
              <button
                className="chat-recurring-btn dismiss"
                onClick={handlePermanentDismiss}
                disabled={loadingAction !== null}
                style={{ opacity: 0.7, fontSize: '0.85em' }}
              >
                {loadingAction === 'dismiss' ? <Loader2 size={14} className="animate-spin" /> : <X size={14} />}{' '}
                {t('ai.proactive.dontRemindAgain', 'Do not remind again')}
              </button>
            )}
            {visibleLinkActions.map((action) => (
              <button
                key={`${message.id}-${action.href}`}
                type="button"
                className="chat-recurring-btn view-doc"
                onClick={() => navigate(action.href)}
              >
                <ArrowRight size={14} />
                <span>{action.label}</span>
              </button>
            ))}
          </div>
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
