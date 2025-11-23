# Fraud Prevention System - Quick Start Guide

Get the fraud prevention system up and running in 5 minutes!

## Quick Setup (5 Minutes)

### Step 1: Run Database Migration (1 min)

```bash
# Connect to your PostgreSQL database
psql -U postgres -d nabavkidata

# Run the migration script
\i migrations/add_fraud_prevention_tables.sql

# Verify tables were created
\dt fraud*
\dt rate*
\dt suspicious*
\dt blocked*
\dt duplicate*
\dt payment*
```

You should see 7 new tables created.

### Step 2: Import Models (30 seconds)

Add to your main application file or `models/__init__.py`:

```python
# Import fraud prevention models
from models_fraud import (
    FraudDetection,
    RateLimit,
    SuspiciousActivity,
    BlockedEmail,
    BlockedIP,
    DuplicateAccountDetection,
    PaymentFingerprint
)
```

### Step 3: Add Middleware (2 min)

Add to your `main.py`:

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from services.fraud_prevention import is_ip_blocked
from database import AsyncSessionLocal

app = FastAPI()

# Helper to get client IP
def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

# Fraud prevention middleware
@app.middleware("http")
async def fraud_middleware(request: Request, call_next):
    # Skip for public endpoints
    public_paths = ["/api/docs", "/api/health", "/api/auth/login"]
    if any(request.url.path.startswith(path) for path in public_paths):
        return await call_next(request)

    # Check IP blocking
    client_ip = get_client_ip(request)
    async with AsyncSessionLocal() as db:
        is_blocked, reason = await is_ip_blocked(db, client_ip)
        if is_blocked:
            return JSONResponse(
                status_code=403,
                content={
                    "error": "Access Denied",
                    "message": reason,
                    "redirect_to": "/blocked"
                }
            )

    return await call_next(request)
```

### Step 4: Protect Your Endpoints (1.5 min)

#### A) Registration Endpoint

```python
from services.fraud_prevention import is_email_allowed, initialize_rate_limit

@app.post("/api/auth/register")
async def register(
    email: str,
    password: str,
    db: AsyncSession = Depends(get_db)
):
    # 1. Check email validity
    email_allowed, reason = await is_email_allowed(db, email)
    if not email_allowed:
        raise HTTPException(400, detail=reason)

    # 2. Create user (your existing logic)
    user = await create_user(db, email, password)

    # 3. Initialize rate limiting
    await initialize_rate_limit(db, user.user_id, "free")

    return {"message": "Registration successful"}
```

#### B) Query Endpoint (AI Queries)

```python
from services.fraud_prevention import perform_fraud_check

@app.post("/api/ai/query")
async def execute_query(
    question: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # 1. Perform fraud check
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "")
    device_fingerprint = request.headers.get("X-Device-Fingerprint", "")

    is_allowed, reason, details = await perform_fraud_check(
        db=db,
        user=current_user,
        ip_address=client_ip,
        device_fingerprint=device_fingerprint,
        user_agent=user_agent,
        check_type="query"
    )

    # 2. Block if not allowed
    if not is_allowed:
        return JSONResponse(
            status_code=403,
            content={
                "error": "Access Denied",
                "message": reason,
                "redirect_to": details.get("redirect_to", "/pricing")
            }
        )

    # 3. Execute query (your existing logic)
    result = await ai_service.query(question)

    return {"result": result, "remaining_queries": details.get("daily_remaining")}
```

## Frontend Integration (5 Minutes)

### Step 1: Add Fingerprinting Script

Create `public/js/fingerprint.js`:

```javascript
// Generate device fingerprint
export async function generateFingerprint() {
  const data = {
    screen_resolution: `${screen.width}x${screen.height}`,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    language: navigator.language,
    platform: navigator.platform
  };

  // Simple hash generation
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
```

### Step 2: Use in API Calls

```javascript
import { generateFingerprint } from './fingerprint.js';

async function makeQuery(question) {
  const fingerprint = await generateFingerprint();

  const response = await fetch('/api/ai/query', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
      'X-Device-Fingerprint': fingerprint.device_fingerprint
    },
    body: JSON.stringify({
      question,
      fingerprint_data: fingerprint
    })
  });

  const result = await response.json();

  if (response.status === 403) {
    // User blocked - redirect to pricing
    window.location.href = result.redirect_to || '/pricing';
    return;
  }

  return result;
}
```

## Testing (2 Minutes)

### Manual Testing

1. **Test Email Validation:**
```bash
curl -X POST http://localhost:8000/api/fraud/validate-email \
  -H "Content-Type: application/json" \
  -d '{"email": "test@tempmail.com"}'

# Should return: {"is_allowed": false, "reason": "Temporary email domain not allowed"}
```

2. **Test Rate Limiting:**
```bash
# Make 4 queries in a row (should block on 4th for free tier)
for i in {1..4}; do
  curl -X POST http://localhost:8000/api/ai/query \
    -H "Authorization: Bearer YOUR_TOKEN" \
    -d '{"question": "test"}';
done

# 4th request should return 403 with upgrade message
```

3. **Check Your Rate Limit:**
```bash
curl http://localhost:8000/api/fraud/rate-limit \
  -H "Authorization: Bearer YOUR_TOKEN"

