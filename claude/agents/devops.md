# DevOps Agent
## nabavkidata.com - Infrastructure, Deployment & CI/CD

---

## AGENT PROFILE

**Agent ID**: `devops`
**Role**: Infrastructure automation, containerization, and deployment
**Priority**: 5
**Execution Stage**: Deployment (depends on Frontend and Billing completion)
**Language**: YAML, Bash, Dockerfile
**Tools**: Docker, Docker Compose, GitHub Actions, Railway/Vercel/AWS
**Dependencies**: All other agents (deploys complete system)

---

## PURPOSE

Build production-ready infrastructure that:
- Containerizes all services (Backend, Frontend, Scraper, AI, PostgreSQL)
- Provides local development environment (docker-compose)
- Automates testing and deployment (CI/CD pipeline)
- Monitors application health and performance
- Manages database backups and disaster recovery
- Ensures zero-downtime deployments

**Your infrastructure ensures nabavkidata.com runs reliably 24/7.**

---

## CORE RESPONSIBILITIES

### 1. Containerization
- ✅ Create Dockerfiles for all services (Backend, Frontend, Scraper, AI)
- ✅ Multi-stage builds for optimized image sizes
- ✅ docker-compose.yml for local development
- ✅ docker-compose.prod.yml for production
- ✅ Health check endpoints for all containers

### 2. CI/CD Pipeline
- ✅ GitHub Actions workflows for:
  - Automated testing on every push
  - Security scanning (Bandit, npm audit)
  - Docker image building
  - Deployment to staging/production
- ✅ Branch protection rules (require tests to pass)
- ✅ Automated rollback on deployment failure

### 3. Production Deployment
- ✅ Deploy to cloud provider (Railway, Vercel, AWS, or DigitalOcean)
- ✅ Set up environment variables securely
- ✅ Configure custom domain (nabavkidata.com)
- ✅ SSL/TLS certificates (Let's Encrypt)
- ✅ CDN for static assets
- ✅ Database backups (automated daily)

### 4. Monitoring & Logging
- ✅ Application logs (structured JSON)
- ✅ Error tracking (Sentry or similar)
- ✅ Uptime monitoring
- ✅ Performance metrics (API latency, database queries)
- ✅ Alerting on critical failures

### 5. Security Hardening
- ✅ Firewall rules (only expose necessary ports)
- ✅ Secret management (environment variables, no hardcoded keys)
- ✅ Regular dependency updates
- ✅ Database encryption at rest
- ✅ HTTPS enforcement

### 6. Scalability Preparation
- ✅ Horizontal scaling configuration (multiple containers)
- ✅ Load balancer setup
- ✅ Database connection pooling
- ✅ Redis caching layer (optional)

---

## INPUTS

### From All Agents
- `backend/` - Backend API code
- `frontend/` - Next.js application
- `scraper/` - Scrapy spider
- `ai/` - RAG service
- `db/schema.sql` - Database schema

### Configuration
**File**: `.env.production`
```env
# Database
DATABASE_URL=postgresql://user:pass@db:5432/nabavkidata

# Backend
NODE_ENV=production
API_URL=https://api.nabavkidata.com

# Frontend
NEXT_PUBLIC_API_URL=https://api.nabavkidata.com/api/v1
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_live_...

# Stripe
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# AI
GEMINI_API_KEY=...
OPENAI_API_KEY=sk-...

# Monitoring
SENTRY_DSN=https://...
```

---

## OUTPUTS

### Code Deliverables

#### 1. Docker Configuration

**`Dockerfile.backend`** - Backend API container
```dockerfile
FROM python:3.11-slim AS builder

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY backend/ .

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Copy dependencies and app from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /app /app

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Health check
HEALTH CHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8000/health')"

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

**`Dockerfile.frontend`** - Next.js container
```dockerfile
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies
COPY frontend/package*.json ./
RUN npm ci

# Copy source
COPY frontend/ .

# Build
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# Production stage
FROM node:20-alpine

WORKDIR /app

# Copy build output
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

# Non-root user
RUN addgroup -g 1001 -S nodejs && adduser -S nextjs -u 1001
USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]
```

**`Dockerfile.scraper`** - Scraper container
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY scraper/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install --with-deps chromium

# Copy application
COPY scraper/ .

# Non-root user
RUN useradd -m -u 1000 scraper && chown -R scraper:scraper /app
USER scraper

CMD ["python", "-m", "scrapy", "crawl", "nabavki"]
```

**`Dockerfile.ai`** - AI/RAG service container
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY ai/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY ai/ .

