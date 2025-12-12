# Historical Price Aggregation API - Quick Reference

## Endpoint

```
GET /api/ai/price-history/{cpv_code}
```

## Authentication

Required: Bearer token in Authorization header

```
Authorization: Bearer <your-jwt-token>
```

## Query Parameters

| Parameter | Type | Default | Required | Description |
|-----------|------|---------|----------|-------------|
| `months` | integer | 24 | No | Number of months to look back (1-120) |
| `group_by` | string | "month" | No | Time period: "month" or "quarter" |

## Response Format

```json
{
  "cpv_code": "50000000",
  "cpv_description": "Repair and maintenance services",
  "time_range": "2023-01 to 2025-11",
  "total_tenders": 64,
  "trend": "increasing",
  "trend_pct": 12.5,
  "data_points": [
    {
      "period": "2025-11",
      "tender_count": 64,
      "avg_estimated": 7762217.16,
      "avg_actual": 7200000.00,
      "avg_discount_pct": 7.24,
      "avg_bidders": 3.2
    }
  ]
}
```

## Response Fields

### Root Level

- **cpv_code**: The CPV code that was queried
- **cpv_description**: Human-readable description (can be null)
- **time_range**: "YYYY-MM to YYYY-MM" or "No data available"
- **total_tenders**: Total number of tenders across all periods
- **trend**: "increasing", "decreasing", or "stable"
- **trend_pct**: Percentage change (positive or negative)
- **data_points**: Array of time period data

### Data Point Fields

- **period**: "2024-11" (month) or "2024-Q4" (quarter)
- **tender_count**: Number of tenders in this period
- **avg_estimated**: Average estimated value in MKD (can be null)
- **avg_actual**: Average actual/winning value in MKD (can be null)
- **avg_discount_pct**: Average discount percentage (can be null)
- **avg_bidders**: Average number of bidders (can be null)

## Trend Classification

- **increasing**: Price trend increased by more than 5%
- **decreasing**: Price trend decreased by more than 5%
- **stable**: Price trend changed by less than ±5%

## Usage Examples

### JavaScript/TypeScript

```typescript
async function getPriceHistory(cpvCode: string, months: number = 24) {
  const response = await fetch(
    `/api/ai/price-history/${cpvCode}?months=${months}&group_by=month`,
    {
      headers: {
        'Authorization': `Bearer ${getToken()}`
      }
    }
  );

  if (!response.ok) {
    throw new Error('Failed to fetch price history');
  }

  return await response.json();
}

// Usage
const data = await getPriceHistory('50000000', 24);
console.log(`Trend: ${data.trend} (${data.trend_pct}%)`);
```

### React Component Example

```tsx
import { useState, useEffect } from 'react';

interface PriceHistoryData {
  cpv_code: string;
  cpv_description: string | null;
  time_range: string;
  total_tenders: number;
  trend: 'increasing' | 'decreasing' | 'stable';
  trend_pct: number;
  data_points: Array<{
    period: string;
    tender_count: number;
    avg_estimated: number | null;
    avg_actual: number | null;
    avg_discount_pct: number | null;
    avg_bidders: number | null;
  }>;
}

export function PriceHistoryChart({ cpvCode }: { cpvCode: string }) {
  const [data, setData] = useState<PriceHistoryData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const response = await fetch(
          `/api/ai/price-history/${cpvCode}?months=24&group_by=month`,
          {
            headers: {
              'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
          }
        );

        const result = await response.json();
        setData(result);
      } catch (error) {
        console.error('Error fetching price history:', error);
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, [cpvCode]);

  if (loading) return <div>Loading...</div>;
  if (!data) return <div>No data available</div>;

  return (
    <div>
      <h2>{data.cpv_description || data.cpv_code}</h2>
      <p>
        Trend: <TrendIndicator trend={data.trend} pct={data.trend_pct} />
      </p>
      <p>Total Tenders: {data.total_tenders}</p>
      <p>Time Range: {data.time_range}</p>

      {/* Render chart with data.data_points */}
      <Chart data={data.data_points} />
    </div>
  );
}

function TrendIndicator({ trend, pct }: { trend: string; pct: number }) {
  const icons = {
    increasing: '↑',
    decreasing: '↓',
    stable: '→'
  };

  const colors = {
    increasing: 'text-green-600',
    decreasing: 'text-red-600',
    stable: 'text-gray-600'
  };

  return (
    <span className={colors[trend]}>
      {icons[trend]} {trend} ({pct > 0 ? '+' : ''}{pct.toFixed(2)}%)
    </span>
  );
}
```

## Error Handling

### HTTP Status Codes

- **200**: Success
- **400**: Invalid CPV code format
- **401**: Unauthorized (missing/invalid token)
- **500**: Server error

### Example Error Response

```json
{
  "detail": "Invalid CPV code format. Must start with digits."
}
```

### Error Handling Example

