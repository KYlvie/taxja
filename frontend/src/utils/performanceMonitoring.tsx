/**
 * Performance monitoring utilities for tracking app performance
 */

import React from 'react';

interface PerformanceMetric {
  name: string;
  value: number;
  timestamp: number;
}

class PerformanceMonitor {
  private metrics: PerformanceMetric[] = [];
  private readonly MAX_METRICS = 100;

  /**
   * Mark the start of a performance measurement
   */
  markStart(name: string): void {
    if (typeof performance !== 'undefined') {
      performance.mark(`${name}-start`);
    }
  }

  /**
   * Mark the end of a performance measurement and calculate duration
   */
  markEnd(name: string): number | null {
    if (typeof performance === 'undefined') return null;

    performance.mark(`${name}-end`);

    try {
      const measure = performance.measure(
        name,
        `${name}-start`,
        `${name}-end`
      );

      const metric: PerformanceMetric = {
        name,
        value: measure.duration,
        timestamp: Date.now()
      };

      this.addMetric(metric);

      // Clean up marks
      performance.clearMarks(`${name}-start`);
      performance.clearMarks(`${name}-end`);
      performance.clearMeasures(name);

      return measure.duration;
    } catch (error) {
      console.warn(`Failed to measure ${name}:`, error);
      return null;
    }
  }

  /**
   * Add a custom metric
   */
  addMetric(metric: PerformanceMetric): void {
    this.metrics.push(metric);

    // Keep only the most recent metrics
    if (this.metrics.length > this.MAX_METRICS) {
      this.metrics.shift();
    }
  }

  /**
   * Get all metrics
   */
  getMetrics(): PerformanceMetric[] {
    return [...this.metrics];
  }

  /**
   * Get metrics by name
   */
  getMetricsByName(name: string): PerformanceMetric[] {
    return this.metrics.filter(m => m.name === name);
  }

  /**
   * Get average value for a metric
   */
  getAverageMetric(name: string): number | null {
    const metrics = this.getMetricsByName(name);
    if (metrics.length === 0) return null;

    const sum = metrics.reduce((acc, m) => acc + m.value, 0);
    return sum / metrics.length;
  }

  /**
   * Clear all metrics
   */
  clearMetrics(): void {
    this.metrics = [];
  }

  /**
   * Log performance metrics to console (development only)
   */
  logMetrics(): void {
    if (import.meta.env.DEV) {
      console.group('Performance Metrics');
      
      const metricsByName = this.metrics.reduce((acc, metric) => {
        if (!acc[metric.name]) {
          acc[metric.name] = [];
        }
        acc[metric.name].push(metric.value);
        return acc;
      }, {} as Record<string, number[]>);

      Object.entries(metricsByName).forEach(([name, values]) => {
        const avg = values.reduce((a, b) => a + b, 0) / values.length;
        const min = Math.min(...values);
        const max = Math.max(...values);
        
        console.log(`${name}:`, {
          count: values.length,
          avg: `${avg.toFixed(2)}ms`,
          min: `${min.toFixed(2)}ms`,
          max: `${max.toFixed(2)}ms`
        });
      });

      console.groupEnd();
    }
  }

  /**
   * Report Web Vitals metrics
   */
  reportWebVitals(): void {
    if (typeof performance === 'undefined') return;

    // First Contentful Paint (FCP)
    const fcpEntry = performance.getEntriesByName('first-contentful-paint')[0];
    if (fcpEntry) {
      this.addMetric({
        name: 'FCP',
        value: fcpEntry.startTime,
        timestamp: Date.now()
      });
    }

    // Largest Contentful Paint (LCP)
    if ('PerformanceObserver' in window) {
      try {
        const lcpObserver = new PerformanceObserver((list) => {
          const entries = list.getEntries();
          const lastEntry = entries[entries.length - 1] as any;
          
          this.addMetric({
            name: 'LCP',
            value: lastEntry.renderTime || lastEntry.loadTime,
            timestamp: Date.now()
          });
        });

        lcpObserver.observe({ entryTypes: ['largest-contentful-paint'] });
      } catch (error) {
        console.warn('Failed to observe LCP:', error);
      }
    }

    // First Input Delay (FID)
    if ('PerformanceObserver' in window) {
      try {
        const fidObserver = new PerformanceObserver((list) => {
          const entries = list.getEntries();
          entries.forEach((entry: any) => {
            this.addMetric({
              name: 'FID',
              value: entry.processingStart - entry.startTime,
              timestamp: Date.now()
            });
          });
        });

        fidObserver.observe({ entryTypes: ['first-input'] });
      } catch (error) {
        console.warn('Failed to observe FID:', error);
      }
    }

    // Cumulative Layout Shift (CLS)
    if ('PerformanceObserver' in window) {
      try {
        let clsValue = 0;
        const clsObserver = new PerformanceObserver((list) => {
          const entries = list.getEntries();
          entries.forEach((entry: any) => {
            if (!entry.hadRecentInput) {
              clsValue += entry.value;
            }
          });

          this.addMetric({
            name: 'CLS',
            value: clsValue,
            timestamp: Date.now()
          });
        });

        clsObserver.observe({ entryTypes: ['layout-shift'] });
      } catch (error) {
        console.warn('Failed to observe CLS:', error);
      }
    }
  }
}

// Singleton instance
export const performanceMonitor = new PerformanceMonitor();

/**
 * Higher-order function to measure component render time
 */
export const withPerformanceTracking = <P extends object>(
  Component: React.ComponentType<P>,
  componentName: string
): React.ComponentType<P> => {
  return (props: P) => {
    performanceMonitor.markStart(`render-${componentName}`);

    React.useEffect(() => {
      performanceMonitor.markEnd(`render-${componentName}`);
    });

    return <Component {...props} />;
  };
};

/**
 * Hook to measure async operation performance
 */
export const usePerformanceTracking = (operationName: string) => {
  const track = React.useCallback(
    async <T,>(operation: () => Promise<T>): Promise<T> => {
      performanceMonitor.markStart(operationName);
      try {
        const result = await operation();
        return result;
      } finally {
        performanceMonitor.markEnd(operationName);
      }
    },
    [operationName]
  );

  return track;
};

/**
 * Measure network request performance
 */
export const trackNetworkRequest = (url: string, duration: number): void => {
  performanceMonitor.addMetric({
    name: `network-${url}`,
    value: duration,
    timestamp: Date.now()
  });
};

/**
 * Get device performance tier (low/medium/high)
 */
export const getDevicePerformanceTier = (): 'low' | 'medium' | 'high' => {
  if (typeof navigator === 'undefined') return 'medium';

  // Check hardware concurrency (CPU cores)
  const cores = navigator.hardwareConcurrency || 2;

  // Check device memory (if available)
  const memory = (navigator as any).deviceMemory || 4;

  // Check connection speed (if available)
  const connection = (navigator as any).connection;
  const effectiveType = connection?.effectiveType || '4g';

  // Calculate tier based on available metrics
  if (cores >= 8 && memory >= 8 && effectiveType === '4g') {
    return 'high';
  } else if (cores >= 4 && memory >= 4) {
    return 'medium';
  } else {
    return 'low';
  }
};

/**
 * Check if device is in power saving mode
 */
export const isLowPowerMode = (): boolean => {
  if (typeof navigator === 'undefined') return false;

  const connection = (navigator as any).connection;
  return connection?.saveData === true;
};