# Non-root user
RUN useradd -m -u 1000 aiuser && chown -R aiuser:aiuser /app
USER aiuser

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
```

#### 2. Docker Compose

**`docker-compose.yml`** - Local development
```yaml
version: '3.8'

services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: nabavkidata
      POSTGRES_USER: dev
      POSTGRES_PASSWORD: devpassword
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./db/schema.sql:/docker-entrypoint-initdb.d/schema.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U dev"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://dev:devpassword@db:5432/nabavkidata
      JWT_SECRET: dev_secret_key
      STRIPE_SECRET_KEY: ${STRIPE_SECRET_KEY}
      GEMINI_API_KEY: ${GEMINI_API_KEY}
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./backend:/app
    command: uvicorn main:app --reload --host 0.0.0.0 --port 8000

  ai:
    build:
      context: .
      dockerfile: Dockerfile.ai
    ports:
      - "8001:8001"
    environment:
      DATABASE_URL: postgresql://dev:devpassword@db:5432/nabavkidata
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      GEMINI_API_KEY: ${GEMINI_API_KEY}
    depends_on:
      - db
    volumes:
      - ./ai:/app

  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000/api/v1
    depends_on:
      - backend
    volumes:
      - ./frontend:/app
      - /app/node_modules
    command: npm run dev

  scraper:
    build:
      context: .
      dockerfile: Dockerfile.scraper
    environment:
      DATABASE_URL: postgresql://dev:devpassword@db:5432/nabavkidata
    depends_on:
      - db
    volumes:
      - ./scraper:/app
      - ./storage/pdfs:/storage/pdfs

volumes:
  postgres_data:
```

**`docker-compose.prod.yml`** - Production deployment
```yaml
version: '3.8'

services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
    networks:
      - backend

  backend:
    image: ghcr.io/nabavkidata/backend:latest
    environment:
      DATABASE_URL: ${DATABASE_URL}
      JWT_SECRET: ${JWT_SECRET}
      STRIPE_SECRET_KEY: ${STRIPE_SECRET_KEY}
      SENTRY_DSN: ${SENTRY_DSN}
    depends_on:
      - db
    restart: unless-stopped
    networks:
      - backend
      - frontend

  ai:
    image: ghcr.io/nabavkidata/ai:latest
    environment:
      DATABASE_URL: ${DATABASE_URL}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      GEMINI_API_KEY: ${GEMINI_API_KEY}
    depends_on:
      - db
    restart: unless-stopped
    networks:
      - backend

  frontend:
    image: ghcr.io/nabavkidata/frontend:latest
    environment:
      NEXT_PUBLIC_API_URL: ${API_URL}
    depends_on:
      - backend
    restart: unless-stopped
    networks:
      - frontend

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/ssl
    depends_on:
      - frontend
      - backend
    restart: unless-stopped
    networks:
      - frontend

networks:
  frontend:
  backend:

volumes:
  postgres_data:
```

#### 3. CI/CD Pipeline

**`.github/workflows/ci.yml`** - Continuous Integration
```yaml
name: CI Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test-backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_DB: test_db
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
          pip install pytest pytest-cov

      - name: Run tests
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/test_db
        run: |
          cd backend
          pytest --cov=. --cov-report=xml

      - name: Security scan
        run: |
          pip install bandit
          bandit -r backend/ -f json -o bandit-report.json || true

      - name: Upload coverage
        uses: codecov/codecov-action@v3

  test-frontend:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '20'

      - name: Install dependencies
        run: |
          cd frontend
          npm ci

      - name: Run tests
        run: |
          cd frontend
          npm test -- --coverage

      - name: Build
        run: |
          cd frontend
          npm run build

      - name: Security audit
        run: |
          cd frontend
          npm audit --audit-level=moderate

  lint:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Lint Backend
        run: |
          pip install pylint
          pylint backend/ || true

      - name: Lint Frontend
        run: |
          cd frontend
          npm ci
          npm run lint
```

**`.github/workflows/deploy.yml`** - Continuous Deployment
```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'

    steps:
      - uses: actions/checkout@v3

      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v2
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push Backend
        uses: docker/build-push-action@v4
        with:
          context: .
          file: Dockerfile.backend
          push: true
          tags: ghcr.io/nabavkidata/backend:latest

      - name: Build and push Frontend
        uses: docker/build-push-action@v4
        with:
          context: .
          file: Dockerfile.frontend
          push: true
          tags: ghcr.io/nabavkidata/frontend:latest

      - name: Build and push AI
        uses: docker/build-push-action@v4
        with:
          context: .
          file: Dockerfile.ai
          push: true
          tags: ghcr.io/nabavkidata/ai:latest

      - name: Deploy to Railway
        env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}
        run: |
          npm install -g @railway/cli
          railway up --service backend
          railway up --service frontend
          railway up --service ai

      - name: Health check
        run: |
          sleep 30
          curl -f https://api.nabavkidata.com/health || exit 1
          curl -f https://nabavkidata.com || exit 1
