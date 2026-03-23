import { RouterProvider } from 'react-router-dom';
import { router } from './routes';
import GlobalConfirmDialog from './components/common/GlobalConfirmDialog';
import AIToastContainer from './components/common/AIToast';
import { OfflineBanner } from './components/mobile/OfflineBanner';
import './i18n';
import './App.css';

function App() {
  return (
    <>
      <OfflineBanner />
      <RouterProvider router={router} />
      <GlobalConfirmDialog />
      <AIToastContainer />
    </>
  );
}

export default App;
