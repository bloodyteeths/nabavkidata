# nabavkidata.com - Macedonian Tender Intelligence Platform

> AI-powered tender search, analysis, and monitoring for Macedonian public procurement

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green)](https://fastapi.tiangolo.com/)

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
- [Development Setup](#development-setup)
- [Testing](#testing)
- [Deployment](#deployment)
- [API Documentation](#api-documentation)
- [Contributing](#contributing)
- [License](#license)

## Overview

**nabavkidata.com** is a comprehensive SaaS platform that transforms how businesses interact with Macedonian public procurement data. The platform scrapes, processes, and analyzes tender data from **e-nabavki.gov.mk**, providing AI-powered search, intelligent notifications, and deep insights into procurement opportunities.

### Problem Statement

- Public tender data is scattered and difficult to search
- Macedonian language content limits accessibility
- No intelligent filtering or personalized alerts
- Procurement documents (PDFs) are hard to analyze at scale
- Competitive intelligence is manual and time-consuming

### Solution

A complete tender intelligence platform featuring:
- **Automated scraping** of tender data and documents
- **AI-powered semantic search** using RAG (Retrieval Augmented Generation)
- **Smart alerts** based on categories, keywords, and entities
- **Multi-language support** (Macedonian and English)
- **Competitive analysis** tracking winners and bid patterns
- **SaaS subscription model** (Free, Standard, Pro, Enterprise)

## Features

### Core Features

#### 1. Tender Data Collection
- **Automated scraping** from e-nabavki.gov.mk
- **Resilient extraction** with multi-fallback selectors
- **Document downloading** (PDF specifications, contracts)
- **Scheduled updates** (daily/hourly scraping)
- **Change detection** and incremental updates

#### 2. AI-Powered Search
- **Semantic search** using vector embeddings (OpenAI/Gemini)
- **RAG-based Q&A** for natural language queries
- **Document content search** (full-text and vector)
- **Multi-language support** (Macedonian, English)
- **Relevance ranking** with confidence scores

#### 3. Smart Notifications
- **Custom alerts** based on:
  - Categories (IT, Construction, Healthcare, etc.)
  - Keywords (technology names, services)
  - Procuring entities (ministries, municipalities)
  - CPV codes (Common Procurement Vocabulary)
  - Value thresholds
- **Email and in-app** notifications
- **Alert frequency** control (instant, daily, weekly)

#### 4. Analytics & Insights
- **Tender statistics** by category, entity, value
- **Competitive intelligence** (winner tracking)
- **Historical trends** and forecasting
- **Export capabilities** (CSV, Excel, PDF)

#### 5. Multi-Tier Subscriptions
- **Free Tier**: 5 AI queries/day, basic search
- **Standard (€99/mo)**: 100 queries/month, alerts, exports
- **Pro (€395/mo)**: 500 queries/month, API access, advanced analytics
- **Enterprise (€1495/mo)**: Unlimited, custom integrations, dedicated support

### Technical Features

- **PostgreSQL + pgvector** for efficient vector search
- **Redis caching** for performance
- **JWT authentication** with role-based access control
- **Stripe integration** for payments
- **Docker containerization** for easy deployment
- **Kubernetes manifests** for cloud scaling
- **Comprehensive logging** and monitoring
- **Rate limiting** and usage tracking
- **RESTful API** with OpenAPI/Swagger docs

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │           Next.js 14 Frontend (React/TypeScript)         │  │
│  │  • Server-side rendering • Tailwind CSS • Zustand       │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ REST API
┌───────────────────────────▼─────────────────────────────────────┐
│                      BACKEND SERVICES                           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │            FastAPI Backend (Python 3.11+)                │  │
│  │  ┌────────────┬──────────────┬──────────────────────┐   │  │
│  │  │ Auth API   │ Tenders API  │ Documents API        │   │  │
│  │  └────────────┴──────────────┴──────────────────────┘   │  │
│  │  ┌────────────┬──────────────┬──────────────────────┐   │  │
│  │  │ RAG API    │ Billing API  │ Admin API            │   │  │
│  │  └────────────┴──────────────┴──────────────────────┘   │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                     AI/ML SERVICES                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  RAG Pipeline  │  Embeddings  │  LLM Integration         │  │
│  │  • OpenAI      │  • text-emb  │  • Gemini Pro           │  │
│  │  • Gemini      │  • Chunking  │  • GPT-4 Fallback       │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                    DATA LAYER                                   │
│  ┌──────────────────────┬──────────────────┬────────────────┐  │
│  │ PostgreSQL 16        │ Redis Cache      │ File Storage   │  │
│  │ • pgvector           │ • Session store  │ • PDFs/Docs    │  │
│  │ • Full-text search   │ • Rate limiting  │ • Embeddings   │  │
│  └──────────────────────┴──────────────────┴────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                  SCRAPING SERVICE                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Scrapy + Playwright Spider                              │  │
│  │  • e-nabavki.gov.mk scraper                              │  │
│  │  • PDF extraction (PyMuPDF, pdfminer, OCR)              │  │
│  │  • Scheduled jobs (cron)                                 │  │
│  │  • Change detection & deduplication                      │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    EXTERNAL SERVICES                            │
│  • Stripe (Payments)  • SMTP (Email)  • Cloud Storage          │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Scraper** → Collects tender data → PostgreSQL
2. **PDF Extractor** → Extracts text from documents → PostgreSQL
3. **Embeddings Pipeline** → Chunks + vectorizes text → pgvector
4. **User Query** → Frontend → Backend API → RAG Pipeline → LLM → Response
5. **Alert System** → Monitors new tenders → Matches criteria → Sends notifications

## Tech Stack

### Frontend
- **Framework**: Next.js 14 (React 18.2, TypeScript 5.3)
- **Styling**: Tailwind CSS 3.4, Radix UI components
- **State Management**: Zustand 4.4
- **Charts**: Recharts 2.10
- **Icons**: Lucide React
- **HTTP Client**: Fetch API

### Backend
- **Framework**: FastAPI 0.109 (Python 3.11+)
- **ORM**: SQLAlchemy 2.0 (async), Alembic migrations
- **Authentication**: JWT (python-jose), bcrypt
- **Validation**: Pydantic 2.5
- **HTTP**: httpx, aiohttp (async)
- **Email**: aiosmtplib
- **Task Queue**: Background tasks (future: Celery/RQ)

### AI/ML
- **LLMs**: OpenAI GPT-4, Google Gemini Pro
- **Embeddings**: OpenAI text-embedding-3-small (1536 dim)
- **Vector Search**: pgvector (IVFFlat index)
- **Framework**: LangChain 0.1
- **Tokenization**: tiktoken

### Database
- **Primary DB**: PostgreSQL 16 with pgvector
- **Extensions**: uuid-ossp, pg_trgm (fuzzy search)
- **Cache**: Redis 7
- **Connection**: asyncpg (async driver)

### Scraping
- **Framework**: Scrapy 2.11
- **Browser**: Playwright 1.40 (headless)
- **PDF**: PyMuPDF (fitz), pdfminer.six, pytesseract (OCR)
- **HTML Parsing**: BeautifulSoup4, html2text

### DevOps
- **Containers**: Docker, Docker Compose
- **Orchestration**: Kubernetes (K8s manifests)
- **Reverse Proxy**: Nginx
- **Monitoring**: Prometheus, Grafana (future)
- **CI/CD**: GitHub Actions (future)
- **Cloud**: AWS/GCP/DigitalOcean ready

### Payments
- **Provider**: Stripe
- **Features**: Subscriptions, webhooks, customer portal

## Quick Start

### Prerequisites

- Docker & Docker Compose installed
- OpenAI API key (for embeddings/LLM)
- Stripe account (for payments, optional for dev)
- 4GB+ RAM available

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/nabavkidata.git
cd nabavkidata
```

### 2. Environment Setup

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your API keys
nano .env
```

**Required environment variables:**

```bash
# Database
DB_NAME=nabavkidata
DB_USER=dev
DB_PASSWORD=devpass

# OpenAI
OPENAI_API_KEY=sk-...

# JWT Secret
JWT_SECRET=your-secret-key-here

# Stripe (optional for local dev)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Email (optional for local dev)
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

### 3. Start Services

```bash
# Start all services with Docker Compose
docker-compose up -d

# Check service health
docker-compose ps
```

Services will be available at:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/api/docs
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

### 4. Initialize Database

```bash
# Database schema is auto-created on first start
# To manually apply schema:
docker exec -i nabavkidata-postgres psql -U dev -d nabavkidata < db/schema.sql
```

### 5. Run Initial Scrape (Optional)

```bash
# Enter scraper container
docker exec -it nabavkidata-scraper bash

# Run spider
cd /app
scrapy crawl nabavki -a limit=10
```

### 6. Access Platform

Open http://localhost:3000 and:
1. Register a new account
2. Verify email (check logs for verification link)
3. Browse tenders
4. Try AI-powered search

## Development Setup

### Local Development (Without Docker)

#### Backend Setup

```bash
cd backend

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql+asyncpg://dev:devpass@localhost:5432/nabavkidata"
export OPENAI_API_KEY="sk-..."
export JWT_SECRET="dev-secret"

# Run development server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Set environment variables
export NEXT_PUBLIC_API_URL="http://localhost:8000/api"

# Run development server
npm run dev
```

#### Scraper Setup

```bash
cd scraper

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Run spider
scrapy crawl nabavki -a limit=10
```

### Database Migrations

```bash
cd backend

# Create migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

### Code Style

We use consistent formatting across the codebase:

**Python:**
```bash
# Format with black
black backend/ scraper/ ai/

# Lint with flake8
flake8 backend/ scraper/ ai/

# Type check with mypy
mypy backend/
```

**TypeScript/JavaScript:**
```bash
# Format with prettier
npm run format

# Lint with ESLint
npm run lint
```

## Testing

### Backend Tests

```bash
cd backend
pytest tests/ -v --cov=. --cov-report=html
```

### Frontend Tests (Future)

```bash
cd frontend
npm test
npm run test:e2e
```

### Integration Tests

```bash
# Run full integration test suite
make test-integration
```

### Load Testing

```bash
# Install k6
brew install k6  # macOS
# or: snap install k6  # Linux

# Run load test
k6 run tests/load/api_load_test.js
```

## Deployment

### Production with Docker Compose

```bash
# Use production compose file
docker-compose -f docker-compose.prod.yml up -d

# With SSL certificates
# Place certs in nginx/ssl/
docker-compose -f docker-compose.prod.yml up -d
```

### Kubernetes Deployment

```bash
# Apply manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/redis.yaml
kubectl apply -f k8s/backend.yaml
kubectl apply -f k8s/frontend.yaml
kubectl apply -f k8s/ingress.yaml

# Check status
kubectl get pods -n nabavkidata
kubectl get services -n nabavkidata
```

### Environment Variables (Production)

**Critical production settings:**

```bash
# Security
JWT_SECRET=<strong-random-secret>  # Generate with: openssl rand -hex 32
ENVIRONMENT=production
DEBUG=false

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@prod-db:5432/nabavkidata

# CORS
CORS_ORIGINS=https://nabavkidata.com,https://www.nabavkidata.com

# Email
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=SG.xxx

# Stripe
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# AI
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...
```

### Monitoring

```bash
# View logs
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f scraper

# Kubernetes logs
kubectl logs -f deployment/backend -n nabavkidata
```

### Backup & Recovery

```bash
# Backup database
docker exec nabavkidata-postgres pg_dump -U dev nabavkidata > backup.sql

# Restore database
docker exec -i nabavkidata-postgres psql -U dev nabavkidata < backup.sql

# Backup embeddings (large!)
docker exec nabavkidata-postgres pg_dump -U dev -t embeddings nabavkidata > embeddings_backup.sql
```

## API Documentation

### Interactive API Docs

- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc
- **OpenAPI JSON**: http://localhost:8000/api/openapi.json

### Key Endpoints

#### Authentication
```
POST /api/auth/register       - Register new user
POST /api/auth/login          - Login (get JWT token)
POST /api/auth/refresh        - Refresh access token
GET  /api/auth/me             - Get current user profile
```

#### Tenders
```
GET  /api/tenders             - List tenders (paginated)
POST /api/tenders/search      - Advanced search
GET  /api/tenders/{id}        - Get tender details
GET  /api/tenders/stats/overview - Statistics
```

#### RAG/AI
```
POST /api/rag/query           - Ask question (RAG)
POST /api/rag/search          - Semantic search
POST /api/rag/embed/document  - Embed document
```

#### Billing
```
GET  /api/billing/plans       - List subscription plans
POST /api/billing/checkout    - Create checkout session
POST /api/billing/portal      - Customer portal link
POST /api/billing/webhook     - Stripe webhook handler
```

For complete API documentation, see [docs/API.md](docs/API.md).

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines.

### Quick Contribution Guide

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes
4. Run tests: `make test`
5. Commit: `git commit -m 'Add amazing feature'`
6. Push: `git push origin feature/amazing-feature`
7. Open a Pull Request

### Development Resources

- [Architecture Documentation](docs/ARCHITECTURE.md)
- [API Reference](docs/API.md)
- [Development Guide](docs/DEVELOPMENT.md)
- [FAQ](docs/FAQ.md)

## Roadmap

### v1.1 (Q1 2025)
- [ ] Mobile app (React Native)
- [ ] Advanced analytics dashboard
- [ ] Email digest notifications
- [ ] Tender comparison tool

### v1.2 (Q2 2025)
- [ ] Multi-language interface (Albanian, Serbian)
- [ ] API rate limiting tiers
- [ ] Webhook integrations
- [ ] Chrome extension

### v2.0 (Q3 2025)
- [ ] Bid recommendation engine
- [ ] Document template generator
- [ ] Tender timeline predictions
- [ ] Procurement network graph

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- **Documentation**: https://docs.nabavkidata.com
- **Email**: support@nabavkidata.com
- **Issues**: https://github.com/yourusername/nabavkidata/issues
- **Discord**: https://discord.gg/nabavkidata

## Acknowledgments

- Data source: [e-nabavki.gov.mk](https://e-nabavki.gov.mk)
- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Powered by [OpenAI](https://openai.com/) and [Google Gemini](https://deepmind.google/technologies/gemini/)
- UI components from [Radix UI](https://www.radix-ui.com/)

---

**Made with ❤️ for the Macedonian procurement ecosystem**

*Last updated: 2025-01-22*
