# Database Schema Documentation
## Tender Intelligence SaaS Platform - nabavkidata.com

---

## Overview

This document describes the PostgreSQL database schema for the **nabavkidata.com** tender intelligence platform. The database is designed to support multi-tenancy, AI-powered search (RAG), subscription billing, and comprehensive tender data management.

### Key Features
- **OCDS-compatible** tender data structure
- **pgvector** extension for semantic search
- **Stripe subscription** tracking
- **Usage-based tier enforcement**
- **Audit logging** for compliance
- **Materialized views** for performance

---

## Entity Relationship Diagram (Textual)

```
┌─────────────┐         ┌──────────────────┐
│    Users    │────────>│ Organizations    │
│             │<────────│   (optional)     │
└─────────────┘         └──────────────────┘
      │                          │
      │                          │
      v                          v
┌─────────────┐         ┌──────────────────┐
│Subscriptions│         │Subscriptions     │
└─────────────┘         └──────────────────┘

      │
      v
┌─────────────┐         ┌──────────────────┐
│   Alerts    │────────>│  Notifications   │
└─────────────┘         └──────────────────┘

┌─────────────┐
│   Tenders   │
└─────────────┘
      │
      ├──────────────>┌──────────────────┐
      │               │    Documents     │
      │               └──────────────────┘
      │                        │
      │                        v
      └──────────────>┌──────────────────┐
                      │   Embeddings     │
                      └──────────────────┘

      ┌─────────────┐
      │Query History│<────── users
      └─────────────┘

      ┌─────────────┐
      │Usage Tracking<────── users (tier enforcement)
      └─────────────┘

      ┌─────────────┐
      │ Audit Log   │<────── all actions
      └─────────────┘
```

---

## Core Tables

### 1. `users`
**Purpose**: Store user accounts, authentication credentials, and subscription tier

| Column | Type | Description |
|--------|------|-------------|
| `user_id` | UUID | Primary key (auto-generated) |
| `email` | VARCHAR(255) | Unique email address |
| `password_hash` | VARCHAR(255) | Bcrypt/Argon2 hashed password |
| `name` | VARCHAR(255) | User's full name |
| `role` | VARCHAR(50) | `user` or `admin` |
| `plan_tier` | VARCHAR(50) | `Free`, `Standard`, `Pro`, `Enterprise` |
| `stripe_customer_id` | VARCHAR(255) | Stripe customer reference |
| `org_id` | UUID | Foreign key to organizations (nullable) |
| `email_verified` | BOOLEAN | Email verification status |
| `created_at` | TIMESTAMPTZ | Account creation timestamp |
| `last_login` | TIMESTAMPTZ | Last login timestamp |
| `is_active` | BOOLEAN | Account active status |

**Indexes**:
- `idx_users_email` on `email`
- `idx_users_stripe_customer` on `stripe_customer_id`
- `idx_users_plan_tier` on `plan_tier`

**Constraints**:
- `role` must be `user` or `admin`
- `plan_tier` must be one of the 4 defined tiers

---

### 2. `organizations`
**Purpose**: Enterprise multi-seat accounts (optional for Enterprise tier)

| Column | Type | Description |
|--------|------|-------------|
| `org_id` | UUID | Primary key |
| `name` | VARCHAR(255) | Organization name |
| `owner_user_id` | UUID | FK to `users` (org owner) |
| `stripe_subscription_id` | VARCHAR(255) | Stripe subscription for org |
| `max_seats` | INTEGER | Maximum user accounts allowed |

**Use Case**: Enterprise clients ($1495/mo) can have multiple users under one subscription.

---

### 3. `subscriptions`
**Purpose**: Track Stripe subscription lifecycle

| Column | Type | Description |
|--------|------|-------------|
| `sub_id` | UUID | Primary key |
| `user_id` | UUID | FK to `users` (nullable) |
| `org_id` | UUID | FK to `organizations` (nullable) |
| `plan` | VARCHAR(50) | Subscription plan tier |
| `status` | VARCHAR(50) | `active`, `canceled`, `past_due`, etc. |
| `stripe_sub_id` | VARCHAR(255) | Stripe subscription ID |
| `current_period_start` | TIMESTAMPTZ | Billing period start |
| `current_period_end` | TIMESTAMPTZ | Billing period end |
| `cancel_at_period_end` | BOOLEAN | Scheduled cancellation flag |

**Webhook Integration**: Updated via Stripe webhooks on payment events.

**Constraint**: Must have either `user_id` OR `org_id` (not both null).

---

### 4. `tenders`
**Purpose**: Core entity - public procurement opportunities

