# Item-Level RAG Query - Quick Reference

## Enhanced RAG System Summary

The RAG system now supports **item-level queries** for specific products, prices, and suppliers.

## What Changed?

### 1. System Prompt Enhancement
Added section 6 to handle item-level queries with specific formatting requirements.

### 2. New Detection Method
```python
def _is_item_level_query(question: str) -> bool:
    """Detect if query asks about specific items vs tenders"""
```

Patterns detected:
- `"price for X"` / `"цена за X"`
- `"who supplies X"` / `"кој испорачува X"`
- `"specifications for X"` / `"спецификации за X"`
- Medical terms: `surgical`, `медицински`, `хируршки`
- Office supplies: `toner`, `тонер`, `канцелариски`

### 3. New Search Method
```python
async def _search_product_items(
    search_keywords: List[str],
    years: int = 3
) -> Tuple[List[Dict], str]:
```

Searches:
- `product_items` table (from tender specs)
- `epazar_items` table (from e-pazar BOQ)

Returns:
- Price history (by year/quarter)
- Top suppliers
- Item details
- Specifications

### 4. Enhanced SQL Search
Modified `_fallback_sql_search()` to:
1. Detect item queries first
2. Search product tables if item query
3. Fall back to tender search if needed

## Example Queries

### Price Queries
```python
"What are past prices for surgical drapes?"
"Колку чинат хируршки ракавици?"
"How much do toner cartridges cost?"
"Price history for medical masks"
```

### Supplier Queries
```python
"Who wins medical supply tenders?"
"Кој добива тендери за медицински материјал?"
"Top suppliers for office equipment"
"Which companies supply surgical equipment?"
```

### Specification Queries
```python
"What specifications are required for surgical gloves?"
"Технички барања за хируршки маски"
"Show me specs for printer toners"
```

### Historical Queries
```python
"Last year around this time, what surgical drape tenders were there?"
"Претходни цени за канцелариски материјал"
"Price trends for medical equipment over 3 years"
```

## Response Format

### Item-Level Response Structure
```
**{ITEM NAME} Price History:**
- {YEAR}: Avg {PRICE} MKD/{UNIT} (range: {MIN}-{MAX}, {COUNT} tenders)

**Top Suppliers:**
1. {COMPANY} - {WINS} wins, avg price {PRICE} MKD
2. {COMPANY} - {WINS} wins, avg price {PRICE} MKD

**Common Specifications:**
- Material: {SPEC}
- Size: {SPEC}
- Standards: {SPEC}

Sources: [tender IDs]
```

## Database Queries

### Search Product Items
```sql
SELECT pi.name, pi.quantity, pi.unit, pi.unit_price,
       t.tender_id, t.title, t.procuring_entity, t.winner
FROM product_items pi
JOIN tenders t ON pi.tender_id = t.tender_id
WHERE pi.name ILIKE '%{keyword}%'
ORDER BY t.publication_date DESC
LIMIT 100
```

### Price Statistics
```sql
SELECT
    EXTRACT(YEAR FROM t.publication_date) as year,
    AVG(pi.unit_price) as avg_price,
    MIN(pi.unit_price) as min_price,
    MAX(pi.unit_price) as max_price,
    COUNT(*) as tender_count
FROM product_items pi
JOIN tenders t ON pi.tender_id = t.tender_id
WHERE pi.name ILIKE '%{keyword}%'
GROUP BY year
ORDER BY year DESC
```

### Top Suppliers
```sql
SELECT
    t.winner,
    COUNT(*) as wins,
    AVG(pi.unit_price) as avg_unit_price
FROM product_items pi
JOIN tenders t ON pi.tender_id = t.tender_id
WHERE pi.name ILIKE '%{keyword}%'
  AND t.winner IS NOT NULL
GROUP BY t.winner
ORDER BY COUNT(*) DESC
LIMIT 10
```

## Testing

### Run All Tests
```bash
python ai/test_item_queries.py
```

