# Item Bids Table & Extraction Logic

## Overview

The `item_bids` table is **CRITICAL** for answering granular procurement questions like:
- **"Who bid what price for surgical drapes?"**
- **"What did Company X offer for item Y?"**
- **"Which bidder had the lowest price per item?"**

This system links **items** → **bidders** → **prices** at the most granular level, enabling detailed competitive analysis.

## Table Structure

### item_bids

Core table linking bidders to specific items with their offered prices.

```sql
CREATE TABLE item_bids (
    bid_id UUID PRIMARY KEY,
    tender_id VARCHAR(100) REFERENCES tenders(tender_id),
    lot_id UUID REFERENCES tender_lots(lot_id),
    item_id INTEGER REFERENCES product_items(id),
    bidder_id UUID REFERENCES tender_bidders(bidder_id),

    -- Bidder info (denormalized)
    company_name VARCHAR(500),
    company_tax_id VARCHAR(100),

    -- Bid details
    quantity_offered NUMERIC(15,4),
    unit_price_mkd NUMERIC(15,2),
    total_price_mkd NUMERIC(15,2),
    unit_price_eur NUMERIC(15,2),

    -- Additional attributes
    delivery_days INTEGER,
    warranty_months INTEGER,
    brand_model VARCHAR(500),
    country_of_origin VARCHAR(100),

    -- Evaluation
    is_compliant BOOLEAN DEFAULT TRUE,
    is_winner BOOLEAN DEFAULT FALSE,
    rank INTEGER,
    evaluation_score NUMERIC(5,2),
    disqualification_reason TEXT,

    -- Extraction metadata
    extraction_source VARCHAR(50),
    extraction_confidence FLOAT,
    source_document_id UUID,
    source_table_id UUID,
    source_page_number INTEGER,
    raw_data JSONB,

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(item_id, bidder_id)
);
```

### Key Indexes

```sql
-- Core lookups
CREATE INDEX idx_item_bids_tender ON item_bids(tender_id);
CREATE INDEX idx_item_bids_item ON item_bids(item_id);
CREATE INDEX idx_item_bids_bidder ON item_bids(bidder_id);
CREATE INDEX idx_item_bids_company ON item_bids(company_name);
CREATE INDEX idx_item_bids_price ON item_bids(unit_price_mkd);

-- Partial index for winners (fast winner queries)
CREATE INDEX idx_item_bids_winner ON item_bids(is_winner) WHERE is_winner = TRUE;

-- GIN index for JSONB queries
CREATE INDEX idx_item_bids_raw_data_gin ON item_bids USING gin(raw_data);
```

## Views for Common Queries

### 1. v_item_bids_full

Complete view joining items, bids, tenders, and bidders.

```sql
SELECT * FROM v_item_bids_full
WHERE item_name ILIKE '%surgical drapes%';
```

### 2. v_item_bid_comparison

Aggregate view showing all bids per item with statistics.

```sql
SELECT
    item_name,
    total_bids,
    min_price,
    max_price,
    avg_price,
    winner_name,
    winner_price,
    lowest_bidder,
    all_bids  -- JSON array of all bids
FROM v_item_bid_comparison
WHERE tender_id = '12345/2025';
```

### 3. v_company_item_performance

Company performance metrics by item category.

```sql
SELECT
    company_name,
    category,
    items_bid_on,
    items_won,
    win_rate_percent,
    avg_unit_price,
    total_value_won
FROM v_company_item_performance
WHERE company_name ILIKE '%Medimpex%';
```

## Extraction Logic

### Data Sources

Item bids can be extracted from:

1. **Bid Evaluation Documents** (comparison tables)
   - Shows all bidders side-by-side with prices per item
   - Most reliable source

2. **Individual Bid Submissions**
   - Single bidder's offer document
   - Contains items + prices from one company

3. **Award Decision Documents**
   - Final prices and winning bids
   - May only show winners

4. **ePazar Data** (e-auction systems)
   - Real-time bid data from electronic auctions
   - Already structured in epazar_offer_items

### Extraction Workflow

```python
from item_bid_extractor import ItemBidExtractor, extract_item_bids_from_tender

# Initialize extractor with DB pool
extractor = ItemBidExtractor(db_pool)

# Extract from a specific table
bids = await extractor.extract_from_table(
    table_id='uuid-of-extracted-table',
    tender_id='12345/2025',
    table_data=normalized_table_data,
    document_id='uuid-of-source-document'
)

# Save extracted bids
saved_count = await extractor.save_item_bids(bids)

# Or extract from all tables for a tender
total_bids = await extract_item_bids_from_tender(
    db_pool=db_pool,
    tender_id='12345/2025'
)
```

