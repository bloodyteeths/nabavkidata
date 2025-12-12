# API Pricing Reference - Nabavkidata Pipeline

**Last Updated:** 2025-11-29

This document provides detailed pricing for all APIs used in the extraction pipeline.

---

## Google Gemini API

### Models Used

| Model | Purpose | Input Cost | Output Cost | Context Window |
|-------|---------|------------|-------------|----------------|
| **gemini-2.5-flash** | RAG queries (primary) | $0.075/1M tokens | $0.30/1M tokens | 1M tokens |
| **gemini-2.0-flash** | RAG queries (fallback) | $0.075/1M tokens | $0.30/1M tokens | 1M tokens |
| **text-embedding-004** | Document embeddings | $0.10/1M tokens | - | - |

### Embedding Pricing

**Current Model:** `text-embedding-004` (768 dimensions)

| Task | Tokens/Item | Items | Total Tokens | Cost |
|------|------------|-------|--------------|------|
| Document chunk | 500 | 13,820 | 6,910,000 | $0.69 |
| Product item | 125 | 11,624 | 1,453,000 | $0.15 |
| Tender summary | 150 | 3,836 | 575,400 | $0.06 |
| **Total** | - | **29,280** | **8,938,400** | **$0.90** |

### RAG Query Pricing

**Average Query:**
- Input: System prompt (500 tokens) + Context (2,000 tokens) + Question (50 tokens) = 2,550 tokens
- Output: Answer (300 tokens)

**Cost per Query:**
- Input: 2,550 tokens × $0.075/1M = $0.00019
- Output: 300 tokens × $0.30/1M = $0.00009
- **Total: $0.00028 per query**

**Monthly Volume Estimates:**

| Usage Level | Queries/Month | Monthly Cost |
|-------------|--------------|--------------|
| Low (100 users) | 3,000 | $0.84 |
| Medium (500 users) | 10,000 | $2.80 |
| High (2000 users) | 30,000 | $8.40 |
| Enterprise (10K users) | 100,000 | $28.00 |

**Current Estimate:** 10,000 queries/month = **$2.80/month**

---

## Alternative Embedding Providers (Comparison)

### OpenAI

| Model | Dimensions | Cost/1M Tokens | Total Cost (9M tokens) | Notes |
|-------|-----------|----------------|----------------------|-------|
| text-embedding-3-small | 1536 | $0.020 | $0.18 | Cheapest, good quality |
| text-embedding-3-large | 3072 | $0.130 | $1.16 | Best quality, expensive |
| text-embedding-ada-002 | 1536 | $0.100 | $0.89 | Legacy model |

### Cohere

| Model | Dimensions | Cost/1M Tokens | Total Cost | Notes |
|-------|-----------|----------------|------------|-------|
| embed-english-v3.0 | 1024 | $0.100 | $0.89 | Good for English only |
| embed-multilingual-v3.0 | 1024 | $0.100 | $0.89 | Better for Macedonian |

### Voyage AI

| Model | Dimensions | Cost/1M Tokens | Total Cost | Notes |
|-------|-----------|----------------|------------|-------|
| voyage-large-2 | 1536 | $0.120 | $1.07 | High quality |
| voyage-code-2 | 1536 | $0.120 | $1.07 | For code (not relevant) |

### Recommendation

**Current Choice: Google text-embedding-004**
- ✅ Cost: $0.90 (competitive)
- ✅ Quality: Excellent for multilingual (handles Macedonian)
- ✅ Integration: Already using Gemini for RAG
- ✅ Dimensions: 768 (good balance of quality/storage)

**Alternative if switching:** OpenAI text-embedding-3-small ($0.18)
- 80% cost savings
- Need to test Macedonian language quality

---

## Document Processing APIs

### OCR Services

| Service | Cost Model | Estimated Cost | Notes |
|---------|-----------|----------------|-------|
| **Tesseract (Local)** | Free | $0 | ✅ Recommended for simple OCR |
| Google Vision API | $1.50/1K pages | $16.50 (11 docs) | Overkill for our use case |
| AWS Textract | $1.50/1K pages | $16.50 | Good quality but expensive |
| Azure Computer Vision | $1.00/1K pages | $11.00 | Mid-range option |

**Recommendation:** Use Tesseract locally (free)

### Table Extraction

