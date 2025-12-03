# Price History Chart Component - Developer Guide

## Overview

The `PriceHistoryChart` component provides advanced visualization of tender price trends over time, showing estimated vs actual values with trend analysis and market insights.

## Location

```
/components/pricing/PriceHistoryChart.tsx
```

## Features

- 📊 **Dual-line chart** showing estimated and actual/winning values
- 📈 **Trend analysis** with automatic calculation and visual indicators
- 💰 **Savings visualization** with gradient fill between lines
- 🎯 **Interactive tooltips** with detailed period information
- 📱 **Responsive design** that adapts to all screen sizes
- 🌐 **Macedonian labels** and currency formatting
- 📉 **Summary statistics** below the chart

## Usage

### Basic Example

```tsx
import { PriceHistoryChart } from "@/components/pricing/PriceHistoryChart";

function MyComponent() {
  const data = [
    {
      period: "2024-01",
      tender_count: 8,
      avg_estimated_mkd: 4500000,
      avg_awarded_mkd: 4100000,
      avg_discount_pct: 8.9,
      avg_bidders: 4.2,
    },
    // ... more data points
  ];

  return (
    <PriceHistoryChart
      data={data}
      cpvCode="33100000"
      title="Пазарна историја на цени"
      showTrend={true}
    />
  );
}
```

### Advanced Example with API

```tsx
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PriceHistoryChart } from "@/components/pricing/PriceHistoryChart";

function TenderDetailPage({ tenderId, cpvCode }) {
  const [priceHistory, setPriceHistory] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    async function loadData() {
      if (!cpvCode) return;

      try {
        setLoading(true);
        const result = await api.getPriceHistory(cpvCode, 12, {
          period: '1y'
        });
        setPriceHistory(result);
      } catch (error) {
        console.error("Failed to load price history:", error);
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [cpvCode]);

  if (loading) {
    return <div>Loading...</div>;
  }

  if (!priceHistory || priceHistory.data_points.length < 2) {
    return null;
  }

  return (
    <PriceHistoryChart
      data={priceHistory.data_points}
      cpvCode={cpvCode}
      trend={priceHistory.trend as "increasing" | "decreasing" | "stable"}
      trendPct={priceHistory.trend_pct}
      showTrend={true}
    />
  );
}
```

## Props

### PriceHistoryChartProps

| Prop | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `data` | `PriceDataPoint[]` | Yes | - | Array of price data points |
| `cpvCode` | `string` | Yes | - | CPV code for the tender category |
| `title` | `string` | No | `"Историја на цени"` | Chart title |
| `showTrend` | `boolean` | No | `true` | Whether to show trend indicator |
| `trend` | `"increasing" \| "decreasing" \| "stable"` | No | Auto-calculated | Trend direction |
| `trendPct` | `number` | No | Auto-calculated | Trend percentage change |

### PriceDataPoint Interface

```typescript
interface PriceDataPoint {
  period: string;              // Format: "YYYY-MM"
  tender_count: number;        // Number of tenders in this period
  avg_estimated_mkd: number;   // Average estimated value in MKD
  avg_awarded_mkd: number;     // Average awarded/winning value in MKD
  avg_discount_pct: number;    // Average discount percentage
  avg_bidders: number;         // Average number of bidders per tender
}
```

## API Integration

### getPriceHistory Method

```typescript
import { api } from "@/lib/api";

// Get price history for a CPV code
const result = await api.getPriceHistory(
  "33100000",  // CPV code
  12,          // months (optional)
  {
    period: "1y",           // "30d" | "90d" | "1y" | "all"
    category: "Medical",    // optional filter
    entity: "Hospital"      // optional filter
  }
);

// Result format:
{
  cpv_code: "33100000",
  data_points: PriceDataPoint[],
  trend: "increasing",
  trend_pct: 5.2,
  total_tenders: 96
}
```

## Styling

The component uses your theme's color variables:

- **Primary Line:** `hsl(var(--primary))` - Estimated values
- **Success Line:** `#22c55e` (green) - Actual values
- **Savings Fill:** Green gradient with opacity
- **Grid Lines:** `stroke-muted` with dashes
- **Card Background:** `bg-background`
- **Text:** Standard text colors

### Customizing Colors

To customize colors, override in your component:

```tsx
<PriceHistoryChart
  data={data}
  cpvCode="33100000"
  // Colors are set in the component's Line components
  // Modify the component directly to change colors
/>
```

## Features in Detail

### 1. Automatic Trend Calculation

If trend is not provided, the component automatically calculates it:

- **Increasing:** > +5% change from first to last data point
- **Decreasing:** < -5% change from first to last data point
- **Stable:** Between -5% and +5% change

### 2. Currency Formatting

The component includes smart formatting:

- Values >= 1M: `"4.5M МКД"`
- Values >= 1K: `"450K МКД"`
- Values < 1K: `"500 МКД"`

In tooltips, full values are shown with thousands separators:
- `"4,500,000 МКД"`