### Table Detection Logic

The extractor automatically detects table types:

```python
def _detect_table_type(table_data: Dict) -> str:
    """
    Heuristics:
    - Bid comparison: Multiple company columns with prices
    - Single bid: One company, multiple items with prices
    - Award decision: Winner column, contract amounts
    """
```

### Column Mapping

Patterns used to identify columns:

**Item Names:**
- Macedonian: `артикул`, `производ`, `ставка`, `опис`, `назив`
- English: `item`, `product`, `description`, `name`

**Companies:**
- Macedonian: `понудувач`, `компанија`, `фирма`
- English: `bidder`, `company`, `supplier`

**Prices:**
- Macedonian: `цена.*единиц`, `единична.*цена`, `вкупна.*цена`
- English: `unit.*price`, `price.*unit`, `total.*price`, `amount`

## Usage Examples

### 1. Who Bid for an Item?

```python
async def who_bid_for_item(pool, item_search):
    async with pool.acquire() as conn:
        results = await conn.fetch("""
            SELECT
                item_name,
                company_name,
                unit_price_mkd,
                quantity_offered,
                is_winner,
                rank
            FROM v_item_bids_full
            WHERE item_name ILIKE $1
            ORDER BY item_name, unit_price_mkd ASC
        """, f'%{item_search}%')

    for row in results:
        print(f"{row['company_name']}: {row['unit_price_mkd']} MKD/unit")
```

### 2. What Did a Company Offer?

```python
async def what_company_offered(pool, company_name, tender_id):
    async with pool.acquire() as conn:
        results = await conn.fetch("""
            SELECT
                item_name,
                quantity_offered,
                unit_price_mkd,
                total_price_mkd,
                is_winner
            FROM v_item_bids_full
            WHERE company_name ILIKE $1 AND tender_id = $2
        """, f'%{company_name}%', tender_id)
```

### 3. Lowest Bidder Per Item

```python
async with pool.acquire() as conn:
    results = await conn.fetch("""
        SELECT
            item_name,
            lowest_bidder,
            min_price,
            winner_name,
            winner_price,
            ROUND(((winner_price - min_price) / min_price * 100)::numeric, 2)
                as price_diff_pct
        FROM v_item_bid_comparison
        WHERE tender_id = $1
    """, tender_id)
```

### 4. Find Non-Optimal Awards

Items where winner wasn't the lowest bidder:

```sql
SELECT
    item_name,
    winner_name,
    winner_price,
    lowest_bidder,
    min_price,
    (winner_price - min_price) as overpayment,
    ROUND(((winner_price - min_price) / min_price * 100), 2) as overpayment_pct
FROM v_item_bid_comparison
WHERE winner_price > min_price
ORDER BY overpayment DESC;
```

### 5. Price Outlier Detection

Find suspiciously high/low bids using z-scores:

```sql
SELECT
    ib.item_id,
    ib.company_name,
    ib.unit_price_mkd,
    comp.avg_price,
    comp.price_stddev,
    (ib.unit_price_mkd - comp.avg_price) / NULLIF(comp.price_stddev, 0) as z_score
FROM item_bids ib
JOIN v_item_bid_comparison comp ON ib.item_id = comp.item_id
WHERE ABS((ib.unit_price_mkd - comp.avg_price) / NULLIF(comp.price_stddev, 0)) > 2
ORDER BY ABS(z_score) DESC;
```

## Integration with RAG

### Adding to rag_query.py

```python
async def search_item_bids(
    query: str,
    tender_id: Optional[str] = None,
    company_name: Optional[str] = None
):
    """
    Search item bids using natural language

    Examples:
    - "Who bid for surgical drapes?"
    - "What did Medimpex offer?"
    - "Show me all bids for tender 12345"
    """

    # Extract entities from query
    item_keywords = extract_items(query)
    company_keywords = extract_companies(query)

    # Build SQL query
    sql = """
        SELECT
            item_name,
            company_name,
            unit_price_mkd,
            quantity_offered,
            total_price_mkd,
            is_winner,
            rank,
            tender_title,
            publication_date
        FROM v_item_bids_full
        WHERE 1=1
    """

    params = []
    if item_keywords:
        sql += " AND item_name ILIKE $1"
        params.append(f'%{item_keywords}%')

    if company_keywords:
        sql += f" AND company_name ILIKE ${len(params)+1}"
        params.append(f'%{company_keywords}%')

    if tender_id:
        sql += f" AND tender_id = ${len(params)+1}"
        params.append(tender_id)

    sql += " ORDER BY unit_price_mkd ASC LIMIT 50"

    async with db_pool.acquire() as conn:
        results = await conn.fetch(sql, *params)

    return format_results(results)
```

