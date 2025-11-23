# Security Testing Checklist

Quick reference for testing all security features implemented by Agent C.

## Pre-Testing Setup

```bash
# 1. Start backend
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000

# 2. Start frontend (separate terminal)
cd frontend
npm run dev

# 3. Set environment variables (if needed)
export JWT_SECRET_KEY=your_test_secret
export DATABASE_URL=postgresql://...
```

---

## 1. Frontend Route Protection

### Test 1.1: Unauthenticated Access
- [ ] Visit http://localhost:3000/dashboard → Should redirect to `/auth/login?redirect=/dashboard`
- [ ] Visit http://localhost:3000/billing → Should redirect to `/auth/login?redirect=/billing`
- [ ] Visit http://localhost:3000/admin → Should redirect to `/auth/login?redirect=/admin`

### Test 1.2: Authenticated Non-Admin Access
```bash
# Login as regular user first
# Then visit:
```
- [ ] Visit http://localhost:3000/dashboard → Should work ✓
- [ ] Visit http://localhost:3000/billing → Should work ✓
- [ ] Visit http://localhost:3000/admin → Should redirect to `/403`

### Test 1.3: Admin Access
```bash
# Login as admin user
# Then visit:
```
- [ ] Visit http://localhost:3000/admin → Should work ✓
- [ ] Visit http://localhost:3000/admin/users → Should work ✓

**Expected Files:**
- `/frontend/middleware.ts` exists
- `/frontend/lib/auth-guard.tsx` exists

---

## 2. Rate Limiting Middleware

### Test 2.1: Auth Endpoint Rate Limiting
```bash
# Try to login 6 times in 60 seconds
for i in {1..6}; do
  curl -X POST http://localhost:8000/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"test@test.com","password":"wrong"}' \
    -i | grep -E "HTTP|429"
  echo "Request $i"
done
```
- [ ] First 5 requests → Should return 401 (wrong password)
- [ ] 6th request → Should return 429 (Too Many Requests)
- [ ] Response includes `Retry-After` header

### Test 2.2: AI Query Rate Limiting
```bash
# Get access token first
TOKEN="your_access_token"

# Try 11 AI queries in 60 seconds
for i in {1..11}; do
  curl -X POST http://localhost:8000/api/ai/query \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"question":"test"}' \
    -i | grep -E "HTTP|429"
  echo "Request $i"
done
```
- [ ] First 10 requests → Should process normally
- [ ] 11th request → Should return 429
- [ ] Response includes `X-RateLimit-*` headers

### Test 2.3: Rate Limit Headers
```bash
curl -i http://localhost:8000/api/tenders
```
- [ ] Response includes `X-RateLimit-Limit` header
- [ ] Response includes `X-RateLimit-Remaining` header
- [ ] Response includes `X-RateLimit-Reset` header

**Expected Files:**
- `/backend/middleware/rate_limit.py` exists
- Activated in `/backend/main.py`

---

## 3. Fraud Prevention Middleware

### Test 3.1: Query Limit Enforcement
```bash
# As free user with 3 queries limit
TOKEN="free_user_token"

# Make 4 queries
for i in {1..4}; do
  curl -X POST http://localhost:8000/api/ai/query \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"question":"test query '$i'"}' \
    -w "\nHTTP Status: %{http_code}\n"
done
```
- [ ] First 3 queries → Should succeed (200)
- [ ] 4th query → Should return 429 or 402
- [ ] Response includes `redirect_to` field
- [ ] Response includes `upgrade_required: true`

### Test 3.2: Device Fingerprinting
```bash
# Query with device fingerprint
curl -X POST http://localhost:8000/api/ai/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Device-Fingerprint: test_device_12345" \
  -H "Content-Type: application/json" \
  -d '{"question":"test"}'
```
- [ ] Request succeeds
- [ ] Check database: `SELECT * FROM fraud_detection WHERE device_fingerprint = 'test_device_12345'`
- [ ] Record should exist