```typescript
try {
  const response = await fetch(`/api/ai/price-history/${cpvCode}`);

  if (response.status === 400) {
    alert('Invalid CPV code');
    return;
  }

  if (response.status === 401) {
    // Redirect to login
    window.location.href = '/login';
    return;
  }

  if (!response.ok) {
    throw new Error('Server error');
  }

  const data = await response.json();
  // Use data...

} catch (error) {
  console.error('Error:', error);
  alert('Failed to load price history');
}
```

## Chart Visualization

### Recommended Chart Types

1. **Line Chart**: Show price trends over time
   - X-axis: period
   - Y-axis: avg_estimated or avg_actual
   - Multiple lines: estimated vs actual

2. **Bar Chart**: Show tender counts by period
   - X-axis: period
   - Y-axis: tender_count

3. **Combo Chart**: Combine line and bar
   - Bars: tender_count
   - Lines: avg_estimated, avg_actual

### Chart.js Example

```javascript
import { Line } from 'react-chartjs-2';

function PriceChart({ data }) {
  const chartData = {
    labels: data.data_points.map(p => p.period),
    datasets: [
      {
        label: 'Average Estimated',
        data: data.data_points.map(p => p.avg_estimated),
        borderColor: 'rgb(75, 192, 192)',
        backgroundColor: 'rgba(75, 192, 192, 0.2)',
      },
      {
        label: 'Average Actual',
        data: data.data_points.map(p => p.avg_actual),
        borderColor: 'rgb(255, 99, 132)',
        backgroundColor: 'rgba(255, 99, 132, 0.2)',
      }
    ]
  };

  const options = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top',
      },
      title: {
        display: true,
        text: `Price History: ${data.cpv_description || data.cpv_code}`
      }
    },
    scales: {
      y: {
        beginAtZero: false,
        ticks: {
          callback: function(value) {
            return value.toLocaleString() + ' MKD';
          }
        }
      }
    }
  };

  return <Line data={chartData} options={options} />;
}
```

## Common Use Cases

### 1. Display Price Trends for Specific Category

```typescript
// On tender details page
const priceHistory = await getPriceHistory(tender.cpv_code, 12);
```

### 2. Compare Monthly vs Quarterly

```typescript
const monthly = await getPriceHistory(cpvCode, 24, 'month');
const quarterly = await getPriceHistory(cpvCode, 24, 'quarter');
```

### 3. Market Analysis Dashboard

```typescript
// Get data for multiple CPV codes
const cpvCodes = ['50000000', '45000000', '09000000'];
const histories = await Promise.all(
  cpvCodes.map(code => getPriceHistory(code, 12))
);

// Display comparison charts
```

### 4. Trend Alerts

```typescript
const data = await getPriceHistory(cpvCode, 6);

if (data.trend === 'increasing' && data.trend_pct > 10) {
  showAlert(`Prices trending up ${data.trend_pct}% - Consider bidding soon`);
}

if (data.trend === 'decreasing' && data.trend_pct < -10) {
  showAlert(`Prices trending down ${data.trend_pct}% - Wait for better rates`);
}
```

## Performance Tips

1. **Cache Results**: Price history data doesn't change frequently
   ```typescript
   // Cache for 1 hour
   const cacheKey = `price-history-${cpvCode}-${months}`;
   const cached = localStorage.getItem(cacheKey);
   if (cached) {
     const { data, timestamp } = JSON.parse(cached);
     if (Date.now() - timestamp < 3600000) {
       return data;
     }
   }
   ```

2. **Lazy Load**: Only fetch when needed
   ```tsx
   // Load on tab click or section expansion
   <Tabs>
     <Tab label="Overview" />
     <Tab label="Price History" onClick={() => fetchPriceHistory()} />
   </Tabs>
   ```

3. **Debounce Requests**: If user can change CPV code
   ```typescript
   import { debounce } from 'lodash';

   const debouncedFetch = debounce((cpvCode) => {
     fetchPriceHistory(cpvCode);
   }, 500);
   ```

## Testing

### Manual Testing

```bash
# Replace <TOKEN> with your JWT token
curl -H "Authorization: Bearer <TOKEN>" \
  "http://localhost:8000/api/ai/price-history/50000000?months=24&group_by=month"
```

### Integration Test Example

```typescript
describe('PriceHistoryAPI', () => {
  it('should fetch price history successfully', async () => {
    const data = await getPriceHistory('50000000', 24);

    expect(data).toBeDefined();
    expect(data.cpv_code).toBe('50000000');
    expect(data.data_points).toBeInstanceOf(Array);
    expect(['increasing', 'decreasing', 'stable']).toContain(data.trend);
  });

  it('should handle invalid CPV code', async () => {
    await expect(getPriceHistory('INVALID')).rejects.toThrow();
  });
});
```

## API Lib Integration

### Add to `/frontend/lib/api.ts`

```typescript
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
  return apiClient.get(`/ai/price-history/${cpvCode}`, {
    params: { months, group_by: groupBy }
  });
}
```

## Questions?

- API Docs: http://localhost:8000/api/docs
- Health Check: http://localhost:8000/api/ai/pricing-health
- Full Documentation: See `PHASE_4_2_AUDIT_REPORT.md`