# Should show: {"daily_used": 3, "daily_limit": 3, "daily_remaining": 0}
```

### Automated Testing

```bash
# Run tests
pytest tests/test_fraud_prevention.py -v

# Run with coverage
pytest tests/test_fraud_prevention.py --cov=services.fraud_prevention
```

## Monitoring Dashboard (Optional, 10 Minutes)

### Simple Admin Dashboard

Create `admin_dashboard.html`:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Fraud Prevention Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .metric { padding: 15px; margin: 10px; border: 1px solid #ddd; border-radius: 5px; }
        .high-risk { background-color: #ffebee; }
        .medium-risk { background-color: #fff9c4; }
        .low-risk { background-color: #e8f5e9; }
    </style>
</head>
<body>
    <h1>Fraud Prevention Dashboard</h1>

    <div id="stats"></div>

    <script>
        async function loadStats() {
            const response = await fetch('/api/fraud/admin/stats', {
                headers: { 'Authorization': 'Bearer ADMIN_TOKEN' }
            });
            const data = await response.json();

            document.getElementById('stats').innerHTML = `
                <div class="metric">
                    <h3>Today's Activity</h3>
                    <p>Suspicious Activities: ${data.suspicious_count}</p>
                    <p>Blocked IPs: ${data.blocked_ips}</p>
                    <p>Duplicate Accounts Detected: ${data.duplicates_today}</p>
                </div>

                <div class="metric ${data.high_risk_users > 5 ? 'high-risk' : 'low-risk'}">
                    <h3>Risk Summary</h3>
                    <p>High Risk Users: ${data.high_risk_users}</p>
                    <p>VPN Usage Detected: ${data.vpn_usage_count}</p>
                </div>
            `;
        }

        loadStats();
        setInterval(loadStats, 60000); // Refresh every minute
    </script>
</body>
</html>
```

## Common Issues & Solutions

### Issue 1: Fingerprint not being sent

**Problem:** Frontend not sending device fingerprint

**Solution:**
```javascript
// Make sure header is set
headers: {
  'X-Device-Fingerprint': fingerprint.device_fingerprint  // Add this!
}
```

### Issue 2: All users being blocked

**Problem:** Too aggressive settings

**Solution:**
```python
# In services/fraud_prevention.py, adjust thresholds
RISK_THRESHOLDS = {
    "low": 0,
    "medium": 40,      # Increase from 30
    "high": 70,        # Increase from 60
    "critical": 90     # Increase from 80
}
```

### Issue 3: Trial not expiring

**Problem:** Trial expiration not checked

**Solution:** Add a daily cron job:
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('cron', hour=0)
async def expire_trials():
    async with AsyncSessionLocal() as db:
        # Expire trials logic here
        pass

scheduler.start()
```

## Production Checklist

Before going to production:

- [ ] Run database migration on production DB
- [ ] Test with real VPN to verify detection
- [ ] Set up monitoring alerts for high-risk activities
- [ ] Configure email notifications for critical events
- [ ] Add admin dashboard for fraud monitoring
- [ ] Test rate limiting with real user flows
- [ ] Verify trial expiration works correctly
- [ ] Set up log aggregation for suspicious activities
- [ ] Review and adjust risk score thresholds
- [ ] Test payment fingerprinting (if using payments)

## Performance Optimization

For high-traffic sites:

1. **Add Redis caching:**
```python
import redis
redis_client = redis.Redis()

# Cache rate limit checks
rate_limit_key = f"rate_limit:{user_id}"
cached = redis_client.get(rate_limit_key)
if cached:
    return cached
```

2. **Use connection pooling:**
```python
# Already configured in database.py
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,      # Adjust based on load
    max_overflow=40
)
```

3. **Add indexes:**
```sql
-- Already included in migration script
-- Verify they exist:
SELECT * FROM pg_indexes WHERE tablename LIKE '%fraud%';
```

## Next Steps

1. **Monitor for 1 week** - Watch for false positives
2. **Adjust thresholds** - Fine-tune based on your user base
3. **Add ML detection** - Use patterns to improve detection
4. **Integrate payment tracking** - Track payment method duplicates
5. **Build admin tools** - Dashboard for reviewing suspicious activity

## Support Resources

- **Full Documentation:** `FRAUD_PREVENTION_README.md`
- **API Reference:** `api/fraud_endpoints.py`
- **Database Schema:** `migrations/add_fraud_prevention_tables.sql`
- **Service Code:** `services/fraud_prevention.py`
- **Tests:** `tests/test_fraud_prevention.py`

## Questions?

Common questions:

**Q: How do I whitelist a user?**
A: Update their rate_limit record:
```sql
UPDATE rate_limits SET is_blocked = false WHERE user_id = 'USER_UUID';
```

**Q: How do I add more disposable email domains?**
A: Insert into blocked_emails table:
```sql
INSERT INTO blocked_emails (email_pattern, block_type, reason)
VALUES ('newdomain.com', 'disposable', 'Temporary email service');
```

**Q: Can I customize tier limits?**
A: Yes! Edit `TIER_LIMITS` in `services/fraud_prevention.py`

**Q: How do I view suspicious activities?**
A: Query the database:
```sql
SELECT * FROM suspicious_activities
WHERE is_resolved = false
ORDER BY detected_at DESC;
```

---

**You're all set! The fraud prevention system is now protecting your application.**

Start monitoring and adjust settings based on your needs. Good luck!
