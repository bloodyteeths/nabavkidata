# Competitor Bidding Patterns API - Quick Start Guide

## Overview

The Competitor Bidding Patterns API endpoint analyzes competitor behavior in Macedonian public procurement tenders.

## Endpoint

```
GET /api/competitors/{company_name}/patterns
```

## Quick Examples

### Basic Usage

```bash
# Analyze company with default 24-month period
curl "http://localhost:8000/api/competitors/MedTech%20DOO/patterns"
```

### Custom Analysis Period

```bash
# Analyze last 12 months
curl "http://localhost:8000/api/competitors/MedTech%20DOO/patterns?analysis_months=12"

# Analyze last 36 months
curl "http://localhost:8000/api/competitors/MedTech%20DOO/patterns?analysis_months=36"
```

### Python Example

```python
import httpx
import asyncio

async def get_competitor_patterns(company_name: str, months: int = 24):
    url = f"http://localhost:8000/api/competitors/{company_name}/patterns"
    params = {"analysis_months": months}

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        return response.json()

# Usage
data = asyncio.run(get_competitor_patterns("MedTech DOO", 12))
print(f"Win Rate: {data['overall_win_rate']:.1f}%")
print(f"Avg Discount: {data['pricing_pattern']['avg_discount']:.1f}%")
```

### JavaScript/TypeScript Example

```typescript
async function getCompetitorPatterns(companyName: string, months: number = 24) {
  const url = `/api/competitors/${encodeURIComponent(companyName)}/patterns`;
  const params = new URLSearchParams({ analysis_months: months.toString() });

  const response = await fetch(`${url}?${params}`);
  return await response.json();
}

// Usage
const data = await getCompetitorPatterns("MedTech DOO", 12);
console.log(`Win Rate: ${data.overall_win_rate.toFixed(1)}%`);
console.log(`Avg Discount: ${data.pricing_pattern.avg_discount.toFixed(1)}%`);
```

## Response Structure

```json
{
  "company_name": "Company Name",
  "analysis_period": "24 months",
  "total_bids": 100,
  "total_wins": 67,
  "overall_win_rate": 67.0,

  "pricing_pattern": {
    "avg_discount": 15.5,
    "discount_range": {"min": 2.0, "max": 30.0},
    "price_consistency": 0.82,
    "avg_bid_mkd": 1500000.0,
    "median_bid_mkd": 1200000.0
  },

  "category_preferences": [
    {
      "cpv_code": "33100000",
      "name": "Medical equipment",
      "count": 45,
      "win_rate": 67.0
    }
  ],

  "size_preferences": {
    "small": {"range": "0-500K MKD", "count": 20, "win_rate": 55.0},
    "medium": {"range": "500K-2M MKD", "count": 50, "win_rate": 72.0},
    "large": {"range": "2M+ MKD", "count": 30, "win_rate": 65.0}
  },

  "seasonal_activity": [
    {"month": "January", "bids": 8, "wins": 5}
  ],

  "top_competitors": [
    {
      "company": "Competitor A",
      "overlap_count": 25,
      "head_to_head_wins": 15,
      "head_to_head_losses": 10
    }
  ],

  "win_factors": {
    "discount_correlation": "Wins with moderate discounts (balanced approach)",
    "preferred_size": "Medium tenders (500K-2M MKD)",
    "preferred_categories": ["Medical equipment (33100000)"],
    "success_rate_by_entity_type": {
      "Hospital": 75.0,
      "University": 60.0
    }
  }
}
```

## Key Metrics Explained

### Pricing Pattern

- **avg_discount**: Average discount percentage from estimated value
  - Positive = bid below estimate
  - Negative = bid above estimate

- **price_consistency**: Score from 0-1 indicating pricing predictability
  - 1.0 = Very consistent
  - 0.5 = Moderate variation
  - 0.0 = Highly variable

### Category Preferences

Top 5 CPV codes the company bids on, sorted by frequency.

