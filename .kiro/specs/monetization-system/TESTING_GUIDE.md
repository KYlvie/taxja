# Monetization System - Testing Guide

## Overview

This guide provides comprehensive testing procedures for the monetization system implementation.

---

## Prerequisites

### 1. Environment Setup

```bash
# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd frontend
npm install
```

### 2. Configuration

Create `.env` files with test credentials:

**Backend `.env`:**
```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/taxja_test

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=1

# Stripe (Test Mode)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# JWT
SECRET_KEY=your-secret-key-for-testing
ALGORITHM=HS256
```

**Frontend `.env`:**
```env
VITE_API_BASE_URL=http://localhost:8000
VITE_STRIPE_PUBLISHABLE_KEY=pk_test_...
```

### 3. Database Setup

```bash
cd backend

# Run migrations
alembic upgrade head

# Seed test data (create this script)
python scripts/seed_plans.py
```

---

## Testing Phases

### Phase 1: Backend Unit Tests ✓

Test individual services and models.

### Phase 2: Backend Integration Tests ✓

Test API endpoints and database interactions.

### Phase 3: Frontend Component Tests ✓

Test React components in isolation.

### Phase 4: End-to-End Tests ✓

Test complete user workflows.

### Phase 5: Manual Testing ✓

Human verification of UI/UX.

---

## Phase 1: Backend Unit Tests

### Test Models

```bash
cd backend
pytest tests/unit/test_subscription_models.py -v
```

**What to test:**
- Plan model validation
- Subscription status transitions
- UsageRecord increment/reset
- PaymentEvent idempotency

### Test Services

```bash
pytest tests/unit/test_subscription_services.py -v
```

**What to test:**
- PlanService CRUD operations
- SubscriptionService lifecycle
- FeatureGateService access control
- UsageTrackerService quota enforcement
- TrialService trial activation

---

## Phase 2: Backend Integration Tests

### Test API Endpoints

```bash
pytest tests/integration/test_subscription_api.py -v
```

**Test scenarios:**

1. **List Plans**
   ```bash
   curl http://localhost:8000/api/v1/subscriptions/plans
   ```
   Expected: 200, array of 3 plans

2. **Get Current Subscription** (requires auth)
   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
        http://localhost:8000/api/v1/subscriptions/current
   ```
   Expected: 200, subscription object

3. **Create Checkout Session**
   ```bash
   curl -X POST \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d '{
          "plan_id": 2,
          "billing_cycle": "monthly",
          "success_url": "http://localhost:3000/success",
          "cancel_url": "http://localhost:3000/pricing"
        }' \
        http://localhost:8000/api/v1/subscriptions/checkout
   ```
   Expected: 200, session_id and url

4. **Get Usage Summary**
   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
        http://localhost:8000/api/v1/usage/summary
   ```
   Expected: 200, usage data for all resources

5. **Stripe Webhook** (simulate)
   ```bash
   curl -X POST \
        -H "Stripe-Signature: $SIGNATURE" \
        -H "Content-Type: application/json" \
        -d @tests/fixtures/stripe_webhook_checkout_completed.json \
        http://localhost:8000/api/v1/webhooks/stripe
   ```
   Expected: 200, success response

### Test Feature Gating

```bash
pytest tests/integration/test_feature_gating.py -v
```

**Test scenarios:**
- Free user accessing Plus feature → 403
- Plus user accessing Pro feature → 403
- Pro user accessing all features → 200
- Expired subscription → treated as Free

### Test Usage Tracking

```bash
pytest tests/integration/test_usage_tracking.py -v
```

**Test scenarios:**
- Increment usage within quota → success
- Increment usage exceeding quota → 429
- Usage reset at period end → count = 0
- 80% warning threshold → header present

---

## Phase 3: Frontend Component Tests

### Test Zustand Store

```bash
cd frontend
npm run test -- subscriptionStore.test.ts
```

**What to test:**
- fetchSubscription action
- fetchUsage action
- createCheckoutSession action
- Error handling
- Loading states

### Test Components

```bash
npm run test -- --coverage
```

**Components to test:**
1. PricingPage
   - Plan rendering
   - Billing toggle
   - Checkout button click

2. SubscriptionStatus
   - Plan badge display
   - Trial countdown
   - Usage bars

3. UsageWidget
   - Progress bar colors
   - Quota warnings
   - Compact mode

4. UpgradePrompt
   - Modal open/close
   - Feature benefits display
   - Navigation to pricing

5. withFeatureGate HOC
   - Access granted
   - Access denied
   - Upgrade prompt trigger

---

