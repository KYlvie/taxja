"""Performance monitoring and metrics"""
import time
from typing import Callable
from functools import wraps
from contextlib import asynccontextmanager

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

# In-memory metrics storage (use Prometheus/Grafana in production)
metrics = {
    "api_requests": {},
    "api_response_times": {},
    "ocr_processing_times": [],
    "tax_calculation_times": [],
    "errors": {},
}


class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware to track API performance metrics"""
    
    async def dispatch(self, request: Request, call_next):
        # Start timer
        start_time = time.time()
        
        # Process request
        try:
            response: Response = await call_next(request)
            
            # Calculate response time
            response_time = time.time() - start_time
            
            # Track metrics
            endpoint = f"{request.method} {request.url.path}"
            
            # Track request count
            if endpoint not in metrics["api_requests"]:
                metrics["api_requests"][endpoint] = 0
            metrics["api_requests"][endpoint] += 1
            
            # Track response time
            if endpoint not in metrics["api_response_times"]:
                metrics["api_response_times"][endpoint] = []
            metrics["api_response_times"][endpoint].append(response_time)
            
            # Keep only last 1000 response times per endpoint
            if len(metrics["api_response_times"][endpoint]) > 1000:
                metrics["api_response_times"][endpoint] = metrics["api_response_times"][endpoint][-1000:]
            
            # Add performance header
            response.headers["X-Response-Time"] = f"{response_time:.3f}s"
            
            return response
            
        except Exception as e:
            # Track errors
            endpoint = f"{request.method} {request.url.path}"
            error_type = type(e).__name__
            
            if endpoint not in metrics["errors"]:
                metrics["errors"][endpoint] = {}
            if error_type not in metrics["errors"][endpoint]:
                metrics["errors"][endpoint][error_type] = 0
            metrics["errors"][endpoint][error_type] += 1
            
            raise


def track_performance(metric_name: str):
    """
    Decorator to track function performance.
    
    Args:
        metric_name: Name of the metric to track
    
    Example:
        @track_performance("ocr_processing")
        async def process_document(image):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                elapsed_time = time.time() - start_time
                
                # Track metric
                if metric_name not in metrics:
                    metrics[metric_name] = []
                
                metrics[metric_name].append(elapsed_time)
                
                # Keep only last 1000 measurements
                if len(metrics[metric_name]) > 1000:
                    metrics[metric_name] = metrics[metric_name][-1000:]
        
        return wrapper
    return decorator


@asynccontextmanager
async def track_time(metric_name: str):
    """
    Context manager to track execution time.
    
    Example:
        async with track_time("database_query"):
            result = await db.execute(query)
    """
    start_time = time.time()
    
    try:
        yield
    finally:
        elapsed_time = time.time() - start_time
        
        if metric_name not in metrics:
            metrics[metric_name] = []
        
        metrics[metric_name].append(elapsed_time)
        
        if len(metrics[metric_name]) > 1000:
            metrics[metric_name] = metrics[metric_name][-1000:]


def get_metrics_summary() -> dict:
    """
    Get summary of all metrics.
    
    Returns:
        Dictionary with metric summaries
    """
    summary = {
        "api_requests": {
            endpoint: count
            for endpoint, count in sorted(
                metrics["api_requests"].items(),
                key=lambda x: x[1],
                reverse=True
            )[:20]  # Top 20 endpoints
        },
        "api_response_times": {},
        "ocr_processing": {},
        "tax_calculation": {},
        "errors": metrics["errors"]
    }
    
    # Calculate response time statistics
    for endpoint, times in metrics["api_response_times"].items():
        if times:
            summary["api_response_times"][endpoint] = {
                "count": len(times),
                "avg": sum(times) / len(times),
                "min": min(times),
                "max": max(times),
                "p50": sorted(times)[len(times) // 2],
                "p95": sorted(times)[int(len(times) * 0.95)] if len(times) > 20 else max(times),
                "p99": sorted(times)[int(len(times) * 0.99)] if len(times) > 100 else max(times),
            }
    
    # OCR processing times
    if metrics.get("ocr_processing_times"):
        times = metrics["ocr_processing_times"]
        summary["ocr_processing"] = {
            "count": len(times),
            "avg": sum(times) / len(times),
            "min": min(times),
            "max": max(times),
        }
    
    # Tax calculation times
    if metrics.get("tax_calculation_times"):
        times = metrics["tax_calculation_times"]
        summary["tax_calculation"] = {
            "count": len(times),
            "avg": sum(times) / len(times),
            "min": min(times),
            "max": max(times),
        }
    
    return summary


def check_performance_alerts() -> list[dict]:
    """
    Check for performance issues and return alerts.
    
    Returns:
        List of alert dictionaries
    """
    alerts = []
    
    # Check API response times
    for endpoint, times in metrics["api_response_times"].items():
        if times:
            avg_time = sum(times) / len(times)
            
            # Alert if average response time > 2 seconds
            if avg_time > 2.0:
                alerts.append({
                    "type": "slow_endpoint",
                    "endpoint": endpoint,
                    "avg_response_time": avg_time,
                    "message": f"Endpoint {endpoint} has slow average response time: {avg_time:.2f}s"
                })
            
            # Alert if p95 > 5 seconds
            p95 = sorted(times)[int(len(times) * 0.95)] if len(times) > 20 else max(times)
            if p95 > 5.0:
                alerts.append({
                    "type": "slow_p95",
                    "endpoint": endpoint,
                    "p95_response_time": p95,
                    "message": f"Endpoint {endpoint} has slow p95 response time: {p95:.2f}s"
                })
    
    # Check OCR processing times
    if metrics.get("ocr_processing_times"):
        times = metrics["ocr_processing_times"]
        avg_time = sum(times) / len(times)
        
        # Alert if average OCR time > 5 seconds
        if avg_time > 5.0:
            alerts.append({
                "type": "slow_ocr",
                "avg_processing_time": avg_time,
                "message": f"OCR processing is slow: {avg_time:.2f}s average"
            })
    
    # Check error rates
    for endpoint, errors in metrics["errors"].items():
        total_requests = metrics["api_requests"].get(endpoint, 0)
        total_errors = sum(errors.values())
        
        if total_requests > 0:
            error_rate = total_errors / total_requests
            
            # Alert if error rate > 5%
            if error_rate > 0.05:
                alerts.append({
                    "type": "high_error_rate",
                    "endpoint": endpoint,
                    "error_rate": error_rate,
                    "total_errors": total_errors,
                    "total_requests": total_requests,
                    "message": f"High error rate on {endpoint}: {error_rate:.1%}"
                })
    
    return alerts


def reset_metrics():
    """Reset all metrics (useful for testing)"""
    global metrics
    metrics = {
        "api_requests": {},
        "api_response_times": {},
        "ocr_processing_times": [],
        "tax_calculation_times": [],
        "errors": {},
    }
