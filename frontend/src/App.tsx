import { useState, useEffect } from 'react';
import { RouterProvider } from 'react-router-dom';
import { router } from './routes';
import { useAuthStore } from './stores/authStore';
import { userService } from './services/userService';
import DisclaimerModal from './components/common/DisclaimerModal';
import './i18n';
import './App.css';

function App() {
  const { isAuthenticated } = useAuthStore();
  const [showDisclaimer, setShowDisclaimer] = useState(false);
  const [disclaimerChecked, setDisclaimerChecked] = useState(false);

  useEffect(() => {
    const checkDisclaimer = async () => {
      if (isAuthenticated && !disclaimerChecked) {
        try {
          const status = await userService.getDisclaimerStatus();
          if (!status.accepted) {
            setShowDisclaimer(true);
          }
          setDisclaimerChecked(true);
        } catch (error) {
          console.error('Failed to check disclaimer status:', error);
          setDisclaimerChecked(true);
        }
      }
    };

    checkDisclaimer();
  }, [isAuthenticated, disclaimerChecked]);

  const handleDisclaimerAccept = () => {
    setShowDisclaimer(false);
  };

  return (
    <>
      <RouterProvider router={router} />
      <DisclaimerModal isOpen={showDisclaimer} onAccept={handleDisclaimerAccept} />
    </>
  );
}

export default App;
