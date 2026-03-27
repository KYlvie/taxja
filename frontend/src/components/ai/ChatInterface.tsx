import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useConfirm } from '../../hooks/useConfirm';
import { ArrowRight, ArrowUp, Check, ClipboardList, FileText, Loader2, Paperclip, Plus, Trash2, X as XIcon, X as XMark } from 'lucide-react';
import { aiService } from '../../services/aiService';
import { documentService } from '../../services/documentService';
import { employerService } from '../../services/employerService';
import { recurringService } from '../../services/recurringService';
import { propertyService } from '../../services/propertyService';
import { useAIAdvisorStore, type ProactiveMessage, type SuggestionChatMessage, type FollowUpChatMessage, type ProcessingUpdateMessage } from '../../stores/aiAdvisorStore';
import { useRefreshStore } from '../../stores/refreshStore';
import { useSubscriptionStore } from '../../stores/subscriptionStore';
import AIResponse from './AIResponse';
import SuggestedQuestions from './SuggestedQuestions';
import ChatProcessingIndicator from './ChatProcessingIndicator';
import ChatSuggestionCard from './ChatSuggestionCard';
import ChatFollowUpQuestion from './ChatFollowUpQuestion';
import ChatProactiveAction, { isActionableProactive } from './ChatProactiveAction';
import { getLocaleForLanguage } from '../../utils/locale';
import i18nInstance from '../../i18n';
import './ChatInterface.css';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  fileName?: string;
  intent?: string;
  showDisclaimer?: boolean;
  sourceTier?: string;
}

interface ChatInterfaceProps {
  contextData?: {
    page?: string;
    documentId?: string;
    transactionId?: string;
  };
  enableFileUpload?: boolean;
}

const ACCEPTED_FILE_TYPES = '.pdf,.jpg,.jpeg,.png,.gif,.webp,.csv,.xlsx,.xls';
const MAX_FILE_SIZE = 5 * 1024 * 1024;

const formatEmployerMonthLabel = (yearMonth?: string, locale?: string) => {
  if (!yearMonth) {
    return '';
  }

  const [yearText, monthText] = yearMonth.split('-');
  const year = Number(yearText);
  const month = Number(monthText);
  if (!Number.isInteger(year) || !Number.isInteger(month) || month < 1 || month > 12) {
    return yearMonth;
  }

  try {
    return new Intl.DateTimeFormat(locale, { month: 'long', year: 'numeric' }).format(
      new Date(year, month - 1, 1)
    );
  } catch {
    return yearMonth;
  }
};

const parseNumericValue = (value: unknown): number | undefined => {
  if (value === null || value === undefined || value === '') {
    return undefined;
  }

  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : undefined;
};

