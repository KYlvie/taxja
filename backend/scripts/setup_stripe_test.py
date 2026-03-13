"""Setup script for Stripe test mode configuration"""
import os
from pathlib import Path

def setup_stripe_test_env():
    """Add Stripe test configuration to .env file"""
    
    backend_dir = Path(__file__).parent.parent
    env_file = backend_dir / ".env"
    env_example = backend_dir / ".env.example"
    
    # Stripe test configuration
    stripe_config = """
# Stripe Payment Integration (Test Mode)
# Get your test keys from: https://dashboard.stripe.com/test/apikeys
STRIPE_SECRET_KEY=sk_test_your_test_secret_key_here
STRIPE_PUBLISHABLE_KEY=pk_test_your_test_publishable_key_here

# Webhook secret from: https://dashboard.stripe.com/test/webhooks
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret_here

# Stripe Price IDs (create products in Stripe Dashboard first)
# Plus Plan Price IDs
STRIPE_PLUS_MONTHLY_PRICE_ID=price_plus_monthly_id_here
STRIPE_PLUS_YEARLY_PRICE_ID=price_plus_yearly_id_here

# Pro Plan Price IDs
STRIPE_PRO_MONTHLY_PRICE_ID=price_pro_monthly_id_here
STRIPE_PRO_YEARLY_PRICE_ID=price_pro_yearly_id_here
"""
    
    # Check if .env exists, if not copy from .env.example
    if not env_file.exists():
        if env_example.exists():
            print("📋 Creating .env from .env.example...")
            with open(env_example, 'r', encoding='utf-8') as f:
                content = f.read()
            with open(env_file, 'w', encoding='utf-8') as f:
                f.write(content)
            print("✅ .env file created")
        else:
            print("❌ .env.example not found")
            return False
    
    # Check if Stripe config already exists
    with open(env_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'STRIPE_SECRET_KEY' in content:
        print("⚠️  Stripe configuration already exists in .env")
        print("   Please update the values manually if needed")
        return True
    
    # Append Stripe configuration
    print("📝 Adding Stripe test configuration to .env...")
    with open(env_file, 'a', encoding='utf-8') as f:
        f.write(stripe_config)
    
    print("✅ Stripe configuration added to .env")
    print("\n" + "="*60)
    print("NEXT STEPS:")
    print("="*60)
    print("\n1. Get Stripe Test Keys:")
    print("   - Visit: https://dashboard.stripe.com/test/apikeys")
    print("   - Copy 'Secret key' (starts with sk_test_)")
    print("   - Copy 'Publishable key' (starts with pk_test_)")
    print("   - Update STRIPE_SECRET_KEY and STRIPE_PUBLISHABLE_KEY in .env")
    
    print("\n2. Create Products in Stripe Dashboard:")
    print("   - Visit: https://dashboard.stripe.com/test/products")
    print("   - Create 'Taxja Plus' product:")
    print("     * Monthly price: €4.90")
    print("     * Yearly price: €49.00")
    print("   - Create 'Taxja Pro' product:")
    print("     * Monthly price: €9.90")
    print("     * Yearly price: €99.00")
    print("   - Copy Price IDs and update in .env")
    
    print("\n3. Setup Webhook:")
    print("   - Visit: https://dashboard.stripe.com/test/webhooks")
    print("   - Add endpoint: http://localhost:8000/api/v1/webhooks/stripe")
    print("   - Select events:")
    print("     * checkout.session.completed")
    print("     * invoice.payment_succeeded")
    print("     * invoice.payment_failed")
    print("     * customer.subscription.updated")
    print("     * customer.subscription.deleted")
    print("   - Copy webhook secret and update STRIPE_WEBHOOK_SECRET in .env")
    
    print("\n4. Test the configuration:")
    print("   python backend/scripts/test_stripe_config.py")
    print("\n" + "="*60)
    
    return True


if __name__ == "__main__":
    print("="*60)
    print("STRIPE TEST MODE SETUP")
    print("="*60)
    print()
    
    success = setup_stripe_test_env()
    
    if success:
        print("\n✅ Setup complete!")
        print("\nIMPORTANT: Update the placeholder values in backend/.env")
        print("           with your actual Stripe test keys")
    else:
        print("\n❌ Setup failed")
        exit(1)