## Phase 4: End-to-End Tests

### Setup E2E Environment

```bash
# Install Playwright
npm install -D @playwright/test

# Run E2E tests
npm run test:e2e
```

### E2E Test Scenarios

#### Scenario 1: New User Trial Activation

```typescript
test('New user activates 14-day Pro trial', async ({ page }) => {
  // 1. Sign up
  await page.goto('/signup');
  await page.fill('[name="email"]', 'test@example.com');
  await page.fill('[name="password"]', 'password123');
  await page.click('button[type="submit"]');
  
  // 2. Verify trial activation
  await page.waitForURL('/dashboard');
  await expect(page.locator('.trial-countdown')).toContainText('14 days');
  
  // 3. Check Pro features are accessible
  await page.goto('/ai-assistant');
  await expect(page.locator('.feature-locked')).not.toBeVisible();
});
```

#### Scenario 2: Upgrade Flow

```typescript
test('User upgrades from Free to Plus', async ({ page }) => {
  // 1. Login as Free user
  await loginAsUser(page, 'free@example.com');
  
  // 2. Navigate to pricing
  await page.goto('/pricing');
  
  // 3. Select Plus plan
  await page.click('[data-plan="plus"] button');
  
  // 4. Complete Stripe checkout (test mode)
  await page.waitForURL(/stripe.com/);
  await fillStripeTestCard(page);
  await page.click('[data-testid="submit-button"]');
  
  // 5. Verify success page
  await page.waitForURL('/subscription/success');
  await expect(page.locator('h1')).toContainText('Payment Successful');
  
  // 6. Verify plan updated
  await page.goto('/subscription/manage');
  await expect(page.locator('.plan-badge')).toContainText('Plus');
});
```

#### Scenario 3: Feature Gating

```typescript
test('Free user sees upgrade prompt for Pro feature', async ({ page }) => {
  // 1. Login as Free user
  await loginAsUser(page, 'free@example.com');
  
  // 2. Try to access Pro feature
  await page.goto('/ai-assistant');
  
  // 3. Verify upgrade prompt appears
  await expect(page.locator('.upgrade-prompt-modal')).toBeVisible();
  await expect(page.locator('.modal-title')).toContainText('Upgrade to Pro');
  
  // 4. Click upgrade button
  await page.click('.btn-upgrade');
  
  // 5. Verify redirect to pricing
  await page.waitForURL('/pricing');
});
```

#### Scenario 4: Usage Quota Enforcement

```typescript
test('User hits OCR quota limit', async ({ page }) => {
  // 1. Login as Plus user (20 OCR/month)
  await loginAsUser(page, 'plus@example.com');
  
  // 2. Use OCR 20 times
  for (let i = 0; i < 20; i++) {
    await uploadAndScanDocument(page);
  }
  
  // 3. Verify usage widget shows 100%
  await page.goto('/dashboard');
  await expect(page.locator('[data-resource="ocr_scans"] .usage-fill'))
    .toHaveCSS('width', '100%');
  
  // 4. Try to use OCR again
  await page.goto('/documents/upload');
  await page.click('[data-action="scan"]');
  
  // 5. Verify quota exceeded error
  await expect(page.locator('.error-message'))
    .toContainText('Quota exceeded');
});
```

#### Scenario 5: Subscription Cancellation

```typescript
test('User cancels subscription', async ({ page }) => {
  // 1. Login as Plus user
  await loginAsUser(page, 'plus@example.com');
  
  // 2. Navigate to subscription management
  await page.goto('/subscription/manage');
  
  // 3. Click cancel button
  await page.click('button:has-text("Cancel Subscription")');
  
  // 4. Confirm cancellation
  await page.click('.confirmation-modal button:has-text("Yes, Cancel")');
  
  // 5. Verify cancellation notice
  await expect(page.locator('.cancellation-notice')).toBeVisible();
  await expect(page.locator('.detail-row.warning'))
    .toContainText('Ends');
  
  // 6. Verify can reactivate
  await expect(page.locator('button:has-text("Reactivate")')).toBeVisible();
});
```

---

## Phase 5: Manual Testing Checklist

### UI/UX Testing

#### Pricing Page
- [ ] All 3 plans display correctly
- [ ] Monthly/yearly toggle works
- [ ] Discount badge shows 17%
- [ ] Plus plan is highlighted
- [ ] Feature lists are complete
- [ ] Buttons are clickable
- [ ] Responsive on mobile
- [ ] All 3 languages work (DE, EN, ZH)

