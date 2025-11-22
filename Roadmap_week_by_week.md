# CLAUDE‑OPTIMIZED 20‑WEEK IMPLEMENTATION ROADMAP  
# (Machine‑Executable for Multi‑Agent Parallel Development)

######################################################################
# GLOBAL EXECUTION RULES
######################################################################
- All tasks MUST be executed by Claude agents strictly in order inside each week.
- Tasks inside the same week MAY run in parallel IF dependencies are satisfied.
- Every task has:
  • TASK_ID  
  • DESCRIPTION  
  • DEPENDENCIES  
  • ASSIGNED_AGENT  
  • OUTPUT  
  • ACCEPTANCE_CRITERIA  
  • ESCALATION_RULES  
- Every agent MUST produce an internal audit after finishing each task.
- No task may be skipped, merged, or changed unless escalated to Orchestrator.
- ALL code must follow project-wide standards defined in `/claude/rules.md`.
- ALL schemas must follow `/db/schema.md`.

######################################################################
# WEEK 1 — FOUNDATIONS & SYSTEM DEFINITION
######################################################################

## TASK W1-1 — Define System Boundaries
DESCRIPTION: Formalize the entire scope of Tender Intelligence SaaS.
DEPENDENCIES: None  
ASSIGNED_AGENT: Orchestrator Agent  
OUTPUT: `/docs/system_scope.md`  
ACCEPTANCE_CRITERIA:
  - Contains feature list, constraints, and MVP limits.
  - Includes internationalization preparation.
ESCALATION_RULES:
  - If requirements unclear → escalate to Product Architect Agent.

## TASK W1-2 — Create High-Level Architecture
DESCRIPTION: Produce high-level architecture diagram & functional block map.  
DEPENDENCIES: W1-1  
ASSIGNED_AGENT: Architecture Agent  
OUTPUT: `/architecture/high_level_architecture.md`  
ACCEPTANCE_CRITERIA:
  - Includes scraper layer, backend API, AI RAG layer, vector DB, UI layer, billing layer.
  - Includes country-adapter layer.
ESCALATION_RULES:
  - If components unclear → escalate to Orchestrator.

## TASK W1-3 — Select Forkable GitHub Repos
DESCRIPTION: Identify all ready-made repos to integrate.  
DEPENDENCIES: W1-2  
ASSIGNED_AGENT: Research Agent  
OUTPUT: `/integration/repos_selected.md`  
ACCEPTANCE_CRITERIA:
  - At least 1 repo for each: scraper, PDF parser, RAG, vector DB client, Next.js SaaS starter, Stripe.
  - URLs verified.
ESCALATION_RULES:
  - If repo unavailable → choose closest alternative.

######################################################################
# WEEK 2 — PROJECT INITIALIZATION & MONOREPO SETUP
######################################################################

## TASK W2-1 — Create Monorepo Infrastructure
DESCRIPTION: Setup monorepo folder structure (backend/, frontend/, scraper/, ai/, db/, claude/).  
DEPENDENCIES: W1-2  
ASSIGNED_AGENT: DevOps Agent  
OUTPUT: Complete folder tree in repo.  
ACCEPTANCE_CRITERIA:
  - All folders exist with README.md.
  - pnpm or npm workspace configured for frontend/backend.
ESCALATION_RULES:
  - If folder structure conflicts → escalate to Orchestrator.

## TASK W2-2 — Generate Agent Files
DESCRIPTION: Create all agent files and roles.  
DEPENDENCIES: W2-1  
ASSIGNED_AGENT: Orchestrator Agent  
OUTPUT:
  - `/claude/agents/*.md`
  - `/claude/rules.md`
ACCEPTANCE_CRITERIA:
  - 7 agents minimum: Scraper, Backend, Frontend, AI/RAG, Billing, DevOps, QA.
  - Each agent has role, rules, input/output spec.
ESCALATION_RULES:
  - Missing roles → escalate to Orchestrator.

## TASK W2-3 — Prepare Empty API and Service Skeletons
DESCRIPTION: Generate empty service files and starter endpoints.  
DEPENDENCIES: W2-1  
ASSIGNED_AGENT: Backend Agent  
OUTPUT:
  - `/backend/src/index.ts`
  - `/backend/src/modules/*`
ACCEPTANCE_CRITERIA:
  - Server boots in dev mode.
ESCALATION_RULES:
  - Build error → escalate to Backend Lead.

######################################################################
# WEEK 3 — DATABASE & SCHEMA FINALIZATION
######################################################################

## TASK W3-1 — Create Full PostgreSQL Schema
DESCRIPTION: Create schema from scratch based on architecture.
DEPENDENCIES: W1-1, W2-1  
ASSIGNED_AGENT: DB Architect Agent  
OUTPUT: `/db/schema.sql`, `/db/schema.md`
ACCEPTANCE_CRITERIA:
  - Must include: tenders, documents, agencies, companies, awards, embeddings, alerts, users, plans.
  - Includes strict indexing & foreign keys.
ESCALATION_RULES:
  - If schema conflicts with RAG → escalate to AI Agent.

## TASK W3-2 — Implement Prisma Models
DESCRIPTION: Convert schema into ORM models.  
DEPENDENCIES: W3-1  
ASSIGNED_AGENT: Backend Agent  
OUTPUT: `/backend/prisma/schema.prisma`  
ACCEPTANCE_CRITERIA:
  - Prisma migrate up works successfully.