### Size Preferences

Tender categorization:
- **Small**: 0 - 500,000 MKD
- **Medium**: 500,000 - 2,000,000 MKD
- **Large**: 2,000,000+ MKD

### Win Factors

**Discount Correlation:**
- "Wins with minimal discount" = avg_discount < 5%
- "Wins with moderate discounts" = 5% ≤ avg_discount ≤ 20%
- "Wins with aggressive discounts" = avg_discount > 20%

**Preferred Size:**
Tender size category with highest win rate

**Success Rate by Entity Type:**
Win rates broken down by procuring entity category (minimum 3 bids required)

## Error Codes

- **200 OK**: Successful analysis
- **404 Not Found**: Company has no bidding data in the period
- **422 Validation Error**: Invalid parameters
  - `analysis_months` must be 1-60

## Performance Notes

- **Response Time**: 1-5 seconds depending on company size
- **Data Freshness**: Real-time query, no caching
- **Concurrent Requests**: Rate limited via middleware

## Testing

### Test with Real Data

```bash
# Find a company with bidding history
curl "http://localhost:8000/api/suppliers/winners?limit=5"

# Use a company name from the results
curl "http://localhost:8000/api/competitors/[COMPANY_NAME]/patterns"
```

### Automated Testing

```python
# Run the provided test script
cd backend
source venv/bin/activate
python3 test_patterns_api.py
```

## Common Use Cases

### 1. Competitive Intelligence Dashboard

```typescript
// Fetch patterns for multiple competitors
const competitors = ["Company A", "Company B", "Company C"];
const patterns = await Promise.all(
  competitors.map(name => getCompetitorPatterns(name, 12))
);

// Compare win rates
const winRates = patterns.map(p => ({
  name: p.company_name,
  winRate: p.overall_win_rate
}));
```

### 2. Pricing Strategy Analysis

```python
# Analyze competitor discount strategies
data = await get_competitor_patterns("Competitor Inc")
pricing = data['pricing_pattern']

if pricing['avg_discount'] > 20:
    strategy = "Aggressive pricing"
elif pricing['avg_discount'] < 5:
    strategy = "Premium positioning"
else:
    strategy = "Balanced approach"
```

### 3. Market Opportunity Identification

```python
# Find categories where competitor has low win rate
data = await get_competitor_patterns("Competitor Inc")
weak_categories = [
    cat for cat in data['category_preferences']
    if cat['win_rate'] < 50
]
```

## Integration with Frontend

### React Component Example

```tsx
import { useQuery } from '@tanstack/react-query';

function CompetitorAnalysis({ companyName }: { companyName: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['competitor-patterns', companyName],
    queryFn: () => getCompetitorPatterns(companyName)
  });

  if (isLoading) return <Spinner />;

  return (
    <div>
      <h2>{data.company_name}</h2>
      <MetricCard
        title="Win Rate"
        value={`${data.overall_win_rate.toFixed(1)}%`}
      />
      <MetricCard
        title="Average Discount"
        value={`${data.pricing_pattern.avg_discount.toFixed(1)}%`}
      />
      <CategoryChart data={data.category_preferences} />
    </div>
  );
}
```

## Database Requirements

The endpoint requires the following tables:
- `tender_bidders` - Bidder participation data
- `tenders` - Tender metadata

**Minimum Data:**
- At least 3 bids for meaningful analysis
- Closing dates within analysis period

## Support

For issues or questions:
1. Check the comprehensive audit report: `BIDDING_PATTERN_ANALYSIS_AUDIT.md`
2. Review OpenAPI docs: `http://localhost:8000/api/docs`
3. Run test scripts: `test_competitor_patterns.py`

## Related Endpoints

- `GET /api/suppliers/winners` - Get list of companies with wins
- `GET /api/suppliers/search/{name}` - Search for companies
- `GET /api/competitors/activity` - Get competitor activity feed
