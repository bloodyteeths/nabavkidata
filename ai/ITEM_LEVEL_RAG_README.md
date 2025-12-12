# Item-Level RAG Query Enhancement

## Overview

The RAG (Retrieval-Augmented Generation) system has been enhanced to support **item-level queries** - questions about specific products, their prices, suppliers, and specifications. This enables users to ask questions like:

- "What are past prices for surgical drapes?"
- "Who supplies medical equipment?"
- "What specifications are required for surgical gloves?"
- "Show me price trends for toner cartridges"

## Key Features

### 1. **Intelligent Query Detection**

The system automatically detects when a query is asking about specific items/products vs general tenders:

```python
# Item-level query patterns detected:
- "price for X", "цена за X"
- "who supplies X", "кој испорачува X"
- "specifications for X", "спецификации за X"
- "past prices", "историја на цени"
- Medical/procurement product terms (surgical, медицински, тонер, etc.)
```

### 2. **Dual-Table Search**

When an item-level query is detected, the system searches:
- `product_items` table (extracted from tender technical specifications)
- `epazar_items` table (e-Pazar marketplace items with detailed BOQ data)

### 3. **Comprehensive Price History**

The system aggregates price data by:
- Year and quarter
- Average, minimum, and maximum prices
- Total tender count
- Unit of measurement

Example output:
```
**Surgical Drapes Price History:**
- 2024: Avg 150 MKD/piece (range: 120-180, 15 tenders)
- 2023: Avg 165 MKD/piece (range: 140-190, 12 tenders)
```

### 4. **Supplier/Winner Analytics**

Automatically identifies and ranks:
- Top suppliers for specific items
- Number of wins per supplier
- Average unit prices per supplier
- Total contract values

Example output:
```
**Top Suppliers:**
1. MediSupply DOO - Won 8 contracts, avg price 145 MKD
2. HealthCare Ltd - Won 5 contracts, avg price 155 MKD
```

### 5. **Specifications Extraction**

Displays technical specifications when available:
- Material type
- Sizes/dimensions
- Quality standards
- Certifications
- Manufacturer and model information

## Architecture

### Query Flow

```
User Query
    ↓
Query Type Detection
    ↓
┌───────────────┬───────────────┐
│ Item Query    │ Tender Query  │
└───────────────┴───────────────┘
        ↓                ↓
Product Search      Tender Search
(product_items +    (tenders +
 epazar_items)       epazar_tenders)
        ↓                ↓
Price Statistics    Standard Context
Supplier Stats
Specifications
        ↓                ↓
    LLM Generation
        ↓
    Formatted Answer
```

### Database Schema

#### product_items
```sql
- name (TEXT) - Product name (searchable)
- name_mk, name_en - Macedonian/English names
- quantity, unit - Quantity and unit of measurement
- unit_price, total_price - Pricing information
- specifications (JSONB) - Technical specs
- cpv_code - Classification
- manufacturer, model, supplier - Product details
- tender_id (FK) - Related tender
```

#### epazar_items
```sql
- item_name - Item name
- item_description - Detailed description
- quantity, unit - Quantity and UoM
- estimated_unit_price_mkd - Price per unit
- estimated_total_price_mkd - Total price
- specifications (JSONB) - Technical specs
- tender_id (FK) - Related e-pazar tender
```

### Key Methods

#### `_is_item_level_query(question: str) -> bool`
Detects if a query is asking about specific items vs general tenders.

Uses regex patterns to match:
- Price queries ("price for", "цена за")
- Supplier queries ("who supplies", "кој испорачува")
- Specification queries ("specs for", "спецификации за")
- Medical/product terms

#### `_search_product_items(keywords: List[str]) -> Tuple[List[Dict], str]`
Searches both `product_items` and `epazar_items` tables.

Returns:
- List of matching items with full details
- Formatted context including:
  - Price history (by year/quarter)
  - Top suppliers
  - Individual item details
  - Specifications

