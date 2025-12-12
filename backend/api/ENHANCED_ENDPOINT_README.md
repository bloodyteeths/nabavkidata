# Enhanced Tender Endpoint Documentation

## Overview

The enhanced tender endpoint provides a comprehensive view of tender data, including bidders, price analysis, data completeness scores, and documents - all in a single API call.

## Endpoints

### 1. By Number/Year Format
```
GET /api/tenders/{number}/{year}/enhanced
```

**Example:**
```bash
curl http://localhost:8000/api/tenders/19816/2025/enhanced
```

### 2. By Any Tender ID Format
```
GET /api/tenders/by-id/{tender_id:path}/enhanced
```

**Example:**
```bash
# For IDs with slashes, URL encode them
curl http://localhost:8000/api/tenders/by-id/01069%2F2025%2FK1/enhanced
```

## Response Structure

```json
{
  // === STANDARD TENDER FIELDS ===
  "tender_id": "19816/2025",
  "title": "Набавка на медицинска опрема",
  "description": "...",
  "category": "Medical Equipment",
  "procuring_entity": "Клинички центар Скопје",
  "opening_date": "2025-11-15",
  "closing_date": "2025-12-15",
  "publication_date": "2025-11-01",
  "estimated_value_mkd": 5000000.00,
  "estimated_value_eur": 81000.00,
  "actual_value_mkd": 4200000.00,
  "actual_value_eur": 68000.00,
  "cpv_code": "33100000",
  "status": "awarded",
  "winner": "МедТех ДОО",
  "source_url": "https://e-nabavki.gov.mk/...",
  "language": "mk",
  "source_category": "awarded",

  // Extended fields
  "procedure_type": "Отворена постапка",
  "contract_signing_date": "2025-12-20",
  "contract_duration": "12 months",
  "contracting_entity_category": "Централна влада",
  "procurement_holder": "John Doe",
  "bureau_delivery_date": "2025-11-05",
  "contact_person": "Jane Smith",
  "contact_email": "jane@example.mk",
  "contact_phone": "+389 2 123 4567",
  "num_bidders": 8,
  "security_deposit_mkd": 100000.00,
  "performance_guarantee_mkd": 200000.00,
  "payment_terms": "30 days",
  "evaluation_method": "Најниска цена",
  "award_criteria": { "criteria": "price" },
  "has_lots": false,
  "num_lots": null,
  "amendment_count": 2,
  "last_amendment_date": "2025-11-20",
  "scraped_at": "2025-11-01T10:30:00",
  "created_at": "2025-11-01T10:30:00",
  "updated_at": "2025-12-01T15:45:00",

  // === ENHANCED FIELDS ===

  // Bidders array (from tender_bidders table or raw_data_json fallback)
  "bidders": [
    {
      "bidder_id": "uuid-here",
      "company_name": "МедТех ДОО",
      "tax_id": "1234567890",
      "bid_amount_mkd": 4200000.00,
      "bid_amount_eur": 68000.00,
      "rank": 1,
      "is_winner": true,
      "disqualified": false,
      "disqualification_reason": null
    },
    {
      "bidder_id": "uuid-here",
      "company_name": "ТехКорп ДООЕЛ",
      "tax_id": "0987654321",
      "bid_amount_mkd": 4350000.00,
      "bid_amount_eur": 70500.00,
      "rank": 2,
      "is_winner": false,
      "disqualified": false,
      "disqualification_reason": null
    }
  ],

  // Price analysis object
  "price_analysis": {
    "estimated_value": 5000000.00,
    "winning_bid": 4200000.00,
    "lowest_bid": 4200000.00,
    "highest_bid": 5500000.00,
    "num_bidders": 8
  },

  // Data completeness score (0-1)
  "data_completeness": 0.85,

  // Documents array
  "documents": [
    {
      "doc_id": "uuid-here",
      "doc_type": "specifications",
      "file_name": "Technical_Specifications.pdf",
      "file_url": "https://e-nabavki.gov.mk/documents/...",
      "file_path": "/path/to/file.pdf",
      "extraction_status": "completed",
      "file_size_bytes": 1024000,
      "page_count": 25,
      "mime_type": "application/pdf",
      "uploaded_at": "2025-11-01T10:30:00"
    }
  ]
}
```

## Data Completeness Calculation

The `data_completeness` score is calculated based on the presence of key fields, weighted by importance:

