"""
Test script to verify properties list API endpoint
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
from app.core.security import create_access_token

def test_properties_list_api():
    """Test GET /api/v1/properties endpoint"""
    
    # Create access token for user_id=11
    token = create_access_token({"sub": "11"})
    
    # Make API request
    url = "http://localhost:8000/api/v1/properties"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    print(f"Making request to: {url}")
    print(f"Token: {token[:50]}...")
    
    try:
        response = requests.get(url, headers=headers)
        
        print(f"\n✅ Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Response received successfully!")
            print(f"   Total properties: {data.get('total', 0)}")
            
            if data.get('properties'):
                for prop in data['properties']:
                    print(f"\n   Property ID: {prop['id']}")
                    print(f"   Address: {prop.get('address', 'N/A')}")
                    print(f"   Status: {prop['status']}")
                    print(f"   Purchase Date: {prop['purchase_date']}")
            
            return True
        else:
            print(f"❌ Request failed!")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Request error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Testing Properties List API Endpoint")
    print("=" * 60)
    
    success = test_properties_list_api()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ API test passed!")
    else:
        print("❌ API test failed!")
    print("=" * 60)
    
    sys.exit(0 if success else 1)