### Interactive Mode
```bash
python ai/test_item_queries.py interactive
```

### Single Query
```bash
python ai/test_item_queries.py "query:What are prices for masks?"
```

## Code Locations

### Main Implementation
- **File**: `/Users/tamsar/Downloads/nabavkidata/ai/rag_query.py`
- **Class**: `RAGQueryPipeline`
- **Methods**:
  - `_is_item_level_query()` - Line ~962
  - `_search_product_items()` - Line ~1013
  - `_fallback_sql_search()` - Enhanced at line ~1313

### System Prompt
- **Location**: `rag_query.py`, `PromptBuilder.SYSTEM_PROMPT`
- **Section**: Item-level query handling (section 6)

### Tests
- **File**: `/Users/tamsar/Downloads/nabavkidata/ai/test_item_queries.py`
- **Functions**: 10 example queries across different categories

### Documentation
- **README**: `/Users/tamsar/Downloads/nabavkidata/ai/ITEM_LEVEL_RAG_README.md`
- **This file**: Quick reference guide

## Performance

### Query Time
- Item detection: ~5ms
- Product search: ~50-200ms (depending on keyword count)
- LLM generation: ~2-5 seconds
- **Total**: ~2-5 seconds for item queries

### Database Load
- Uses existing indexes (no new indexes needed)
- Limits to 100 items per table
- Aggregates at DB level (efficient)

### Context Size
- ~2000-4000 tokens for item context
- Fits within Gemini limits
- Leaves room for conversation history

## Common Issues

### Issue: No Items Found
**Solution**:
1. Check if tables have data: `SELECT COUNT(*) FROM product_items;`
2. Try broader keywords
3. Check date range (default: 3 years)

### Issue: Wrong Language Response
**Solution**: System matches user's language automatically. If wrong, check query language.

### Issue: Slow Response
**Solution**:
1. Check database indexes
2. Reduce `years` parameter
3. Use more specific keywords

### Issue: Incomplete Specifications
**Solution**: Specifications may not exist in all tenders. Try multiple similar items.

## API Usage

### Python
```python
from ai.rag_query import RAGQueryPipeline

pipeline = RAGQueryPipeline()
answer = await pipeline.generate_answer("What are prices for surgical drapes?")

print(answer.answer)
print(f"Confidence: {answer.confidence}")
print(f"Sources: {len(answer.sources)}")
```

### With User Personalization
```python
answer = await pipeline.generate_answer(
    question="What are prices for surgical drapes?",
    user_id="user123"
)
```

### Batch Queries
```python
queries = [
    "Price for surgical masks",
    "Who supplies medical equipment",
    "Specs for surgical gloves"
]

answers = await pipeline.batch_query(queries)
for answer in answers:
    print(answer.answer)
```

## Environment Setup

Required environment variables:
```bash
export DATABASE_URL="postgresql+asyncpg://user:pass@host/db"
export GEMINI_API_KEY="your-api-key"
export GEMINI_MODEL="gemini-2.5-flash"  # optional
```

## Monitoring

### Logging
```python
import logging
logging.basicConfig(level=logging.INFO)

# Watch for these log messages:
# "Item-level query detected: pattern '{pattern}' matched"
# "Found {N} product items matching keywords"
# "Detected item-level query, searching product_items..."
```

### Metrics
Track in your application:
- `item_query_count` - Number of item-level queries
- `item_search_time` - Time to search product tables
- `items_found_avg` - Average items found per query

## Future Development

### Immediate
- [x] Item query detection
- [x] Product table search
- [x] Price statistics
- [x] Supplier rankings
- [x] System prompt enhancement

### Next Phase
- [ ] Price trend visualization
- [ ] Seasonal analysis
- [ ] Specification matching
- [ ] Supplier recommendations
- [ ] Anomaly detection

### Long Term
- [ ] Semantic product search with embeddings
- [ ] Multi-item price comparisons
- [ ] Predictive pricing models
- [ ] Quality scoring integration
