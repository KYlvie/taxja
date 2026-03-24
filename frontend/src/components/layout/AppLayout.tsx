import { useEffect, useState, useCallback } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import Header from './Header';
import Sidebar from './Sidebar';
import MobileBottomNav from './MobileBottomNav';
import FloatingAIChat from '../ai/FloatingAIChat';
import DisclaimerModal from '../common/DisclaimerModal';
import DraggableRobot from '../common/DraggableRobot';
import OnboardingGuide from '../onboarding/OnboardingGuide';
import { getPageTourSteps } from '../onboarding/tourConfigs';
import type { TourStep } from '../onboarding/tourConfigs';
import { useAuthStore } from '../../stores/authStore';
import { useCyberTilt } from '../../hooks/useCyberTilt';
import './AppLayout.css';

const SIDEBAR_COLLAPSED_KEY = 'taxja_sidebar_collapsed';

const AppLayout = () => {
  const location = useLocation();

  const { user, isAuthenticated } = useAuthStore((s) => ({ user: s.user, isAuthenticated: s.isAuthenticated }));

  // Show disclaimer once per login session
  const [showDisclaimer, setShowDisclaimer] = useState(() => {
    const accepted = sessionStorage.getItem('taxja_disclaimer_accepted');
    return !accepted;
  });

  useEffect(() => {
    if (!isAuthenticated) {
      sessionStorage.removeItem('taxja_disclaimer_accepted');
    }
  }, [isAuthenticated]);

  const handleDisclaimerAccept = () => {
    sessionStorage.setItem('taxja_disclaimer_accepted', '1');
    setShowDisclaimer(false);
  };
  const mainTilt = useCyberTilt<HTMLElement>(4);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showGuide, setShowGuide] = useState(false);
  const [tourSteps, setTourSteps] = useState<TourStep[] | undefined>(undefined);
  const [isPageTour, setIsPageTour] = useState(false);
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
        <main ref={mainTilt.ref} className="main-content" onMouseMove={mainTilt.onMove} onMouseLeave={mainTilt.onLeave}>
          <div className="main-content-shell">
            <Outlet />
          </div>
        </main>
      </div>
      <FloatingAIChat />
      <MobileBottomNav />

      <DraggableRobot onClick={() => {
        if (!user?.onboarding_completed) {
          setTourSteps(undefined);
          setIsPageTour(false);
        } else {
          const pageTour = getPageTourSteps(location.pathname);
          setTourSteps(pageTour ?? undefined);
          setIsPageTour(!!pageTour);
        }
        setShowGuide(true);
      }} />
      {showGuide && (
        <OnboardingGuide
          onClose={() => setShowGuide(false)}
          steps={tourSteps}
          isPageTour={isPageTour}
        />
      )}
      {showDisclaimer && isAuthenticated && (
        <DisclaimerModal isOpen={showDisclaimer} onAccept={handleDisclaimerAccept} />
      )}
    </div>
  );
};

export default AppLayout;
