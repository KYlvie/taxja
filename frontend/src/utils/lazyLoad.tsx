import { lazy, Suspense, ComponentType } from 'react';

// Loading fallback component
const LoadingFallback = () => (
  <div className="lazy-loading">
    <div className="lazy-loading-spinner">
      <div className="spinner"></div>
      <p>Loading...</p>
    </div>
    <style>{`
      .lazy-loading {
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: 400px;
        width: 100%;
      }
      
      .lazy-loading-spinner {
        text-align: center;
      }
      
      .spinner {
        width: 40px;
        height: 40px;
        margin: 0 auto 16px;
        border: 4px solid #f3f3f3;
        border-top: 4px solid #1976d2;
        border-radius: 50%;
        animation: spin 1s linear infinite;
      }
      
      @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
      }
      
      .lazy-loading-spinner p {
        color: #666;
        font-size: 14px;
      }
    `}</style>
  </div>
);

/**
 * Lazy load a component with automatic code splitting
 * Includes retry logic for failed chunk loads
 */
export const lazyLoad = <T extends ComponentType<any>>(
  importFunc: () => Promise<{ default: T }>,
  fallback: React.ReactNode = <LoadingFallback />
) => {
  const LazyComponent = lazy(() =>
    importFunc().catch((error) => {
      console.error('Failed to load component:', error);
      
      // Retry once after a delay (handles temporary network issues)
      return new Promise<{ default: T }>((resolve) => {
        setTimeout(() => {
          resolve(importFunc());
        }, 1000);
      });
    })
  );

  return (props: any) => (
    <Suspense fallback={fallback}>
      <LazyComponent {...props} />
    </Suspense>
  );
};

/**
 * Preload a lazy component
 * Useful for prefetching routes the user is likely to visit
 */
export const preloadComponent = (importFunc: () => Promise<any>) => {
  importFunc();
};

/**
 * Lazy load with minimum display time
 * Prevents flash of loading state for fast loads
 */
export const lazyLoadWithMinDelay = <T extends ComponentType<any>>(
  importFunc: () => Promise<{ default: T }>,
  minDelay: number = 300
) => {
  const LazyComponent = lazy(() =>
    Promise.all([
      importFunc(),
      new Promise((resolve) => setTimeout(resolve, minDelay))
    ]).then(([moduleExports]) => moduleExports)
  );

  return (props: any) => (
    <Suspense fallback={<LoadingFallback />}>
      <LazyComponent {...props} />
    </Suspense>
  );
};
