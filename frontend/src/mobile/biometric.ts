import { isNativeApp } from './runtime';

/**
 * Biometric authentication using the Web Credentials API on native platforms.
 * Capacitor's WebView supports the Web Authentication / Credential Management API
 * which delegates to the OS biometric prompt (fingerprint / Face ID) on both
 * Android and iOS without requiring an extra native plugin.
 *
 * For a full FIDO2/WebAuthn flow a dedicated plugin like
 * `@nicolo-ribaudo/capacitor-native-biometric` can be added later.
 * This module provides a lightweight "lock screen" guard that simply asks the
 * OS to verify the device owner before granting access.
 */

export const isBiometricAvailable = async (): Promise<boolean> => {
  if (!isNativeApp()) return false;

  try {
    // PublicKeyCredential is available in modern WebViews
    if (typeof PublicKeyCredential !== 'undefined') {
      const available =
        await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
      return available;
    }
  } catch {
    // not supported
  }

  return false;
};

/**
 * Prompt the user for biometric verification.
 * Returns true if the user passed, false otherwise.
 *
 * NOTE: This is a simplified check. For production FIDO2 flows you would
 * create and verify a credential with your backend. This version only
 * checks whether the platform authenticator is reachable, which is enough
 * for a "confirm identity" gate.
 */
export const requestBiometricVerification = async (): Promise<boolean> => {
  if (!isNativeApp()) return true; // no-op on web

  try {
    const challenge = crypto.getRandomValues(new Uint8Array(32));
    const userId = crypto.getRandomValues(new Uint8Array(16));

    const credential = await navigator.credentials.create({
      publicKey: {
        challenge,
        rp: { name: 'Taxja', id: window.location.hostname },
        user: {
          id: userId,
          name: 'taxja-user',
          displayName: 'Taxja User',
        },
        pubKeyCredParams: [{ alg: -7, type: 'public-key' }],
        authenticatorSelection: {
          authenticatorAttachment: 'platform',
          userVerification: 'required',
        },
        timeout: 60_000,
      },
    });

    return credential !== null;
  } catch {
    return false;
  }
};