#### Subscription Status
- [ ] Current plan badge displays
- [ ] Status badge shows correct state
- [ ] Trial countdown is accurate
- [ ] Period dates are correct
- [ ] Usage bars show correct percentages
- [ ] Colors change at 80% (yellow) and 100% (red)
- [ ] Manage button navigates correctly

#### Usage Widget
- [ ] All 3 resources display
- [ ] Progress bars animate smoothly
- [ ] Quota warnings appear at 80%
- [ ] Exceeded state shows red
- [ ] Reset date is correct
- [ ] Compact mode works
- [ ] Auto-refreshes every 5 minutes

#### Upgrade Prompt
- [ ] Modal opens on restricted feature access
- [ ] Feature name displays correctly
- [ ] Required plan is shown
- [ ] Benefits list is complete
- [ ] Upgrade button navigates to pricing
- [ ] Close button works
- [ ] Overlay dismisses modal
- [ ] Animations are smooth

#### Subscription Management
- [ ] Current plan details are accurate
- [ ] Change plan button works
- [ ] Cancel subscription shows confirmation
- [ ] Reactivate button appears after cancel
- [ ] Payment method section displays
- [ ] Billing history shows (when available)
- [ ] All modals work correctly

#### Checkout Success
- [ ] Success icon displays
- [ ] Plan name is correct
- [ ] Session ID shows
- [ ] Continue button navigates to dashboard
- [ ] View subscription button works
- [ ] Animations play smoothly

### Functional Testing

#### Authentication
- [ ] Login required for subscription endpoints
- [ ] Token validation works
- [ ] Expired tokens are rejected

#### Feature Gating
- [ ] Free users can't access Plus features
- [ ] Plus users can't access Pro features
- [ ] Pro users can access all features
- [ ] Expired subscriptions treated as Free
- [ ] Trial users have Pro access

#### Usage Tracking
- [ ] Usage increments correctly
- [ ] Quota limits are enforced
- [ ] 80% warning appears
- [ ] Exceeded error shows with details
- [ ] Usage resets at period end
- [ ] Upgrade applies new limits immediately

#### Stripe Integration
- [ ] Checkout session creates successfully
- [ ] Redirect to Stripe works
- [ ] Test card payment succeeds
- [ ] Webhook processes correctly
- [ ] Subscription activates after payment
- [ ] Failed payment marks past_due
- [ ] Subscription deletion downgrades to Free

#### Trial Management
- [ ] New users get 14-day Pro trial
- [ ] Trial countdown is accurate
- [ ] 3-day reminder triggers (if implemented)
- [ ] Trial expiration downgrades to Free
- [ ] Only one trial per user

### Internationalization
- [ ] German translations are accurate
- [ ] English translations are accurate
- [ ] Chinese translations are accurate
- [ ] Language switcher works
- [ ] Numbers format correctly
- [ ] Dates format correctly
- [ ] Currency displays as EUR

### Responsive Design
- [ ] Mobile (320px-767px) works
- [ ] Tablet (768px-1023px) works
- [ ] Desktop (1024px+) works
- [ ] Touch interactions work on mobile
- [ ] Buttons are large enough on mobile
- [ ] Text is readable on all sizes

### Accessibility
- [ ] Keyboard navigation works
- [ ] Screen reader labels present
- [ ] Color contrast is sufficient
- [ ] Focus indicators visible
- [ ] ARIA labels are correct
- [ ] Error messages are announced

---

## Test Data Setup

### Create Test Plans

```python
# backend/scripts/seed_plans.py
from app.db.base import SessionLocal
from app.models.plan import Plan, PlanType

def seed_plans():
    db = SessionLocal()
    
    plans = [
        Plan(
            plan_type=PlanType.FREE,
            name="Free",
            monthly_price=0,
            yearly_price=0,
            features={
                "basic_tax_calc": True,
                "transaction_entry": True,
            },
            quotas={
                "transactions": 50,
                "ocr_scans": 0,
                "ai_conversations": 0,
            }
        ),
        Plan(
            plan_type=PlanType.PLUS,
            name="Plus",
            monthly_price=4.90,
            yearly_price=49.00,
            features={
                "basic_tax_calc": True,
                "transaction_entry": True,
                "unlimited_transactions": True,
                "ocr_scanning": True,
                "full_tax_calc": True,
                "multi_language": True,
                "vat_calc": True,
                "svs_calc": True,
            },
            quotas={
                "transactions": -1,  # unlimited
                "ocr_scans": 20,
                "ai_conversations": 0,
            }
        ),
        Plan(
            plan_type=PlanType.PRO,
            name="Pro",
            monthly_price=9.90,
            yearly_price=99.00,
            features={
                "basic_tax_calc": True,
                "transaction_entry": True,
                "unlimited_transactions": True,
                "ocr_scanning": True,
                "unlimited_ocr": True,
                "full_tax_calc": True,
                "multi_language": True,
                "vat_calc": True,
                "svs_calc": True,
                "ai_assistant": True,
                "e1_generation": True,
                "advanced_reports": True,
                "priority_support": True,
                "api_access": True,
            },
            quotas={
                "transactions": -1,  # unlimited
                "ocr_scans": -1,  # unlimited
                "ai_conversations": -1,  # unlimited
            }
        ),
    ]
    
    for plan in plans:
        db.add(plan)
    
    db.commit()
    print("✓ Plans seeded successfully")

if __name__ == "__main__":
    seed_plans()
```