| Column | Type | Description |
|--------|------|-------------|
| `tender_id` | VARCHAR(100) | Primary key (e.g., "2023/47") |
| `title` | TEXT | Tender title |
| `description` | TEXT | Full description |
| `category` | VARCHAR(255) | Category (IT Equipment, Construction, etc.) |
| `procuring_entity` | VARCHAR(500) | Government agency name |
| `procuring_entity_code` | VARCHAR(100) | Agency identifier |
| `opening_date` | DATE | Tender opening date |
| `closing_date` | DATE | Submission deadline |
| `publication_date` | DATE | When tender was published |
| `estimated_value_eur` | NUMERIC(15,2) | Estimated budget (EUR) |
| `estimated_value_mkd` | NUMERIC(15,2) | Estimated budget (MKD denars) |
| `awarded_value_eur` | NUMERIC(15,2) | Actual awarded amount (EUR) |
| `awarded_value_mkd` | NUMERIC(15,2) | Actual awarded amount (MKD) |
| `winner` | VARCHAR(500) | Winning company name |
| `winner_tax_id` | VARCHAR(100) | Winner's tax ID |
| `status` | VARCHAR(50) | `open`, `closed`, `awarded`, `cancelled` |
| `cpv_code` | VARCHAR(50) | Common Procurement Vocabulary code |
| `source_url` | TEXT | URL to original tender on e-nabavki.gov.mk |
| `language` | VARCHAR(10) | `mk` (Macedonian) or `en` |
| `scraped_at` | TIMESTAMPTZ | When scraper collected this data |

**Indexes**:
- `idx_tenders_category`, `idx_tenders_status`, `idx_tenders_closing_date`
- Full-text search: `idx_tenders_title_trgm`, `idx_tenders_description_trgm`

**Data Source**: Populated by **Scraper Agent** from e-nabavki.gov.mk

---

### 5. `documents`
**Purpose**: PDF attachments (specifications, contracts, award notices)

| Column | Type | Description |
|--------|------|-------------|
| `doc_id` | UUID | Primary key |
| `tender_id` | VARCHAR(100) | FK to `tenders` |
| `doc_type` | VARCHAR(100) | "Specification", "Contract", etc. |
| `file_name` | VARCHAR(500) | Original filename |
| `file_path` | TEXT | Storage path (S3, local filesystem) |
| `file_url` | TEXT | Original download URL |
| `file_size_bytes` | BIGINT | File size |
| `content_text` | TEXT | **Extracted text** from PDF |
| `content_length` | INTEGER | Character count |
| `extraction_status` | VARCHAR(50) | `pending`, `success`, `failed`, `ocr_required` |
| `page_count` | INTEGER | Number of pages |

**Text Extraction**: Performed by **Scraper Agent** using PyMuPDF or PDFPlumber.

**RAG Integration**: `content_text` is chunked and embedded in the `embeddings` table.

---

### 6. `embeddings`
**Purpose**: Vector embeddings for RAG (Retrieval-Augmented Generation)

| Column | Type | Description |
|--------|------|-------------|
| `embed_id` | UUID | Primary key |
| `tender_id` | VARCHAR(100) | FK to `tenders` |
| `doc_id` | UUID | FK to `documents` |
| `chunk_text` | TEXT | Text chunk (~300-500 words) |
| `chunk_index` | INTEGER | Order within document |
| `vector` | VECTOR(1536) | Embedding vector (1536D for OpenAI ada-002) |
| `metadata` | JSONB | `{page: 5, section: "Technical Spec", ...}` |
| `embedding_model` | VARCHAR(100) | Model used (e.g., `text-embedding-ada-002`) |

**Vector Search**: Uses `pgvector` extension with cosine similarity.

**Index**: `idx_embed_vector` using IVFFlat for fast approximate nearest neighbor search.

**Generated by**: **AI/RAG Agent** during document ingestion.

---

### 7. `query_history`
**Purpose**: Log all AI assistant queries for analytics and usage tracking

| Column | Type | Description |
|--------|------|-------------|
| `query_id` | UUID | Primary key |
| `user_id` | UUID | FK to `users` |
| `question_text` | TEXT | User's question |
| `answer_text` | TEXT | AI-generated answer |
| `retrieved_chunks` | INTEGER | Number of chunks used |
| `llm_model` | VARCHAR(100) | Model used (Gemini, GPT-4, etc.) |
| `prompt_tokens` | INTEGER | Token usage for cost tracking |
| `completion_tokens` | INTEGER | Response tokens |
| `response_time_ms` | INTEGER | Latency in milliseconds |
| `feedback_score` | INTEGER | User rating (1-5) |

