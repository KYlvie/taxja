import { useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '../../stores/authStore';
import { useSubscriptionStore } from '../../stores/subscriptionStore';
import { authService } from '../../services/authService';
import LanguageSwitcher from '../common/LanguageSwitcher';
import ThemeToggle from '../common/ThemeToggle';
import { getLayoutCopy } from './layoutCopy';
import { useCyberTilt } from '../../hooks/useCyberTilt';
import './Header.css';

interface HeaderProps {
  onMenuClick: () => void;
  sidebarCollapsed?: boolean;
}

const Header = ({ onMenuClick, sidebarCollapsed }: HeaderProps) => {
  const { t, i18n } = useTranslation();
  const { user, logout } = useAuthStore();
  const { currentPlan, fetchSubscription } = useSubscriptionStore();
  const location = useLocation();
  const copy = getLayoutCopy(i18n.resolvedLanguage || i18n.language);
  const tilt = useCyberTilt<HTMLElement>(6);

  useEffect(() => {
    if (user && !currentPlan) {
      fetchSubscription();
    }
  }, [user, currentPlan, fetchSubscription]);

  const planLabel = currentPlan?.name || 'Free';
  const planType = currentPlan?.plan_type || 'free';

  const activeLabel = [
    { path: '/dashboard', label: t('nav.dashboard') },
    { path: '/transactions', label: t('nav.transactions') },
    { path: '/advanced', label: copy.advancedLabel },
    { path: '/properties', label: t('nav.properties') },
    { path: '/recurring', label: t('nav.recurringTransactions') },
    { path: '/documents', label: t('nav.documents') },
    { path: '/reports', label: t('nav.reports') },
    { path: '/pricing', label: t('nav.pricing') },
    { path: '/profile', label: t('nav.profile') },
    { path: '/admin/tax-configs', label: t('nav.taxConfigs') },
    { path: '/admin', label: t('nav.admin') },
  ].find((item) => location.pathname.startsWith(item.path))?.label || t('common.appName');

  const userInitial = (user?.name || 'T').trim().charAt(0).toUpperCase() || 'T';

  const handleLogout = async () => {
    try {
      await authService.logout();
    } finally {
      logout();
      window.location.href = '/login';
    }
  };

  return (
    <header ref={tilt.ref} className="header" onMouseMove={tilt.onMove} onMouseLeave={tilt.onLeave}>
      <div className="header-left">
        <button type="button" className={`menu-button ${sidebarCollapsed ? 'sidebar-is-collapsed' : ''}`} onClick={onMenuClick} aria-label={copy.openNavigation}>
          <span />
          <span />
          <span />
        </button>

        <Link to="/" className="brand-lockup">
          <span className="brand-mark">
            <span className="brand-mark-core" />
          </span>
          <span className="brand-text-block">
            <span className="app-title">{t('common.appName')}</span>
            <span className="app-caption">{copy.appCaption}</span>
          </span>
        </Link>

        <div className="header-context">
          <span className="header-context-kicker">{copy.contextKicker}</span>
          <strong>{activeLabel}</strong>
        </div>
      </div>

      <div className="header-right">
        <Link to="/pricing" className="header-status" title={t('pricing.manageSubscription', 'Manage subscription')}>
          <span className={`header-plan-badge plan-${planType}`}>{planLabel}</span>
          <span style={{ position: 'relative', zIndex: 1 }}>{t('common.slogan')}</span>
        </Link>

        <LanguageSwitcher />
        <ThemeToggle />

        <div className="user-menu">
          <Link to="/profile" className="user-badge" aria-label={t('nav.profile')}>
            <span className="user-avatar">{userInitial}</span>
            <span className="user-name">{user?.name}</span>
          </Link>

          <button type="button" className="logout-button" onClick={handleLogout}>
            {t('auth.logout')}
          </button>
        </div>
      </div>
    </header>
  );
};

export default Header;
