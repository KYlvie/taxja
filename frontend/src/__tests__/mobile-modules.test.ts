import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock Capacitor core before importing modules
vi.mock('@capacitor/core', () => ({
  Capacitor: {
    isNativePlatform: vi.fn(() => false),
    getPlatform: vi.fn(() => 'web'),
    convertFileSrc: vi.fn((path: string) => path),
  },
}));

vi.mock('@capacitor/push-notifications', () => ({
  PushNotifications: {
    requestPermissions: vi.fn(),
    checkPermissions: vi.fn(() => ({ receive: 'denied' })),
    register: vi.fn(),
    addListener: vi.fn(),
    getDeliveredNotifications: vi.fn(() => ({ notifications: [] })),
    removeAllDeliveredNotifications: vi.fn(),
  },
}));

vi.mock('@capacitor/network', () => ({
  Network: {
    getStatus: vi.fn(() => ({ connected: true, connectionType: 'wifi' })),
    addListener: vi.fn(),
  },
}));

vi.mock('@capacitor/preferences', () => ({
  Preferences: {
    set: vi.fn(),
    get: vi.fn(() => ({ value: null })),
    remove: vi.fn(),
    clear: vi.fn(),
  },
}));

vi.mock('@capacitor/haptics', () => ({
  Haptics: {
    impact: vi.fn(),
    notification: vi.fn(),
    vibrate: vi.fn(),
  },
  ImpactStyle: { Heavy: 'HEAVY', Medium: 'MEDIUM', Light: 'LIGHT' },
  NotificationType: { Success: 'SUCCESS', Warning: 'WARNING', Error: 'ERROR' },
}));

vi.mock('@capacitor/browser', () => ({
  Browser: {
    open: vi.fn(),
  },
}));

vi.mock('@capacitor/app', () => ({
  App: {
    addListener: vi.fn(),
    exitApp: vi.fn(),
  },
}));

vi.mock('@capacitor/status-bar', () => ({
  StatusBar: {
    setStyle: vi.fn(),
    setOverlaysWebView: vi.fn(),
  },
  Style: { Dark: 'DARK', Light: 'LIGHT' },
}));

vi.mock('@capacitor/camera', () => ({
  Camera: { getPhoto: vi.fn() },
  CameraResultType: { Uri: 'uri' },
  CameraSource: { Camera: 'CAMERA' },
}));

vi.mock('@capacitor/filesystem', () => ({
  Filesystem: { writeFile: vi.fn(() => ({ uri: 'file://test' })) },
  Directory: { Cache: 'CACHE' },
}));

vi.mock('@capacitor/share', () => ({
  Share: {
    canShare: vi.fn(() => ({ value: false })),
    share: vi.fn(),
  },
}));

vi.mock('@capawesome/capacitor-file-picker', () => ({
  FilePicker: { pickFiles: vi.fn(() => ({ files: [] })) },
}));

// ─── Tests ───

describe('mobile/network', () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it('initializes with browser online/offline on web', async () => {
    const { initializeNetworkMonitor, isOnline } = await import('../mobile/network');
    await initializeNetworkMonitor();
    // navigator.onLine is true in jsdom
    expect(isOnline()).toBe(true);
  });

  it('notifies listeners on network change', async () => {
    const { initializeNetworkMonitor, onNetworkChange } = await import('../mobile/network');
    await initializeNetworkMonitor();

    const handler = vi.fn();
    const unsubscribe = onNetworkChange(handler);

    // Simulate going offline
    window.dispatchEvent(new Event('offline'));
    expect(handler).toHaveBeenCalledWith(
      expect.objectContaining({ connected: false })
    );

    unsubscribe();
    handler.mockClear();

    // After unsubscribe, handler should not be called
    window.dispatchEvent(new Event('online'));
    expect(handler).not.toHaveBeenCalled();
  });
});

describe('mobile/storage', () => {
  it('uses localStorage on web', async () => {
    const { secureSet, secureGet, secureRemove } = await import('../mobile/storage');

    await secureSet('token', 'abc123');
    expect(localStorage.getItem('taxja_token')).toBe('abc123');

    const value = await secureGet('token');
    expect(value).toBe('abc123');

    await secureRemove('token');
    expect(localStorage.getItem('taxja_token')).toBeNull();
  });

  it('secureClear only removes taxja-prefixed keys', async () => {
    const { secureClear } = await import('../mobile/storage');

    localStorage.setItem('taxja_a', '1');
    localStorage.setItem('taxja_b', '2');
    localStorage.setItem('other_key', '3');

    await secureClear();

    expect(localStorage.getItem('taxja_a')).toBeNull();
    expect(localStorage.getItem('taxja_b')).toBeNull();
    expect(localStorage.getItem('other_key')).toBe('3');

    localStorage.removeItem('other_key');
  });
});

describe('mobile/notifications', () => {
  it('returns null for push permission on web', async () => {
    const { requestPushPermission } = await import('../mobile/notifications');
    const token = await requestPushPermission();
    expect(token).toBeNull();
  });
});

describe('mobile/haptics', () => {
  it('is a no-op on web', async () => {
    const { hapticsImpact, hapticsNotification, hapticsVibrate } = await import(
      '../mobile/haptics'
    );
    // Should not throw
    await hapticsImpact();
    await hapticsNotification();
    await hapticsVibrate();
  });
});

describe('mobile/biometric', () => {
  it('returns false for availability on web', async () => {
    const { isBiometricAvailable } = await import('../mobile/biometric');
    const available = await isBiometricAvailable();
    expect(available).toBe(false);
  });

  it('returns true for verification on web (no-op passthrough)', async () => {
    const { requestBiometricVerification } = await import('../mobile/biometric');
    const result = await requestBiometricVerification();
    expect(result).toBe(true);
  });
});

describe('mobile/app-update', () => {
  it('returns no update on web', async () => {
    const { checkForUpdate } = await import('../mobile/app-update');
    const info = await checkForUpdate('/api/v1');
    expect(info.updateAvailable).toBe(false);
    expect(info.currentVersion).toBe('1.0.0');
  });
});