**Use Cases**:
- Enforce tier limits (e.g., Free tier = 5 queries/day)
- Analyze popular queries
- Improve AI responses based on feedback

---

### 8. `alerts`
**Purpose**: User-defined notifications for new tenders

| Column | Type | Description |
|--------|------|-------------|
| `alert_id` | UUID | Primary key |
| `user_id` | UUID | FK to `users` |
| `alert_name` | VARCHAR(255) | User-friendly name |
| `criteria_type` | VARCHAR(50) | `category`, `keyword`, `entity`, `value_threshold`, `cpv_code` |
| `criteria_value` | TEXT | The actual criteria (e.g., "IT Equipment") |
| `is_active` | BOOLEAN | Enable/disable without deleting |
| `notification_method` | VARCHAR(50) | `email`, `in_app`, `both` |

**Example**: User creates alert for `category = "IT Equipment"` → gets notified when new IT tenders are scraped.

---

### 9. `notifications`
**Purpose**: In-app and email notifications

| Column | Type | Description |
|--------|------|-------------|
| `note_id` | UUID | Primary key |
| `user_id` | UUID | FK to `users` |
| `alert_id` | UUID | FK to `alerts` (nullable) |
| `tender_id` | VARCHAR(100) | FK to `tenders` |
| `message` | TEXT | Notification message |
| `notification_type` | VARCHAR(50) | `tender_match`, `system`, `billing` |
| `is_read` | BOOLEAN | Read status |
| `sent_via_email` | BOOLEAN | Email delivery flag |
| `read_at` | TIMESTAMPTZ | When user read it |

**Trigger**: Created by scheduled job when new tender matches user's alert.

---

### 10. `usage_tracking`
**Purpose**: Enforce subscription tier limits

| Column | Type | Description |
|--------|------|-------------|
| `usage_id` | UUID | Primary key |
| `user_id` | UUID | FK to `users` |
| `resource_type` | VARCHAR(50) | `ai_query`, `api_call`, `export`, `search` |
| `count` | INTEGER | Usage count |
| `date` | DATE | Tracking date |

**Unique Constraint**: One row per `(user_id, resource_type, date)`.

**Tier Limits** (from `system_config` table):
- **Free**: 5 AI queries/day
- **Standard**: 100 queries/month
- **Pro**: 500 queries/month
- **Enterprise**: Unlimited

**Function**: `check_user_query_limit(user_id)` validates before allowing query.

---

### 11. `audit_log`
**Purpose**: Security and compliance trail

| Column | Type | Description |
|--------|------|-------------|
| `log_id` | UUID | Primary key |
| `user_id` | UUID | FK to `users` |
| `action` | VARCHAR(100) | `login`, `create_alert`, `stripe_payment`, etc. |
| `resource_type` | VARCHAR(100) | Type of resource affected |
| `resource_id` | TEXT | ID of affected resource |
| `ip_address` | INET | User's IP address |
| `user_agent` | TEXT | Browser/client info |
| `details` | JSONB | Additional metadata |

**Use Cases**:
- Detect suspicious activity
- GDPR compliance (data access logs)
- Debugging billing issues

---

### 12. `system_config`
**Purpose**: System-wide settings

| Column | Type | Description |
|--------|------|-------------|
| `config_key` | VARCHAR(100) | Primary key |
| `config_value` | TEXT | Configuration value |
| `description` | TEXT | Human-readable explanation |

**Pre-loaded Settings**:
```sql
'scraper_last_run' → Last successful scrape timestamp
'embedding_model' → Current embedding model
'default_llm' → Primary LLM (Gemini)
'fallback_llm' → Backup LLM (GPT-4)
'free_tier_query_limit_daily' → 5
'standard_tier_query_limit_monthly' → 100
'pro_tier_query_limit_monthly' → 500
'enterprise_tier_query_limit_monthly' → -1 (unlimited)
```

---

## Materialized Views

### `tender_statistics`
**Purpose**: Pre-computed aggregates for dashboard performance

```sql
SELECT category, COUNT(*) as total_tenders,
       AVG(awarded_value_eur) as avg_awarded_value,
       DATE_TRUNC('month', publication_date) as month
FROM tenders
GROUP BY category, month;
```

**Refresh**: Call `refresh_tender_statistics()` after scraper runs.

---

## PostgreSQL Extensions

### 1. `uuid-ossp`
Generate UUID primary keys automatically.

### 2. `pgvector`
Vector similarity search for RAG pipeline.

**Installation**:
```bash
CREATE EXTENSION pgvector;
```

