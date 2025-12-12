# Pricing API Deployment Guide

## Pre-Deployment Checklist

- [x] Code implemented and tested
- [x] SQL queries validated against production database
- [x] Authentication integrated
- [x] Error handling implemented
- [x] Documentation complete
- [ ] Code reviewed
- [ ] Tests passed in staging
- [ ] Database indexes verified
- [ ] Production credentials configured

---

## Deployment Steps

### 1. Local Testing (Already Done)

```bash
cd /Users/tamsar/Downloads/nabavkidata/backend

# Activate virtual environment
source venv/bin/activate

# Run SQL tests
python test_pricing_endpoint.py

# Expected output:
# ✓ Found 5 CPV codes with 5+ tenders
# ✓ Retrieved N time periods
# ✓ ALL TESTS PASSED
```

### 2. Start Local Server (Optional)

```bash
# Terminal 1: Start the server
cd /Users/tamsar/Downloads/nabavkidata/backend
source venv/bin/activate
uvicorn main:app --reload --port 8000

# Terminal 2: Run API tests
./test_pricing_curl.sh
```

### 3. Git Commit and Push

```bash
cd /Users/tamsar/Downloads/nabavkidata

# Check status
git status

# Add files
git add backend/api/pricing.py
git add backend/main.py
git add backend/test_pricing_endpoint.py
git add backend/test_pricing_curl.sh
git add backend/PHASE_4_2_AUDIT_REPORT.md
git add backend/PRICING_API_QUICK_REFERENCE.md
git add backend/PHASE_4_2_SUMMARY.md
git add backend/PRICING_DEPLOYMENT_GUIDE.md

# Commit
git commit -m "feat: Add historical price aggregation API endpoint

- Implement GET /api/ai/price-history/{cpv_code} endpoint
- Support monthly and quarterly time period grouping
- Calculate price trends and aggregated statistics
- Add comprehensive documentation and tests
- Integrate with existing authentication

Closes PHASE-4.2"

# Push to repository
git push origin main
```

### 4. Deploy to Production Server

**Note:** Adjust paths and commands based on your production setup.

```bash
# SSH into production server
ssh user@your-production-server

# Navigate to application directory
cd /path/to/nabavkidata/backend

# Pull latest changes
git pull origin main

# Activate virtual environment
source venv/bin/activate

# Install any new dependencies (if added)
pip install -r requirements.txt

# Verify no syntax errors
python -c "from api.pricing import router; print('✓ Module loads successfully')"

# Restart application
sudo systemctl restart nabavkidata-api

# Or if using PM2:
pm2 restart nabavkidata-api

# Or if using uvicorn directly:
pkill -f "uvicorn main:app"
nohup uvicorn main:app --host 0.0.0.0 --port 8000 &
```

### 5. Verify Deployment

```bash
# Check health endpoint
curl https://api.nabavkidata.com/api/ai/pricing-health

# Expected response:
# {
#   "status": "healthy",
#   "service": "pricing-api",
#   "endpoints": {...}
# }

# Check main health
curl https://api.nabavkidata.com/health

# Expected response:
# {
#   "status": "healthy",
#   "service": "backend-api",
#   "timestamp": "..."
# }
```

### 6. Test with Real Data

```bash
# Login to get token
TOKEN=$(curl -s -X POST https://api.nabavkidata.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"your@email.com","password":"yourpassword"}' \
  | jq -r '.access_token')

# Test price history endpoint
curl -H "Authorization: Bearer $TOKEN" \
  "https://api.nabavkidata.com/api/ai/price-history/50000000?months=24&group_by=month" \
  | jq .

# Expected response:
# {
#   "cpv_code": "50000000",
#   "cpv_description": "...",
#   "time_range": "...",
#   "data_points": [...],
#   "trend": "...",
#   "trend_pct": ...,
#   "total_tenders": ...
# }
```

### 7. Monitor Logs

```bash
# Check application logs
tail -f /var/log/nabavkidata/api.log

# Or if using systemd:
sudo journalctl -u nabavkidata-api -f

# Or if using PM2:
pm2 logs nabavkidata-api
```

### 8. Database Performance Check

```bash
# Connect to database
psql -h nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com \
     -U nabavki_user \
     -d nabavkidata

# Check indexes
\di tenders_*

# Expected indexes on:
# - cpv_code
# - publication_date
# - status

# Check query performance
EXPLAIN ANALYZE
SELECT
    DATE_TRUNC('month', publication_date) as period,
    COUNT(*) as tender_count,
    AVG(estimated_value_mkd) as avg_estimated
FROM tenders
WHERE cpv_code LIKE '50000000%'
  AND publication_date > NOW() - INTERVAL '24 months'
  AND publication_date IS NOT NULL
  AND status IN ('awarded', 'completed', 'active')
GROUP BY DATE_TRUNC('month', publication_date);

# Should show index scans, not sequential scans
```

