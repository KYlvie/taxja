import { useEffect, useState, useCallback, useMemo, useRef, type MouseEvent as ReactMouseEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router-dom';
import { X, ChevronUp, ChevronDown, MessageSquare, Maximize2, Minimize2 } from 'lucide-react';
import ChatInterface from './ChatInterface';
import { useAIAdvisorStore } from '../../stores/aiAdvisorStore';
import { useAuthStore } from '../../stores/authStore';
import { useSubscriptionStore } from '../../stores/subscriptionStore';
import { dashboardService } from '../../services/dashboardService';
import { employerService } from '../../services/employerService';
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
    login: '👋', tip: '💡', reminder: '📅', upload_success: '✅',
    upload_review: '📋', upload_error: '❌', recurring_confirm: '🔄',
    contract_expired: '🔴', health_check: '📊', tax_form_review: '📋',
    asset_confirm: '🏠',
  };
  return icons[type] || '💬';
};

const FloatingAIChat = () => {
  const { t } = useTranslation();
  const location = useLocation();

  // Desktop docked panel state
  const [panelOpen, setPanelOpen] = useState(() =>
    localStorage.getItem(PANEL_OPEN_KEY) !== '0'
  );
  const [panelHeight, setPanelHeight] = useState(() => {
    const saved = localStorage.getItem(PANEL_HEIGHT_KEY);
    return saved ? Math.max(MIN_PANEL_H, Math.min(MAX_PANEL_H, Number(saved))) : DEFAULT_PANEL_H;
  });
  const [isMaximized, setIsMaximized] = useState(false);
  const dragging = useRef(false);
  const startY = useRef(0);
  const startH = useRef(0);

  // Mobile FAB state
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
  } = useAIAdvisorStore();
  // Combined badge count: unread proactive messages + pending suggestions + processing docs
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

  // Track viewport size
  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth <= 768);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  // Visible notifications (unread + not dismissed)
  const visibleNotifs = useMemo(() => {
    return proactiveMessages.filter((m) => !m.read && !m.dismissed).slice(-6);
  }, [proactiveMessages]);

  // Persist panel open state
  useEffect(() => {
    localStorage.setItem(PANEL_OPEN_KEY, panelOpen ? '1' : '0');
  }, [panelOpen]);

  // Persist panel height
  useEffect(() => {
    localStorage.setItem(PANEL_HEIGHT_KEY, String(panelHeight));
  }, [panelHeight]);

  // Auto-open panel when confirmation is pending
  useEffect(() => {
    if (!pendingConfirmation) return;
    if (isMobile) {
      setMobileOpen(true);
    } else {
      setPanelOpen(true);
    }
  }, [pendingConfirmation, isMobile]);

  useEffect(() => {
    if (!isAuthenticated) {
      return;
    }

    if (panelOpen || mobileOpen || creditBalance === null) {
      void fetchCreditBalance();
    }
  }, [isAuthenticated, panelOpen, mobileOpen, creditBalance, fetchCreditBalance]);

  // Expose dock height as CSS variable so sidebar can shrink accordingly
  useEffect(() => {
    if (isMobile) {
      document.documentElement.style.setProperty('--ai-dock-height', '0px');
      return;
    }
    const h = panelOpen ? (isMaximized ? MAX_PANEL_H : panelHeight) : 38;
    document.documentElement.style.setProperty('--ai-dock-height', `${h}px`);
  }, [panelOpen, panelHeight, isMaximized, isMobile]);

  const dockCreditDisplay = creditLoading && creditBalance === null
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
  const overageDisplay = creditLoading && creditBalance === null
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
        ].filter(Boolean).join(' | ')
      : t('subscription.overage_unavailable', 'No overage');
  const overagePillClassName = `ai-overage-pill${
    overageEnabled && !overageSuspended ? ' is-enabled' : ''
  }${overageSuspended ? ' is-suspended' : ''}`;
  const overageToggleDisabled =
    !overageSupported || overageBusy || creditBalance === null || overageSuspended;

  const handleOverageToggle = useCallback(async (event: ReactMouseEvent<HTMLButtonElement>) => {
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
  }, [creditBalance, overageBusy, overageSupported, overageSuspended, overageEnabled, toggleOverage, t]);

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

  // Drag resize handler (desktop only)
  const onDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;
    startY.current = e.clientY;
    startH.current = panelHeight;
    document.body.style.cursor = 'row-resize';
    document.body.style.userSelect = 'none';

    const onMove = (ev: MouseEvent) => {
      if (!dragging.current) return;
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
  }, [panelHeight]);

  const togglePanel = useCallback(() => {
    setPanelOpen((prev) => {
      if (!prev) markAllRead();
      return !prev;
    });
    setIsMaximized(false);
  }, [markAllRead]);

  const handleMaximize = useCallback(() => {
    setIsMaximized((prev) => !prev);
  }, []);

  // Mobile FAB open
  const handleMobileOpen = useCallback(() => {
    setMobileOpen(true);
    setShowTooltip(false);
    sessionStorage.setItem(TOOLTIP_DISMISSED_KEY, '1');
    markAllRead();
  }, [markAllRead]);

  // Dashboard tooltip (mobile only, first visit)
  useEffect(() => {
    if (!isMobile) { setShowTooltip(false); return; }
    if (!location.pathname.startsWith('/dashboard')) { setShowTooltip(false); return; }
    const dismissed = sessionStorage.getItem(TOOLTIP_DISMISSED_KEY);
    if (dismissed) return;
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

  // ── Login greeting ──
  useEffect(() => {
    if (!isAuthenticated || !user) return;
    if (loginGreetingShown) return;

    const timer = window.setTimeout(async () => {
      const tipKey = TAX_TIP_KEYS[Math.floor(Math.random() * TAX_TIP_KEYS.length)];
      const greeting = t('ai.proactive.loginGreeting');
      const tip = `${t('ai.proactive.taxTip')} ${t(`ai.proactive.tips.${tipKey}`)}`;
      pushMessage({ type: 'login', content: `${greeting}\n${tip}` });

      try {
        const suggestions = await dashboardService.getSuggestions();
        const items = suggestions?.suggestions || suggestions?.items || [];
        if (Array.isArray(items) && items.length > 0) {
          const top = items.slice(0, 2);
          const lines = top.map((s: any) => {
            const text = s.message || s.description || s.title || '';
            const amount = s.potential_savings || s.amount;
            return amount ? `• ${text}（${t('ai.proactive.potentialSave')} €${Number(amount).toLocaleString()}）` : `• ${text}`;
          }).filter(Boolean);
          if (lines.length > 0) {
            pushMessage({ type: 'tip', content: `💡 ${t('ai.proactive.personalizedTips')}\n${lines.join('\n')}` });
          }
        }
      } catch { /* skip */ }

      try {
        const calResp = await dashboardService.getCalendar();
        const deadlines = calResp?.deadlines || [];
        if (deadlines.length > 0) {
          const next = deadlines[0];
          const dStr = new Date(next.date).toLocaleDateString(undefined, { month: 'long', day: 'numeric' });
          pushMessage({ type: 'reminder', content: `📅 ${t('ai.proactive.nextDeadline', { title: next.title, date: dStr })}`, link: '/dashboard' });
        }
      } catch { /* skip */ }

      try {
        const alerts = await dashboardService.getAlerts();
        const pending = alerts?.pending_suggestions || [];
        for (const item of pending.slice(0, 3)) {
          if (item.suggestion_type === 'create_recurring_income') {
            pushMessage({ type: 'recurring_confirm', content: t('ai.proactive.pendingRecurringIncome', { description: item.description || item.file_name, amount: item.amount }), documentId: item.document_id, actionData: { ...item, monthly_rent: item.amount, suggestion_type: item.suggestion_type }, actionStatus: 'pending' });
          } else if (item.suggestion_type === 'create_recurring_expense') {
            pushMessage({ type: 'recurring_confirm', content: t('ai.proactive.pendingRecurringExpense', { description: item.description || item.file_name, amount: item.amount, frequency: t(`recurring.frequency.${item.frequency || 'monthly'}`) }), documentId: item.document_id, actionData: { ...item, suggestion_type: item.suggestion_type }, actionStatus: 'pending' });
          } else if (item.suggestion_type?.startsWith('import_')) {
            pushMessage({ type: 'tax_form_review', content: t('ai.proactive.pendingTaxForm', { defaultValue: '📋 You have unconfirmed tax form data from "{{name}}". Review and confirm to include in your tax filing.', name: item.file_name || item.description }), documentId: item.document_id, link: `/documents/${item.document_id}`, actionData: { suggestion_type: item.suggestion_type, file_name: item.file_name }, actionStatus: 'pending' });
          }
        }
        for (const item of (alerts?.expiring_contracts || []).slice(0, 3)) {
          const endStr = new Date(item.end_date).toLocaleDateString('de-AT');
          pushMessage({ type: 'reminder', content: `⚠️ ${t('ai.proactive.contractExpiring', { description: item.description, days: item.days_remaining, endDate: endStr })}`, link: item.property_id ? `/properties` : '/documents' });
        }
        for (const item of (alerts?.expired_contracts || []).slice(0, 3)) {
          const endStr = new Date(item.end_date).toLocaleDateString('de-AT');
          pushMessage({ type: 'contract_expired', content: `🔴 ${t('ai.proactive.contractExpired', { description: item.description, endDate: endStr })}`, actionData: { property_id: item.property_id, description: item.description }, actionStatus: 'pending' });
        }
      } catch { /* skip */ }

      try {
        const canCheck = user.employer_mode && user.employer_mode !== 'none' && (user.user_type === 'self_employed' || user.user_type === 'mixed');
        if (canCheck) {
          const overview = await employerService.getOverview(new Date().getFullYear());
          if (overview.missing_confirmation_months > 0) {
            const dl = overview.next_deadline ? new Date(overview.next_deadline).toLocaleDateString('de-AT') : null;
            pushMessage({ type: 'reminder', content: t('ai.proactive.employerMonthReminder', { defaultValue: dl ? 'You have {{count}} payroll month(s) waiting for confirmation. Next employer deadline: {{date}}.' : 'You have {{count}} payroll month(s) waiting for confirmation.', count: overview.missing_confirmation_months, date: dl || '' }), link: '/documents' });
          }
          const archives = await employerService.getAnnualArchives();
          const pendingArchives = archives.filter((a) => a.status === 'pending_confirmation');
          if (pendingArchives.length > 0) {
            pushMessage({ type: 'reminder', content: t('ai.proactive.employerAnnualArchiveReminder', { defaultValue: 'You still have {{count}} historical payroll year pack(s) waiting to be archived.', count: pendingArchives.length }), link: '/documents' });
          }
        }
      } catch { /* skip */ }

      try {
        const health = await dashboardService.getHealthCheck();
        const hItems = health?.items || [];
        if (hItems.length > 0) {
          const sevIcon: Record<string, string> = { high: '🔴', medium: '🟡', low: '💡' };
          let hp = 0, mp = 0;
          for (const item of hItems) {
            const sev = item.severity || 'low';
            if (sev === 'high' && hp >= 3) continue;
            if (sev === 'medium' && mp >= 2) continue;
            if (sev === 'low') continue;
            pushMessage({ type: 'health_check', content: `${sevIcon[sev] || '💡'} ${t(item.i18n_key, item.i18n_params || {})}`, link: item.action_url || undefined, severity: sev, actionData: { category: item.category, potential_savings: item.potential_savings, action_label: item.action_label_key ? t(item.action_label_key) : undefined } });
            if (sev === 'high') hp++;
            if (sev === 'medium') mp++;
          }
          if (health.score !== undefined && health.score < 80) {
            pushMessage({ type: 'health_check', content: `📊 ${t('healthCheck.title')}: ${health.score}/100 — ${t('healthCheck.itemsFound', { count: hItems.length })}`, link: '/dashboard', severity: health.score < 50 ? 'high' : 'medium' });
          }
        }
      } catch { /* skip */ }

      setLoginGreetingShown();
    }, 2500);
    return () => window.clearTimeout(timer);
  }, [isAuthenticated, user, loginGreetingShown, setLoginGreetingShown, pushMessage, t]);

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

  if (location.pathname === '/ai-assistant') return null;

  // ═══ DESKTOP: Docked bottom panel (IDE terminal style) ═══
  if (!isMobile) {
    const effectiveHeight = isMaximized ? MAX_PANEL_H : panelHeight;
    return (
      <>
        <div
          className={`ai-dock${panelOpen ? ' ai-dock--open' : ' ai-dock--closed'}${isMaximized ? ' ai-dock--maximized' : ''}`}
          style={panelOpen ? { height: effectiveHeight } : undefined}
        >
        {/* Drag handle for resizing */}
        {panelOpen && !isMaximized && (
          <div className="ai-dock-drag" onMouseDown={onDragStart} role="separator" aria-orientation="horizontal" />
        )}

        {/* Header bar — always visible */}
        <div className="ai-dock-header" onClick={!panelOpen ? togglePanel : undefined} role={!panelOpen ? 'button' : undefined} tabIndex={!panelOpen ? 0 : undefined} onKeyDown={!panelOpen ? (e) => e.key === 'Enter' && togglePanel() : undefined}>
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
            {!panelOpen && (visibleNotifs.length + pendingSuggestionDocIds.length + processingDocs.length) > 0 && (
              <span className="ai-dock-badge">{visibleNotifs.length + pendingSuggestionDocIds.length + processingDocs.length}</span>
            )}
            {!panelOpen && visibleNotifs.length > 0 && (
              <span className="ai-dock-preview">{visibleNotifs[visibleNotifs.length - 1].content.split('\n')[0].slice(0, 60)}</span>
            )}
          </div>
          <div className="ai-dock-header-right">
            {panelOpen && (
              <button type="button" onClick={handleMaximize} className="ai-dock-btn" aria-label={isMaximized ? t('ai.collapse', 'Restore') : t('ai.expand', 'Maximize')}>
                {isMaximized ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
              </button>
            )}
            <button type="button" onClick={togglePanel} className="ai-dock-btn" aria-label={panelOpen ? t('ai.collapse', 'Collapse') : t('ai.expand', 'Expand')}>
              {panelOpen ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
            </button>
          </div>
        </div>

        {/* Body — notification feed + chat */}
        {panelOpen && (
          <div className="ai-dock-body">
            {/* Notification sidebar within the panel */}
            {visibleNotifs.length > 0 && (
              <div className="ai-dock-notifs">
                <div className="ai-dock-notifs-header">
                  <span>{t('ai.notifications', 'Notifications')}</span>
                  <button type="button" onClick={() => visibleNotifs.forEach((m) => dismissMessage(m.id))} className="ai-dock-notifs-clear">
                    {t('common.clearAll', 'Clear')}
                  </button>
                </div>
                <div className="ai-dock-notifs-list">
                  {visibleNotifs.map((msg) => (
                    <div key={msg.id} className={`ai-dock-notif ai-dock-notif--${msg.severity || 'default'}`}>
                      <span className="ai-dock-notif-icon">{getNotifIcon(msg.type)}</span>
                      <span className="ai-dock-notif-text">{msg.content.split('\n')[0]}</span>
                      <button type="button" className="ai-dock-notif-x" onClick={() => dismissMessage(msg.id)} aria-label={t('common.close')}>
                        <X size={11} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {/* Chat area */}
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

  // ═══ MOBILE: FAB + overlay chat ═══
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
              <button type="button" className="ai-fab-tooltip-close" onClick={() => { setShowTooltip(false); sessionStorage.setItem(TOOLTIP_DISMISSED_KEY, '1'); }} aria-label={t('common.close')}>
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
              <button type="button" onClick={() => setMobileExpanded((c) => !c)} aria-label={mobileExpanded ? t('ai.collapse') : t('ai.expand')}>
                {mobileExpanded ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
              </button>
              <button type="button" onClick={() => { setMobileOpen(false); setMobileExpanded(false); }} aria-label={t('common.close')}>
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
