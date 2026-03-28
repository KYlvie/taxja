import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { useAuthStore } from '../stores/authStore';
import { useSubscriptionStore } from '../stores/subscriptionStore';
import { getApiBaseUrl, isNativeApp } from '../mobile/runtime';
import { normalizeLanguage } from '../utils/locale';
import { isSelfHandledAuthRequest } from './authRequestPolicy';

// ---------------------------------------------------------------------------
// CSRF token — kept in-memory only (not localStorage)
// ---------------------------------------------------------------------------
let csrfToken: string | null = null;

export const setCsrfToken = (token: string | null) => {
  csrfToken = token;
};

// ---------------------------------------------------------------------------
// Mutex to prevent concurrent refresh calls
// ---------------------------------------------------------------------------
let isRefreshing = false;
let refreshSubscribers: Array<(token: string) => void> = [];

function subscribeTokenRefresh(cb: (token: string) => void) {
  refreshSubscribers.push(cb);
}

function onRefreshed(newToken: string) {
  refreshSubscribers.forEach((cb) => cb(newToken));
  refreshSubscribers = [];
}

// ---------------------------------------------------------------------------
// Debounced credit balance refresh — collapses rapid-fire header triggers
// ---------------------------------------------------------------------------
let _creditRefreshTimer: ReturnType<typeof setTimeout> | null = null;

function debouncedCreditRefresh() {
  if (_creditRefreshTimer) return;           // already scheduled
  _creditRefreshTimer = setTimeout(() => {
    _creditRefreshTimer = null;
    void useSubscriptionStore.getState().fetchCreditBalance();
  }, 500);
}

// ---------------------------------------------------------------------------
// Axios instance
// ---------------------------------------------------------------------------
const api = axios.create({
  baseURL: getApiBaseUrl(),
  timeout: 30000,
  withCredentials: true, // Send/receive HttpOnly cookies
  headers: {
    'Content-Type': 'application/json',
  },
});

const MUTATING_METHODS = ['post', 'put', 'delete', 'patch'];