ESCALATION_RULES:
  - Migration errors → escalate to DB Architect.

## WEEK 4 — SCRAPER ENGINE (PHASE I)

### TASK W4-1 — Select Scraper Base Repo  
DESCRIPTION: Fork the strongest scraping repo (Scrapy/Playwright hybrid).  
DEPENDENCIES: W1-3  
ASSIGNED_AGENT: Research Agent  
OUTPUT: `/scraper/BASE_REPO_SELECTED.md`  
ACCEPTANCE_CRITERIA:
  - Repo supports concurrency, retries, captcha bypass or API fallbacks.
ESCALATION_RULES:
  - If repo outdated → pick second-best.

### TASK W4-2 — Implement Nabavki.gov.mk Spider  
DESCRIPTION: Create spider for Macedonia tenders.  
DEPENDENCIES: W4-1  
ASSIGNED_AGENT: Scraper Agent  
OUTPUT: `/scraper/spiders/nabavki_spider.py`  
ACCEPTANCE_CRITERIA:
  - Fetch listing pages, extract tender links.
ESCALATION_RULES:
  - If anti-bot blocks → escalate for proxy rotation.

### TASK W4-3 — Document Parser (HTML + JSON)  
DESCRIPTION: Extract structured tender fields.  
DEPENDENCIES: W4-2  
ASSIGNED_AGENT: Scraper Agent  
OUTPUT: `/scraper/parsers/tender_parser.py`  
ACCEPTANCE_CRITERIA:
  - Extract title, CPV, deadline, agency, documents list.
ESCALATION_RULES:
  - Missing fields → fallback extraction rules added.

### TASK W4-4 — Scheduler & Cron  
DESCRIPTION: Implement scraper scheduler.  
DEPENDENCIES: W4-2  
ASSIGNED_AGENT: DevOps Agent  
OUTPUT: `/scraper/schedule.yaml`  
ACCEPTANCE_CRITERIA:
  - Runs every 3h without human input.
ESCALATION_RULES:
  - Failing runs → automatic retry logic.

---------------------------------------------------------------------

## WEEK 5 — DOCUMENT INGESTION (PDF PIPELINE)

### TASK W5-1 — PDF Downloader  
DESCRIPTION: Download all tender-related PDFs.  
DEPENDENCIES: W4-2  
ASSIGNED_AGENT: Scraper Agent  
OUTPUT: `/scraper/downloaders/pdf_downloader.py`  
ACCEPTANCE_CRITERIA:
  - Handles 20+ MB documents.
ESCALATION_RULES:
  - Timeout → fallback retry queue.

### TASK W5-2 — PDF OCR Pipeline  
DESCRIPTION: Integrate Tesseract/Poppler-based OCR.  
DEPENDENCIES: W5-1  
ASSIGNED_AGENT: AI/RAG Agent  
OUTPUT: `/ai/ocr/ocr_pipeline.py`  
ACCEPTANCE_CRITERIA:
  - Supports Cyrillic + Macedonian text.
ESCALATION_RULES:
  - Low accuracy → fallback to cloud OCR.

### TASK W5-3 — Structured PDF Extractor  
DESCRIPTION: Convert extracted text → structured JSON.  
DEPENDENCIES: W5-2  
ASSIGNED_AGENT: AI/RAG Agent  
OUTPUT: `/ai/ocr/pdf_structured_extractor.py`  
ACCEPTANCE_CRITERIA:
  - Produces normalized fields: requirements, quantities, specs.
ESCALATION_RULES:
  - If messy → add regex cleaning layer.

---------------------------------------------------------------------

## WEEK 6 — DATABASE INGESTION PIPELINE

### TASK W6-1 — Normalize Extracted Data  
DESCRIPTION: Clean & normalize all parsed PDF + HTML fields.  
DEPENDENCIES: W5-3  
ASSIGNED_AGENT: Backend Agent  
OUTPUT: `/backend/src/pipelines/normalizeTender.ts`  
ACCEPTANCE_CRITERIA:
  - Produces consistent DB-ready objects.
ESCALATION_RULES:
  - Data mismatch → escalate to DB Architect.

### TASK W6-2 — Insert Ingestion Pipeline  
DESCRIPTION: Implement pipeline saving tenders & documents.  
DEPENDENCIES: W6-1  
ASSIGNED_AGENT: Backend Agent  
OUTPUT: `/backend/src/pipelines/ingestTender.ts`  
ACCEPTANCE_CRITERIA:
  - Inserts: tender + docs + agencies + pdf text.
ESCALATION_RULES:
  - If duplicates → implement dedup logic.

### TASK W6-3 — Full Scrape → DB Test  
DESCRIPTION: Execute full scrape cycle test.  
DEPENDENCIES: W6-2  
ASSIGNED_AGENT: QA Agent  
OUTPUT: `/reports/scrape_db_test.md`  
ACCEPTANCE_CRITERIA:
  - 100% pages fetched successfully.
ESCALATION_RULES:
  - Missing rows → ping Scraper Agent.

---------------------------------------------------------------------

## WEEK 7 — VECTOR DB & EMBEDDINGS

