# E-Pazar Price Intelligence Components

This directory contains components for displaying price intelligence and market insights for the e-Pazar platform.

## Components

### PriceIntelligenceCard.tsx
Displays recommended bid ranges and market price statistics for products.

**Features:**
- Recommended bid range (min-max)
- Market statistics (min/avg/max prices)
- Price trend indicator (up/down/stable)
- Competition level badge (low/medium/high)
- Sample size display

**Props:**
```typescript
interface PriceIntelligenceCardProps {
  data: PriceIntelligence;
  showProductName?: boolean; // Default: true
}
```

**Usage:**
```tsx
import { PriceIntelligenceCard } from '@/components/epazar/PriceIntelligenceCard';

<PriceIntelligenceCard
  data={priceIntelligence}
  showProductName={true}
/>
```

### SupplierRankings.tsx
Displays a sortable table of top suppliers with performance metrics.

**Features:**
- Sortable columns (name, win rate, wins, contract value)
- Win rate badge (high/medium/low)
- Top 3 trophy indicators
- Optional city column
- Links to supplier detail pages

**Props:**
```typescript
interface SupplierRankingsProps {
  suppliers: SupplierRanking[];
  title?: string;
  description?: string;
  showCity?: boolean; // Default: false
}
```

**Usage:**
```tsx
import { SupplierRankings } from '@/components/epazar/SupplierRankings';

<SupplierRankings
  suppliers={supplierRankings}
  title="Топ Добавувачи"
  description="Рангирање според успешност"
  showCity={true}
/>
```

## API Endpoints Required

The components expect the following API endpoints to be implemented in the backend:

### 1. Price Intelligence
```
GET /api/epazar/price-intelligence?product_name={name}
```

**Response:**
```json
{
  "product_name": "string",
  "recommended_bid_min_mkd": number,
  "recommended_bid_max_mkd": number,
  "market_min_mkd": number,
  "market_max_mkd": number,
  "market_avg_mkd": number,
  "trend": "up" | "down" | "stable",
  "trend_percentage": number,
  "competition_level": "low" | "medium" | "high",
  "sample_size": number
}
```

### 2. Supplier Rankings
```
GET /api/epazar/supplier-rankings?page={page}&page_size={size}
```

**Response:**
```json
{
  "total": number,
  "page": number,
  "page_size": number,
  "suppliers": [
    {
      "supplier_id": "string",
      "company_name": "string",
      "tax_id": "string",
      "total_wins": number,
      "total_offers": number,
      "win_rate": number,
      "total_contract_value_mkd": number,
      "avg_bid_amount_mkd": number,
      "city": "string"
    }
  ]
}
```

### 3. Buyer Statistics
```
GET /api/epazar/buyers?page={page}&page_size={size}
```

**Response:**
```json
{
  "total": number,
  "page": number,
  "page_size": number,
  "buyers": [
    {
      "buyer_id": "string",
      "buyer_name": "string",
      "total_tenders": number,
      "total_value_mkd": number,
      "avg_tender_value_mkd": number,
      "active_tenders": number,
      "completed_tenders": number,
      "top_categories": ["string"]
    }
  ]
}
```

### 4. Similar Tenders
```
GET /api/epazar/tenders/{tender_id}/similar?limit={limit}
```

**Response:**
```json
{
  "tender_id": "string",
  "total": number,
  "similar_tenders": [
    {
      "tender_id": "string",
      "title": "string",
      "contracting_authority": "string",
      "estimated_value_mkd": number,
      "similarity_score": number,
      "match_reason": "string",
      // ... other tender fields
    }
  ]
}
```

## Pages Updated

### 1. /app/epazar/page.tsx
Added new "Market Intelligence" tab with:
- Supplier rankings table
- Buyer statistics table
- Market insights

### 2. /app/epazar/[id]/page.tsx
Added sections:
- Price Intelligence card (for first item in tender)
- Similar Tenders list (with similarity scores)
- Competition level indicator in overview cards

## Backend Implementation Notes

The backend should implement the following logic:

1. **Price Intelligence**: Analyze historical data for similar products to calculate:
   - Min/max/avg prices across recent tenders
   - Recommended bid range (e.g., 5-10th percentile for competitive bids)
   - Price trends over time
   - Competition level based on number of bidders

2. **Supplier Rankings**: Aggregate supplier performance metrics:
   - Calculate win rate (wins / total offers)
   - Sum total contract values
   - Rank by configurable metric (win rate, total value, etc.)

3. **Similar Tenders**: Use similarity algorithms based on:
   - Item names/descriptions (text similarity)
   - CPV codes (exact match)
   - Contracting authority (same buyer patterns)
   - Price ranges (similar budget)

4. **Buyer Statistics**: Track buyer activity:
   - Count tenders by status
   - Sum estimated and awarded values
   - Identify top procurement categories
