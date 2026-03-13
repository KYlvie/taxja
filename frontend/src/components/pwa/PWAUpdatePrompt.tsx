import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useRegisterSW } from 'virtual:pwa-register/react';
import './PWAUpdatePrompt.css';

export const PWAUpdatePrompt = () => {
  const { t } = useTranslation();
  const [showPrompt, setShowPrompt] = useState(false);

  const {
    offlineReady: [offlineReady, setOfflineReady],
    needRefresh: [needRefresh, setNeedRefresh],
    updateServiceWorker,
  } = useRegisterSW({
    onRegistered(r) {
      console.log('SW Registered: ' + r);
    },
    onRegisterError(error) {
      console.log('SW registration error', error);
    },
  });

  useEffect(() => {
    if (offlineReady || needRefresh) {
      setShowPrompt(true);
    }
  }, [offlineReady, needRefresh]);

  const close = () => {
    setOfflineReady(false);
    setNeedRefresh(false);
    setShowPrompt(false);
  };

  const handleUpdate = () => {
    updateServiceWorker(true);
  };

  if (!showPrompt) return null;

  return (
    <div className="pwa-update-prompt">
      <div className="pwa-update-content">
        {offlineReady ? (
          <>
            <div className="pwa-update-icon">✓</div>
            <div className="pwa-update-text">
              <h3>{t('pwa.offlineReady')}</h3>
              <p>{t('pwa.offlineDescription')}</p>
            </div>
            <button className="pwa-update-button" onClick={close}>
              {t('pwa.gotIt')}
            </button>
          </>
        ) : (
          <>
            <div className="pwa-update-icon">🔄</div>
            <div className="pwa-update-text">
              <h3>{t('pwa.newVersion')}</h3>
              <p>{t('pwa.newVersionDescription')}</p>
            </div>
            <div className="pwa-update-actions">
              <button className="pwa-update-button primary" onClick={handleUpdate}>
                {t('pwa.reload')}
              </button>
              <button className="pwa-update-button" onClick={close}>
                {t('pwa.later')}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
