# Item Bids - Quick Reference

## 🎯 Purpose

Answer granular questions:
- **"Who bid what price for surgical drapes?"**
- **"What did Company X offer for item Y?"**
- **"Which bidder had the lowest price per item?"**

## 📊 Database Objects

### Table
- `item_bids` - Main table (28 columns, 11 indexes, 4 foreign keys)

### Views
- `v_item_bids_full` - Complete bid data with context
- `v_item_bid_comparison` - Aggregate stats per item
- `v_company_item_performance` - Company performance by category

## 🔍 Common Queries

### Who bid for an item?
```sql
SELECT item_name, company_name, unit_price_mkd, is_winner, rank
FROM v_item_bids_full
WHERE item_name ILIKE '%surgical drapes%'
ORDER BY unit_price_mkd;
```

### What did a company offer?
```sql
SELECT item_name, unit_price_mkd, total_price_mkd, is_winner
FROM v_item_bids_full
WHERE company_name ILIKE '%Medimpex%'
AND tender_id = '12345/2025';
```

### Lowest bidder per item?
```sql
SELECT item_name, lowest_bidder, min_price, winner_name, winner_price
FROM v_item_bid_comparison
WHERE tender_id = '12345/2025';
```

### Non-optimal awards?
```sql
SELECT item_name, winner_name, winner_price, lowest_bidder, min_price
FROM v_item_bid_comparison
WHERE winner_price > min_price
ORDER BY (winner_price - min_price) DESC;
```

## 🐍 Python Usage

### Extract bids from tender
```python
from item_bid_extractor import extract_item_bids_from_tender

total_bids = await extract_item_bids_from_tender(
    db_pool=db_pool,
    tender_id='12345/2025'
)
```

### Query with RAG
```python
from item_bid_rag_integration import ItemBidRAGSearcher

searcher = ItemBidRAGSearcher(db_pool)
result = await searcher.search_item_bids(
    "Who bid for surgical drapes?"
)
print(result['answer'])
```

### Insert manual bids
```python
await conn.execute("""
    INSERT INTO item_bids (
        tender_id, item_id, bidder_id, company_name,
        unit_price_mkd, total_price_mkd
    ) VALUES ($1, $2, $3, $4, $5, $6)
    ON CONFLICT (item_id, bidder_id)
    DO UPDATE SET unit_price_mkd = EXCLUDED.unit_price_mkd
""", tender_id, item_id, bidder_id, company_name, price, total)
```

## 📂 Files

All in `/Users/tamsar/Downloads/nabavkidata/`:

- **Migration:** `backend/alembic/versions/20251129_add_item_bids.py`
- **Extractor:** `ai/item_bid_extractor.py`
- **RAG Integration:** `ai/item_bid_rag_integration.py`
- **Examples:** `ai/item_bid_usage_examples.py`
- **Docs:** `ai/ITEM_BIDS_README.md`

## ⚡ Quick Test

```bash
# Run examples
cd /Users/tamsar/Downloads/nabavkidata/ai
python item_bid_usage_examples.py

# Check table
psql ... -c "SELECT COUNT(*) FROM item_bids;"

# Check views
psql ... -c "SELECT * FROM v_item_bids_full LIMIT 5;"
```

## 🔗 Relationships

```
tenders (tender_id)
    ↓
item_bids (tender_id)
    ↓
├── product_items (item_id)
├── tender_bidders (bidder_id)
└── tender_lots (lot_id)
```

## 📈 Key Metrics

Query this to track data:
```sql
SELECT
    COUNT(*) as total_bids,
    COUNT(DISTINCT tender_id) as tenders_with_bids,
    COUNT(DISTINCT item_id) as items_with_bids,
    COUNT(DISTINCT bidder_id) as unique_bidders,
    AVG(extraction_confidence) as avg_confidence
FROM item_bids;
```

## 🚀 Next Steps

1. **Extract from documents** → `item_bid_extractor.py`
2. **Query with SQL** → Use views
3. **Query with RAG** → `item_bid_rag_integration.py`
4. **Add to API** → Create endpoints
5. **Show in UI** → Bid comparison tables

## 💡 Pro Tips

- Use `tender_id` filter for best performance
- Views are pre-optimized for common queries
- Partial index on winners is very fast
- Denormalized company_name for speed
- JSONB raw_data for debugging extraction