| Field | Weight | Description |
|-------|--------|-------------|
| `title` | 0.1 | Tender title (required) |
| `description` | 0.15 | Tender description |
| `estimated_value_mkd` | 0.1 | Estimated budget |
| `actual_value_mkd` | 0.1 | Awarded value |
| `winner` | 0.1 | Winner company name |
| `procuring_entity` | 0.1 | Procuring institution |
| `has_bidders` | 0.2 | At least one bidder exists |
| `has_documents` | 0.15 | At least one document exists |

**Total Weight:** 1.0

**Formula:**
```
data_completeness = (sum of weights for present fields) / (total weight)
```

## Bidder Data Sources

The endpoint intelligently retrieves bidder data from multiple sources:

1. **Primary source:** `tender_bidders` table
   - Structured, normalized data
   - Includes ranking, disqualification info
   - Best for analysis

2. **Fallback source:** `tenders.raw_data_json.bidders_data`
   - Used when `tender_bidders` table is empty
   - Contains original scraped data
   - May have less structured format

## Implementation Details

**File Location:** `/Users/tamsar/Downloads/nabavkidata/backend/api/tenders.py`

**Functions:**
- `get_enhanced_tender_by_id()` - Main implementation (lines 1630-1814)
- `get_enhanced_tender()` - Wrapper for number/year format (lines 1212-1230)

**Database Queries:**
1. Tender lookup
2. Bidders from `tender_bidders` table
3. Documents from `documents` table

**Performance Considerations:**
- 3 database queries per request
- Consider adding Redis caching for frequently accessed tenders
- Response size: ~5-50KB depending on number of bidders/documents

## Frontend Integration

**TypeScript Interface:**
```typescript
interface EnhancedTender {
  tender_id: string;
  title: string;
  // ... all standard fields ...
  bidders: Array<{
    bidder_id: string;
    company_name: string;
    bid_amount_mkd: number | null;
    rank: number | null;
    is_winner: boolean;
  }>;
  price_analysis: {
    estimated_value: number | null;
    winning_bid: number | null;
    lowest_bid: number | null;
    highest_bid: number | null;
    num_bidders: number;
  };
  data_completeness: number;
  documents: Array<{
    doc_id: string;
    file_name: string;
    file_url: string;
    extraction_status: string;
  }>;
}
```

**Usage Example:**
```typescript
import { getEnhancedTender } from '@/lib/api';

const tender = await getEnhancedTender('19816/2025');
console.log(`Data completeness: ${tender.data_completeness * 100}%`);
console.log(`Number of bidders: ${tender.bidders.length}`);
console.log(`Winning bid: ${tender.price_analysis.winning_bid} MKD`);
```

## Use Cases

1. **Tender Detail Page**
   - Display all tender information in one call
   - Show bidder comparison table
   - Display data completeness indicator

2. **Price Analysis Dashboard**
   - Use `price_analysis` for charts
   - Compare estimated vs. winning bid
   - Analyze bid ranges

3. **Data Quality Monitoring**
   - Track `data_completeness` across tenders
   - Identify incomplete records
   - Prioritize data enhancement efforts

4. **Competitor Intelligence**
   - Analyze bidder participation patterns
   - Track winning companies
   - Study bidding strategies

## Error Handling

**404 Not Found:**
```json
{
  "detail": "Tender not found"
}
```

**Example:**
```bash
curl http://localhost:8000/api/tenders/99999/2099/enhanced
# Returns: {"detail": "Tender not found"}
```

## Future Enhancements

Potential additions to this endpoint:

1. **AI Summary Field**
   - Add `ai_summary` with Gemini-generated overview
   - Useful for quick understanding

2. **Similar Tenders**
   - Add `similar_tenders` array
   - Based on category, CPV code, or procuring entity

3. **Price Recommendations**
   - Add `recommended_bid_range`
   - Based on historical data analysis

4. **Real-time Calculations**
   - Add `days_until_closing`
   - Add `competition_level` metric

5. **Caching Layer**
   - Implement Redis caching
   - Cache invalidation on tender updates
   - 5-15 minute TTL for frequently accessed tenders

## Testing

**Manual Testing:**
```bash
# Start backend server
cd /Users/tamsar/Downloads/nabavkidata/backend
source venv/bin/activate
uvicorn main:app --reload

# Test endpoint
curl http://localhost:8000/api/tenders/19816/2025/enhanced | jq
```

**Expected Response:**
- Status: 200 OK
- Content-Type: application/json
- Body: Complete tender data with enhanced fields

## Support

For issues or questions:
- Check logs in `/Users/tamsar/Downloads/nabavkidata/log.txt`
- Review database schema in `/Users/tamsar/Downloads/nabavkidata/backend/models.py`
- Consult roadmap: `/Users/tamsar/Downloads/nabavkidata/docs/UI_REFACTOR_ROADMAP.md`
