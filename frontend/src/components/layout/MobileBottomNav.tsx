import { BarChart3, FileText, LayoutDashboard, ArrowLeftRight, UserRound } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import './MobileBottomNav.css';

const MobileBottomNav = () => {
  const { t } = useTranslation();
  const location = useLocation();

  const tabs = [
    { path: '/dashboard', label: t('nav.dashboard'), icon: LayoutDashboard },
    { path: '/transactions', label: t('nav.transactions'), icon: ArrowLeftRight },
    { path: '/documents', label: t('nav.documents'), icon: FileText },
    { path: '/reports', label: t('nav.reports'), icon: BarChart3 },
    { path: '/profile', label: t('nav.profile'), icon: UserRound },
  ];

  const isActive = (path: string) =>
    location.pathname === path || location.pathname.startsWith(`${path}/`);

  return (
    <nav
      className="mobile-bottom-nav"
      aria-label={t('common.navigation', 'Primary navigation')}
    >
      {tabs.map((tab) => {
        const Icon = tab.icon;

        return (
          <Link
            key={tab.path}
            to={tab.path}
            className={`mobile-bottom-nav-item${isActive(tab.path) ? ' active' : ''}`}
            aria-current={isActive(tab.path) ? 'page' : undefined}
          >
            <span className="mobile-bottom-nav-icon">
              <Icon size={18} strokeWidth={2.2} />
            </span>
            <span className="mobile-bottom-nav-label">{tab.label}</span>
          </Link>
        );
      })}
    </nav>
  );
};

export default MobileBottomNav;
