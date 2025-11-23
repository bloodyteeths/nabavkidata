# Scraper API Reference

Quick reference guide for the new scraper API endpoints.

---

## Base URL
```
http://localhost:8000/api/scraper
```

---

## Endpoints

### 1. Health Check (Public)
**GET** `/api/scraper/health`

No authentication required. Returns current health status of the scraper.

**Response:**
```json
{
  "status": "healthy",
  "last_successful_run": "2025-11-23T10:15:30Z",
  "hours_since_success": 1.5,
  "recent_jobs_count": 10,
  "failed_jobs_count": 1,
  "error_rate": 10.0,
  "avg_duration_minutes": 15.2,
  "total_tenders_scraped": 12450,
  "total_documents_scraped": 34890,
  "issues": ["No issues detected"],
  "timestamp": "2025-11-23T12:00:00Z"
}
```

**Status Values:**
- `healthy` - Last run < 2h ago, error rate < 20%
- `warning` - Last run < 24h ago, error rate < 50%
- `unhealthy` - Last run > 24h ago or error rate > 50%

**Use Case:** Monitoring dashboards, uptime checks

**cURL Example:**
```bash
curl http://localhost:8000/api/scraper/health
```

---

### 2. Job History (Admin)
**GET** `/api/scraper/jobs`

Returns paginated list of scraping jobs.

**Authentication:** Required (Admin role)

**Query Parameters:**
- `skip` (int, default: 0) - Number of records to skip
- `limit` (int, default: 20, max: 100) - Number of records to return
- `status` (string, optional) - Filter by status: `running`, `completed`, `failed`

**Response:**
```json
{
  "total": 45,
  "skip": 0,
  "limit": 20,
  "jobs": [
    {
      "job_id": "550e8400-e29b-41d4-a716-446655440000",
      "started_at": "2025-11-23T10:00:00Z",
      "completed_at": "2025-11-23T10:15:30Z",
      "status": "completed",
      "tenders_scraped": 127,
      "documents_scraped": 345,
      "errors_count": 2,
      "error_message": null,
      "spider_name": "nabavki",
      "incremental": true,
      "duration_seconds": 930
    }
  ]
}
```

**cURL Example:**
```bash
# Get first 20 jobs
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/api/scraper/jobs

# Get only failed jobs
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  "http://localhost:8000/api/scraper/jobs?status=failed"

# Pagination
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  "http://localhost:8000/api/scraper/jobs?skip=20&limit=10"
```

---

### 3. Scraper Status (Admin)
**GET** `/api/scraper/status`

Returns detailed scraper status including running jobs.

**Authentication:** Required (Admin role)

**Response:**
```json
{
  "is_running": true,
  "running_jobs": [
    {
      "job_id": "550e8400-e29b-41d4-a716-446655440000",
      "started_at": "2025-11-23T12:00:00Z",
      "spider_name": "nabavki",
      "incremental": true
    }
  ],
  "last_job": {
    "job_id": "450e8400-e29b-41d4-a716-446655440000",
    "completed_at": "2025-11-23T11:45:00Z",
    "status": "completed",
    "tenders_scraped": 127,
    "documents_scraped": 345,
    "errors_count": 0
  },
  "statistics": {
    "total_jobs": 523,
    "total_tenders": 12450,
    "total_documents": 34890
  }
}
```

**cURL Example:**
```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/api/scraper/status
```

---

### 4. Trigger Scraper (Admin)
**POST** `/api/scraper/trigger`

Manually trigger a scraping job.

**Authentication:** Required (Admin role)

**Request Body:**
```json
{
  "incremental": true,
  "max_pages": 10,
  "notify_on_complete": true
}
```

**Request Fields:**
- `incremental` (bool, default: true) - Only scrape new/updated tenders
- `max_pages` (int, optional) - Limit pages to scrape (for testing)
- `notify_on_complete` (bool, default: true) - Send email when complete

**Response:**
```json
{
  "message": "Scraper triggered successfully",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running"
}
```

