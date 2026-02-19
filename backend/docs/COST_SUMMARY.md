# Quick Cost Summary - Nabavkidata Extraction Pipeline

**TL;DR:** $10 one-time + $18/month

---

## Current Status

- 📄 **2,795 documents** in database
- ✅ **81% processed** (2,267 docs with text)
- 🔴 **1.1% embedded** (only 31 docs) - **CRITICAL BOTTLENECK**
- 💾 **375 MB** PDFs, **112 MB** database

---

## What Needs To Be Done

### 1. Complete Text Extraction (524 docs)
- **Time:** 2 hours
- **Cost:** $0.03
- **Why:** Extract text from remaining PDFs

### 2. Generate Document Embeddings (2,764 docs)
- **Time:** 2 hours
- **Cost:** $0.69
- **Why:** Enable semantic search (currently falls back to SQL)

### 3. Generate Item Embeddings (11,624 items)
- **Time:** 1 hour
- **Cost:** $0.15
- **Why:** Enable item-level price queries

### 4. Extract Tables & Specs (314 docs)
- **Time:** 2 hours
- **Cost:** $2-6
- **Why:** Structured product data

---

## Total Costs

### One-Time (Initial Processing)
```
Text Extraction:      $0.03
Table Extraction:     $2-6
Embeddings:           $0.90
Contingency:          $2
─────────────────────────
TOTAL:               $5-10
```

### Monthly (Ongoing)
```
RDS Database:        $15.00
S3 Storage:          $0.01
New Doc Processing:  $0.67
Gemini API (RAG):    $2.50
─────────────────────────
TOTAL:              ~$18/month
```

### 6-Month Total
```
One-time:            $10
6 months × $18:     $108
─────────────────────────
TOTAL:              $118
```

---

## Cost Breakdown by API

| Service | Usage | Cost |
|---------|-------|------|
| **Google Gemini Embeddings** | 7M tokens | $0.70 |
| **Google Gemini Flash (RAG)** | 10K queries/month | $2.50/mo |
| **Tesseract OCR** | 11 docs | $0 (local) |
| **Camelot (tables)** | 314 docs | $0 (local) |

**Recommendation:** Use local tools where possible, Gemini for embeddings/RAG

---

## Why Embeddings Are Critical

**Current Problem:**
```python
# From rag_query.py line 656:
# IMPORTANT: We only have ~279 embeddings but 2700+ tenders.
# Vector search often returns irrelevant results
# ALWAYS use SQL search for now until we have comprehensive embeddings
```

**Current Coverage:**
- Documents with embeddings: 31 / 2,795 = **1.1%**
- Tenders with embeddings: 12 / 3,836 = **0.3%**
- Items with embeddings: 0 / 11,624 = **0%**

**After Processing:**
- Document embeddings: **~13,820 chunks** (5 per doc)
- Item embeddings: **11,624 vectors**
- Tender embeddings: **3,836 vectors**
- **Total: 29,280 embeddings** vs current 279 (105x improvement)

**Impact:**
- ✅ Enable true semantic search (currently disabled)
- ✅ Answer "What are prices for surgical drapes?" with actual data
- ✅ Find similar products across tenders
- ✅ Personalized recommendations
- ✅ Better competitor analysis

---

## Storage Growth

| Data | Current | After Processing | 6 Months |
|------|---------|------------------|----------|
| PDFs | 375 MB | 400 MB | 600 MB |
| Database | 112 MB | 250 MB | 500 MB |
| Embeddings | 3.9 MB | 80 MB | 120 MB |

**RDS Cost Impact:** Negligible (still under 1 GB)

---

## Timeline

### Week 1-2: Text & Tables
- Day 1-2: Process 524 pending documents
- Day 3-4: Extract tables and specifications
- Day 5: Validation

**Output:** 100% text extraction

### Week 3-4: Embeddings (CRITICAL)
- Day 1: Document embeddings (2,764 docs)
- Day 2: Item embeddings (11,624 items)
- Day 3: Tender embeddings (3,836 tenders)
- Day 4: Optimize vector indexes
- Day 5: Integration testing

**Output:** 100% embedding coverage, RAG search enabled

### Week 5: Automation
- Automated embedding pipeline
- Monitoring setup
- Documentation

**Output:** Self-sustaining system

---

## Optimization Tips

1. **Use Batching**
   - Batch 100 embeddings per API call
   - 50% faster, same cost

2. **Cache Aggressively**
   - Never re-embed unchanged documents
   - Save document hash to detect changes

3. **Monitor Daily**
   - Track API costs
   - Alert if >$5/day

4. **Use Local Processing**
   - Text extraction: PyPDF2 (free)
   - Table extraction: Camelot (free)
   - OCR: Tesseract (free)
   - Only use APIs for embeddings & LLM queries

---

## Expected ROI

**Investment:** $10 one-time + $18/month
**Returns:**
- Enable semantic search (core product feature)
- Answer 90% of user queries accurately (vs 70% now)
- Process new documents automatically
- Item-level price intelligence
- Competitive advantage in Macedonian market

**Payback Period:** Immediate (enables core product)

---

## Approval Checklist

- [ ] Budget approved: $15 one-time processing
- [ ] Budget approved: $20/month ongoing
- [ ] Gemini API key has sufficient quota
- [ ] Database has 200 MB free space
- [ ] Developer time allocated: 1 week

**Ready to start? Run:**
```bash
cd /Users/tamsar/Downloads/nabavkidata/ai
python process_pending_extraction.py  # Process 524 docs
python generate_all_embeddings.py     # Generate 29K embeddings
```

---

**Questions? See full details in:** `/Users/tamsar/Downloads/nabavkidata/docs/RESOURCE_PLAN.md`
