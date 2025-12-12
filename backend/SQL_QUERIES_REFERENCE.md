# Bidding Pattern Analysis - SQL Queries Reference

This document contains all SQL queries used in the bidding pattern analysis endpoint for quick reference and debugging.

---

## 1. Basic Statistics Query

**Purpose:** Get total bids, wins, and win rate for a company

**Parameters:**
- `:company_name` - Company name (case-insensitive)
- Hardcoded: `analysis_months` - Number of months to analyze

```sql
WITH date_threshold AS (
    SELECT NOW() - INTERVAL '24 months' as cutoff
)
SELECT
    COUNT(DISTINCT tb.bidder_id) as total_bids,
    COUNT(DISTINCT tb.bidder_id) FILTER (WHERE tb.is_winner = TRUE) as total_wins,
    CASE
        WHEN COUNT(DISTINCT tb.bidder_id) > 0
        THEN (COUNT(DISTINCT tb.bidder_id) FILTER (WHERE tb.is_winner = TRUE)::float /
              COUNT(DISTINCT tb.bidder_id) * 100)
        ELSE 0
    END as win_rate
FROM tender_bidders tb
JOIN tenders t ON tb.tender_id = t.tender_id
CROSS JOIN date_threshold dt
WHERE tb.company_name ILIKE :company_name
    AND t.closing_date >= dt.cutoff
```

**Returns:**
- `total_bids` (int)
- `total_wins` (int)
- `win_rate` (float, percentage)

---

## 2. Pricing Pattern Analysis Query

**Purpose:** Calculate discount statistics and pricing consistency

**Parameters:**
- `:company_name` - Company name
- Hardcoded: `analysis_months`

```sql
WITH date_threshold AS (
    SELECT NOW() - INTERVAL '24 months' as cutoff
),
bid_analysis AS (
    SELECT
        tb.bid_amount_mkd,
        t.estimated_value_mkd,
        CASE
            WHEN t.estimated_value_mkd > 0
            THEN ((t.estimated_value_mkd - tb.bid_amount_mkd) / t.estimated_value_mkd * 100)
            ELSE NULL
        END as discount_pct
    FROM tender_bidders tb
    JOIN tenders t ON tb.tender_id = t.tender_id
    CROSS JOIN date_threshold dt
    WHERE tb.company_name ILIKE :company_name
        AND t.closing_date >= dt.cutoff
        AND tb.bid_amount_mkd IS NOT NULL
        AND tb.bid_amount_mkd > 0
)
SELECT
    AVG(discount_pct) as avg_discount,
    MIN(discount_pct) as min_discount,
    MAX(discount_pct) as max_discount,
    STDDEV(discount_pct) as discount_stddev,
    AVG(bid_amount_mkd) as avg_bid,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY bid_amount_mkd) as median_bid
FROM bid_analysis
WHERE discount_pct IS NOT NULL
```

**Returns:**
- `avg_discount` (float, %)
- `min_discount` (float, %)
- `max_discount` (float, %)
- `discount_stddev` (float)
- `avg_bid` (numeric, MKD)
- `median_bid` (numeric, MKD)

**Post-processing:**
```python
# Price consistency calculation
cv = abs(discount_stddev / avg_discount) if avg_discount != 0 else 0
price_consistency = max(0, min(1, 1 - cv / 2))
```

---

## 3. Category Preferences Query

**Purpose:** Get top 5 CPV codes by bid frequency

**Parameters:**
- `:company_name` - Company name
- Hardcoded: `analysis_months`

```sql
WITH date_threshold AS (
    SELECT NOW() - INTERVAL '24 months' as cutoff
)
SELECT
    t.cpv_code,
    t.category as name,
    COUNT(DISTINCT tb.bidder_id) as bid_count,
    COUNT(DISTINCT tb.bidder_id) FILTER (WHERE tb.is_winner = TRUE) as win_count,
    CASE
        WHEN COUNT(DISTINCT tb.bidder_id) > 0
        THEN (COUNT(DISTINCT tb.bidder_id) FILTER (WHERE tb.is_winner = TRUE)::float /
              COUNT(DISTINCT tb.bidder_id) * 100)
        ELSE 0
    END as win_rate
FROM tender_bidders tb
JOIN tenders t ON tb.tender_id = t.tender_id
CROSS JOIN date_threshold dt
WHERE tb.company_name ILIKE :company_name
    AND t.closing_date >= dt.cutoff
    AND t.cpv_code IS NOT NULL
GROUP BY t.cpv_code, t.category
ORDER BY bid_count DESC
LIMIT 5
```