| Service | Cost Model | Estimated Cost | Notes |
|---------|-----------|----------------|-------|
| **Camelot (Local)** | Free | $0 | ✅ Recommended for simple tables |
| **Tabula (Local)** | Free | $0 | Alternative to Camelot |
| GPT-4 Vision | $0.01/image | $6.28 (628 tables) | Good for complex tables |
| Gemini Vision | $0.0025/image | $1.57 | ✅ Best quality/price ratio |
| AWS Textract (Tables) | $0.015/page | $9.42 | Specialized but expensive |

**Recommendation:**
1. Try Camelot first (free)
2. Use Gemini Vision for failed extractions ($0.0025/image)

---

## LLM APIs (For Specification Extraction)

### GPT Models

| Model | Input Cost/1M | Output Cost/1M | Use Case |
|-------|--------------|----------------|----------|
| GPT-4 Turbo | $10.00 | $30.00 | Too expensive |
| GPT-4o | $2.50 | $10.00 | High quality, pricey |
| GPT-4o-mini | $0.15 | $0.60 | Good balance |
| GPT-3.5-turbo | $0.50 | $1.50 | Older, cheaper |

**Cost for 500 spec extractions (avg 2K input, 500 output):**
- GPT-4o-mini: (500 × 2K × $0.15/1M) + (500 × 500 × $0.60/1M) = $0.15 + $0.15 = **$0.30**

### Gemini Models

| Model | Input Cost/1M | Output Cost/1M | Use Case |
|-------|--------------|----------------|----------|
| gemini-2.5-pro | $1.25 | $5.00 | Best quality |
| gemini-2.5-flash | $0.075 | $0.30 | ✅ Best value |
| gemini-2.0-flash | $0.075 | $0.30 | Fallback |

**Cost for 500 spec extractions:**
- gemini-2.5-flash: (500 × 2K × $0.075/1M) + (500 × 500 × $0.30/1M) = $0.075 + $0.075 = **$0.15**

### Claude Models

| Model | Input Cost/1M | Output Cost/1M | Use Case |
|-------|--------------|----------------|----------|
| Claude 3.5 Sonnet | $3.00 | $15.00 | Best quality, expensive |
| Claude 3 Haiku | $0.25 | $1.25 | Fast, cheap |

**Recommendation:** Gemini 2.5-flash ($0.15 for 500 docs) - already integrated

---

## AWS Infrastructure Costs

### RDS PostgreSQL

**Current Instance:** db.t3.micro (Single-AZ)
- vCPUs: 2
- Memory: 1 GB
- Storage: 20 GB (GP3)

| Component | Specification | Cost/Month |
|-----------|--------------|------------|
| Instance (On-Demand) | db.t3.micro | $14.60 |
| Instance (1-yr Reserved) | db.t3.micro | $9.90 |
| Storage (GP3) | 20 GB @ $0.115/GB | $2.30 |
| Backups | 20 GB | $2.00 |
| **Total (On-Demand)** | - | **$18.90** |
| **Total (Reserved)** | - | **$14.20** |

**Projected After Processing:**

| Component | Specification | Cost/Month |
|-----------|--------------|------------|
| Instance | db.t3.micro | $14.60 |
| Storage (GP3) | 1 GB @ $0.115/GB | $0.12 |
| Backups | 1 GB | $0.10 |
| **Total** | - | **$14.82** |

**Storage grows slowly - no significant cost impact**

### S3 Storage

**Document Storage:**

| Storage Tier | Volume | Cost/GB/Month | Monthly Cost |
|--------------|--------|---------------|--------------|
| S3 Standard | 500 MB | $0.023 | $0.012 |
| S3 IA (backup) | 200 MB | $0.0125 | $0.003 |
| **Total** | - | - | **$0.015** |

**Data Transfer:**

| Direction | Volume/Month | Cost/GB | Monthly Cost |
|-----------|-------------|---------|--------------|
| IN (upload) | 100 MB | Free | $0 |
| OUT (download) | 1 GB | $0.09 | $0.09 |
| **Total** | - | - | **$0.09** |

---

## Cost Monitoring & Alerts

### Recommended Budget Alerts

| Alert Type | Threshold | Action |
|------------|-----------|--------|
| Daily API costs | >$5 | Email notification |
| Monthly API costs | >$50 | Email + pause processing |
| RDS storage | >5 GB | Review data retention |
| Embedding batch failure | >10% | Check API keys/quotas |

### Usage Tracking

**Implement these metrics:**