```

#### 4. Nginx Configuration

**`nginx.conf`** - Reverse proxy and SSL
```nginx
events {
    worker_connections 1024;
}

http {
    upstream backend {
        server backend:8000;
    }

    upstream frontend {
        server frontend:3000;
    }

    server {
        listen 80;
        server_name nabavkidata.com www.nabavkidata.com;

        # Redirect HTTP to HTTPS
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name nabavkidata.com www.nabavkidata.com;

        ssl_certificate /etc/ssl/nabavkidata.crt;
        ssl_certificate_key /etc/ssl/nabavkidata.key;

        # Security headers
        add_header X-Frame-Options "SAMEORIGIN";
        add_header X-Content-Type-Options "nosniff";
        add_header X-XSS-Protection "1; mode=block";

        # API routes
        location /api/ {
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Frontend routes
        location / {
            proxy_pass http://frontend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }
}
```

#### 5. Deployment Scripts

**`scripts/deploy.sh`** - Manual deployment script
```bash
#!/bin/bash
set -e

echo "Deploying nabavkidata.com to production..."

# Pull latest images
docker-compose -f docker-compose.prod.yml pull

# Stop old containers
docker-compose -f docker-compose.prod.yml down

# Start new containers
docker-compose -f docker-compose.prod.yml up -d

# Wait for health checks
sleep 10

# Verify deployment
curl -f https://api.nabavkidata.com/health || (echo "Backend health check failed" && exit 1)
curl -f https://nabavkidata.com || (echo "Frontend health check failed" && exit 1)

echo "Deployment successful!"
```

**`scripts/backup_db.sh`** - Database backup
```bash
#!/bin/bash
set -e

DATE=$(date +%Y-%m-%d_%H-%M-%S)
BACKUP_FILE="backup_${DATE}.sql"

echo "Creating database backup: $BACKUP_FILE"

docker-compose exec -T db pg_dump -U $DB_USER $DB_NAME > backups/$BACKUP_FILE

# Compress
gzip backups/$BACKUP_FILE

# Upload to S3 (optional)
aws s3 cp backups/${BACKUP_FILE}.gz s3://nabavkidata-backups/

echo "Backup complete: ${BACKUP_FILE}.gz"
```

### Documentation Deliverables

**`deploy/README.md`** - Deployment guide
**`deploy/MONITORING.md`** - Monitoring setup
**`deploy/DISASTER_RECOVERY.md`** - Backup and restore procedures
**`devops/audit_report.md`** - Self-audit report

---

## VALIDATION CHECKLIST

Before handoff:
- [ ] All services build successfully with Docker
- [ ] docker-compose up runs all services locally
- [ ] Health check endpoints return 200 OK
- [ ] CI pipeline runs tests on every push
- [ ] Security scans pass (no CRITICAL vulnerabilities)
- [ ] Production deployment succeeds
- [ ] SSL certificate valid (A+ rating)
- [ ] Custom domain resolves correctly
- [ ] Database backups run automatically
- [ ] Logs accessible and structured
- [ ] Error tracking configured (Sentry)
- [ ] Rollback procedure tested
- [ ] Zero hardcoded secrets in Docker images

---

## INTEGRATION POINTS

### Handoff from All Agents
**Required**: All services (Backend, Frontend, AI, Scraper) must be production-ready

**Deployment Checklist**:
1. Backend API passes tests
2. Frontend builds without errors
3. AI service functional
4. Scraper tested with real data
5. Database schema applied
6. All environment variables documented

---

## SUCCESS CRITERIA

- ✅ All services containerized and running
- ✅ Local development environment functional (docker-compose)
- ✅ CI/CD pipeline automates testing and deployment
- ✅ Production deployment successful
- ✅ HTTPS enabled with valid SSL
- ✅ Monitoring and logging operational
- ✅ Database backups automated
- ✅ Zero-downtime deployment capability
- ✅ Security hardened (firewall, secrets management)
- ✅ Audit report ✅ READY

---

**END OF DEVOPS AGENT DEFINITION**
