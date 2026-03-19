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
