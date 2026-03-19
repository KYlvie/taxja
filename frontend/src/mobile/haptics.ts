import { Haptics, ImpactStyle, NotificationType } from '@capacitor/haptics';
import { isNativeApp } from './runtime';

export const hapticsImpact = async (style: ImpactStyle = ImpactStyle.Medium): Promise<void> => {
  if (!isNativeApp()) return;
  try {
    await Haptics.impact({ style });
  } catch {
    // silently ignore on unsupported devices
  }
};

export const hapticsNotification = async (
  type: NotificationType = NotificationType.Success
): Promise<void> => {
  if (!isNativeApp()) return;
  try {
    await Haptics.notification({ type });
  } catch {
    // silently ignore
  }
};

export const hapticsVibrate = async (duration = 300): Promise<void> => {
  if (!isNativeApp()) return;
  try {
    await Haptics.vibrate({ duration });
  } catch {
    // silently ignore
  }
};

export { ImpactStyle, NotificationType };