### Sample RAG Responses

**Query:** "Who bid for surgical drapes in tender 12345?"

**Response:**
```
Found 5 bids for surgical drapes in tender 12345/2025:

1. Alkaloid AD - 145.50 MKD/unit (WINNER) ✓
2. Medimpex DOOEL - 150.00 MKD/unit (Rank 2)
3. Replek Farm - 152.00 MKD/unit (Rank 3)
4. Import Medical - 155.50 MKD/unit (Rank 4)
5. MediSupply Ltd - Disqualified (missing documentation)

The winning bid from Alkaloid AD was 3.0% lower than the second-lowest bid.
```

## Performance Considerations

### Optimization Tips

1. **Use Partial Indexes**
   - Winners index only includes winners (very fast)
   - Price index for range queries

2. **Denormalize Company Names**
   - Faster text search without joining tender_bidders

3. **JSONB for Flexibility**
   - Store raw extracted data for debugging
   - Use GIN index for fast JSONB queries

4. **Materialized Views** (Future)
   - For heavy analytics, consider materialized views
   - Refresh periodically (daily/hourly)

### Query Performance

```sql
-- FAST: Uses indexes
SELECT * FROM item_bids WHERE tender_id = '12345/2025';

-- FAST: Partial index
SELECT * FROM item_bids WHERE is_winner = TRUE;

-- SLOWER: Full text search (use with LIMIT)
SELECT * FROM v_item_bids_full WHERE item_name ILIKE '%drapes%' LIMIT 100;
```

## Data Quality

### Extraction Confidence

Track confidence scores for quality monitoring:

```sql
-- Low confidence extractions (review these)
SELECT
    tender_id,
    item_name,
    company_name,
    extraction_confidence,
    extraction_source
FROM item_bids
WHERE extraction_confidence < 0.7
ORDER BY extraction_confidence ASC;
```

### Missing Data Checks

```sql
-- Bids without prices
SELECT COUNT(*) FROM item_bids WHERE unit_price_mkd IS NULL;

-- Items without bids
SELECT
    pi.id,
    pi.name,
    pi.tender_id
FROM product_items pi
LEFT JOIN item_bids ib ON pi.id = ib.item_id
WHERE ib.bid_id IS NULL;
```

## Future Enhancements

1. **Brand/Model Extraction**
   - Extract brand names from bid documents
   - Enable brand-based searches

2. **Technical Specifications Matching**
   - Link to product specifications
   - Compare offered specs vs. required specs

3. **Price History Tracking**
   - Track price changes over time
   - Detect price trends by item category

4. **Automated Winner Detection**
   - Use evaluation criteria to predict winners
   - Highlight potential errors in award decisions

## Troubleshooting

### Common Issues

**Issue:** Duplicate bids for same item + bidder
**Solution:** Unique constraint on (item_id, bidder_id) prevents this. Use ON CONFLICT for upserts.

**Issue:** Missing bidder records
**Solution:** Extractor creates bidders automatically via `_get_or_create_bidders()`

**Issue:** Incorrect price parsing
**Solution:** Check `_parse_price()` method, may need to handle new formats

**Issue:** Low extraction confidence
**Solution:** Review source table structure, may need new column patterns

## Testing

Run the usage examples:

```bash
cd /Users/tamsar/Downloads/nabavkidata/ai
python item_bid_usage_examples.py
```

This will:
1. Insert sample bids
2. Run all query examples
3. Display results and performance metrics

## Summary

The `item_bids` table provides the missing link between bidders and specific items, enabling:

✅ **Granular price analysis** per item
✅ **Company performance tracking** at item level
✅ **Award decision validation** (lowest bidder checks)
✅ **Fraud detection** (price outliers, collusion patterns)
✅ **Natural language queries** via RAG

This is the **foundation for answering the most valuable procurement questions** in the system.
