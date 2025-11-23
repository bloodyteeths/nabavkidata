# Stripe Webhook Handler Documentation

## Overview

Complete Stripe webhook handler for nabavkidata.com that processes all subscription-related events, manages user subscription tiers, handles payment failures, and maintains subscription state synchronization.

## File Location

`/Users/tamsar/Downloads/nabavkidata/backend/api/stripe_webhook.py`

## Features

### Supported Webhook Events

1. **customer.subscription.created** - Creates new subscription and updates user tier
2. **customer.subscription.updated** - Handles subscription changes (upgrades, downgrades, renewals)
3. **customer.subscription.deleted** - Cancels subscription and downgrades to free tier
4. **invoice.payment_succeeded** - Confirms successful payment and activates subscription
5. **invoice.payment_failed** - Handles payment failures with automatic downgrade after retries
6. **customer.subscription.trial_will_end** - Notifies when trial is ending (3 days before)

### Key Capabilities

- ✅ Stripe webhook signature verification
- ✅ Automatic user tier management (free, starter, professional, enterprise)
- ✅ Payment failure handling with grace period (4 retry attempts)
- ✅ Subscription end date tracking
- ✅ Comprehensive logging for all events
- ✅ Error handling with rollback support
- ✅ Price ID to tier mapping
- ✅ Database transaction safety

## Price ID Mapping

The webhook handler maps Stripe price IDs to subscription tiers:

```python
PRICE_ID_TO_TIER = {
    "price_1SWeAqHkVI5icjTlYgQujATs": "free",        # Free Monthly
    "price_1SWeAsHkVI5icjTl9GZ8Ciui": "starter",     # Starter Monthly
    "price_1SWeAtHkVI5icjTl8UxSYNYX": "professional", # Professional Monthly
    "price_1SWeAvHkVI5icjTlF8eFK8kh": "enterprise",   # Enterprise Monthly
}
```

## Integration Steps

### 1. Add to Main Application

Add the webhook router to your main FastAPI application:

```python
# backend/main.py
from api.stripe_webhook import router as stripe_webhook_router

app = FastAPI(title="nabavkidata.com")

# Add stripe webhook router
app.include_router(stripe_webhook_router)
```

### 2. Environment Configuration

Add these environment variables to your `.env` file:

```bash
# Stripe Configuration
STRIPE_SECRET_KEY=sk_live_your_secret_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret_here
FRONTEND_URL=https://nabavkidata.com
```

### 3. Configure Stripe Webhook

1. Go to your Stripe Dashboard: https://dashboard.stripe.com/webhooks
2. Click "Add endpoint"
3. Enter your webhook URL: `https://yourdomain.com/stripe/webhook`
4. Select the following events:
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
   - `customer.subscription.trial_will_end`
5. Copy the webhook signing secret and add it to your environment as `STRIPE_WEBHOOK_SECRET`

## API Endpoints

### POST /stripe/webhook

Main webhook endpoint that receives all Stripe events.

**Headers:**
- `stripe-signature`: Stripe webhook signature (automatically sent by Stripe)

**Request Body:** Stripe event object (JSON)

**Response:**
```json
{
  "status": "success",
  "event_type": "customer.subscription.created",
  "event_id": "evt_1234567890",
  "processed_at": "2025-11-23T10:30:00.000Z"
}
```

### GET /stripe/webhook/health

Health check endpoint to verify webhook configuration.

**Response:**
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

## Event Handling Details

### Subscription Created

When a new subscription is created:
1. Finds user by Stripe customer ID
2. Determines subscription tier from price ID or metadata
3. Creates subscription record in database
4. Updates user's `subscription_tier` field
5. Logs successful creation

### Subscription Updated

When a subscription is updated:
1. Finds existing subscription by Stripe ID
2. Determines new tier (in case of plan change)
3. Updates subscription details (status, dates, cancellation info)
4. Updates user tier if subscription is active/trialing
5. Downgrades to free if subscription is canceled/unpaid

### Subscription Deleted

When a subscription is cancelled:
1. Finds subscription by Stripe ID
2. Updates subscription status to "canceled"
3. Sets cancellation timestamp
4. Downgrades user to "free" tier immediately

### Payment Succeeded

When a payment is successful:
1. Finds user by customer ID
2. Ensures subscription status is "active"
3. Confirms user has correct tier assigned
4. Logs payment details

### Payment Failed

When a payment fails:
1. Finds user by customer ID
2. Marks subscription as "past_due"
3. Tracks attempt count (Stripe retries up to 4 times)
4. After 4th failed attempt: downgrades user to "free" tier
5. Before 4th attempt: keeps tier but marks as past_due

### Trial Will End

When a trial is about to expire:
1. Logs notification event
2. Calculates days remaining
3. Can trigger email notification (integration point)
4. No database changes made

## Database Schema

