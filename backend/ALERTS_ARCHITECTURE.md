# Alert Matching Engine - Architecture Overview

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Next.js)                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │ Alert Config │  │ Match Viewer │  │ Notifications│             │
│  │   Dashboard  │  │   Component  │  │    Center    │             │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘             │
│         │                  │                  │                     │
│         └──────────────────┼──────────────────┘                     │
│                            │ REST API (JWT Auth)                    │
└────────────────────────────┼────────────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │   FastAPI App   │
                    │  (main.py)      │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        │            ┌───────▼───────┐           │
        │            │  alerts.router │           │
        │            │  (/api/alerts) │           │
        │            └───────┬────────┘           │
        │                    │                    │
┌───────▼───────┐   ┌────────▼────────┐   ┌──────▼──────┐
│ Middleware    │   │  Alert Endpoints │   │  Database   │
│ - Auth (JWT)  │   │  - List Alerts   │   │ PostgreSQL  │
│ - Rate Limit  │   │  - Create Alert  │   │             │
│ - Fraud Prev. │   │  - Update Alert  │   │ Tables:     │
└───────────────┘   │  - Delete Alert  │   │ - tender_   │
                    │  - Get Matches   │   │   alerts    │
                    │  - Mark Read     │   │ - alert_    │
                    │  - Check Now     │   │   matches   │
                    └────────┬─────────┘   │ - tenders   │
                             │              └──────┬──────┘
                    ┌────────▼─────────┐           │
                    │ Matching Engine  │           │
                    │ - check_alert_   │◄──────────┘
                    │   against_tender │  Queries
                    │ - check_alerts_  │
                    │   for_user       │
                    └──────────────────┘
```

## Data Flow Diagram

### 1. Create Alert Flow
```
User → Frontend → POST /api/alerts → [Auth Check] → Validate Alert Type
                                           ↓
                                    Insert to DB
                                           ↓
                                    Return AlertResponse
                                           ↓
                                    Frontend Updates UI
```

### 2. Match Detection Flow
```
Cron Job → check_alerts_for_user() → Fetch Active Alerts
               │                            ↓
               │                     Fetch Recent Tenders
               │                            ↓
               │                ┌───────────▼───────────┐
               │                │  For Each Alert:      │
               │                │  For Each Tender:     │
               │                │  - Check if matched   │
               │                │  - Run algorithm      │
               │                │  - Insert if score>0  │
               │                └───────────┬───────────┘
               │                            ↓
               └──────────────────► Commit Matches to DB
```

### 3. User Views Matches Flow
```
User → GET /api/alerts/{id}/matches → [Auth + Ownership Check]
                                              ↓
                                       Fetch Matches
                                              ↓
                                    Join with Tenders
                                              ↓
                                    Return with Details
                                              ↓
                                    Frontend Displays
```

## Database Schema

### Entity Relationship Diagram
```
┌─────────────────┐
│     users       │
│─────────────────│
│ user_id (PK)    │◄────────┐
│ email           │         │
│ password_hash   │         │
└─────────────────┘         │
                            │
                    ┌───────┴──────────┐
                    │                  │
            ┌───────▼──────────┐       │
            │  tender_alerts   │       │
            │──────────────────│       │
            │ alert_id (PK)    │       │
            │ user_id (FK)     │───────┘
            │ name             │
            │ alert_type       │
            │ criteria (JSONB) │
            │ is_active        │
            │ notification_ch. │
            │ created_at       │
            │ updated_at       │
            └───────┬──────────┘
                    │
                    │ 1:N
                    │
            ┌───────▼──────────┐       ┌─────────────────┐
            │  alert_matches   │       │    tenders      │
            │──────────────────│       │─────────────────│
            │ match_id (PK)    │       │ tender_id (PK)  │
            │ alert_id (FK)    │       │ title           │
            │ tender_id        │───────►│ description     │
            │ tender_source    │       │ cpv_code        │
            │ match_score      │       │ procuring_ent.  │
            │ match_reasons    │       │ estimated_value │
            │ is_read          │       │ winner          │
            │ notified_at      │       │ ...             │
            │ created_at       │       └─────────────────┘
            └──────────────────┘