**Returns:**
- `cpv_code` (string)
- `name` (string)
- `bid_count` (int)
- `win_count` (int)
- `win_rate` (float, %)

---

## 4. Size Preferences Query

**Purpose:** Categorize tenders by size and calculate win rates

**Parameters:**
- `:company_name` - Company name
- Hardcoded: `analysis_months`

**Size Categories:**
- Small: 0 - 500,000 MKD
- Medium: 500,000 - 2,000,000 MKD
- Large: 2,000,000+ MKD

```sql
WITH date_threshold AS (
    SELECT NOW() - INTERVAL '24 months' as cutoff
),
size_categorized AS (
    SELECT
        tb.is_winner,
        tb.bid_amount_mkd,
        t.estimated_value_mkd,
        CASE
            WHEN t.estimated_value_mkd > 0 AND tb.bid_amount_mkd > 0
            THEN ((t.estimated_value_mkd - tb.bid_amount_mkd) / t.estimated_value_mkd * 100)
            ELSE NULL
        END as discount_pct,
        CASE
            WHEN t.estimated_value_mkd < 500000 THEN 'small'
            WHEN t.estimated_value_mkd < 2000000 THEN 'medium'
            ELSE 'large'
        END as size_category
    FROM tender_bidders tb
    JOIN tenders t ON tb.tender_id = t.tender_id
    CROSS JOIN date_threshold dt
    WHERE tb.company_name ILIKE :company_name
        AND t.closing_date >= dt.cutoff
        AND t.estimated_value_mkd IS NOT NULL
        AND t.estimated_value_mkd > 0
)
SELECT
    size_category,
    COUNT(*) as total_bids,
    COUNT(*) FILTER (WHERE is_winner = TRUE) as wins,
    CASE
        WHEN COUNT(*) > 0
        THEN (COUNT(*) FILTER (WHERE is_winner = TRUE)::float / COUNT(*) * 100)
        ELSE 0
    END as win_rate,
    AVG(discount_pct) FILTER (WHERE discount_pct IS NOT NULL) as avg_discount
FROM size_categorized
GROUP BY size_category
ORDER BY
    CASE size_category
        WHEN 'small' THEN 1
        WHEN 'medium' THEN 2
        WHEN 'large' THEN 3
    END
```

**Returns:**
- `size_category` (string: 'small', 'medium', 'large')
- `total_bids` (int)
- `wins` (int)
- `win_rate` (float, %)
- `avg_discount` (float, %)

---

## 5. Seasonal Activity Query

**Purpose:** Aggregate bidding activity by month

**Parameters:**
- `:company_name` - Company name
- Hardcoded: `analysis_months`

```sql
WITH date_threshold AS (
    SELECT NOW() - INTERVAL '24 months' as cutoff
)
SELECT
    TO_CHAR(t.closing_date, 'Month') as month,
    EXTRACT(MONTH FROM t.closing_date) as month_num,
    COUNT(DISTINCT tb.bidder_id) as bids,
    COUNT(DISTINCT tb.bidder_id) FILTER (WHERE tb.is_winner = TRUE) as wins
FROM tender_bidders tb
JOIN tenders t ON tb.tender_id = t.tender_id
CROSS JOIN date_threshold dt
WHERE tb.company_name ILIKE :company_name
    AND t.closing_date >= dt.cutoff
GROUP BY TO_CHAR(t.closing_date, 'Month'), EXTRACT(MONTH FROM t.closing_date)
ORDER BY month_num
```

**Returns:**
- `month` (string: 'January', 'February', etc.)
- `month_num` (int: 1-12)
- `bids` (int)
- `wins` (int)

---

## 6. Top Competitors Query

**Purpose:** Find companies frequently competing in same tenders

**Parameters:**
- `:company_name` - Company name (used 3 times in query)
- Hardcoded: `analysis_months`

