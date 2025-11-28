# AI Pipeline Specification
Target design for the next-gen RAG/assistant stack. This is a specification only—no code or migrations.

## Goals
- High recall over tenders, epazar data, and documents even when structured fields are sparse.
- Deterministic audit trail for every answer (sources, confidences, fallbacks).
- Tier-aware usage metering and graceful degradation (search fallback, partial answers).

## Embedding Strategy
- **Models:** Primary `text-embedding-3-large` (or Gemini equivalent); backup `text-embedding-3-small` for cost-sensitive tiers.
- **Namespaces:** Separate vectors by domain to improve recall and filtering: `tenders`, `epazar_tenders`, `documents`, `boq_items`, `cpv_reference`.
- **Metadata:** store `tender_id`, `source`, `language`, `cpv_code`, `category`, `publication_date`, `plan_tier_visibility`, `content_hash`.
- **Refresh cadence:** nightly for new/updated records; immediate re-embed on document extraction success; backfill job for legacy documents until 100% coverage.
- **Duplication guard:** hash chunks; skip if hash already exists in vector store; keep version field for regenerated embeddings.

## Chunking Strategy
- **Documents:** sliding window 800 tokens with 200-token overlap; split by headings and tables first, then sentences. Preserve page and section numbers in metadata.
- **Structured fields:** create synthetic snippets for key fields (title, description, cpv_code, values, dates, contacts) joined into small 200–300 token chunks for fast recall.
- **BOQ/line items:** chunk per item; include unit, quantity, lot reference, currency flags.
- **Context budget:** cap total retrieved context per answer to ~2,400 tokens per source type (documents vs. structured) to balance diversity vs. verbosity.

## CPV Extraction from Raw JSON
- **Source:** `tenders.raw_data_json` (currently empty) plus `content_text` heuristics.
- **Pipeline:** keyword/regex prefilter → ML classifier (multilabel) → confidence normalization → CPV hierarchy roll-up to 3–5 digit codes when full code is uncertain.
- **Storage:** write back derived CPV suggestions to an enrichment cache (not DB) with `confidence`, `evidence` (text spans), and `version`.
- **Feedback loop:** when user corrects CPV, log correction for retraining; avoid auto-writing to production tables without manual approval.

## Retrieval and Fallback to Web Search
- **Primary:** vector search with metadata filters (cpv_code/category/date/tier). Require minimum density (e.g., 2+ chunks) before answering.
- **Secondary:** keyword BM25 over `content_text` when vector recall < threshold.
- **Tertiary:** web search fallback (tier-gated) triggered when local corpus returns <2 relevant hits or query is out-of-domain; inject results as low-confidence context labeled `external`.
- **Escalation rules:** if all channels fail, return clarification prompt instead of hallucinating.

## Confidence Scoring
- **Per-chunk score:** weighted sum of vector similarity, metadata match bonus (same tender_id/CPV), recency decay, and extraction quality flags.
- **Answer-level score:** aggregate top-k chunks (e.g., top 6) via weighted mean; penalize cross-source disagreement; downgrade when context is thin (<3 facts).
- **User messaging:** expose score buckets (High/Medium/Low) with tooltips; include why (e.g., "No CPV match; using description similarity only").
- **Tier impact:** free/pro tiers may require higher confidence to return full answers; otherwise return partial + prompt to upgrade or refine query.

## RAG Response Verification
- **Grounding:** every sentence must cite at least one source chunk with tender_id/doc_id and page/section when available.
- **Consistency checks:** detect conflicting numeric values; prefer awarded value over estimated; ensure dates are within publication/open/close ranges; flag currency inconsistencies.
- **Safety rails:** refuse to guess bidder counts when bidder table is sparse; avoid emitting contacts if tier disallows; redact PII on free tier.
- **Post-response audit log:** store question, used sources, scores, and tier in `query_history` (read-only cache) for debugging; no writes to production transactional tables.
- **Regression guard:** periodic benchmark suite with canonical Q&A pairs; fail build if grounding score or factual accuracy drops beyond thresholds.

## Operational Considerations
- **Observability:** metrics for recall hit rate, empty-result rate, fallback usage, and average confidence; structured logs with question → retrieved IDs.
- **Resilience:** cached health check for embeddings DB; circuit breaker on upstream LLM timeouts; retry budget for transient errors.
- **Data quality alignment:** prioritize re-embedding when new CPV backfills arrive; label chunks as `low_quality` when source fields are null to avoid overweighting them.
