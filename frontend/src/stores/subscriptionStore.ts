/**
 * Subscription Store (Zustand)
 * 
 * Manages subscription state, plan information, and usage tracking.
 * Per Requirements 7.3, 7.5: Centralized subscription state management.
 */

import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import api from '../services/api';

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

export interface CreditBalance {
  plan_balance: number;
  topup_balance: number;
  total_balance: number;
  available_without_overage: number;
  monthly_credits: number;
  overage_enabled: boolean;
  overage_credits_used: number;
  overage_price_per_credit: number | null;
  estimated_overage_cost: number;
  has_unpaid_overage: boolean;
  reset_date: string | null;
}

export interface CreditLedgerEntry {
  id: number;
  operation: string;
  operation_detail: string | null;
  status: string;
  credit_amount: number;
  source: string;
  plan_balance_after: number;
  topup_balance_after: number;
  is_overage: boolean;
  overage_portion: number;
  context_type: string | null;
  context_id: number | null;
  reason: string | null;
  created_at: string;
}

export interface CreditCost {
  operation: string;
  credit_cost: number;
  description: string | null;
}

export interface TopupPackage {
  id: number;
  name: string;
  credits: number;
  price: number;
  stripe_price_id: string | null;
  is_active: boolean;
}

export interface CreditEstimate {
  operation: string;
  cost: number;
  sufficient: boolean;
  sufficient_without_overage: boolean;
  would_use_overage: boolean;
}

interface SubscriptionState {
  // State
  currentPlan: Plan | null;
  subscription: Subscription | null;
  usage: UsageSummary | null;
  loading: boolean;
  error: string | null;
  
  // Credit state
  creditBalance: CreditBalance | null;
  creditHistory: CreditLedgerEntry[];
  creditCosts: CreditCost[];
  topupPackages: TopupPackage[];
  creditLoading: boolean;
  
  // Actions
  fetchSubscription: () => Promise<void>;
  fetchUsage: () => Promise<void>;
  createCheckoutSession: (
    planId: number,
    billingCycle: 'monthly' | 'yearly',
    successUrl: string,
    cancelUrl: string
  ) => Promise<{ session_id: string; url: string }>;
  syncCheckoutSession: (sessionId: string) => Promise<void>;
  upgradeSubscription: (planId: number, billingCycle: 'monthly' | 'yearly') => Promise<void>;
  downgradeSubscription: (planId: number) => Promise<void>;
  cancelSubscription: () => Promise<void>;
  reactivateSubscription: () => Promise<void>;
  openCustomerPortal: (returnUrl?: string) => Promise<void>;
  clearError: () => void;
  reset: () => void;
  
  // Credit actions
  fetchCreditBalance: () => Promise<void>;
  fetchCreditHistory: (limit?: number, offset?: number) => Promise<void>;
  fetchCreditCosts: () => Promise<void>;
  createTopupCheckout: (packageId: number, successUrl: string, cancelUrl: string) => Promise<{ session_id: string; url: string }>;
  toggleOverage: (enabled: boolean) => Promise<void>;
  fetchOverageEstimate: () => Promise<number>;
  estimateCost: (operation: string, quantity?: number) => Promise<CreditEstimate>;
}

// Helper function for API calls
const normalizeHeaders = (headers?: HeadersInit): Record<string, string> | undefined => {
  if (!headers) {
    return undefined;
  }

  if (headers instanceof Headers) {
    return Object.fromEntries(headers.entries());
  }

  if (Array.isArray(headers)) {
    return Object.fromEntries(headers);
  }

  return headers;
};

const parseRequestBody = (body?: BodyInit | null, headers?: Record<string, string>) => {
  if (body === undefined || body === null) {
    return undefined;
  }

  if (typeof body !== 'string') {
    return body;
  }

  const contentType = headers?.['Content-Type'] || headers?.['content-type'] || 'application/json';
  if (!contentType.includes('application/json')) {
    return body;
  }

  try {
    return JSON.parse(body);
  } catch {
    return body;
  }
};