### TASK W7-1 — Choose Vector DB Repo  
DESCRIPTION: Fork strongest vector DB starter (Weaviate/Pinecone/Supabase Vector).  
DEPENDENCIES: W1-3  
ASSIGNED_AGENT: Research Agent  
OUTPUT: `/ai/vector/vector_repo_selected.md`  
ACCEPTANCE_CRITERIA:
  - Repo supports metadata filters + hybrid search.
ESCALATION_RULES:
  - If unstable → pick alternative.

### TASK W7-2 — Embedding Pipeline  
DESCRIPTION: Build embeddings for all PDFs + tender metadata.  
DEPENDENCIES: W7-1  
ASSIGNED_AGENT: AI/RAG Agent  
OUTPUT: `/ai/embeddings/generate_embeddings.py`  
ACCEPTANCE_CRITERIA:
  - Supports incremental updates.
ESCALATION_RULES:
  - Vector mismatch → re-index.

### TASK W7-3 — RAG Query Engine  
DESCRIPTION: Implement RAG querying with Gemini + metadata filters.  
DEPENDENCIES: W7-2  
ASSIGNED_AGENT: AI/RAG Agent  
OUTPUT: `/ai/rag/query_engine.py`  
ACCEPTANCE_CRITERIA:
  - Accepts natural language queries.
ESCALATION_RULES:
  - Latency >2s → optimize chunk sizes.

---------------------------------------------------------------------

## WEEK 8 — BACKEND API (PHASE I)

### TASK W8-1 — Tender Search API  
DESCRIPTION: Implement full-feature tender search.  
DEPENDENCIES: W6-2  
ASSIGNED_AGENT: Backend Agent  
OUTPUT: `/backend/src/modules/tenders/searchTender.ts`  
ACCEPTANCE_CRITERIA:
  - Supports CPV, date range, free text.
ESCALATION_RULES:
  - Slow queries → escalate to DB Architect.

### TASK W8-2 — Tender Details API  
DESCRIPTION: Serve full tender details.  
DEPENDENCIES: W8-1  
ASSIGNED_AGENT: Backend Agent  
OUTPUT: `/backend/src/modules/tenders/getTender.ts`  
ACCEPTANCE_CRITERIA:
  - Includes documents, metadata, specs.
ESCALATION_RULES:
  - Missing fields → fix normalization.

### TASK W8-3 — AI Insights API  
DESCRIPTION: Endpoint for Gemini-based tender analysis.  
DEPENDENCIES: W7-3  
ASSIGNED_AGENT: AI/RAG Agent  
OUTPUT: `/backend/src/modules/ai/getInsights.ts`  
ACCEPTANCE_CRITERIA:
  - Returns: requirements summary, anomalies, risk score.
ESCALATION_RULES:
  - If hallucination risk → enforce strict grounding.

---------------------------------------------------------------------

## WEEK 9 — USER SYSTEM & AUTH

### TASK W9-1 — User Registration  
DESCRIPTION: Implement secure user registration.  
DEPENDENCIES: W2-3  
ASSIGNED_AGENT: Backend Agent  
OUTPUT: `/backend/src/modules/auth/register.ts`  
ACCEPTANCE_CRITERIA:
  - Email verification included.
ESCALATION_RULES:
  - Delivery issues → escalate to DevOps.

### TASK W9-2 — Login & Sessions  
DESCRIPTION: Implement JWT or session tokens.  
DEPENDENCIES: W9-1  
ASSIGNED_AGENT: Backend Agent  
OUTPUT: `/backend/src/modules/auth/login.ts`  
ACCEPTANCE_CRITERIA:
  - Sessions expire correctly.
ESCALATION_RULES:
  - Session leak → security escalation.

### TASK W9-3 — RBAC for Plans  
DESCRIPTION: Restrict features per plan tier.  
DEPENDENCIES: W9-2  
ASSIGNED_AGENT: Backend Agent  
OUTPUT: `/backend/src/modules/auth/roleGuard.ts`  
ACCEPTANCE_CRITERIA:
  - Free, €99, €395, €1495 tiers enforced.
ESCALATION_RULES:
  - Incorrect gating → escalate to Billing Agent.

---------------------------------------------------------------------

## WEEK 10 — BILLING & STRIPE

### TASK W10-1 — Stripe Integration  
DESCRIPTION: Connect Stripe Billing + webhooks.  
DEPENDENCIES: W9-2  
ASSIGNED_AGENT: Billing Agent  
OUTPUT: `/backend/src/modules/billing/stripe.ts`  
ACCEPTANCE_CRITERIA:
  - Creates subscriptions, upgrades, downgrades.
ESCALATION_RULES:
  - Webhook issues → retry logic.

### TASK W10-2 — Plan Enforcement Backend  
DESCRIPTION: Connect billing tiers to RBAC.  
DEPENDENCIES: W10-1  
ASSIGNED_AGENT: Backend Agent  
OUTPUT: `/backend/src/modules/billing/enforcePlan.ts`  
ACCEPTANCE_CRITERIA:
  - AI queries limited per plan.
ESCALATION_RULES:
  - Abuse → rate limiter added.

