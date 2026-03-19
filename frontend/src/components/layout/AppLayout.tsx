import { useEffect, useState, useCallback } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import Header from './Header';
import Sidebar from './Sidebar';
import MobileBottomNav from './MobileBottomNav';
import FloatingAIChat from '../ai/FloatingAIChat';
import './AppLayout.css';

const SIDEBAR_COLLAPSED_KEY = 'taxja_sidebar_collapsed';

const AppLayout = () => {
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try {
      return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === 'true';
    } catch {
      return false;
    }
  });

  const toggleSidebar = useCallback(() => {
    const isMobile = window.innerWidth <= 768;
    if (isMobile) {
      setSidebarOpen(prev => !prev);
    } else {
      setSidebarCollapsed(prev => {
        const next = !prev;
        try { localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(next)); } catch {}
        return next;
      });
    }
  }, []);

  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    const bodyClassName = 'mobile-sidebar-open';
    if (sidebarOpen) {
      document.body.classList.add(bodyClassName);
    } else {
      document.body.classList.remove(bodyClassName);
    }
    return () => { document.body.classList.remove(bodyClassName); };
  }, [sidebarOpen]);

  const layoutClass = [
    'app-layout',
    sidebarOpen ? 'sidebar-is-open' : '',
    sidebarCollapsed ? 'sidebar-collapsed' : '',
  ].filter(Boolean).join(' ');

  return (
    <div className={layoutClass}>
      <Header onMenuClick={toggleSidebar} sidebarCollapsed={sidebarCollapsed} />
      <div className="app-content">
        <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} collapsed={sidebarCollapsed} />
        <main className="main-content">
          <div className="main-content-shell">
            <Outlet />
          </div>
        </main>
      </div>
      <FloatingAIChat />
      <MobileBottomNav />
    </div>
  );
};

export default AppLayout;