```sql
WITH date_threshold AS (
    SELECT NOW() - INTERVAL '24 months' as cutoff
),
company_tenders AS (
    -- Get all tenders where target company participated
    SELECT DISTINCT tb.tender_id
    FROM tender_bidders tb
    JOIN tenders t ON tb.tender_id = t.tender_id
    CROSS JOIN date_threshold dt
    WHERE tb.company_name ILIKE :company_name
        AND t.closing_date >= dt.cutoff
),
competing_companies AS (
    -- Get other bidders in same tenders
    SELECT
        tb2.company_name,
        tb2.is_winner as competitor_won,
        tb1.is_winner as target_won
    FROM company_tenders ct
    JOIN tender_bidders tb1 ON ct.tender_id = tb1.tender_id
    JOIN tender_bidders tb2 ON ct.tender_id = tb2.tender_id
    WHERE tb1.company_name ILIKE :company_name
        AND tb2.company_name NOT ILIKE :company_name
        AND tb2.company_name IS NOT NULL
)
SELECT
    company_name,
    COUNT(*) as overlap_count,
    COUNT(*) FILTER (WHERE target_won = TRUE AND competitor_won = FALSE) as our_wins,
    COUNT(*) FILTER (WHERE target_won = FALSE AND competitor_won = TRUE) as their_wins
FROM competing_companies
GROUP BY company_name
ORDER BY overlap_count DESC
LIMIT 10
```

**Returns:**
- `company_name` (string)
- `overlap_count` (int) - Times competed in same tender
- `our_wins` (int) - Times target company won
- `their_wins` (int) - Times competitor won

**Logic:**
- Finds all tenders where target company bid
- Identifies all other bidders in those tenders
- Calculates head-to-head matchup results

---

## 7. Success Rate by Entity Type Query

**Purpose:** Analyze win rates across procuring entity categories

**Parameters:**
- `:company_name` - Company name
- Hardcoded: `analysis_months`

```sql
WITH date_threshold AS (
    SELECT NOW() - INTERVAL '24 months' as cutoff
)
SELECT
    t.contracting_entity_category,
    COUNT(*) as total_bids,
    COUNT(*) FILTER (WHERE tb.is_winner = TRUE) as wins,
    CASE
        WHEN COUNT(*) > 0
        THEN (COUNT(*) FILTER (WHERE tb.is_winner = TRUE)::float / COUNT(*) * 100)
        ELSE 0
    END as win_rate
FROM tender_bidders tb
JOIN tenders t ON tb.tender_id = t.tender_id
CROSS JOIN date_threshold dt
WHERE tb.company_name ILIKE :company_name
    AND t.closing_date >= dt.cutoff
    AND t.contracting_entity_category IS NOT NULL
GROUP BY t.contracting_entity_category
HAVING COUNT(*) >= 3  -- Minimum 3 bids for relevance
ORDER BY win_rate DESC
LIMIT 5
```

**Returns:**
- `contracting_entity_category` (string)
- `total_bids` (int)
- `wins` (int)
- `win_rate` (float, %)

**Filter:** Minimum 3 bids per entity type to ensure statistical relevance

---

## Query Performance Notes

### Optimization Techniques Used

1. **CTEs (Common Table Expressions)**
   - `date_threshold` - Calculated once, used throughout
   - Multi-level CTEs for complex transformations

2. **Indexed Columns**
   - `company_name` - Indexed for fast filtering
   - `closing_date` - Indexed for date range queries
   - `is_winner` - Indexed for conditional counting
   - `cpv_code` - Indexed for category grouping

3. **FILTER Clauses**
   - More efficient than CASE WHEN for conditional aggregation
   - Allows single-pass aggregation

4. **DISTINCT on Primary Keys**
   - Uses `bidder_id` for accurate counting
   - Prevents double-counting in joins

5. **Limited Result Sets**
   - Category query: LIMIT 5
   - Competitors query: LIMIT 10
   - Entity types query: LIMIT 5

### Expected Performance

- **Small datasets (<100 bids):** <1 second
- **Medium datasets (100-500 bids):** 1-3 seconds
- **Large datasets (500+ bids):** 3-5 seconds

### Bottlenecks

1. **Competitors Query** - Most complex (3 CTEs, self-joins)
2. **Pricing Analysis** - Heavy calculations (STDDEV, PERCENTILE)
3. **Size Categorization** - CASE expressions in CTE

---

## Database Requirements

