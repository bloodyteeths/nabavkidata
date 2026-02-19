# System Architecture

> Comprehensive architectural documentation for nabavkidata.com

## Table of Contents

- [System Overview](#system-overview)
- [Architecture Principles](#architecture-principles)
- [Component Architecture](#component-architecture)
- [Database Design](#database-design)
- [API Architecture](#api-architecture)
- [Authentication & Authorization](#authentication--authorization)
- [Data Flow](#data-flow)
- [AI/ML Pipeline](#aiml-pipeline)
- [Scraping Architecture](#scraping-architecture)
- [Scalability Considerations](#scalability-considerations)
- [Security Architecture](#security-architecture)
- [Monitoring & Observability](#monitoring--observability)

## System Overview

### High-Level Architecture

```
                    ┌─────────────────────────────┐
                    │      Load Balancer          │
                    │    (Nginx/CloudFlare)       │
                    └────────────┬────────────────┘
                                 │
                ┌────────────────┼────────────────┐
                │                │                │
        ┌───────▼──────┐  ┌─────▼──────┐  ┌─────▼──────┐
        │   Frontend   │  │  Frontend  │  │  Frontend  │
        │   Instance 1 │  │ Instance 2 │  │ Instance N │
        │  (Next.js)   │  │ (Next.js)  │  │ (Next.js)  │
        └───────┬──────┘  └─────┬──────┘  └─────┬──────┘
                │                │                │
                └────────────────┼────────────────┘
                                 │ HTTP/REST
                    ┌────────────▼────────────┐
                    │    API Gateway          │
                    │  (FastAPI Backend)      │
                    └────────────┬────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
┌───────▼──────┐      ┌──────────▼─────────┐   ┌────────▼────────┐
│   Auth       │      │   Business Logic   │   │   AI/RAG        │
│   Service    │      │   • Tenders        │   │   Pipeline      │
│              │      │   • Documents      │   │                 │
└───────┬──────┘      │   • Billing        │   └────────┬────────┘
        │             │   • Alerts         │            │
        │             └──────────┬─────────┘            │
        │                        │                      │
        └────────────────────────┼──────────────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
┌───────▼──────┐      ┌──────────▼─────────┐   ┌────────▼────────┐
│ PostgreSQL   │      │     Redis          │   │  File Storage   │
│ + pgvector   │      │   (Cache/Queue)    │   │  (S3/Local)     │
└──────────────┘      └────────────────────┘   └─────────────────┘
        │
┌───────▼──────────────────────────────────────────────────┐
│              Background Services                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Scraper    │  │  Embeddings  │  │   Alerts     │  │
│  │   (Scrapy)   │  │   Pipeline   │  │   Scheduler  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└──────────────────────────────────────────────────────────┘
        │                        │                │
        │                        │                │
┌───────▼──────┐      ┌──────────▼─────┐  ┌──────▼──────┐
│  External    │      │   OpenAI       │  │   Stripe    │
│  Websites    │      │   Gemini API   │  │   API       │
└──────────────┘      └────────────────┘  └─────────────┘
```

### Technology Stack Layers

| Layer | Technologies | Purpose |
|-------|-------------|---------|
| **Presentation** | Next.js 14, React 18, TypeScript, Tailwind CSS | User interface, SSR |
| **API Gateway** | FastAPI, Uvicorn | REST API, request routing |
| **Business Logic** | Python 3.11+, SQLAlchemy, Pydantic | Core application logic |
| **AI/ML** | LangChain, OpenAI, Gemini, pgvector | RAG, embeddings, LLM |
| **Data Storage** | PostgreSQL 16, Redis 7 | Relational data, cache |
| **Background Jobs** | Scrapy, asyncio, cron | Web scraping, scheduled tasks |
| **Infrastructure** | Docker, Kubernetes, Nginx | Containerization, orchestration |
| **External** | Stripe, SMTP, Cloud Storage | Payments, email, files |

## Architecture Principles

### Design Philosophy

1. **Separation of Concerns**: Clear boundaries between UI, API, business logic, and data
2. **Microservices-Ready**: Modular design allowing future service decomposition
3. **API-First**: All features exposed via REST API for flexibility
4. **Scalability**: Horizontal scaling for frontend, backend, and scraping
5. **Resilience**: Graceful degradation, fallbacks, error handling
6. **Security**: Defense in depth, least privilege, encryption
7. **Observability**: Comprehensive logging, metrics, tracing

### Key Architectural Patterns

- **RESTful API**: Standard HTTP methods, JSON responses, stateless
- **Repository Pattern**: Data access abstraction (SQLAlchemy ORM)
- **Dependency Injection**: FastAPI's DI for database sessions, services
- **Pipeline Pattern**: RAG query processing, embeddings generation
- **Observer Pattern**: Webhook handlers, event-driven alerts
- **Strategy Pattern**: Multiple LLM providers, fallback strategies

## Component Architecture

### Frontend Architecture

```
frontend/
├── app/                    # Next.js 14 App Router
│   ├── (auth)/            # Authentication pages
│   │   ├── login/
│   │   ├── register/
│   │   └── reset-password/
│   ├── (dashboard)/       # Main application
│   │   ├── tenders/       # Tender list and details
│   │   ├── chat/          # AI assistant
│   │   ├── inbox/         # Notifications
│   │   ├── settings/      # User settings
│   │   └── billing/       # Subscription management
│   ├── admin/             # Admin panel
│   └── layout.tsx         # Root layout
├── components/            # Reusable React components
│   ├── ui/               # Base UI components (Radix)
│   ├── tender/           # Tender-specific components
│   ├── chat/             # Chat interface components
│   └── billing/          # Billing components
├── lib/                  # Utility libraries
│   ├── api.ts           # API client
│   ├── auth.ts          # Auth utilities
│   └── utils.ts         # Helper functions
├── stores/              # Zustand state stores
│   ├── auth.ts         # Auth state
│   ├── tenders.ts      # Tender data
│   └── ui.ts           # UI state
└── config/             # Configuration
    └── navigation.ts   # Menu structure
```

**Key Patterns:**
- **Server Components**: Default for data fetching
- **Client Components**: Interactive elements, state management
- **API Routes**: Minimal use (prefer backend API)
- **Middleware**: Auth checks, redirects
- **State Management**: Zustand for global state, React hooks for local

### Backend Architecture

```
backend/
├── api/                   # API endpoints (routers)
│   ├── auth.py           # Authentication
│   ├── tenders.py        # Tender CRUD
│   ├── documents.py      # Document management
│   ├── rag.py            # RAG/AI queries
│   ├── billing.py        # Stripe integration
│   ├── admin.py          # Admin endpoints
│   └── personalization.py # User preferences
├── services/             # Business logic layer
│   ├── tender_service.py
│   ├── document_service.py
│   ├── billing_service.py
│   └── notification_service.py
├── models/               # SQLAlchemy ORM models
│   ├── models.py         # Core models
│   ├── models_auth.py    # Auth models
│   └── models_billing.py # Billing models
├── schemas/              # Pydantic schemas
│   ├── schemas.py        # Request/response models
│   ├── schemas_auth.py
│   └── schemas_billing.py
├── middleware/           # Custom middleware
│   ├── auth.py          # JWT validation
│   ├── rate_limit.py    # Rate limiting
│   └── logging.py       # Request logging
├── crons/               # Scheduled jobs
│   ├── scraper_trigger.py
│   └── alert_processor.py
├── database.py          # DB connection pool
└── main.py              # FastAPI app entry
```

**Layered Architecture:**

1. **API Layer** (`api/`): HTTP request handling, validation, routing
2. **Service Layer** (`services/`): Business logic, orchestration
3. **Data Layer** (`models/`, `database.py`): ORM, database access
4. **Schema Layer** (`schemas/`): Request/response validation

### AI/ML Architecture

```
ai/
├── rag_query.py          # RAG pipeline orchestration
├── embeddings.py         # Text chunking & embedding
├── llm_client.py         # LLM API clients (OpenAI, Gemini)
├── vector_store.py       # pgvector operations
├── prompt_templates.py   # LLM prompts
└── config.py             # AI configuration
```

**RAG Pipeline Flow:**

```
User Question
      │
      ▼
┌─────────────────┐
│ Query Embedding │  (OpenAI text-embedding-3-small)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Vector Search   │  (pgvector cosine similarity)
│ Top-K Chunks    │  (Default: K=5)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Context Build   │  (Combine chunks + metadata)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Prompt Template │  (System + context + question)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ LLM Generation  │  (Gemini Pro / GPT-4)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Answer + Sources│
└─────────────────┘
```

### Scraper Architecture

```
scraper/
├── scraper/
│   ├── spiders/
│   │   └── nabavki_spider.py   # Main spider
│   ├── items.py                # Data models
│   ├── pipelines.py            # Data processing
│   ├── middlewares.py          # Request handling
│   └── settings.py             # Scrapy config
├── document_parser.py          # PDF extraction
├── pdf_extractor.py            # PDF utilities
├── scheduler.py                # Cron scheduler
└── scripts/
    └── health_check.py         # Monitoring
```

**Scraping Pipeline:**

```
e-nabavki.gov.mk
      │
      ▼
┌─────────────────┐
│ Playwright      │  (Headless browser)
│ Page Load       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Multi-Fallback  │  (Resilient extraction)
│ Field Extraction│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Data Validation │  (Scrapy Items)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Deduplication   │  (Check tender_id)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ PostgreSQL      │  (Store tender data)
│ Insert/Update   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ PDF Download    │  (Document URLs)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Text Extraction │  (PyMuPDF/pdfminer/OCR)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Embedding Queue │  (Background task)
└─────────────────┘
```

## Database Design

### Schema Overview

**Core Tables:**

1. **users**: User accounts, authentication, subscription tier
2. **tenders**: Procurement tender data
3. **documents**: PDF files associated with tenders
4. **embeddings**: Vector embeddings for RAG
5. **subscriptions**: Stripe subscription tracking
6. **alerts**: User-defined notification criteria
7. **notifications**: In-app and email notifications
8. **query_history**: AI query logging and analytics
9. **usage_tracking**: Tier limit enforcement
10. **audit_log**: Security and compliance logging

### Entity-Relationship Diagram

```
┌────────────┐
│   users    │
└─────┬──────┘
      │
      ├─────────────────────────────────┐
      │                                 │
┌─────▼────────┐              ┌────────▼────────┐
│ subscriptions│              │   query_history │
└──────────────┘              └─────────────────┘
      │
┌─────▼──────┐
│   alerts   │
└─────┬──────┘
      │
┌─────▼────────┐
│notifications │
└──────────────┘

┌────────────┐
│  tenders   │◄──────────────────┐
└─────┬──────┘                   │
      │                          │
┌─────▼──────┐         ┌─────────┴──────┐
│ documents  │         │   embeddings   │
└─────┬──────┘         └────────────────┘
      │
      └────────────────►
```

### Key Tables Detail

#### users

| Column | Type | Description |
|--------|------|-------------|
| user_id | UUID | Primary key |
| email | VARCHAR(255) | Unique, indexed |
| password_hash | VARCHAR(255) | bcrypt hash |
| name | VARCHAR(255) | Full name |
| role | VARCHAR(50) | user, admin |
| plan_tier | VARCHAR(50) | Free, Standard, Pro, Enterprise |
| stripe_customer_id | VARCHAR(255) | Stripe customer ID |
| email_verified | BOOLEAN | Email verification status |
| created_at | TIMESTAMP | Account creation |
| last_login | TIMESTAMP | Last login timestamp |

**Indexes:**
- `idx_users_email` (email)
- `idx_users_stripe_customer` (stripe_customer_id)
- `idx_users_plan_tier` (plan_tier)

#### tenders

| Column | Type | Description |
|--------|------|-------------|
| tender_id | VARCHAR(100) | Primary key (e.g., "2023/47") |
| title | TEXT | Tender title |
| description | TEXT | Full description |
| category | VARCHAR(255) | Category (indexed) |
| procuring_entity | VARCHAR(500) | Organization name |
| opening_date | DATE | Tender opening date |
| closing_date | DATE | Submission deadline |
| estimated_value_eur | NUMERIC(15,2) | Estimated value in EUR |
| awarded_value_eur | NUMERIC(15,2) | Actual awarded value |
| status | VARCHAR(50) | open, closed, awarded |
| cpv_code | VARCHAR(50) | CPV classification |
| winner | VARCHAR(500) | Winning bidder |
| source_url | TEXT | Original URL |
| scraped_at | TIMESTAMP | Last scrape time |

**Indexes:**
- `idx_tenders_category` (category)
- `idx_tenders_status` (status)
- `idx_tenders_closing_date` (closing_date)
- `idx_tenders_title_trgm` (GIN for fuzzy search)

#### embeddings

| Column | Type | Description |
|--------|------|-------------|
| embed_id | UUID | Primary key |
| tender_id | VARCHAR(100) | Foreign key → tenders |
| doc_id | UUID | Foreign key → documents |
| chunk_text | TEXT | Text chunk (500-1000 chars) |
| chunk_index | INTEGER | Order within document |
| vector | VECTOR(1536) | Embedding vector |
| metadata | JSONB | {page, section, ...} |
| embedding_model | VARCHAR(100) | Model name |

**Indexes:**
- `idx_embed_vector` (IVFFlat index for similarity search)
- `idx_embed_tender` (tender_id)
- `idx_embed_doc` (doc_id)

**Vector Search Query:**

```sql
SELECT
  embed_id,
  tender_id,
  chunk_text,
  1 - (vector <=> query_vector) AS similarity
FROM embeddings
WHERE tender_id = :tender_id  -- Optional filter
ORDER BY vector <=> query_vector
LIMIT 5;
```

### Database Performance Optimizations

1. **Connection Pooling**: asyncpg with 10-50 connections
2. **Indexes**: Strategic indexes on foreign keys, frequent filters
3. **Materialized Views**: Pre-computed statistics (`tender_statistics`)
4. **Partitioning**: Future: partition `embeddings` by date
5. **Vector Index**: IVFFlat with 100 lists for embeddings
6. **Query Optimization**: EXPLAIN ANALYZE for slow queries

### Data Retention

| Table | Retention | Cleanup Strategy |
|-------|-----------|------------------|
| tenders | Indefinite | Archive old tenders (>5 years) |
| documents | Indefinite | Move to cold storage |
| embeddings | 2 years | Delete old embeddings periodically |
| query_history | 1 year | Aggregate then delete |
| audit_log | 2 years | Archive to object storage |
| notifications | 90 days | Delete read notifications |

## API Architecture

### API Design Principles

1. **RESTful**: Standard HTTP methods (GET, POST, PUT, DELETE)
2. **Versioned**: `/api/v1/...` for future compatibility
3. **Consistent**: Uniform response format, error handling
4. **Documented**: OpenAPI 3.0 spec, auto-generated docs
5. **Validated**: Pydantic schemas for all inputs/outputs
6. **Secured**: JWT authentication, CORS, rate limiting

### API Response Format

**Success Response:**

```json
{
  "data": { ... },
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 150
  }
}
```

**Error Response:**

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Invalid tender ID format",
    "details": {
      "field": "tender_id",
      "expected": "YYYY/NN"
    }
  }
}
```

### Rate Limiting

**Tiers:**

| Tier | Rate Limit | Burst |
|------|-----------|-------|
| Free | 10 req/min | 20 |
| Standard | 60 req/min | 100 |
| Pro | 300 req/min | 500 |
| Enterprise | Unlimited | N/A |

**Implementation:**
- In-memory rate limiter (production: Redis)
- Token bucket algorithm
- Per-user and per-IP tracking
- `X-RateLimit-*` headers in response

### Pagination

**Query Parameters:**
- `page`: Page number (1-indexed)
- `page_size`: Items per page (default: 20, max: 100)

**Response Headers:**
- `X-Total-Count`: Total items
- `Link`: Next/prev/first/last page URLs

## Authentication & Authorization

### Authentication Flow

```
┌──────────┐                ┌──────────┐                ┌──────────┐
│ Client   │                │ Backend  │                │ Database │
└────┬─────┘                └────┬─────┘                └────┬─────┘
     │                           │                           │
     │ POST /auth/login          │                           │
     ├──────────────────────────►│                           │
     │  {email, password}        │                           │
     │                           │ Verify credentials        │
     │                           ├──────────────────────────►│
     │                           │                           │
     │                           │◄──────────────────────────┤
     │                           │ User record               │
     │                           │                           │
     │                           │ Generate JWT              │
     │                           │ (access + refresh)        │
     │                           │                           │
     │◄──────────────────────────┤                           │
     │ {access_token, refresh_token, user}                   │
     │                           │                           │
     │ GET /api/tenders          │                           │
     │ Authorization: Bearer     │                           │
     ├──────────────────────────►│                           │
     │                           │ Verify JWT                │
     │                           │ Extract user_id           │
     │                           │                           │
     │                           │ Fetch data                │
     │                           ├──────────────────────────►│
     │                           │                           │
     │◄──────────────────────────┤                           │
     │ {data: [...]}             │                           │
     │                           │                           │
```

### JWT Structure

**Access Token** (30 min expiry):

```json
{
  "sub": "user_id_uuid",
  "email": "user@example.com",
  "role": "user",
  "plan_tier": "Pro",
  "type": "access",
  "exp": 1704564000,
  "iat": 1704562200
}
```

**Refresh Token** (7 days expiry):

```json
{
  "sub": "user_id_uuid",
  "type": "refresh",
  "exp": 1705168800,
  "iat": 1704562200
}
```

### Authorization Levels

| Role | Permissions |
|------|-------------|
| **user** | View tenders, create alerts, use AI (within tier limits) |
| **admin** | All user permissions + manage users, view analytics, system config |

### Tier-Based Access Control

**Middleware checks:**

```python
async def check_tier_limit(user: User, resource_type: str):
    # Get usage count for today/month
    usage = await get_usage_count(user.user_id, resource_type)

    # Check against tier limit
    limit = TIER_LIMITS[user.plan_tier][resource_type]

    if limit == -1:  # Unlimited (Enterprise)
        return True

    if usage >= limit:
        raise HTTPException(403, "Tier limit exceeded")

    # Increment usage
    await increment_usage(user.user_id, resource_type)
```

## Data Flow

### Tender Ingestion Flow

```
Scraper → PostgreSQL → Embedding Pipeline → pgvector → Search API
   │                         │
   │                         └──► OpenAI API (embeddings)
   │
   └──► Alert Matcher → Notification Service → Email/In-app
```

### User Query Flow

```
Frontend → Backend API → RAG Pipeline → LLM → Response
                │              │           │
                │              ▼           │
                │         Vector Search    │
                │         (pgvector)       │
                │              │           │
                └──────────────┴───────────┘
```

### Billing Flow

```
User → Frontend → Backend → Stripe API → Webhook → Backend → DB Update
  │                                         │
  │                                         └──► Email Notification
  │
  └──► Tier Update → Feature Access Change
```

## AI/ML Pipeline

### Embedding Generation

**Chunk Strategy:**
- **Size**: 500-1000 characters per chunk
- **Overlap**: 100 characters overlap
- **Metadata**: Page number, section, tender_id, doc_id

**Embedding Model:**
- **Primary**: OpenAI `text-embedding-3-small` (1536 dimensions)
- **Fallback**: OpenAI `text-embedding-ada-002`

**Batch Processing:**
- Process documents in batches of 10
- Rate limit: 3000 requests/min (OpenAI tier)
- Retry with exponential backoff

### RAG Query Pipeline

**Steps:**

1. **Query Embedding**: Convert user question to vector
2. **Vector Search**: Find top-K similar chunks (K=5)
3. **Context Building**: Combine chunks with metadata
4. **Prompt Construction**: System + context + question
5. **LLM Generation**: Gemini Pro (fallback: GPT-4)
6. **Response Formatting**: Answer + source citations

**Prompt Template:**

```
System: You are an AI assistant for the Macedonian public procurement platform nabavkidata.com.
Your role is to help users find and understand tender opportunities.
Answer in the same language as the question (Macedonian or English).

Context:
{context_chunks}

Question: {user_question}

Instructions:
- Answer based on the provided context
- Cite specific tenders using [Tender ID]
- If unsure, say "I don't have enough information"
- Be concise but complete
```

### Model Selection Strategy

**Primary LLM**: Google Gemini Pro
- Reason: Cost-effective, good multilingual support
- Fallback: OpenAI GPT-4 Turbo

**Fallback Logic:**

```python
try:
    response = await gemini_client.generate(prompt)
except GeminiError:
    logger.warning("Gemini failed, falling back to GPT-4")
    response = await openai_client.generate(prompt)
```

## Scraping Architecture

### Resilience Strategy

1. **Multi-Fallback Selectors**: Try CSS, XPath, regex, label-based
2. **Content-Based Extraction**: Pattern matching over hardcoded paths
3. **Flexible Field Detection**: Keyword search over positional
4. **Graceful Degradation**: Continue on missing fields
5. **Change Monitoring**: Track extraction success rate

**Example Fallback Chain:**

```python
TITLE_SELECTORS = [
    {"type": "css", "path": "h1.tender-title::text"},
    {"type": "xpath", "path": "//div[@class='title']/text()"},
    {"type": "regex", "pattern": r"<h1[^>]*>([^<]+)</h1>"},
    {"type": "label", "label": "Наслов"}  # Macedonian: "Title"
]
```

### PDF Extraction Pipeline

```
PDF File
   │
   ▼
┌────────────────┐
│ PyMuPDF (fitz) │  (Fast, good for text PDFs)
└────────┬───────┘
         │ If text extraction fails
         ▼
┌────────────────┐
│ pdfminer.six   │  (More robust parser)
└────────┬───────┘
         │ If still fails (scanned PDF)
         ▼
┌────────────────┐
│ Tesseract OCR  │  (Optical Character Recognition)
└────────┬───────┘
         │
         ▼
┌────────────────┐
│ Text Cleaning  │  (Remove artifacts, normalize)
└────────┬───────┘
         │
         ▼
┌────────────────┐
│ Save to DB     │  (documents.content_text)
└────────────────┘
```

### Scheduling

**Cron Schedule:**
- **Full scrape**: Daily at 2:00 AM (low traffic)
- **Incremental**: Every 6 hours
- **Alert processing**: Every 15 minutes
- **Embedding backfill**: Continuous (rate-limited)

## Scalability Considerations

### Horizontal Scaling

**Frontend:**
- Stateless Next.js instances
- Load balancer (Nginx/CloudFlare)
- CDN for static assets

**Backend:**
- Multiple FastAPI instances
- Shared PostgreSQL + Redis
- Session affinity not required (stateless)

**Scraper:**
- Multiple spider instances (distributed Scrapy)
- Deduplication via database unique constraints
- Task queue (future: Celery/RQ)

### Vertical Scaling Limits

| Component | Bottleneck | Scale-Out Solution |
|-----------|-----------|-------------------|
| PostgreSQL | Write throughput | Read replicas, sharding |
| Redis | Memory | Redis Cluster |
| Vector Search | Query latency | Dedicated vector DB (Qdrant, Pinecone) |
| LLM API | Rate limits | Request batching, caching |

### Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| API Response Time (p95) | <200ms | ~150ms |
| Vector Search Latency | <50ms | ~30ms |
| RAG Query Time | <3s | ~2s |
| Scraper Throughput | 1000 tenders/hour | ~800/hour |
| Concurrent Users | 1000 | Tested to 500 |

### Caching Strategy

**Redis Cache:**
- Tender list queries (5 min TTL)
- User sessions (7 days)
- Rate limit counters (1 hour)
- API response cache (1 min)

**Application Cache:**
- Embeddings for frequent queries (in-memory LRU)
- Static configuration (reload on change)

## Security Architecture

### Threat Model

**Threats:**
1. Unauthorized access to user data
2. SQL injection
3. XSS attacks
4. CSRF attacks
5. DDoS attacks
6. API abuse
7. Data breaches

**Mitigations:**
1. JWT authentication, bcrypt passwords
2. Parameterized queries (SQLAlchemy ORM)
3. Content Security Policy, input sanitization
4. SameSite cookies, CSRF tokens
5. Rate limiting, Cloudflare protection
6. Usage quotas, API keys
7. Encryption at rest/transit, audit logging

### Data Security

**Encryption:**
- **At Rest**: PostgreSQL encryption (AES-256)
- **In Transit**: TLS 1.3 (HTTPS)
- **Passwords**: bcrypt (cost factor 12)
- **API Keys**: Encrypted environment variables

**Secrets Management:**
- Environment variables (`.env`)
- Kubernetes secrets (production)
- Never commit secrets to Git
- Rotate secrets quarterly

### Compliance

**GDPR Considerations:**
- User data minimization
- Right to erasure (delete account)
- Data export (JSON format)
- Cookie consent banner
- Privacy policy

## Monitoring & Observability

### Logging

**Log Levels:**
- **DEBUG**: Detailed debugging info
- **INFO**: Normal operations
- **WARNING**: Potential issues
- **ERROR**: Errors requiring attention
- **CRITICAL**: System failures

**Log Aggregation:**
- Structured JSON logging
- Centralized log storage (future: ELK stack)
- Log rotation (10MB per file, keep 3)

**Key Metrics:**

| Metric | Source | Frequency |
|--------|--------|-----------|
| Request rate | Backend | 1 min |
| Error rate | Backend | 1 min |
| Response time | Backend | 1 min |
| DB query time | PostgreSQL | 1 min |
| Scraper success rate | Scraper | 1 hour |
| Embedding queue size | AI pipeline | 5 min |
| LLM API costs | Usage tracking | Daily |

### Health Checks

**Endpoints:**
- `/health`: Basic health check
- `/api/health`: Backend status
- `/api/rag/health`: AI service status

**Health Check Response:**

```json
{
  "status": "healthy",
  "timestamp": "2025-01-22T10:00:00Z",
  "services": {
    "database": "connected",
    "redis": "connected",
    "openai": "configured",
    "gemini": "configured"
  },
  "version": "1.0.0"
}
```

### Alerting (Future)

**Alert Conditions:**
- API error rate > 5%
- Database connection pool exhausted
- Disk usage > 80%
- Scraper failing for >1 hour
- LLM API errors > 10/hour

**Alert Channels:**
- Email notifications
- Slack integration
- PagerDuty (critical)

---

**Document Version**: 1.0
**Last Updated**: 2025-01-22
**Maintained By**: Engineering Team