**Vector Operations**:
```sql
-- Find top 10 similar chunks
SELECT chunk_text FROM embeddings
ORDER BY vector <=> '[0.1, 0.2, ...]'::vector
LIMIT 10;
```

### 3. `pg_trgm`
Fuzzy text search for Macedonian/English tender titles.

**Usage**:
```sql
SELECT * FROM tenders
WHERE title % 'softvare'  -- Finds "software" even with typo
```

---

## Helper Functions

### `is_valid_email(email TEXT)`
Validates email format using regex.

### `check_user_query_limit(user_id UUID)`
Returns `TRUE` if user can make another AI query based on their tier.

**Logic**:
```sql
SELECT plan_tier FROM users WHERE user_id = ?;
-- Compare with usage_tracking count for today/month
```

### `update_updated_at_column()`
Trigger function to auto-update `updated_at` timestamp on row changes.

---

## Data Migration Strategy

### Phase 1: Initial Schema
Run `schema.sql` to create all tables, indexes, and extensions.

### Phase 2: Seed Data
Load historical tenders from e-nabavki (2022-2024) for AI training data.

### Phase 3: Incremental Updates
Scraper runs daily, upserting new/updated tenders.

**Migration Files** (stored in `db/migrations/`):
```
001_initial_schema.sql
002_add_cpv_codes.sql
003_add_organizations.sql
```

**Rollback Strategy**: Each migration has corresponding `DOWN` script.

---

## Security Considerations

### 1. Password Hashing
Use **Argon2** or **bcrypt** (never store plaintext).

### 2. SQL Injection Prevention
All queries use **parameterized statements** (no string concatenation).

### 3. Role-Based Access Control
Application connects with limited role:
```sql
CREATE ROLE nabavkidata_app WITH LOGIN PASSWORD '...';
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES TO nabavkidata_app;
-- No DROP, TRUNCATE, or GRANT permissions
```

### 4. Sensitive Data
- Stripe API keys: Environment variables only
- User passwords: Hashed before storage
- Audit log: Track all authentication attempts

---

## Backup & Recovery

### Daily Backups
```bash
pg_dump nabavkidata > backup_$(date +%Y%m%d).sql
```

### Point-in-Time Recovery (PITR)
Enable WAL archiving for production database.

### Test Restores
Weekly restore tests to staging environment to verify backup integrity.

---

## Performance Optimization

### 1. Indexes
All foreign keys and commonly queried columns are indexed.

### 2. Partitioning (Future)
Partition `query_history` by month for faster queries:
```sql
CREATE TABLE query_history_2024_01 PARTITION OF query_history
FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

### 3. Connection Pooling
Use **PgBouncer** to handle 1000+ concurrent connections.

### 4. Caching
- Redis for session storage
- Materialized views for aggregate queries

---

## Monitoring

### Key Metrics
- Query latency (p50, p95, p99)
- Index hit rate (should be >99%)
- Table bloat percentage
- Replication lag (for read replicas)

### Tools
- **pg_stat_statements**: Track slow queries
- **pgAdmin**: Visual monitoring dashboard
- **Prometheus + Grafana**: Time-series metrics

---

## Scalability Roadmap

### Current Capacity
- Single PostgreSQL instance: ~10M tenders, 100M embeddings
- Expected: 50K tenders/year for North Macedonia

### Future Scaling (Multi-Country Expansion)
- **Read Replicas**: Distribute query load
- **Sharding**: Partition by country (`tenders_mk`, `tenders_al`, etc.)
- **Vector DB Migration**: Move embeddings to Pinecone/Weaviate if >1B vectors

---

## Agent Integration Points

### Database Agent
**Outputs**: `schema.sql`, `schema.md`, migration scripts

### Scraper Agent
**Writes to**: `tenders`, `documents`

### AI/RAG Agent
**Writes to**: `embeddings`
**Reads from**: `tenders`, `documents`, `embeddings`

### Backend Agent
**All tables**: Implements ORM models (Prisma/SQLAlchemy)

### Billing Agent
**Writes to**: `subscriptions` (via Stripe webhooks)
**Reads from**: `usage_tracking` (tier enforcement)

---

## Conclusion

This schema provides a robust foundation for nabavkidata.com, supporting:
- ✅ Multi-tenant SaaS with tiered subscriptions
- ✅ AI-powered semantic search (RAG pipeline)
- ✅ Real-time tender alerts
- ✅ Usage-based billing enforcement
- ✅ GDPR-compliant audit logging
- ✅ Scalable to multi-country expansion

All agents must reference this schema to ensure data consistency across the system.