```

## Alert Matching Algorithm

### Matching Process Flow
```
┌─────────────────────────────────────────────────────────────┐
│                 check_alert_against_tender()                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Input: alert (criteria), tender (details)                 │
│                                                             │
│  ┌─────────────────────────────────────────────────┐       │
│  │ 1. Keyword Matching (25 points)                 │       │
│  │    - Combine title + description                │       │
│  │    - Case-insensitive search                    │       │
│  │    - Match any keyword in list                  │       │
│  └─────────────────────────────────────────────────┘       │
│                      ↓                                      │
│  ┌─────────────────────────────────────────────────┐       │
│  │ 2. CPV Code Matching (30 points)                │       │
│  │    - Match first 4 digits (category level)      │       │
│  │    - Allows broader category matching           │       │
│  └─────────────────────────────────────────────────┘       │
│                      ↓                                      │
│  ┌─────────────────────────────────────────────────┐       │
│  │ 3. Entity Matching (25 points)                  │       │
│  │    - Case-insensitive substring match           │       │
│  │    - Match in procuring_entity field            │       │
│  └─────────────────────────────────────────────────┘       │
│                      ↓                                      │
│  ┌─────────────────────────────────────────────────┐       │
│  │ 4. Budget Range Matching (20 points)            │       │
│  │    - Check if value in [min, max] range         │       │
│  │    - Supports min-only or max-only              │       │
│  └─────────────────────────────────────────────────┘       │
│                      ↓                                      │
│  ┌─────────────────────────────────────────────────┐       │
│  │ 5. Competitor Tracking (25 points)              │       │
│  │    - Match in winner field                      │       │
│  │    - Case-insensitive substring match           │       │
│  └─────────────────────────────────────────────────┘       │
│                      ↓                                      │
│  ┌─────────────────────────────────────────────────┐       │
│  │ Score Calculation                               │       │
│  │    - Sum all matched criteria scores            │       │
│  │    - Cap at 100 maximum                         │       │
│  │    - Match if score > 0                         │       │
│  └─────────────────────────────────────────────────┘       │
│                      ↓                                      │
│  Output: (matches: bool, score: float, reasons: list)      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## API Request/Response Flow

### Example: Create Combined Alert
```
REQUEST:
POST /api/alerts
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json

{
  "name": "High Value IT for Ministries",
  "alert_type": "combined",
  "criteria": {
    "keywords": ["software", "hardware"],
    "cpv_codes": ["3021"],
    "entities": ["Министерство"],
    "budget_min": 500000
  },
  "notification_channels": ["email", "in_app"]
}

PROCESSING:
1. Middleware: Rate Limit Check ✓
2. Middleware: Fraud Prevention ✓
3. Auth: Decode JWT → get user_id ✓
4. Validate: alert_type in valid_types ✓
5. Validate: Pydantic schema ✓
6. Database: INSERT INTO tender_alerts ✓
7. Database: COMMIT ✓

RESPONSE:
HTTP 201 Created
{
  "alert_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "user_id": "u1u2u3u4-u5u6-u7u8-u9u0-uuuuuuuuuuuu",
  "name": "High Value IT for Ministries",
  "alert_type": "combined",
  "criteria": {
    "keywords": ["software", "hardware"],
    "cpv_codes": ["3021"],
    "entities": ["Министерство"],
    "budget_min": 500000
  },
  "is_active": true,
  "notification_channels": ["email", "in_app"],
  "created_at": "2025-12-02T10:30:00",
  "updated_at": "2025-12-02T10:30:00"
}
```

## Performance Optimization Strategy

### Database Indexes
```
┌──────────────────────────────────────────────────────────┐
│ Index Name            │ Table          │ Purpose         │
├──────────────────────────────────────────────────────────┤
│ idx_alerts_user       │ tender_alerts  │ Fast user query │
│ idx_alerts_active     │ tender_alerts  │ Filter active   │
│ idx_matches_alert     │ alert_matches  │ Fast retrieval  │
│ idx_matches_unread    │ alert_matches  │ Notification Q  │
│   (Partial Index)     │                │ (WHERE NOT read)│
└──────────────────────────────────────────────────────────┘

Query Patterns:
- List alerts: Uses idx_alerts_user
- Get matches: Uses idx_matches_alert
- Unread count: Uses idx_matches_unread (partial index)
- Batch check: Uses idx_alerts_active
```

### Query Optimization
```
Technique               Impact
─────────────────────  ──────────────────────────────
Pagination             Prevents large result sets
Async/Await            Non-blocking I/O operations
Batch Commits          Reduces DB round-trips
Duplicate Detection    Prevents re-processing
Optional Counts        Can skip expensive aggregation
Parameterized Queries  Query plan caching
Connection Pooling     Reuses DB connections
```