### Create Test Users

```python
# backend/scripts/seed_test_users.py
from app.db.base import SessionLocal
from app.models.user import User
from app.models.subscription import Subscription, SubscriptionStatus
from app.core.security import get_password_hash
from datetime import datetime, timedelta

def seed_test_users():
    db = SessionLocal()
    
    # Get plans
    free_plan = db.query(Plan).filter(Plan.plan_type == PlanType.FREE).first()
    plus_plan = db.query(Plan).filter(Plan.plan_type == PlanType.PLUS).first()
    pro_plan = db.query(Plan).filter(Plan.plan_type == PlanType.PRO).first()
    
    users = [
        {
            "email": "free@example.com",
            "password": "password123",
            "plan": free_plan,
            "status": SubscriptionStatus.ACTIVE,
        },
        {
            "email": "plus@example.com",
            "password": "password123",
            "plan": plus_plan,
            "status": SubscriptionStatus.ACTIVE,
        },
        {
            "email": "pro@example.com",
            "password": "password123",
            "plan": pro_plan,
            "status": SubscriptionStatus.ACTIVE,
        },
        {
            "email": "trial@example.com",
            "password": "password123",
            "plan": pro_plan,
            "status": SubscriptionStatus.TRIALING,
        },
    ]
    
    for user_data in users:
        user = User(
            email=user_data["email"],
            hashed_password=get_password_hash(user_data["password"]),
        )
        db.add(user)
        db.flush()
        
        subscription = Subscription(
            user_id=user.id,
            plan_id=user_data["plan"].id,
            status=user_data["status"],
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow() + timedelta(days=30),
        )
        db.add(subscription)
    
    db.commit()
    print("✓ Test users seeded successfully")

if __name__ == "__main__":
    seed_test_users()
```

---

## Running Tests

### Quick Test

```bash
# Backend
cd backend
pytest tests/integration/test_subscription_api.py::test_list_plans -v

# Frontend
cd frontend
npm run test -- PricingPage.test.tsx
```

### Full Test Suite

```bash
# Backend
cd backend
pytest --cov=app --cov-report=html

# Frontend
cd frontend
npm run test -- --coverage

# E2E
npm run test:e2e
```

### Manual Testing

```bash
# Start backend
cd backend
uvicorn app.main:app --reload

# Start frontend
cd frontend
npm run dev

# Open browser
open http://localhost:3000/pricing
```

---

## Expected Results

### Success Criteria

- ✅ All unit tests pass
- ✅ All integration tests pass
- ✅ All E2E tests pass
- ✅ Manual testing checklist 100% complete
- ✅ No console errors
- ✅ No TypeScript errors
- ✅ No accessibility violations
- ✅ Responsive on all devices
- ✅ All 3 languages work correctly

### Performance Benchmarks

- Page load < 2s
- API response < 500ms
- Stripe redirect < 1s
- Usage widget refresh < 200ms

---

## Troubleshooting

### Common Issues

1. **Stripe webhook fails**
   - Check webhook secret is correct
   - Verify signature calculation
   - Use Stripe CLI for local testing

2. **Redis connection fails**
   - Ensure Redis is running
   - Check connection settings
   - Fallback to no-cache mode works

3. **Database migration fails**
   - Check PostgreSQL is running
   - Verify connection string
   - Run migrations manually

4. **Frontend API calls fail**
   - Check CORS settings
   - Verify API base URL
   - Check authentication token

---

## Next Steps

After testing is complete:
1. Fix any bugs found
2. Implement remaining tasks (7, 8, 9, 10)
3. Deploy to staging environment
4. Conduct user acceptance testing
5. Deploy to production

---

## Support

For issues or questions:
- Check logs: `docker-compose logs -f`
- Review error messages
- Consult documentation
- Contact development team
