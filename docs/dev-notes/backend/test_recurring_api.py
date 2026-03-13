"""Test recurring transactions API"""
import requests
import json

# Test user credentials
email = "ylvie.khoo@hotmail.com"
password = "test123"  # You may need to adjust this

# Login to get token
login_response = requests.post(
    "http://localhost:8000/api/v1/auth/login",
    json={"email": email, "password": password}
)

if login_response.status_code != 200:
    print(f"Login failed: {login_response.status_code}")
    print(login_response.text)
    exit(1)

token = login_response.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Test recurring transactions endpoint
print("Testing recurring transactions API...")
response = requests.get(
    "http://localhost:8000/api/v1/recurring-transactions?active_only=false",
    headers=headers
)

print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")

if response.status_code == 200:
    data = response.json()
    print(f"\nTotal: {data.get('total', 0)}")
    print(f"Active: {data.get('active_count', 0)}")
    print(f"Paused: {data.get('paused_count', 0)}")
    print(f"Items: {len(data.get('items', []))}")
