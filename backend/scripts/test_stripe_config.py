"""Test Stripe configuration and connectivity"""
import sys
import os
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
os.chdir(backend_dir)

from dotenv import load_dotenv
load_dotenv()

def test_stripe_config():
    """Test Stripe configuration"""
    print("="*60)
    print("STRIPE CONFIGURATION TEST")
    print("="*60)
    
    # Check environment variables
    print("\n1. Checking environment variables...")
    
    required_vars = [
        'STRIPE_SECRET_KEY',
        'STRIPE_PUBLISHABLE_KEY',
        'STRIPE_WEBHOOK_SECRET',
    ]
    
    optional_vars = [
        'STRIPE_PLUS_MONTHLY_PRICE_ID',
        'STRIPE_PLUS_YEARLY_PRICE_ID',
        'STRIPE_PRO_MONTHLY_PRICE_ID',
        'STRIPE_PRO_YEARLY_PRICE_ID',
    ]
    
    all_set = True
    for var in required_vars:
        value = os.getenv(var)
        if not value or 'your_' in value or '_here' in value:
            print(f"   ❌ {var} not configured")
            all_set = False
        else:
            masked = value[:12] + "..." if len(value) > 12 else value
            print(f"   ✅ {var} = {masked}")
    
    print("\n   Optional Price IDs:")
    for var in optional_vars:
        value = os.getenv(var)
        if not value or 'your_' in value or '_here' in value:
            print(f"   ⚠️  {var} not configured (optional)")
        else:
            print(f"   ✅ {var} = {value}")
    
    if not all_set:
        print("\n❌ Required Stripe configuration missing")
        print("\nPlease update backend/.env with your Stripe test keys")
        print("Run: python backend/scripts/setup_stripe_test.py for instructions")
        return False
    
    # Test Stripe API connection
    print("\n2. Testing Stripe API connection...")
    try:
        import stripe
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
        
        # Try to retrieve account info
        account = stripe.Account.retrieve()
        print(f"   ✅ Connected to Stripe account: {account.id}")
        print(f"   ✅ Account type: {account.type}")
        print(f"   ✅ Country: {account.country}")
        
        # Check if in test mode
        if stripe.api_key.startswith('sk_test_'):
            print(f"   ✅ Using TEST mode (safe for testing)")
        else:
            print(f"   ⚠️  WARNING: Using LIVE mode!")
        
    except ImportError:
        print("   ❌ Stripe library not installed")
        print("   Run: pip install stripe")
        return False
    except stripe.error.AuthenticationError as e:
        print(f"   ❌ Authentication failed: {e}")
        print("   Check your STRIPE_SECRET_KEY in .env")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # Test webhook secret format
    print("\n3. Checking webhook secret...")
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
    if webhook_secret and webhook_secret.startswith('whsec_'):
        print(f"   ✅ Webhook secret format valid")
    else:
        print(f"   ⚠️  Webhook secret format may be invalid")
        print(f"   Expected format: whsec_...")
    
    # List products (if any)
    print("\n4. Checking Stripe products...")
    try:
        products = stripe.Product.list(limit=10)
        if products.data:
            print(f"   ✅ Found {len(products.data)} products:")
            for product in products.data:
                print(f"      - {product.name} (ID: {product.id})")
        else:
            print(f"   ⚠️  No products found")
            print(f"   Create products in Stripe Dashboard:")
            print(f"   https://dashboard.stripe.com/test/products")
    except Exception as e:
        print(f"   ❌ Error listing products: {e}")
    
    # List prices (if any)
    print("\n5. Checking Stripe prices...")
    try:
        prices = stripe.Price.list(limit=10)
        if prices.data:
            print(f"   ✅ Found {len(prices.data)} prices:")
            for price in prices.data:
                amount = price.unit_amount / 100 if price.unit_amount else 0
                currency = price.currency.upper()
                interval = price.recurring.interval if price.recurring else 'one-time'
                print(f"      - {currency} {amount}/{interval} (ID: {price.id})")
        else:
            print(f"   ⚠️  No prices found")
            print(f"   Create prices in Stripe Dashboard")
    except Exception as e:
        print(f"   ❌ Error listing prices: {e}")
    
    print("\n" + "="*60)
    print("✅ STRIPE CONFIGURATION TEST COMPLETE")
    print("="*60)
    
    print("\nTest Cards for Testing:")
    print("  Success:        4242 4242 4242 4242")
    print("  Decline:        4000 0000 0000 0002")
    print("  3D Secure:      4000 0027 6000 3184")
    print("  Insufficient:   4000 0000 0000 9995")
    
    print("\nNext Steps:")
    print("  1. Create products and prices in Stripe Dashboard")
    print("  2. Update Price IDs in backend/.env")
    print("  3. Start backend: uvicorn app.main:app --reload")
    print("  4. Test checkout flow")
    
    return True


if __name__ == "__main__":
    try:
        success = test_stripe_config()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