### TASK W10-3 — Billing UI  
DESCRIPTION: Create pricing page + upgrade UI.  
DEPENDENCIES: W10-1  
ASSIGNED_AGENT: Frontend Agent  
OUTPUT: `/frontend/pages/billing/*`
ACCEPTANCE_CRITERIA:
  - Stripe checkout works visually.
ESCALATION_RULES:
  - UI errors → escalate to QA Agent.

---------------------------------------------------------------------

## WEEK 11 — FRONTEND (PHASE I)

### TASK W11-1 — React/Next.js App Setup  
DESCRIPTION: Fork Next.js SaaS starter.  
DEPENDENCIES: W2-1  
ASSIGNED_AGENT: Frontend Agent  
OUTPUT: `/frontend/*`  
ACCEPTANCE_CRITERIA:
  - Routing functional.
ESCALATION_RULES:
  - Build error → escalate to DevOps.

### TASK W11-2 — Dashboard UI  
DESCRIPTION: Build tender overview dashboard.  
DEPENDENCIES: W11-1  
ASSIGNED_AGENT: Frontend Agent  
OUTPUT: `/frontend/pages/dashboard.tsx`  
ACCEPTANCE_CRITERIA:
  - Graphs + metrics visible.
ESCALATION_RULES:
  - Slow loading → caching layer.

### TASK W11-3 — Tender Viewer UI  
DESCRIPTION: Present full tender details.  
DEPENDENCIES: W8-2  
ASSIGNED_AGENT: Frontend Agent  
OUTPUT: `/frontend/pages/tender/[id].tsx`  
ACCEPTANCE_CRITERIA:
  - Documents listed + download.
ESCALATION_RULES:
  - Missing fields → fix API.

---------------------------------------------------------------------

## WEEK 12 — FRONTEND (PHASE II)

### TASK W12-1 — AI Chat Interface  
DESCRIPTION: Build AI chat UI for insights.  
DEPENDENCIES: W8-3  
ASSIGNED_AGENT: Frontend Agent  
OUTPUT: `/frontend/pages/ai.tsx`  
ACCEPTANCE_CRITERIA:
  - Supports chat history.
ESCALATION_RULES:
  - Slow → streaming responses.

### TASK W12-2 — Alerts & Notifications UI  
DESCRIPTION: Users set alerts for CPV or agencies.  
DEPENDENCIES: W6-2  
ASSIGNED_AGENT: Frontend Agent  
OUTPUT: `/frontend/pages/alerts.tsx`  
ACCEPTANCE_CRITERIA:
  - Email alerts configurable.
ESCALATION_RULES:
  - Notification issues → escalate.

### TASK W12-3 — Global UI Polish  
DESCRIPTION: Apply consistent design system.  
DEPENDENCIES: W11-3  
ASSIGNED_AGENT: Frontend Agent  
OUTPUT: `/frontend/styles/*`  
ACCEPTANCE_CRITERIA:
  - Responsive layout.
ESCALATION_RULES:
  - Inconsistent components → refactor.

---------------------------------------------------------------------

## WEEK 13 — FULL SYSTEM INTEGRATION

### TASK W13-1 — Scraper → DB → API → UI Integration Test  
DESCRIPTION: Full data flow validation.  
DEPENDENCIES: W12-3  
ASSIGNED_AGENT: QA Agent  
OUTPUT: `/reports/full_integration_test.md`  
ACCEPTANCE_CRITERIA:
  - 0 critical failures.
ESCALATION_RULES:
  - Any break → notify relevant agent.

### TASK W13-2 — AI Pipeline Integration Test  
DESCRIPTION: RAG + Gemini end-to-end test.
DEPENDENCIES: W12-1  
ASSIGNED_AGENT: QA Agent  
OUTPUT: `/reports/ai_pipeline_test.md`
ACCEPTANCE_CRITERIA:
  - >90% accuracy on sample tenders.
ESCALATION_RULES:
  - Low accuracy → escalate to AI Agent.

### TASK W13-3 — Billing Integration Test  
DESCRIPTION: Verify billing enforcement + limits.
DEPENDENCIES: W10-3  
ASSIGNED_AGENT: QA Agent  
OUTPUT: `/reports/billing_test.md`
ACCEPTANCE_CRITERIA:
  - All tiers enforced correctly.
ESCALATION_RULES:
  - Incorrect limits → patch RBAC.

---------------------------------------------------------------------

## WEEK 14 — PERFORMANCE & RELIABILITY


### TASK W14-1 — Scraper Load Test  
DESCRIPTION: Run scraper stress test.  
DEPENDENCIES: W13-1  
ASSIGNED_AGENT: DevOps Agent  
OUTPUT: `/reports/scraper_load_test.md`  
ACCEPTANCE_CRITERIA:
  - Supports 5,000+ pages/hour scraping load without failure.
ESCALATION_RULES:
  - If scraper crashes → auto‑scale workers.

### TASK W14-2 — API Load Test  
DESCRIPTION: High‑traffic API simulation.  
DEPENDENCIES: W13-1  
ASSIGNED_AGENT: QA Agent  
OUTPUT: `/reports/api_load_test.md`  
ACCEPTANCE_CRITERIA:
  - API handles 200 concurrent users.
ESCALATION_RULES:
  - Degradation → caching patch.

