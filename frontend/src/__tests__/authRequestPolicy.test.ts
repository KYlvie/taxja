import { describe, expect, it } from 'vitest';
import { isSelfHandledAuthRequest } from '../services/authRequestPolicy';

describe('isSelfHandledAuthRequest', () => {
  it('treats Google sign-in as a self-handled auth flow', () => {
    expect(isSelfHandledAuthRequest('/auth/google')).toBe(true);
    expect(isSelfHandledAuthRequest('http://localhost:5173/api/v1/auth/google')).toBe(true);
  });

  it('treats other public auth routes as self-handled', () => {
    expect(isSelfHandledAuthRequest('/auth/login')).toBe(true);
    expect(isSelfHandledAuthRequest('/auth/register')).toBe(true);
    expect(isSelfHandledAuthRequest('/auth/forgot-password')).toBe(true);
    expect(isSelfHandledAuthRequest('/auth/reset-password')).toBe(true);
    expect(isSelfHandledAuthRequest('/auth/verify-email')).toBe(true);
    expect(isSelfHandledAuthRequest('/auth/resend-verification')).toBe(true);
    expect(isSelfHandledAuthRequest('/auth/refresh')).toBe(true);
    expect(isSelfHandledAuthRequest('/auth/2fa/verify')).toBe(true);
  });

  it('keeps normal protected API requests eligible for session recovery', () => {
    expect(isSelfHandledAuthRequest('/documents')).toBe(false);
    expect(isSelfHandledAuthRequest('/api/v1/transactions')).toBe(false);
    expect(isSelfHandledAuthRequest(undefined)).toBe(false);
  });
});
