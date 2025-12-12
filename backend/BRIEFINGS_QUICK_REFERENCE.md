# Daily Briefings API - Quick Reference

## Endpoints

### 1. Get Today's Briefing
```
GET /api/briefings/today
Authorization: Bearer {jwt_token}

Response: BriefingResponse
```

### 2. Get Briefing History
```
GET /api/briefings/history?page=1&page_size=10
Authorization: Bearer {jwt_token}

Response: BriefingHistoryResponse
```

### 3. Get Specific Date's Briefing
```
GET /api/briefings/{briefing_date}
Authorization: Bearer {jwt_token}

Example: GET /api/briefings/2025-12-01

Response: BriefingResponse
```

### 4. Force Regenerate Today's Briefing
```
POST /api/briefings/generate
Authorization: Bearer {jwt_token}

Response: BriefingResponse (201 Created)
```

### 5. Health Check
```
GET /api/briefings/health/status

Response: {
  "status": "healthy",
  "service": "daily-briefings",
  "gemini_available": true,
  "gemini_model": "gemini-2.0-flash",
  "features": { ... }
}
```

## Alert Matching Scoring System

| Filter Type | Points | Priority Threshold |
|-------------|--------|-------------------|
| Query/Keyword (title) | 40 | High: >= 70 |
| Query/Keyword (description) | 25 | Medium: >= 40 |
| Category Match | 20 | Low: < 40 |
| CPV Code Match | 20 | |
| Procuring Entity Match | 15 | |
| Value Range Match | 5 | |

**Total Possible:** 100 points

## Database

### Table: daily_briefings
```sql
briefing_id         UUID PRIMARY KEY
user_id             UUID (FK to users)
briefing_date       DATE
content             JSONB
ai_summary          TEXT
total_matches       INTEGER
high_priority_count INTEGER
generated_at        TIMESTAMP
is_viewed           BOOLEAN
```

### Constraints
- UNIQUE(user_id, briefing_date) - one briefing per user per day
- CASCADE DELETE on user_id

## Environment Variables

```bash
GEMINI_API_KEY=AIzaSyBz-Q2SG_ayM4fWilHSPaLnwr13NlwmiaI
GEMINI_MODEL=gemini-2.0-flash  # optional
```

## Test Commands

```bash
# Check table structure
psql -h nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com \
     -U nabavki_user -d nabavkidata \
     -c "\d daily_briefings"

# Count recent tenders
psql -h nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com \
     -U nabavki_user -d nabavkidata \
     -c "SELECT COUNT(*) FROM tenders WHERE created_at >= NOW() - INTERVAL '24 hours';"

# Check syntax
python3 -m py_compile api/briefings.py
```

## Integration Example

```typescript
// Frontend - Next.js
const fetchTodaysBriefing = async () => {
  const response = await fetch('/api/briefings/today', {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  return await response.json();
};
```

## Files Modified

1. `/backend/api/briefings.py` - NEW (735 lines)
2. `/backend/main.py` - MODIFIED (added router import and registration)
3. Database: `daily_briefings` table - CREATED

## Common Issues & Solutions

### No matches returned
- Ensure user has active alerts: `SELECT * FROM alerts WHERE user_id = ?`
- Check recent tenders: `SELECT COUNT(*) FROM tenders WHERE created_at > NOW() - INTERVAL '24 hours'`

### AI summary not working
- Verify GEMINI_API_KEY is set
- Check Gemini API quota
- Fallback to generic summary if AI fails

### Slow performance
- Add index: `CREATE INDEX idx_tenders_created_at ON tenders(created_at DESC)`
- Consider Redis cache for recent tenders
- Reduce tender lookup window to 12 hours

---

**Quick Start:** Run backend with `uvicorn main:app --reload` and test with `/api/briefings/health/status`
