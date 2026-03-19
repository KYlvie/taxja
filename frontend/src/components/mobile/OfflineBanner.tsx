import { useTranslation } from 'react-i18next';
import { useNetworkStatus } from '../../mobile/useNetworkStatus';

export const OfflineBanner = () => {
  const { t } = useTranslation();
  const { connected } = useNetworkStatus();

  if (connected) return null;

  return (
    <div
      role="alert"
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        zIndex: 9999,
        background: '#d32f2f',
        color: '#fff',
        textAlign: 'center',
        padding: '8px 16px',
        fontSize: '14px',
        fontWeight: 500,
      }}
    >
      {t('common.offline', 'You are offline. Some features may be unavailable.')}
    </div>
  );
};
