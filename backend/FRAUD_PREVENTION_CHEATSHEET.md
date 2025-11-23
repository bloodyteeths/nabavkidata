# Fraud Prevention System - Quick Reference

## One-Page Cheat Sheet

### Installation (One Command)

```bash
psql -U postgres -d nabavkidata < migrations/add_fraud_prevention_tables.sql
```

### Basic Usage

#### Check if user can make a query

```python
from services.fraud_prevention import perform_fraud_check

is_allowed, reason, details = await perform_fraud_check(
    db=db,
    user=current_user,
    ip_address="192.168.1.1",
    device_fingerprint="abc123",
    user_agent="Mozilla/5.0...",
    check_type="query"
)

if not is_allowed:
    return 403, {"message": reason, "redirect_to": "/pricing"}
```

#### Validate email during registration

```python
from services.fraud_prevention import is_email_allowed

is_allowed, reason = await is_email_allowed(db, "user@example.com")
if not is_allowed:
    raise HTTPException(400, detail=reason)
```

#### Initialize new user rate limit

```python
from services.fraud_prevention import initialize_rate_limit

await initialize_rate_limit(db, user_id, "free")
```

### Tier Limits Quick Reference

| Tier | Daily | Trial | VPN | Action After Limit |
|------|-------|-------|-----|-------------------|
| FREE | 3 | 14d | ❌ | Redirect /pricing |
| STARTER | 5 | No | ✅ | Redirect /pricing |
| PRO | 20 | No | ✅ | Redirect /pricing |
| ENTERPRISE | ∞ | No | ✅ | Never blocked |

### API Endpoints

```bash
# Check rate limit
GET /api/fraud/rate-limit

# Validate email
POST /api/fraud/validate-email
Body: {"email": "test@example.com"}

# Perform fraud check
POST /api/fraud/check
Body: {
  "ip_address": "1.2.3.4",
  "user_agent": "Mozilla...",
  "fingerprint_data": {...}
}
```

### Database Tables

```sql
-- View rate limits
SELECT * FROM rate_limits WHERE user_id = 'UUID';

-- View suspicious activities
SELECT * FROM suspicious_activities WHERE is_resolved = false;

-- View blocked IPs
SELECT * FROM blocked_ips WHERE is_active = true;

-- View duplicate accounts
SELECT * FROM duplicate_account_detection WHERE confidence_score >= 80;

-- Unblock a user
UPDATE rate_limits SET is_blocked = false WHERE user_id = 'UUID';

-- Block an IP
INSERT INTO blocked_ips (ip_address, reason, block_type)
VALUES ('1.2.3.4', 'Suspicious activity', 'manual');

-- Add disposable email domain
INSERT INTO blocked_emails (email_pattern, block_type, reason)
VALUES ('tempmail.com', 'disposable', 'Temporary email service');
```

### Frontend JavaScript

```javascript
// Generate fingerprint
async function getFingerprint() {
  const data = {
    screen_resolution: `${screen.width}x${screen.height}`,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    language: navigator.language,
    platform: navigator.platform
  };

  const str = JSON.stringify(data);
  const buffer = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(str));
  const hash = Array.from(new Uint8Array(buffer))
    .map(b => b.toString(16).padStart(2, '0')).join('');

  return { device_fingerprint: hash, ...data };
}

// Use in API call
const fp = await getFingerprint();
fetch('/api/ai/query', {
  headers: { 'X-Device-Fingerprint': fp.device_fingerprint },
  body: JSON.stringify({ question, fingerprint_data: fp })
});
```

### Common SQL Queries

```sql
-- Daily usage by user
SELECT user_id, daily_query_count, daily_limit, subscription_tier
FROM rate_limits
WHERE daily_query_count > 0
ORDER BY daily_query_count DESC;

-- High risk users
SELECT user_id, risk_score, is_suspicious
FROM fraud_detection
WHERE risk_score >= 60
ORDER BY risk_score DESC;

-- Today's suspicious activities
SELECT activity_type, severity, COUNT(*)
FROM suspicious_activities
WHERE detected_at >= CURRENT_DATE
GROUP BY activity_type, severity;

-- Users with expired trials
SELECT user_id, trial_end_date
FROM rate_limits
WHERE subscription_tier = 'free'
  AND trial_end_date < NOW()
  AND is_blocked = false;

-- Duplicate account clusters
SELECT user_id, COUNT(*) as duplicate_count
FROM duplicate_account_detection
WHERE confidence_score >= 80
GROUP BY user_id
HAVING COUNT(*) > 1;
```

### Configuration Variables

In `services/fraud_prevention.py`:

```python
# Tier limits
TIER_LIMITS["free"]["daily_queries"] = 3
TIER_LIMITS["free"]["trial_days"] = 14

# Risk thresholds
RISK_THRESHOLDS["high"] = 60
RISK_THRESHOLDS["critical"] = 80

# Add disposable email domain
DISPOSABLE_EMAIL_DOMAINS.append("newdomain.com")
```

### Troubleshooting Commands

```bash
# Check if tables exist
psql -d nabavkidata -c "\dt fraud*"

# Count records
psql -d nabavkidata -c "SELECT COUNT(*) FROM rate_limits;"

# View recent blocks
psql -d nabavkidata -c "
  SELECT * FROM rate_limits
  WHERE is_blocked = true
  ORDER BY blocked_at DESC
  LIMIT 10;
"

# Reset user's daily count
psql -d nabavkidata -c "
  UPDATE rate_limits
  SET daily_query_count = 0
  WHERE user_id = 'UUID';
"
```

