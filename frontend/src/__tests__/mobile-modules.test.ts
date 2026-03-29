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

describe('mobile/notifications', () => {
  it('returns null for push permission on web', async () => {
    const { requestPushPermission } = await import('../mobile/notifications');
    const token = await requestPushPermission();
    expect(token).toBeNull();
  });
});
