import { Monitor, Zap } from 'lucide-react';
import { useThemeStore } from '../../stores/themeStore';
import './ThemeToggle.css';

const ThemeToggle = () => {
  const { theme, toggleTheme } = useThemeStore();
  const isCyber = theme === 'cyber';

  return (
    <button
      type="button"
      className={`theme-toggle${isCyber ? ' theme-toggle--cyber' : ''}`}
      onClick={toggleTheme}
      aria-label={isCyber ? 'Switch to Classic theme' : 'Switch to Cyber theme'}
      title={isCyber ? 'Classic mode' : 'Cyber mode'}
    >
      {isCyber ? <Zap size={16} /> : <Monitor size={16} />}
    </button>
  );
};

export default ThemeToggle;
