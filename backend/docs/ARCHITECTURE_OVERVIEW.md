# Architecture Overview
Static, high-level view of how scraping, API, AI, UI, and billing pieces fit together. No executable code here; use this as a map for audits and onboarding.

## System Topology
```
External sites (e-nabavki, epazar)
           │
     Scraper stack (Scrapy + schedulers)
           │
        PostgreSQL (+pgvector) ──> Object storage (docs/text)
           │
        FastAPI services (auth, tenders, epazar, documents, billing, rag)
           │
      Next.js frontend (SSR/CSR) + Admin console
           │
        Users + AI assistant (chat/RAG)
```

## Data Flow (End-to-End)
```
Scrapers → staging validators → DB write (tenders, epazar_*, documents)
DB → ETL/embedding workers → pgvector embeddings + content_text
API → exposes tenders/docs/analytics/billing/RAG endpoints
Frontend → fetches API → renders routes → AI chat hits RAG → responses returned
Billing/tiers → enforced in API middleware → UI gating + RAG throttling
```

**Dependency chain:** scrapers ➜ PostgreSQL ➜ FastAPI ➜ Next.js UI ➜ RAG/LLM responses. A failure upstream (scraper lag) degrades downstream freshness; API outages block UI and RAG; pgvector/DB issues limit AI recall.

## Scraper Architecture
- **Sources:** primary spider for e-nabavki.gov.mk tenders/documents; secondary spider for epazar (items/offers). Incremental mode by publication date.
- **Execution:** scheduler (cron/CLI) creates jobs; workers run Scrapy spiders; retries/backoff with error counters in `scrape_history`.
- **Validation:** duplicate prevention by `tender_id`/`file_url` hashes; schema validation before DB insert; stuck-job cleanup planned.
- **Persistence:** structured fields into `tenders`, `epazar_tenders`, `epazar_items`, `documents`; raw files to storage; audit log to `scrape_history`.
- **Gaps noted:** epazar financials/CPV missing; product_items under-populated; EUR conversions absent; raw_data_json column currently empty (future AI fallback).

## API Architecture (FastAPI)
- **Routers:** `auth`, `tenders`, `epazar`, `documents`, `billing`, `admin`, `rag`.
- **Layers:** request validation via Pydantic schemas → service layer (SQLAlchemy) → PostgreSQL/pgvector. Dependency injection for DB sessions.
- **Cross-cutting:** JWT auth, role-based admin gating, rate limits per tier, pagination/filter helpers, health checks per subsystem (DB, scraper, RAG).
- **Operational notes:** RAG DSN must be PostgreSQL/asyncpg compliant; billing endpoints expose plan catalog, checkout, webhooks; admin routes for scraper control and audit views.

## RAG Pipeline
- **Ingestion:** documents and tender fields normalized; `content_text` extracted from PDFs; embeddings generated (OpenAI/Gemini) and stored in pgvector alongside metadata.
- **Retrieval:** hybrid search (metadata filter + vector similarity); CPV/category/date filters applied when present.
- **Generation:** retrieved chunks passed to LLM with system prompt; optional rerank; responses streamed to UI. Health endpoint `/api/rag/health` checks model+DB connectivity.
- **Failure modes:** DSN misconfig, empty embeddings table, malformed content_text; fallback to keyword search recommended for empty recalls.

## UI Routes (Next.js app)
- **Public/legal:** `/privacy`, `/terms`.
- **Auth:** `/auth/login`, `/auth/register`, `/auth/forgot-password`, `/auth/reset-password`, `/auth/callback`, `/auth/verify-email`, `/403`.
- **Dashboard hub:** `/dashboard` (wrapper for authenticated workspace).
- **Datasets:** `/tenders`, `/tenders/[id]`, `/epazar`, `/epazar/[id]`, `/products`, `/suppliers`, `/suppliers/[id]`, `/competitors`.
- **Comms/AI:** `/inbox`, `/chat` (AI assistant).
- **Billing:** `/billing`, `/billing/plans`, `/billing/success`, `/billing/cancelled`.
- **Admin:** `/admin`, `/admin/tenders`, `/admin/scraper`, `/admin/monitor`, `/admin/logs`, `/admin/users`, `/admin/broadcast`, `/admin/analytics`.

## Database Schema Summary (Core tables)
- **tenders:** master tender records with status, values (MKD/EUR), CPV, dates, contacts, winner info, raw_data_json (future), search vector indexes.
- **epazar_tenders / epazar_items / epazar_offers:** epazar-specific tenders with items/offers; strong fill rates except financials/CPV.
- **documents / epazar_documents:** PDF metadata, hashes, extraction status, `content_text`, search vectors; linked to tenders.
- **tender_bidders / suppliers / procuring_entities:** participants and authorities; bidders currently represent winners only.
- **product_items:** items extracted from financial bids; mostly empty metadata.
- **cpv_codes:** reference for CPV hierarchy and descriptions.
- **subscriptions / users / user_sessions / usage_tracking:** auth, sessions, plan tiers, and per-resource usage caps.
- **logs & misc:** `scrape_history`, `audit_log`, `system_config`, alert/notification scaffolding.

## Subscription & Tier Logic
- **Catalog:** Free (basic search, 5 RAG queries/month, 1 alert, no exports), Pro (100 RAG queries/month, 10 alerts, exports), Premium (unlimited queries/alerts, API access, analytics).
- **Enforcement points:** middleware checks `plan_tier` against per-resource limits (rag_queries_per_month, saved alerts, exports); RAG endpoints reject with tier errors; UI hides premium-only features; Stripe webhooks update subscription state.
- **Upgrade path:** `/api/billing/plans` for catalog → `/api/billing/checkout` → Stripe webhook → plan/usage updated → UI reflects new tier.

## Data Flow Diagram (Text)
```
[Scrapy spiders] --clean/validate--> [PostgreSQL + files]
     │                                      │
     │ (cron/jobs)                          ├── triggers embeddings → [pgvector]
     │                                      │
     └──────────────▶ [FastAPI] ──SQL/Vector queries──▶ [AI/RAG service]
                                            │
                                     [Next.js UI]
                                            │
                                   [End user + AI chat]
```

## Dependency Chain Notes
- **Scrapers → DB:** freshness and fill rates depend on scraper coverage; stuck jobs delay data.
- **DB → API:** API contracts rely on populated columns and indexes; empty EUR/CPV values propagate gaps.
- **API → UI:** routes render via API responses; missing fields create empty UI slots (e.g., bidders, procedure_type).
- **UI → AI:** AI uses API/RAG endpoints; missing embeddings or raw_data_json reduce recall; tier gating limits usage.
