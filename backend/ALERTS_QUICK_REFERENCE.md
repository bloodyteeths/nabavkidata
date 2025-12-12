# Alerts API - Quick Reference Guide

## Endpoints Overview

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/api/alerts` | List user alerts | ✓ |
| POST | `/api/alerts` | Create alert | ✓ |
| PUT | `/api/alerts/{id}` | Update alert | ✓ |
| DELETE | `/api/alerts/{id}` | Delete alert | ✓ |
| GET | `/api/alerts/{id}/matches` | Get matches | ✓ |
| POST | `/api/alerts/mark-read` | Mark read | ✓ |
| POST | `/api/alerts/check-now` | Force check | ✓ |

## Common Usage Examples

### 1. Create a Keyword Alert

```bash
curl -X POST "http://localhost:8000/api/alerts" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Software Tenders",
    "alert_type": "keyword",
    "criteria": {
      "keywords": ["software", "компјутер", "лиценци"]
    },
    "notification_channels": ["email", "in_app"]
  }'
```

### 2. Create a CPV Code Alert

```bash
curl -X POST "http://localhost:8000/api/alerts" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Medical Equipment",
    "alert_type": "cpv",
    "criteria": {
      "cpv_codes": ["3311", "3312", "3340"]
    }
  }'
```

### 3. Create a Budget Range Alert

```bash
curl -X POST "http://localhost:8000/api/alerts" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "High Value Tenders",
    "alert_type": "budget",
    "criteria": {
      "budget_min": 1000000,
      "budget_max": 10000000
    }
  }'
```

### 4. Create a Combined Alert

```bash
curl -X POST "http://localhost:8000/api/alerts" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "High Value IT for Ministries",
    "alert_type": "combined",
    "criteria": {
      "keywords": ["software", "hardware"],
      "cpv_codes": ["3021"],
      "entities": ["Министерство"],
      "budget_min": 500000
    }
  }'
```

### 5. Create a Competitor Tracking Alert

```bash
curl -X POST "http://localhost:8000/api/alerts" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Track Competitor Wins",
    "alert_type": "competitor",
    "criteria": {
      "competitors": ["Македонски Телеком", "One.Vip", "А1"]
    }
  }'
```

### 6. List Alerts with Match Counts

```bash
curl -X GET "http://localhost:8000/api/alerts?include_counts=true" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### 7. Get Alert Matches (with pagination)

```bash
curl -X GET "http://localhost:8000/api/alerts/{alert_id}/matches?limit=20&offset=0&unread_only=true" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### 8. Update Alert

```bash
curl -X PUT "http://localhost:8000/api/alerts/{alert_id}" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated Alert Name",
    "is_active": true,
    "criteria": {
      "keywords": ["new", "keywords"]
    }
  }'
```

### 9. Mark Matches as Read

```bash
curl -X POST "http://localhost:8000/api/alerts/mark-read" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "match_ids": [
      "uuid-1",
      "uuid-2",
      "uuid-3"
    ]
  }'
```

### 10. Force Check Alerts

```bash
curl -X POST "http://localhost:8000/api/alerts/check-now" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### 11. Delete Alert

```bash
curl -X DELETE "http://localhost:8000/api/alerts/{alert_id}" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## Python Client Examples

### Create Alert
```python
import httpx

async def create_alert(token: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/alerts",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "Software Tenders",
                "alert_type": "keyword",
                "criteria": {
                    "keywords": ["software", "компјутер"]
                }
            }
        )
        return response.json()
```

### Get Matches
```python
async def get_matches(token: str, alert_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://localhost:8000/api/alerts/{alert_id}/matches",
            headers={"Authorization": f"Bearer {token}"},
            params={"unread_only": True, "limit": 50}
        )
        return response.json()
```

### Force Check
```python
async def check_alerts(token: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/alerts/check-now",
            headers={"Authorization": f"Bearer {token}"}
        )
        return response.json()
```

## Matching Score Breakdown

| Criterion | Score | Example |
|-----------|-------|---------|
| Keyword Match | 25 | "software" found in tender title |
| CPV Code Match | 30 | CPV "30213000" matches alert "3021" |
| Entity Match | 25 | "Министерство" found in procuring entity |
| Budget Range | 20 | Tender value 500,000 MKD within 100K-1M range |
| Competitor Match | 25 | "Македонски Телеком" found in winner field |

**Maximum Score:** 100 (capped)
**Match Threshold:** > 0 (any matching criterion)

## Alert Types

| Type | Description | Typical Use Case |
|------|-------------|------------------|
| `keyword` | Match keywords in title/description | "Find all software tenders" |
| `cpv` | Match CPV codes (4-digit prefix) | "Monitor medical equipment procurement" |
| `entity` | Match procuring entities | "Track specific ministry tenders" |
| `competitor` | Track competitor wins | "Monitor competitor activity" |
| `budget` | Filter by budget range | "High-value opportunities only" |
| `combined` | Multi-criteria matching | "Complex alert with multiple filters" |

## Database Schema

### tender_alerts
```sql
alert_id              UUID PRIMARY KEY
user_id               UUID REFERENCES users
name                  VARCHAR(200)
alert_type            VARCHAR(50)
criteria              JSONB
is_active             BOOLEAN
notification_channels JSONB
created_at            TIMESTAMP
updated_at            TIMESTAMP
```

### alert_matches
```sql
match_id      UUID PRIMARY KEY
alert_id      UUID REFERENCES tender_alerts
tender_id     VARCHAR(100)
tender_source VARCHAR(20)
match_score   NUMERIC(5,2)
match_reasons JSONB
is_read       BOOLEAN
notified_at   TIMESTAMP
created_at    TIMESTAMP
```

## Error Codes

| Status | Description |
|--------|-------------|
| 200 | Success |
| 201 | Created |
| 204 | No Content (delete) |
| 400 | Bad Request (invalid alert_type, no fields to update) |
| 401 | Unauthorized (missing/invalid token) |
| 403 | Forbidden (not your alert) |
| 404 | Not Found (alert doesn't exist) |

## Performance Tips

1. **Use pagination** for large match lists (limit ≤ 200)
2. **Filter unread matches** to reduce response size
3. **Disable match counts** if not needed (`include_counts=false`)
4. **Batch mark-read** operations instead of individual updates
5. **Use indexes** - database has indexes on user_id, is_active, alert_id, is_read

## Testing

Run the test suite:
```bash
cd /Users/tamsar/Downloads/nabavkidata/backend
python3 test_alerts_simple.py
```

Expected output:
```
✓ All 10 tests passed successfully!
```

## Next Steps

After implementing alerts, integrate with:
1. **Daily Briefings** (Phase 6.2) - Email digests
2. **Real-time Notifications** - WebSocket push
3. **Frontend UI** - Alert management dashboard
4. **Analytics** - Alert performance tracking