### TASK W14-3 — AI Load Test  
DESCRIPTION: Validate AI request throughput.  
DEPENDENCIES: W13-2  
ASSIGNED_AGENT: AI/RAG Agent  
OUTPUT: `/reports/ai_load_test.md`  
ACCEPTANCE_CRITERIA:
  - 50 concurrent queries with <3s latency.
ESCALATION_RULES:
  - Slow → adjust chunking + batching.

---------------------------------------------------------------------

## WEEK 15 — STAGING ENVIRONMENT

### TASK W15-1 — Create Dockerized Environment  
DESCRIPTION: Containerize backend, frontend, scraper, and AI.  
DEPENDENCIES: W14-3  
ASSIGNED_AGENT: DevOps Agent  
OUTPUT: `/deploy/docker-compose.staging.yml`
ACCEPTANCE_CRITERIA:
  - All services build successfully.
ESCALATION_RULES:
  - Build failure → fix Dockerfiles.

### TASK W15-2 — Deploy Staging Cluster  
DESCRIPTION: Deploy staging stack to cloud provider.  
DEPENDENCIES: W15-1  
ASSIGNED_AGENT: DevOps Agent  
OUTPUT: Staging URL live.  
ACCEPTANCE_CRITERIA:
  - All services reachable via staging domain.
ESCALATION_RULES:
  - Network issues → patch firewall rules.

### TASK W15-3 — Staging DB Migration  
DESCRIPTION: Apply schema to staging database.  
DEPENDENCIES: W3-1  
ASSIGNED_AGENT: DB Architect Agent  
OUTPUT: Staging DB ready.  
ACCEPTANCE_CRITERIA:
  - Migrations run cleanly.
ESCALATION_RULES:
  - Migration conflict → schema patch.

---------------------------------------------------------------------

## WEEK 16 — BETA TESTING

### TASK W16-1 — Internal Beta Test  
DESCRIPTION: Run internal testing with staff/AI users.  
DEPENDENCIES: W15-2  
ASSIGNED_AGENT: QA Agent  
OUTPUT: `/reports/internal_beta_report.md`
ACCEPTANCE_CRITERIA:
  - All critical flows validated.
ESCALATION_RULES:
  - Major UI/API bugs → alert responsible agent.

### TASK W16-2 — External Beta Group  
DESCRIPTION: Invite limited users to test.  
DEPENDENCIES: W16-1  
ASSIGNED_AGENT: Product Agent  
OUTPUT: `/reports/external_beta_feedback.md`
ACCEPTANCE_CRITERIA:
  - Collect 30+ valid feedback submissions.
ESCALATION_RULES:
  - Low engagement → expand beta group.

### TASK W16-3 — Bug Prioritization & Fixes  
DESCRIPTION: Fix issues revealed in beta.  
DEPENDENCIES: W16-2  
ASSIGNED_AGENT: Backend/Frontend Agents  
OUTPUT: Patch releases committed.  
ACCEPTANCE_CRITERIA:
  - 100% blocker bugs resolved.
ESCALATION_RULES:
  - Unresolved blockers → escalate to Orchestrator.

---------------------------------------------------------------------

## WEEK 17 — POLISH & HARDENING

### TASK W17-1 — Final UI Polish  
DESCRIPTION: Smooth UI/UX, spacing, typography, responsiveness.  
DEPENDENCIES: W16-3  
ASSIGNED_AGENT: Frontend Agent  
OUTPUT: `/frontend/polish/*`  
ACCEPTANCE_CRITERIA:
  - No broken layouts on any device size.
ESCALATION_RULES:
  - UI regression → re-test.

### TASK W17-2 — Security Hardening  
DESCRIPTION: Conduct security audit + patch vulnerabilities.  
DEPENDENCIES: W16-3  
ASSIGNED_AGENT: DevOps Agent  
OUTPUT: `/reports/security_audit.md`  
ACCEPTANCE_CRITERIA:
  - Pass OWASP Top 10 checklist.
ESCALATION_RULES:
  - Severe risk → hotfix required.

### TASK W17-3 — Production Readiness Checklist  
DESCRIPTION: Final pre-launch verification.  
DEPENDENCIES: W17-2  
ASSIGNED_AGENT: Orchestrator Agent  
OUTPUT: `/docs/production_readiness.md`
ACCEPTANCE_CRITERIA:
  - All critical systems green-checked.
ESCALATION_RULES:
  - Any red item → block launch until fixed.

---------------------------------------------------------------------

## WEEK 18 — PRODUCTION INFRASTRUCTURE

### TASK W18-1 — Create Production Deployment Stack  
DESCRIPTION: Provision live cluster (k8s or Docker swarm).  
DEPENDENCIES: W17-3  
ASSIGNED_AGENT: DevOps Agent  
OUTPUT: `/deploy/production_stack.yml`  
ACCEPTANCE_CRITERIA:
  - Ready to run full SaaS at scale.
ESCALATION_RULES:
  - Scaling issues → adjust resource limits.

### TASK W18-2 — Production DB Setup  
DESCRIPTION: Create primary & replica DB nodes.  
DEPENDENCIES: W18-1  
ASSIGNED_AGENT: DB Architect  
OUTPUT: Production DB cluster live.  
ACCEPTANCE_CRITERIA:
  - Replication functioning.
ESCALATION_RULES:
  - Data inconsistency → re-sync.

