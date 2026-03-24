const SELF_HANDLED_AUTH_PATHS = [
  '/auth/login',
  '/auth/register',
  '/auth/google',
  '/auth/verify-email',
  '/auth/resend-verification',
  '/auth/forgot-password',
  '/auth/reset-password',
  '/auth/refresh',
  '/auth/logout',
];

export function isSelfHandledAuthRequest(url?: string | null): boolean {
  if (!url) {
    return false;
  }

  return (
    url.includes('/auth/2fa/')
    || SELF_HANDLED_AUTH_PATHS.some((path) => url.includes(path))
  );
}