#### Enhanced `_fallback_sql_search()`
Now checks for item-level queries first:
1. Detect query type
2. If item query → search product tables
3. If tender query OR no items found → search tender tables
4. Return formatted context for LLM

## Usage Examples

### Example 1: Price History Query

```python
from ai.rag_query import ask_question

answer = await ask_question("What are past prices for surgical drapes?")
print(answer.answer)
```

Expected response:
```
Based on 27 tenders over the last 3 years:

**Surgical Drapes Price History:**
- 2024: Avg 150 MKD/piece (range: 120-180, 15 tenders)
- 2023: Avg 165 MKD/piece (range: 140-190, 12 tenders)

**Top Suppliers:**
1. MediSupply DOO - Won 8 contracts, avg price 145 MKD
2. HealthCare Ltd - Won 5 contracts, avg price 155 MKD
3. BioMed Skopje - Won 4 contracts, avg price 160 MKD

**Common Specifications:**
- Material: Non-woven SMS fabric
- Sizes: 120x150cm, 150x200cm
- Sterility: EO sterilized
- Standards: EN 13795

Sources: [list of tender IDs]
```

### Example 2: Supplier Analysis

```python
answer = await ask_question("Who wins medical supply tenders?")
```

Expected response:
```
Based on our tender data, the top medical supply winners are:

**Top Medical Suppliers:**
1. MediSupply DOO - 34 wins, total value 12.5M MKD
2. HealthCare Macedonia - 28 wins, total value 9.8M MKD
3. BioMed Skopje - 21 wins, total value 7.2M MKD
4. PharmaDist DOOEL - 18 wins, total value 6.1M MKD

These companies consistently win medical supply contracts across
hospitals and health institutions in North Macedonia.
```

### Example 3: Specification Query

```python
answer = await ask_question("What specifications are required for surgical gloves?")
```

Expected response:
```
Based on tender technical specifications:

**Surgical Gloves Requirements:**

Common specifications:
- Material: Natural latex or nitrile
- Powder: Powder-free (required by most hospitals)
- Sterility: Sterile, individually packaged
- Sizes: 6.5, 7.0, 7.5, 8.0, 8.5
- Standards:
  - EN 455 (Medical gloves)
  - ISO 10282 (Sterile surgical gloves)
  - CE marked

Typical quantities: 50-200 pairs per tender
Average price: 8-12 MKD/pair

Found in 45 tenders across 23 healthcare institutions.
```

### Example 4: Macedonian Query

```python
answer = await ask_question("Колку чинат хируршки маски?")
```

Expected response (in Macedonian):
```
Според нашите податоци за последните 3 години:

**Цени за хируршки маски:**
- 2024: Просечна цена 2.50 МКД/парче (опсег: 1.80-3.20, 32 тендери)
- 2023: Просечна цена 2.80 МКД/парче (опсег: 2.10-3.50, 28 тендери)

**Главни добавувачи:**
1. МедиСупли ДОО - 12 победи, просечна цена 2.30 МКД
2. Фарма Дистрибуција - 9 победи, просечна цена 2.60 МКД
3. БиоМед Скопје - 7 победи, просечна цена 2.40 МКД

Маските се со три слоја, нетканен материјал, со еластична лента.
```

## Testing

Run the test suite:

```bash
# Test all example queries
python ai/test_item_queries.py

# Interactive mode
python ai/test_item_queries.py interactive

# Test specific functionality
python ai/test_item_queries.py price      # Price history
python ai/test_item_queries.py supplier   # Supplier analysis

# Custom query
python ai/test_item_queries.py "query:What are prices for masks?"
```

## System Prompt Enhancement

The system prompt has been updated with specific instructions for item-level queries:

```
6. ITEM-LEVEL QUERY HANDLING:
   When the context includes "ПРОИЗВОДИ / АРТИКЛИ" or "ИСТОРИЈА НА ЦЕНИ" sections:
   - Extract and report SPECIFIC per-unit prices in MKD
   - Calculate price trends (avg, min, max) by year/quarter if multiple entries exist
   - List TOP suppliers/winners for this specific item
   - Show technical specifications if available
   - If exact match not found, show similar items and explain the difference
   - Always cite tender IDs as sources
```

