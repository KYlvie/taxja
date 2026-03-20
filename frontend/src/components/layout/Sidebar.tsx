import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { LogOut, UserRound, X } from 'lucide-react';
import { useAuthStore } from '../../stores/authStore';
import LanguageSwitcher from '../common/LanguageSwitcher';
import { getLayoutCopy } from './layoutCopy';
import './Sidebar.css';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  collapsed?: boolean;
}

const Sidebar = ({ isOpen, onClose, collapsed }: SidebarProps) => {
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const copy = getLayoutCopy(i18n.resolvedLanguage || i18n.language);
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);

  const menuItems = [
    { path: '/dashboard', label: t('nav.dashboard'), icon: '\u25A7' },
    { path: '/documents', label: t('nav.documents'), icon: '\u25A3' },
    { path: '/transactions', label: t('nav.transactions'), icon: '\u21C4' },
    { path: '/reports', label: t('nav.reports'), icon: '\u25F0' },
    { path: '/advanced', label: copy.advancedLabel, icon: '\u2699' },
  ];

  // Admin menu items — only shown to admin users
  const adminItems = user?.is_admin ? [
    { path: '/admin', label: t('nav.admin', 'Admin'), icon: '\u2699' },
    { path: '/admin/tax-configs', label: t('nav.taxConfigs', 'Tax Config'), icon: '\u2696' },
  ] : [];

  // External admin tools (open in new tab)
  const adminExternalLinks = user?.is_admin ? [
    { href: 'http://localhost:9001', label: t('nav.minioConsole', 'MinIO Console'), icon: '\u2601' },
  ] : [];

  const isActive = (path: string) => {
    if (path === '/advanced') {
      return (
        location.pathname === path ||
        location.pathname.startsWith(`${path}/`) ||
        location.pathname.startsWith('/properties') ||
        location.pathname.startsWith('/recurring') ||
        location.pathname.startsWith('/tax-tools')
      );
    }

    return location.pathname === path || location.pathname.startsWith(`${path}/`);
  };

  const userName = user?.name || t('nav.profile');
  const userEmail = user?.email || '';
  const userInitial = (userName || 'T').trim().charAt(0).toUpperCase() || 'T';

  const handleLogout = () => {
    logout();
    window.location.href = '/login';
  };

  return (
    <>
      {isOpen && <div className="sidebar-overlay" onClick={onClose} />}
      <aside className={`sidebar ${isOpen ? 'open' : ''} ${collapsed ? 'collapsed' : ''}`}>
        <div className="sidebar-mobile-controls">
          <LanguageSwitcher />
          <button
            type="button"
            className="sidebar-mobile-close"
            onClick={onClose}
            aria-label={t('common.close')}
          >
            <X size={18} />
          </button>
        </div>

        <Link to="/" className="sidebar-brand" onClick={onClose}>
          <span className="sidebar-brand-mark">TJ</span>
          <div className="sidebar-brand-copy">
            <strong>{t('common.appName')}</strong>
            <span>{copy.sidebarSubtitle}</span>
          </div>
        </Link>

        <nav className="sidebar-nav">
          {menuItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={`sidebar-item ${isActive(item.path) ? 'active' : ''}`}
              onClick={onClose}
            >
              <span className="sidebar-icon">{item.icon}</span>
              <span className="sidebar-label">{item.label}</span>
            </Link>
          ))}

          {adminItems.length > 0 && (
            <>
              <div className="sidebar-divider" />
              {adminItems.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`sidebar-item admin-item ${isActive(item.path) ? 'active' : ''}`}
                  onClick={onClose}
                >
                  <span className="sidebar-icon">{item.icon}</span>
                  <span className="sidebar-label">{item.label}</span>
                </Link>
              ))}
              {adminExternalLinks.map((item) => (
                <a
                  key={item.href}
                  href={item.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="sidebar-item admin-item"
                  onClick={onClose}
                >
                  <span className="sidebar-icon">{item.icon}</span>
                  <span className="sidebar-label">{item.label}</span>
                </a>
              ))}
            </>
          )}
        </nav>

        <div className="sidebar-account-card">
          <div className="sidebar-account-meta">
            <span className="sidebar-account-avatar">{userInitial}</span>
            <div className="sidebar-account-copy">
              <strong>{userName}</strong>
              {userEmail ? <span>{userEmail}</span> : null}
            </div>
          </div>

          <div className="sidebar-account-actions">
            <Link to="/profile" className="sidebar-account-link" onClick={onClose}>
              <UserRound size={16} />
              <span>{t('nav.profile')}</span>
            </Link>
            <Link to="/pricing" className="sidebar-account-link" onClick={onClose}>
              <span className="sidebar-icon-inline">◇</span>
              <span>{t('nav.pricing')}</span>
            </Link>
            <button type="button" className="sidebar-account-logout" onClick={handleLogout}>
              <LogOut size={16} />
              <span>{t('auth.logout')}</span>
            </button>
          </div>
        </div>

      </aside>
    </>
  );
};

export default Sidebar;