### TASK W18-3 — Domain & SSL  
DESCRIPTION: Configure main domain + SSL certificates.  
DEPENDENCIES: W18-1  
ASSIGNED_AGENT: DevOps Agent  
OUTPUT: Live HTTPS domain.  
ACCEPTANCE_CRITERIA:
  - A+ SSL rating.
ESCALATION_RULES:
  - Certificate failure → regenerate.

---------------------------------------------------------------------

## WEEK 19 — GO-LIVE

### TASK W19-1 — Production Deployment  
DESCRIPTION: Release full system publicly.  
DEPENDENCIES: W18-3  
ASSIGNED_AGENT: DevOps Agent  
OUTPUT: Live production URL.  
ACCEPTANCE_CRITERIA:
  - Backend, frontend, scraper, AI all operational.
ESCALATION_RULES:
  - Any crash → rollback + patch.

### TASK W19-2 — Real Data Validation  
DESCRIPTION: Validate live scraper + ingestion.  
DEPENDENCIES: W19-1  
ASSIGNED_AGENT: QA Agent  
OUTPUT: `/reports/live_data_validation.md`  
ACCEPTANCE_CRITERIA:
  - 24h scrape cycle successful.
ESCALATION_RULES:
  - Missing tenders → escalate to Scraper Agent.

### TASK W19-3 — First Paying Users  
DESCRIPTION: Ensure payments + upgrades operational.  
DEPENDENCIES: W19-1  
ASSIGNED_AGENT: Billing Agent  
OUTPUT: Verified first successful Stripe charges.  
ACCEPTANCE_CRITERIA:
  - No failed billing logic.
ESCALATION_RULES:
  - Failed payments → fix webhook logic.

---------------------------------------------------------------------

## WEEK 20 — POST-LAUNCH OPTIMIZATION

### TASK W20-1 — Monitoring & Alerts  
DESCRIPTION: Implement long-term observability stack.  
DEPENDENCIES: W19-1  
ASSIGNED_AGENT: DevOps Agent  
OUTPUT: `/deploy/monitoring/*`  
ACCEPTANCE_CRITERIA:
  - Metrics, logs, alerts functioning.
ESCALATION_RULES:
  - Missing alerts → configure Prometheus/Grafana.

### TASK W20-2 — Performance Tuning  
DESCRIPTION: Optimize slow endpoints & AI queries.  
DEPENDENCIES: W20-1  
ASSIGNED_AGENT: Backend + AI Agents  
OUTPUT: `/reports/performance_tuning.md`  
ACCEPTANCE_CRITERIA:
  - ≥30% reduction in average latency.
ESCALATION_RULES:
  - No improvement → re-profile stack.

### TASK W20-3 — Final Documentation & Handover  
DESCRIPTION: Generate full system documentation with Claude.  
DEPENDENCIES: W20-2  
ASSIGNED_AGENT: Orchestrator Agent  
OUTPUT: `/docs/final_system_docs/*`  
ACCEPTANCE_CRITERIA:
  - Architecture, API, AI, scraper, deployment fully documented.
ESCALATION_RULES:
  - Missing docs → regenerate.

---------------------------------------------------------------------

# END OF 20-WEEK ROADMAP (STANDARD FORMAT)


# CLAUDE‑OPTIMIZED 20‑WEEK IMPLEMENTATION ROADMAP  
# (Machine‑Executable for Multi‑Agent Parallel Development)

######################################################################
# GLOBAL EXECUTION RULES
######################################################################
- Tasks must be executed sequentially inside each week.
- Tasks inside the same week may run in parallel if dependencies allow.
- Each task includes:
  - TASK_ID  
  - DESCRIPTION  
  - DEPENDENCIES  
  - ASSIGNED_AGENT  
  - OUTPUT  
  - ACCEPTANCE_CRITERIA  
  - ESCALATION_RULES  
- Every agent must produce an internal audit after completing each task.
- No task may be skipped or altered without escalation to Orchestrator.
- All code must follow `/claude/rules.md`.
- All database structures must follow `/db/schema.md`.

######################################################################
# WEEK 1 — FOUNDATIONS & SYSTEM DEFINITION
######################################################################

## TASK W1-1 — Define System Boundaries
DESCRIPTION: Define complete scope of Tender Intelligence SaaS.  
DEPENDENCIES: None  
ASSIGNED_AGENT: Orchestrator Agent  
OUTPUT: `/docs/system_scope.md`  
ACCEPTANCE_CRITERIA:
  - MVP features clearly defined.
  - Internationalization prepared.
ESCALATION_RULES:
  - If unclear → escalate to Product Architect.

## TASK W1-2 — Create High-Level Architecture
DESCRIPTION: Create architecture diagrams & functional map.  
DEPENDENCIES: W1-1  
ASSIGNED_AGENT: Architecture Agent  
OUTPUT: `/architecture/high_level_architecture.md`  
ACCEPTANCE_CRITERIA:
  - Covers scraper, backend, RAG, vector DB, UI, billing.
  - Includes modular country adapters.
ESCALATION_RULES:
  - Missing components → escalate to Orchestrator.

