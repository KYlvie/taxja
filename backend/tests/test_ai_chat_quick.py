"""Quick integration test for AI chat via Ollama"""
import httpx
import time

BASE = "http://localhost:8000/api/v1"

# Login
login_resp = httpx.post(f"{BASE}/auth/login", json={"email": "demo@taxja.at", "password": "demo123"})
token = login_resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Chat
print("Sending AI chat request...")
start = time.time()
chat_resp = httpx.post(
    f"{BASE}/ai/chat",
    json={"message": "What are the Austrian income tax rates?", "language": "en"},
    headers=headers,
    timeout=300,
)
elapsed = time.time() - start
print(f"Status: {chat_resp.status_code} | Time: {elapsed:.1f}s")

if chat_resp.status_code == 200:
    data = chat_resp.json()
    msg = data.get("message", "")
    print(f"Response length: {len(msg)} chars")
    print(f"Response preview:\n{msg[:500]}")
else:
    print(f"Error: {chat_resp.text[:500]}")