### Test 3.3: VPN Detection (Free Tier)
```bash
# As free user with VPN-like user agent
curl -X POST http://localhost:8000/api/ai/query \
  -H "Authorization: Bearer $FREE_TOKEN" \
  -H "User-Agent: Mozilla/5.0 (VPN Protected) ..." \
  -H "Content-Type: application/json" \
  -d '{"question":"test"}'
```
- [ ] Should return 403 (Free tier doesn't allow VPN)
- [ ] Response message mentions VPN/Proxy

**Expected Files:**
- `/backend/middleware/fraud.py` exists
- Activated in `/backend/main.py`
- Uses `/backend/services/fraud_prevention.py`

---

## 4. CSRF Protection

### Test 4.1: Billing Request Without CSRF Token
```bash
# Try to create checkout session without CSRF token
curl -X POST http://localhost:8000/api/billing/checkout \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tier":"starter","interval":"monthly"}'
```
- [ ] Should succeed (backend doesn't enforce yet, client sends it)
- [ ] Check browser Network tab: billing requests include `X-CSRF-Token` header

### Test 4.2: Browser Console Check
```javascript
// In browser console on /billing page
console.log(sessionStorage.getItem('csrf_token'));
```
- [ ] Should show JSON with `token` and `expiry` fields
- [ ] Token should be 64 character hex string
- [ ] Expiry should be ~1 hour in future

### Test 4.3: Token Regeneration
```javascript
// In browser console
sessionStorage.removeItem('csrf_token');
// Then trigger a billing action (e.g., click "Subscribe")
// Check network tab
```
- [ ] New token should be generated
- [ ] Request includes new `X-CSRF-Token` header

**Expected Files:**
- `/frontend/lib/csrf.ts` exists
- `/frontend/lib/api.ts` modified to include CSRF

---

## 5. Role-Based Access Control (RBAC)

### Test 5.1: User Roles in Database
```sql
-- Check user roles
SELECT user_id, email, subscription_tier FROM users LIMIT 5;
SELECT user_id, email, role FROM users_auth LIMIT 5;
```
- [ ] `users.subscription_tier` matches tier (free, starter, professional, enterprise)
- [ ] `users_auth.role` is one of (user, admin, superadmin)

### Test 5.2: Admin Endpoint Protection
```bash
# As regular user
curl -X GET http://localhost:8000/admin/dashboard \
  -H "Authorization: Bearer $USER_TOKEN"
```
- [ ] Should return 403 (Forbidden)
- [ ] Error message: "Admin access required"

```bash
# As admin
curl -X GET http://localhost:8000/admin/dashboard \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```
- [ ] Should return 200 with dashboard data

### Test 5.3: Subscription Tier Mapping
```bash
# Check role mapping in middleware
curl -X GET http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer $TOKEN"
```
- [ ] Response includes `subscription_tier` field
- [ ] Matches one of: free, starter, professional, enterprise, admin

**Expected Files:**
- `/backend/models_auth.py` - Unified UserRole enum
- `/backend/middleware/rbac.py` - Role checking logic

---

## 6. Email Verification

### Test 6.1: Registration Sends Email
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email":"newuser@test.com",
    "password":"Test123!",
    "confirm_password":"Test123!",
    "full_name":"Test User"
  }'
```
- [ ] Returns 200 with access token
- [ ] User created with `email_verified=false`
- [ ] Email sent (check logs or SES console if in sandbox)

### Test 6.2: Verification Check (Currently Disabled)
```bash
# Check if verification is enforced
curl -X GET http://localhost:8000/api/billing/subscription \
  -H "Authorization: Bearer $UNVERIFIED_USER_TOKEN"
```
- [ ] Should succeed (verification check disabled)
- [ ] Check code: `middleware/rbac.py` has commented verification check

### Test 6.3: Database Schema
```sql
-- Check email verification fields
SELECT user_id, email, email_verified FROM users LIMIT 5;

-- Check verification tokens table
SELECT * FROM email_verifications ORDER BY created_at DESC LIMIT 5;
```
- [ ] `users.email_verified` field exists
- [ ] `email_verifications` table exists

**Expected Files:**
- `/backend/EMAIL_VERIFICATION_STATUS.md` - Full documentation

---

## 7. Integration Tests

### Test 7.1: Complete User Journey
```bash
# 1. Register
REGISTER_RESPONSE=$(curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"journey@test.com","password":"Test123!","confirm_password":"Test123!"}')

TOKEN=$(echo $REGISTER_RESPONSE | jq -r '.access_token')

# 2. Get user info
curl -X GET http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer $TOKEN"

# 3. Try to make AI query (should track in fraud system)
curl -X POST http://localhost:8000/api/ai/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Device-Fingerprint: integration_test" \
  -H "Content-Type: application/json" \
  -d '{"question":"test query"}'

# 4. Check fraud detection recorded it
# Query database: SELECT * FROM fraud_detection WHERE device_fingerprint = 'integration_test'
```
- [ ] All requests succeed
- [ ] User tracked in fraud_detection table
- [ ] Rate limits applied correctly

### Test 7.2: Middleware Stack Order
```bash
# Send request and check order of processing
curl -v http://localhost:8000/api/tenders?page=1 \
  -H "Authorization: Bearer $TOKEN" 2>&1 | grep -E "X-RateLimit|CORS"
```
- [ ] CORS headers present
- [ ] Rate limit headers present
- [ ] No errors in backend logs

**Check logs for order:**
```
INFO: CORS middleware processed
INFO: Rate limit middleware processed
INFO: Fraud prevention middleware processed
INFO: Request reached endpoint
```

---

## 8. Performance Tests

### Test 8.1: Middleware Latency
```bash
# Measure request time with and without authentication
time curl http://localhost:8000/api/tenders

# With auth
time curl http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer $TOKEN"
```
- [ ] Overhead < 10ms per request
- [ ] No significant performance degradation

### Test 8.2: Rate Limit Storage Efficiency
```bash
# Check memory usage before
ps aux | grep uvicorn

# Make 1000 requests from different IPs (simulation)
# Check memory usage after
ps aux | grep uvicorn
```
- [ ] Memory increase < 50MB
- [ ] No memory leaks

---

## 9. Error Handling Tests

### Test 9.1: Invalid JWT Token
```bash
curl -X GET http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer invalid_token_here"
```
- [ ] Returns 401 (Unauthorized)
- [ ] Error message: "Could not validate credentials"

### Test 9.2: Expired Token
```bash
# Use an expired token
curl -X GET http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer $EXPIRED_TOKEN"
```
- [ ] Returns 401 (Unauthorized)
- [ ] Error message mentions expiration

### Test 9.3: CSRF Token Missing (Backend Check)
```bash
# If backend validates CSRF (currently client-side only)
curl -X POST http://localhost:8000/api/billing/checkout \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tier":"starter"}'
# (No X-CSRF-Token header)
```
- [ ] Should succeed (backend doesn't enforce, relies on client)
- [ ] Document this as potential improvement

---

## 10. Security Audit Checks

### Test 10.1: Verify All Middleware Active
```bash
# Check main.py imports
grep -E "FraudPreventionMiddleware|RateLimitMiddleware" backend/main.py
```
- [ ] Both imports present
- [ ] Both `app.add_middleware()` calls present
- [ ] Correct order: CORS → RateLimit → FraudPrevention

### Test 10.2: Verify Route Protection
```bash
# Check middleware.ts config
grep -A 5 "PROTECTED_ROUTES" frontend/middleware.ts
```
- [ ] All sensitive routes listed
- [ ] Correct role requirements
- [ ] Admin routes require 'admin'

### Test 10.3: Database Security
```sql
-- Check for test/dummy data
SELECT COUNT(*) FROM users WHERE email LIKE '%test%';
SELECT COUNT(*) FROM users WHERE email LIKE '%dummy%';

-- Check for unverified old users
SELECT COUNT(*) FROM users
WHERE email_verified = false
  AND created_at < NOW() - INTERVAL '30 days';
```
- [ ] Document any test users for cleanup
- [ ] Monitor old unverified accounts

---

## Test Results Template

```
Date: __________
Tester: __________

✅ Frontend Route Protection       [Pass/Fail]
✅ Rate Limiting                    [Pass/Fail]
✅ Fraud Prevention                 [Pass/Fail]
✅ CSRF Protection                  [Pass/Fail]
✅ RBAC                             [Pass/Fail]
✅ Email Verification (Disabled)    [N/A]
✅ Integration Tests                [Pass/Fail]
✅ Performance Tests                [Pass/Fail]
✅ Error Handling                   [Pass/Fail]
✅ Security Audit                   [Pass/Fail]

Notes:
_________________________________
_________________________________

Issues Found:
_________________________________
_________________________________

Action Items:
_________________________________
_________________________________
```

---

## Automated Test Script

```bash
#!/bin/bash
# security_test_suite.sh

echo "🔒 Running Security Test Suite..."

# Set variables
API_URL="http://localhost:8000"
FRONTEND_URL="http://localhost:3000"

# Test 1: Rate Limiting
echo "Testing rate limiting..."
for i in {1..6}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST $API_URL/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"test@test.com","password":"wrong"}'
done

