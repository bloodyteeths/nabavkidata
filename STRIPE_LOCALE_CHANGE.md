# Stripe Checkout Language Change

**Date:** 2025-11-23
**Status:** ✅ COMPLETED
**Change:** Turkish → Macedonian

---

## Summary

Changed the Stripe Checkout page language from Turkish to Macedonian by adding the `locale='mk'` parameter to the Stripe Checkout Session creation.

---

## Changes Made

### File Modified
**`backend/services/billing_service.py`**

### Code Change
```python
# Before (line 112-137):
session = self.stripe.checkout.Session.create(
    customer_email=email,
    client_reference_id=user_id,
    mode='subscription',
    payment_method_types=['card'],
    line_items=[{
        'price': price_id,
        'quantity': 1
    }],
    success_url=success_url,
    cancel_url=cancel_url,
    # No locale parameter
    metadata={...},
    ...
)

# After (line 112-138):
session = self.stripe.checkout.Session.create(
    customer_email=email,
    client_reference_id=user_id,
    mode='subscription',
    payment_method_types=['card'],
    line_items=[{
        'price': price_id,
        'quantity': 1
    }],
    success_url=success_url,
    cancel_url=cancel_url,
    locale='mk',  # Macedonian language ← ADDED
    metadata={...},
    ...
)
```

---

## Deployment

### 1. Local Changes
```bash
✅ Modified backend/services/billing_service.py
✅ Added locale='mk' parameter
✅ Committed to git
✅ Pushed to GitHub
```

### 2. Production Deployment
```bash
✅ Uploaded file to EC2: /home/ubuntu/nabavkidata/backend/services/billing_service.py
✅ Restarted backend service: nabavkidata-backend
✅ Service status: Active (running)
✅ Verified locale='mk' in deployed file
```

### 3. Git Commit
```
Commit: 859b011
Message: fix: Change Stripe checkout language from Turkish to Macedonian
Branch: main
Status: Pushed to origin
```

---

## Testing

### How to Test

1. **Create a checkout session:**
   ```bash
   curl -X POST https://nabavkidata.com/api/billing/checkout \
     -H "Authorization: Bearer <your_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "tier": "starter",
       "interval": "monthly"
     }'
   ```

2. **Open the returned `checkout_url` in a browser**

3. **Verify the Stripe Checkout page is in Macedonian:**
   - Page title should be in Macedonian
   - Form labels should be in Macedonian
   - Button text should be in Macedonian
   - Error messages should be in Macedonian

### Expected Result
The Stripe Checkout page should now display in **Macedonian (mk)** instead of Turkish.

---

## Supported Stripe Locales

Stripe supports the following locales. You can change to any of these if needed:

- `auto` - Automatically detect based on browser settings
- `en` - English
- `mk` - **Macedonian** (currently set)
- `tr` - Turkish
- `de` - German
- `es` - Spanish
- `fr` - French
- `it` - Italian
- `nl` - Dutch
- `pl` - Polish
- `pt` - Portuguese
- `ru` - Russian
- `sv` - Swedish
- And many more...

**Full list:** https://stripe.com/docs/api/checkout/sessions/create#create_checkout_session-locale

---

## Rollback Instructions

If you need to change the language back or to a different locale:

1. **Edit the file on EC2:**
   ```bash
   ssh -i ~/.ssh/nabavki-key.pem ubuntu@3.120.26.153
   nano /home/ubuntu/nabavkidata/backend/services/billing_service.py
   ```

2. **Find line 123 and change:**
   ```python
   # For Turkish:
   locale='tr',

   # For auto-detect:
   locale='auto',

   # For English:
   locale='en',
   ```

3. **Restart the backend:**
   ```bash
   sudo systemctl restart nabavkidata-backend
   ```

---

## Additional Notes

### Why This Change?
- The Stripe Checkout page was displaying in Turkish
- The target audience is Macedonian users
- Macedonian language provides better user experience

### Impact
- ✅ No breaking changes
- ✅ No database changes required
- ✅ No frontend changes required
- ✅ Only affects new checkout sessions
- ✅ Existing subscriptions unaffected

### Stripe Billing Portal
**Note:** The Stripe Customer Portal (for managing subscriptions) does NOT currently have a locale parameter. It automatically detects the language from the browser settings.

If you need to customize the billing portal language, you would need to:
1. Configure it in Stripe Dashboard → Settings → Billing → Customer Portal
2. Or use Stripe's hosted invoice links which support localization

---

## Verification

### Production Verification
```bash
✅ File updated: /home/ubuntu/nabavkidata/backend/services/billing_service.py
✅ Backend restarted: 2025-11-23 19:23:33 UTC
✅ Service status: Active (running)
✅ Locale parameter: locale='mk'
```

### Git Status
```bash
✅ Committed: 859b011
✅ Pushed to: origin/main
✅ Branch: main
```

---

## Reference

**Stripe Checkout Session API:**
https://stripe.com/docs/api/checkout/sessions/create

**Locale Parameter:**
https://stripe.com/docs/api/checkout/sessions/create#create_checkout_session-locale

**Supported Locales:**
https://stripe.com/docs/payments/checkout/customization#supported-languages

---

**Last Updated:** 2025-11-23 19:23:33 UTC
**Status:** ✅ COMPLETED AND DEPLOYED
