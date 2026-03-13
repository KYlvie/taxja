"""
Prometheus Metrics for Property Management

This module defines Prometheus metrics for monitoring property management operations:
- property_created_total: Counter for property creation events
- depreciation_generated_total: Counter for depreciation generation events
- backfill_duration_seconds: Histogram for backfill operation duration

Usage:
    from app.core.metrics import (
        property_created_counter,
        depreciation_generated_counter,
        backfill_duration_histogram
    )
    
    # Increment counters
    property_created_counter.inc()
    depreciation_generated_counter.labels(user_id="123", year="2026").inc()
    
    # Record histogram
    with backfill_duration_histogram.time():
        # ... backfill operation ...
        pass
"""

from prometheus_client import Counter, Histogram


# Counter for property creation events
property_created_counter = Counter(
    'property_created_total',
    'Total number of properties created',
    ['user_id']
)

# Counter for depreciation generation events
depreciation_generated_counter = Counter(
    'depreciation_generated_total',
    'Total number of depreciation transactions generated',
    ['user_id', 'year']
)

# Histogram for backfill operation duration
backfill_duration_histogram = Histogram(
    'backfill_duration_seconds',
    'Duration of historical depreciation backfill operations',
    ['property_id'],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, float('inf'))
)