// ---------------------------------------------------------------------------
// Request interceptor
// ---------------------------------------------------------------------------
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // On native (Capacitor), always send Bearer token — cookies don't work reliably
    if (isNativeApp()) {
      const token = useAuthStore.getState().token;
      if (token && config.headers) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    // On web, cookies are sent automatically via withCredentials.
    // We still set the Bearer header if token is available (dual-mode compat).
    else {
      const token = useAuthStore.getState().token;
      if (token && config.headers) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }

    // Attach CSRF token for mutating requests (web only; harmless on native)
    if (
      csrfToken &&
      config.headers &&
      MUTATING_METHODS.includes((config.method || '').toLowerCase())
    ) {
      config.headers['X-CSRF-Token'] = csrfToken;
    }

    // Accept-Language
    if (config.headers) {
      config.headers['Accept-Language'] = normalizeLanguage(
        localStorage.getItem('language') || navigator.language
      );
    }
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

// ---------------------------------------------------------------------------
// Normalize error detail
// ---------------------------------------------------------------------------
function normalizeErrorDetail(data: any): void {
  if (!data) return;

  if (typeof data.detail === 'object' && data.detail !== null) {
    data._detail_obj = data.detail;
    data.detail = data.detail.message || data.detail.error || JSON.stringify(data.detail);
    return;
  }

  if (
    (!data.detail || typeof data.detail !== 'string')
    && typeof data.error === 'object'
    && data.error !== null
  ) {
    data._detail_obj = data.error;
    data.detail = data.error.message || data.error.error || JSON.stringify(data.error);
  }
}

// ---------------------------------------------------------------------------
// Response interceptor — captures CSRF token + silent refresh on 401
// ---------------------------------------------------------------------------
api.interceptors.response.use(
  (response) => {
    // Capture CSRF token from every response that provides one
    const newCsrf = response.headers['x-csrf-token'];
    if (newCsrf) {
      setCsrfToken(newCsrf);
    }

    // Update credit display when a credit-consuming endpoint responds.
    // Skip /credits/ URLs to avoid a fetch→response→fetch infinite loop,
    // and debounce so rapid-fire responses don't flood the balance endpoint.
    const reqUrl = response.config.url || '';
    if (
      response.headers['x-credits-remaining'] !== undefined &&
      !reqUrl.includes('/credits/')
    ) {
      debouncedCreditRefresh();
    }
    return response;
  },
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    if (error.response) {
      // Normalize detail to string BEFORE any component reads it
      if (error.response.data) {
        normalizeErrorDetail(error.response.data);
      }

      // --- Silent refresh on 401 -------------------------------------------
      if (
        error.response.status === 401 &&
        originalRequest &&
        !originalRequest._retry &&
        // Let login/signup/password reset/Google auth flows handle their own errors.
        !isSelfHandledAuthRequest(originalRequest.url)
      ) {
        originalRequest._retry = true;

        if (!isRefreshing) {
          isRefreshing = true;

          try {
            const refreshResponse = await axios.post(
              `${getApiBaseUrl()}/auth/refresh`,
              {},
              { withCredentials: true, timeout: 10000 }
            );

            const newAccessToken: string = refreshResponse.data.access_token;

            // Capture CSRF from refresh response
            const refreshCsrf = refreshResponse.headers['x-csrf-token'];
            if (refreshCsrf) {
              setCsrfToken(refreshCsrf);
            }

            // Update store token (for native + Bearer fallback)
            useAuthStore.getState().login(
              useAuthStore.getState().user!,
              newAccessToken
            );

            isRefreshing = false;
            onRefreshed(newAccessToken);

            // Retry original request
            if (originalRequest.headers) {
              originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
              if (csrfToken && MUTATING_METHODS.includes((originalRequest.method || '').toLowerCase())) {
                originalRequest.headers['X-CSRF-Token'] = csrfToken;
              }
            }
            return api(originalRequest);
          } catch (refreshError) {
            isRefreshing = false;
            refreshSubscribers = [];

            // Refresh failed — force logout
            useAuthStore.getState().logout();
            window.location.href = '/login';
            return Promise.reject(refreshError);
          }
        } else {
          // Another refresh is in progress — queue this request
          return new Promise((resolve) => {
            subscribeTokenRefresh((newToken: string) => {
              if (originalRequest.headers) {
                originalRequest.headers.Authorization = `Bearer ${newToken}`;
                if (csrfToken && MUTATING_METHODS.includes((originalRequest.method || '').toLowerCase())) {
                  originalRequest.headers['X-CSRF-Token'] = csrfToken;
                }
              }
              resolve(api(originalRequest));
            });
          });
        }
      }

      // Handle other error codes
      switch (error.response.status) {
        case 401: {
          // If we reach here, refresh already failed or was skipped
          // Don't force-redirect for login/auth requests — let the component handle the error
          const reqUrl = originalRequest?.url || '';
          if (!isSelfHandledAuthRequest(reqUrl)) {
            useAuthStore.getState().logout();
            window.location.href = '/login';
          }
          break;
        }
        case 403: {
          const detailObj = (error.response.data as any)?._detail_obj;
          if (detailObj?.error === 'feature_not_available' || detailObj?.error === 'insufficient_plan') {
            console.warn(`Feature requires ${detailObj.required_plan} plan`);
          } else {
            console.error('Access forbidden');
          }
          break;
        }
        case 429: {
          const quotaObj = (error.response.data as any)?._detail_obj;
          if (quotaObj?.error === 'quota_exceeded') {
            console.warn(`Quota exceeded for ${quotaObj.resource_type}: ${quotaObj.current}/${quotaObj.limit}`);
          }
          break;
        }
        case 404:
          console.error('Resource not found');
          break;
        case 500:
          console.error('Server error occurred');
          break;
        default:
          console.error('An error occurred:', error.response.data);
      }
    } else if (error.request) {
      console.error('Network error - please check your connection');
    } else {
      console.error('Error:', error.message);
    }
    return Promise.reject(error);
  }
);

export default api;