**cURL Example:**
```bash
# Trigger incremental scrape
curl -X POST \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"incremental": true}' \
  http://localhost:8000/api/scraper/trigger

# Trigger full scrape (test mode, 5 pages)
curl -X POST \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"incremental": false, "max_pages": 5}' \
  http://localhost:8000/api/scraper/trigger
```

---

## Authentication

All admin endpoints require a Bearer token in the Authorization header.

**Getting a Token:**
```bash
# Login to get token
TOKEN=$(curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "your-password"}' \
  http://localhost:8000/api/auth/login | jq -r '.access_token')

# Use token
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/scraper/jobs
```

---

## Error Responses

**401 Unauthorized:**
```json
{
  "detail": "Not authenticated"
}
```

**403 Forbidden:**
```json
{
  "detail": "Insufficient permissions"
}
```

**404 Not Found:**
```json
{
  "detail": "Resource not found"
}
```

**500 Internal Server Error:**
```json
{
  "detail": "Internal server error",
  "message": "Error details..."
}
```

---

## Rate Limits

Admin endpoints are rate-limited to prevent abuse:
- 100 requests per minute per IP
- 1000 requests per hour per IP

Health check endpoint:
- 300 requests per minute per IP (higher limit for monitoring)

---

## Integration Examples

### Python
```python
import requests

# Health check
response = requests.get('http://localhost:8000/api/scraper/health')
health = response.json()
print(f"Scraper status: {health['status']}")

# Get job history (with auth)
headers = {'Authorization': f'Bearer {token}'}
response = requests.get(
    'http://localhost:8000/api/scraper/jobs',
    headers=headers,
    params={'limit': 10}
)
jobs = response.json()['jobs']

# Trigger scraper
response = requests.post(
    'http://localhost:8000/api/scraper/trigger',
    headers=headers,
    json={'incremental': True, 'max_pages': 10}
)
job_id = response.json()['job_id']
print(f"Started job: {job_id}")
```

### JavaScript (fetch)
```javascript
// Health check
const health = await fetch('http://localhost:8000/api/scraper/health')
  .then(r => r.json());
console.log('Scraper status:', health.status);

// Get job history
const jobs = await fetch('http://localhost:8000/api/scraper/jobs', {
  headers: { 'Authorization': `Bearer ${token}` }
}).then(r => r.json());

// Trigger scraper
const result = await fetch('http://localhost:8000/api/scraper/trigger', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ incremental: true, max_pages: 10 })
}).then(r => r.json());

console.log('Job ID:', result.job_id);
```

### Monitoring Script (Bash)
```bash
#!/bin/bash
# scraper-monitor.sh - Check scraper health every 5 minutes

while true; do
  STATUS=$(curl -s http://localhost:8000/api/scraper/health | jq -r '.status')

  if [ "$STATUS" = "unhealthy" ]; then
    echo "ALERT: Scraper is unhealthy!"
    # Send alert (email, Slack, etc.)
  fi

  echo "$(date): Scraper status is $STATUS"
  sleep 300  # 5 minutes
done
```

---

## Webhooks (Future Enhancement)

*Not yet implemented, but planned:*

```json
POST /api/scraper/webhooks
{
  "url": "https://your-app.com/webhook",
  "events": ["job.completed", "job.failed"],
  "secret": "your-webhook-secret"
}
```

---

## Best Practices

1. **Health Monitoring:** Poll the health endpoint every 5-10 minutes
2. **Job History:** Query job history to track scraper performance trends
3. **Manual Triggers:** Use `max_pages` parameter for testing before full scrape
4. **Error Handling:** Always check response status codes and handle errors gracefully
5. **Token Management:** Refresh auth tokens before they expire
6. **Rate Limiting:** Implement exponential backoff for rate limit errors

---

## Support

For API issues or questions:
- Email: support@nabavkidata.com
- Documentation: https://nabavkidata.com/api/docs
- Status Page: https://status.nabavkidata.com
