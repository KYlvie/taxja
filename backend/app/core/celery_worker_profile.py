"""Celery worker runtime profile helpers."""

from __future__ import annotations

import os
import sys
from typing import Optional


def default_worker_pool(platform_name: Optional[str] = None) -> str:
    """Return the safest default Celery pool for the current platform."""
    platform_name = (platform_name or sys.platform).lower()
    if platform_name.startswith("win"):
        return "threads"
    return "prefork"


def default_worker_concurrency(
    *,
    platform_name: Optional[str] = None,
    cpu_count: Optional[int] = None,
) -> int:
    """Choose a conservative default worker concurrency."""
    platform_name = (platform_name or sys.platform).lower()
    cpu_total = cpu_count or os.cpu_count() or 4

    if platform_name.startswith("win"):
        return max(4, min(8, cpu_total))
    return max(2, min(8, cpu_total))


def resolve_worker_pool(configured_pool: Optional[str] = None, *, platform_name: Optional[str] = None) -> str:
    normalized = (configured_pool or "").strip().lower()
    if normalized:
        return normalized
    return default_worker_pool(platform_name)


def resolve_worker_concurrency(
    configured_concurrency: Optional[int] = None,
    *,
    platform_name: Optional[str] = None,
    cpu_count: Optional[int] = None,
) -> int:
    if configured_concurrency and int(configured_concurrency) > 0:
        return int(configured_concurrency)
    return default_worker_concurrency(platform_name=platform_name, cpu_count=cpu_count)
