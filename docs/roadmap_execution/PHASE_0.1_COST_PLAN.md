# PHASE 0.1: Extraction Cost & Compute Plan

**Generated:** 2025-12-01
**Status:** COMPLETE
**Author:** AI Infrastructure Agent

---

## Executive Summary

Cost and compute analysis for processing **~13,000 usable documents** with text extraction, table detection, LLM-assisted extraction, and embedding generation.

### Total Estimated Costs

| Component | Estimated Cost | Notes |
|-----------|---------------|-------|
| **Text Extraction** | $0 | Local libraries (free) |
| **OCR (if needed)** | $13.50 - $135 | ~135 documents |
| **LLM Extraction** | $50 - $200 | Gemini for complex tables |
| **Embeddings** | $5 - $15 | ~13,000 documents |
| **Compute (EC2)** | ~$50/month | Existing t3.medium |
| **TOTAL** | **$118.50 - $400** | One-time processing |

---

## 1. Document Processing Volume

Based on Phase 0.0 audit:

| Document Type | Count | Avg Pages | Total Pages | Action |
|---------------|-------|-----------|-------------|--------|
| PDFs (text) | ~5,000 | 8 | ~40,000 | Text extraction |
| PDFs (OCR) | ~135 | 10 | ~1,350 | OCR service |
| PDFs (retry) | ~1,500 | 6 | ~9,000 | Retry extraction |
| Word docs | ~850 | 5 | ~4,250 | python-docx |
| Excel files | ~100 | 3 sheets | ~300 sheets | openpyxl |
| ePazar docs | ~2,500 | 4 | ~10,000 | Text extraction |
| OTHER (detect) | ~3,000 | ? | ? | File type detection |
| **TOTAL** | **~13,085** | - | **~64,900 pages** | - |

---

## 2. Text Extraction Costs

### 2.1 PDF Extraction (Free - PyMuPDF/pdfminer)

| Library | Documents | Cost | Speed |
|---------|-----------|------|-------|
| PyMuPDF (fitz) | ~8,000 | $0 | ~100 docs/min |
| pdfminer.six | Fallback | $0 | ~50 docs/min |

**Estimated Time:** 8,000 docs ÷ 100/min = **80 minutes**

### 2.2 Word Extraction (Free - python-docx)

| Library | Documents | Cost | Speed |
|---------|-----------|------|-------|
| python-docx | ~850 | $0 | ~200 docs/min |
| antiword (DOC) | ~91 | $0 | ~100 docs/min |

**Estimated Time:** ~950 docs ÷ 150/min = **6 minutes**

### 2.3 Excel Extraction (Free - openpyxl)

| Library | Documents | Cost | Speed |
|---------|-----------|------|-------|
| openpyxl | ~100 | $0 | ~50 docs/min |

**Estimated Time:** 100 docs ÷ 50/min = **2 minutes**

### 2.4 Total Text Extraction

| Metric | Value |
|--------|-------|
| **Total Cost** | $0 |
| **Total Time** | ~90 minutes |
| **Libraries** | PyMuPDF, python-docx, openpyxl |

---

## 3. OCR Costs (Scanned PDFs)

### 3.1 Volume Estimate
- **Scanned PDFs identified:** ~135 documents
- **Average pages:** ~10 per document
- **Total pages for OCR:** ~1,350 pages

### 3.2 OCR Service Options

| Service | Cost per Page | Total Cost (1,350 pages) | Quality |
|---------|--------------|--------------------------|---------|
| **Tesseract (local)** | $0 | $0 | Medium |
| **Google Vision API** | $0.001 (first 1k free) | ~$0.35 | High |
| **AWS Textract** | $0.015 | ~$20.25 | High |
| **Azure Computer Vision** | $0.001 | ~$1.35 | High |
| **LLM Vision (Gemini)** | $0.10 | ~$135 | Highest |

### 3.3 Recommended OCR Strategy

**Tier 1: Tesseract (Free)**
- Use for initial attempt on all 135 scanned PDFs
- Expected success: ~70% (95 docs)

**Tier 2: Google Vision API (Fallback)**
- For Tesseract failures: ~40 docs × 10 pages = 400 pages
- Cost: ~$0.40 (first 1k free)

**Total OCR Budget:** **$0 - $20** (with free tier + Tesseract)

---

## 4. LLM Extraction Costs

### 4.1 Use Cases for LLM

| Task | Documents | Tokens/Doc | Total Tokens |
|------|-----------|------------|--------------|
| Complex table extraction | ~500 | 5,000 | 2,500,000 |
| Failed auto-extraction | ~1,000 | 3,000 | 3,000,000 |
| Item specification parsing | ~2,000 | 2,000 | 4,000,000 |
| **TOTAL** | - | - | **9,500,000 tokens** |

### 4.2 LLM Pricing (Gemini)

