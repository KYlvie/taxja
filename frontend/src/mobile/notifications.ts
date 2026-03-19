import { PushNotifications, type Token, type ActionPerformed } from '@capacitor/push-notifications';
import { isNativeApp } from './runtime';

export type NotificationHandler = (notification: ActionPerformed) => void;

let onNotificationTap: NotificationHandler | null = null;

export const setNotificationTapHandler = (handler: NotificationHandler): void => {
  onNotificationTap = handler;
};

export const requestPushPermission = async (): Promise<string | null> => {
  if (!isNativeApp()) return null;

  const permission = await PushNotifications.requestPermissions();
  if (permission.receive !== 'granted') return null;

  await PushNotifications.register();

  return new Promise<string | null>((resolve) => {
    const timeout = setTimeout(() => resolve(null), 10_000);

    void PushNotifications.addListener('registration', (token: Token) => {
      clearTimeout(timeout);
      resolve(token.value);
    });

    void PushNotifications.addListener('registrationError', () => {
      clearTimeout(timeout);
      resolve(null);
    });
  });
};

export const initializePushNotifications = async (): Promise<void> => {
  if (!isNativeApp()) return;

  const permission = await PushNotifications.checkPermissions();
  if (permission.receive !== 'granted') return;

  await PushNotifications.addListener('pushNotificationActionPerformed', (action) => {
    onNotificationTap?.(action);
  });
};

export const getDeliveredNotifications = async () => {
  if (!isNativeApp()) return [];
  const result = await PushNotifications.getDeliveredNotifications();
  return result.notifications;
};

export const clearAllNotifications = async (): Promise<void> => {
  if (!isNativeApp()) return;
  await PushNotifications.removeAllDeliveredNotifications();
};
