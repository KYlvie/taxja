/**
 * Subscription Store (Zustand)
 * 
 * Manages subscription state, plan information, and usage tracking.
 * Per Requirements 7.3, 7.5: Centralized subscription state management.
 */

import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { useAuthStore } from './authStore';

// Types
export interface Plan {
  id: number;
  plan_type: 'free' | 'plus' | 'pro';
  name: string;
  monthly_price: number;
  yearly_price: number;
  features: Record<string, boolean>;
  quotas: Record<string, number>;
  created_at: string;
  updated_at: string;
}

export interface Subscription {
  id: number;
  user_id: number;
  plan_id: number;
  status: 'active' | 'past_due' | 'canceled' | 'trialing';
  billing_cycle: 'monthly' | 'yearly' | null;
  stripe_subscription_id: string | null;
  stripe_customer_id: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  created_at: string;
  updated_at: string;
}

export interface UsageData {
  resource_type: string;
  current: number;
  limit: number;
  percentage: number;
  is_warning: boolean;
  is_exceeded: boolean;
  reset_date: string;
}

export interface UsageSummary {
  transactions: UsageData;
  ocr_scans: UsageData;
  ai_conversations: UsageData;
}

interface SubscriptionState {
  // State
  currentPlan: Plan | null;
  subscription: Subscription | null;
  usage: UsageSummary | null;
  loading: boolean;
  error: string | null;
  
  // Actions
  fetchSubscription: () => Promise<void>;
  fetchUsage: () => Promise<void>;
  createCheckoutSession: (
    planId: number,
    billingCycle: 'monthly' | 'yearly',
    successUrl: string,
    cancelUrl: string
  ) => Promise<{ session_id: string; url: string }>;
  upgradeSubscription: (planId: number, billingCycle: 'monthly' | 'yearly') => Promise<void>;
  downgradeSubscription: (planId: number) => Promise<void>;
  cancelSubscription: () => Promise<void>;
  reactivateSubscription: () => Promise<void>;
  clearError: () => void;
  reset: () => void;
}

// API base URL
const API_BASE = '/api/v1';

// Helper function to get auth token from Zustand auth store
const getAuthToken = (): string | null => {
  return useAuthStore.getState().token;
};

// Helper function for API calls
const apiCall = async (endpoint: string, options: RequestInit = {}) => {
  const token = getAuthToken();
  
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...options.headers,
    },
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || error.message || 'Request failed');
  }
  
  return response.json();
};

export const useSubscriptionStore = create<SubscriptionState>()(
  devtools(
    (set, get) => ({
      // Initial state
      currentPlan: null,
      subscription: null,
      usage: null,
      loading: false,
      error: null,
      
      // Fetch current subscription
      fetchSubscription: async () => {
        set({ loading: true, error: null });
        
        try {
          const subscription = await apiCall('/subscriptions/current');
          
          // Fetch the plan details
          const plans = await apiCall('/subscriptions/plans');
          const currentPlan = plans.find((p: Plan) => p.id === subscription.plan_id);
          
          set({
            subscription,
            currentPlan,
            loading: false,
          });
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Failed to fetch subscription';
          set({
            error: errorMessage,
            loading: false,
          });
        }
      },
      
      // Fetch usage summary
      fetchUsage: async () => {
        set({ loading: true, error: null });
        
        try {
          const usage = await apiCall('/usage/summary');
          
          set({
            usage,
            loading: false,
          });
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Failed to fetch usage';
          set({
            error: errorMessage,
            loading: false,
          });
        }
      },
      
      // Create Stripe checkout session
      createCheckoutSession: async (planId, billingCycle, successUrl, cancelUrl) => {
        set({ loading: true, error: null });
        
        try {
          const result = await apiCall('/subscriptions/checkout', {
            method: 'POST',
            body: JSON.stringify({
              plan_id: planId,
              billing_cycle: billingCycle,
              success_url: successUrl,
              cancel_url: cancelUrl,
            }),
          });
          
          set({ loading: false });
          return result;
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Failed to create checkout session';
          set({
            error: errorMessage,
            loading: false,
          });
          throw error;
        }
      },
      
      // Upgrade subscription
      upgradeSubscription: async (planId, billingCycle) => {
        set({ loading: true, error: null });
        
        try {
          const subscription = await apiCall(
            `/subscriptions/upgrade?plan_id=${planId}&billing_cycle=${billingCycle}`,
            { method: 'POST' }
          );
          
          // Fetch updated plan details
          const plans = await apiCall('/subscriptions/plans');
          const currentPlan = plans.find((p: Plan) => p.id === subscription.plan_id);
          
          set({
            subscription,
            currentPlan,
            loading: false,
          });
          
          // Refresh usage after upgrade
          get().fetchUsage();
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Failed to upgrade subscription';
          set({
            error: errorMessage,
            loading: false,
          });
          throw error;
        }
      },
      
      // Downgrade subscription
      downgradeSubscription: async (planId) => {
        set({ loading: true, error: null });
        
        try {
          const subscription = await apiCall(
            `/subscriptions/downgrade?plan_id=${planId}`,
            { method: 'POST' }
          );
          
          set({
            subscription,
            loading: false,
          });
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Failed to downgrade subscription';
          set({
            error: errorMessage,
            loading: false,
          });
          throw error;
        }
      },
      
      // Cancel subscription
      cancelSubscription: async () => {
        set({ loading: true, error: null });
        
        try {
          const subscription = await apiCall('/subscriptions/cancel', {
            method: 'POST',
          });
          
          set({
            subscription,
            loading: false,
          });
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Failed to cancel subscription';
          set({
            error: errorMessage,
            loading: false,
          });
          throw error;
        }
      },
      
      // Reactivate subscription
      reactivateSubscription: async () => {
        set({ loading: true, error: null });
        
        try {
          const subscription = await apiCall('/subscriptions/reactivate', {
            method: 'POST',
          });
          
          set({
            subscription,
            loading: false,
          });
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Failed to reactivate subscription';
          set({
            error: errorMessage,
            loading: false,
          });
          throw error;
        }
      },
      
      // Clear error
      clearError: () => set({ error: null }),
      
      // Reset store
      reset: () => set({
        currentPlan: null,
        subscription: null,
        usage: null,
        loading: false,
        error: null,
      }),
    }),
    { name: 'SubscriptionStore' }
  )
);