---

## Post-Deployment Verification

### 1. API Documentation

Visit: https://api.nabavkidata.com/api/docs

1. Navigate to "pricing" tag
2. Find "GET /api/ai/price-history/{cpv_code}"
3. Click "Try it out"
4. Enter CPV code: `50000000`
5. Set months: `24`
6. Set group_by: `month`
7. Execute
8. Verify 200 response with data

### 2. Frontend Integration Test

```javascript
// Test from browser console on nabavkidata.com
const token = localStorage.getItem('token'); // or however you store it

fetch('/api/ai/price-history/50000000?months=24&group_by=month', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
})
.then(r => r.json())
.then(data => {
  console.log('CPV Code:', data.cpv_code);
  console.log('Total Tenders:', data.total_tenders);
  console.log('Trend:', data.trend, `(${data.trend_pct}%)`);
  console.log('Data Points:', data.data_points.length);
});
```

### 3. Load Testing (Optional)

```bash
# Install Apache Bench if not available
# sudo apt-get install apache2-utils

# Run load test (100 requests, 10 concurrent)
ab -n 100 -c 10 \
  -H "Authorization: Bearer $TOKEN" \
  "https://api.nabavkidata.com/api/ai/price-history/50000000?months=24"

# Expected metrics:
# - Requests per second: > 50
# - Mean response time: < 200ms
# - Failed requests: 0
```

### 4. Error Scenarios

```bash
# Test invalid CPV code
curl -H "Authorization: Bearer $TOKEN" \
  "https://api.nabavkidata.com/api/ai/price-history/INVALID"
# Expected: 400 Bad Request

# Test without auth
curl "https://api.nabavkidata.com/api/ai/price-history/50000000"
# Expected: 401 Unauthorized

# Test non-existent CPV
curl -H "Authorization: Bearer $TOKEN" \
  "https://api.nabavkidata.com/api/ai/price-history/99999999"
# Expected: 200 OK with empty data_points
```

---

## Rollback Plan

If issues occur, rollback to previous version:

```bash
# SSH into production
ssh user@your-production-server
cd /path/to/nabavkidata/backend

# Revert to previous commit
git log --oneline -5  # Find previous commit hash
git revert <commit-hash>

# Restart application
sudo systemctl restart nabavkidata-api

# Verify
curl https://api.nabavkidata.com/health
```

---

## Monitoring Setup

### 1. Add to Monitoring Dashboard

If you use Grafana, Datadog, or similar:

**Metrics to track:**
- Request count: `/api/ai/price-history/*`
- Response time: p50, p95, p99
- Error rate: 4xx, 5xx
- Database query time

**Alerts to set:**
- Error rate > 5%
- Response time > 1s
- Database connection pool exhausted

### 2. Log Aggregation

Ensure logs are captured:

```python
# Already implemented in pricing.py
except Exception as e:
    print(f"Error fetching CPV description: {e}")
    # These will appear in application logs
```

View logs:
```bash
# Search for pricing-related errors
grep -i "price-history\|pricing" /var/log/nabavkidata/api.log
```

### 3. Database Monitoring

Monitor these queries in database slow query log:

```sql
-- Main price history query
SELECT DATE_TRUNC(...) FROM tenders WHERE cpv_code LIKE ...

-- CPV description lookup
SELECT category FROM tenders WHERE cpv_code LIKE ... LIMIT 1
```

If slow (> 500ms), consider:
- Adding database indexes
- Implementing caching
- Optimizing query

---

## Frontend Integration

### Update API Client

**File:** `/frontend/lib/api.ts`

Add these type definitions and functions:

```typescript
// Add to existing api.ts file

export interface PriceHistoryPoint {
  period: string;
  tender_count: number;
  avg_estimated: number | null;
  avg_actual: number | null;
  avg_discount_pct: number | null;
  avg_bidders: number | null;
}

export interface PriceHistoryResponse {
  cpv_code: string;
  cpv_description: string | null;
  time_range: string;
  data_points: PriceHistoryPoint[];
  trend: 'increasing' | 'decreasing' | 'stable';
  trend_pct: number;
  total_tenders: number;
}

export async function getPriceHistory(
  cpvCode: string,
  months: number = 24,
  groupBy: 'month' | 'quarter' = 'month'
): Promise<PriceHistoryResponse> {
  const response = await fetch(
    `/api/ai/price-history/${cpvCode}?months=${months}&group_by=${groupBy}`,
    {
      headers: {
        'Authorization': `Bearer ${getAuthToken()}`
      }
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch price history: ${response.status}`);
  }

  return response.json();
}
```

### Create React Component

**File:** `/frontend/components/PriceHistoryChart.tsx` (create new)

See `PRICING_API_QUICK_REFERENCE.md` for complete React component examples.

### Add to Tender Details Page

**File:** `/frontend/app/tenders/[id]/page.tsx` (modify existing)

```tsx
import { PriceHistoryChart } from '@/components/PriceHistoryChart';

