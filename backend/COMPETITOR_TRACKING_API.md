# Competitor Tracking API - Phase 5.1 Implementation

## Overview
Complete backend implementation for competitor tracking functionality as specified in Phase 5.1 of the UI Refactor Roadmap.

## Database Schema

### Table: `tracked_competitors`
Stores user-tracked competitor companies.

```sql
CREATE TABLE tracked_competitors (
    tracking_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    company_name VARCHAR(500) NOT NULL,
    tax_id VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_user_company UNIQUE(user_id, company_name)
);
```

**Indexes:**
- `idx_tracked_competitors_user_id` on `user_id`
- `idx_tracked_competitors_company_name` on `company_name`

### Table: `competitor_stats`
Aggregated statistics for competitor analysis.

```sql
CREATE TABLE competitor_stats (
    stat_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name VARCHAR(500) NOT NULL UNIQUE,
    total_bids INTEGER DEFAULT 0,
    total_wins INTEGER DEFAULT 0,
    win_rate NUMERIC(5,2),
    avg_bid_discount NUMERIC(5,2),
    top_cpv_codes JSONB,
    top_categories JSONB,
    recent_tenders JSONB,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Indexes:**
- `idx_competitor_stats_company_name` on `company_name`

## API Endpoints

### 1. GET /api/competitors
**Description:** List user's tracked competitors

**Authentication:** Required (JWT)

**Response:**
```json
{
  "total": 5,
  "items": [
    {
      "tracking_id": "uuid",
      "user_id": "uuid",
      "company_name": "Company Name",
      "tax_id": "123456789",
      "notes": "Main competitor",
      "created_at": "2025-12-02T10:00:00"
    }
  ]
}
```

### 2. POST /api/competitors
**Description:** Add a company to tracked list

**Authentication:** Required (JWT)

**Request Body:**
```json
{
  "company_name": "Company Name",
  "tax_id": "123456789",
  "notes": "Optional notes"
}
```

**Response:** 201 Created
```json
{
  "tracking_id": "uuid",
  "user_id": "uuid",
  "company_name": "Company Name",
  "tax_id": "123456789",
  "notes": "Optional notes",
  "created_at": "2025-12-02T10:00:00"
}
```

**Validations:**
- Company must exist in `tender_bidders` table
- Prevents duplicate tracking (unique constraint)

### 3. DELETE /api/competitors/{tracking_id}
**Description:** Remove a company from tracked list

**Authentication:** Required (JWT)

**Response:**
```json
{
  "message": "Competitor removed from tracking",
  "detail": "Stopped tracking Company Name"
}
```

### 4. GET /api/competitors/{company_name}/stats
**Description:** Get detailed statistics for a competitor

**Authentication:** Required (JWT)

**Response:**
```json
{
  "company_name": "Company Name",
  "total_bids": 44,
  "total_wins": 37,
  "win_rate": 84.09,
  "avg_bid_discount": 2.02,
  "top_cpv_codes": [
    {
      "cpv_code": "72000000",
      "category": "IT services",
      "bid_count": 15
    }
  ],
  "top_categories": [
    {
      "category": "IT services",
      "bid_count": 20
    }
  ],
  "recent_tenders": [
    {
      "tender_id": "uuid",
      "title": "Tender title",
      "procuring_entity": "Entity name",
      "bid_amount_mkd": 100000,
      "estimated_value_mkd": 120000,
      "is_winner": true,
      "rank": 1,
      "closing_date": "2025-11-01",
      "status": "awarded"
    }
  ],
  "last_updated": "2025-12-02T10:00:00"
}
```

**Statistics Calculation:**
- Total bids: Count of all bids by company
- Total wins: Count of bids where `is_winner = true`
- Win rate: Percentage of wins vs total bids
- Avg bid discount: Average percentage discount from estimated value
- Top CPV codes: Top 5 CPV categories by bid count
- Top categories: Top 5 tender categories by bid count
- Recent tenders: Last 10 tenders ordered by closing date

### 5. GET /api/competitors/search?q={query}
**Description:** Search for companies in tender database

**Authentication:** Required (JWT)

**Query Parameters:**
- `q` (required): Search query, min 2 characters
- `limit` (optional): Max results, default 20, max 100

**Response:**
```json
{
  "total": 15,
  "items": [
    {
      "company_name": "Company Name",
      "tax_id": "123456789",
      "total_bids": 44,
      "total_wins": 37,
      "win_rate": 84.09,
      "total_contract_value": 15000000.00
    }
  ]
}
```

## Implementation Details

### Files Created/Modified

1. **Database Schema:**
   - Created `tracked_competitors` table
   - Created `competitor_stats` table
   - Populated `competitor_stats` with initial data (1,238 companies)

2. **Backend API:**
   - `/backend/api/competitor_tracking.py` - New API router
   - `/backend/schemas.py` - Added competitor schemas
   - `/backend/main.py` - Added router import and registration

3. **Schemas Added:**
   - `TrackedCompetitorCreate`
   - `TrackedCompetitorResponse`
   - `TrackedCompetitorListResponse`
   - `CompetitorTender`
   - `CompetitorStatsResponse`
   - `CompetitorSearchResult`
   - `CompetitorSearchResponse`

### Key Features

1. **Real-time Stats:** Statistics are updated on-demand when viewing competitor details
2. **Efficient Queries:** Uses indexes and aggregated stats table for performance
3. **User Isolation:** Each user can track their own set of competitors
4. **Validation:** Prevents tracking non-existent companies
5. **Duplicate Prevention:** Unique constraint on (user_id, company_name)

### Performance Optimizations

1. **Indexes:**
   - B-tree indexes on frequently queried columns
   - Composite unique index for duplicate prevention

2. **Aggregation:**
   - Pre-calculated stats in `competitor_stats` table
   - On-demand updates only when viewing specific company

3. **Query Optimization:**
   - FILTER clauses for conditional aggregation
   - NULLS LAST for ordering
   - Subqueries for JSONB aggregation

## Testing

All queries tested successfully:
- Search query returns results efficiently
- Stats calculation accurate
- Recent tenders ordered correctly
- All table constraints working

**Database Status:**
- tracked_competitors: 0 rows (ready for user data)
- competitor_stats: 1,238 rows (pre-populated)
- tender_bidders: 18,462 rows (source data)
- users: 7 rows

## Security

1. **Authentication:** All endpoints require JWT authentication
2. **Authorization:** Users can only modify their own tracked competitors
3. **Input Validation:** Pydantic schemas validate all inputs
4. **SQL Injection:** Protected by parameterized queries

## Integration Notes

### Frontend Integration
The API is ready for frontend integration. Example usage:

```typescript
// Search for companies
const results = await fetch('/api/competitors/search?q=Македонски', {
  headers: { 'Authorization': `Bearer ${token}` }
});

// Add to tracking
await fetch('/api/competitors', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    company_name: 'Company Name',
    notes: 'Main competitor'
  })
});

// Get statistics
const stats = await fetch('/api/competitors/Company%20Name/stats', {
  headers: { 'Authorization': `Bearer ${token}` }
});
```

## Next Steps

Phase 5.1 is now **COMPLETE**. Ready for:
1. Frontend UI implementation
2. Integration with existing tender pages
3. User acceptance testing

---

**Implementation Date:** December 2, 2025
**Developer:** Claude Code
**Status:** ✅ Complete and tested
