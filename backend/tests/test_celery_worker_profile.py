from app.core.celery_worker_profile import (
    default_worker_concurrency,
    default_worker_pool,
    resolve_worker_concurrency,
    resolve_worker_pool,
)


def test_windows_defaults_to_threads_pool():
    assert default_worker_pool("win32") == "threads"


def test_linux_defaults_to_prefork_pool():
    assert default_worker_pool("linux") == "prefork"


def test_windows_default_concurrency_is_capped_and_not_too_low():
    assert default_worker_concurrency(platform_name="win32", cpu_count=2) == 4
    assert default_worker_concurrency(platform_name="win32", cpu_count=16) == 8


def test_resolve_worker_profile_prefers_explicit_values():
    assert resolve_worker_pool("solo", platform_name="win32") == "solo"
    assert resolve_worker_concurrency(
        3,
        platform_name="win32",
        cpu_count=16,
    ) == 3