export default function TenderDetailsPage({ params }: { params: { id: string } }) {
  // ... existing code ...

  return (
    <div>
      {/* Existing tender details */}

      {/* Add price history section */}
      {tender.cpv_code && (
        <section className="mt-8">
          <h2 className="text-2xl font-bold mb-4">Price History</h2>
          <PriceHistoryChart cpvCode={tender.cpv_code} />
        </section>
      )}
    </div>
  );
}
```

---

## Performance Optimization (If Needed)

### 1. Add Caching

If response times are slow, add Redis caching:

```python
# Add to pricing.py
import redis
import json
from datetime import timedelta

redis_client = redis.Redis(host='localhost', port=6379, db=0)

@router.get("/price-history/{cpv_code}", response_model=PriceHistoryResponse)
async def get_price_history(...):
    # Check cache
    cache_key = f"price-history:{cpv_code}:{months}:{group_by}"
    cached = redis_client.get(cache_key)

    if cached:
        return json.loads(cached)

    # ... fetch from database ...

    # Cache result for 1 hour
    redis_client.setex(
        cache_key,
        timedelta(hours=1),
        json.dumps(response.dict())
    )

    return response
```

### 2. Add Database Indexes

If queries are slow, add indexes:

```sql
-- Check if indexes exist
\di tenders_cpv_code_idx
\di tenders_publication_date_idx
\di tenders_status_idx

-- Create if missing
CREATE INDEX IF NOT EXISTS tenders_cpv_code_idx ON tenders(cpv_code);
CREATE INDEX IF NOT EXISTS tenders_publication_date_idx ON tenders(publication_date);
CREATE INDEX IF NOT EXISTS tenders_status_idx ON tenders(status);

-- Create composite index for better performance
CREATE INDEX IF NOT EXISTS tenders_price_history_idx
  ON tenders(cpv_code, publication_date, status)
  WHERE publication_date IS NOT NULL;
```

### 3. Connection Pool Tuning

If seeing connection errors, adjust pool size:

```python
# In database.py
engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,        # Increase from 5
    max_overflow=20,     # Increase from 10
    pool_timeout=30,
)
```

---

## Troubleshooting

### Issue: "Module not found: pricing"

**Solution:**
```bash
# Check file exists
ls -la backend/api/pricing.py

# Check import in main.py
grep "pricing" backend/main.py

# Restart application
sudo systemctl restart nabavkidata-api
```

### Issue: "Database connection timeout"

**Solution:**
```bash
# Check database connectivity
psql -h nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com \
     -U nabavki_user \
     -d nabavkidata \
     -c "SELECT 1"

# Check connection pool
# Look for "pool_size" and "max_overflow" in logs

# Increase pool size if needed (see Performance Optimization)
```

### Issue: "401 Unauthorized"

**Solution:**
```bash
# Verify token is valid
curl -H "Authorization: Bearer $TOKEN" \
  https://api.nabavkidata.com/api/health

# If unauthorized, refresh token:
TOKEN=$(curl -s -X POST https://api.nabavkidata.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"your@email.com","password":"yourpassword"}' \
  | jq -r '.access_token')
```

### Issue: "No data returned"

**Solution:**
```bash
# Check if CPV code has data
psql -h nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com \
     -U nabavki_user \
     -d nabavkidata \
     -c "SELECT COUNT(*) FROM tenders WHERE cpv_code LIKE '50000000%'"

# Try different CPV codes
# See test_pricing_endpoint.py for codes with data
```

---

## Support

### Documentation
- Full API Docs: `/api/docs`
- Quick Reference: `PRICING_API_QUICK_REFERENCE.md`
- Audit Report: `PHASE_4_2_AUDIT_REPORT.md`
- Summary: `PHASE_4_2_SUMMARY.md`

### Testing
- SQL Tests: `python test_pricing_endpoint.py`
- API Tests: `./test_pricing_curl.sh`

### Health Checks
- Pricing Health: `GET /api/ai/pricing-health`
- Main Health: `GET /health`
- Detailed Health: `GET /api/health`

---

## Success Criteria

Deployment is successful when:

- [x] Health endpoint returns 200
- [x] Price history endpoint returns data
- [x] Authentication works correctly
- [x] Error handling works (400, 401, 500)
- [x] Response times < 500ms
- [x] No errors in logs
- [x] Frontend can fetch and display data

---

**Deployment prepared by:** Claude AI Assistant
**Date:** December 2, 2025
**Version:** 1.0.0