```python
# Track in database
CREATE TABLE api_usage_logs (
    log_id UUID PRIMARY KEY,
    api_provider VARCHAR(50),  -- 'gemini', 'openai', etc.
    operation_type VARCHAR(50), -- 'embedding', 'query', 'vision'
    tokens_used INTEGER,
    estimated_cost DECIMAL(10,6),
    timestamp TIMESTAMP DEFAULT NOW()
);

# Daily cost query
SELECT
    api_provider,
    operation_type,
    SUM(tokens_used) as total_tokens,
    SUM(estimated_cost) as total_cost
FROM api_usage_logs
WHERE timestamp >= NOW() - INTERVAL '1 day'
GROUP BY api_provider, operation_type;
```

---

## Rate Limits & Quotas

### Google Gemini API

**Free Tier:**
- Embedding API: 1,500 requests/day
- Flash models: 1,500 requests/day
- Our usage: ~500 requests/day (well under limit)

**Paid Tier:**
- Embedding API: 1,000 requests/minute
- Flash models: 1,000 requests/minute
- More than sufficient for our needs

**Current Status:** Free tier is adequate

### Batching Strategy

**Optimal Batch Sizes:**
- Embeddings: 100 texts per request (balance speed/reliability)
- RAG queries: 1 per request (individual user queries)

**Processing Time:**
- 13,820 embeddings ÷ 100 per batch = 139 batches
- 139 batches × 2 sec/batch = 278 seconds = **4.6 minutes**
- With retries/delays: ~15-20 minutes

---

## Cost Projections

### Year 1 Projection

| Month | One-Time | Monthly Recurring | Total/Month |
|-------|----------|-------------------|-------------|
| Month 1 | $10 | $18 | $28 |
| Month 2-6 | $0 | $18 | $18 |
| Month 7-12 | $0 | $20 | $20 |

**Year 1 Total:** $10 + (6 × $18) + (6 × $20) = **$238**

**Breakdown:**
- Infrastructure: $15/month × 12 = $180
- APIs: $3-5/month × 12 = $36-60
- One-time processing: $10

### Scaling Projections

**At 10x Traffic (10K users):**

| Component | Current | At 10x | Cost Increase |
|-----------|---------|--------|---------------|
| RDS | db.t3.micro | db.t3.small | +$15/month |
| Storage | 1 GB | 10 GB | +$1/month |
| RAG queries | 10K/month | 100K/month | +$25/month |
| New embeddings | 200/month | 2,000/month | +$1/month |
| **Total** | **$18/month** | **$60/month** | **+$42/month** |

**Still very affordable at scale**

---

## Cost Optimization Checklist

- [ ] Use local processing (Tesseract, Camelot) instead of cloud APIs
- [ ] Batch embedding requests (100 per call)
- [ ] Cache embeddings to avoid re-processing
- [ ] Use gemini-2.0-flash instead of 2.5-flash for simple queries
- [ ] Consider OpenAI embeddings ($0.18 vs $0.90 for initial load)
- [ ] Monitor daily costs with alerts
- [ ] Use RDS reserved instances after 3 months (33% savings)
- [ ] Implement exponential backoff for API retries
- [ ] Archive old documents to S3 Glacier ($0.004/GB)
- [ ] Use database connection pooling to reduce RDS costs

---

## Break-Even Analysis

**Development Costs:**
- Initial setup: 1 week developer time (~$2,000)
- Pipeline processing: $10
- Monthly maintenance: 2 hours/month (~$100/month)

**vs. Manual Processing:**
- Manual document review: 5 min/doc × 2,800 docs = 233 hours = $4,660
- Manual price extraction: ~$10,000/month

**Savings:** ~$10,000/month in manual labor
**ROI:** Immediate positive ROI

---

## Resources

### API Documentation
- [Gemini API Pricing](https://ai.google.dev/pricing)
- [OpenAI Pricing](https://openai.com/pricing)
- [AWS RDS Pricing](https://aws.amazon.com/rds/postgresql/pricing/)

### Tools for Cost Management
- [Google Cloud Cost Calculator](https://cloud.google.com/products/calculator)
- [AWS Cost Calculator](https://calculator.aws/)
- [OpenAI Usage Dashboard](https://platform.openai.com/usage)

### Monitoring Scripts
```bash
# Daily cost check
python /Users/tamsar/Downloads/nabavkidata/ai/scripts/check_daily_costs.py

# API usage report
python /Users/tamsar/Downloads/nabavkidata/ai/scripts/api_usage_report.py --days 7
```

---

**Last Review:** 2025-11-29
**Next Review:** 2025-12-29 (monthly)