### 3. Data Validation

The component automatically handles:

- **Insufficient data:** Hides if less than 2 data points
- **Missing values:** Handles null/undefined gracefully
- **Zero values:** Displays without errors

### 4. Responsive Behavior

- **Desktop:** Full width, 350px height
- **Tablet:** Adapts smoothly, maintains readability
- **Mobile:** Stacks elements vertically if needed

## Performance

### Optimization Techniques

1. **Memoization:** Trend calculations are memoized with `useMemo`
2. **Conditional Rendering:** Only renders when data is valid
3. **Lazy Loading:** Only loads when CPV code exists
4. **Efficient Updates:** Minimal re-renders

### Best Practices

```tsx
// ✅ Good: Memoize data transformations
const chartData = useMemo(() =>
  rawData.map(transform),
  [rawData]
);

// ✅ Good: Conditionally render
if (data.length < 2) return null;

// ❌ Bad: Don't transform data on every render
const chartData = rawData.map(transform);
```

## Troubleshooting

### Chart doesn't appear

1. **Check data length:** Minimum 2 data points required
2. **Verify CPV code:** Component requires valid CPV code
3. **Check console:** Look for errors in browser console
4. **Validate data format:** Ensure data matches `PriceDataPoint[]` interface

### Tooltip not showing

1. **Recharts dependency:** Ensure recharts@2.15.4 is installed
2. **Data keys:** Verify `avg_estimated_mkd` and `avg_awarded_mkd` exist
3. **Browser support:** Requires modern browser with SVG support

### Styling issues

1. **CSS variables:** Ensure your theme provides all necessary CSS variables
2. **Card components:** Verify shadcn/ui Card components are installed
3. **Responsive classes:** Check Tailwind CSS is configured correctly

### Performance issues

1. **Large datasets:** Consider pagination for > 100 data points
2. **Unnecessary renders:** Wrap in `React.memo()` if needed
3. **Heavy calculations:** Move to Web Worker for very large datasets

## Examples

### Example 1: Medical Equipment Price Trends

```tsx
<PriceHistoryChart
  data={[
    {
      period: "2024-01",
      tender_count: 12,
      avg_estimated_mkd: 8500000,
      avg_awarded_mkd: 7900000,
      avg_discount_pct: 7.1,
      avg_bidders: 5.3,
    },
    // ... more periods
  ]}
  cpvCode="33100000"
  title="Медицинска опрема - Историја на цени"
/>
```

### Example 2: Construction Materials

```tsx
<PriceHistoryChart
  data={constructionData}
  cpvCode="45000000"
  title="Градежни материјали - Пазарни трендови"
  showTrend={true}
/>
```

### Example 3: IT Services

```tsx
<PriceHistoryChart
  data={itServicesData}
  cpvCode="72000000"
  title="IT Услуги - Историски преглед"
  showTrend={true}
  trend="decreasing"
  trendPct={12.5}
/>
```

## Testing

### Unit Tests

```tsx
import { render, screen } from "@testing-library/react";
import { PriceHistoryChart } from "./PriceHistoryChart";

describe("PriceHistoryChart", () => {
  const mockData = [
    {
      period: "2024-01",
      tender_count: 10,
      avg_estimated_mkd: 5000000,
      avg_awarded_mkd: 4500000,
      avg_discount_pct: 10,
      avg_bidders: 4,
    },
    {
      period: "2024-02",
      tender_count: 8,
      avg_estimated_mkd: 5200000,
      avg_awarded_mkd: 4700000,
      avg_discount_pct: 9.6,
      avg_bidders: 4.2,
    },
  ];

  it("renders chart with data", () => {
    render(
      <PriceHistoryChart
        data={mockData}
        cpvCode="33100000"
      />
    );

    expect(screen.getByText(/Историја на цени/)).toBeInTheDocument();
  });

  it("hides with insufficient data", () => {
    const { container } = render(
      <PriceHistoryChart
        data={[mockData[0]]}
        cpvCode="33100000"
      />
    );

    expect(container.firstChild).toBeNull();
  });

  it("calculates trend correctly", () => {
    render(
      <PriceHistoryChart
        data={mockData}
        cpvCode="33100000"
        showTrend={true}
      />
    );

    // Should show "Растечки" (increasing) trend
    expect(screen.getByText(/Растечки/)).toBeInTheDocument();
  });
});
```

## Changelog

### Version 1.0.0 (2025-12-02)
- Initial release
- Complete feature set
- Production ready

## Related Components

- **TenderCard**: Shows individual tender details
- **BidRecommendation**: Provides bidding strategy recommendations
- **PriceHistoryChart** (charts/): Tender-specific price history

## Support

For issues or questions:
1. Check this documentation
2. Review the component source code
3. Check the audit report: `PHASE_4.3_AUDIT_REPORT.md`
4. Look at the integration example in `/app/tenders/[id]/page.tsx`

## License

Part of the Nabavkidata platform. Internal use only.
