# AI Bid Advisor - Quick Reference Guide

## Endpoint
```
GET /api/ai/bid-advisor/{number}/{year}
```

## Example Request
```bash
curl -X GET "https://api.nabavkidata.com/api/ai/bid-advisor/18836/2025" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `tender_id` | string | Full tender ID (e.g., "18836/2025") |
| `tender_title` | string | Tender title in Macedonian |
| `estimated_value` | float | Procuring entity's estimated value (MKD) |
| `cpv_code` | string | Common Procurement Vocabulary code |
| `category` | string | Tender category |
| `procuring_entity` | string | Institution issuing the tender |
| `market_analysis` | object | Market-level statistics |
| `historical_data` | object | Historical tender statistics |
| `recommendations` | array | 3 bid strategies (aggressive, balanced, safe) |
| `competitor_insights` | array | Top 10 competitor performance |
| `ai_summary` | string | AI-generated summary in Macedonian |
| `generated_at` | string | ISO timestamp of generation |

## Recommendation Strategies

### 1. Aggressive (High Risk, Low Price)
- **Target:** Win on price
- **Price Point:** ~15% below median
- **Win Probability:** ~45%
- **Risk:** May not cover costs or be unrealistic

### 2. Balanced (Moderate Risk, Market Price)
- **Target:** Competitive bid
- **Price Point:** Market median
- **Win Probability:** ~65%
- **Risk:** Standard market competition

### 3. Safe (Low Risk, Higher Price)
- **Target:** Higher chance of winning
- **Price Point:** ~15% above median
- **Win Probability:** ~85%
- **Risk:** May lose to lower bidders

## Market Analysis Fields

```json
{
  "avg_discount_percentage": 8.5,       // Average % below estimate
  "typical_bidders_per_tender": 3.2,    // Avg # of bidders
  "price_trend": "stable",              // "increasing", "decreasing", "stable"
  "competition_level": "high"           // "high" or "medium"
}
```

## Historical Data Fields

```json
{
  "similar_tenders": 1242,              // # of similar tenders analyzed
  "total_bids_analyzed": 3876,          // Total # of bids
  "winning_bids_count": 1242,           // # of winning bids
  "avg_winning_bid": 1233340.00,        // Mean winning bid
  "median_winning_bid": 1016754.00,     // Median winning bid
  "min_winning_bid": 32812.00,          // Minimum winning bid
  "max_winning_bid": 5297610.00,        // Maximum winning bid
  "std_dev": 1205678.50                 // Standard deviation
}
```

## Competitor Insights Fields

```json
[
  {
    "company": "Company Name",
    "total_bids": 25,
    "total_wins": 12,
    "win_rate": 48.0,                   // Win percentage
    "avg_bid_mkd": 1150000.00,
    "avg_discount_percentage": 7.5      // Average discount on wins
  }
]
```

## Error Codes

| Code | Message | Fix |
|------|---------|-----|
| 401 | Unauthorized | Add valid JWT token |
| 404 | Tender not found | Check tender ID format |
| 404 | No historical data | Tender has no comparable data |
| 500 | Database query failed | Contact support |

## Data Sources

1. **Similar Tenders:** Matched by CPV code, category, or 2-digit CPV prefix
2. **Time Range:** Last 2 years of awarded tenders
3. **Status Filter:** Only "awarded" tenders with actual values
4. **Competitor Data:** Top 10 by win count in similar tenders

## AI Integration

- **Model:** Gemini 1.5 Flash
- **Language:** Macedonian
- **Fallback:** Statistical recommendations if AI unavailable
- **Response Time:** 1-4 seconds

## File Locations

- **Endpoint:** `/Users/tamsar/Downloads/nabavkidata/backend/api/pricing.py` (lines 374-789)
- **Schemas:** `/Users/tamsar/Downloads/nabavkidata/backend/schemas.py` (lines 820-841)
- **Router:** Registered in `main.py` line 80

## Testing

### Health Check
```bash
curl https://api.nabavkidata.com/api/ai/pricing-health
```

### Database Test
```python
# Test tender with known data
tender_id = "18836/2025"
# Expected: 1242 similar tenders, median bid ~1,016,754 MKD
```

## Best Practices

1. **Cache responses** for frequently queried tenders
2. **Monitor AI availability** via health endpoint
3. **Validate tender ID** format before calling
4. **Handle 404 errors** gracefully (no data available)
5. **Display all 3 strategies** to users for informed decision

## Support

- **Documentation:** `/api/docs` (FastAPI auto-generated)
- **Audit Report:** `BID_ADVISOR_AUDIT_REPORT.md`
- **Status:** Production-ready ✅
