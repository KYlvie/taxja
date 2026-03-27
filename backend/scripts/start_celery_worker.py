"""Start a Celery worker with platform-safe defaults."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.celery_worker_profile import (  # noqa: E402
    resolve_worker_concurrency,
    resolve_worker_pool,
)
from app.core.config import settings  # noqa: E402


def build_worker_command() -> list[str]:
    pool = resolve_worker_pool(settings.CELERY_WORKER_POOL)
    concurrency = resolve_worker_concurrency(settings.CELERY_WORKER_CONCURRENCY)
    queues = settings.CELERY_WORKER_QUEUES or "default,ocr,ml"

    return [
        sys.executable,
        "-m",
        "celery",
        "-A",
        "app.celery_app",
        "worker",
        "--loglevel=info",
        "--pool",
        pool,
        "--concurrency",
        str(concurrency),
        "-Q",
        queues,
    ]


def main() -> int:
    command = build_worker_command()
    print(
        f"Starting Celery worker with pool={command[8]} concurrency={command[10]} queues={command[12]}",
        flush=True,
    )
    completed = subprocess.run(command, cwd=str(ROOT), env=os.environ.copy())
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