const formatCurrency = (value: unknown) => {
  const numeric = parseNumericValue(value);
  if (numeric === undefined) {
    return null;
  }
  return numeric.toLocaleString(getLocaleForLanguage(i18nInstance.language), {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
};

const ChatInterface: React.FC<ChatInterfaceProps> = ({ contextData, enableFileUpload }) => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { confirm: showConfirm } = useConfirm();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attachedFile, setAttachedFile] = useState<File | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const creditBalance = useSubscriptionStore((s) => s.creditBalance);
  const creditLoading = useSubscriptionStore((s) => s.creditLoading);
  const fetchCreditBalance = useSubscriptionStore((s) => s.fetchCreditBalance);
  const proactiveMessages = useAIAdvisorStore((s) => s.messages);
  const structuredMessages = useAIAdvisorStore((s) => s.structuredMessages);
  const updateMessageAction = useAIAdvisorStore((s) => s.updateMessageAction);
  const dismissMessage = useAIAdvisorStore((s) => s.dismissMessage);
  const pushMessage = useAIAdvisorStore((s) => s.pushMessage);

  useEffect(() => { loadChatHistory(); }, []);
  useEffect(() => { fetchCreditBalance(); }, [fetchCreditBalance]);
  useEffect(() => { scrollToBottom(); }, [messages, isLoading, proactiveMessages, structuredMessages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadChatHistory = async () => {
    try {
      const history = await aiService.getChatHistory();
      setMessages(
        history.map((msg: any) => ({
          id: msg.id,
          role: msg.role,
          content: msg.content,
          timestamp: new Date(msg.timestamp),
        }))
      );
    } catch (err) {
      console.error('Failed to load chat history:', err);
    }
  };

  const handleSend = async () => {
    if ((!input.trim() && !attachedFile) || isLoading) return;

  const displayContent = attachedFile
      ? (input.trim() ? `${t('chat.attachment')} ${attachedFile.name}\n${input.trim()}` : `${t('chat.attachment')} ${attachedFile.name}`)
      : input.trim();

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: displayContent,
      timestamp: new Date(),
      fileName: attachedFile?.name,
    };

    setMessages((prev) => [...prev, userMessage]);
    const messageText = input.trim();
    const file = attachedFile;
    setInput('');
    setAttachedFile(null);
    setIsLoading(true);
    setError(null);

    try {
      let response;
      if (file) {
        response = await aiService.sendMessageWithFile(messageText, file, contextData);
      } else {
        response = await aiService.sendMessage(messageText, contextData);
      }
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.content,
        timestamp: new Date(),
        intent: response.intent,
        showDisclaimer: response.showDisclaimer,
        sourceTier: response.sourceTier,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err: any) {
      setError(err.message || t('ai.errorSendingMessage'));
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleClearHistory = async () => {
    const ok = await showConfirm(t('ai.confirmClearHistory'), { variant: 'warning' });
    if (!ok) return;
    try {
      await aiService.clearChatHistory();
      setMessages([]);
    } catch (err) {
      console.error('Failed to clear history:', err);
    }
  };

  const handleSuggestedQuestion = (question: string) => {
    setInput(question);
    inputRef.current?.focus();
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > MAX_FILE_SIZE) {
      setError(t('ai.fileTooLarge', 'File is too large. Maximum size is 10MB.'));
      return;
    }
    setAttachedFile(file);
    setError(null);
    e.target.value = '';
  };

  const getContextGreeting = () => {
    const page = contextData?.page;
    switch (page) {
      case 'dashboard':
        return t('ai.greeting.dashboard', 'I can see your dashboard. Want me to analyze your tax situation or check for savings opportunities?');
      case 'transactions':
        return t('ai.greeting.transactions', 'Looking at your transactions? I can help classify them, check deductibility, or explain VAT rules.');
      case 'documents':
        return t('ai.greeting.documents', 'Working with documents? Upload a receipt or invoice and I\'ll extract the details for you.');
      case 'reports':
        return t('ai.greeting.reports', 'Need help with your tax reports? I can explain the numbers or guide you through FinanzOnline filing.');
      case 'recurring':
        return t('ai.greeting.recurring', 'Managing recurring transactions? I can help set up regular expenses or check their tax treatment.');
      default:
        return t('ai.greeting.general', 'I\'m your tax advisor. Ask me anything about Austrian tax law, deductions, or your financial data.');
    }
  };

  const getPlaceholder = () => {
    if (attachedFile) return t('ai.fileAttachedPlaceholder', 'Add a message about this file...');
    const page = contextData?.page;
    switch (page) {
      case 'transactions': return t('ai.placeholder.transactions', 'Ask about a transaction...');
      case 'documents': return t('ai.placeholder.documents', 'Ask about a document...');
      case 'dashboard': return t('ai.placeholder.dashboard', 'Ask about your tax overview...');
      default: return t('ai.inputPlaceholder', 'Ask me anything...');
    }
  };

  const isEmpty = messages.length === 0 && !isLoading;
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const availableCredits = creditBalance?.available_without_overage;
  const creditDisplay = creditLoading && availableCredits === undefined
    ? '...'
    : availableCredits !== undefined
      ? String(availableCredits)
      : '--';

  const handleConfirmRecurring = useCallback(async (pm: ProactiveMessage) => {
    if (!pm.documentId) return;
    setActionLoading(pm.id);
    try {
      const isExpense = pm.actionData?.suggestion_type === 'create_recurring_expense';
      let result: any;
      if (isExpense) {
        result = await documentService.confirmRecurringExpense(pm.documentId);
      } else {
        result = await documentService.confirmRecurring(pm.documentId);
      }
      updateMessageAction(pm.id, 'confirmed');
      pushMessage({
        type: 'tip',
        content: isExpense
          ? t('ai.proactive.recurringExpenseConfirmed')
          : t('ai.proactive.recurringConfirmed'),
      });

      // If property was auto-created from rental contract, notify user to fill in details
      if (!isExpense && result?.property_auto_created) {
        pushMessage({
          type: 'reminder',
          content: t('ai.proactive.propertyAutoCreatedFromRental', {
            address: result.property_address || '',
          }),
          link: `/properties/${result.property_id}`,
        });
      }
      const { refreshRecurring, refreshTransactions, refreshDashboard, refreshProperties } = useRefreshStore.getState();
      refreshRecurring();
      refreshDashboard();
      refreshProperties();
      if (isExpense) refreshTransactions();

      // If unit_percentage is null after confirm, prompt user to set it
      if (!isExpense && result && result.recurring_id && result.unit_percentage == null) {
        pushMessage({
          type: 'unit_percentage_prompt',
          content: t('ai.proactive.setUnitPercentage'),
          actionData: { recurring_id: result.recurring_id, property_id: result.property_id },
          actionStatus: 'pending',
        });
      }
    } catch (err: any) {
      console.error('Failed to confirm recurring:', err);
      setError(err?.response?.data?.detail || err?.message || 'Error');
    } finally {
      setActionLoading(null);
    }
  }, [updateMessageAction, pushMessage, t]);

  const handleDismissRecurring = useCallback(async (pm: ProactiveMessage) => {
    if (!pm.documentId) return;
    setActionLoading(pm.id);
    try {
      await documentService.dismissSuggestion(pm.documentId);
      updateMessageAction(pm.id, 'dismissed');
      pushMessage({
        type: 'tip',
        content: t('ai.proactive.recurringDismissed'),
      });
    } catch (err: any) {
      console.error('Failed to dismiss suggestion:', err);
    } finally {
      setActionLoading(null);
    }
  }, [updateMessageAction, pushMessage, t]);

  const handleConfirmEmployerMonth = useCallback(async (pm: ProactiveMessage) => {
    const yearMonth = typeof pm.actionData?.year_month === 'string' ? pm.actionData.year_month : undefined;
    if (!yearMonth) {
      return;
    }

    setActionLoading(pm.id);
    try {
      await employerService.confirmPayroll({
        year_month: yearMonth,
        document_id: pm.documentId,
        payroll_signal: typeof pm.actionData?.payroll_signal === 'string' ? pm.actionData.payroll_signal : undefined,
        source_type: 'ai_confirm',
        employee_count: parseNumericValue(pm.actionData?.employee_count),
        gross_wages: parseNumericValue(pm.actionData?.gross_wages),
        net_paid: parseNumericValue(pm.actionData?.net_paid),
        lohnsteuer: parseNumericValue(pm.actionData?.lohnsteuer),
      });

      updateMessageAction(pm.id, 'confirmed');
      pushMessage({
        type: 'tip',
        content: t('ai.proactive.employerMonthConfirmed', {
          defaultValue: '{{month}} is now recorded as a payroll month.',
          month: formatEmployerMonthLabel(yearMonth, getLocaleForLanguage(i18n.language)),
        }),
      });

      const { refreshDashboard } = useRefreshStore.getState();
      refreshDashboard();
    } catch (err: any) {
      console.error('Failed to confirm employer month:', err);
      setError(err?.response?.data?.detail || err?.message || 'Error');
    } finally {
      setActionLoading(null);
    }
  }, [pushMessage, t, updateMessageAction]);

  const handleConfirmNoPayroll = useCallback(async (pm: ProactiveMessage) => {
    const yearMonth = typeof pm.actionData?.year_month === 'string' ? pm.actionData.year_month : undefined;
    if (!yearMonth) {
      return;
    }

    setActionLoading(pm.id);
    try {
      await employerService.confirmNoPayroll(
        yearMonth,
        pm.documentId
          ? `Confirmed via AI review for document ${pm.documentId}`
          : 'Confirmed via AI review'
      );

      updateMessageAction(pm.id, 'dismissed');
      pushMessage({
        type: 'tip',
        content: t('ai.proactive.employerMonthNoPayroll', {
          defaultValue: '{{month}} has been marked as a month without employees.',
          month: formatEmployerMonthLabel(yearMonth, getLocaleForLanguage(i18n.language)),
        }),
      });

      const { refreshDashboard } = useRefreshStore.getState();
      refreshDashboard();
    } catch (err: any) {
      console.error('Failed to confirm no-payroll month:', err);
      setError(err?.response?.data?.detail || err?.message || 'Error');
    } finally {
      setActionLoading(null);
    }
  }, [pushMessage, t, updateMessageAction]);

  const handleConfirmAnnualArchive = useCallback(async (pm: ProactiveMessage) => {
    const taxYear = parseNumericValue(pm.actionData?.tax_year);
    if (!taxYear) {
      return;
    }

    setActionLoading(pm.id);
    try {
      await employerService.confirmAnnualArchive({
        tax_year: taxYear,
        document_id: pm.documentId,
        archive_signal: typeof pm.actionData?.archive_signal === 'string' ? pm.actionData.archive_signal : undefined,
        source_type: 'ai_confirm',
        employer_name: typeof pm.actionData?.employer_name === 'string' ? pm.actionData.employer_name : undefined,
        gross_income: parseNumericValue(pm.actionData?.gross_income),
        withheld_tax: parseNumericValue(pm.actionData?.withheld_tax),
      });

      updateMessageAction(pm.id, 'confirmed');
      pushMessage({
        type: 'tip',
        content: t('ai.proactive.employerAnnualArchiveConfirmed', {
          defaultValue: 'The payroll year pack for {{year}} has been archived.',
          year: taxYear,
        }),
      });

      const { refreshDashboard } = useRefreshStore.getState();
      refreshDashboard();
    } catch (err: any) {
      console.error('Failed to confirm annual payroll archive:', err);
      setError(err?.response?.data?.detail || err?.message || 'Error');
    } finally {
      setActionLoading(null);
    }
  }, [pushMessage, t, updateMessageAction]);

  const [percentageInputs, setPercentageInputs] = useState<Record<string, string>>({});

  const handleSubmitUnitPercentage = useCallback(async (pm: ProactiveMessage) => {
    const val = Number(percentageInputs[pm.id]);
    if (!val || val <= 0 || val > 100 || !pm.actionData?.recurring_id) return;
    setActionLoading(pm.id);
    try {
      await recurringService.update(pm.actionData.recurring_id, { unit_percentage: val });
      updateMessageAction(pm.id, 'confirmed');
      // Recalculate property rental percentage
      if (pm.actionData.property_id) {
        try {
          await propertyService.recalculateRental(pm.actionData.property_id);
        } catch (_) { /* ignore */ }
      }
      pushMessage({
        type: 'tip',
        content: t('ai.proactive.unitPercentageSaved', { percentage: val }),
      });
      const { refreshRecurring, refreshProperties, refreshDashboard } = useRefreshStore.getState();
      refreshRecurring();
      refreshProperties();
      refreshDashboard();
    } catch (err: any) {
      console.error('Failed to save unit percentage:', err);
      setError(err?.message || 'Error');
    } finally {
      setActionLoading(null);
    }
  }, [percentageInputs, updateMessageAction, pushMessage, t]);

  const getProactiveLinkActions = useCallback((pm: ProactiveMessage) => {
    const actions: Array<{ href: string; label: string }> = [];

    if (pm.link) {
      actions.push({
        href: pm.link,
        label:
          pm.linkLabel ||
          (pm.link.startsWith('/documents/')
            ? t('ai.proactive.viewDocument', 'View document')
            : t('ai.proactive.viewDetails', 'View details')),
      });
    }

    if (pm.secondaryLink) {
      actions.push({
        href: pm.secondaryLink,
        label: pm.secondaryLinkLabel || t('ai.proactive.viewDocument', 'View document'),
      });
    }

    return actions;
  }, [t]);

  return (
    <div className="chat-interface">
      <div className="chat-messages">
        {isEmpty && (
          <div className="chat-welcome">
            <div className="chat-welcome-advisor">
              <div className="chat-advisor-avatar-lg">T</div>
              <div className="chat-welcome-text">
                <p className="chat-welcome-greeting">
                  {t('ai.welcomeTitle', 'Hi, I\'m your Taxja advisor')}
                </p>
                <p className="chat-welcome-context">{getContextGreeting()}</p>
              </div>
            </div>

            <SuggestedQuestions
              key={contextData?.page}
              contextData={contextData}
              onQuestionClick={handleSuggestedQuestion}
            />
          </div>
        )}

        {/* Chat history messages rendered first (older) */}
        {messages.map((message, idx) => {
          const isAssistant = message.role === 'assistant';
          const showAvatar = isAssistant && (idx === 0 || messages[idx - 1]?.role !== 'assistant');
          return (
            <div key={message.id} className={`chat-msg ${message.role}`}>
              {isAssistant && (
                <div className={`chat-msg-avatar${showAvatar ? '' : ' invisible'}`}>T</div>
              )}
              <div className="chat-msg-bubble">
                {message.role === 'user' ? (
                  <p>{message.content}</p>
                ) : (
                  <AIResponse content={message.content} intent={message.intent} showDisclaimer={message.showDisclaimer} sourceTier={message.sourceTier} />
                )}
                <span className="chat-msg-time">
                  {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            </div>
          );
        })}

        {/* Proactive advisor messages — shown after chat history (newer session messages) */}
        {proactiveMessages.filter((m) => !m.dismissed).length > 0 && (
          <div className="chat-proactive-section">
            {proactiveMessages.filter((m) => !m.dismissed).slice(-5)
              .sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime())
              .map((pm) => {
              const linkActions = getProactiveLinkActions(pm);

              return (
              <div key={pm.id} className="chat-msg assistant chat-proactive-bubble">
                <div className="chat-msg-avatar">T</div>
                <div className="chat-msg-bubble">
                  <button
                    type="button"
                    className="chat-proactive-dismiss"
                    onClick={() => dismissMessage(pm.id)}
                    aria-label={t('common.close')}
                  >
                    <XMark size={12} />
                  </button>
                  {pm.content.split('\n').map((line, i) => (
                    <p key={i} className="chat-proactive-line">{line}</p>
                  ))}

                  {/* Recurring transaction confirmation card */}
                  {!pm.bucket && pm.type === 'recurring_confirm' && pm.actionStatus === 'pending' && pm.actionData && (
                    <div className="chat-recurring-card">
                      <div className="chat-recurring-details">
                        {pm.actionData.monthly_rent && (
                          <div className="chat-recurring-row">
                            <span>{t('documents.ocr.monthlyRent', 'Monthly rent')}</span>
                            <span className="chat-recurring-value">
                              € {Number(pm.actionData.monthly_rent).toLocaleString(getLocaleForLanguage(i18n.language), { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </span>
                          </div>
                        )}
                        {pm.actionData.amount && !pm.actionData.monthly_rent && (
                          <div className="chat-recurring-row">
                            <span>{t('common.amount', 'Amount')}</span>
                            <span className="chat-recurring-value">
                              € {Number(pm.actionData.amount).toLocaleString(getLocaleForLanguage(i18n.language), { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </span>
                          </div>
                        )}
                        {pm.actionData.frequency && !pm.actionData.monthly_rent && (
                          <div className="chat-recurring-row">
                            <span>{t('recurring.frequency.label', 'Frequency')}</span>
                            <span className="chat-recurring-value">{String(t(`recurring.frequency.${pm.actionData.frequency}`, pm.actionData.frequency))}</span>
                          </div>
                        )}
                        {(pm.actionData.address || pm.actionData.matched_property_address) && (
                          <div className="chat-recurring-row">
                            <span>{t('documents.ocr.propertyAddress', 'Address')}</span>
                            <span className="chat-recurring-value">{pm.actionData.address || pm.actionData.matched_property_address}</span>
                          </div>
                        )}
                        {pm.actionData.start_date && (
                          <div className="chat-recurring-row">
                            <span>{t('documents.ocr.startDate', 'Start date')}</span>
                            <span className="chat-recurring-value">
                              {(() => { try { return new Date(pm.actionData.start_date).toLocaleDateString(getLocaleForLanguage(i18n.language)); } catch { return pm.actionData.start_date; } })()}
                            </span>
                          </div>
                        )}
                        {pm.actionData.end_date && (
                          <div className="chat-recurring-row">
                            <span>{t('recurring.form.endDate', 'End date')}</span>
                            <span className="chat-recurring-value">
                              {(() => { try { return new Date(pm.actionData.end_date).toLocaleDateString(getLocaleForLanguage(i18n.language)); } catch { return pm.actionData.end_date; } })()}
                            </span>
                          </div>
                        )}
                      </div>
                      <div className="chat-recurring-actions">
                        <button
                          className="chat-recurring-btn confirm"
                          onClick={() => handleConfirmRecurring(pm)}
                          disabled={actionLoading === pm.id}
                        >
                          {actionLoading === pm.id ? <Loader2 size={14} className="spin" /> : <Check size={14} />}
                          <span>{t('documents.suggestion.confirm', 'Confirm')}</span>
                        </button>
                        <button
                          className="chat-recurring-btn dismiss"
                          onClick={() => handleDismissRecurring(pm)}
                          disabled={actionLoading === pm.id}
                        >
                          <XMark size={14} />
                          <span>{t('ai.proactive.skip', 'Skip')}</span>
                        </button>
                      </div>
                      {linkActions.length > 0 && (
                        <div className="chat-inline-link-actions">
                          {linkActions.map((action) => (
                            <button
                              key={`${pm.id}-${action.href}`}
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

                  {/* Show result after action */}
                  {!pm.bucket && pm.type === 'recurring_confirm' && pm.actionStatus === 'confirmed' && (
                    <div className="chat-recurring-result confirmed">
                      <Check size={14} /> {t('ai.proactive.recurringConfirmed')}
                    </div>
                  )}
                  {!pm.bucket && pm.type === 'recurring_confirm' && pm.actionStatus === 'dismissed' && (
                    <div className="chat-recurring-result dismissed">
                      {t('ai.proactive.recurringDismissed')}
                    </div>
                  )}

                  {!pm.bucket && pm.type === 'employer_month_confirm' && pm.actionStatus === 'pending' && pm.actionData && (
                    <div className="chat-recurring-card">
                      <div className="chat-recurring-details">
                        {pm.actionData.year_month && (
                          <div className="chat-recurring-row">
                            <span>{t('common.month', 'Month')}</span>
                            <span className="chat-recurring-value">
                              {formatEmployerMonthLabel(pm.actionData.year_month, getLocaleForLanguage(i18n.language))}
                            </span>
                          </div>
                        )}
                        {pm.actionData.file_name && (
                          <div className="chat-recurring-row">
                            <span>{t('documents.title', 'Document')}</span>
                            <span className="chat-recurring-value">{pm.actionData.file_name}</span>
                          </div>
                        )}
                        {formatCurrency(pm.actionData.gross_wages) && (
                          <div className="chat-recurring-row">
                            <span>{t('documents.ocr.grossIncome', 'Gross income')}</span>
                            <span className="chat-recurring-value">
                              EUR {formatCurrency(pm.actionData.gross_wages)}
                            </span>
                          </div>
                        )}
                        {formatCurrency(pm.actionData.lohnsteuer) && (
                          <div className="chat-recurring-row">
                            <span>{t('transactions.fields.lohnsteuer', 'Lohnsteuer')}</span>
                            <span className="chat-recurring-value">
                              EUR {formatCurrency(pm.actionData.lohnsteuer)}
                            </span>
                          </div>
                        )}
                      </div>
                      <div className="chat-recurring-actions">
                        <button
                          className="chat-recurring-btn confirm"
                          onClick={() => handleConfirmEmployerMonth(pm)}
                          disabled={actionLoading === pm.id}
                        >
                          {actionLoading === pm.id ? <Loader2 size={14} className="spin" /> : <Check size={14} />}
                          <span>{t('ai.proactive.recordPayrollMonth', 'Record payroll month')}</span>
                        </button>
                        <button
                          className="chat-recurring-btn dismiss"
                          onClick={() => handleConfirmNoPayroll(pm)}
                          disabled={actionLoading === pm.id}
                        >
                          <XMark size={14} />
                          <span>{t('ai.proactive.noPayrollThisMonth', 'No employees this month')}</span>
                        </button>
                      </div>
                      {linkActions.length > 0 && (
                        <div className="chat-inline-link-actions">
                          {linkActions.map((action) => (
                            <button
                              key={`${pm.id}-${action.href}`}
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
                  {!pm.bucket && pm.type === 'employer_month_confirm' && pm.actionStatus === 'confirmed' && (
                    <div className="chat-recurring-result confirmed">
                      <Check size={14} />{' '}
                      {t('ai.proactive.employerMonthConfirmed', {
                        defaultValue: '{{month}} is now recorded as a payroll month.',
                        month: formatEmployerMonthLabel(pm.actionData?.year_month, getLocaleForLanguage(i18n.language)),
                      })}
                    </div>
                  )}
                  {!pm.bucket && pm.type === 'employer_month_confirm' && pm.actionStatus === 'dismissed' && (
                    <div className="chat-recurring-result dismissed">
                      {t('ai.proactive.employerMonthNoPayroll', {
                        defaultValue: '{{month}} has been marked as a month without employees.',
                        month: formatEmployerMonthLabel(pm.actionData?.year_month, getLocaleForLanguage(i18n.language)),
                      })}
                    </div>
                  )}
                  {!pm.bucket && pm.type === 'employer_annual_archive_confirm' && pm.actionStatus === 'pending' && pm.actionData && (
                    <div className="chat-recurring-card">
                      <div className="chat-recurring-details">
                        {pm.actionData.tax_year && (
                          <div className="chat-recurring-row">
                            <span>{t('common.year', 'Year')}</span>
                            <span className="chat-recurring-value">{pm.actionData.tax_year}</span>
                          </div>
                        )}
                        {pm.actionData.file_name && (
                          <div className="chat-recurring-row">
                            <span>{t('documents.title', 'Document')}</span>
                            <span className="chat-recurring-value">{pm.actionData.file_name}</span>
                          </div>
                        )}
                        {pm.actionData.employer_name && (
                          <div className="chat-recurring-row">
                            <span>{t('documents.ocr.employer', 'Employer')}</span>
                            <span className="chat-recurring-value">{pm.actionData.employer_name}</span>
                          </div>
                        )}
                        {formatCurrency(pm.actionData.gross_income) && (
                          <div className="chat-recurring-row">
                            <span>{t('documents.ocr.grossIncome', 'Gross income')}</span>
                            <span className="chat-recurring-value">
                              EUR {formatCurrency(pm.actionData.gross_income)}
                            </span>
                          </div>
                        )}
                      </div>
                      <div className="chat-recurring-actions">
                        <button
                          className="chat-recurring-btn confirm"
                          onClick={() => handleConfirmAnnualArchive(pm)}
                          disabled={actionLoading === pm.id}
                        >
                          {actionLoading === pm.id ? <Loader2 size={14} className="spin" /> : <Check size={14} />}
                          <span>{t('ai.proactive.archivePayrollYear', 'Archive payroll year')}</span>
                        </button>
                        <button
                          className="chat-recurring-btn dismiss"
                          onClick={() => updateMessageAction(pm.id, 'dismissed')}
                          disabled={actionLoading === pm.id}
                        >
                          <XMark size={14} />
                          <span>{t('ai.proactive.later', 'Later')}</span>
                        </button>
                      </div>
                      {linkActions.length > 0 && (
                        <div className="chat-inline-link-actions">
                          {linkActions.map((action) => (
                            <button
                              key={`${pm.id}-${action.href}`}
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
                  {!pm.bucket && pm.type === 'employer_annual_archive_confirm' && pm.actionStatus === 'confirmed' && (
                    <div className="chat-recurring-result confirmed">
                      <Check size={14} />{' '}
                      {t('ai.proactive.employerAnnualArchiveConfirmed', {
                        defaultValue: 'The payroll year pack for {{year}} has been archived.',
                        year: pm.actionData?.tax_year,
                      })}
                    </div>
                  )}
                  {!pm.bucket && pm.type === 'employer_annual_archive_confirm' && pm.actionStatus === 'dismissed' && (
                    <div className="chat-recurring-result dismissed">
                      {t('ai.proactive.laterSaved', {
                        defaultValue: 'No problem. You can archive this payroll year later.',
                      })}
                    </div>
                  )}

                  {/* Contract expired — action buttons: upload renewal or go to manual add */}
                  {!pm.bucket && pm.type === 'contract_expired' && pm.actionStatus === 'pending' && (
                    <div className="chat-recurring-actions" style={{ marginTop: '8px' }}>
                      <button
                        className="chat-recurring-btn confirm"
                        onClick={() => { navigate('/documents'); updateMessageAction(pm.id, 'confirmed'); }}
                      >
                        <FileText size={14} />
                        <span>{t('ai.proactive.uploadRenewal')}</span>
                      </button>
                      {pm.actionData?.property_id && (
                        <button
                          className="chat-recurring-btn confirm"
                          onClick={() => { navigate(`/properties/${pm.actionData!.property_id}?addContract=1`); updateMessageAction(pm.id, 'confirmed'); }}
                        >
                          <Plus size={14} />
                          <span>{t('ai.proactive.addContractManually')}</span>
                        </button>
                      )}
                      <button
                        className="chat-recurring-btn dismiss"
                        onClick={() => updateMessageAction(pm.id, 'dismissed')}
                      >
                        <XMark size={14} />
                        <span>{t('ai.proactive.skip', 'Skip')}</span>
                      </button>
                    </div>
                  )}
                  {!pm.bucket && pm.type === 'contract_expired' && pm.actionStatus !== 'pending' && (
                    <div className="chat-recurring-result confirmed">
                      <Check size={14} />
                    </div>
                  )}

                  {/* Unit percentage prompt — inline input in chat */}
                  {!pm.bucket && pm.type === 'unit_percentage_prompt' && pm.actionStatus === 'pending' && (
                    <div className="chat-recurring-card">
                      <div className="chat-recurring-details">
                        <div className="chat-recurring-row">
                          <span>{t('properties.rentalContracts.unitPercentage')}</span>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <input
                              type="number"
                              min="0.01"
                              max="100"
                              step="0.01"
                              style={{ width: '80px', padding: '4px 8px', borderRadius: '6px', border: '1px solid #ddd', fontSize: '0.85rem' }}
                              placeholder="e.g. 33"
                              value={percentageInputs[pm.id] || ''}
                              onChange={(e) => setPercentageInputs((prev) => ({ ...prev, [pm.id]: e.target.value }))}
                              onKeyDown={(e) => { if (e.key === 'Enter') handleSubmitUnitPercentage(pm); }}
                            />
                            <span style={{ fontSize: '0.85rem' }}>%</span>
                          </div>
                        </div>
                      </div>
                      <div className="chat-recurring-actions">
                        <button
                          className="chat-recurring-btn confirm"
                          onClick={() => handleSubmitUnitPercentage(pm)}
                          disabled={actionLoading === pm.id || !percentageInputs[pm.id]}
                        >
                          {actionLoading === pm.id ? <Loader2 size={14} className="spin" /> : <Check size={14} />}
                          <span>{t('common.confirm')}</span>
                        </button>
                        <button
                          className="chat-recurring-btn dismiss"
                          onClick={() => updateMessageAction(pm.id, 'dismissed')}
                          disabled={actionLoading === pm.id}
                        >
                          <XMark size={14} />
                          <span>{t('ai.proactive.skip', 'Skip')}</span>
                        </button>
                      </div>
                    </div>
                  )}
                  {!pm.bucket && pm.type === 'unit_percentage_prompt' && pm.actionStatus === 'confirmed' && (
                    <div className="chat-recurring-result confirmed">
                      <Check size={14} /> {t('ai.proactive.unitPercentageSaved', { percentage: percentageInputs[pm.id] || '' })}
                    </div>
                  )}
                  {!pm.bucket && pm.type === 'unit_percentage_prompt' && pm.actionStatus === 'dismissed' && (
                    <div className="chat-recurring-result dismissed">
                      {t('ai.proactive.skipped')}
                    </div>
                  )}

                  {/* Tax form review — show extracted data summary + view button */}
                  {!pm.bucket && pm.type === 'tax_form_review' && pm.actionStatus === 'pending' && pm.actionData && (
                    <div className="chat-recurring-card">
                      <div className="chat-recurring-details">
                        {pm.actionData.suggestion_type && (
                          <div className="chat-recurring-row">
                            <span>{t('documents.fields.type', 'Type')}</span>
                            <span className="chat-recurring-value">{pm.actionData.suggestion_type.replace('import_', '').toUpperCase()}</span>
                          </div>
                        )}
                        {pm.actionData.tax_year && (
                          <div className="chat-recurring-row">
                            <span>{t('common.year', 'Year')}</span>
                            <span className="chat-recurring-value">{pm.actionData.tax_year}</span>
                          </div>
                        )}
                        {pm.actionData.summary && pm.actionData.summary.split('\n').map((line: string, i: number) => {
                          const parts = line.split(': ');
                          return parts.length === 2 ? (
                            <div key={i} className="chat-recurring-row">
                              <span>{parts[0]}</span>
                              <span className="chat-recurring-value">{parts[1]}</span>
                            </div>
                          ) : null;
                        })}
                      </div>
                      <div className="chat-recurring-actions">
                        <button
                          className="chat-recurring-btn confirm"
                          onClick={() => { if (pm.link) navigate(pm.link); updateMessageAction(pm.id, 'confirmed'); }}
                        >
                          <ClipboardList size={14} />
                          <span>{t('ai.proactive.viewAndConfirm', 'View & Confirm')}</span>
                        </button>
                        <button
                          className="chat-recurring-btn dismiss"
                          onClick={() => updateMessageAction(pm.id, 'dismissed')}
                        >
                          <XMark size={14} />
                          <span>{t('ai.proactive.later', 'Later')}</span>
                        </button>
                      </div>
                    </div>
                  )}
                  {!pm.bucket && pm.type === 'tax_form_review' && pm.actionStatus === 'confirmed' && (
                    <div className="chat-recurring-result confirmed">
                      <Check size={14} /> {t('ai.proactive.taxFormViewed', 'Navigated to document for review.')}
                    </div>
                  )}

                  {/* Inline action buttons for actionable proactive messages (asset_confirm, tax_form_review, etc.) */}
                  {isActionableProactive(pm) && (
                    <ChatProactiveAction message={pm} />
                  )}

                  {/* Generic link buttons for messages with navigation but no special card-level CTA */}
                  {linkActions.length > 0 && !isActionableProactive(pm) && !['recurring_confirm', 'employer_month_confirm', 'employer_annual_archive_confirm', 'contract_expired', 'unit_percentage_prompt', 'tax_form_review'].includes(pm.type) && (
                    <div className="chat-inline-link-actions">
                      {linkActions.map((action) => (
                        <button
                          key={`${pm.id}-${action.href}`}
                          className="chat-recurring-btn confirm chat-inline-link-btn"
                          onClick={() => navigate(action.href)}
                          type="button"
                        >
                          <ArrowRight size={14} />
                          <span>{action.label}</span>
                        </button>
                      ))}
                    </div>
                  )}

                  <span className="chat-msg-time">
                    {pm.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              </div>
            );
            })}
          </div>
        )}

        {/* Structured AI messages — after Q&A so they appear at the bottom */}
        {structuredMessages.length > 0 && structuredMessages.map((sm) => {
          if (sm.type === 'processing_update') {
            return <ChatProcessingIndicator key={sm.id} message={sm as ProcessingUpdateMessage} />;
          }
          if (sm.type === 'suggestion') {
            return <ChatSuggestionCard key={sm.id} message={sm as SuggestionChatMessage} />;
          }
          if (sm.type === 'follow_up') {
            return <ChatFollowUpQuestion key={sm.id} message={sm as FollowUpChatMessage} />;
          }
          return null;
        })}

        {isLoading && (
          <div className="chat-msg assistant">
            <div className="chat-msg-avatar">T</div>
            <div className="chat-msg-bubble">
              <div className="chat-typing">
                <span className="chat-typing-dot" />
                <span className="chat-typing-dot" />
                <span className="chat-typing-dot" />
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="chat-error">
            <p>{error}</p>
          </div>
        )}
        {!isEmpty && !isLoading && (
          <SuggestedQuestions
            key={contextData?.page}
            contextData={contextData}
            onQuestionClick={handleSuggestedQuestion}
          />
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">
        <div className="chat-credits-bar" title={t('subscription.credits_available', 'Available credits')}>
          <span className="chat-credits-label">{t('subscription.credits_title', 'Credits')}</span>
          <span className="chat-credits-pill">
            <span className="chat-credits-icon">⚡</span>
            <strong>{creditDisplay}</strong>
          </span>
        </div>

        {attachedFile && (
          <div className="chat-file-preview">
            <Paperclip size={14} />
            <span className="chat-file-name">{attachedFile.name}</span>
            <button className="chat-file-remove" onClick={() => setAttachedFile(null)} aria-label={t('common.remove', 'Remove')}>
              <XIcon size={14} />
            </button>
          </div>
        )}

        <div className="chat-input-row">
          {enableFileUpload && (
            <>
              <input
                ref={fileInputRef}
                type="file"
                accept={ACCEPTED_FILE_TYPES}
                onChange={handleFileSelect}
                className="chat-file-input"
                aria-hidden="true"
                tabIndex={-1}
              />
              <button
                className="chat-action-btn"
                onClick={() => fileInputRef.current?.click()}
                disabled={isLoading}
                aria-label={t('ai.attachFile', 'Attach file')}
                title={t('ai.attachFile', 'Attach file')}
              >
                <Paperclip size={18} />
              </button>
            </>
          )}
          {messages.length > 0 && (
            <button
              className="chat-action-btn chat-action-btn--clear"
              onClick={handleClearHistory}
              disabled={isLoading}
              aria-label={t('ai.clearHistory')}
              title={t('ai.clearHistory')}
            >
              <Trash2 size={16} />
            </button>
          )}
          <textarea
            ref={inputRef}
            className="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={getPlaceholder()}
            rows={1}
            disabled={isLoading}
          />
          <button
            className="chat-send-btn"
            onClick={handleSend}
            disabled={(!input.trim() && !attachedFile) || isLoading}
            aria-label={t('ai.send')}
          >
            {isLoading ? <Loader2 size={18} className="spin" /> : <ArrowUp size={18} />}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;
