import { Network, type ConnectionStatus } from '@capacitor/network';
import { isNativeApp } from './runtime';

type NetworkChangeHandler = (status: ConnectionStatus) => void;

let currentStatus: ConnectionStatus = { connected: true, connectionType: 'unknown' };
const listeners: Set<NetworkChangeHandler> = new Set();

export const getNetworkStatus = (): ConnectionStatus => currentStatus;

export const isOnline = (): boolean => currentStatus.connected;

export const onNetworkChange = (handler: NetworkChangeHandler): (() => void) => {
  listeners.add(handler);
  return () => listeners.delete(handler);
};

export const initializeNetworkMonitor = async (): Promise<void> => {
  if (!isNativeApp()) {
    // Fallback to browser online/offline events
    currentStatus = { connected: navigator.onLine, connectionType: 'unknown' };

    window.addEventListener('online', () => {
      currentStatus = { connected: true, connectionType: 'unknown' };
      listeners.forEach((fn) => fn(currentStatus));
    });

    window.addEventListener('offline', () => {
      currentStatus = { connected: false, connectionType: 'none' };
      listeners.forEach((fn) => fn(currentStatus));
    });

    return;
  }

  currentStatus = await Network.getStatus();

  await Network.addListener('networkStatusChange', (status) => {
    currentStatus = status;
    listeners.forEach((fn) => fn(status));
  });
};
