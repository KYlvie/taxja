import { useState, useEffect } from 'react';
import { RouterProvider } from 'react-router-dom';
import { router } from './routes';
import { useAuthStore } from './stores/authStore';
import DisclaimerModal from './components/common/DisclaimerModal';
import GlobalConfirmDialog from './components/common/GlobalConfirmDialog';
import AIToastContainer from './components/common/AIToast';
import { OfflineBanner } from './components/mobile/OfflineBanner';
import './i18n';
import './App.css';

function App() {
  const { isAuthenticated, user } = useAuthStore();
  const [showDisclaimer, setShowDisclaimer] = useState(false);

  useEffect(() => {
    if (isAuthenticated) {
      const accepted = sessionStorage.getItem('taxja_disclaimer_accepted');
      // Wait until onboarding finishes before showing disclaimer
      const onboardingDone = !user || user.onboarding_completed;
      if (!accepted && onboardingDone) {
        setShowDisclaimer(true);
      } else {
        setShowDisclaimer(false);
      }
    } else {
      sessionStorage.removeItem('taxja_disclaimer_accepted');
      setShowDisclaimer(false);
    }
  }, [isAuthenticated, user]);

  const handleDisclaimerAccept = () => {
    sessionStorage.setItem('taxja_disclaimer_accepted', '1');
    setShowDisclaimer(false);
  };

  return (
    <>
      <OfflineBanner />
      <RouterProvider router={router} />
      <DisclaimerModal isOpen={showDisclaimer} onAccept={handleDisclaimerAccept} />
      <GlobalConfirmDialog />
      <AIToastContainer />
    </>
  );
}

export default App;
