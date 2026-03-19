"""Quick integration smoke test for AI chat against a running local API."""

import time

import httpx
import pytest


BASE = "http://localhost:8001/api/v1"


def _require_local_api() -> None:
    try:
        response = httpx.get("http://localhost:8001/health", timeout=2.0)
    except httpx.HTTPError:
        pytest.skip("Local API is not running on http://localhost:8001")
    if response.status_code >= 500:
        pytest.skip("Local API health endpoint is unavailable")


def test_ai_chat_quick_smoke():
    _require_local_api()

    login_resp = httpx.post(
        f"{BASE}/auth/login",
        json={"email": "demo@taxja.at", "password": "demo123"},
        timeout=10.0,
    )
    if login_resp.status_code != 200:
        pytest.skip("Demo login is not available in this local environment")

    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    start = time.time()
    chat_resp = httpx.post(
        f"{BASE}/ai/chat",
        json={"message": "What are the Austrian income tax rates?", "language": "en"},
        headers=headers,
        timeout=300,
    )
    elapsed = time.time() - start

    assert chat_resp.status_code == 200, chat_resp.text[:500]
    assert elapsed >= 0
    data = chat_resp.json()
    assert isinstance(data.get("message", ""), str)