## TASK W1-3 — Select Forkable GitHub Repos
DESCRIPTION: Identify ready-to-fork repos for each module.  
DEPENDENCIES: W1-2  
ASSIGNED_AGENT: Research Agent  
OUTPUT: `/integration/repos_selected.md`  
ACCEPTANCE_CRITERIA:
  - Repos selected for scraper, OCR, embedding, RAG, UI, billing.
ESCALATION_RULES:
  - Repo outdated → choose backup.

######################################################################
# WEEK 2 — MONOREPO SETUP & AGENTS
######################################################################

## TASK W2-1 — Create Monorepo Structure
DESCRIPTION: Create `backend/`, `frontend/`, `scraper/`, `ai/`, `db/`, `claude/`.  
DEPENDENCIES: W1-2  
ASSIGNED_AGENT: DevOps Agent  
OUTPUT: Full monorepo tree with READMEs.  
ACCEPTANCE_CRITERIA:
  - PNPM/NPM workspaces functional.
ESCALATION_RULES:
  - Structure conflict → escalate.

## TASK W2-2 — Generate Agent Files
DESCRIPTION: Create agent definition files.  
DEPENDENCIES: W2-1  
ASSIGNED_AGENT: Orchestrator Agent  
OUTPUT:
  - `/claude/agents/*.md`
  - `/claude/rules.md`
ACCEPTANCE_CRITERIA:
  - Minimum 7 agents (Scraper, Backend, Frontend, AI/RAG, Billing, DevOps, QA).
ESCALATION_RULES:
  - Missing roles → escalate.

## TASK W2-3 — Prepare Backend Skeleton
DESCRIPTION: Create empty backend service.  
DEPENDENCIES: W2-1  
ASSIGNED_AGENT: Backend Agent  
OUTPUT:
  - `/backend/src/index.ts`
  - `/backend/src/modules/*`
ACCEPTANCE_CRITERIA:
  - Local dev server boots.
ESCALATION_RULES:
  - Build fails → escalate.

######################################################################
# WEEK 3 — DATABASE & ORM
######################################################################

## TASK W3-1 — Create PostgreSQL Schema
DESCRIPTION: Create schema based on architecture.  
DEPENDENCIES: W1-1, W2-1  
ASSIGNED_AGENT: DB Architect  
OUTPUT: `/db/schema.sql`, `/db/schema.md`  
ACCEPTANCE_CRITERIA:
  - Includes: tenders, documents, agencies, companies, awards, embeddings, alerts, users, plans.
ESCALATION_RULES:
  - Schema conflicts → escalate.

## TASK W3-2 — Implement Prisma Models
DESCRIPTION: Convert schema to Prisma.  
DEPENDENCIES: W3-1  
ASSIGNED_AGENT: Backend Agent  
OUTPUT: `/backend/prisma/schema.prisma`  
ACCEPTANCE_CRITERIA:
  - `prisma migrate dev` runs cleanly.
ESCALATION_RULES:
  - Migration error → review with DB Architect.

######################################################################
# WEEK 4 — SCRAPER ENGINE
######################################################################

## TASK W4-1 — Select Scraper Base Repo
DESCRIPTION: Fork Playwright/Scrapy hybrid.  
DEPENDENCIES: W1-3  
ASSIGNED_AGENT: Research Agent  
OUTPUT: `/scraper/BASE_REPO_SELECTED.md`  
ACCEPTANCE_CRITERIA:
  - Supports concurrency, retries, captcha bypass.
ESCALATION_RULES:
  - Unmaintained → switch repo.

## TASK W4-2 — Implement Nabavki Spider
DESCRIPTION: Spider for Macedonia tenders.  
DEPENDENCIES: W4-1  
ASSIGNED_AGENT: Scraper Agent  
OUTPUT: `/scraper/spiders/nabavki_spider.py`  
ACCEPTANCE_CRITERIA:
  - Listing → detail links extracted.
ESCALATION_RULES:
  - Anti-bot → enable proxies.

## TASK W4-3 — Document Parser (HTML/JSON)
DESCRIPTION: Extract structured tender data.  
DEPENDENCIES: W4-2  
ASSIGNED_AGENT: Scraper Agent  
OUTPUT: `/scraper/parsers/tender_parser.py`  
ACCEPTANCE_CRITERIA:
  - Extracts CPV, dates, documents.
ESCALATION_RULES:
  - Missing fields → fallback methods.

## TASK W4-4 — Scheduler
DESCRIPTION: Create scraper schedule.  
DEPENDENCIES: W4-2  
ASSIGNED_AGENT: DevOps Agent  
OUTPUT: `/scraper/schedule.yaml`  
ACCEPTANCE_CRITERIA:
  - Runs every 3 hours.
ESCALATION_RULES:
  - Schedule failure → retry logic.

######################################################################
# WEEK 5 — PDF PIPELINE
######################################################################

## TASK W5-1 — PDF Downloader
DESCRIPTION: Download all tender PDFs.  
DEPENDENCIES: W4-2  
ASSIGNED_AGENT: Scraper Agent  
OUTPUT: `/scraper/downloaders/pdf_downloader.py`  
ACCEPTANCE_CRITERIA:
  - Handles large PDFs.
ESCALATION_RULES:
  - Timeout → retry queue.

