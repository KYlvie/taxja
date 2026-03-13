import { useTranslation } from 'react-i18next';
import { useAuthStore } from '../../stores/authStore';
import LanguageSwitcher from '../common/LanguageSwitcher';
import './Header.css';

interface HeaderProps {
  onMenuClick: () => void;
}

const Header = ({ onMenuClick }: HeaderProps) => {
  const { t } = useTranslation();
  const { user, logout } = useAuthStore();

  const handleLogout = () => {
    logout();
    window.location.href = '/login';
  };

  return (
    <header className="header">
      <div className="header-left">
        <button className="menu-button" onClick={onMenuClick}>
          ☰
        </button>
        <h1 className="app-title">{t('common.appName')}</h1>
      </div>
      <div className="header-right">
        <LanguageSwitcher />
        <div className="user-menu">
          <span className="user-name">{user?.name}</span>
          <button className="logout-button" onClick={handleLogout}>
            {t('auth.logout')}
          </button>
        </div>
      </div>
    </header>
  );
};

export default Header;