### Tables
- `tender_bidders` - Must have company_name, bid_amount_mkd, is_winner
- `tenders` - Must have closing_date, estimated_value_mkd, cpv_code, category

### Indexes (recommended)
```sql
CREATE INDEX idx_tender_bidders_company ON tender_bidders(company_name);
CREATE INDEX idx_tender_bidders_winner ON tender_bidders(is_winner);
CREATE INDEX idx_tenders_closing_date ON tenders(closing_date);
CREATE INDEX idx_tenders_cpv_code ON tenders(cpv_code);
CREATE INDEX idx_tenders_entity_category ON tenders(contracting_entity_category);
```

### Data Quality
- `closing_date` should be populated for all tenders
- `estimated_value_mkd` needed for pricing analysis
- `cpv_code` and `category` needed for category preferences
- `contracting_entity_category` needed for entity analysis

---

## Debugging Tips

### No Results

**Check:**
1. Company name spelling (case-insensitive but must match)
2. Date range (closing_date within analysis period)
3. Data exists in tender_bidders table

**SQL:**
```sql
-- Verify company exists
SELECT COUNT(*) FROM tender_bidders WHERE company_name ILIKE '%CompanyName%';

-- Check date range
SELECT MIN(closing_date), MAX(closing_date)
FROM tenders t
JOIN tender_bidders tb ON t.tender_id = tb.tender_id
WHERE tb.company_name ILIKE '%CompanyName%';
```

### NULL Values in Pricing Pattern

**Causes:**
- `estimated_value_mkd` is NULL or 0
- `bid_amount_mkd` is NULL or 0

**Fix:** Filter ensures only valid bids are included

### Missing Categories

**Causes:**
- `cpv_code` is NULL
- Not enough bids in time period

**Check:**
```sql
SELECT COUNT(*)
FROM tender_bidders tb
JOIN tenders t ON tb.tender_id = tb.tender_id
WHERE tb.company_name ILIKE '%CompanyName%'
  AND t.cpv_code IS NOT NULL;
```

---

## Testing Queries Individually

### Test Query 1 (Basic Stats)
```bash
psql -h HOST -U USER -d DATABASE -c "
WITH date_threshold AS (SELECT NOW() - INTERVAL '24 months' as cutoff)
SELECT COUNT(*) FROM tender_bidders tb
JOIN tenders t ON tb.tender_id = t.tender_id
WHERE tb.company_name ILIKE '%COMPANY%' AND t.closing_date >= (SELECT cutoff FROM date_threshold);
"
```

### Test Query 2 (Pricing)
```bash
psql -h HOST -U USER -d DATABASE -c "
SELECT AVG(
  (t.estimated_value_mkd - tb.bid_amount_mkd) / NULLIF(t.estimated_value_mkd, 0) * 100
) as avg_discount
FROM tender_bidders tb
JOIN tenders t ON tb.tender_id = t.tender_id
WHERE tb.company_name ILIKE '%COMPANY%'
  AND t.estimated_value_mkd > 0
  AND tb.bid_amount_mkd > 0;
"
```

---

## F-String Safety

All queries use f-strings for `analysis_months` only:
```python
query = text(f"""
    WITH date_threshold AS (
        SELECT NOW() - INTERVAL '{analysis_months} months' as cutoff
    )
    ...
""")
```

**Why this is safe:**
- `analysis_months` is validated by Pydantic (1-60 range)
- Not user-controlled string input
- Only integers from validated parameter

**User input uses parameterization:**
```python
await db.execute(query, {"company_name": company_name})
```

---

## Common Query Patterns

### Time-based filtering
```sql
WITH date_threshold AS (
    SELECT NOW() - INTERVAL '24 months' as cutoff
)
```

### Conditional counting
```sql
COUNT(DISTINCT tb.bidder_id) FILTER (WHERE tb.is_winner = TRUE)
```

### Win rate calculation
```sql
CASE
    WHEN COUNT(*) > 0
    THEN (COUNT(*) FILTER (WHERE is_winner = TRUE)::float / COUNT(*) * 100)
    ELSE 0
END as win_rate
```

### Discount calculation
```sql
CASE
    WHEN estimated_value > 0
    THEN ((estimated_value - bid_amount) / estimated_value * 100)
    ELSE NULL
END as discount_pct
```

---

**Last Updated:** December 2, 2025
**Version:** 1.0
**Queries:** 7 total