## Security Architecture

### Authentication Flow
```
1. User Login → JWT Token Generated
              ↓
2. Frontend stores token (localStorage/cookie)
              ↓
3. API Request with Authorization: Bearer {token}
              ↓
4. oauth2_scheme extracts token
              ↓
5. get_current_user() dependency:
   - Decode JWT
   - Validate signature
   - Check expiration
   - Fetch user from DB
              ↓
6. Endpoint receives User object
              ↓
7. Ownership validation (if needed)
              ↓
8. Process request
```

### Authorization Checks
```
Endpoint                Check Performed
─────────────────────  ──────────────────────────────
GET /alerts            User authenticated
POST /alerts           User authenticated
PUT /alerts/{id}       User owns alert
DELETE /alerts/{id}    User owns alert
GET /alerts/{id}/m...  User owns alert
POST /mark-read        User owns all alerts in request
POST /check-now        User authenticated
```

## Scalability Considerations

### Current Capacity
```
Component            Current Limit        Notes
──────────────────  ──────────────────  ──────────────────────
Alerts per user      Unlimited           Practical: ~100
Matches per alert    Unlimited           Paginated responses
Tenders scanned      100 per check       Configurable
Concurrent users     500+                Connection pool: 5+10
API rate limit       Via middleware      Protects from abuse
```

### Future Scaling Strategy
```
┌─────────────────────────────────────────────────────────┐
│ Growth Stage  │ Solution                                │
├─────────────────────────────────────────────────────────┤
│ 1K users      │ Current setup sufficient                │
│ 10K users     │ - Increase connection pool              │
│               │ - Add Redis caching                     │
│ 100K users    │ - Job queue (Celery/RQ)                 │
│               │ - Read replicas                         │
│ 1M users      │ - Sharding by user_id                   │
│               │ - Separate matching service             │
│               │ - Message queue (RabbitMQ/Kafka)        │
└─────────────────────────────────────────────────────────┘
```

## Integration with Phase 6.2 (Daily Briefings)

### Proposed Architecture
```
┌──────────────────────────────────────────────────────────┐
│                    Cron Job (7:00 AM)                    │
│  ┌────────────────────────────────────────────────────┐  │
│  │ scripts/run_daily_alerts.py                        │  │
│  │                                                     │  │
│  │ 1. Fetch all users with active alerts             │  │
│  │ 2. For each user:                                  │  │
│  │    - check_alerts_for_user()                       │  │
│  │    - Collect new matches                           │  │
│  │ 3. Group matches by user                           │  │
│  │ 4. Generate email digest                           │  │
│  │ 5. Send via POSTMARK                               │  │
│  │ 6. Update notified_at timestamp                    │  │
│  │ 7. Log to cron_executions table                    │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────┐
│                   Email Template                         │
│  ┌────────────────────────────────────────────────────┐  │
│  │ Subject: Daily Tender Alert Digest - 12 New Matches│  │
│  │                                                     │  │
│  │ Alert: "High Value IT Tenders"                     │  │
│  │ - Tender: OP-123-2025 (Score: 75)                  │  │
│  │   • Keywords matched: software, компјутер          │  │
│  │   • CPV matched: 3021                              │  │
│  │   • Budget in range: 500,000 MKD                   │  │
│  │                                                     │  │
│  │ [View All Matches] [Manage Alerts]                 │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

## Monitoring and Observability

### Key Metrics to Track
```
Metric                    Type         Purpose
────────────────────────  ───────────  ────────────────────────
alerts_created_total      Counter      Track alert creation rate
matches_found_total       Counter      Track matching effectiveness
check_duration_seconds    Histogram    Monitor performance
api_request_duration      Histogram    API performance
active_alerts_gauge       Gauge        Current active alerts
unread_matches_gauge      Gauge        Pending notifications
errors_total              Counter      Track failures
```

### Logging Strategy
```python
# Example logging points
logger.info(f"Alert created: {alert_id} for user {user_id}")
logger.info(f"Match check: {matches_found} matches in {duration}ms")
logger.warning(f"No tenders to check for user {user_id}")
logger.error(f"Failed to create alert: {error}")
```

---

**Architecture Version:** 1.0
**Last Updated:** December 2, 2025
**Status:** Production Ready
