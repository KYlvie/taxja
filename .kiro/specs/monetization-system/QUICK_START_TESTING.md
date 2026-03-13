# Quick Start Testing Guide

## 🚀 Get Started in 5 Minutes

This guide will help you quickly test the monetization system implementation.

---

## Step 1: Setup Database (2 minutes)

```bash
cd backend

# Make sure PostgreSQL is running
docker-compose up -d postgres

# Run migrations
alembic upgrade head

# Seed plans
python scripts/seed_plans.py
```

**Expected output:**
```
🌱 Seeding subscription plans...

  ✓ Created Free plan (€0/month)
  ✓ Created Plus plan (€4.9/month)
  ✓ Created Pro plan (€9.9/month)

✅ Plans seeded successfully!
```

---

## Step 2: Run Quick Test (1 minute)

```bash
python scripts/quick_test.py
```

**Expected output:**
```
============================================================
MONETIZATION SYSTEM - QUICK TEST
============================================================

1. Testing database connection...
   ✅ Database connection successful

2. Checking if plans exist...
   ✅ Found 3 plans:
      - Free (€0/month)
      - Plus (€4.9/month)
      - Pro (€9.9/month)

3. Testing PlanService...
   ✅ list_plans() returned 3 plans
   ✅ get_plan_by_type(FREE) returned: Free
   ✅ get_plan_features() returned 2 features
   ✅ get_plan_quotas() returned 3 quotas

4. Testing FeatureGateService...
   ✅ Free plan has AI Assistant: False (expected: False)
   ✅ AI Assistant requires: pro

5. Testing model methods...
   ✅ Plan model validation works
   ✅ Free plan transaction quota: 50

6. Testing API imports...
   ✅ Subscription endpoints imported
   ✅ Usage endpoints imported
   ✅ Webhook endpoints imported
   ✅ Feature gate dependencies imported
   ✅ Custom exceptions imported

============================================================
TEST SUMMARY
============================================================
✅ PASS - Database Connection
✅ PASS - Plans Exist
✅ PASS - PlanService
✅ PASS - FeatureGateService
✅ PASS - Model Methods
✅ PASS - API Imports

Total: 6/6 tests passed

🎉 All tests passed! System is ready for testing.
```

---

## Step 3: Start Backend (30 seconds)

```bash
# In backend directory
uvicorn app.main:app --reload
```

**Test API endpoints:**

```bash
# List plans (no auth required)
curl http://localhost:8000/api/v1/subscriptions/plans

# Expected: JSON array with 3 plans
```

---

## Step 4: Start Frontend (30 seconds)

```bash
cd frontend

# Install dependencies (first time only)
npm install

# Start dev server
npm run dev
```

**Open browser:**
```
http://localhost:3000/pricing
```

---

## Step 5: Manual Testing (1 minute)

### Test Pricing Page

1. Open http://localhost:3000/pricing
2. ✅ Check: All 3 plans display
3. ✅ Check: Monthly/yearly toggle works
4. ✅ Check: Discount badge shows "Save 17%"
5. ✅ Check: Plus plan is highlighted

### Test Language Switching

1. Change language to German
2. ✅ Check: Plan names translate
3. ✅ Check: Feature lists translate
4. Change to Chinese
5. ✅ Check: All text translates

---

## Common Issues & Solutions

### Issue: "No plans found"

**Solution:**
```bash
cd backend
python scripts/seed_plans.py
```

### Issue: "Database connection failed"

**Solution:**
```bash
# Check if PostgreSQL is running
docker-compose ps

# Start if not running
docker-compose up -d postgres

# Check connection string in .env
DATABASE_URL=postgresql://user:password@localhost:5432/taxja
```

### Issue: "Module not found"

**Solution:**
```bash
# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd frontend
npm install
```

### Issue: "Port already in use"

**Solution:**
```bash
# Backend (change port)
uvicorn app.main:app --reload --port 8001

# Frontend (change port)
npm run dev -- --port 3001
```

---

## Quick API Tests

### 1. List Plans
```bash
curl http://localhost:8000/api/v1/subscriptions/plans | jq
```

**Expected:**
```json
[
  {
    "id": 1,
    "plan_type": "free",
    "name": "Free",
    "monthly_price": 0,
    "yearly_price": 0,
    "features": {...},
    "quotas": {...}
  },
  ...
]
```

### 2. Health Check
```bash
curl http://localhost:8000/health
```

**Expected:**
```json
{"status": "healthy"}
```

### 3. API Documentation
Open: http://localhost:8000/docs

---

## Next Steps

### For Full Testing

See [TESTING_GUIDE.md](./TESTING_GUIDE.md) for:
- Unit tests
- Integration tests
- E2E tests
- Manual testing checklist

### For Stripe Testing

1. Get Stripe test keys from https://dashboard.stripe.com/test/apikeys
2. Add to `.env`:
   ```
   STRIPE_SECRET_KEY=sk_test_...
   STRIPE_PUBLISHABLE_KEY=pk_test_...
   STRIPE_WEBHOOK_SECRET=whsec_...
   ```
3. Use Stripe CLI for webhook testing:
   ```bash
   stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe
   ```

### For Redis Testing

1. Start Redis:
   ```bash
   docker-compose up -d redis
   ```
2. Verify caching works:
   ```bash
   redis-cli ping
   # Expected: PONG
   ```

---

## Testing Checklist

### Backend ✓
- [x] Database connection works
- [x] Plans are seeded
- [x] Services can be imported
- [x] Models validate correctly
- [x] API endpoints are registered

### Frontend ✓
- [ ] Pricing page loads
- [ ] Plans display correctly
- [ ] Language switching works
- [ ] Responsive on mobile
- [ ] No console errors

### Integration ✓
- [ ] API calls work from frontend
- [ ] Authentication works
- [ ] Stripe checkout creates session
- [ ] Webhooks process correctly
- [ ] Usage tracking works

---

## Success Criteria

✅ All quick tests pass  
✅ Backend starts without errors  
✅ Frontend starts without errors  
✅ Pricing page displays correctly  
✅ API endpoints respond  
✅ No TypeScript errors  
✅ No console errors  

---

## Get Help

If you encounter issues:

1. Check logs:
   ```bash
   # Backend
   tail -f backend/logs/app.log
   
   # Frontend
   # Check browser console
   ```

2. Verify configuration:
   ```bash
   # Backend
   cat backend/.env
   
   # Frontend
   cat frontend/.env
   ```

3. Reset database:
   ```bash
   cd backend
   alembic downgrade base
   alembic upgrade head
   python scripts/seed_plans.py
   ```

---

## 🎉 Ready to Test!

Once all steps pass, you're ready for comprehensive testing. The system is fully functional and ready for:

- Feature testing
- User acceptance testing
- Performance testing
- Security testing
- Deployment preparation

Good luck! 🚀
