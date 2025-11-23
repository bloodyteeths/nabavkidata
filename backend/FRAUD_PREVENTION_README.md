# Fraud Prevention System Documentation

A comprehensive fraud detection and prevention system for nabavkidata.com that protects the free tier from abuse while allowing legitimate users to access the service.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Usage](#usage)
- [API Reference](#api-reference)
- [Database Schema](#database-schema)
- [Configuration](#configuration)
- [Best Practices](#best-practices)

## Overview

The Fraud Prevention System is designed to:

1. **Detect duplicate accounts** through multiple fingerprinting techniques
2. **Enforce rate limits** based on subscription tiers
3. **Block abusive behavior** such as VPN usage on free tier
4. **Prevent temporary email usage** for registration
5. **Track suspicious activities** for security monitoring
6. **Enforce trial period limits** for free tier users

## Features

### 1. Duplicate Account Detection

Detects duplicate accounts using:

- **Email Similarity Detection**
  - Detects variations like `test@gmail.com`, `test1@gmail.com`, `test+1@gmail.com`
  - Uses Levenshtein distance for fuzzy matching
  - Confidence scoring (0-100)

- **IP Address Tracking**
  - Detects multiple accounts from same IP
  - Tracks IP history across all accounts

- **Device Fingerprinting**
  - Unique device identification
  - Browser and OS detection
  - Screen resolution and timezone tracking

- **Browser Fingerprinting**
  - Canvas fingerprinting
  - WebGL fingerprinting
  - Platform detection

- **Payment Method Fingerprinting**
  - Hashed card information
  - Detects same payment method across accounts

### 2. Rate Limiting

Tier-based query limits:

| Tier | Daily Queries | Monthly Queries | Trial Days | VPN Allowed |
|------|--------------|----------------|------------|-------------|
| FREE | 3 | 90 | 14 | No |
| STARTER | 5 | 150 | 0 | Yes |
| PROFESSIONAL | 20 | 600 | 0 | Yes |
| ENTERPRISE | Unlimited | Unlimited | 0 | Yes |

**Free Tier Restrictions:**
- Maximum 3 AI queries per day
- 14-day trial period only
- After 14 days, users MUST upgrade
- VPN/Proxy usage blocked
- Automatic redirect to `/pricing` when blocked

### 3. Email Validation

Blocks temporary/disposable email services:

- Built-in list of 20+ common disposable email domains
- Database-backed blocking system
- Custom domain blocking support
- Real-time validation during registration

### 4. IP Blocking

- Manual and automatic IP blocking
- VPN/Proxy/Tor detection
- Temporary and permanent blocks
- IP range blocking support

### 5. Risk Scoring

Calculates fraud risk (0-100):

- **0-29**: Low risk (allow)
- **30-59**: Medium risk (monitor)
- **60-79**: High risk (flag)
- **80-100**: Critical risk (block)

Factors that increase risk score:
- Tor usage: +50
- VPN usage: +30
- Proxy usage: +25
- Missing fingerprint data: +10

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     API Request                              │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              Fraud Prevention Middleware                     │
│  ├── Extract IP, User Agent, Device Fingerprint            │
│  └── Check IP Blocking                                       │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│           Comprehensive Fraud Check                          │
│  ├── Track Fingerprint                                       │
│  ├── Validate Email (if registration)                       │
│  ├── Check VPN/Proxy (if free tier)                         │
│  ├── Check Rate Limits                                       │
│  ├── Detect Duplicates                                       │
│  └── Log Suspicious Activity                                 │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
        ▼             ▼             ▼
    ┌───────┐   ┌─────────┐   ┌────────┐
    │ Allow │   │  Block  │   │  Flag  │
    └───────┘   └─────────┘   └────────┘
                     │
                     ▼
              ┌─────────────┐
              │  Redirect   │
              │ to /pricing │
              └─────────────┘
```

## Installation

### 1. Database Migration

Run the SQL migration to create required tables:

```bash
psql -U your_user -d nabavkidata < migrations/add_fraud_prevention_tables.sql
```

Or if using Alembic:

```bash
alembic revision --autogenerate -m "Add fraud prevention tables"
alembic upgrade head
```

### 2. Update Requirements

The fraud prevention system uses only built-in Python libraries and existing dependencies. No additional packages needed!

### 3. Import Models

Add to your main application:

```python
# In your models/__init__.py or main.py
from models_fraud import (
    FraudDetection, RateLimit, SuspiciousActivity,
    BlockedEmail, BlockedIP, DuplicateAccountDetection,
    PaymentFingerprint
)
```

## Usage

### Basic Integration

#### 1. Registration Flow

```python
from services.fraud_prevention import (
    perform_fraud_check, is_email_allowed, initialize_rate_limit
)

@app.post("/api/auth/register")
async def register(
    email: str,
    password: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    # Validate email
    email_allowed, email_reason = await is_email_allowed(db, email)
    if not email_allowed:
        raise HTTPException(400, detail=email_reason)

    # Create user
    user = await create_user(db, email, password)

    # Initialize rate limit
    await initialize_rate_limit(db, user.user_id, "free")

    # Perform fraud check
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "")
    device_fingerprint = request.headers.get("X-Device-Fingerprint", "")

    is_allowed, reason, details = await perform_fraud_check(
        db=db,
        user=user,
        ip_address=client_ip,
        device_fingerprint=device_fingerprint,
        user_agent=user_agent,
        check_type="registration"
    )

    if not is_allowed:
        # Log and potentially flag account
        logger.warning(f"Suspicious registration: {email} - {reason}")

    return {"user": user, "message": "Registration successful"}
```

#### 2. Query Execution Flow

```python
from services.fraud_prevention import perform_fraud_check

@app.post("/api/ai/query")
async def execute_query(
    question: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Extract request info
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "")
    device_fingerprint = request.headers.get("X-Device-Fingerprint", "")

    # Perform fraud check
    is_allowed, reason, details = await perform_fraud_check(
        db=db,
        user=current_user,
        ip_address=client_ip,
        device_fingerprint=device_fingerprint,
        user_agent=user_agent,
        check_type="query"
    )

    if not is_allowed:
        return JSONResponse(
            status_code=403,
            content={
                "error": "Access Denied",
                "message": reason,
                "redirect_to": details.get("redirect_to", "/pricing"),
                "details": details
            }
        )

    # Execute query
    result = await ai_service.query(question)

    return {"result": result, "limit_info": details}
```

#### 3. Middleware Integration

Add to your `main.py`:

```python
from services.fraud_prevention import is_ip_blocked

@app.middleware("http")
async def fraud_prevention_middleware(request: Request, call_next):
    # Skip for public paths
    public_paths = ["/api/docs", "/api/health", "/api/auth/login"]
    if any(request.url.path.startswith(path) for path in public_paths):
        return await call_next(request)

    # Get client IP
    client_ip = get_client_ip(request)

    # Check if IP is blocked
    async with AsyncSessionLocal() as db:
        is_blocked, reason = await is_ip_blocked(db, client_ip)

        if is_blocked:
            return JSONResponse(
                status_code=403,
                content={
                    "error": "Access Denied",
                    "message": reason or "Your IP has been blocked",
                    "redirect_to": "/blocked"
                }
            )

    response = await call_next(request)
    return response
```

### Frontend Integration

#### JavaScript Fingerprinting

```javascript
// Generate device fingerprint
async function generateFingerprint() {
  const data = {
    screen_resolution: `${screen.width}x${screen.height}`,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    language: navigator.language,
    platform: navigator.platform,
    user_agent: navigator.userAgent
  };

  // Generate canvas fingerprint
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  ctx.textBaseline = 'top';
  ctx.font = '14px Arial';
  ctx.fillText('Fingerprint', 2, 2);
  data.canvas_fingerprint = canvas.toDataURL();

  // Generate device hash
  const dataString = JSON.stringify(data);
  const hashBuffer = await crypto.subtle.digest(
    'SHA-256',
    new TextEncoder().encode(dataString)
  );
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');

  return {
    device_fingerprint: hashHex,
    ...data
  };
}

// Use in API calls
async function makeQuery(question) {
  const fingerprint = await generateFingerprint();

  const response = await fetch('/api/ai/query', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Device-Fingerprint': fingerprint.device_fingerprint
    },
    body: JSON.stringify({
      question,
      fingerprint_data: fingerprint
    })
  });

  const result = await response.json();

  if (response.status === 403) {
    // Redirect to pricing or show upgrade modal
    if (result.redirect_to) {
      window.location.href = result.redirect_to;
    }
  }

  return result;
}
```

## API Reference

### Endpoints

#### POST `/api/fraud/check`

Perform comprehensive fraud check.

**Request:**
```json
{
  "ip_address": "192.168.1.1",
  "user_agent": "Mozilla/5.0...",
  "fingerprint_data": {
    "device_fingerprint": "abc123...",
    "screen_resolution": "1920x1080",
    "timezone": "Europe/Skopje"
  },
  "check_type": "query"
}
```

**Response:**
```json
{
  "is_allowed": true,
  "block_reason": null,
  "redirect_to": null,
  "details": {
    "tier": "free",
    "daily_limit": 3,
    "daily_used": 1,
    "daily_remaining": 2
  },
  "risk_score": 15
}
```

#### GET `/api/fraud/rate-limit`

Get current rate limit status.

**Response:**
```json
{
  "user_id": "uuid",
  "subscription_tier": "free",
  "daily_query_count": 1,
  "daily_limit": 3,
  "daily_remaining": 2,
  "trial_end_date": "2024-01-15T00:00:00Z",
  "trial_expired": false,
  "is_blocked": false
}
```

#### GET `/api/fraud/tier-limits`

Get all tier limits (public endpoint).

#### GET `/api/fraud/summary`

Get fraud detection summary for current user.

#### POST `/api/fraud/validate-email`

Validate if email is allowed.

#### POST `/api/fraud/validate-ip`

Check if IP is blocked.

## Database Schema

### Tables Created

1. **fraud_detection** - Fingerprint tracking
2. **rate_limits** - Query limits per user
3. **suspicious_activities** - Security event log
4. **blocked_emails** - Blocked email domains
5. **blocked_ips** - Blocked IP addresses
6. **duplicate_account_detection** - Duplicate account links
7. **payment_fingerprints** - Payment method tracking

See `migrations/add_fraud_prevention_tables.sql` for full schema.

## Configuration

### Environment Variables

```bash
# In your .env file

# Rate limit settings (optional - defaults shown)
FREE_TIER_DAILY_LIMIT=3
FREE_TIER_TRIAL_DAYS=14
STARTER_TIER_DAILY_LIMIT=5
PROFESSIONAL_TIER_DAILY_LIMIT=20
```

### Customizing Tier Limits

Edit `services/fraud_prevention.py`:

```python
TIER_LIMITS = {
    "free": {
        "daily_queries": 3,
        "monthly_queries": 90,
        "trial_days": 14,
        "allow_vpn": False,
    },
    # ... other tiers
}
```

## Best Practices

### 1. Regular Monitoring

Monitor suspicious activities:

```python
# Daily cron job
@scheduler.scheduled_job('cron', hour=0)
async def monitor_fraud():
    async with AsyncSessionLocal() as db:
        # Get unresolved high-severity activities
        result = await db.execute(
            select(SuspiciousActivity)
            .where(
                and_(
                    SuspiciousActivity.is_resolved == False,
                    SuspiciousActivity.severity.in_(['high', 'critical'])
                )
            )
        )
        activities = result.scalars().all()

        # Send alerts to admins
        if activities:
            await send_admin_alert(f"Found {len(activities)} unresolved high-risk activities")
```

### 2. False Positive Handling

Allow admins to mark false positives:

```python
async def mark_false_positive(
    db: AsyncSession,
    detection_id: UUID,
    admin_user_id: UUID
):
    result = await db.execute(
        select(DuplicateAccountDetection)
        .where(DuplicateAccountDetection.detection_id == detection_id)
    )
    detection = result.scalar_one_or_none()

    if detection:
        detection.is_false_positive = True
        detection.reviewed_at = datetime.utcnow()
        detection.reviewed_by = str(admin_user_id)
        await db.commit()
```

### 3. Gradual Enforcement

Start with monitoring before strict blocking:

```python
# Phase 1: Log only
if not is_allowed:
    await log_suspicious_activity(...)
    # Still allow the action
    return True, None, details

# Phase 2: Warn users
if not is_allowed:
    return True, "Warning: suspicious activity detected", details

# Phase 3: Strict enforcement
if not is_allowed:
    return False, block_reason, details
```

### 4. User Communication

Provide clear messages:

```python
BLOCK_MESSAGES = {
    "trial_expired": {
        "title": "Free Trial Expired",
        "message": "Your 14-day free trial has ended. Upgrade to continue using our AI-powered search.",
        "action": "View Pricing",
        "redirect": "/pricing"
    },
    "rate_limit": {
        "title": "Daily Limit Reached",
        "message": "You've used all 3 daily queries. Upgrade for more queries or wait until tomorrow.",
        "action": "Upgrade Now",
        "redirect": "/pricing"
    },
    "vpn_blocked": {
        "title": "VPN Detected",
        "message": "VPN usage is not allowed on the free tier. Please disable your VPN or upgrade to a paid plan.",
        "action": "Learn More",
        "redirect": "/pricing"
    }
}
```

## Troubleshooting

### Issue: Users blocked incorrectly

**Solution:** Check duplicate account detection confidence scores. Lower the threshold if needed:

```python
high_confidence_duplicates = [d for d in duplicates if d.confidence_score >= 90]  # Instead of 80
```

### Issue: Legitimate VPN users blocked

**Solution:** Allow manual whitelisting:

```python
WHITELISTED_IPS = ["1.2.3.4", "5.6.7.8"]

if ip_address in WHITELISTED_IPS:
    return True, None, details
```

### Issue: Trial period not expiring

**Solution:** Run cleanup cron job:

```python
@scheduler.scheduled_job('cron', hour=0)
async def expire_trials():
    async with AsyncSessionLocal() as db:
        now = datetime.utcnow()
        await db.execute(
            update(RateLimit)
            .where(
                and_(
                    RateLimit.trial_end_date < now,
                    RateLimit.is_blocked == False,
                    RateLimit.subscription_tier == 'free'
                )
            )
            .values(
                is_blocked=True,
                block_reason="Free trial expired. Please upgrade.",
                blocked_at=now
            )
        )
        await db.commit()
```

## Security Considerations

1. **Never expose internal risk scores** to users
2. **Use HTTPS** for all fingerprinting data
3. **Rotate detection algorithms** periodically
4. **Monitor for circumvention attempts**
5. **Rate limit API endpoints** themselves
6. **Encrypt sensitive fingerprint data** at rest
7. **Regularly update disposable email list**
8. **Use proper admin authentication** for management endpoints

## Support

For issues or questions:
- Check logs in `suspicious_activities` table
- Review fraud detection summary for users
- Contact: security@nabavkidata.com

---

**Version:** 1.0.0
**Last Updated:** 2024-01-01
**License:** Proprietary