The webhook handler works with these database models:

### User Model
- `user_id`: UUID primary key
- `email`: User email
- `stripe_customer_id`: Stripe customer ID
- `subscription_tier`: Current tier (free, starter, professional, enterprise)

### Subscription Model
- `subscription_id`: UUID primary key
- `user_id`: Foreign key to User
- `stripe_subscription_id`: Stripe subscription ID
- `stripe_customer_id`: Stripe customer ID
- `tier`: Subscription tier
- `status`: Subscription status (active, canceled, past_due, etc.)
- `current_period_start`: Current billing period start
- `current_period_end`: Current billing period end
- `cancel_at_period_end`: Boolean flag
- `cancelled_at`: Cancellation timestamp

## Security

### Webhook Signature Verification

All webhook requests are verified using Stripe's signature verification:

```python
def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    try:
        stripe.Webhook.construct_event(
            payload, signature, STRIPE_WEBHOOK_SECRET
        )
        return True
    except stripe.error.SignatureVerificationError:
        return False
```

**Important:** The webhook secret (`STRIPE_WEBHOOK_SECRET`) must be configured for production use. In development mode (when not set), verification is skipped with a warning log.

## Logging

All events are logged with detailed information:

- **INFO**: Successful event processing
- **WARNING**: Missing users, unhandled events, payment failures
- **ERROR**: Processing errors with full stack traces

Example log output:
```
2025-11-23 10:30:00 - stripe_webhook - INFO - Received Stripe webhook event: customer.subscription.created (ID: evt_123)
2025-11-23 10:30:00 - stripe_webhook - INFO - Processing subscription.created: sub_123 for customer: cus_456
2025-11-23 10:30:00 - stripe_webhook - INFO - Found tier in metadata: professional
2025-11-23 10:30:00 - stripe_webhook - INFO - Successfully created subscription for user abc-def-ghi with tier: professional
```

## Error Handling

The webhook handler implements robust error handling:

1. **Signature Verification Errors**: Returns 400 Bad Request
2. **Payload Parsing Errors**: Returns 400 Bad Request
3. **Database Errors**: Automatic rollback with error logging
4. **Processing Errors**: Returns 200 OK with error details (prevents Stripe retries)

## Testing

### Local Testing with Stripe CLI

1. Install Stripe CLI: https://stripe.com/docs/stripe-cli

2. Login to Stripe:
   ```bash
   stripe login
   ```

3. Forward webhooks to local server:
   ```bash
   stripe listen --forward-to localhost:8000/stripe/webhook
   ```

4. Trigger test events:
   ```bash
   # Test subscription created
   stripe trigger customer.subscription.created

   # Test payment succeeded
   stripe trigger invoice.payment_succeeded

   # Test payment failed
   stripe trigger invoice.payment_failed
   ```

### Manual Testing

Test the health endpoint:
```bash
curl http://localhost:8000/stripe/webhook/health
```

## Monitoring

Monitor webhook processing in your logs:

```bash
# View recent webhook events
tail -f logs/app.log | grep "stripe_webhook"

# Check for errors
grep "ERROR" logs/app.log | grep "stripe_webhook"

# Monitor payment failures
grep "payment_failed" logs/app.log
```

## Troubleshooting

### Webhook Not Receiving Events

1. Verify webhook URL is publicly accessible
2. Check Stripe Dashboard for webhook delivery status
3. Ensure HTTPS is configured (required for production)
4. Verify no firewall blocking Stripe IPs

### Signature Verification Failing

1. Verify `STRIPE_WEBHOOK_SECRET` is correct
2. Check that raw request body is used for verification
3. Ensure no middleware modifying request body

### User Not Found

1. Verify user has `stripe_customer_id` set
2. Check customer ID matches between Stripe and database
3. Ensure customer was created during checkout

### Tier Not Updating

1. Check price ID mapping in `PRICE_ID_TO_TIER`
2. Verify subscription metadata includes `tier` field
3. Check subscription status is "active" or "trialing"

## Best Practices

1. **Always verify webhook signatures** in production
2. **Log all webhook events** for audit trail
3. **Handle errors gracefully** to prevent infinite retries
4. **Use database transactions** to ensure data consistency
5. **Monitor webhook delivery** in Stripe Dashboard
6. **Test with Stripe CLI** before deploying to production
7. **Keep price ID mappings up to date** when adding new plans

## Support

For issues or questions:
- Check Stripe Dashboard webhook logs
- Review application logs for error details
- Contact Stripe support for webhook delivery issues
- Refer to Stripe webhook documentation: https://stripe.com/docs/webhooks

## Version History

- **v1.0.0** (2025-11-23): Initial implementation with all core events
  - Subscription lifecycle management
  - Payment handling
  - Automatic tier updates
  - Comprehensive logging

## License

Copyright 2025 nabavkidata.com. All rights reserved.
