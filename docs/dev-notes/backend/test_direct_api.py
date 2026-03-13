"""
Direct test of properties list endpoint using TestClient
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token

def test_properties_list():
    """Test properties list endpoint directly"""
    client = TestClient(app)
    
    # Create token for user_id=11
    token = create_access_token({"sub": "11"})
    
    # Make request
    response = client.get(
        "/api/v1/properties",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Success!")
        print(f"Total: {data['total']}")
        
        if data['properties']:
            for prop in data['properties']:
                print(f"\nProperty:")
                print(f"  ID: {prop['id']}")
                print(f"  Address: {prop.get('address', 'MISSING!')}")
                print(f"  Street: {prop.get('street')}")
                print(f"  City: {prop.get('city')}")
                print(f"  Status: {prop['status']}")
        
        return True
    else:
        print(f"❌ Failed!")
        print(f"Response: {response.text}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Direct API Test - Properties List")
    print("=" * 60)
    
    success = test_properties_list()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ Test passed!")
    else:
        print("❌ Test failed!")
    print("=" * 60)
