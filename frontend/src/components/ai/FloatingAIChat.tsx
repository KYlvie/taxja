import {
  useEffect,
  useState,
  useCallback,
  useMemo,
  useRef,
  type MouseEvent as ReactMouseEvent,
} from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router-dom';
import { X, ChevronUp, ChevronDown, MessageSquare, Maximize2, Minimize2 } from 'lucide-react';
import ChatInterface from './ChatInterface';
import { useAIAdvisorStore, type ActionDescriptor, type ProactiveMessage } from '../../stores/aiAdvisorStore';
import { useAuthStore } from '../../stores/authStore';
import { useSubscriptionStore } from '../../stores/subscriptionStore';
import { dashboardService, type ProactiveReminderDto } from '../../services/dashboardService';
import { translateReminderContent } from '../../utils/proactiveReminderI18n';
import './FloatingAIChat.css';

const PANEL_HEIGHT_KEY = 'taxja_ai_panel_height';
const PANEL_OPEN_KEY = 'taxja_ai_panel_open';
const TOOLTIP_DISMISSED_KEY = 'taxja_ai_tooltip_dismissed';
const TAX_TIP_KEYS = ['deadline', 'receipts', 'svs', 'homeOffice'] as const;
const MIN_PANEL_H = 180;
const MAX_PANEL_H = 900;
const DEFAULT_PANEL_H = 320;

const formatEuroAmount = (value: number | string | null | undefined) => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return null;
  }

  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(numeric);
};

const getNotifIcon = (type: string) => {
  const icons: Record<string, string> = {
    login: '👋',
    tip: '💡',
    reminder: '📅',
    upload_success: '✅',
    upload_review: '📋',
    upload_error: '❌',
    recurring_confirm: '🔄',
    contract_expired: '🔴',
    health_check: '📊',
    tax_form_review: '📋',
    asset_confirm: '🏠',
  };
  return icons[type] || '💬';
};

const LEGACY_PROACTIVE_TYPES = new Set<ProactiveMessage['type']>([
  'login',
  'upload_success',
  'upload_review',
  'upload_error',
  'tip',
  'reminder',
  'recurring_confirm',
  'unit_percentage_prompt',
  'contract_expired',
  'health_check',
  'asset_confirm',
  'employer_month_confirm',
  'employer_annual_archive_confirm',
  'tax_form_review',
]);

const toProactiveMessageType = (value?: string): ProactiveMessage['type'] => {
  if (value && LEGACY_PROACTIVE_TYPES.has(value as ProactiveMessage['type'])) {
    return value as ProactiveMessage['type'];
  }
  return 'reminder';
};

const normalizeActionDescriptor = (
  action?: ProactiveReminderDto['action']
): ActionDescriptor | undefined => {
  if (!action || typeof action !== 'object') {
    return undefined;
  }

  const record = action as Record<string, unknown>;
  const endpoint = typeof record.endpoint === 'string' ? record.endpoint : undefined;
  const method =
    record.method === 'POST' || record.method === 'PUT' || record.method === 'DELETE'
      ? record.method
      : undefined;
  const kind = typeof record.kind === 'string' ? record.kind : undefined;
  const targetId = typeof record.target_id === 'string' ? record.target_id : undefined;

  if (!endpoint || !method || !kind || !targetId) {
    return undefined;
  }

  return {
    kind: kind as ActionDescriptor['kind'],
    targetId,
    endpoint,
    method,
    payload:
      typeof record.payload === 'object' && record.payload !== null
        ? (record.payload as Record<string, unknown>)
        : undefined,
    confirmLabel: typeof record.confirm_label === 'string' ? record.confirm_label : undefined,
    dismissLabel: typeof record.dismiss_label === 'string' ? record.dismiss_label : undefined,
    detailLabel: typeof record.detail_label === 'string' ? record.detail_label : undefined,
  };
};