## TASK W5-2 — OCR Pipeline
DESCRIPTION: Integrate Tesseract/Poppler OCR.  
DEPENDENCIES: W5-1  
ASSIGNED_AGENT: AI/RAG Agent  
OUTPUT: `/ai/ocr/ocr_pipeline.py`  
ACCEPTANCE_CRITERIA:
  - Macedonian Cyrillic supported.
ESCALATION_RULES:
  - Poor OCR → cloud fallback.

## TASK W5-3 — Structured PDF Extractor
DESCRIPTION: Convert text → structured JSON.  
DEPENDENCIES: W5-2  
ASSIGNED_AGENT: AI/RAG Agent  
OUTPUT: `/ai/ocr/pdf_structured_extractor.py`  
ACCEPTANCE_CRITERIA:
  - Cleaned specification fields.
ESCALATION_RULES:
  - Messy output → regex cleaner.

######################################################################
# WEEK 6 — INGESTION PIPELINE
######################################################################

## TASK W6-1 — Normalize Extracted Data
DESCRIPTION: Normalize all parsed fields.  
DEPENDENCIES: W5-3  
ASSIGNED_AGENT: Backend Agent  
OUTPUT: `/backend/src/pipelines/normalizeTender.ts`  
ACCEPTANCE_CRITERIA:
  - DB-ready objects.
ESCALATION_RULES:
  - Inconsistency → escalate.

## TASK W6-2 — DB Insertion Pipeline
DESCRIPTION: Save tenders, docs, agencies.  
DEPENDENCIES: W6-1  
ASSIGNED_AGENT: Backend Agent  
OUTPUT: `/backend/src/pipelines/ingestTender.ts`  
ACCEPTANCE_CRITERIA:
  - Deduplicated inserts.
ESCALATION_RULES:
  - Duplicate → implement hashing.

## TASK W6-3 — Scrape → DB Test
DESCRIPTION: Full cycle test.  
DEPENDENCIES: W6-2  
ASSIGNED_AGENT: QA Agent  
OUTPUT: `/reports/scrape_db_test.md`  
ACCEPTANCE_CRITERIA:
  - 100% pages fetched.
ESCALATION_RULES:
  - Missing rows → fix spider.

######################################################################
# WEEK 7 — VECTOR DB & RAG
######################################################################

## TASK W7-1 — Select Vector DB Repo
DESCRIPTION: Pick Weaviate/Pinecone/Supabase Vector.  
DEPENDENCIES: W1-3  
ASSIGNED_AGENT: Research Agent  
OUTPUT: `/ai/vector/vector_repo_selected.md`  
ACCEPTANCE_CRITERIA:
  - Metadata filtering support.
ESCALATION_RULES:
  - Unstable repo → replace.

## TASK W7-2 — Embedding Pipeline
DESCRIPTION: Generate embeddings for all docs.  
DEPENDENCIES: W7-1  
ASSIGNED_AGENT: AI/RAG Agent  
OUTPUT: `/ai/embeddings/generate_embeddings.py`  
ACCEPTANCE_CRITERIA:
  - Incremental updates supported.
ESCALATION_RULES:
  - Mismatch → re-index.

## TASK W7-3 — RAG Query Engine
DESCRIPTION: Gemini-powered factual retrieval.  
DEPENDENCIES: W7-2  
ASSIGNED_AGENT: AI/RAG Agent  
OUTPUT: `/ai/rag/query_engine.py`  
ACCEPTANCE_CRITERIA:
  - Fast, grounded answers.
ESCALATION_RULES:
  - Latency >2s → optimize.

######################################################################
# WEEK 8 — BACKEND API
######################################################################

## TASK W8-1 — Tender Search API
DESCRIPTION: Search by CPV, keywords, date.  
DEPENDENCIES: W6-2  
ASSIGNED_AGENT: Backend Agent  
OUTPUT: `/backend/src/modules/tenders/searchTender.ts`  
ACCEPTANCE_CRITERIA:
  - Indexed, fast queries.
ESCALATION_RULES:
  - Slow → add indices.

## TASK W8-2 — Tender Details API
DESCRIPTION: Serve full tender object.  
DEPENDENCIES: W8-1  
ASSIGNED_AGENT: Backend Agent  
OUTPUT: `/backend/src/modules/tenders/getTender.ts`  
ACCEPTANCE_CRITERIA:
  - All fields present.
ESCALATION_RULES:
  - Missing → fix schema link.

## TASK W8-3 — AI Insights API
DESCRIPTION: AI tender analysis endpoint.  
DEPENDENCIES: W7-3  
ASSIGNED_AGENT: AI/RAG Agent  
OUTPUT: `/backend/src/modules/ai/getInsights.ts`  
ACCEPTANCE_CRITERIA:
  - Requirements summary, risk, anomalies.
ESCALATION_RULES:
  - Hallucination → harder grounding.

######################################################################
# WEEK 9 — USERS & RBAC
######################################################################

## TASK W9-1 — User Registration
DESCRIPTION: Sign-up with email verify.  
DEPENDENCIES: W2-3  
ASSIGNED_AGENT: Backend Agent  
OUTPUT: `/backend/src/modules/auth/register.ts`  
ACCEPTANCE_CRITERIA:
  - Tokens issued.
ESCALATION_RULES:
  - Email fail → fix mailer.

## TASK W9-2 — Login & Sessions
DESCRIPTION: JWT/session management.  
DEPENDENCIES: W9-