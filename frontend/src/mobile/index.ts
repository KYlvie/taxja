// Core runtime
export { isNativeApp, getApiBaseUrl, initializeMobileRuntime } from './runtime';

// File operations (camera, picker, share)
export {
  pickNativeFiles,
  pickNativeSingleFile,
  capturePhotoAsFile,
  saveBlobWithNativeShare,
  supportsNativeFileActions,
} from './files';

// Push notifications
export {
  requestPushPermission,
  initializePushNotifications,
  setNotificationTapHandler,
  getDeliveredNotifications,
  clearAllNotifications,
} from './notifications';

// Network monitoring
export {
  getNetworkStatus,
  isOnline,
  onNetworkChange,
  initializeNetworkMonitor,
} from './network';

// Secure storage
export { secureSet, secureGet, secureRemove, secureClear } from './storage';

// Biometric authentication
export { isBiometricAvailable, requestBiometricVerification } from './biometric';

// Haptic feedback
export {
  hapticsImpact,
  hapticsNotification,
  hapticsVibrate,
  ImpactStyle,
  NotificationType,
} from './haptics';

// App update
export { checkForUpdate, openStoreListing } from './app-update';

// React hooks
export { useNetworkStatus } from './useNetworkStatus';