const mapReminderToMessage = (
  reminder: ProactiveReminderDto,
  t: ReturnType<typeof useTranslation>['t']
): ProactiveMessage => ({
  id: `server:${reminder.id}`,
  serverId: reminder.id,
  messageOrigin: 'server',
  type: toProactiveMessageType(reminder.legacy_type),
  content: translateReminderContent(reminder.body_key, reminder.params, t),
  timestamp: new Date(),
  read: false,
  dismissed: false,
  link: reminder.link || undefined,
  documentId: reminder.document_id ?? undefined,
  actionData:
    typeof reminder.action_data === 'object' && reminder.action_data !== null
      ? (reminder.action_data as Record<string, unknown>)
      : undefined,
  actionStatus: reminder.bucket === 'terminal_action' ? 'pending' : undefined,
  severity: reminder.severity,
  action: normalizeActionDescriptor(reminder.action),
  bucket: reminder.bucket,
  kind: reminder.kind,
  sourceType: reminder.source_type,
  snoozedUntil: reminder.snoozed_until ?? null,
  nextDueAt: reminder.next_due_at ?? null,
});

const FloatingAIChat = () => {
  const { t, i18n } = useTranslation();
  const location = useLocation();

  const [panelOpen, setPanelOpen] = useState(() => localStorage.getItem(PANEL_OPEN_KEY) !== '0');
  const [panelHeight, setPanelHeight] = useState(() => {
    const saved = localStorage.getItem(PANEL_HEIGHT_KEY);
    return saved ? Math.max(MIN_PANEL_H, Math.min(MAX_PANEL_H, Number(saved))) : DEFAULT_PANEL_H;
  });
  const [isMaximized, setIsMaximized] = useState(false);
  const dragging = useRef(false);
  const startY = useRef(0);
  const startH = useRef(0);

  const [mobileOpen, setMobileOpen] = useState(false);
  const [mobileExpanded, setMobileExpanded] = useState(false);
  const [showTooltip, setShowTooltip] = useState(false);
  const [isMobile, setIsMobile] = useState(() => window.innerWidth <= 768);

  const {
    messages: proactiveMessages,
    unreadCount,
    markAllRead,
    pushMessage,
    dismissMessage,
    loginGreetingShown,
    setLoginGreetingShown,
    pendingConfirmation,
    pendingSuggestionDocIds,
    processingDocs,
    syncServerMessages,
  } = useAIAdvisorStore();

  const totalBadgeCount = unreadCount + pendingSuggestionDocIds.length + processingDocs.length;
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const user = useAuthStore((s) => s.user);
  const creditBalance = useSubscriptionStore((s) => s.creditBalance);
  const creditLoading = useSubscriptionStore((s) => s.creditLoading);
  const fetchCreditBalance = useSubscriptionStore((s) => s.fetchCreditBalance);
  const toggleOverage = useSubscriptionStore((s) => s.toggleOverage);
  const openCustomerPortal = useSubscriptionStore((s) => s.openCustomerPortal);
  const [overageBusy, setOverageBusy] = useState(false);
  const [billingBusy, setBillingBusy] = useState(false);
  const [overageError, setOverageError] = useState<string | null>(null);

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth <= 768);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  const visibleNotifs = useMemo(() => {
    return proactiveMessages.filter((m) => !m.read && !m.dismissed).slice(-6);
  }, [proactiveMessages]);

  useEffect(() => {
    localStorage.setItem(PANEL_OPEN_KEY, panelOpen ? '1' : '0');
  }, [panelOpen]);

  useEffect(() => {
    localStorage.setItem(PANEL_HEIGHT_KEY, String(panelHeight));
  }, [panelHeight]);

  useEffect(() => {
    if (!pendingConfirmation) {
      return;
    }
    if (isMobile) {
      setMobileOpen(true);
    } else {
      setPanelOpen(true);
    }
  }, [pendingConfirmation, isMobile]);

  // Fetch credit balance when panel opens or on first load (avoid infinite loop by not including creditBalance in deps)
  const creditBalanceInitialized = useRef(false);
  useEffect(() => {
    if (!isAuthenticated) {
      return;
    }

    if (panelOpen || mobileOpen || !creditBalanceInitialized.current) {
      creditBalanceInitialized.current = true;
      void fetchCreditBalance();
    }
  }, [isAuthenticated, panelOpen, mobileOpen, fetchCreditBalance]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (isMobile) {
      document.documentElement.style.setProperty('--ai-dock-height', '0px');
      document.documentElement.classList.remove('ai-chat-maximized');
      return () => { document.documentElement.classList.remove('ai-chat-maximized'); };
    }
    const h = panelOpen ? (isMaximized ? MAX_PANEL_H : panelHeight) : 38;
    document.documentElement.style.setProperty('--ai-dock-height', `${h}px`);
    if (panelOpen && isMaximized) {
      document.documentElement.classList.add('ai-chat-maximized');
    } else {
      document.documentElement.classList.remove('ai-chat-maximized');
    }
    return () => { document.documentElement.classList.remove('ai-chat-maximized'); };
  }, [panelOpen, panelHeight, isMaximized, isMobile]);

  const dockCreditDisplay =
    creditLoading && creditBalance === null
      ? '...'
      : creditBalance
        ? String(creditBalance.available_without_overage)
        : '--';
  const overageSupported =
    creditBalance?.overage_price_per_credit !== null &&
    creditBalance?.overage_price_per_credit !== undefined;
  const overageEnabled = creditBalance?.overage_enabled ?? false;
  const overageSuspended = creditBalance?.has_unpaid_overage ?? false;
  const overageRate = formatEuroAmount(creditBalance?.overage_price_per_credit);
  const overageEstimate = formatEuroAmount(creditBalance?.estimated_overage_cost);
  const overageDisplay =
    creditLoading && creditBalance === null
      ? '...'
      : overageSuspended
        ? t('subscription.overage_suspended', 'Paused')
        : overageSupported
          ? overageEnabled
            ? t('subscription.overage_on', 'Overage on')
            : t('subscription.overage_off', 'Overage off')
          : t('subscription.overage_unavailable', 'No overage');
  const overageTitle = overageSuspended
    ? t(
        'subscription.overage_payment_due_message',
        'Overage is paused until your unpaid invoice is settled in Stripe.'
      )
    : overageSupported
      ? [
          t('subscription.overage_mode', 'Overage'),
          overageRate
            ? t('subscription.overage_rate', {
                defaultValue: '{{rate}} / credit',
                rate: overageRate,
              })
            : null,
          overageEstimate
            ? t('subscription.overage_estimate', {
                defaultValue: 'Estimate {{amount}}',
                amount: overageEstimate,
              })
            : null,
        ]
          .filter(Boolean)
          .join(' | ')
      : t('subscription.overage_unavailable', 'No overage');
  const overagePillClassName = `ai-overage-pill${
    overageEnabled && !overageSuspended ? ' is-enabled' : ''
  }${overageSuspended ? ' is-suspended' : ''}`;
  const overageToggleDisabled =
    !overageSupported || overageBusy || creditBalance === null || overageSuspended;

  const handleOverageToggle = useCallback(
    async (event: ReactMouseEvent<HTMLButtonElement>) => {
      event.preventDefault();
      event.stopPropagation();

      if (!creditBalance || !overageSupported || overageBusy || overageSuspended) {
        return;
      }

      setOverageError(null);
      setOverageBusy(true);
      try {
        await toggleOverage(!overageEnabled);
      } catch (error) {
        setOverageError(
          error instanceof Error
            ? error.message
            : t('subscription.overage_toggle_error', 'Failed to update overage mode.')
        );
      } finally {
        setOverageBusy(false);
      }
    },
    [creditBalance, overageBusy, overageSupported, overageSuspended, overageEnabled, toggleOverage, t]
  );

  const handleResolveBilling = useCallback(async () => {
    setOverageError(null);
    setBillingBusy(true);
    try {
      await openCustomerPortal(window.location.href);
    } catch (error) {
      setOverageError(
        error instanceof Error
          ? error.message
          : t('subscription.billing_portal_error', 'Failed to open billing portal.')
      );
    } finally {
      setBillingBusy(false);
    }
  }, [openCustomerPortal, t]);

  const onDragStart = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      dragging.current = true;
      startY.current = e.clientY;
      startH.current = panelHeight;
      document.body.style.cursor = 'row-resize';
      document.body.style.userSelect = 'none';

      const onMove = (ev: MouseEvent) => {
        if (!dragging.current) {
          return;
        }
        const delta = startY.current - ev.clientY;
        setPanelHeight(Math.max(MIN_PANEL_H, Math.min(MAX_PANEL_H, startH.current + delta)));
      };
      const onUp = () => {
        dragging.current = false;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
      };
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
    },
    [panelHeight]
  );

  const togglePanel = useCallback(() => {
    setPanelOpen((prev) => {
      if (!prev) {
        markAllRead();
      }
      return !prev;
    });
    setIsMaximized(false);
  }, [markAllRead]);

  const handleMaximize = useCallback(() => {
    setIsMaximized((prev) => !prev);
  }, []);

  const handleMobileOpen = useCallback(() => {
    setMobileOpen(true);
    setShowTooltip(false);
    sessionStorage.setItem(TOOLTIP_DISMISSED_KEY, '1');
    markAllRead();
  }, [markAllRead]);

  useEffect(() => {
    if (!isMobile) {
      setShowTooltip(false);
      return;
    }
    if (!location.pathname.startsWith('/dashboard')) {
      setShowTooltip(false);
      return;
    }
    const dismissed = sessionStorage.getItem(TOOLTIP_DISMISSED_KEY);
    if (dismissed) {
      return;
    }
    const timer = window.setTimeout(() => setShowTooltip(true), 1500);
    return () => window.clearTimeout(timer);
  }, [location.pathname, isMobile]);

  const getContext = () => {
    const path = location.pathname;
    if (path.startsWith('/transactions')) return { page: 'transactions' };
    if (path.startsWith('/documents')) return { page: 'documents' };
    if (path.startsWith('/properties')) return { page: 'properties' };
    if (path.startsWith('/reports')) return { page: 'reports' };
    if (path.startsWith('/recurring')) return { page: 'recurring' };
    if (path.startsWith('/dashboard')) return { page: 'dashboard' };
    return { page: 'general' };
  };

  useEffect(() => {
    if (!isAuthenticated || !user || loginGreetingShown) {
      return;
    }

    const timer = window.setTimeout(async () => {
      const tipKey = TAX_TIP_KEYS[Math.floor(Math.random() * TAX_TIP_KEYS.length)];
      const greeting = t('ai.proactive.loginGreeting');
      const tip = `${t('ai.proactive.taxTip')} ${t(`ai.proactive.tips.${tipKey}`)}`;
      pushMessage({
        type: 'login',
        content: `${greeting}\n${tip}`,
        messageOrigin: 'local',
      });

      try {
        const suggestions = await dashboardService.getSuggestions();
        const items = suggestions?.suggestions || suggestions?.items || [];
        if (Array.isArray(items) && items.length > 0) {
          const top = items.slice(0, 2);
          const lines = top
            .map((suggestion: any) => {
              const text = suggestion.message || suggestion.description || suggestion.title || '';
              const amount = suggestion.potential_savings || suggestion.amount;
              return amount
                ? `• ${text} (${t('ai.proactive.potentialSave')} €${Number(amount).toLocaleString()})`
                : `• ${text}`;
            })
            .filter(Boolean);
          if (lines.length > 0) {
            pushMessage({
              type: 'tip',
              content: `💡 ${t('ai.proactive.personalizedTips')}\n${lines.join('\n')}`,
              messageOrigin: 'local',
            });
          }
        }
      } catch {
        // Keep greeting resilient.
      }

      setLoginGreetingShown();
    }, 2500);

    return () => window.clearTimeout(timer);
  }, [isAuthenticated, user, loginGreetingShown, setLoginGreetingShown, pushMessage, t]);

  useEffect(() => {
    let cancelled = false;

    const loadProactiveReminders = async () => {
      if (!isAuthenticated) {
        syncServerMessages([]);
        return;
      }

      try {
        const response = await dashboardService.getProactiveReminders();
        if (cancelled) {
          return;
        }
        const messages = (response.items || []).map((item) => mapReminderToMessage(item, t));
        syncServerMessages(messages);
      } catch {
        if (!cancelled) {
          syncServerMessages([]);
        }
      }
    };

    void loadProactiveReminders();
    const intervalId = window.setInterval(() => {
      void loadProactiveReminders();
    }, 60000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [isAuthenticated, i18n.language, i18n.resolvedLanguage, syncServerMessages, t]);

  const overageAlert = overageSuspended ? (
    <div className="ai-inline-alert ai-inline-alert--warning">
      <div className="ai-inline-alert-copy">
        <strong>{t('subscription.overage_payment_due_title', 'Overage paused')}</strong>
        <span>
          {t(
            'subscription.overage_payment_due_message',
            'Overage is paused until your unpaid invoice is settled in Stripe.'
          )}
        </span>
      </div>
      <button
        type="button"
        className="ai-inline-alert-action"
        onClick={handleResolveBilling}
        disabled={billingBusy}
      >
        {billingBusy
          ? t('pricing.buttons.loading', 'Loading...')
          : t('subscription.resolve_billing', 'Resolve billing')}
      </button>
    </div>
  ) : null;

  if (location.pathname === '/ai-assistant') {
    return null;
  }

  if (!isMobile) {
    const effectiveHeight = isMaximized ? MAX_PANEL_H : panelHeight;
    return (
      <>
        <div
          className={`ai-dock${panelOpen ? ' ai-dock--open' : ' ai-dock--closed'}${isMaximized ? ' ai-dock--maximized' : ''}`}
          style={panelOpen ? { height: effectiveHeight } : undefined}
        >
          {panelOpen && !isMaximized && (
            <div className="ai-dock-drag" onMouseDown={onDragStart} role="separator" aria-orientation="horizontal" />
          )}

          <div
            className="ai-dock-header"
            onClick={!panelOpen ? togglePanel : undefined}
            role={!panelOpen ? 'button' : undefined}
            tabIndex={!panelOpen ? 0 : undefined}
            onKeyDown={!panelOpen ? (e) => e.key === 'Enter' && togglePanel() : undefined}
          >
            <div className="ai-dock-header-left">
              {!panelOpen && visibleNotifs.length > 0 ? (
                <span className="ai-dock-avatar-indicator">
                  <span className="ai-dock-avatar-ring" />
                  T
                </span>
              ) : (
                <MessageSquare size={14} />
              )}
              <span className="ai-dock-title">Taxja AI</span>
              <span className="ai-dock-status-dot" />
              <div className="ai-dock-header-meta">
                <span className="ai-dock-credit-pill" title={t('subscription.credits_available', 'Available credits')}>
                  <span className="ai-dock-credit-icon">⚡</span>
                  <strong>{dockCreditDisplay}</strong>
                </span>
                <button
                  type="button"
                  className={overagePillClassName}
                  title={overageTitle}
                  onClick={handleOverageToggle}
                  disabled={overageToggleDisabled}
                >
                  <span className="ai-overage-pill-label">{t('subscription.overage_mode', 'Overage')}</span>
                  <strong>{overageDisplay}</strong>
                </button>
              </div>
              {!panelOpen && totalBadgeCount > 0 && (
                <span className="ai-dock-badge">{totalBadgeCount}</span>
              )}
              {!panelOpen && visibleNotifs.length > 0 && (
                <span className="ai-dock-preview">
                  {visibleNotifs[visibleNotifs.length - 1].content.split('\n')[0].slice(0, 60)}
                </span>
              )}
            </div>
            <div className="ai-dock-header-right">
              {panelOpen && (
                <button
                  type="button"
                  onClick={handleMaximize}
                  className="ai-dock-btn"
                  aria-label={isMaximized ? t('ai.collapse', 'Restore') : t('ai.expand', 'Maximize')}
                >
                  {isMaximized ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
                </button>
              )}
              <button
                type="button"
                onClick={togglePanel}
                className="ai-dock-btn"
                aria-label={panelOpen ? t('ai.collapse', 'Collapse') : t('ai.expand', 'Expand')}
              >
                {panelOpen ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
              </button>
            </div>
          </div>

          {panelOpen && (
            <div className="ai-dock-body">
              {visibleNotifs.length > 0 && (
                <div className="ai-dock-notifs">
                  <div className="ai-dock-notifs-header">
                    <span>{t('ai.notifications', 'Notifications')}</span>
                    <button
                      type="button"
                      onClick={() => visibleNotifs.forEach((message) => dismissMessage(message.id))}
                      className="ai-dock-notifs-clear"
                    >
                      {t('common.clearAll', 'Clear')}
                    </button>
                  </div>
                  <div className="ai-dock-notifs-list">
                    {visibleNotifs.map((message) => (
                      <div key={message.id} className={`ai-dock-notif ai-dock-notif--${message.severity || 'default'}`}>
                        <span className="ai-dock-notif-icon">{getNotifIcon(message.type)}</span>
                        <span className="ai-dock-notif-text">{message.content.split('\n')[0]}</span>
                        <button
                          type="button"
                          className="ai-dock-notif-x"
                          onClick={() => dismissMessage(message.id)}
                          aria-label={t('common.close')}
                        >
                          <X size={11} />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="ai-dock-chat">
                {overageAlert}
                {overageError && <div className="ai-inline-alert">{overageError}</div>}
                <ChatInterface contextData={getContext()} enableFileUpload />
              </div>
            </div>
          )}
        </div>
      </>
    );
  }

  return (
    <>
      {!mobileOpen && (
        <div className="ai-fab-wrapper">
          {showTooltip && (
            <div className="ai-fab-tooltip" role="status">
              <div className="ai-fab-tooltip-avatar">T</div>
              <div className="ai-fab-tooltip-body">
                <span className="ai-fab-tooltip-name">Taxja</span>
                <span>{t('ai.tooltip', "Need help with your taxes? I'm here.")}</span>
              </div>
              <button
                type="button"
                className="ai-fab-tooltip-close"
                onClick={() => {
                  setShowTooltip(false);
                  sessionStorage.setItem(TOOLTIP_DISMISSED_KEY, '1');
                }}
                aria-label={t('common.close')}
              >
                <X size={14} />
              </button>
            </div>
          )}
          <button
            type="button"
            className={`ai-fab${totalBadgeCount > 0 ? ' ai-fab--has-unread' : ''}`}
            onClick={handleMobileOpen}
            aria-label={t('ai.openChat', 'Open AI assistant')}
          >
            <div className="ai-fab-avatar">T</div>
            <span className="ai-fab-pulse" />
            {totalBadgeCount > 0 && (
              <span className="ai-fab-badge">{totalBadgeCount > 9 ? '9+' : totalBadgeCount}</span>
            )}
          </button>
        </div>
      )}

      {mobileOpen && (
        <div className={`ai-chat-panel${mobileExpanded ? ' ai-chat-expanded' : ''}`}>
          <div className="ai-chat-panel-header">
            <div className="ai-chat-panel-identity">
              <div className="ai-panel-avatar">T</div>
              <div className="ai-panel-info">
                <span className="ai-panel-name">{t('ai.advisorName', 'Taxja')}</span>
                <span className="ai-panel-status">
                  <span className="ai-status-dot" />
                  {t('ai.advisorStatus', 'Tax Advisor · Online')}
                </span>
                <div className="ai-panel-meta">
                  <span className="ai-panel-credit-pill" title={t('subscription.credits_available', 'Available credits')}>
                    <span className="ai-dock-credit-icon">⚡</span>
                    <strong>{dockCreditDisplay}</strong>
                  </span>
                  <button
                    type="button"
                    className={`${overagePillClassName} ai-overage-pill--mobile`}
                    title={overageTitle}
                    onClick={handleOverageToggle}
                    disabled={overageToggleDisabled}
                  >
                    <span className="ai-overage-pill-label">{t('subscription.overage_mode', 'Overage')}</span>
                    <strong>{overageDisplay}</strong>
                  </button>
                </div>
              </div>
            </div>
            <div className="ai-chat-panel-actions">
              <button
                type="button"
                onClick={() => setMobileExpanded((current) => !current)}
                aria-label={mobileExpanded ? t('ai.collapse') : t('ai.expand')}
              >
                {mobileExpanded ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
              </button>
              <button
                type="button"
                onClick={() => {
                  setMobileOpen(false);
                  setMobileExpanded(false);
                }}
                aria-label={t('common.close')}
              >
                <X size={16} />
              </button>
            </div>
          </div>
          <div className="ai-chat-panel-body">
            {overageAlert}
            {overageError && <div className="ai-inline-alert">{overageError}</div>}
            <ChatInterface contextData={getContext()} enableFileUpload />
          </div>
        </div>
      )}
    </>
  );
};

export default FloatingAIChat;