This ensures the LLM properly formats item-level responses with:
- Price statistics and trends
- Supplier rankings
- Technical specifications
- Source attribution

## Performance Considerations

### Efficiency
- Uses database indexes on `product_items.name`, `epazar_items.item_name`
- Full-text search with `ILIKE ANY()` for multiple keywords
- Limits results to 100 items per table
- Aggregates statistics at database level (not in Python)

### Context Size
- Item details limited to 30 items in context (prevents token overflow)
- Price statistics grouped by year (not quarter) for conciseness
- Top 10 suppliers only
- Specifications truncated if too long

### Query Optimization
```sql
-- Indexes used:
CREATE INDEX idx_product_items_name ON product_items USING gin(to_tsvector('simple', name));
CREATE INDEX idx_epazar_items_name ON epazar_items USING gin(to_tsvector('simple', item_name));
CREATE INDEX idx_product_items_tender_id ON product_items(tender_id);
CREATE INDEX idx_epazar_items_tender_id ON epazar_items(tender_id);
```

## Integration with Existing System

The enhancement is **backward compatible**:
- Non-item queries still work exactly as before
- Falls back to tender-level search if no items found
- Uses same LLM prompt structure
- Returns same `RAGAnswer` format

### API Unchanged

```python
# Existing code continues to work
pipeline = RAGQueryPipeline()
answer = await pipeline.generate_answer("your question")

# Works for both tender and item queries
answer_tender = await pipeline.generate_answer("Show me IT tenders")
answer_item = await pipeline.generate_answer("What are prices for laptops?")
```

## Future Enhancements

### Planned Features
1. **Price Trend Visualization** - Generate charts showing price trends over time
2. **Seasonal Analysis** - Detect seasonal patterns in procurement (e.g., medical supplies in flu season)
3. **Specification Matching** - Match user requirements to available products
4. **Supplier Recommendation** - Suggest best suppliers based on price/quality/reliability
5. **Anomaly Detection** - Flag unusual prices or specifications
6. **Multi-Item Comparisons** - "Compare surgical gloves vs surgical drapes prices"

### Technical Improvements
1. **Semantic Search** - Use embeddings for better product matching
2. **Fuzzy Matching** - Handle typos and variations in product names
3. **CPV Code Integration** - Use standard procurement classification codes
4. **Currency Conversion** - Support EUR/MKD conversions with historical rates
5. **Caching** - Cache frequent item queries for faster response

## Troubleshooting

### No Items Found

If the system returns "No items found":
1. Check if `product_items` or `epazar_items` tables have data
2. Verify search keywords are in Macedonian or English
3. Try broader terms (e.g., "medical" instead of "surgical drapes")
4. Check date range (default: last 3 years)

### Inaccurate Prices

If prices seem wrong:
1. Verify `unit_price` vs `total_price` in database
2. Check if currency is MKD (not EUR)
3. Look for outliers in data (e.g., typos in original tender)
4. Cross-reference with tender PDFs

### Missing Specifications

If specifications not showing:
1. Check if `specifications` field is populated (JSONB)
2. May need to run specification extraction job
3. Some tenders don't include detailed specs

## Database Population

To populate product_items and epazar_items:

```bash
# Extract items from tender PDFs
python scripts/extract_product_items.py

# Scrape e-pazar items
python scraper/run_epazar_scraper.py

# Import from external source
python scripts/import_items_from_csv.py data/items.csv
```

## Support

For issues or questions:
- Check logs: `tail -f /var/log/nabavkidata/rag.log`
- Review test output: `python ai/test_item_queries.py > test_results.txt`
- Database queries: Check SQL in `ai/rag_query.py` `_search_product_items()`

## License

Part of NabavkiData platform - Internal use only
