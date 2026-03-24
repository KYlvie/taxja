export const getApiErrorMessage = (
  error: any,
  fallback = 'An error occurred'
): string => {
  const responseData = error?.response?.data;

  if (typeof responseData?.detail === 'string' && responseData.detail.trim()) {
    return responseData.detail;
  }

  if (typeof responseData?.error?.message === 'string' && responseData.error.message.trim()) {
    return responseData.error.message;
  }

  if (typeof error?.message === 'string' && error.message.trim()) {
    return error.message;
  }

  return fallback;
};

/**
 * Extract feature gate plan requirement from an API error.
 * Returns the required plan name (e.g. "pro") or null if not a feature gate error.
 */
export const getFeatureGatePlan = (error: any): string | null => {
  const detail = error?.response?.data?.detail;
  // Object format: { error: "feature_not_available", required_plan: "pro", ... }
  if (detail && typeof detail === 'object') {
    if (detail.error === 'feature_not_available' || detail.error === 'insufficient_plan' || detail.error === 'plan_required') {
      return detail.required_plan || 'pro';
    }
  }
  // String format fallback: "This feature requires Pro plan or higher"
  if (typeof detail === 'string') {
    const match = detail.match(/requires\s+(\w+)\s+plan/i);
    if (match) return match[1].toLowerCase();
  }
  return null;
};

const LINE_ITEM_RECONCILIATION_REGEX = /Line items do not reconcile with the parent amount\. Expected\s+([-0-9.,]+), reconstructed\s+([-0-9.,]+)\./i;

const parseApiNumber = (value: string | undefined): number | null => {
  if (!value) return null;
  const normalized = value.replace(/,/g, '');
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : null;
};

export const getLineItemReconciliationError = (
  error: any
): { expected: number | null; reconstructed: number | null } | null => {
  const message = getApiErrorMessage(error, '');
  if (!message) return null;

  const match = message.match(LINE_ITEM_RECONCILIATION_REGEX);
  if (!match) return null;

  return {
    expected: parseApiNumber(match[1]),
    reconstructed: parseApiNumber(match[2]),
  };
};
