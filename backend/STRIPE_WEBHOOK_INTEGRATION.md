# Stripe Webhook Integration Guide

## Quick Start

Follow these steps to integrate the Stripe webhook handler into your application.

## Step 1: Update main.py

Add the Stripe webhook router to your main application:

```python
# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import os

from database import init_db, close_db
from api import tenders, documents, rag, auth
from api.stripe_webhook import router as stripe_webhook_router  # ADD THIS LINE

app = FastAPI(
    title="nabavkidata.com API",
    description="Macedonian Tender Intelligence Platform - AI-powered tender search and analysis",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://nabavkidata.com",
        "https://www.nabavkidata.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup/Shutdown Events
@app.on_event("startup")
async def startup():
    """Initialize database connection on startup"""
    await init_db()
    print("✓ Database connection pool initialized")

@app.on_event("shutdown")
async def shutdown():
    """Close database connections on shutdown"""
    await close_db()
    print("✓ Database connections closed")

# Include API routers
app.include_router(auth.router, prefix="/api")
app.include_router(tenders.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(rag.router, prefix="/api")
app.include_router(stripe_webhook_router, prefix="/api")  # ADD THIS LINE

# Root endpoints
@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "service": "nabavkidata.com API",
        "version": "1.0.0",
        "description": "Macedonian Tender Intelligence Platform",
        "documentation": "/api/docs",
        "status": "operational"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "backend-api",
        "timestamp": datetime.utcnow().isoformat(),
        "database": "connected" if os.getenv('DATABASE_URL') else "not configured",
        "rag": "enabled" if os.getenv('OPENAI_API_KEY') else "disabled"
    }
```

## Step 2: Update Environment Variables

Add these to your `.env` file:

```bash
# Stripe Configuration
STRIPE_SECRET_KEY=sk_test_your_test_key_here
STRIPE_PUBLISHABLE_KEY=pk_test_your_test_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret_here

# Frontend URL (for redirects)
FRONTEND_URL=http://localhost:3000
```

For production (`.env.prod` or `.env.production`):

```bash
# Stripe Configuration (PRODUCTION)
STRIPE_SECRET_KEY=sk_live_YOUR_LIVE_SECRET_KEY
STRIPE_PUBLISHABLE_KEY=pk_live_YOUR_LIVE_PUBLISHABLE_KEY
STRIPE_WEBHOOK_SECRET=whsec_YOUR_LIVE_WEBHOOK_SECRET

# Frontend URL (PRODUCTION)
FRONTEND_URL=https://nabavkidata.com
```

## Step 3: Configure Stripe Webhook

### Development (using Stripe CLI)

1. Install Stripe CLI:
   ```bash
   # macOS
   brew install stripe/stripe-cli/stripe

   # Linux
   wget https://github.com/stripe/stripe-cli/releases/download/v1.17.0/stripe_1.17.0_linux_x86_64.tar.gz
   tar -xvf stripe_1.17.0_linux_x86_64.tar.gz
   sudo mv stripe /usr/local/bin/
   ```

2. Login to Stripe:
   ```bash
   stripe login
   ```

3. Forward webhooks to local server:
   ```bash
   stripe listen --forward-to localhost:8000/api/stripe/webhook
   ```

4. Copy the webhook signing secret displayed and add it to your `.env`:
   ```bash
   STRIPE_WEBHOOK_SECRET=whsec_xxx...
   ```

### Production (Stripe Dashboard)

1. Login to Stripe Dashboard: https://dashboard.stripe.com/webhooks

2. Click "Add endpoint"

3. Configure endpoint:
   - **Endpoint URL**: `https://yourdomain.com/api/stripe/webhook`
   - **Description**: "nabavkidata.com Subscription Webhooks"
   - **Events to send**: Select these events:
     - `customer.subscription.created`
     - `customer.subscription.updated`
     - `customer.subscription.deleted`
     - `invoice.payment_succeeded`
     - `invoice.payment_failed`
     - `customer.subscription.trial_will_end`

4. Click "Add endpoint"

5. Copy the **Signing secret** (starts with `whsec_`) and add it to your production environment

## Step 4: Test the Integration

### Test 1: Health Check

```bash
curl http://localhost:8000/api/stripe/webhook/health
```

Expected response:
```json
{
  "status": "healthy",
  "webhook_secret_configured": true,
  "stripe_api_key_configured": true,
  "supported_events": [
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.payment_succeeded",
    "invoice.payment_failed",
    "customer.subscription.trial_will_end"
  ],
  "price_id_mappings": 4,
  "timestamp": "2025-11-23T10:30:00.000Z"
}
```

### Test 2: Trigger Test Events (Development)

With Stripe CLI listening, trigger test events:

```bash
# Test subscription created
stripe trigger customer.subscription.created

# Test payment succeeded
stripe trigger invoice.payment_succeeded

# Test payment failed
stripe trigger invoice.payment_failed

# Test subscription updated
stripe trigger customer.subscription.updated

# Test subscription deleted
stripe trigger customer.subscription.deleted
```

### Test 3: View Logs

Monitor your application logs to see webhook processing:

```bash
# If running with uvicorn
tail -f logs/app.log | grep stripe_webhook

# Or just monitor console output
```

Expected log output:
```
2025-11-23 10:30:00 - stripe_webhook - INFO - Received Stripe webhook event: customer.subscription.created (ID: evt_123)
2025-11-23 10:30:00 - stripe_webhook - INFO - Processing subscription.created: sub_123 for customer: cus_456
2025-11-23 10:30:00 - stripe_webhook - INFO - Successfully created subscription for user abc-def with tier: professional
```

