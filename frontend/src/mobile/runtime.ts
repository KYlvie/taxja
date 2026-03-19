import { Capacitor } from '@capacitor/core';
import { App as CapacitorApp } from '@capacitor/app';
import { StatusBar, Style } from '@capacitor/status-bar';
import { initializeNetworkMonitor } from './network';
import { initializePushNotifications } from './notifications';

export const isNativeApp = (): boolean => Capacitor.isNativePlatform();

const normalizeNativeApiBaseUrl = (url: string): string => {
  const trimmedUrl = url.trim();

  if (!isNativeApp()) {
    return trimmedUrl;
  }

  const platform = Capacitor.getPlatform();

  if (platform !== 'android') {
    return trimmedUrl;
  }

  try {
    const parsedUrl = new URL(trimmedUrl);
    if (['localhost', '127.0.0.1', '0.0.0.0'].includes(parsedUrl.hostname)) {
      parsedUrl.hostname = '10.0.2.2';
      return parsedUrl.toString();
    }
  } catch {
    return trimmedUrl;
  }

  return trimmedUrl;
};

export const getApiBaseUrl = (): string => {
  const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();

  if (isNativeApp()) {
    const nativeBaseUrl = (
      import.meta.env.VITE_MOBILE_API_BASE_URL ||
      configuredBaseUrl ||
      'https://api.taxja.at/api/v1'
    ).trim();

    return normalizeNativeApiBaseUrl(nativeBaseUrl);
  }

  if (configuredBaseUrl) {
    return configuredBaseUrl;
  }

  return '/api/v1';
};

export const initializeMobileRuntime = async (): Promise<void> => {
  if (!isNativeApp()) {
    return;
  }

  document.documentElement.classList.add('is-native-app', `platform-${Capacitor.getPlatform()}`);

  try {
    await StatusBar.setStyle({ style: Style.Dark });
    await StatusBar.setOverlaysWebView({ overlay: false });
  } catch (error) {
    console.warn('Failed to initialize status bar', error);
  }

  try {
    await CapacitorApp.addListener('backButton', ({ canGoBack }) => {
      if (canGoBack) {
        window.history.back();
      } else {
        void CapacitorApp.exitApp();
      }
    });
  } catch (error) {
    console.warn('Failed to initialize native back button handler', error);
  }

  // Initialize network monitoring (works on both web and native)
  try {
    await initializeNetworkMonitor();
  } catch (error) {
    console.warn('Failed to initialize network monitor', error);
  }

  // Initialize push notification listeners (native only)
  try {
    await initializePushNotifications();
  } catch (error) {
    console.warn('Failed to initialize push notifications', error);
  }
};
