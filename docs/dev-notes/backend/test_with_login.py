"""
Test with actual login
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from app.main import app

def test_with_login():
    """Test properties list with actual login"""
    client = TestClient(app)
    
    # Login first
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "ylvie.khoo@hotmail.com",
            "password": "password123"
        }
    )
    
    print(f"Login Status: {login_response.status_code}")
    
    if login_response.status_code != 200:
        print(f"❌ Login failed: {login_response.text}")
        return False
    
    token_data = login_response.json()
    token = token_data["access_token"]
    print(f"✅ Login successful, token: {token[:50]}...")
    
    # Now get properties
    response = client.get(
        "/api/v1/properties",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    print(f"\nProperties Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Properties retrieved!")
        print(f"Total: {data['total']}")
        
        if data['properties']:
            for prop in data['properties']:
                print(f"\nProperty:")
                print(f"  ID: {prop['id']}")
                print(f"  Address: {prop.get('address', 'MISSING!')}")
                print(f"  Status: {prop['status']}")
        
        return True
    else:
        print(f"❌ Failed: {response.text}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Test with Login - Properties List")
    print("=" * 60)
    
    success = test_with_login()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ Test passed!")
    else:
        print("❌ Test failed!")
    print("=" * 60)