# Test 2: Protected Routes (requires curl to follow redirects)
echo "Testing route protection..."
curl -s -o /dev/null -w "%{http_code}\n" $FRONTEND_URL/dashboard
curl -s -o /dev/null -w "%{http_code}\n" $FRONTEND_URL/admin

# Test 3: RBAC
echo "Testing RBAC..."
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Authorization: Bearer $USER_TOKEN" \
  $API_URL/admin/dashboard

echo "✅ Security tests complete!"
```

---

## Quick Verification Commands

```bash
# Check all security files exist
ls -la backend/middleware/fraud.py
ls -la backend/middleware/rate_limit.py
ls -la backend/middleware/rbac.py
ls -la frontend/middleware.ts
ls -la frontend/lib/auth-guard.tsx
ls -la frontend/lib/csrf.ts

# Check middleware is activated
grep "add_middleware" backend/main.py

# Check database tables exist
psql $DATABASE_URL -c "\dt fraud*"
psql $DATABASE_URL -c "\dt email_verifications"
psql $DATABASE_URL -c "\dt users_auth"

# Check environment variables
env | grep -E "JWT_SECRET|AWS_|FRONTEND_URL"
```

---

## Success Criteria

All tests should pass with these results:

- ✅ Route protection blocks unauthenticated access
- ✅ Rate limiting returns 429 after limit exceeded
- ✅ Fraud prevention tracks user activity
- ✅ CSRF tokens generated and included in requests
- ✅ RBAC prevents unauthorized admin access
- ✅ Email verification infrastructure in place (disabled)
- ✅ No errors in backend logs
- ✅ Performance overhead < 10ms
- ✅ All middleware files exist and activated
- ✅ Database tables created correctly

**Next Steps After Testing:**
1. Fix any failing tests
2. Document any issues found
3. Update security configuration if needed
4. Schedule regular security audits
5. Monitor production logs for anomalies

---

Last Updated: November 23, 2025