| Model | Input (per 1M) | Output (per 1M) | Estimated Cost |
|-------|---------------|-----------------|----------------|
| Gemini 1.5 Flash | $0.075 | $0.30 | ~$4 |
| Gemini 1.5 Pro | $1.25 | $5.00 | ~$60 |
| Gemini 2.0 Flash | $0.10 | $0.40 | ~$5 |

### 4.3 Recommended LLM Strategy

**Tier 1: Gemini 2.0 Flash (Primary)**
- Use for 80% of LLM tasks
- Cost: ~$4 for 8M tokens

**Tier 2: Gemini 1.5 Pro (Complex)**
- Use for 20% of complex documents
- Cost: ~$12 for 2M tokens

**Total LLM Budget:** **$16 - $50** (conservative)

---

## 5. Embeddings Costs

### 5.1 Volume

| Content Type | Items | Avg Chars | Avg Tokens |
|--------------|-------|-----------|------------|
| Document chunks | ~26,000 | 2,000 | ~500 |
| Product items | ~12,000 | 500 | ~125 |
| Tender summaries | ~5,000 | 1,000 | ~250 |
| **TOTAL** | **~43,000** | - | **~18,750,000 tokens** |

### 5.2 Embedding Service Pricing

| Service | Model | Cost per 1M tokens | Total Cost |
|---------|-------|-------------------|------------|
| OpenAI | text-embedding-3-small | $0.02 | ~$0.38 |
| OpenAI | text-embedding-3-large | $0.13 | ~$2.44 |
| Google | text-embedding-004 | $0.00025 | ~$0.005 |
| Voyage | voyage-3 | $0.06 | ~$1.13 |

### 5.3 Recommended Embedding Strategy

**Google text-embedding-004 (Best Value)**
- 18.75M tokens × $0.00025 = **$0.005**
- Effectively free

**Alternative: OpenAI text-embedding-3-small**
- 18.75M tokens × $0.02 = **$0.38**
- Still very cheap

**Total Embedding Budget:** **$0 - $5**

---

## 6. Compute Infrastructure

### 6.1 Current EC2 Instance

| Attribute | Value |
|-----------|-------|
| Instance Type | t3.medium |
| vCPUs | 2 |
| RAM | 4 GB |
| Cost | ~$0.0416/hour (~$30/month) |

### 6.2 Processing Capacity

| Task | Current Speed | With Optimization |
|------|---------------|-------------------|
| Text extraction | ~100 docs/min | ~200 docs/min (parallel) |
| Table detection | ~10 docs/min | ~30 docs/min (camelot batch) |
| LLM extraction | ~5 docs/min | ~10 docs/min (async) |
| Embeddings | ~100 items/min | ~500 items/min (batch) |

### 6.3 Recommended Upgrade

For faster processing, consider:

| Instance | vCPUs | RAM | Cost/hour | Speed Gain |
|----------|-------|-----|-----------|------------|
| t3.large | 2 | 8 GB | $0.0832 | 1.5x |
| t3.xlarge | 4 | 16 GB | $0.1664 | 2.5x |
| c6i.xlarge | 4 | 8 GB | $0.17 | 3x (CPU) |

**Recommendation:** Stay with t3.medium for now; upgrade to t3.xlarge ($0.17/hr) if processing takes >24 hours.

**Compute Budget:** **$30 - $100/month**

---

## 7. Batch Processing Architecture

### 7.1 Recommended Queue System

```
┌─────────────────┐
│  PostgreSQL     │  ← Use existing DB for queue
│  extraction_    │
│  queue table    │
└────────┬────────┘
         │
    ┌────▼────┐
    │ Worker  │  ← Python worker process
    │ Process │
    └────┬────┘
         │
    ┌────▼────────────────────┐
    │  Processing Pipeline    │
    │  1. Download document   │
    │  2. Detect file type    │
    │  3. Extract text        │
    │  4. Detect tables       │
    │  5. LLM extraction      │
    │  6. Generate embeddings │
    │  7. Update database     │
    └─────────────────────────┘
```

### 7.2 Queue Table (Already Proposed)

```sql
CREATE TABLE extraction_queue (
    queue_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id UUID REFERENCES documents(doc_id),
    priority INTEGER DEFAULT 5,  -- 1=highest
    status VARCHAR(50) DEFAULT 'pending',
    attempts INTEGER DEFAULT 0,
    last_error TEXT,
    queued_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);
```

### 7.3 Batch Size Recommendations

| Task | Batch Size | Reason |
|------|------------|--------|
| Text extraction | 100 docs | Memory efficient |
| Table detection | 10 docs | CPU intensive |
| LLM extraction | 5 docs | Rate limits |
| Embeddings | 100 items | API batch limit |

### 7.4 Rate Limits

| Service | Rate Limit | Recommended |
|---------|------------|-------------|
| Gemini API | 60 RPM | 30 RPM (safe) |
| Google Embeddings | 600 RPM | 300 RPM |
| e-nabavki downloads | Unknown | 10 RPM (polite) |
| Database writes | No limit | 1000/batch |

