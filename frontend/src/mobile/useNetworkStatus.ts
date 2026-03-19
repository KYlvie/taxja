import { useEffect, useState } from 'react';
import { type ConnectionStatus } from '@capacitor/network';
import { getNetworkStatus, onNetworkChange } from './network';

/**
 * React hook that returns the current network connection status.
 * Updates reactively when the connection changes.
 */
export const useNetworkStatus = (): ConnectionStatus => {
  const [status, setStatus] = useState<ConnectionStatus>(getNetworkStatus);

  useEffect(() => {
    return onNetworkChange(setStatus);
  }, []);

  return status;
};