### Test Commands

```bash
# Run all tests
pytest tests/test_fraud_prevention.py -v

# Run specific test
pytest tests/test_fraud_prevention.py::test_email_similarity_plus_alias

# Run with coverage
pytest tests/test_fraud_prevention.py --cov=services.fraud_prevention
```

### Monitoring Queries

```sql
-- Dashboard stats
SELECT
  (SELECT COUNT(*) FROM rate_limits WHERE is_blocked = true) as blocked_users,
  (SELECT COUNT(*) FROM suspicious_activities WHERE is_resolved = false) as pending_activities,
  (SELECT COUNT(*) FROM duplicate_account_detection WHERE is_confirmed = false) as pending_duplicates,
  (SELECT COUNT(DISTINCT user_id) FROM fraud_detection WHERE is_vpn = true) as vpn_users;

-- Usage by tier
SELECT
  subscription_tier,
  COUNT(*) as user_count,
  AVG(daily_query_count) as avg_queries,
  COUNT(CASE WHEN is_blocked THEN 1 END) as blocked_count
FROM rate_limits
GROUP BY subscription_tier;
```

### Error Messages

Common block reasons and what they mean:

| Message | Cause | Solution |
|---------|-------|----------|
| "Daily query limit reached" | Used all queries | Wait until reset or upgrade |
| "Free trial expired" | 14 days passed | Must upgrade to continue |
| "VPN/Proxy not allowed" | VPN detected on free tier | Disable VPN or upgrade |
| "Temporary email not allowed" | Used disposable email | Use real email address |
| "IP address blocked" | IP blacklisted | Contact support |

### Admin Actions

```python
# Block a user
from services.fraud_prevention import block_ip

await block_ip(db, "1.2.3.4", "Fraud detected", "automatic")

# Get user fraud summary
from services.fraud_prevention import get_user_fraud_summary

summary = await get_user_fraud_summary(db, user_id)
print(f"Risk score: {summary['latest_risk_score']}")
print(f"Duplicates: {summary['duplicate_accounts_count']}")

# Log suspicious activity
from services.fraud_prevention import log_suspicious_activity

await log_suspicious_activity(
    db=db,
    activity_type="multiple_accounts",
    severity="high",
    description="Same IP used for 5+ accounts",
    user_id=user_id,
    ip_address="1.2.3.4"
)
```

### Quick Fixes

**User blocked by mistake:**
```sql
UPDATE rate_limits SET is_blocked = false, block_reason = null WHERE user_id = 'UUID';
```

**Reset rate limit:**
```sql
UPDATE rate_limits SET daily_query_count = 0 WHERE user_id = 'UUID';
```

**Whitelist IP:**
```sql
DELETE FROM blocked_ips WHERE ip_address = '1.2.3.4';
```

**Allow disposable email temporarily:**
```sql
UPDATE blocked_emails SET is_active = false WHERE email_pattern = 'domain.com';
```

### Performance Tips

1. **Add index if needed:**
```sql
CREATE INDEX idx_custom ON table_name(column_name);
```

2. **Clean old data:**
```sql
DELETE FROM fraud_detection WHERE created_at < NOW() - INTERVAL '90 days';
DELETE FROM suspicious_activities WHERE is_resolved = true AND resolved_at < NOW() - INTERVAL '30 days';
```

3. **Optimize queries:**
```sql
VACUUM ANALYZE fraud_detection;
VACUUM ANALYZE rate_limits;
```

### Files Reference

| File | Purpose | Size |
|------|---------|------|
| `services/fraud_prevention.py` | Main service | 35 KB |
| `models_fraud.py` | Database models | 11 KB |
| `schemas_fraud.py` | API schemas | 17 KB |
| `api/fraud_endpoints.py` | API endpoints | 11 KB |
| `migrations/add_fraud_prevention_tables.sql` | Database setup | 16 KB |
| `tests/test_fraud_prevention.py` | Test suite | 11 KB |

### Important Functions

| Function | Purpose | Returns |
|----------|---------|---------|
| `perform_fraud_check()` | Complete fraud check | (is_allowed, reason, details) |
| `is_email_allowed()` | Validate email | (is_allowed, reason) |
| `is_ip_blocked()` | Check IP block | (is_blocked, reason) |
| `check_rate_limit()` | Check query limit | (is_allowed, reason, info) |
| `detect_duplicate_accounts()` | Find duplicates | [DuplicateDetection] |
| `track_user_fingerprint()` | Record fingerprint | FraudDetection |
| `initialize_rate_limit()` | Setup new user | RateLimit |

### Support Checklist

When user reports being blocked:

1. Check rate limit: `SELECT * FROM rate_limits WHERE user_id = ?`
2. Check IP block: `SELECT * FROM blocked_ips WHERE ip_address = ?`
3. Check suspicious activities: `SELECT * FROM suspicious_activities WHERE user_id = ?`
4. Check fraud detections: `SELECT * FROM fraud_detection WHERE user_id = ? ORDER BY created_at DESC`
5. Review and unblock if legitimate

### Links

- Full Documentation: `FRAUD_PREVENTION_README.md`
- Quick Start: `FRAUD_PREVENTION_QUICKSTART.md`
- Summary: `FRAUD_PREVENTION_SUMMARY.md`

---

**Print this page and keep it handy!**