const apiCall = async (endpoint: string, options: RequestInit = {}) => {
  const headers = normalizeHeaders(options.headers);
  const response = await api.request({
    url: endpoint,
    method: options.method || 'GET',
    headers,
    data: parseRequestBody(options.body, headers),
  });

  return response.data;
};

export const useSubscriptionStore = create<SubscriptionState>()(
  devtools(
    (set) => ({
      // Initial state
      currentPlan: null,
      subscription: null,
      usage: null,
      loading: false,
      error: null,
      
      // Credit state
      creditBalance: null,
      creditHistory: [],
      creditCosts: [],
      topupPackages: [],
      creditLoading: false,
      
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

      syncCheckoutSession: async (sessionId) => {
        set({ loading: true, error: null });

        try {
          const subscription = await apiCall(
            `/subscriptions/checkout/sync?session_id=${encodeURIComponent(sessionId)}`,
            { method: 'POST' }
          );

          const plans = await apiCall('/subscriptions/plans');
          const currentPlan = plans.find((p: Plan) => p.id === subscription.plan_id);

          set({
            subscription,
            currentPlan,
            creditBalance: subscription.credit_balance ?? null,
            loading: false,
          });
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Failed to sync checkout session';
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
      
      // Open Stripe Customer Portal
      openCustomerPortal: async (returnUrl?: string) => {
        set({ loading: true, error: null });
        
        try {
          const url = returnUrl || `${window.location.origin}/pricing`;
          const result = await apiCall(
            `/subscriptions/customer-portal?return_url=${encodeURIComponent(url)}`,
            { method: 'POST' }
          );
          window.location.href = result.url;
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Failed to open customer portal';
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
        creditBalance: null,
        creditHistory: [],
        creditCosts: [],
        topupPackages: [],
        creditLoading: false,
      }),

      // Credit actions
      fetchCreditBalance: async () => {
        set({ creditLoading: true });
        try {
          const balance = await apiCall('/credits/balance');
          set({ creditBalance: balance, creditLoading: false });
        } catch (error) {
          set({ creditLoading: false });
        }
      },

      fetchCreditHistory: async (limit = 50, offset = 0) => {
        set({ creditLoading: true });
        try {
          const history = await apiCall(`/credits/history?limit=${limit}&offset=${offset}`);
          set({ creditHistory: history, creditLoading: false });
        } catch (error) {
          set({ creditLoading: false });
        }
      },

      fetchCreditCosts: async () => {
        try {
          const costs = await apiCall('/credits/costs');
          set({ creditCosts: costs });
        } catch (error) {
          // silently fail
        }
      },

      createTopupCheckout: async (packageId, successUrl, cancelUrl) => {
        set({ creditLoading: true });
        try {
          const result = await apiCall('/credits/topup', {
            method: 'POST',
            body: JSON.stringify({
              package_id: packageId,
              success_url: successUrl,
              cancel_url: cancelUrl,
            }),
          });
          set({ creditLoading: false });
          return result;
        } catch (error) {
          set({ creditLoading: false });
          throw error;
        }
      },

      toggleOverage: async (enabled) => {
        set({ creditLoading: true });
        try {
          await apiCall('/credits/overage', {
            method: 'PUT',
            body: JSON.stringify({ enabled }),
          });
          // Refresh balance after toggle
          const balance = await apiCall('/credits/balance');
          set({ creditBalance: balance, creditLoading: false });
        } catch (error) {
          set({ creditLoading: false });
          throw error;
        }
      },

      fetchOverageEstimate: async () => {
        try {
          const result = await apiCall('/credits/overage/estimate');
          return result.estimated_cost || 0;
        } catch {
          return 0;
        }
      },

      estimateCost: async (operation, quantity = 1) => {
        const result = await apiCall('/credits/estimate', {
          method: 'POST',
          body: JSON.stringify({ operation, quantity }),
        });
        return result;
      },
    }),
    { name: 'SubscriptionStore' }
  )
);
