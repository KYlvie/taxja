import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import './Sidebar.css';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

const Sidebar = ({ isOpen, onClose }: SidebarProps) => {
  const { t } = useTranslation();
  const location = useLocation();

  const menuItems = [
    { path: '/dashboard', label: t('nav.dashboard'), icon: '📊' },
    { path: '/transactions', label: t('nav.transactions'), icon: '💰' },
    { path: '/properties', label: t('nav.assets', '资产'), icon: '💼' },
    { path: '/recurring', label: t('nav.recurringTransactions', '定期交易'), icon: '🔄' },
    { path: '/documents', label: t('nav.documents'), icon: '📄' },
    { path: '/reports', label: t('nav.reports'), icon: '📈' },
    { path: '/pricing', label: t('nav.pricing'), icon: '💎' },
    { path: '/profile', label: t('nav.profile'), icon: '👤' },
  ];

  const isActive = (path: string) => location.pathname === path;

  return (
    <>
      {isOpen && <div className="sidebar-overlay" onClick={onClose} />}
      <aside className={`sidebar ${isOpen ? 'open' : ''}`}>
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
        </nav>
      </aside>
    </>
  );
};

export default Sidebar;
