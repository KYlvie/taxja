import { Browser } from '@capacitor/browser';
import { Capacitor } from '@capacitor/core';
import { isNativeApp } from './runtime';

interface VersionInfo {
  currentVersion: string;
  latestVersion: string;
  updateAvailable: boolean;
  storeUrl: string;
}

const ANDROID_PACKAGE = 'at.taxja.app';
const IOS_APP_ID = ''; // Fill in after App Store submission
const CURRENT_VERSION = '1.0.0';

const getStoreUrl = (): string => {
  const platform = Capacitor.getPlatform();
  if (platform === 'android') {
    return `https://play.google.com/store/apps/details?id=${ANDROID_PACKAGE}`;
  }
  if (platform === 'ios' && IOS_APP_ID) {
    return `https://apps.apple.com/app/id${IOS_APP_ID}`;
  }
  return '';
};

/**
 * Check for app updates by calling the backend version endpoint.
 * The backend should expose a simple GET /api/v1/app/version that returns
 * { "latest_version": "1.1.0", "min_version": "1.0.0", "force_update": false }
 *
 * Until that endpoint exists this function returns no update available.
 */
export const checkForUpdate = async (
  apiBaseUrl: string
): Promise<VersionInfo> => {
  const result: VersionInfo = {
    currentVersion: CURRENT_VERSION,
    latestVersion: CURRENT_VERSION,
    updateAvailable: false,
    storeUrl: getStoreUrl(),
  };

  if (!isNativeApp()) return result;

  try {
    const response = await fetch(`${apiBaseUrl}/app/version`, {
      headers: { 'X-App-Version': CURRENT_VERSION },
    });

    if (response.ok) {
      const data = await response.json();
      result.latestVersion = data.latest_version ?? CURRENT_VERSION;
      result.updateAvailable = result.latestVersion !== CURRENT_VERSION;
    }
  } catch {
    // Network error — skip update check silently
  }

  return result;
};

export const openStoreListing = async (): Promise<void> => {
  const url = getStoreUrl();
  if (!url) return;

  if (isNativeApp()) {
    await Browser.open({ url });
  } else {
    window.open(url, '_blank');
  }
};
