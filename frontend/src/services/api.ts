import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { useAuthStore } from '../stores/authStore';
import { useSubscriptionStore } from '../stores/subscriptionStore';
import { getApiBaseUrl } from '../mobile/runtime';
import { normalizeLanguage } from '../utils/locale';

// Create axios instance with base configuration
const api = axios.create({
  baseURL: getApiBaseUrl(),
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = useAuthStore.getState().token;
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
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

// Normalize error.response.data.detail to always be a string.
// Backend sometimes returns structured objects (e.g. feature gate, quota errors)
// which crash React if rendered directly as children.
function normalizeErrorDetail(data: any): void {
  if (!data || typeof data.detail !== 'object' || data.detail === null) return;
  // Preserve the original structured detail for programmatic access
  data._detail_obj = data.detail;
  // Flatten to a human-readable string for UI rendering
  data.detail = data.detail.message || data.detail.error || JSON.stringify(data.detail);
}

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    if (response.headers['x-credits-remaining'] !== undefined) {
      void useSubscriptionStore.getState().fetchCreditBalance();
    }
    return response;
  },
  (error: AxiosError) => {
    if (error.response) {
      // Normalize detail to string BEFORE any component reads it
      if (error.response.data) {
        normalizeErrorDetail(error.response.data);
      }

      // Handle specific error codes
      switch (error.response.status) {
        case 401:
          // Unauthorized - clear auth and redirect to login
          useAuthStore.getState().logout();
          window.location.href = '/login';
          break;
        case 403: {
          // Check if this is a feature gate response
          const detailObj = (error.response.data as any)?._detail_obj;
          if (detailObj?.error === 'feature_not_available' || detailObj?.error === 'insufficient_plan') {
            console.warn(`Feature requires ${detailObj.required_plan} plan`);
          } else {
            console.error('Access forbidden');
          }
          break;
        }
        case 429: {
          // Quota exceeded
          const quotaObj = (error.response.data as any)?._detail_obj;
          if (quotaObj?.error === 'quota_exceeded') {
            console.warn(`Quota exceeded for ${quotaObj.resource_type}: ${quotaObj.current}/${quotaObj.limit}`);
          }
          break;
        }
        case 404:
          // Not found
          console.error('Resource not found');
          break;
        case 500:
          // Server error
          console.error('Server error occurred');
          break;
        default:
          console.error('An error occurred:', error.response.data);
      }
    } else if (error.request) {
      // Network error
      console.error('Network error - please check your connection');
    } else {
      console.error('Error:', error.message);
    }
    return Promise.reject(error);
  }
);

export default api;