## Step 5: Update Subscription Tiers (Optional)

If you need to add or modify subscription tiers, update the price ID mapping in `stripe_webhook.py`:

```python
# backend/api/stripe_webhook.py

PRICE_ID_TO_TIER = {
    # Your actual Stripe price IDs
    "price_1SWeAqHkVI5icjTlYgQujATs": "free",
    "price_1SWeAsHkVI5icjTl9GZ8Ciui": "starter",
    "price_1SWeAtHkVI5icjTl8UxSYNYX": "professional",
    "price_1SWeAvHkVI5icjTlF8eFK8kh": "enterprise",

    # Add new tiers here:
    # "price_XXXXXXXXXXXXXXXXX": "premium",
}
```

## Webhook URL Reference

Once integrated, these endpoints will be available:

- **Webhook Endpoint**: `https://yourdomain.com/api/stripe/webhook`
  - POST: Receives Stripe webhook events

- **Health Check**: `https://yourdomain.com/api/stripe/webhook/health`
  - GET: Check webhook configuration status

## Database Verification

After webhook processing, verify database updates:

```sql
-- Check user subscription tiers
SELECT user_id, email, subscription_tier, stripe_customer_id
FROM users
ORDER BY created_at DESC
LIMIT 10;

-- Check subscriptions
SELECT subscription_id, user_id, tier, status,
       current_period_start, current_period_end
FROM subscriptions
ORDER BY created_at DESC
LIMIT 10;
```

## Common Issues and Solutions

### Issue 1: Webhook Signature Verification Failed

**Symptoms:**
- 400 Bad Request response
- Log: "Invalid webhook signature"

**Solution:**
1. Verify `STRIPE_WEBHOOK_SECRET` is correct
2. Ensure you're using the signing secret from the correct webhook endpoint
3. Check that request body is not being modified by middleware

### Issue 2: User Not Found

**Symptoms:**
- Log: "User not found for customer_id: cus_xxx"

**Solution:**
1. Ensure user has `stripe_customer_id` set during checkout
2. Verify customer ID matches between Stripe and database
3. Check that checkout process properly updates user record

### Issue 3: Tier Not Updating

**Symptoms:**
- Subscription created but user tier remains "free"

**Solution:**
1. Check price ID mapping in `PRICE_ID_TO_TIER`
2. Verify subscription includes correct price ID
3. Check database transaction completed successfully
4. Review logs for any error messages

### Issue 4: 500 Internal Server Error

**Symptoms:**
- Webhook returns 500 error
- Stripe retries webhook

**Solution:**
1. Check application logs for Python exceptions
2. Verify database connection is working
3. Ensure all required imports are available
4. Check database schema matches models

## Monitoring in Production

### Stripe Dashboard

Monitor webhook delivery in Stripe Dashboard:
1. Go to Developers → Webhooks
2. Click on your webhook endpoint
3. View delivery attempts, responses, and errors

### Application Logs

Set up log monitoring for webhook events:

```bash
# Count successful webhook processings
grep "Successfully processed webhook event" logs/app.log | wc -l

# View failed webhooks
grep "Error processing webhook event" logs/app.log

# Monitor payment failures
grep "payment_failed" logs/app.log
```

### Database Monitoring

Track subscription metrics:

```sql
-- Subscription tier distribution
SELECT subscription_tier, COUNT(*) as count
FROM users
GROUP BY subscription_tier;

-- Active subscriptions
SELECT tier, status, COUNT(*) as count
FROM subscriptions
GROUP BY tier, status;

-- Recent payment failures
SELECT COUNT(*) as failed_payments
FROM subscriptions
WHERE status = 'past_due'
AND updated_at > NOW() - INTERVAL '24 hours';
```

## Security Best Practices

1. **Always verify webhook signatures** in production
2. **Use HTTPS** for webhook endpoint (required by Stripe)
3. **Keep webhook secret secure** - never commit to git
4. **Rotate webhook secrets** periodically
5. **Monitor for unusual activity** (high failure rates, etc.)
6. **Rate limit webhook endpoint** if needed
7. **Log all webhook events** for audit trail

## Next Steps

After integration:

1. ✅ Test all webhook events in development
2. ✅ Verify database updates are correct
3. ✅ Test subscription lifecycle (create, update, cancel)
4. ✅ Test payment failure scenarios
5. ✅ Set up production webhook in Stripe Dashboard
6. ✅ Configure production environment variables
7. ✅ Deploy to production
8. ✅ Monitor webhook delivery and logs

## Support Resources

- **Stripe Webhook Documentation**: https://stripe.com/docs/webhooks
- **Stripe CLI Documentation**: https://stripe.com/docs/stripe-cli
- **Stripe Testing**: https://stripe.com/docs/testing
- **Webhook Best Practices**: https://stripe.com/docs/webhooks/best-practices

## Files Created

1. `/Users/tamsar/Downloads/nabavkidata/backend/api/stripe_webhook.py` - Main webhook handler (649 lines)
2. `/Users/tamsar/Downloads/nabavkidata/backend/api/STRIPE_WEBHOOK_README.md` - Detailed documentation
3. `/Users/tamsar/Downloads/nabavkidata/backend/STRIPE_WEBHOOK_INTEGRATION.md` - This integration guide

## Version

- **Created**: 2025-11-23
- **Version**: 1.0.0
- **Status**: Production Ready

---

For questions or issues, refer to the documentation files or Stripe support.
