import { Preferences } from '@capacitor/preferences';
import { isNativeApp } from './runtime';

/**
 * Secure key-value storage using Capacitor Preferences.
 *
 * On native platforms this uses SharedPreferences (Android) / UserDefaults (iOS)
 * which are sandboxed to the app. For truly sensitive secrets (tokens, keys)
 * consider adding `@nicolo-ribaudo/capacitor-secure-storage` which uses
 * Android Keystore / iOS Keychain. This module provides a safe default that
 * is already better than localStorage in a WebView.
 *
 * On web it falls back to localStorage transparently.
 */

const PREFIX = 'taxja_';

export const secureSet = async (key: string, value: string): Promise<void> => {
  if (isNativeApp()) {
    await Preferences.set({ key: PREFIX + key, value });
  } else {
    localStorage.setItem(PREFIX + key, value);
  }
};

export const secureGet = async (key: string): Promise<string | null> => {
  if (isNativeApp()) {
    const result = await Preferences.get({ key: PREFIX + key });
    return result.value;
  }
  return localStorage.getItem(PREFIX + key);
};

export const secureRemove = async (key: string): Promise<void> => {
  if (isNativeApp()) {
    await Preferences.remove({ key: PREFIX + key });
  } else {
    localStorage.removeItem(PREFIX + key);
  }
};

export const secureClear = async (): Promise<void> => {
  if (isNativeApp()) {
    await Preferences.clear();
  } else {
    // Only clear taxja-prefixed keys
    const keysToRemove: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k?.startsWith(PREFIX)) keysToRemove.push(k);
    }
    keysToRemove.forEach((k) => localStorage.removeItem(k));
  }
};
