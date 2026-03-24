import { NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Camera, CreditCard, FileText, House, UserRound } from 'lucide-react';
import FuturisticIcon from '../common/FuturisticIcon';
import './MobileNavigation.css';

export const MobileNavigation = () => {
  const { t } = useTranslation();

  return (
    <nav className="mobile-navigation">
      <NavLink
        to="/dashboard"
        className={({ isActive }) => `mobile-nav-item ${isActive ? 'active' : ''}`}
      >
        <div className="mobile-nav-icon">
          <FuturisticIcon icon={House} tone="cyan" size="sm" />
        </div>
        <div className="mobile-nav-label">{t('nav.dashboard')}</div>
      </NavLink>

      <NavLink
        to="/transactions"
        className={({ isActive }) => `mobile-nav-item ${isActive ? 'active' : ''}`}
      >
        <div className="mobile-nav-icon">
          <FuturisticIcon icon={CreditCard} tone="emerald" size="sm" />
        </div>
        <div className="mobile-nav-label">{t('nav.transactions')}</div>
      </NavLink>

      <NavLink
        to="/documents"
        className="mobile-nav-item mobile-nav-fab"
      >
        <div className="mobile-nav-fab-icon">
          <FuturisticIcon icon={Camera} tone="slate" size="md" />
        </div>
      </NavLink>

      <NavLink
        to="/documents"
        className={({ isActive }) => `mobile-nav-item ${isActive ? 'active' : ''}`}
      >
        <div className="mobile-nav-icon">
          <FuturisticIcon icon={FileText} tone="amber" size="sm" />
        </div>
        <div className="mobile-nav-label">{t('nav.documents')}</div>
      </NavLink>

      <NavLink
        to="/profile"
        className={({ isActive }) => `mobile-nav-item ${isActive ? 'active' : ''}`}
      >
        <div className="mobile-nav-icon">
          <FuturisticIcon icon={UserRound} tone="violet" size="sm" />
        </div>
        <div className="mobile-nav-label">{t('nav.profile')}</div>
      </NavLink>
    </nav>
  );
};