---

## 8. Worker Process Architecture

### 8.1 Single Worker (Current)

```python
# Recommended for initial processing
async def process_documents():
    while True:
        # Get batch from queue
        batch = await get_pending_batch(limit=100)
        if not batch:
            await asyncio.sleep(60)
            continue

        # Process each document
        for doc in batch:
            try:
                await process_single_document(doc)
            except Exception as e:
                await mark_failed(doc, str(e))
```

### 8.2 Multi-Worker (Scaled)

For faster processing, run multiple workers:

```bash
# Terminal 1
python3 worker.py --worker-id=1 --priority=high

# Terminal 2
python3 worker.py --worker-id=2 --priority=medium

# Terminal 3
python3 worker.py --worker-id=3 --priority=low
```

### 8.3 Worker Monitoring

```python
# Log progress every 100 documents
if processed % 100 == 0:
    logger.info(f"Progress: {processed}/{total} ({processed/total*100:.1f}%)")
    logger.info(f"Success: {success_count}, Failed: {fail_count}")
    logger.info(f"ETA: {estimate_remaining_time()}")
```

---

## 9. Processing Timeline

### 9.1 Estimated Time (Single Worker)

| Phase | Documents | Time (est) |
|-------|-----------|------------|
| Text extraction | 13,000 | 2-3 hours |
| Table detection | 5,000 | 8-10 hours |
| LLM extraction | 3,500 | 6-8 hours |
| Embeddings | 43,000 items | 2-3 hours |
| **TOTAL** | - | **18-24 hours** |

### 9.2 Estimated Time (Multi-Worker, t3.xlarge)

| Phase | Documents | Time (est) |
|-------|-----------|------------|
| Text extraction | 13,000 | 1 hour |
| Table detection | 5,000 | 3-4 hours |
| LLM extraction | 3,500 | 3-4 hours |
| Embeddings | 43,000 items | 1 hour |
| **TOTAL** | - | **8-10 hours** |

---

## 10. Total Cost Summary

### 10.1 One-Time Processing Costs

| Component | Low Estimate | High Estimate |
|-----------|--------------|---------------|
| Text extraction | $0 | $0 |
| OCR | $0 | $20 |
| LLM extraction | $16 | $50 |
| Embeddings | $0 | $5 |
| Compute (extra) | $0 | $20 |
| **TOTAL** | **$16** | **$95** |

### 10.2 Monthly Ongoing Costs

| Component | Cost | Notes |
|-----------|------|-------|
| EC2 (t3.medium) | $30 | Current |
| RDS (PostgreSQL) | $15 | Current |
| LLM (maintenance) | $5 | Updates |
| **TOTAL** | **$50/month** | Current infrastructure |

### 10.3 ROI Analysis

| Metric | Value |
|--------|-------|
| One-time extraction cost | ~$50 |
| Documents processed | ~13,000 |
| Cost per document | **$0.004** |
| Items with prices enabled | ~5,000+ |
| Value per user query | High |

---

## 11. Recommendations

### 11.1 Immediate Actions

1. **Use existing infrastructure** (t3.medium)
   - Sufficient for 13k documents
   - No upgrade needed initially

2. **Start with free tools**
   - PyMuPDF for PDFs
   - python-docx for Word
   - Tesseract for OCR

3. **Use Gemini Flash for LLM**
   - Cheapest viable option
   - Good quality for tables

4. **Use Google embeddings**
   - Essentially free
   - Good quality

### 11.2 Cost Optimization

1. **Batch aggressively** - Reduce API calls
2. **Cache LLM responses** - Don't re-extract same content
3. **Prioritize high-value docs** - Extract most valuable first
4. **Skip known bad documents** - Save processing time

### 11.3 Risk Mitigation

1. **Set spending alerts** - $50 warning, $100 stop
2. **Monitor API usage** - Check daily
3. **Implement retries** - Don't fail on transient errors
4. **Log everything** - Debug failures efficiently

---

## 12. Implementation Checklist

### Pre-Processing
- [ ] Set up extraction_queue table
- [ ] Install required libraries (PyMuPDF, python-docx, camelot)
- [ ] Configure Gemini API keys
- [ ] Set up Google embedding credentials
- [ ] Create worker script

### Processing
- [ ] Run Phase A.0 (bad document detection) first
- [ ] Process priority documents first (Phase 0.2)
- [ ] Monitor costs during processing
- [ ] Checkpoint progress regularly

### Post-Processing
- [ ] Verify extraction quality
- [ ] Generate embeddings
- [ ] Update extraction metrics
- [ ] Clean up temporary files

---

## Status: DONE

**Phase 0.1 Extraction Cost & Compute Plan is COMPLETE.**

**Key Decision:** Proceed with existing infrastructure. Total cost: **$16 - $95** one-time.

Next: Proceed to Phase 0.2 (Prioritization Engine).
